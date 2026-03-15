import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import {
  Layers, Database, Cloud, Brain, FileText, MessageSquare, Shield,
  Globe, Lock, Settings, BarChart3, ArrowRight, Play, Loader2,
  CheckCircle2, XCircle, Clock, Link2, Upload, Search, Bot,
  Zap, Eye, FileSearch, Server
} from "lucide-react";

/* ─── system layers ─── */
const layers = [
  {
    title: "Frontend — React + Vite + TypeScript",
    icon: Layers,
    color: "bg-primary/10 text-primary",
    items: [
      "Login / Signup with email verification (Lovable Cloud Auth)",
      "Dashboard with real-time assessment stats & risk distribution",
      "Assessment CRUD — create, evaluate, compare runs, generate summaries",
      "Document & URL ingestion with live indexing pipeline indicator",
      "AI Chat panel with RAG-grounded Q&A per assessment",
      "Customizable checklist schema editor (Settings page)",
      "Architecture & API Playground (this page)",
      "Protected routes, responsive sidebar, dark-mode-ready design system",
    ],
  },
  {
    title: "Backend Functions (Edge Functions)",
    icon: Cloud,
    color: "bg-accent/10 text-accent",
    items: [
      "parse-document — PDF/text extraction → chunking → Gemini embeddings → pgvector",
      "parse-url — web scraping → HTML stripping → chunking → embeddings → pgvector",
      "vendor-ai — per-control RAG retrieval → AI checklist evaluation, chat, summaries",
      "mcp-server — MCP Streamable HTTP protocol for external AI agents",
      "cleanup-assessment-assets — cascading deletion of storage & chunks",
    ],
  },
  {
    title: "Database & Storage",
    icon: Database,
    color: "bg-secondary/80 text-secondary-foreground",
    items: [
      "profiles — user display names & organizations (auto-created on signup)",
      "assessments — full assessment state incl. controls, chat history, scores",
      "assessment_runs — historical snapshots for run-over-run comparison",
      "documents — file/URL metadata with processing status tracking",
      "document_chunks — text chunks with pgvector embeddings (768-dim)",
      "checklist_schemas — per-user customizable control templates",
      "vendor-documents bucket — encrypted file storage with RLS",
    ],
  },
  {
    title: "RAG Pipeline (Retrieval-Augmented Generation)",
    icon: Brain,
    color: "bg-destructive/10 text-destructive",
    items: [
      "Ingestion: Upload/URL → parse → 500-word chunks (100-word overlap) → Gemini embedding-001",
      "Indexing: pgvector storage with HNSW index for fast cosine similarity",
      "Retrieval: Per-control semantic search → top-24 chunks from ≤8 unique sources",
      "Generation: Context injection → Gemini Flash → evidence-cited responses",
      "Public source fallback: well-known vendor features cited with live URLs",
    ],
  },
];

const techStack = [
  { name: "React 18", category: "Frontend" },
  { name: "Vite", category: "Build" },
  { name: "TypeScript", category: "Language" },
  { name: "Tailwind CSS", category: "Styling" },
  { name: "shadcn/ui", category: "Components" },
  { name: "Tanstack Query", category: "Data" },
  { name: "Lovable Cloud", category: "Backend" },
  { name: "pgvector", category: "Vector DB" },
  { name: "Gemini embedding-001", category: "Embeddings" },
  { name: "Gemini Flash", category: "LLM" },
  { name: "MCP Protocol", category: "Integration" },
  { name: "Deno Edge Functions", category: "Runtime" },
];

