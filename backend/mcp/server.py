"""MCP (Model Context Protocol) server for VendorShield.

Exposes vendor assessment tools to external AI agents (Claude, GPT, etc.)
via the MCP Streamable HTTP protocol (JSON-RPC over HTTP).

RESPONSIBILITY:
    Thin JSON-RPC dispatcher.  Each tool handler delegates to the services
    and storage layers — NO business logic lives here.

    The 8 tools mirror the core capabilities of the system:
    1. list_assessments      — browse all assessments
    2. get_documents         — list documents for an assessment
    3. query_documents       — semantic search within an assessment
    4. ask_question          — RAG chat over vendor documents
    5. run_assessment        — trigger a full 20-control risk assessment
    6. get_assessment_report — fetch a completed assessment report
    7. get_controls          — list all 20 security controls and domains
    8. send_report           — generate PDF and email it to a recipient

IMPORTS FROM: storage/local_store, services/retrieval, services/chat,
              chains/assessment_graph, models/controls
IMPORTED BY:  main.py
"""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from storage.local_store import list_assessments, list_documents, get_assessment
from services.retrieval import search_documents
from services.chat import chat_with_docs
from services.evaluation import evaluate_all_controls
from services.aggregation import aggregate_results
from models.controls import get_all_controls, get_domains
from models.schemas import ControlResult

from chains.assessment_graph import run_assessment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MCP"])


# ── Tool Registry ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "list_assessments",
        "description": "List all vendor assessments with their status and document counts",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_documents",
        "description": "Get all documents uploaded for a specific assessment",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
            },
            "required": ["assessment_id"],
        },
    },
    {
        "name": "query_documents",
        "description": (
            "Search document chunks for a specific vendor assessment "
            "using semantic search"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
                "query": {
                    "type": "string",
                    "description": "Natural-language search query",
                },
                "top_k": {
                    "type": "number",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["assessment_id", "query"],
        },
    },
    {
        "name": "ask_question",
        "description": (
            "Ask a question about a vendor's documents using "
            "RAG (retrieval-augmented generation)"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask",
                },
            },
            "required": ["assessment_id", "question"],
        },
    },
    {
        "name": "run_assessment",
        "description": (
            "Trigger a full vendor risk assessment against all 20 "
            "NIST-based security controls"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
                "vendor_name": {
                    "type": "string",
                    "description": "Vendor name",
                },
            },
            "required": ["assessment_id", "vendor_name"],
        },
    },
    {
        "name": "get_assessment_report",
        "description": "Get the complete risk assessment report for a vendor",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
            },
            "required": ["assessment_id"],
        },
    },
    {
        "name": "get_controls",
        "description": (
            "List all 20 NIST SP 800-53 security controls used for "
            "vendor risk assessments, grouped by domain"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "evaluate_controls",
        "description": (
            "Evaluate all 20 controls for an assessment and return "
            "control-level scoring results"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
            },
            "required": ["assessment_id"],
        },
    },
    {
        "name": "aggregate_scores",
        "description": (
            "Aggregate control-level results into final domain scores, "
            "overall score, risk level, and gaps summary"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
                "vendor_name": {
                    "type": "string",
                    "description": "Vendor name",
                },
                "control_results": {
                    "type": "array",
                    "description": "Array of control results compatible with ControlResult schema",
                },
            },
            "required": ["assessment_id", "vendor_name", "control_results"],
        },
    },
    {
        "name": "send_report",
        "description": (
            "Generate a PDF risk assessment report and email it "
            "to a recipient."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "The assessment ID",
                },
                "recipient_email": {
                    "type": "string",
                    "description": "Email address to send the report to",
                },
            },
            "required": ["assessment_id", "recipient_email"],
        },
    },
]


# ── Tool Handlers ────────────────────────────────────────────────────────────
# Each handler calls the services/storage layer ONLY.
# No business logic, no direct DB clients, no inline queries.


async def handle_list_assessments(_args: dict) -> str:
    """Delegate to local_store.list_assessments()."""
    assessments = list_assessments()
    # Enrich each assessment with its document count
    enriched = []
    for a in assessments:
        docs = list_documents(assessment_id=a["id"])
        enriched.append({
            "assessment_id": a["id"],
            "vendor_name": a.get("vendor_name", ""),
            "status": a.get("status", ""),
            "created_at": a.get("created_at", ""),
            "document_count": len(docs),
        })
    return json.dumps(enriched, indent=2, default=str)


async def handle_get_documents(args: dict) -> str:
    """Delegate to local_store.list_documents()."""
    docs = list_documents(assessment_id=args["assessment_id"])
    return json.dumps(docs, indent=2, default=str)


