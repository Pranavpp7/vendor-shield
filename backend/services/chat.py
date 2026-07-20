"""Layer 3: Chat — agentic tool-loop chat and single-shot RAG over vendor docs.

RESPONSIBILITY:
    Three capabilities:
    1. chat_agentic() — the chat endpoint's default: a bounded tool loop
       where the MODEL decides which tools to call (semantic search,
       assessment overview, per-control results) and how many searches a
       question needs.  Chat is the one open-ended surface in the app,
       so it is the one place model-directed control flow is used — the
       assessment pipeline itself stays deterministic and eval-gated.
       Falls back to chat_with_docs() on any failure (e.g. a provider
       without tool-calling support).
    2. chat_with_docs() — single-shot RAG: retrieve chunks once, build a
       grounded prompt, return answer + citations.  Also what the MCP
       query tool uses — external agents orchestrate themselves.
    3. generate_summary() — executive summary from assessment data.

    No database writes.  Retrieval is delegated to
    services/retrieval.search_documents(); assessment reads to
    storage/local_store.

IMPORTS FROM: services/retrieval, services/llm, storage/local_store,
              models/schemas, config
IMPORTED BY:  routers/chat.py, mcp/server.py
"""

import asyncio
import json
import logging
from config import get_settings
from services.llm import acomplete, acomplete_tools
from services.retrieval import search_documents
from storage.local_store import get_assessment
from models.schemas import Citation

logger = logging.getLogger(__name__)

# Cap on any single replayed history message — keeps a pasted wall of text
# from one earlier turn from crowding out retrieval context.
_HISTORY_MSG_CHAR_CAP = 2000


def build_history_messages(history: list[dict], window: int) -> list[dict]:
    """SHORT-TERM MEMORY: the last `window` chat messages as LLM messages.

    Takes the persisted history (role/content dicts, oldest first), keeps
    the most recent `window` entries, and truncates oversized messages —
    so follow-up questions resolve against the actual conversation.
    """
    if window <= 0:
        return []
    recent = history[-window:]
    return [
        {
            "role": m["role"] if m.get("role") in ("user", "assistant") else "user",
            "content": (m.get("content") or "")[:_HISTORY_MSG_CHAR_CAP],
        }
        for m in recent
        if m.get("content")
    ]


# ── Agentic chat: bounded tool loop ──────────────────────────────────────────

_CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Semantic search over THIS assessment's vendor documents. "
                "Returns the most relevant document chunks with source names. "
                "Call it multiple times with different phrasings if the first "
                "search misses; use specific security terminology."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search the vendor documents for.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assessment_overview",
            "description": (
                "The stored assessment result: overall score, risk level, "
                "per-domain scores, verdict counts, and run history. Use for "
                "questions about scores, risk, trends, or 'how did this "
                "vendor do'."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_control_result",
            "description": (
                "Full scored detail for ONE control: verdict, confidence, "
                "evidence quote, reasoning, gap, and any analyst override. "
                "Use when asked about a specific control (e.g. 'why did "
                "AC-2 fail?')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "control_id": {
                        "type": "string",
                        "description": "Control id, e.g. 'IAM-001'.",
                    },
                },
                "required": ["control_id"],
            },
        },
    },
]


def _search_to_text(results: list[dict]) -> str:
    if not results:
        return "No relevant document content found for this query."
    return "\n\n---\n\n".join(
        f"[Source: {r['document_name']}, Chunk {r['chunk_index']}]\n{r['content']}"
        for r in results
    )


