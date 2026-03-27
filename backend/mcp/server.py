"""MCP (Model Context Protocol) server for VendorShield.

Exposes vendor assessment tools to external AI agents (Claude, GPT, etc.)
via the MCP Streamable HTTP protocol (JSON-RPC over HTTP).
"""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from supabase import create_client
from config import get_settings
from services.pinecone_store import search
from services.chat import chat_with_docs
from chains.assessment_graph import run_assessment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MCP"])

# --- Tool Registry ---

TOOLS = [
    {
        "name": "list_assessments",
        "description": "List all vendor assessments with document counts",
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
                "assessment_id": {"type": "string", "description": "The assessment ID"},
            },
            "required": ["assessment_id"],
        },
    },
    {
        "name": "query_documents",
        "description": "Search document chunks for a specific vendor assessment using semantic search",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string", "description": "The assessment ID"},
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "number", "description": "Max results (default 5)"},
            },
            "required": ["assessment_id", "query"],
        },
    },
    {
        "name": "ask_question",
        "description": "Ask a question about a vendor assessment using RAG (retrieval-augmented generation)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string", "description": "The assessment ID"},
                "question": {"type": "string", "description": "The question to ask"},
            },
            "required": ["assessment_id", "question"],
        },
    },
    {
        "name": "run_assessment",
        "description": "Trigger a full vendor risk assessment against internal controls",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string", "description": "The assessment ID"},
                "vendor_name": {"type": "string", "description": "Vendor name"},
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
                "assessment_id": {"type": "string", "description": "The assessment ID"},
            },
            "required": ["assessment_id"],
        },
    },
]


# --- Tool Handlers ---

async def handle_list_assessments(_args: dict) -> str:
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = supabase.table("documents").select(
        "assessment_id, file_name, status, created_at"
    ).order("created_at", desc=True).execute()

    grouped: dict[str, list] = {}
    for doc in result.data or []:
        aid = doc["assessment_id"]
        if aid not in grouped:
            grouped[aid] = []
        grouped[aid].append(doc)

    summary = [
        {
            "assessment_id": aid,
            "document_count": len(docs),
            "documents": [{"file_name": d["file_name"], "status": d["status"]} for d in docs],
        }
        for aid, docs in grouped.items()
    ]
    return json.dumps(summary, indent=2)


async def handle_get_documents(args: dict) -> str:
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = (
        supabase.table("documents")
        .select("id, file_name, file_size, content_type, status, created_at")
        .eq("assessment_id", args["assessment_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return json.dumps(result.data, indent=2)


async def handle_query_documents(args: dict) -> str:
    results = search(
        assessment_id=args["assessment_id"],
        query=args["query"],
        top_k=args.get("limit", 5),
    )
    formatted = [
        {
            "file": r["document_name"],
            "page": r["page_number"],
            "chunk": r["chunk_index"],
            "relevance": round(r["score"], 3),
            "content": r["content"][:500],
        }
        for r in results
    ]
    return json.dumps(formatted, indent=2) if formatted else "No matching document chunks found."


async def handle_ask_question(args: dict) -> str:
    reply, _ = await chat_with_docs(
        question=args["question"],
        assessment_id=args["assessment_id"],
    )
    return reply


async def handle_run_assessment(args: dict) -> str:
    result = await run_assessment(
        vendor_name=args["vendor_name"],
        assessment_id=args["assessment_id"],
    )
    return json.dumps(result.model_dump(), indent=2, default=str)


async def handle_get_assessment_report(args: dict) -> str:
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = (
        supabase.table("assessments")
        .select("*")
        .eq("id", args["assessment_id"])
        .single()
        .execute()
    )
    if not result.data:
        return "Assessment not found."
    return json.dumps(result.data, indent=2, default=str)


TOOL_HANDLERS = {
    "list_assessments": handle_list_assessments,
    "get_documents": handle_get_documents,
    "query_documents": handle_query_documents,
    "ask_question": handle_ask_question,
    "run_assessment": handle_run_assessment,
    "get_assessment_report": handle_get_assessment_report,
}


# --- MCP JSON-RPC Endpoint ---

@router.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP Streamable HTTP endpoint — handles JSON-RPC requests from AI agents."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400,
        )

    jsonrpc = body.get("jsonrpc", "2.0")
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    # Handle initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "vendor-shield-mcp", "version": "1.0.0"},
            },
        })

    # Handle tools/list
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {"tools": TOOLS},
        })

    # Handle tools/call
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            })

        try:
            result_text = await handler(tool_args)
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result_text}]},
            })
        except Exception as e:
            logger.error(f"MCP tool error ({tool_name}): {e}")
            return JSONResponse({
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True},
            })

    # Unknown method
    return JSONResponse({
        "jsonrpc": jsonrpc,
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    })
