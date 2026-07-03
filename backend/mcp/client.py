"""MCP Client — Python interface to the VendorShield MCP server.

RESPONSIBILITY:
    Sends JSON-RPC requests to the MCP server endpoint and returns
    parsed results.  This is the ONLY way Layer 5 (the LangGraph agent)
    interacts with the system's capabilities.

    Flow:  Agent → MCPClient.call_tool() → HTTP POST /mcp → server.py → services

IMPORTS FROM: config.py, httpx
IMPORTED BY:  chains/assessment_graph.py (Layer 5)
"""

import json
import logging

import httpx

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
        # One pooled HTTP client per MCPClient instance — avoids paying the
        # TCP/TLS handshake on every JSON-RPC call (the agent makes 20+
        # per assessment).
        self._http: httpx.AsyncClient | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=300.0)
        return self._http

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Call on app shutdown."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

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

        http = self._get_http()
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
        self, assessment_id: str, vendor_name: str, framework_id: str | None = None
    ) -> dict:
        """Trigger a full risk assessment."""
        args: dict = {
            "assessment_id": assessment_id,
            "vendor_name": vendor_name,
        }
        if framework_id:
            args["framework_id"] = framework_id
        raw = await self.call_tool("run_assessment", args)
        return json.loads(raw)

    async def get_assessment_report(self, assessment_id: str) -> dict:
        """Fetch a completed assessment report."""
        raw = await self.call_tool("get_assessment_report", {
            "assessment_id": assessment_id,
        })
        if raw == "Assessment not found.":
            return {}
        return json.loads(raw)

    async def get_controls(self, framework_id: str | None = None) -> dict:
        """List a framework's security controls and domains."""
        args = {"framework_id": framework_id} if framework_id else {}
        raw = await self.call_tool("get_controls", args)
        return json.loads(raw)

    async def list_frameworks(self) -> list[dict]:
        """List all available control frameworks."""
        raw = await self.call_tool("list_frameworks", {})
        return json.loads(raw)

    async def evaluate_controls(
        self, assessment_id: str, framework_id: str | None = None
    ) -> list[dict]:
        """Evaluate all controls for an assessment."""
        args: dict = {"assessment_id": assessment_id}
        if framework_id:
            args["framework_id"] = framework_id
        raw = await self.call_tool("evaluate_controls", args)
        return json.loads(raw)

    async def aggregate_scores(
        self,
        assessment_id: str,
        vendor_name: str,
        control_results: list[dict],
        framework_id: str | None = None,
    ) -> dict:
        """Aggregate control-level scores into an assessment summary."""
        args: dict = {
            "assessment_id": assessment_id,
            "vendor_name": vendor_name,
            "control_results": control_results,
        }
        if framework_id:
            args["framework_id"] = framework_id
        raw = await self.call_tool("aggregate_scores", args)
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
