"""MCP Client — Python interface to the VendorShield MCP server.

RESPONSIBILITY:
    Sends JSON-RPC requests to the MCP server endpoint and returns
    parsed results.  This is the ONLY way Layer 5 (the LangGraph agent)
    interacts with the system's capabilities.

    Flow:  Agent → MCPClient.call_tool() → HTTP POST /mcp → server.py → services

    Also provides get_mcp_tools() which returns LangChain Tool objects
    that can be plugged directly into a LangGraph agent.

IMPORTS FROM: config.py, httpx, langchain_core.tools
IMPORTED BY:  chains/assessment_graph.py (Layer 5)
"""

import json
import logging
import asyncio
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)


# ── MCP Client ───────────────────────────────────────────────────────────────


class MCPClient:
    """Async client that talks to the VendorShield MCP server via JSON-RPC.

    Usage:
        client = MCPClient()
        await client.initialize()
        result = await client.call_tool("list_assessments", {})
    """

    def __init__(self, server_url: str | None = None):
        settings = get_settings()
        self.server_url = server_url or settings.mcp_server_url
        self._request_id = 0
        self._initialized = False

    def _next_id(self) -> int:
        """Return a monotonically increasing request ID."""
        self._request_id += 1
        return self._request_id

    async def _send(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and return the parsed response.

        Raises RuntimeError on transport or protocol errors.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }

        async with httpx.AsyncClient(timeout=300.0) as http:
            try:
                resp = await http.post(self.server_url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise RuntimeError(
                    f"MCP transport error calling {method}: {e}"
                ) from e

        body = resp.json()

        # Check for JSON-RPC error
        if "error" in body:
            err = body["error"]
            raise RuntimeError(
                f"MCP error ({err.get('code')}): {err.get('message')}"
            )

        return body.get("result", {})

    # ── Protocol methods ─────────────────────────────────────────────────

    async def initialize(self) -> dict:
        """Perform the MCP initialize handshake (called once)."""
        if self._initialized:
            return {}
        result = await self._send("initialize")
        self._initialized = True
        logger.info(
            f"MCP client initialized — server: "
            f"{result.get('serverInfo', {}).get('name', 'unknown')}"
        )
        return result

    async def list_tools(self) -> list[dict]:
        """Fetch the tool registry from the server."""
        await self.initialize()
        result = await self._send("tools/list")
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Invoke a tool by name and return its text result.

        Automatically initializes on first call.
        """
        await self.initialize()
        result = await self._send("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        # Check for tool-level errors
        if result.get("isError"):
            content = result.get("content", [{}])
            error_text = content[0].get("text", "Unknown tool error") if content else "Unknown tool error"
            raise RuntimeError(f"MCP tool '{tool_name}' error: {error_text}")

        # Extract text from the content array
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return content[0]["text"]
        return json.dumps(result, default=str)

    # ── Convenience wrappers (typed) ─────────────────────────────────────
    # These parse the raw JSON string into Python dicts/lists so callers
    # get structured data.  Used by the agent and by tests.

    async def list_assessments(self) -> list[dict]:
        """List all vendor assessments."""
        raw = await self.call_tool("list_assessments", {})
        return json.loads(raw)

    async def get_documents(self, assessment_id: str) -> list[dict]:
        """Get documents for an assessment."""
        raw = await self.call_tool("get_documents", {
            "assessment_id": assessment_id,
        })
        return json.loads(raw)

    async def query_documents(
        self, assessment_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Semantic search within an assessment's documents."""
        raw = await self.call_tool("query_documents", {
            "assessment_id": assessment_id,
            "query": query,
            "top_k": top_k,
        })
        if raw == "No matching document chunks found.":
            return []
        return json.loads(raw)

    async def ask_question(self, assessment_id: str, question: str) -> dict:
        """RAG chat over vendor documents."""
        raw = await self.call_tool("ask_question", {
            "assessment_id": assessment_id,
            "question": question,
        })
        return json.loads(raw)

    async def run_assessment(
        self, assessment_id: str, vendor_name: str
    ) -> dict:
        """Trigger a full risk assessment."""
        raw = await self.call_tool("run_assessment", {
            "assessment_id": assessment_id,
            "vendor_name": vendor_name,
        })
        return json.loads(raw)

    async def get_assessment_report(self, assessment_id: str) -> dict:
        """Fetch a completed assessment report."""
        raw = await self.call_tool("get_assessment_report", {
            "assessment_id": assessment_id,
        })
        if raw == "Assessment not found.":
            return {}
        return json.loads(raw)

    async def get_controls(self) -> dict:
        """List all 20 security controls and domains."""
        raw = await self.call_tool("get_controls", {})
        return json.loads(raw)

    async def send_report(
        self, assessment_id: str, recipient_email: str
    ) -> dict:
        """Generate a PDF report and email it to a recipient."""
        raw = await self.call_tool("send_report", {
            "assessment_id": assessment_id,
            "recipient_email": recipient_email,
        })
        return json.loads(raw)


# ── LangChain Tool Wrappers ─────────────────────────────────────────────────
# These wrap MCPClient methods as LangChain StructuredTool objects so
# the LangGraph agent can use them directly.  Each tool has a typed
# Pydantic input schema for the LLM to fill.


# --- Input schemas ---

class QueryDocumentsInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID to search")
    query: str = Field(description="Natural-language search query")
    top_k: int = Field(default=5, description="Max results (default 5)")


class AskQuestionInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID")
    question: str = Field(description="Question to ask about the documents")


class RunAssessmentInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID")
    vendor_name: str = Field(description="The vendor's name")


class GetDocumentsInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID")


class GetReportInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID")


class SendReportInput(BaseModel):
    assessment_id: str = Field(description="The assessment ID")
    recipient_email: str = Field(description="Email address to send the report to")


# --- Singleton client ---

_client: MCPClient | None = None


def _get_client() -> MCPClient:
    """Return the singleton MCPClient."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client


def _run(coro):
    """Run an async coroutine from a sync context.

    LangChain tools are sync by default.  This helper bridges the gap.
    If an event loop is already running (e.g. inside FastAPI), it
    uses the existing loop.  Otherwise it creates a new one.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context (FastAPI, Jupyter, etc.)
        # Create a new thread to avoid "cannot run nested event loop"
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# --- Tool factory ---

def get_mcp_tools() -> list[StructuredTool]:
    """Return LangChain StructuredTool objects for all 7 MCP tools.

    These are what Layer 5 passes to the LangGraph agent.
    Each tool sends a JSON-RPC call through MCPClient → server → services.
    """
    client = _get_client()

    def list_assessments_fn() -> str:
        """List all vendor assessments with status and document counts."""
        return json.dumps(_run(client.list_assessments()), indent=2, default=str)

    def get_documents_fn(assessment_id: str) -> str:
        """Get all documents for an assessment."""
        return json.dumps(_run(client.get_documents(assessment_id)), indent=2, default=str)

    def query_documents_fn(assessment_id: str, query: str, top_k: int = 5) -> str:
        """Semantic search within an assessment's documents."""
        results = _run(client.query_documents(assessment_id, query, top_k))
        return json.dumps(results, indent=2, default=str) if results else "No matching chunks found."

    def ask_question_fn(assessment_id: str, question: str) -> str:
        """Ask a RAG question about vendor documents."""
        return json.dumps(_run(client.ask_question(assessment_id, question)), indent=2, default=str)

    def run_assessment_fn(assessment_id: str, vendor_name: str) -> str:
        """Trigger a full 20-control vendor risk assessment."""
        return json.dumps(_run(client.run_assessment(assessment_id, vendor_name)), indent=2, default=str)

    def get_report_fn(assessment_id: str) -> str:
        """Fetch a completed assessment report."""
        result = _run(client.get_assessment_report(assessment_id))
        return json.dumps(result, indent=2, default=str) if result else "Assessment not found."

    def get_controls_fn() -> str:
        """List all 20 NIST security controls and their domains."""
        return json.dumps(_run(client.get_controls()), indent=2, default=str)

    return [
        StructuredTool.from_function(
            func=list_assessments_fn,
            name="list_assessments",
            description="List all vendor assessments with status and document counts",
        ),
        StructuredTool.from_function(
            func=get_documents_fn,
            name="get_documents",
            description="Get all documents uploaded for a specific assessment",
            args_schema=GetDocumentsInput,
        ),
        StructuredTool.from_function(
            func=query_documents_fn,
            name="query_documents",
            description="Semantic search within an assessment's documents",
            args_schema=QueryDocumentsInput,
        ),
        StructuredTool.from_function(
            func=ask_question_fn,
            name="ask_question",
            description="Ask a RAG question about vendor documents",
            args_schema=AskQuestionInput,
        ),
        StructuredTool.from_function(
            func=run_assessment_fn,
            name="run_assessment",
            description="Trigger a full 20-control vendor risk assessment",
            args_schema=RunAssessmentInput,
        ),
        StructuredTool.from_function(
            func=get_report_fn,
            name="get_assessment_report",
            description="Fetch a completed assessment report",
            args_schema=GetReportInput,
        ),
        StructuredTool.from_function(
            func=get_controls_fn,
            name="get_controls",
            description="List all 20 NIST security controls and their domains",
        ),
        StructuredTool.from_function(
            func=lambda assessment_id, recipient_email: json.dumps(
                _run(client.send_report(assessment_id, recipient_email)),
                indent=2,
                default=str,
            ),
            name="send_report",
            description="Generate a PDF risk report and email it to a recipient",
            args_schema=SendReportInput,
        ),
    ]
