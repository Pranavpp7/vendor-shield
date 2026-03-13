import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Layers, Database, Cloud, Brain, FileText, MessageSquare, Shield } from "lucide-react";

const layers = [
  {
    title: "Frontend (React + Vite + TypeScript)",
    icon: Layers,
    color: "bg-primary/10 text-primary",
    items: [
      "Login, Dashboard, Assessments, Assessment Detail pages",
      "AuthContext (Lovable Cloud auth) + AssessmentContext (state)",
      "shadcn/ui component library + Tailwind CSS design system",
      "Protected routes with role-based access",
    ],
  },
  {
    title: "Backend Functions",
    icon: Cloud,
    color: "bg-accent/10 text-accent",
    items: [
      "parse-document — extracts text, chunks, generates Gemini embeddings (768d)",
      "vendor-ai — embeds query → vector search → contextual AI response",
      "mcp-server — exposes tools for external AI agents via MCP protocol",
    ],
  },
  {
    title: "Database & Storage",
    icon: Database,
    color: "bg-secondary/80 text-secondary-foreground",
    items: [
      "profiles — user display names & organizations",
      "documents — uploaded file metadata & processing status",
      "document_chunks — text chunks with pgvector embeddings (768d)",
      "vendor-documents storage bucket for file uploads",
    ],
  },
  {
    title: "RAG Pipeline",
    icon: Brain,
    color: "bg-destructive/10 text-destructive",
    items: [
      "Upload → parse & chunk → Gemini embedding → pgvector storage",
      "Query → embed question → cosine similarity search → top-K retrieval",
      "Context injection → Gemini AI generates grounded response",
    ],
  },
];

export default function Architecture() {
  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Shield className="h-8 w-8 text-accent" />
            System Architecture
          </h1>
          <p className="text-muted-foreground mt-2">
            High-level overview of Vendor Shield's technical architecture and data flow.
          </p>
        </div>

        {/* Flow diagram as styled cards */}
        <Card className="border-dashed border-2 border-muted">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5" /> End-to-End Document Flow
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center justify-center gap-3 text-sm font-medium">
              {[
                "Upload Document",
                "→",
                "Parse & Chunk",
                "→",
                "Generate Embeddings",
                "→",
                "Store in pgvector",
                "→",
                "User Asks Question",
                "→",
                "Embed Query",
                "→",
                "Cosine Similarity Search",
                "→",
                "AI Response with Context",
              ].map((step, i) =>
                step === "→" ? (
                  <span key={i} className="text-muted-foreground text-lg">→</span>
                ) : (
                  <Badge key={i} variant="secondary" className="px-3 py-1.5 text-xs">
                    {step}
                  </Badge>
                )
              )}
            </div>
          </CardContent>
        </Card>

        {/* Architecture layers */}
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
                      <span className="text-accent mt-1">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* MCP Integration */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              MCP Server (External AI Agent Interface)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {["list_assessments", "get_documents", "query_documents", "ask_question"].map((tool) => (
                <Badge key={tool} variant="outline" className="font-mono text-xs">
                  {tool}
                </Badge>
              ))}
            </div>
            <p className="text-sm text-muted-foreground mt-3">
              Exposes assessment data and RAG-powered Q&A to external AI agents via the MCP Streamable HTTP protocol.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