async def handle_query_documents(args: dict) -> str:
    """Delegate to services/retrieval.search_documents()."""
    results = search_documents(
        query=args["query"],
        assessment_id=args["assessment_id"],
        top_k=args.get("top_k", 5),
    )
    formatted = [
        {
            "document": r["document_name"],
            "chunk_index": r["chunk_index"],
            "relevance": round(r["score"], 3),
            "content": r["content"][:500],
        }
        for r in results
    ]
    return json.dumps(formatted, indent=2) if formatted else "No matching document chunks found."


async def handle_ask_question(args: dict) -> str:
    """Delegate to services/chat.chat_with_docs()."""
    reply, citations = await chat_with_docs(
        question=args["question"],
        assessment_id=args["assessment_id"],
    )
    result = {
        "answer": reply,
        "sources": [c.model_dump() for c in citations],
    }
    return json.dumps(result, indent=2, default=str)


async def handle_run_assessment(args: dict) -> str:
    """Delegate to chains/assessment_graph.run_assessment().

    NOTE: The assessment graph is built in Layer 5.  If Layer 5 has not
    been implemented yet, the guarded import at the top of this file
    provides a stub that raises NotImplementedError.
    """
    result = await run_assessment(
        vendor_name=args["vendor_name"],
        assessment_id=args["assessment_id"],
    )
    return json.dumps(result.model_dump(), indent=2, default=str)


async def handle_get_assessment_report(args: dict) -> str:
    """Delegate to local_store.get_assessment()."""
    report = get_assessment(args["assessment_id"])
    if not report:
        return "Assessment not found."
    return json.dumps(report, indent=2, default=str)


async def handle_get_controls(_args: dict) -> str:
    """Delegate to models/controls helpers."""
    controls = get_all_controls()
    domains = get_domains()
    result = {
        "total_controls": len(controls),
        "domains": domains,
        "controls": [
            {
                "id": c["id"],
                "domain": c["domain"],
                "title": c["title"],
                "description": c["description"],
                "nist_ref": c["nist_ref"],
            }
            for c in controls
        ],
    }
    return json.dumps(result, indent=2)


async def handle_evaluate_controls(args: dict) -> str:
    """Delegate to services/evaluation.evaluate_all_controls()."""
    results = evaluate_all_controls(args["assessment_id"])
    return json.dumps([r.model_dump(mode="json") for r in results], indent=2, default=str)


async def handle_aggregate_scores(args: dict) -> str:
    """Delegate to services/aggregation.aggregate_results()."""
    control_results = [
        ControlResult(**r)
        for r in args["control_results"]
    ]
    response = aggregate_results(
        assessment_id=args["assessment_id"],
        vendor_name=args["vendor_name"],
        control_results=control_results,
    )
    return json.dumps(response.model_dump(mode="json"), indent=2, default=str)


async def handle_send_report(args: dict) -> str:
    """Delegate to services/email_service.send_report_email()."""
    from services.email_service import send_report_email

    assessment = get_assessment(args["assessment_id"])
    if not assessment:
        return json.dumps({"error": "Assessment not found"})

    if assessment.get("status") != "completed":
        return json.dumps({
            "error": f"Assessment is not completed (status: {assessment.get('status', 'unknown')})"
        })

    result = send_report_email(args["recipient_email"], assessment)
    return json.dumps(result, default=str)


# ── Handler Dispatch Table ───────────────────────────────────────────────────

TOOL_HANDLERS = {
    "list_assessments": handle_list_assessments,
    "get_documents": handle_get_documents,
    "query_documents": handle_query_documents,
    "ask_question": handle_ask_question,
    "run_assessment": handle_run_assessment,
    "get_assessment_report": handle_get_assessment_report,
    "get_controls": handle_get_controls,
    "evaluate_controls": handle_evaluate_controls,
    "aggregate_scores": handle_aggregate_scores,
    "send_report": handle_send_report,
}


# ── MCP JSON-RPC Endpoint ───────────────────────────────────────────────────


@router.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP Streamable HTTP endpoint — handles JSON-RPC requests from AI agents."""

    # --- Parse request body ---
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            },
            status_code=400,
        )

    jsonrpc = body.get("jsonrpc", "2.0")
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    # --- initialize ---
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "vendorshield-mcp",
                    "version": "1.0.0",
                },
            },
        })

    # --- tools/list ---
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {"tools": TOOLS},
        })

    # --- tools/call ---
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            })

        try:
            result_text = await handler(tool_args)
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            })
        except Exception as e:
            logger.error(f"MCP tool error ({tool_name}): {e}", exc_info=True)
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                },
            })

    # --- Unknown method ---
    return JSONResponse({
        "jsonrpc": jsonrpc,
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    })
