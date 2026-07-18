"""
Layer 3: LLM observability — optional Langfuse tracing, zero-cost when off.

RESPONSIBILITY:
    The ONLY place the app knows about Langfuse.  Everything else imports
    two things from here:

      - openai_client_classes() → (AsyncOpenAI, OpenAI) classes.  When
        tracing is enabled these are Langfuse's drop-in OpenAI wrappers
        (subclasses of the real SDK clients), so every LLM call made by
        services/llm.py — both providers, failover included — is traced
        with latency, tokens, and cost automatically.  Otherwise they are
        the plain openai SDK classes.

      - observe — Langfuse's @observe decorator when enabled, a no-op
        passthrough otherwise.  Graph nodes and evaluate_control use it,
        so each assessment renders as one nested trace:
        ingest → retrieve → evaluate_control (×N concurrent) → aggregate.

    Tracing is enabled iff LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are
    both set (config.py) AND the langfuse package is importable.  The keys
    are exported to os.environ before importing langfuse because the SDK
    reads its configuration from environment variables.  With no keys the
    langfuse import never happens — no network, no overhead, works in
    demo mode and offline.

IMPORTS FROM: config
IMPORTED BY:  services/llm.py, services/evaluation.py,
              chains/assessment_graph.py
"""

import logging
import os

from config import get_settings

logger = logging.getLogger(__name__)

_enabled: bool | None = None


def tracing_enabled() -> bool:
    """True when Langfuse keys are configured and the SDK is installed.

    Resolved once and cached; reset_tracing() clears (tests/settings
    changes).
    """
    global _enabled
    if _enabled is None:
        s = get_settings()
        if not (s.langfuse_public_key and s.langfuse_secret_key):
            _enabled = False
        else:
            # The langfuse SDK configures itself from env vars; settings
            # may have come from .env, which pydantic does not export.
            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", s.langfuse_public_key)
            os.environ.setdefault("LANGFUSE_SECRET_KEY", s.langfuse_secret_key)
            os.environ.setdefault("LANGFUSE_HOST", s.langfuse_host)
            try:
                import langfuse  # noqa: F401
                _enabled = True
                logger.info(f"Langfuse tracing enabled ({s.langfuse_host})")
            except ImportError:
                logger.warning(
                    "LANGFUSE_* keys are set but the langfuse package is not "
                    "installed — tracing disabled (uv sync to install)"
                )
                _enabled = False
    return _enabled


def openai_client_classes() -> tuple[type, type]:
    """(AsyncOpenAI, OpenAI) — Langfuse drop-in wrappers when tracing."""
    if tracing_enabled():
        from langfuse.openai import AsyncOpenAI, OpenAI
        return AsyncOpenAI, OpenAI
    from openai import AsyncOpenAI, OpenAI
    return AsyncOpenAI, OpenAI


def observe(*args, **kwargs):
    """Langfuse @observe when tracing is enabled, no-op passthrough otherwise.

    Supports both usage forms: @observe and @observe(name="...").
    """
    if tracing_enabled():
        try:
            from langfuse import observe as _observe  # SDK v3
        except ImportError:
            from langfuse.decorators import observe as _observe  # SDK v2
        return _observe(*args, **kwargs)

    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]  # bare @observe

    def passthrough(fn):
        return fn

    return passthrough  # @observe(name="...")


def reset_tracing() -> None:
    """Forget the cached enabled/disabled decision (tests, settings changes)."""
    global _enabled
    _enabled = None