def _overview_to_text(assessment: dict | None) -> str:
    if not assessment:
        return "No stored assessment result — the assessment has not been run yet."
    controls = assessment.get("control_results") or []
    counts: dict[str, int] = {}
    for c in controls:
        effective = c.get("analyst_score") or c.get("score", "?")
        counts[effective] = counts.get(effective, 0) + 1
    lines = [
        f"Vendor: {assessment.get('vendor_name', '?')}",
        f"Overall score: {assessment.get('overall_score', '?')}/100",
        f"Risk level: {assessment.get('risk_level', '?')}",
        f"Framework: {assessment.get('framework_id', '?')}",
        f"Verdict counts (analyst overrides applied): {counts}",
        f"Domain scores: {assessment.get('domain_scores', {})}",
    ]
    if assessment.get("gaps_summary"):
        lines.append(f"Gaps summary: {assessment['gaps_summary']}")
    history = assessment.get("run_history") or []
    if history:
        lines.append(
            "Run history (oldest first): "
            + "; ".join(
                f"{h.get('ran_at', '?')[:10]} score {h.get('score', '?')}"
                f" ({h.get('risk_level', '?')})"
                for h in history
            )
        )
    return "\n".join(lines)


def _control_to_text(assessment: dict | None, control_id: str) -> str:
    if not assessment:
        return "No stored assessment result — the assessment has not been run yet."
    for c in assessment.get("control_results") or []:
        if c.get("control_id", "").upper() == control_id.upper():
            return json.dumps(
                {
                    k: c.get(k)
                    for k in (
                        "control_id", "title", "domain", "score", "confidence",
                        "evidence_quote", "reasoning", "gap",
                        "analyst_score", "analyst_comment",
                    )
                },
                indent=1,
            )
    known = [c.get("control_id") for c in assessment.get("control_results") or []]
    return f"Unknown control_id '{control_id}'. Known controls: {known}"


async def _dispatch_tool(
    name: str,
    args: dict,
    assessment_id: str,
    citations: list[Citation],
) -> str:
    """Execute one tool call; the returned string goes back to the model.

    Errors come back as text, not exceptions — the model can recover
    (retry with fixed args, or answer without the tool)."""
    settings = get_settings()
    if name == "search_documents":
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: search_documents requires a non-empty 'query'."
        results = await asyncio.to_thread(
            search_documents, query, assessment_id, settings.retrieval_top_k,
        )
        citations.extend(
            Citation(
                document=r["document_name"],
                excerpt=r["content"][:200],
                similarity=r["score"],
            )
            for r in results
        )
        return _search_to_text(results)
    if name == "get_assessment_overview":
        assessment = await asyncio.to_thread(get_assessment, assessment_id)
        return _overview_to_text(assessment)
    if name == "get_control_result":
        assessment = await asyncio.to_thread(get_assessment, assessment_id)
        return _control_to_text(assessment, str(args.get("control_id", "")))
    return f"Error: unknown tool '{name}'."


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple] = set()
    unique = []
    for c in citations:
        key = (c.document, c.excerpt)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


async def chat_agentic(
    question: str,
    assessment_id: str,
    context: str | None = None,
    history: list[dict] | None = None,
    memories: list[str] | None = None,
) -> tuple[str, list[Citation]]:
    """Agentic chat: the model drives a bounded tool loop.

    Unlike chat_with_docs (one fixed retrieval, then answer), the model
    decides which tools to call and how many searches a question needs —
    reformulating queries, pulling stored scores, or reading a specific
    control's verdict.  The loop is capped at chat_agent_max_tool_turns
    rounds, after which the model must answer with what it has.

    Falls back to chat_with_docs on any error, and entirely when
    chat_agent_enabled is false — so chat keeps working on providers
    without tool-calling support.
    """
    settings = get_settings()
    if not settings.chat_agent_enabled:
        return await chat_with_docs(question, assessment_id, context, history, memories)
    try:
        return await _chat_tool_loop(question, assessment_id, context, history, memories)
    except Exception as e:
        logger.warning(
            f"Agentic chat failed ({e}) — falling back to single-shot RAG"
        )
        return await chat_with_docs(question, assessment_id, context, history, memories)


