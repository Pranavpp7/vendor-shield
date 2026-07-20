"""
Layer 3: LLM access — the ONE place the app talks to a language model.

RESPONSIBILITY:
    Every LLM call in the codebase goes through complete()/acomplete()
    (text) or acomplete_tools() (tool-calling, returns the message
    object so callers can run a bounded tool loop).
    This module owns:
      - client singletons (async + sync) for the PRIMARY provider
        (OpenRouter by default) and an optional FALLBACK provider
        (Groq's OpenAI-compatible endpoint by default — its free tier
        hosts llama-3.3-70b-versatile and openai/gpt-oss-120b)
      - JSON mode with automatic retry-without when a provider rejects
        response_format
      - PROVIDER FAILOVER: when the primary is dead for account/model
        reasons (402 insufficient credits, 401 bad key, 404/410 model
        gone/deprecated) — not transient errors — the same call is
        retried once on the fallback provider, loudly logged
      - per-assessment token metering (services/usage)

    Rate limits and 5xx are handled by the SDK's own retries
    (max_retries=5) and are NOT failover triggers: a throttled primary
    is alive, just busy.

    Client classes come from services/tracing: when Langfuse keys are
    configured they are Langfuse's drop-in OpenAI wrappers (tracing every
    call automatically), otherwise the plain openai SDK classes.

    Model changes on EITHER provider must pass the eval gate:
        uv run python evals/run_evals.py

IMPORTS FROM: config, services/usage, services/tracing
IMPORTED BY:  services/evaluation, services/chat, services/followup,
              services/framework_extraction
"""

import logging

from openai import AsyncOpenAI, OpenAI

from config import get_settings
from services.tracing import openai_client_classes
from services.usage import record_usage

logger = logging.getLogger(__name__)

_primary_async: AsyncOpenAI | None = None
_primary_sync: OpenAI | None = None
_fallback_async: AsyncOpenAI | None = None
_fallback_sync: OpenAI | None = None

# Message fragments that mean "this provider/model will not recover on
# its own" — account or model problems, not transient load.
_DEAD_MARKERS = (
    "insufficient credits",
    "invalid api key",
    "no auth credentials",
    "model not found",
    "does not exist",
    "deprecated",
    "decommissioned",
    "discontinued",
)
_DEAD_STATUS = {401, 402, 404, 410}


def _is_provider_dead(exc: Exception) -> bool:
    """True when retrying the same provider is pointless (account/model
    dead), so failover is warranted.  429/5xx are NOT dead — the SDK
    already retried those with backoff."""
    status = getattr(exc, "status_code", None)
    if status in _DEAD_STATUS:
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _DEAD_MARKERS)


def fallback_configured() -> bool:
    return bool(get_settings().fallback_api_key)


def _clients_async() -> tuple[AsyncOpenAI, AsyncOpenAI | None]:
    global _primary_async, _fallback_async
    s = get_settings()
    async_cls, _ = openai_client_classes()
    if _primary_async is None:
        _primary_async = async_cls(
            api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
            max_retries=5,
        )
    if _fallback_async is None and s.fallback_api_key:
        _fallback_async = async_cls(
            api_key=s.fallback_api_key, base_url=s.fallback_base_url,
            max_retries=5,
        )
    return _primary_async, _fallback_async


def _clients_sync() -> tuple[OpenAI, OpenAI | None]:
    global _primary_sync, _fallback_sync
    s = get_settings()
    _, sync_cls = openai_client_classes()
    if _primary_sync is None:
        _primary_sync = sync_cls(
            api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
            max_retries=5,
        )
    if _fallback_sync is None and s.fallback_api_key:
        _fallback_sync = sync_cls(
            api_key=s.fallback_api_key, base_url=s.fallback_base_url,
            max_retries=5,
        )
    return _primary_sync, _fallback_sync


def _kwargs(model: str, messages: list[dict], temperature: float,
            max_tokens: int | None, json_mode: bool) -> dict:
    kw: dict = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kw["max_tokens"] = max_tokens
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    return kw


