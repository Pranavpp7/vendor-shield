"""Tests for the chat memory layers.

SHORT-TERM: build_history_messages (services/chat.py) — pure windowing.
LONG-TERM:  services/memory.py — the mem0 wrapper's disabled path, fake-
            client recall/remember, and failure swallowing.  The real
            mem0 pipeline (LLM extraction + Qdrant) is exercised live,
            not in unit tests — conftest sets MEMORY_ENABLED=0.
"""

import pytest

import services.memory as memory_mod
from services.chat import build_history_messages, chat_with_docs


@pytest.fixture(autouse=True)
def _fresh_memory():
    memory_mod.reset_memory()
    yield
    memory_mod.reset_memory()


# ── Short-term: history windowing ────────────────────────────────────────────


def _msg(role, content):
    return {"role": role, "content": content, "timestamp": "2026-07-18T00:00:00"}


class TestHistoryWindow:
    def test_keeps_only_last_window_messages(self):
        history = [_msg("user", f"q{i}") for i in range(20)]
        out = build_history_messages(history, window=6)
        assert len(out) == 6
        assert out[0]["content"] == "q14"
        assert out[-1]["content"] == "q19"

    def test_maps_roles_and_strips_extra_keys(self):
        out = build_history_messages(
            [_msg("user", "hi"), _msg("assistant", "hello")], window=10
        )
        assert out == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

    def test_unknown_roles_become_user_and_empty_dropped(self):
        history = [_msg("system", "x"), _msg("assistant", ""), _msg("user", "ok")]
        out = build_history_messages(history, window=10)
        assert [m["role"] for m in out] == ["user", "user"]

    def test_oversized_message_truncated(self):
        out = build_history_messages([_msg("user", "a" * 10_000)], window=5)
        assert len(out[0]["content"]) == 2000

    def test_zero_window_disables_history(self):
        assert build_history_messages([_msg("user", "hi")], window=0) == []


# ── Long-term: mem0 wrapper ──────────────────────────────────────────────────


class _DisabledSettings:
    memory_enabled = False


class _FakeMem0:
    def __init__(self, search_result=None, add_raises=False):
        self.search_result = search_result if search_result is not None else {}
        self.add_raises = add_raises
        self.added = []
        self.searched = []

    def search(self, query, filters=None, limit=None, user_id=None):
        # mem0 2.x passes filters={'user_id': ...}; 1.x passed user_id=
        scope = (filters or {}).get("user_id", user_id)
        self.searched.append((query, scope, limit))
        return self.search_result

    def add(self, messages, user_id):
        if self.add_raises:
            raise RuntimeError("qdrant down")
        self.added.append((messages, user_id))


def _install_fake(fake):
    memory_mod.reset_memory()
    memory_mod._memory = fake


class TestLongTermMemory:
    def test_disabled_by_settings_is_noop(self, monkeypatch):
        monkeypatch.setattr(memory_mod, "get_settings", lambda: _DisabledSettings())
        assert memory_mod.recall("u1", "anything") == []
        memory_mod.remember("u1", "q", "a")  # must not raise
        assert memory_mod._client() is None

    def test_recall_extracts_memory_strings(self):
        _install_fake(_FakeMem0(search_result={
            "results": [
                {"memory": "org requires SOC 2 Type II"},
                {"memory": ""},          # empty → dropped
                "not-a-dict",            # junk → dropped
                {"other": "no memory key"},
            ]
        }))
        assert memory_mod.recall("u1", "what do we require?") == [
            "org requires SOC 2 Type II"
        ]

    def test_recall_handles_bare_list_shape(self):
        _install_fake(_FakeMem0(search_result=[{"memory": "old-shape hit"}]))
        assert memory_mod.recall("u1", "q") == ["old-shape hit"]

    def test_empty_user_id_scoped_to_default_analyst(self):
        fake = _FakeMem0(search_result={"results": []})
        _install_fake(fake)
        memory_mod.recall("", "q")
        assert fake.searched[0][1] == "default-analyst"

    def test_remember_stores_exchange(self):
        fake = _FakeMem0()
        _install_fake(fake)
        memory_mod.remember("u1", "question?", "answer.")
        (messages, user_id), = fake.added
        assert user_id == "u1"
        assert [m["role"] for m in messages] == ["user", "assistant"]

    def test_remember_swallows_failures(self):
        _install_fake(_FakeMem0(add_raises=True))
        memory_mod.remember("u1", "q", "a")  # must not raise


# ── Prompt assembly: both layers land in the right places ────────────────────


class TestChatPromptAssembly:
    @pytest.mark.asyncio
    async def test_history_and_memories_in_messages(self, monkeypatch):
        captured = {}

        async def fake_acomplete(messages, **kw):
            captured["messages"] = messages
            return "reply"

        monkeypatch.setattr("services.chat.acomplete", fake_acomplete)
        monkeypatch.setattr("services.chat.search_documents",
                            lambda *a, **k: [])

        history = [{"role": "user", "content": "earlier question"},
                   {"role": "assistant", "content": "earlier answer"}]
        reply, citations = await chat_with_docs(
            "follow-up?", "a-1",
            history=history,
            memories=["org requires SOC 2 Type II"],
        )

        msgs = captured["messages"]
        assert reply == "reply" and citations == []
        # system, then replayed history in order, then the new question
        assert msgs[0]["role"] == "system"
        assert "ANALYST MEMORY" in msgs[0]["content"]
        assert "org requires SOC 2 Type II" in msgs[0]["content"]
        assert msgs[1]["content"] == "earlier question"
        assert msgs[2]["content"] == "earlier answer"
        assert "follow-up?" in msgs[3]["content"]

    @pytest.mark.asyncio
    async def test_no_memory_block_when_memories_empty(self, monkeypatch):
        captured = {}

        async def fake_acomplete(messages, **kw):
            captured["messages"] = messages
            return "reply"

        monkeypatch.setattr("services.chat.acomplete", fake_acomplete)
        monkeypatch.setattr("services.chat.search_documents",
                            lambda *a, **k: [])

        await chat_with_docs("q?", "a-1", history=None, memories=[])
        assert "ANALYST MEMORY" not in captured["messages"][0]["content"]
        assert len(captured["messages"]) == 2  # system + question only