"""Tests for the Langfuse tracing shim (services/tracing.py).

The shim must be a perfect no-op when keys are absent (the default in
dev, demo mode, and per-PR CI) and must degrade gracefully — never
crash — when keys are set.  The fully-enabled path is exercised by the
nightly eval workflow, which runs with real Langfuse secrets.
"""

import importlib.util

import pytest

import services.tracing as tracing


@pytest.fixture(autouse=True)
def _fresh_shim():
    tracing.reset_tracing()
    yield
    tracing.reset_tracing()


class _KeylessSettings:
    langfuse_public_key = ""
    langfuse_secret_key = ""
    langfuse_host = "https://cloud.langfuse.com"


class _KeyedSettings:
    langfuse_public_key = "pk-lf-test"
    langfuse_secret_key = "sk-lf-test"
    langfuse_host = "https://cloud.langfuse.com"


def test_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _KeylessSettings())
    assert tracing.tracing_enabled() is False


def test_plain_sdk_classes_when_disabled(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _KeylessSettings())
    from openai import AsyncOpenAI, OpenAI

    assert tracing.openai_client_classes() == (AsyncOpenAI, OpenAI)


def test_observe_is_noop_bare(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _KeylessSettings())

    def fn():
        return 42

    assert tracing.observe(fn) is fn


def test_observe_is_noop_with_name(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _KeylessSettings())

    def fn():
        return 42

    decorated = tracing.observe(name="anything")(fn)
    assert decorated is fn


def test_keys_set_resolves_by_package_presence(monkeypatch):
    """With keys set: enabled iff langfuse is installed — never a crash.

    Locally (langfuse not yet synced) this exercises the degrade path;
    in CI (langfuse in main deps) it exercises the enabled path.
    """
    monkeypatch.setattr(tracing, "get_settings", lambda: _KeyedSettings())
    # Sandbox env writes so the shim can't pollute the real environment.
    monkeypatch.setattr(tracing.os, "environ", {})

    installed = importlib.util.find_spec("langfuse") is not None
    assert tracing.tracing_enabled() is installed

    async_cls, sync_cls = tracing.openai_client_classes()
    assert isinstance(async_cls, type)
    assert isinstance(sync_cls, type)
