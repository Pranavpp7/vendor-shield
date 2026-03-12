import { Hono } from "hono";
import { McpServer, StreamableHttpTransport } from "mcp-lite";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const app = new Hono();

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const mcpServer = new McpServer({
  name: "vendor-assessment-mcp",
  version: "1.0.0",
});

// Tool: List all assessments (from localStorage-based app, we read documents table for assessment IDs)
mcpServer.tool({
  name: "list_assessments",
  description: "List all vendor assessment IDs that have uploaded documents",
  inputSchema: {
    type: "object",
    properties: {},
  },
  handler: async () => {
    const supabase = createClient(supabaseUrl, supabaseKey);
    const { data, error } = await supabase
      .from("documents")
      .select("assessment_id, file_name, status, created_at")
      .order("created_at", { ascending: false });

    if (error) {
      return { content: [{ type: "text", text: `Error: ${error.message}` }] };
    }

    // Group by assessment_id
    const grouped: Record<string, any[]> = {};
    for (const doc of data || []) {
      if (!grouped[doc.assessment_id]) grouped[doc.assessment_id] = [];
      grouped[doc.assessment_id].push(doc);
    }

    const summary = Object.entries(grouped).map(([id, docs]) => ({
      assessment_id: id,
      document_count: docs.length,
      documents: docs.map(d => ({ file_name: d.file_name, status: d.status })),
    }));

    return {
      content: [{ type: "text", text: JSON.stringify(summary, null, 2) }],
    };
  },
});

// Tool: Query documents for a vendor assessment
mcpServer.tool({
  name: "query_documents",
  description: "Search document chunks for a specific vendor assessment using full-text search",
  inputSchema: {
    type: "object",
    properties: {
      assessment_id: { type: "string", description: "The assessment ID to search within" },
      query: { type: "string", description: "Search query to find relevant document chunks" },
      limit: { type: "number", description: "Max results to return (default 5)" },
    },
    required: ["assessment_id", "query"],
  },
  handler: async ({ assessment_id, query, limit }) => {
    const supabase = createClient(supabaseUrl, supabaseKey);
    const { data, error } = await supabase.rpc("search_document_chunks", {
      p_assessment_id: assessment_id,
      p_query: query,
      p_limit: limit || 5,
    });

    if (error) {
      return { content: [{ type: "text", text: `Error: ${error.message}` }] };
    }

    if (!data || data.length === 0) {
      return { content: [{ type: "text", text: "No matching document chunks found for this query." }] };
    }

    const results = data.map((r: any) => ({
      file: r.file_name,
      chunk: r.chunk_index,
      relevance: r.rank,
      content: r.content,
    }));

    return {
      content: [{ type: "text", text: JSON.stringify(results, null, 2) }],
    };
  },
});

// Tool: Ask a question with RAG context
mcpServer.tool({
  name: "ask_question",
  description: "Ask a question about a vendor assessment. Uses document context for grounded answers.",
  inputSchema: {
    type: "object",
    properties: {
      assessment_id: { type: "string", description: "The assessment ID" },
      question: { type: "string", description: "The question to ask" },
    },
    required: ["assessment_id", "question"],
  },
  handler: async ({ assessment_id, question }) => {
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Get document context via FTS
    const { data: chunks } = await supabase.rpc("search_document_chunks", {
      p_assessment_id: assessment_id,
      p_query: question,
      p_limit: 5,
    });

    const context = chunks?.map((c: any) => `[${c.file_name}, chunk ${c.chunk_index}]: ${c.content}`).join("\n\n") || "No documents found.";

    // Call AI
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      return { content: [{ type: "text", text: "AI not configured. Here is the raw context:\n\n" + context }] };
    }

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          { role: "system", content: "You are a vendor security assessment assistant. Answer questions using the provided document context. Cite specific documents when possible." },
          { role: "user", content: `Document context:\n${context}\n\nQuestion: ${question}` },
        ],
        max_tokens: 800,
        temperature: 0.7,
      }),
    });

    const data = await response.json();
    const reply = data.choices?.[0]?.message?.content || "Unable to generate response.";

    return { content: [{ type: "text", text: reply }] };
  },
});

// Tool: Get document list for an assessment
mcpServer.tool({
  name: "get_documents",
  description: "Get all documents uploaded for a specific assessment",
  inputSchema: {
    type: "object",
    properties: {
      assessment_id: { type: "string", description: "The assessment ID" },
    },
    required: ["assessment_id"],
  },
  handler: async ({ assessment_id }) => {
    const supabase = createClient(supabaseUrl, supabaseKey);
    const { data, error } = await supabase
      .from("documents")
      .select("id, file_name, file_size, content_type, status, created_at")
      .eq("assessment_id", assessment_id)
      .order("created_at", { ascending: false });

    if (error) {
      return { content: [{ type: "text", text: `Error: ${error.message}` }] };
    }

    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
    };
  },
});

const transport = new StreamableHttpTransport();

app.all("/*", async (c) => {
  return await transport.handleRequest(c.req.raw, mcpServer);
});

Deno.serve(app.fetch);
