"""Shared LLM module — provider-dead classification and failover selection."""

import pytest

import services.llm as llm_mod
from services.llm import _is_provider_dead, complete


class FakeDeadError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class TestProviderDeadClassifier:
    @pytest.mark.parametrize("exc,dead", [
        (FakeDeadError("Insufficient credits. This account never purchased credits."), True),
        (FakeDeadError("whatever", status_code=402), True),
        (FakeDeadError("model not found", status_code=404), True),
        (FakeDeadError("This model has been deprecated"), True),
        (FakeDeadError("Rate limit exceeded", status_code=429), False),   # alive, just busy
        (FakeDeadError("Internal server error", status_code=500), False), # transient
        (FakeDeadError("connection timed out"), False),
    ])
    def test_classification(self, exc, dead):
        assert _is_provider_dead(exc) is dead


class _FakeResponse:
    class _Choice:
        class _Msg:
            content = "FALLBACK-ANSWER"
        message = _Msg()
    choices = [_Choice()]
    usage = None


class _FakeCompletions:
    def __init__(self, fail_with: Exception | None):
        self.fail_with = fail_with
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_with:
            raise self.fail_with
        return _FakeResponse()


class _FakeClient:
    def __init__(self, fail_with: Exception | None = None):
        self.chat = type("chat", (), {})()
        self.chat.completions = _FakeCompletions(fail_with)


class TestFailover:
    def test_dead_primary_fails_over_to_fallback(self, monkeypatch):
        primary = _FakeClient(fail_with=FakeDeadError("Insufficient credits", status_code=402))
        fallback = _FakeClient()
        monkeypatch.setattr(llm_mod, "_clients_sync", lambda: (primary, fallback))
        out = complete([{"role": "user", "content": "hi"}])
        assert out == "FALLBACK-ANSWER"
        assert len(primary.chat.completions.calls) == 1
        # Fallback used the FALLBACK model, not the primary's
        from config import get_settings
        assert fallback.chat.completions.calls[0]["model"] == get_settings().fallback_model

    def test_transient_error_does_not_fail_over(self, monkeypatch):
        primary = _FakeClient(fail_with=FakeDeadError("rate limit", status_code=429))
        fallback = _FakeClient()
        monkeypatch.setattr(llm_mod, "_clients_sync", lambda: (primary, fallback))
        with pytest.raises(FakeDeadError):
            complete([{"role": "user", "content": "hi"}])
        assert fallback.chat.completions.calls == []  # never touched

    def test_dead_primary_without_fallback_raises(self, monkeypatch):
        primary = _FakeClient(fail_with=FakeDeadError("Insufficient credits", status_code=402))
        monkeypatch.setattr(llm_mod, "_clients_sync", lambda: (primary, None))
        with pytest.raises(FakeDeadError):
            complete([{"role": "user", "content": "hi"}])

    def test_json_mode_rejection_retries_without_on_same_provider(self, monkeypatch):
        class JsonPicky(_FakeCompletions):
            def create(self, **kwargs):
                self.calls.append(kwargs)
                if "response_format" in kwargs:
                    raise FakeDeadError("response_format not supported")
                return _FakeResponse()
        primary = _FakeClient()
        primary.chat.completions = JsonPicky(None)
        monkeypatch.setattr(llm_mod, "_clients_sync", lambda: (primary, None))
        out = complete([{"role": "user", "content": "hi"}], json_mode=True)
        assert out == "FALLBACK-ANSWER"
        assert len(primary.chat.completions.calls) == 2  # with, then without
