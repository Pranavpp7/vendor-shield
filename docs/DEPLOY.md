# Deploying VendorShield

VendorShield is **self-hosted**. Vendor documents are sensitive, and the
stack is heavy: PyTorch + BGE-large-en-v1.5 (~2–4 GB RAM, ~6 GB Docker
image) plus Qdrant. **There is no no-card public host that can run this
image.** Render / SnapDeploy / Railway free are 512 MB (the process will
OOM). Hugging Face Docker Spaces requires PRO. Oracle Always Free needs
a credit card.

For a portfolio demo, run it **on your laptop**. Seeded vendors work with
no LLM key. New scoring runs and Chat need Groq.

## 1. Local (recommended)

Prerequisites: Docker, Python 3.11+, Node 18+, a
[Groq](https://console.groq.com/keys) API key.

```bash
git clone https://github.com/Pranavpp7/vendor-shield-1.git
cd vendor-shield-1
docker compose up -d          # Qdrant
cd backend
cp .env.example .env          # paste the Groq key
uv sync
uv run python seed.py         # three demo vendors, $0 LLM
uv run start.py               # http://localhost:8000
```

Or one container for the whole stack:

```bash
cp deploy.env.example .env    # paste the Groq key
docker compose --profile full up -d --build
# → http://localhost:8000
```

`.env` (backend/ for `start.py`, repo root for compose):

```
OPENROUTER_BASE_URL=https://api.groq.com/openai/v1
OPENROUTER_MODEL=openai/gpt-oss-120b
OPENROUTER_API_KEY=gsk_...
LLM_CONCURRENCY=1
```

`llama-3.3-70b-versatile` 404s on Groq free (shutdown 2026-08-16).
`openai/gpt-oss-120b` is the local demo scorer. Without a filter it
failed the gate on 2026-10-25 (2 false-PASS on fake JSON in a PDF).
With the filter in `services/evaluation.py` it passed on 2026-10-29
(48/50 agreement, **zero false-PASS**, 100% citation faithfulness).
Eval-verified paid alternative: OpenRouter
`meta-llama/llama-3.3-70b-instruct` (~$0.006/run).

Seeded dashboard / compare / CSV / PDF work with Groq down. **Run** and
**Chat** need the key.

## 2. Why not a free public URL

| Host | Card? | Why it cannot run this app |
|---|---|---|
| Render / SnapDeploy free | No | 512 MB RAM |
| Railway free | No (tiny credit) | 0.5 GB RAM, 4 GB image cap |
| Fly.io | Yes | no free tier for new accounts |
| Hugging Face Docker Spaces | PRO | compute Spaces are not free to create |
| Oracle Always Free Ampere | Yes | only $0 VM that actually fits; not used here |

Compose still includes Caddy + `AUTO_SEED` if you later put this on a
machine you control. Do not tweet a live URL with `API_KEY` baked into
the SPA.

## 3. Read-only (`DEMO_MODE=1`)

Mutating requests return 403. Useful on a machine you do expose:

```
DEMO_MODE=1
AUTO_SEED=1
```

No LLM key required.

## Authentication tiers

| Configuration | Behavior |
|---|---|
| Neither `CLERK_JWKS_URL` nor `API_KEY` | Dev mode — fully open (localhost only!) |
| `API_KEY` set | Single-tenant shared secret: `X-API-Key` required on `/api` + `/mcp`. Frontend must be built with `VITE_API_KEY` (compose does this). |
| `CLERK_JWKS_URL` set | Multi-user Clerk JWT auth. |

## Checklist before exposing an instance

- [ ] `API_KEY` or Clerk (never dev-open beyond localhost)
- [ ] Groq `openai/gpt-oss-120b` + `LLM_CONCURRENCY=1`, or OpenRouter Llama
- [ ] `DEMO_MODE=1` if visitors should only view
- [ ] Do not open Qdrant (6333) to the internet
