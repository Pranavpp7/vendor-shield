# VendorShield Backend

AI-powered vendor security risk assessment system. Evaluates vendor documents
against 20 security controls grounded in NIST SP 800-53 Rev.5.

## Architecture (7 Layers)

```
Layer 1: config.py           → All settings via pydantic BaseSettings
Layer 2: storage/            → Qdrant (vectors) + SQLite (structured data)
Layer 3: services/           → One file per responsibility (extract, chunk, embed, etc.)
Layer 4: mcp/                → MCP server (tools) + MCP client (agent interface)
Layer 5: chains/             → LangGraph agent workflow
Layer 6: routers/            → Thin FastAPI HTTP endpoints
Layer 7: main.py             → FastAPI app entry point
```

### Folder Structure

```
backend/
├── .env                     ← API keys (never commit)
├── .env.example             ← template showing what keys are needed
├── config.py                ← Layer 1: all settings
├── auth.py                  ← Clerk JWT verification; dev mode returns empty string
├── main.py                  ← Layer 7: FastAPI entry point
├── start.py                 ← build frontend + launch uvicorn; --dev for hot-reload
├── models/
│   ├── controls.py          ← 20 NIST controls (DO NOT MODIFY)
│   └── schemas.py           ← Pydantic request/response models
├── storage/
│   ├── qdrant_store.py      ← Layer 2: vector DB operations
│   └── local_store.py       ← Layer 2: SQLite operations (data/vendorshield.db, 3 tables: assessments, documents, chat_messages)
├── services/
│   ├── extraction.py        ← text from PDF/DOCX/URL
│   ├── chunking.py          ← split text into chunks
│   ├── embedding.py         ← text → 1024-dim vectors
│   ├── ingestion.py         ← orchestrates extract+chunk+embed+store
│   ├── retrieval.py         ← semantic search against Qdrant
│   ├── evaluation.py        ← scores one control via LLM
│   ├── aggregation.py       ← calculates final scores
│   ├── chat.py              ← RAG chat over documents
│   └── email_service.py     ← ReportLab PDF generation in memory + Resend email delivery
├── mcp/
│   ├── server.py            ← MCP server (exposes tools via SSE)
│   └── client.py            ← MCP client (used by agent)
├── chains/
│   └── assessment_graph.py  ← LangGraph agent
└── routers/
    ├── documents.py         ← document upload endpoints
    ├── assessments.py       ← assessment run endpoints
    ├── chat.py              ← chat endpoints
    ├── controls.py          ← controls list endpoint
    └── email.py             ← POST /api/email/send-report
```

### Data Flow

```
User uploads PDF
  → extraction.py reads text
  → chunking.py splits into 500-word chunks
  → embedding.py converts to 1024-dim vectors (BGE-large-en-v1.5)
  → qdrant_store.py stores vectors in collection "vendorshield_{assessment_id}"
  → local_store.py saves document metadata to SQLite (vendorshield.db)

User runs assessment
  → agent iterates 20 controls from controls.py
  → for each control: retrieval.py searches Qdrant using control["search_query"]
  → evaluation.py calls get_scoring_prompt() + sends to OpenRouter LLM
  → LLM returns: score, evidence_quote, reasoning, gap
  → aggregation.py calls calculate_scores() for final results
```

---

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 18+** with npm
- **Docker** (for Qdrant vector database)
- **OpenRouter API key** (https://openrouter.ai/keys)

## Package Managers

This project uses **two package managers**:

| Tool | Scope | Run from | Purpose |
|------|-------|----------|---------|
| **npm** | Frontend (React/Vite) | Project root `/` | JavaScript dependencies |
| **uv** | Backend (FastAPI/Python) | `backend/` folder | Python dependencies |

---

## Quick Start

### 1. Start Qdrant (run first)

Qdrant is the vector database. It runs in Docker.

```bash
# From the project root
docker-compose up -d
```

Verify it's running: open http://localhost:6333/dashboard

### 2. Backend Setup

```bash
# Navigate to backend folder
cd backend

# Install Python dependencies with uv
uv sync

# Create .env from template and add your OpenRouter API key
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=your_key_here

# Start the backend server
uv run uvicorn main:app --reload --port 8000
```

The API is now available at http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- MCP endpoint: http://localhost:8000/mcp

### 3. Frontend Setup

```bash
# From the project root (not backend/)
npm install

# Development mode (with hot reload)
npm run dev

# Or build for production (served by FastAPI)
npm run build
```

In production mode, the FastAPI backend serves the built frontend
from `dist/` — no separate frontend server needed.

---

### One-Command Start (Alternative)

Instead of steps 2–3 above, you can use `start.py` to build the frontend
and start the server in a single command:

```bash
# From the backend/ folder

# Production: build frontend + start server
uv run start.py

# Development: skip build, start with hot-reload
uv run start.py --dev

# Skip build but no hot-reload
uv run start.py --skip-build
```

---

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| LLM | OpenRouter (Llama 3.3 70B) | OpenAI-compatible API, structured JSON output |
| Embeddings | BGE-large-en-v1.5 | Local, free, 1024-dim vectors |
| Vector DB | Qdrant | Local Docker, no API key needed |
| Structured Data | SQLite (vendorshield.db) | 3 tables, zero config |
| AI Framework | LangChain + LangGraph | Orchestration + agent workflow |
| Protocol | MCP (Model Context Protocol) | Agent-to-tool communication |
| Backend | FastAPI | Python async web framework |
| Frontend | React + Vite + TypeScript | SPA served by FastAPI |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| OPENROUTER_API_KEY | Yes | — | OpenRouter API key for LLM inference |
| OPENROUTER_BASE_URL | No | https://openrouter.ai/api/v1 | OpenRouter base URL |
| OPENROUTER_MODEL | No | meta-llama/llama-3.3-70b-instruct | Model to use for assessment and chat |
| RESEND_API_KEY | Yes (email) | — | Resend API key for PDF email delivery |
| CLERK_JWKS_URL | No | "" | Clerk JWKS URL; empty string disables auth (dev mode) |
| API_KEY | No | vendorshield-dev-key-... | Static API key for MCP tool authentication |
| SERVER_PORT | No | 8000 | Port uvicorn listens on |
| QDRANT_HOST | No | localhost | Qdrant host |
| QDRANT_PORT | No | 6333 | Qdrant HTTP port |
| EMBEDDING_MODEL | No | BAAI/bge-large-en-v1.5 | Local embedding model |
| EMBEDDING_DIMENSIONS | No | 1024 | Vector dimensions (must match model) |
| CHUNK_SIZE | No | 500 | Token chunk size for document splitting |
| CHUNK_OVERLAP | No | 50 | Token overlap between chunks |
| RETRIEVAL_TOP_K | No | 8 | Chunks retrieved per control during assessment |
| DATA_DIR | No | data | Directory for SQLite DB |
| UPLOAD_DIR | No | data/uploads | Directory for raw uploaded files |

See `backend/.env.example` for a ready-to-copy template.
