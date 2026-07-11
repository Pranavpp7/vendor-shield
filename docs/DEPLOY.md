# Deploying VendorShield

VendorShield is **self-hosted by design** — vendor documents are sensitive,
so the stack runs where you control it. Three deployment shapes, cheapest
first.

## 1. Single machine, one command (recommended)

Runs the full stack (app + Qdrant) in containers on any machine with Docker:

```bash
OPENROUTER_API_KEY=sk-... docker compose --profile full up -d
# → http://localhost:8000
```

The image bakes the embedding model (~6 GB image) so cold starts are fast.
SQLite + uploads persist in the `vendorshield_data` volume, vectors in
`qdrant_data`.

**If the machine is reachable by others, set an API key:**

```bash
API_KEY=$(openssl rand -hex 24)   # any long random string
OPENROUTER_API_KEY=sk-... API_KEY=$API_KEY docker compose --profile full up -d
```

With `API_KEY` set, every `/api` and `/mcp` request requires
`X-API-Key: <key>`. Build the frontend with `VITE_API_KEY=<key>` so the SPA
authenticates to its own backend. For real multi-user auth, configure Clerk
instead (below).

## 2. Free read-only demo (zero cost, zero risk)

For a public "look but don't touch" instance (e.g. Hugging Face Spaces free
tier, which accepts Dockerfiles):

```bash
DEMO_MODE=1
```

In demo mode every mutating request (uploads, runs, chat, overrides,
deletes) returns 403 with a friendly pointer to the repo — the instance
serves the seeded demo vendors read-only, so **zero LLM spend and zero
abuse surface by construction**. Bake the seed data in by running
`uv run python seed.py` during image build or on first boot.

## 3. Split services (Railway or similar)

Deploy the Dockerfile as the app service and a `qdrant/qdrant:v1.17.1`
container as a second service with private networking; set
`QDRANT_HOST=<qdrant service host>`. Note: the Qdrant client config speaks
plain host/port — Qdrant Cloud (API key + TLS) would need a small config
addition.

## Authentication tiers

| Configuration | Behavior |
|---|---|
| Neither `CLERK_JWKS_URL` nor `API_KEY` | Dev mode — fully open (localhost only!) |
| `API_KEY` set | Single-tenant shared secret: `X-API-Key` required on `/api` + `/mcp` |
| `CLERK_JWKS_URL` set | Multi-user Clerk JWT auth (set `VITE_CLERK_PUBLISHABLE_KEY` for the frontend); per-user data isolation |

## Checklist before exposing an instance

- [ ] `API_KEY` or Clerk configured (never dev-open beyond localhost)
- [ ] OpenRouter key is a **provisioned key with a credit limit** (caps
      worst-case spend if the key leaks)
- [ ] `DEMO_MODE=1` if the audience should only view, not run
- [ ] HTTPS termination in front (reverse proxy / platform default)
