"""Smart router that picks the right FunctionType for a chat message.

Uses regex rules for the obvious cases and falls back to a small LLM
classification call for ambiguous messages. Returns the user-supplied
fallback if nothing matches.
"""

import re

import structlog

from app.models.conversation import FunctionType
from app.services.openai_client import AzureOpenAIClient

logger = structlog.get_logger(__name__)


_RULES: list[tuple[re.Pattern[str], FunctionType]] = [
    (
        re.compile(
            r"\b(add|log|save|record|enter|put)\s+(?:this|the|a|that)?\s*hazard\b",
            re.IGNORECASE,
        ),
        FunctionType.RISK_REGISTER,
    ),
    (
        re.compile(r"\b(risk\s+register|hazard\s+entry)\b", re.IGNORECASE),
        FunctionType.RISK_REGISTER,
    ),
    (
        re.compile(
            r"\b(?:assess(?:ment)?\s+(?:the|a|this)?\s*risk|"
            r"risk\s+(?:assessment|score|severity|likelihood|matrix|acceptance))\b",
            re.IGNORECASE,
        ),
        FunctionType.SRA,
    ),
    (
        re.compile(r"\b(?:severity|likelihood)\s+(?:of|score|rating)\b", re.IGNORECASE),
        FunctionType.SRA,
    ),
    (re.compile(r"\bSRA\b"), FunctionType.SRA),
    (
        re.compile(
            r"\b(?:identify|list|enumerate|find|show|extract)\s+"
            r"(?:the|all|any|any\s+of\s+the)?\s*hazards?\b",
            re.IGNORECASE,
        ),
        FunctionType.PHL,
    ),
    (
        re.compile(
            r"\b(?:preliminary\s+hazard|hazard\s+(?:list|assessment))\b",
            re.IGNORECASE,
        ),
        FunctionType.PHL,
    ),
    (re.compile(r"\bPHL\b"), FunctionType.PHL),
    (
        re.compile(
            r"\b(?:analy[sz]e|breakdown\s+of)\s+(?:the\s+)?system\b",
            re.IGNORECASE,
        ),
        FunctionType.SYSTEM_ANALYSIS,
    ),
    (
        re.compile(
            r"\bsystem\s+(?:analysis|change|impact|breakdown)\b", re.IGNORECASE
        ),
        FunctionType.SYSTEM_ANALYSIS,
    ),
]


_CLASSIFIER_PROMPT = """You route a user message in an aviation safety AI assistant to the correct mode.

Return EXACTLY ONE of these labels (lowercase, no quotes, no punctuation, no explanation):

- system        — analyze a system, change, or operation (system breakdown, dependencies, impacts)
- phl           — identify, list, or enumerate hazards (Preliminary Hazard List / Hazard Assessment)
- sra           — score or assess risk of a hazard (severity, likelihood, mitigation planning)
- risk_register — ADD, SAVE, or LOG a hazard to the Airport Risk Register
- general       — ordinary question, no specific workflow

Output only the single word label."""


_LABEL_TO_FUNCTION: dict[str, FunctionType] = {
    "system": FunctionType.SYSTEM_ANALYSIS,
    "phl": FunctionType.PHL,
    "sra": FunctionType.SRA,
    "risk_register": FunctionType.RISK_REGISTER,
    "general": FunctionType.GENERAL,
}


async def classify_function(
    message: str,
    openai_client: AzureOpenAIClient,
    fallback: FunctionType,
) -> FunctionType:
    for pattern, fn in _RULES:
        if pattern.search(message):
            logger.info("router_rule_match", function=fn.value)
            return fn

    try:
        raw = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": _CLASSIFIER_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        token = raw.strip().lower().split()[0] if raw and raw.strip() else ""
        if token in _LABEL_TO_FUNCTION:
            logger.info("router_llm_match", function=token)
            return _LABEL_TO_FUNCTION[token]
        logger.info("router_llm_unrecognized", raw=raw[:50] if raw else "")
    except Exception:
        logger.warning("router_llm_failed", exc_info=True)

    return fallback
