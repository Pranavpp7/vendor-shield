# VendorShield — AI-Powered Vendor Risk Assessment Platform

An AI-powered vendor risk assessment system that compares uploaded vendor security/compliance documents against an internal control checklist using RAG (Retrieval-Augmented Generation).

## 🏗️ Architecture

```
Frontend (React + Vite)          FastAPI Backend (Python)
├── shadcn/ui components         ├── Document Ingestion (PDF/URL)
├── Tailwind CSS                 ├── Snowflake Arctic Embed (local)
├── Supabase Auth                ├── Pinecone Vector Store
└── Assessment Dashboard         ├── LangChain + LangGraph
                                 ├── Groq API (Llama 3.3 70B)
                                 └── MCP Server (JSON-RPC)
```

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI (Python), Swagger UI at `/docs` |
| **LLM** | Llama 3.3 70B via Groq API |
| **Embeddings** | Snowflake Arctic Embed M (768d, runs locally) |
| **Vector DB** | Pinecone (serverless, namespace per assessment) |
| **AI Framework** | LangChain + LangGraph |
| **Auth & DB** | Supabase (PostgreSQL + Auth + Storage) |
| **Protocol** | MCP (Model Context Protocol) for AI agent integration |

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- API keys: [Groq](https://console.groq.com), [Pinecone](https://app.pinecone.io), [Supabase](https://supabase.com)

### 1. Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Copy and fill in your API keys
cp .env.example .env
# Edit .env with your GROQ_API_KEY, PINECONE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

First startup will download the Snowflake Arctic embedding model (~400MB, one-time).

### 2. Frontend Setup

```bash
# From project root
npm install
npm run dev
```

### 3. Access the Application

- **Frontend UI**: http://localhost:8080
- **Swagger API Docs**: http://localhost:8000/docs
- **MCP Endpoint**: POST http://localhost:8000/mcp

## 📋 API Endpoints

### Documents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents/upload` | Upload PDF/DOCX → extract → chunk → embed → Pinecone |
| POST | `/api/documents/ingest-url` | Ingest URL content into Pinecone |
| GET | `/api/documents/{assessment_id}` | List documents for an assessment |
| DELETE | `/api/documents/{document_id}` | Delete document + vectors |

### Assessments
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/assessments/run` | Run full assessment (LangGraph workflow) |
| POST | `/api/assessments/{id}/rerun` | Re-run with latest docs |
| GET | `/api/assessments/{id}/report` | Get assessment report |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | RAG-powered Q&A over vendor docs |
| POST | `/api/chat/summary` | Generate executive summary |

### Controls
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/controls` | Get internal control checklist |

### MCP
| Method | Path | Description |
|--------|------|-------------|
| POST | `/mcp` | MCP JSON-RPC endpoint for AI agents |

## 🤖 MCP Tools

The MCP server exposes these tools for external AI agents (Claude, GPT, etc.):

- `list_assessments` — List all vendor assessments
- `get_documents` — List documents for an assessment
- `query_documents` — Semantic search in vendor docs
- `ask_question` — RAG-powered Q&A
- `run_assessment` — Trigger full risk assessment
- `get_assessment_report` — Get complete results

## 🔄 Assessment Pipeline (LangGraph)

```
check_documents → evaluate_controls → aggregate_scores → generate_summary
```

1. **Check Documents**: Verify if indexed documents exist in Pinecone
2. **Evaluate Controls**: For each of 20 internal controls:
   - Embed control name → search Pinecone for evidence
   - Inject evidence into prompt → Groq Llama evaluates
   - Returns: Pass / Partial / Fail / No Evidence + rationale + citations
3. **Aggregate Scores**: Weighted scoring per domain, overall risk level
4. **Generate Summary**: LLM-generated executive summary with recommendations

## 📁 Project Structure

```
vendor-shield-1/
├── backend/                    # FastAPI backend
│   ├── main.py                 # App entry point
│   ├── config.py               # Settings (env vars)
│   ├── models/
│   │   ├── schemas.py          # Pydantic models
│   │   └── controls.py         # Internal control checklist
│   ├── services/
│   │   ├── extraction.py       # PDF/URL text extraction
│   │   ├── chunking.py         # Text chunking
│   │   ├── embedding.py        # Snowflake Arctic Embed
│   │   ├── pinecone_store.py   # Pinecone operations
│   │   ├── ingestion.py        # Ingestion orchestrator
│   │   ├── retrieval.py        # Per-control evidence retrieval
│   │   ├── evaluation.py       # LangChain + Groq evaluation
│   │   ├── aggregation.py      # Score computation
│   │   └── chat.py             # RAG chat service
│   ├── chains/
│   │   └── assessment_graph.py # LangGraph assessment workflow
│   ├── routers/
│   │   ├── documents.py        # Document endpoints
│   │   ├── assessments.py      # Assessment endpoints
│   │   ├── controls.py         # Controls endpoints
│   │   └── chat.py             # Chat endpoints
│   └── mcp/
│       └── server.py           # MCP server
├── src/                        # React frontend
│   ├── pages/                  # UI pages
│   ├── components/             # Reusable components
│   ├── lib/api.ts              # FastAPI client
│   └── types/                  # TypeScript types
├── supabase/                   # Supabase migrations
└── package.json
```

## 🔑 Environment Variables

### Backend (`backend/.env`)
```
GROQ_API_KEY=gsk_...
PINECONE_API_KEY=pcsk_...
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...
```

### Frontend (`.env`)
```
VITE_SUPABASE_URL=https://...
VITE_SUPABASE_PUBLISHABLE_KEY=...
VITE_API_BASE_URL=http://localhost:8000
```
