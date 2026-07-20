"""Agentic chat tool loop: model-driven dispatch, turn budget, fallback.

No LLM, no Qdrant — acomplete_tools and search_documents are stubbed.
"""

import json

import pytest

import services.chat as chat_mod
from config import get_settings
from models.schemas import Citation


# ── Minimal fakes for the OpenAI message shape the loop consumes ─────────────


class _FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **kw) -> dict:
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (self.tool_calls or [])
            ],
        }


def _search_result(text: str) -> dict:
    return {
        "content": text,
        "document_name": "policy.pdf",
        "chunk_index": 0,
        "score": 0.9,
    }


def _scripted_llm(script: list[_FakeMessage], calls: list[dict]):
    """acomplete_tools stub that pops messages off a script and records calls."""

    async def fake(messages, *, tools=None, temperature=0.0,
                   max_tokens=None, assessment_id=None):
        calls.append({"messages": list(messages), "tools": tools})
        return script.pop(0)

    return fake


# ── The loop ─────────────────────────────────────────────────────────────────


class TestChatToolLoop:
    @pytest.mark.asyncio
    async def test_search_then_answer(self, monkeypatch):
        searches = []

        def fake_search(query, assessment_id, top_k):
            searches.append(query)
            return [_search_result("We encrypt data at rest with AES-256.")]

        calls: list[dict] = []
        script = [
            _FakeMessage(tool_calls=[
                _FakeToolCall("t1", "search_documents",
                              json.dumps({"query": "encryption at rest"})),
            ]),
            _FakeMessage(content="The vendor encrypts data at rest (policy.pdf)."),
        ]
        monkeypatch.setattr(chat_mod, "search_documents", fake_search)
        monkeypatch.setattr(chat_mod, "acomplete_tools", _scripted_llm(script, calls))

        reply, citations = await chat_mod.chat_agentic("Is data encrypted?", "aid")

        assert searches == ["encryption at rest"]
        assert reply == "The vendor encrypts data at rest (policy.pdf)."
        assert [c.document for c in citations] == ["policy.pdf"]
        # Tool result was fed back to the model on the second call
        tool_msgs = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "AES-256" in tool_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_turn_budget_forces_final_answer(self, monkeypatch):
        max_turns = get_settings().chat_agent_max_tool_turns

        def fake_search(query, assessment_id, top_k):
            return []

        calls: list[dict] = []
        # Model insists on searching every turn; the final scripted message
        # is the forced no-tools answer.
        script = [
            _FakeMessage(tool_calls=[
                _FakeToolCall(f"t{i}", "search_documents",
                              json.dumps({"query": f"attempt {i}"})),
            ])
            for i in range(max_turns)
        ] + [_FakeMessage(content="I could not find this information in the vendor documents.")]

        monkeypatch.setattr(chat_mod, "search_documents", fake_search)
        monkeypatch.setattr(chat_mod, "acomplete_tools", _scripted_llm(script, calls))

        reply, citations = await chat_mod.chat_agentic("Unanswerable?", "aid")

        assert len(calls) == max_turns + 1
        assert calls[-1]["tools"] is None           # forced answer: no tools offered
        assert "could not find" in reply
        assert citations == []

    @pytest.mark.asyncio
    async def test_loop_error_falls_back_to_single_shot_rag(self, monkeypatch):
        async def broken_llm(*a, **kw):
            raise RuntimeError("provider does not support tools")

        async def fake_rag(question, assessment_id, context=None,
                           history=None, memories=None):
            return "single-shot answer", [
                Citation(document="d.pdf", excerpt="x", similarity=0.5)
            ]

        monkeypatch.setattr(chat_mod, "acomplete_tools", broken_llm)
        monkeypatch.setattr(chat_mod, "chat_with_docs", fake_rag)

        reply, citations = await chat_mod.chat_agentic("q", "aid")

        assert reply == "single-shot answer"
        assert citations[0].document == "d.pdf"

    @pytest.mark.asyncio
    async def test_disabled_flag_skips_loop_entirely(self, monkeypatch):
        async def fail_llm(*a, **kw):  # pragma: no cover
            raise AssertionError("tool loop must not run when disabled")

        async def fake_rag(question, assessment_id, context=None,
                           history=None, memories=None):
            return "classic", []

        monkeypatch.setattr(get_settings(), "chat_agent_enabled", False)
        monkeypatch.setattr(chat_mod, "acomplete_tools", fail_llm)
        monkeypatch.setattr(chat_mod, "chat_with_docs", fake_rag)

        reply, _ = await chat_mod.chat_agentic("q", "aid")
        assert reply == "classic"


# ── Tool dispatch ────────────────────────────────────────────────────────────


class TestDispatchTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_text(self):
        out = await chat_mod._dispatch_tool("rm_rf", {}, "aid", [])
        assert out.startswith("Error: unknown tool")

    @pytest.mark.asyncio
    async def test_empty_query_returns_error_text(self):
        out = await chat_mod._dispatch_tool(
            "search_documents", {"query": "  "}, "aid", [])
        assert "non-empty" in out

    @pytest.mark.asyncio
    async def test_overview_formats_stored_assessment(self, monkeypatch):
        stored = {
            "vendor_name": "Acme",
            "overall_score": 72,
            "risk_level": "Medium",
            "framework_id": "nist-800-53",
            "domain_scores": {"Access Control": 80},
            "control_results": [
                {"control_id": "AC-1", "score": "PASS"},
                {"control_id": "AC-2", "score": "FAIL", "analyst_score": "PASS"},
            ],
            "run_history": [
                {"ran_at": "2026-07-01T00:00:00+00:00", "score": 72,
                 "risk_level": "Medium"},
            ],
        }
        monkeypatch.setattr(chat_mod, "get_assessment", lambda aid: stored)

        out = await chat_mod._dispatch_tool("get_assessment_overview", {}, "aid", [])

        assert "72/100" in out
        # Analyst override supersedes the AI verdict in counts
        assert "'PASS': 2" in out
        assert "2026-07-01" in out

    @pytest.mark.asyncio
    async def test_control_result_lookup_and_miss(self, monkeypatch):
        stored = {
            "control_results": [
                {"control_id": "AC-2", "score": "FAIL", "title": "Least privilege",
                 "reasoning": "No RBAC evidence."},
            ],
        }
        monkeypatch.setattr(chat_mod, "get_assessment", lambda aid: stored)

        hit = await chat_mod._dispatch_tool(
            "get_control_result", {"control_id": "ac-2"}, "aid", [])
        assert "No RBAC evidence." in hit

        miss = await chat_mod._dispatch_tool(
            "get_control_result", {"control_id": "ZZ-9"}, "aid", [])
        assert "Unknown control_id" in miss
        assert "AC-2" in miss
