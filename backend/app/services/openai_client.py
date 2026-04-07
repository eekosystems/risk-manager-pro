from collections.abc import AsyncGenerator

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
    ) -> str:
        client = await self._get_client()
        try:
            response = await client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            logger.info(
                "chat_completion_success",
                tokens_used=response.usage.total_tokens if response.usage else 0,
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