/* ─── API Playground ─── */
function EndpointTester() {
  const { toast } = useToast();
  const [loading, setLoading] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, { status: "success" | "error"; data: any; time: number } | null>>({});

  // inputs
  const [docUrl, setDocUrl] = useState("https://www.darwinbox.com/security");
  const [chatQuestion, setChatQuestion] = useState("Does this vendor support SSO?");
  const [mcpAssessmentId, setMcpAssessmentId] = useState("");

  const runTest = async (key: string, fn: () => Promise<any>) => {
    setLoading(key);
    setResults((r) => ({ ...r, [key]: null }));
    const start = Date.now();
    try {
      const data = await fn();
      setResults((r) => ({ ...r, [key]: { status: "success", data, time: Date.now() - start } }));
    } catch (err: any) {
      setResults((r) => ({ ...r, [key]: { status: "error", data: err.message || String(err), time: Date.now() - start } }));
    } finally {
      setLoading(null);
    }
  };

  const testParseUrl = () =>
    runTest("parse-url", async () => {
      const { data, error } = await supabase.functions.invoke("parse-url", {
        body: { url: docUrl, assessmentId: "test-architecture-demo", userId: null },
      });
      if (error) throw error;
      return data;
    });

  const testVendorAiChat = () =>
    runTest("vendor-ai-chat", async () => {
      const { data, error } = await supabase.functions.invoke("vendor-ai", {
        body: { action: "chat", question: chatQuestion, context: "Test assessment context from Architecture page", assessmentId: mcpAssessmentId || undefined },
      });
      if (error) throw error;
      return data;
    });

  const testVendorAiChecklist = () =>
    runTest("vendor-ai-checklist", async () => {
      const { data, error } = await supabase.functions.invoke("vendor-ai", {
        body: {
          action: "generate-checklist",
          vendorName: "Test Vendor",
          controls: [
            { id: "test-1", category: "Security", name: "MFA enforced for all users" },
            { id: "test-2", category: "Security", name: "Data encryption at rest" },
          ],
          assessmentId: mcpAssessmentId || undefined,
        },
      });
      if (error) throw error;
      return data;
    });

  const testMcpListAssessments = () =>
    runTest("mcp-list", async () => {
      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
      const res = await fetch(`${supabaseUrl}/functions/v1/mcp-server`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json, text/event-stream",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "tools/call",
          params: { name: "list_assessments", arguments: {} },
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    });

  const testMcpAsk = () =>
    runTest("mcp-ask", async () => {
      if (!mcpAssessmentId) throw new Error("Enter an Assessment ID first");
      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
      const res = await fetch(`${supabaseUrl}/functions/v1/mcp-server`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json, text/event-stream",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 2,
          method: "tools/call",
          params: { name: "ask_question", arguments: { assessment_id: mcpAssessmentId, question: chatQuestion } },
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    });

  const ResultBlock = ({ testKey }: { testKey: string }) => {
    const r = results[testKey];
    if (!r) return null;
    return (
      <div className={`mt-3 rounded-lg border p-3 text-xs font-mono ${r.status === "success" ? "border-accent/30 bg-accent/5" : "border-destructive/30 bg-destructive/5"}`}>
        <div className="flex items-center gap-2 mb-2">
          {r.status === "success" ? <CheckCircle2 className="h-3.5 w-3.5 text-accent" /> : <XCircle className="h-3.5 w-3.5 text-destructive" />}
          <span className={r.status === "success" ? "text-accent" : "text-destructive"}>{r.status.toUpperCase()}</span>
          <span className="text-muted-foreground ml-auto flex items-center gap-1"><Clock className="h-3 w-3" />{r.time}ms</span>
        </div>
        <pre className="whitespace-pre-wrap break-all max-h-48 overflow-auto text-[11px] text-muted-foreground">
          {typeof r.data === "string" ? r.data : JSON.stringify(r.data, null, 2)}
        </pre>
      </div>
    );
  };

  const isLoading = (key: string) => loading === key;

  return (
    <div className="space-y-4">
      {/* Shared inputs */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Settings className="h-4 w-4 text-muted-foreground" /> Test Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Assessment ID (optional, for RAG context)</label>
              <Input value={mcpAssessmentId} onChange={(e) => setMcpAssessmentId(e.target.value)} placeholder="paste an assessment ID…" className="text-xs h-8" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Question / Query</label>
              <Input value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)} placeholder="Ask something…" className="text-xs h-8" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* parse-url */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Globe className="h-4 w-4 text-accent" /> parse-url
              <Badge variant="outline" className="text-[10px] font-mono">POST</Badge>
            </CardTitle>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={testParseUrl} disabled={!!loading}>
              {isLoading("parse-url") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Run
            </Button>
          </div>
          <CardDescription className="text-xs">Scrapes a URL, chunks text, generates Gemini embeddings, stores in pgvector</CardDescription>
        </CardHeader>
        <CardContent>
          <Input value={docUrl} onChange={(e) => setDocUrl(e.target.value)} placeholder="https://example.com/security" className="text-xs h-8" />
          <ResultBlock testKey="parse-url" />
        </CardContent>
      </Card>

      {/* vendor-ai chat */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" /> vendor-ai / chat
              <Badge variant="outline" className="text-[10px] font-mono">POST</Badge>
            </CardTitle>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={testVendorAiChat} disabled={!!loading}>
              {isLoading("vendor-ai-chat") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Run
            </Button>
          </div>
          <CardDescription className="text-xs">AI Q&A with optional RAG document context</CardDescription>
        </CardHeader>
        <CardContent>
          <ResultBlock testKey="vendor-ai-chat" />
        </CardContent>
      </Card>

      {/* vendor-ai checklist */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-primary" /> vendor-ai / generate-checklist
              <Badge variant="outline" className="text-[10px] font-mono">POST</Badge>
            </CardTitle>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={testVendorAiChecklist} disabled={!!loading}>
              {isLoading("vendor-ai-checklist") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Run
            </Button>
          </div>
          <CardDescription className="text-xs">Evaluates controls against uploaded evidence or public knowledge</CardDescription>
        </CardHeader>
        <CardContent>
          <ResultBlock testKey="vendor-ai-checklist" />
        </CardContent>
      </Card>

      {/* MCP list_assessments */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4 text-accent" /> MCP / list_assessments
              <Badge variant="outline" className="text-[10px] font-mono">JSON-RPC</Badge>
            </CardTitle>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={testMcpListAssessments} disabled={!!loading}>
              {isLoading("mcp-list") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Run
            </Button>
          </div>
          <CardDescription className="text-xs">Lists all assessments with uploaded documents via MCP Streamable HTTP</CardDescription>
        </CardHeader>
        <CardContent>
          <ResultBlock testKey="mcp-list" />
        </CardContent>
      </Card>

      {/* MCP ask_question */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Bot className="h-4 w-4 text-accent" /> MCP / ask_question
              <Badge variant="outline" className="text-[10px] font-mono">JSON-RPC</Badge>
            </CardTitle>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={testMcpAsk} disabled={!!loading}>
              {isLoading("mcp-ask") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Run
            </Button>
          </div>
          <CardDescription className="text-xs">RAG-powered Q&A via MCP protocol (requires Assessment ID)</CardDescription>
        </CardHeader>
        <CardContent>
          <ResultBlock testKey="mcp-ask" />
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Main page ─── */
export default function Architecture() {
  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-8 pb-12">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Shield className="h-8 w-8 text-accent" />
            Vendor Shield — System Architecture
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            End-to-end vendor risk assessment platform built on Lovable with AI-powered checklist evaluation, 
            RAG-based document intelligence, and MCP integration for external AI agents.
          </p>
        </div>

        {/* Tech stack badges */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-5 w-5 text-accent" /> Technology Stack
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {techStack.map((t) => (
                <Badge key={t.name} variant="secondary" className="text-xs px-2.5 py-1">
                  <span className="text-muted-foreground mr-1.5">{t.category}:</span> {t.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview" className="gap-1.5"><Eye className="h-3.5 w-3.5" /> System Overview</TabsTrigger>
            <TabsTrigger value="flow" className="gap-1.5"><ArrowRight className="h-3.5 w-3.5" /> Data Flows</TabsTrigger>
            <TabsTrigger value="playground" className="gap-1.5"><Play className="h-3.5 w-3.5" /> API Playground</TabsTrigger>
          </TabsList>

          {/* ── Overview tab ── */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              {layers.map((layer) => (
                <Card key={layer.title}>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <div className={`p-1.5 rounded-md ${layer.color}`}>
                        <layer.icon className="h-4 w-4" />
                      </div>
                      {layer.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      {layer.items.map((item, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-accent mt-0.5">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* MCP tools */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageSquare className="h-5 w-5 text-primary" />
                  MCP Server — External AI Agent Interface
                </CardTitle>
                <CardDescription>
                  Exposes vendor assessment data and RAG-powered Q&A to external AI agents (Claude, GPT, etc.) via the MCP Streamable HTTP protocol.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {[
                    { tool: "list_assessments", desc: "Get all assessments with document counts" },
                    { tool: "get_documents", desc: "List documents for an assessment" },
                    { tool: "query_documents", desc: "Semantic search across document chunks" },
                    { tool: "ask_question", desc: "RAG-powered Q&A with cited sources" },
                  ].map(({ tool, desc }) => (
                    <div key={tool} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                      <Badge variant="outline" className="font-mono text-[10px]">{tool}</Badge>
                      <span className="text-muted-foreground text-xs">{desc}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Key features list */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" /> Key Features Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    { icon: Lock, label: "Email Auth with verification + protected routes" },
                    { icon: FileText, label: "PDF & text document upload with real-time indexing" },
                    { icon: Link2, label: "URL scraping and indexing into RAG pipeline" },
                    { icon: Brain, label: "AI-powered checklist evaluation per control" },
                    { icon: Search, label: "Semantic vector search (pgvector + cosine similarity)" },
                    { icon: MessageSquare, label: "RAG-grounded AI chat per assessment" },
                    { icon: BarChart3, label: "Run history with side-by-side comparison" },
                    { icon: Eye, label: "Executive summary generation with document citations" },
                    { icon: Globe, label: "Public source evidence with clickable URL badges" },
                    { icon: Upload, label: "Evidence badges — Uploaded Document vs Public Source" },
                    { icon: Settings, label: "Customizable checklist schema (add/edit/delete)" },
                    { icon: Bot, label: "MCP server for external AI agent integration" },
                  ].map(({ icon: Icon, label }, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <Icon className="h-4 w-4 text-accent mt-0.5 shrink-0" />
                      <span className="text-muted-foreground">{label}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Data Flows tab ── */}
          <TabsContent value="flow" className="space-y-6">
            {/* Document ingestion flow */}
            <Card className="border-dashed border-2 border-muted">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Upload className="h-5 w-5 text-accent" /> Document Ingestion Pipeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium">
                  {["Upload PDF/Text", "→", "parse-document", "→", "Extract Text (unpdf)", "→", "Chunk (500w / 100 overlap)", "→", "Gemini embedding-001", "→", "pgvector Storage", "→", "Status: ready"].map((step, i) =>
                    step === "→" ? (
                      <ArrowRight key={i} className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Badge key={i} variant="secondary" className="px-2.5 py-1 text-[11px]">{step}</Badge>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* URL ingestion flow */}
            <Card className="border-dashed border-2 border-muted">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Globe className="h-5 w-5 text-accent" /> URL Ingestion Pipeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium">
                  {["Paste URL", "→", "parse-url", "→", "Fetch & Strip HTML", "→", "Chunk (500w / 100 overlap)", "→", "Gemini embedding-001", "→", "pgvector Storage", "→", "Status: ready"].map((step, i) =>
                    step === "→" ? (
                      <ArrowRight key={i} className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Badge key={i} variant="secondary" className="px-2.5 py-1 text-[11px]">{step}</Badge>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* RAG evaluation flow */}
            <Card className="border-dashed border-2 border-muted">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Brain className="h-5 w-5 text-destructive" /> RAG Checklist Evaluation
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium">
                  {["Run Checklist", "→", "Per-Control Embedding", "→", "Cosine Similarity (top-24)", "→", "≤8 Unique Sources", "→", "Context Injection", "→", "Gemini Flash", "→", "Pass / Fail / Needs Info"].map((step, i) =>
                    step === "→" ? (
                      <ArrowRight key={i} className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Badge key={i} variant="secondary" className="px-2.5 py-1 text-[11px]">{step}</Badge>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* MCP flow */}
            <Card className="border-dashed border-2 border-muted">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bot className="h-5 w-5 text-primary" /> MCP Agent Interaction
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium">
                  {["External AI Agent", "→", "JSON-RPC over HTTP", "→", "mcp-server", "→", "Tool Router", "→", "Database / RAG / AI", "→", "Structured Response"].map((step, i) =>
                    step === "→" ? (
                      <ArrowRight key={i} className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Badge key={i} variant="secondary" className="px-2.5 py-1 text-[11px]">{step}</Badge>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Assessment lifecycle */}
            <Card className="border-dashed border-2 border-muted">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <ClipboardList className="h-5 w-5 text-primary" /> Assessment Lifecycle
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center justify-center gap-2 text-sm font-medium">
                  {["Create Assessment", "→", "Upload Docs / URLs", "→", "Wait for Indexing", "→", "Run Checklist (AI)", "→", "Review & Chat", "→", "Compare Runs", "→", "Generate Summary", "→", "Export / Share"].map((step, i) =>
                    step === "→" ? (
                      <ArrowRight key={i} className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Badge key={i} variant="secondary" className="px-2.5 py-1 text-[11px]">{step}</Badge>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Playground tab ── */}
          <TabsContent value="playground" className="space-y-4">
            <Card className="bg-accent/5 border-accent/20">
              <CardContent className="pt-4">
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground">Live API Playground</strong> — Test each backend endpoint directly. 
                  Results show response data, status, and latency. All endpoints hit the live backend functions.
                </p>
              </CardContent>
            </Card>
            <EndpointTester />
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
