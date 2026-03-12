

# RAG + MCP Server Plan for Vendor Assessment Tool

## What You Want
- **RAG**: Upload vendor documents (SOC 2 reports, policies, etc.), extract and chunk their text, store embeddings, and use them as context when the AI answers questions or generates checklist results.
- **MCP Server**: Expose your assessment data/tools via an MCP-compatible endpoint so external AI agents (Claude Desktop, Cursor, etc.) can query your vendor assessments.

## The "Completely Free" Reality Check

Here is what is achievable at zero additional cost using what you already have:

| Component | Free Approach |
|-----------|--------------|
| Document parsing | Parse PDFs/text in an Edge Function (basic text extraction) |
| Embeddings | Use Lovable AI (Gemini) to generate embeddings — **not supported**. Gemini models on the gateway are chat-completion only, no embedding endpoint. |
| Vector storage | Supabase has `pgvector` but you need embeddings to store. |
| RAG retrieval | Without embeddings, use **keyword/full-text search** as a free alternative |
| MCP Server | Build as a Supabase Edge Function using `mcp-lite` — fully free |

### The Embedding Problem

The Lovable AI gateway only exposes `/v1/chat/completions`. It does not support `/v1/embeddings`. This means:
- You cannot generate vector embeddings for free through Lovable AI
- True semantic vector search requires an embeddings API (OpenAI, Cohere, etc.) which costs money

### Two Paths Forward

**Path A — Free: Full-Text Search RAG (No Embeddings)**
Use Postgres full-text search (`tsvector`) instead of vector similarity. Less precise than semantic search but fully functional and zero cost.

**Path B — Paid: True Vector RAG**
Requires an external embeddings API key (e.g., OpenAI `text-embedding-3-small` at ~$0.02/1M tokens — very cheap but not free).

## Recommended Plan: Path A (Free Full-Text Search RAG)

### Architecture

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Upload Doc  │────▶│  Edge Function   │────▶│  Supabase   │
│  (Frontend)  │     │  parse-document  │     │  DB Tables  │
└─────────────┘     │  - extract text  │     │  - chunks   │
                    │  - split chunks  │     │  - tsvector  │
                    └──────────────────┘     └──────┬──────┘
                                                    │
┌─────────────┐     ┌──────────────────┐           │
│  Chat / AI  │────▶│  vendor-ai       │───────────┘
│  Question   │     │  - FTS query     │  retrieve top-K
└─────────────┘     │  - inject context│  chunks as context
                    │  - Gemini call   │
                    └──────────────────┘
```

### Step-by-Step Implementation

**1. Database: Create document storage tables**
```sql
-- Store uploaded document metadata
CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id text NOT NULL,
  file_name text NOT NULL,
  file_size integer,
  content_type text,
  created_at timestamptz DEFAULT now()
);

-- Store text chunks with full-text search
CREATE TABLE public.document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES public.documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX idx_chunks_fts ON public.document_chunks USING GIN (fts);
```

**2. Storage bucket** for actual file uploads (PDFs, docs).

**3. Edge Function: `parse-document`**
- Receives uploaded file from storage
- Extracts raw text (for PDFs: basic text extraction in Deno)
- Splits into ~500-word overlapping chunks
- Inserts chunks into `document_chunks` table

**4. Update `vendor-ai` Edge Function**
- Before calling Gemini, run a full-text search query against `document_chunks` for the assessment
- Inject top 5-10 matching chunks into the system prompt as context
- Gemini then answers grounded in actual document content

**5. Frontend changes**
- Update `DocsLinksSection` to upload files to Supabase Storage (not just store metadata)
- Show processing status (parsing, chunked, ready)
- Chat panel gets "grounded" responses referencing actual documents

### MCP Server

**6. Edge Function: `mcp-server`** using `mcp-lite`
- Expose tools like:
  - `list_assessments` — returns all vendor assessments
  - `get_assessment` — returns details for a specific vendor
  - `query_documents` — searches document chunks for a vendor
  - `ask_question` — runs a RAG query against a vendor's documents
- This lets external AI tools (Claude Desktop, etc.) query your assessment data

### Limitations of the Free Approach

- **Full-text search** matches keywords, not meaning. "Does the vendor encrypt data at rest?" will find chunks containing "encrypt" and "data" but might miss passages that discuss "AES-256 storage protection" without using those exact words.
- **PDF text extraction** in Deno is basic — complex PDFs with tables/images may not parse well. For production, a paid service like Adobe PDF Extract or a Python-based parser would be better.
- **No authentication** on the current app — documents stored in Supabase will need RLS policies once auth is added.

### What This Gets You

- Users upload real vendor documents (SOC 2 reports, policies, questionnaires)
- AI chat answers are grounded in actual document content, not hallucinated
- Evidence source tags link back to specific document chunks
- External AI agents can query your assessment data via MCP