async def _chat_tool_loop(
    question: str,
    assessment_id: str,
    context: str | None,
    history: list[dict] | None,
    memories: list[str] | None,
) -> tuple[str, list[Citation]]:
    settings = get_settings()

    system_message = (
        "You are a security assessment assistant with tools over ONE "
        "vendor assessment: semantic search over the vendor's documents, "
        "the stored assessment overview, and per-control results.\n\n"
        "GROUNDING RULES (strict):\n"
        "- Statements about the VENDOR must be grounded in search_documents "
        "results; statements about SCORES/VERDICTS in the assessment tools. "
        "Never use general knowledge or training data for vendor facts.\n"
        "- Search before answering any question about the vendor's practices. "
        "If a search misses, retry with different terminology before giving up.\n"
        "- If the information is not in the tool results, say: 'I could not "
        "find this information in the vendor documents.' Never guess.\n"
        "- Always cite the source document name when referencing document "
        "content.\n"
        "- Keep responses concise and professional. Use bullet points where "
        "appropriate."
    )
    if memories:
        system_message += (
            "\n\nANALYST MEMORY — organizational context this analyst "
            "established in earlier sessions. Use it to frame and prioritize "
            "your answer (what this organization requires or cares about), "
            "but it is NOT evidence about this vendor: vendor facts must "
            "still come only from tool results.\n"
            + "\n".join(f"- {m}" for m in memories)
        )

    messages: list[dict] = [
        {"role": "system", "content": system_message},
        *(history or []),
        {
            "role": "user",
            "content": (
                f"Assessment context:\n{context or 'No additional context provided.'}"
                f"\n\nQuestion: {question}"
            ),
        },
    ]

    citations: list[Citation] = []
    for _turn in range(settings.chat_agent_max_tool_turns):
        msg = await acomplete_tools(
            messages,
            tools=_CHAT_TOOLS,
            temperature=0.1,
            max_tokens=800,
            assessment_id=assessment_id,
        )
        if not msg.tool_calls:
            return (msg.content or ""), _dedupe_citations(citations)

        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None
            if isinstance(args, dict):
                result = await _dispatch_tool(
                    tc.function.name, args, assessment_id, citations,
                )
            else:
                result = "Error: tool arguments were not valid JSON."
            logger.info(
                f"[chat {assessment_id}] tool {tc.function.name} → "
                f"{len(result)} chars"
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Turn budget exhausted — force a final answer without tools.
    messages.append({
        "role": "user",
        "content": (
            "Tool budget exhausted. Answer the question now using only the "
            "tool results above; state plainly anything you could not find."
        ),
    })
    msg = await acomplete_tools(
        messages, tools=None, temperature=0.1, max_tokens=800,
        assessment_id=assessment_id,
    )
    return (msg.content or ""), _dedupe_citations(citations)


async def chat_with_docs(
    question: str,
    assessment_id: str,
    context: str | None = None,
    history: list[dict] | None = None,
    memories: list[str] | None = None,
) -> tuple[str, list[Citation]]:
    """RAG chat: retrieve relevant chunks from Qdrant, then ask the LLM.

    history:  short-term memory — prior turns of THIS conversation,
              already windowed by build_history_messages().
    memories: long-term memory — the analyst's organizational context
              recalled by services/memory (mem0), never vendor evidence.
    """
    settings = get_settings()

    # 1. Retrieve relevant document chunks (search_documents is sync — run in thread)
    results = await asyncio.to_thread(
        search_documents,
        question,
        assessment_id,
        settings.retrieval_top_k,
    )

    # 2. Build RAG context string from retrieved chunks
    rag_context = ""
    if results:
        chunk_lines = [
            f"[Source: {r['document_name']}, Chunk {r['chunk_index']}]\n{r['content']}"
            for r in results
        ]
        rag_context = "\n\n---\n\n".join(chunk_lines)

    # 3. Build citations from the same results
    citations = [
        Citation(
            document=r["document_name"],
            excerpt=r["content"][:200],
            similarity=r["score"],
        )
        for r in results
    ]

    # 4. Build LLM prompt
    system_message = (
        "You are a security assessment assistant. "
        "You MUST answer ONLY from the document context provided below. "
        "Do NOT use general knowledge, training data, or outside information. "
        "If the answer is not explicitly present in the provided document context, "
        "you MUST respond with exactly: "
        "'I could not find this information in the vendor documents.' "
        "Never guess or infer beyond what the documents state. "
        "Keep responses concise and professional. Use bullet points where appropriate."
    )
    if rag_context:
        system_message += (
            "\n\nDocument context retrieved from vendor files:\n\n"
            + rag_context
            + "\n\nOnly answer using the above document context. "
            "Always cite the source document name when referencing information."
        )
    else:
        system_message += (
            "\n\nNo relevant document content was retrieved for this question. "
            "You must respond: 'I could not find this information in the vendor documents.'"
        )

    if memories:
        system_message += (
            "\n\nANALYST MEMORY — organizational context this analyst "
            "established in earlier sessions. Use it to frame and prioritize "
            "your answer (what this organization requires or cares about), "
            "but it is NOT evidence about this vendor: vendor facts must "
            "still come only from the document context above.\n"
            + "\n".join(f"- {m}" for m in memories)
        )

    messages = [
        {"role": "system", "content": system_message},
        *(history or []),
        {"role": "user", "content": f"Assessment context:\n{context or 'No additional context provided.'}\n\nQuestion: {question}"},
    ]

    # 5. Call LLM (shared module: retries + provider failover)
    reply = await acomplete(messages, temperature=0.1, max_tokens=800)
    return reply, citations


async def generate_summary(
    vendor_name: str,
    score: int,
    risk_level: str,
    controls: list[dict],
    notes: str = "",
) -> str:
    """Generate executive summary using LLM."""
    settings = get_settings()

    # Consistent terminology contract — must match the rest of the app:
    # "Failed" is reserved for VERIFIED deficiencies; unverified controls
    # are "Needs Info", never "failed".
    _LABELS = {
        "passed": "PASSED",
        "partial": "PARTIAL",
        "failed": "FAILED",
        "needs_info": "NEEDS INFO (unverified — no evidence provided)",
    }
    controls_text = "\n".join(
        f"  - {c.get('id', '?')} [{c.get('category', '')}] {c.get('name', '')}: "
        f"{_LABELS.get(c.get('status', ''), str(c.get('status', 'unknown')).upper())}"
        for c in controls[:40]
    ) if controls else "  No controls evaluated."

    counts = {s: sum(1 for c in controls if c.get("status") == s)
              for s in ("passed", "partial", "failed", "needs_info")}

    messages = [
        {
            "role": "system",
            "content": (
                "You are a security assessment report writer. Generate a concise "
                "executive summary in markdown with headers and bullet points.\n\n"
                "TERMINOLOGY RULES (strict):\n"
                "- 'Failed' means a VERIFIED deficiency — evidence proved the "
                "vendor does not meet the control. Only controls marked FAILED "
                "may ever appear under a failed/deficient heading.\n"
                "- NEEDS INFO means the documents contained no evidence either "
                "way. These are documentation gaps to chase, NOT failures — "
                "never describe them as failed, deficient, or non-compliant.\n"
                "- Do not invent findings beyond the control list given."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Vendor: {vendor_name}\n"
                f"Score: {score}/100 (unverified controls count as 0)\n"
                f"Risk Level: {risk_level}\n"
                f"Status counts: {counts['passed']} passed, {counts['partial']} partial, "
                f"{counts['failed']} failed, {counts['needs_info']} needs info\n"
                f"Controls:\n{controls_text}\n"
                f"Analyst Notes: {notes or 'None'}\n\n"
                "Generate these sections:\n"
                "1. Executive Overview\n"
                "2. Key Findings\n"
                "3. Confirmed Gaps — FAILED controls only; if none, state "
                "'No verified control failures.'\n"
                "4. Unverified Controls (Needs Info) — list them as evidence "
                "to request from the vendor\n"
                "5. Recommendations"
            ),
        },
    ]

    return await acomplete(
        messages,
        temperature=0.2,  # report writing wants consistency, not creativity
        max_tokens=1200,
    )