def _json_mode_rejected(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "response_format" in msg or "json" in msg


def _meter(response, assessment_id: str | None) -> str:
    if assessment_id and response.usage is not None:
        record_usage(
            assessment_id,
            response.usage.prompt_tokens or 0,
            response.usage.completion_tokens or 0,
        )
    return response.choices[0].message.content or ""


async def acomplete(
    messages: list[dict],
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    json_mode: bool = False,
    assessment_id: str | None = None,
) -> str:
    """Async completion with JSON-mode handling and provider failover."""
    settings = get_settings()
    primary, fallback = _clients_async()

    async def _call(client: AsyncOpenAI, model: str) -> str:
        try:
            resp = await client.chat.completions.create(
                **_kwargs(model, messages, temperature, max_tokens, json_mode)
            )
        except Exception as e:
            if not (json_mode and _json_mode_rejected(e)):
                raise
            logger.warning(f"JSON mode rejected by provider, retrying without: {e}")
            resp = await client.chat.completions.create(
                **_kwargs(model, messages, temperature, max_tokens, False)
            )
        return _meter(resp, assessment_id)

    try:
        return await _call(primary, settings.openrouter_model)
    except Exception as e:
        if fallback is None or not _is_provider_dead(e):
            raise
        logger.warning(
            f"PRIMARY LLM provider dead ({e}) — failing over to "
            f"{settings.fallback_base_url} / {settings.fallback_model}"
        )
        return await _call(fallback, settings.fallback_model)


async def acomplete_tools(
    messages: list[dict],
    *,
    tools: list[dict] | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    assessment_id: str | None = None,
):
    """Async completion that returns the full assistant MESSAGE object
    (not just text), so callers can inspect .tool_calls and run a tool
    loop.  Same provider failover and usage metering as acomplete().

    tools: OpenAI function-tool definitions.  None/[] = plain call that
    still returns the message object (used to force a final answer when
    a tool loop hits its turn budget).

    Providers that don't support tool calling raise — the caller
    (services/chat) is responsible for falling back to single-shot RAG.
    """
    settings = get_settings()
    primary, fallback = _clients_async()

    async def _call(client: AsyncOpenAI, model: str):
        kw = _kwargs(model, messages, temperature, max_tokens, False)
        if tools:
            kw["tools"] = tools
        resp = await client.chat.completions.create(**kw)
        if assessment_id and resp.usage is not None:
            record_usage(
                assessment_id,
                resp.usage.prompt_tokens or 0,
                resp.usage.completion_tokens or 0,
            )
        return resp.choices[0].message

    try:
        return await _call(primary, settings.openrouter_model)
    except Exception as e:
        if fallback is None or not _is_provider_dead(e):
            raise
        logger.warning(
            f"PRIMARY LLM provider dead ({e}) — failing over to "
            f"{settings.fallback_base_url} / {settings.fallback_model}"
        )
        return await _call(fallback, settings.fallback_model)


def complete(
    messages: list[dict],
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    json_mode: bool = False,
    assessment_id: str | None = None,
) -> str:
    """Sync completion with JSON-mode handling and provider failover."""
    settings = get_settings()
    primary, fallback = _clients_sync()

    def _call(client: OpenAI, model: str) -> str:
        try:
            resp = client.chat.completions.create(
                **_kwargs(model, messages, temperature, max_tokens, json_mode)
            )
        except Exception as e:
            if not (json_mode and _json_mode_rejected(e)):
                raise
            logger.warning(f"JSON mode rejected by provider, retrying without: {e}")
            resp = client.chat.completions.create(
                **_kwargs(model, messages, temperature, max_tokens, False)
            )
        return _meter(resp, assessment_id)

    try:
        return _call(primary, settings.openrouter_model)
    except Exception as e:
        if fallback is None or not _is_provider_dead(e):
            raise
        logger.warning(
            f"PRIMARY LLM provider dead ({e}) — failing over to "
            f"{settings.fallback_base_url} / {settings.fallback_model}"
        )
        return _call(fallback, settings.fallback_model)


def reset_clients() -> None:
    """Drop client singletons (tests / settings changes)."""
    global _primary_async, _primary_sync, _fallback_async, _fallback_sync
    _primary_async = _primary_sync = _fallback_async = _fallback_sync = None
