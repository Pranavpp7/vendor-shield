# VendorShield — full-stack image (React SPA served by FastAPI)
#
# Build:  docker build -t vendorshield .
# Run:    docker run -p 8000:8000 -e OPENROUTER_API_KEY=... -e QDRANT_HOST=... vendorshield
# Or:     docker compose --profile full up   (app + Qdrant together)
#
# The BGE embedding model (~1.3 GB) is baked into the image at build
# time so cold starts don't download it. Expect a ~6 GB image (torch
# CPU + model weights) — that's the price of fully local embeddings.

# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json \
     tailwind.config.ts postcss.config.js components.json eslint.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

# ── Stage 2: Python backend + baked embedding model ─────────────────────────
FROM python:3.11-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/opt/hf-cache \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Install dependencies first (cached layer — only busts when the lock changes)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image
RUN uv run --no-project python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"

# Backend source + built frontend (main.py serves ../dist)
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=frontend /app/dist /app/dist

EXPOSE 8000

# No curl in slim images — health-check with stdlib
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["uv", "run", "--no-project", "python", "-c", \
         "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
