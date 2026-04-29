from collections.abc import AsyncGenerator
from typing import Any

import structlog
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import APIStatusError, AsyncAzureOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger(__name__)

_retry_on_rate_limit = retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
)


class AzureOpenAIClient:
    def __init__(self) -> None:
        self._client: AsyncAzureOpenAI | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> AsyncAzureOpenAI:
        if self._client is None:
            if settings.azure_openai_endpoint:
                self._credential = DefaultAzureCredential()
                token_provider = get_bearer_token_provider(
                    self._credential,
                    "https://cognitiveservices.azure.com/.default",
                )
                self._client = AsyncAzureOpenAI(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version=settings.azure_openai_api_version,
                    azure_ad_token_provider=token_provider,
                )
            else:
                logger.warning("azure_openai_not_configured", msg="Using stub — configure endpoint")
                raise RuntimeError("Azure OpenAI endpoint not configured")
        return self._client

    @_retry_on_rate_limit
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        client = await self._get_client()
        try:
            kwargs: dict[str, Any] = {
                "model": settings.azure_openai_deployment_name,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = choice.finish_reason
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            total_tokens = response.usage.total_tokens if response.usage else 0
            if not content:
                logger.warning(
                    "chat_completion_empty_content",
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    max_tokens_requested=max_tokens,
                    message_count=len(messages),
                )
            else:
                logger.info(
                    "chat_completion_success",
                    finish_reason=finish_reason,
                    content_length=len(content),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            return content
        except APIStatusError as e:
            logger.error(
                "openai_api_error",
                status=e.status_code,
                message=str(e.message),
                body=str(e.body) if e.body else None,
            )
            raise

    @_retry_on_rate_limit
    async def chat_completion_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        """Run a chat completion that may emit tool calls.

        Returns a dict with keys:
          - `content`: assistant text (possibly empty if the model only emitted tool calls)
          - `tool_calls`: list of tool-call dicts (each with `id`, `name`, `arguments` (str))
                          — empty list when the model did not call any tools.
          - `finish_reason`: the raw finish reason from the API.

        The caller is responsible for executing tool calls and appending the
        results (role="tool") before re-invoking the model.
        """
        client = await self._get_client()
        try:
            response = await client.chat.completions.create(  # type: ignore[call-overload]
                model=settings.azure_openai_deployment_name,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            choice = response.choices[0]
            raw_tool_calls = choice.message.tool_calls or []
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in raw_tool_calls
            ]
            logger.info(
                "chat_completion_with_tools_success",
                tool_call_count=len(tool_calls),
                finish_reason=choice.finish_reason,
                tokens_used=response.usage.total_tokens if response.usage else 0,
            )
            return {
                "content": choice.message.content or "",
                "tool_calls": tool_calls,
                "finish_reason": choice.finish_reason,
            }
        except APIStatusError as e:
            logger.error(
                "openai_tool_call_error",
                status=e.status_code,
                message=str(e.message),
            )
            raise

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        client = await self._get_client()
        stream = await client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_completion_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @_retry_on_rate_limit
    async def describe_image(self, image_b64: str, prompt: str) -> str:
        """Send a base64-encoded image to GPT-4o vision and return a text description."""
        client = await self._get_client()
        try:
            response = await client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_completion_tokens=1000,
                temperature=0.2,
            )
            content = response.choices[0].message.content or ""
            logger.info(
                "image_description_success",
                tokens_used=response.usage.total_tokens if response.usage else 0,
            )
            return content
        except APIStatusError as e:
            logger.error(
                "image_description_error",
                status=e.status_code,
                message=str(e.message),
            )
            raise

    @_retry_on_rate_limit
    async def embed(self, text: str) -> list[float]:
        client = await self._get_client()
        response = await client.embeddings.create(
            model=settings.azure_openai_embedding_deployment,
            input=text,
        )
        return response.data[0].embedding

    @_retry_on_rate_limit
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        response = await client.embeddings.create(
            model=settings.azure_openai_embedding_deployment,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def close(self) -> None:
        if self._credential:
            await self._credential.close()
        self._client = None
