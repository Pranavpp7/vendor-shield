"""
Authentication via Clerk JWT.

RESPONSIBILITY:
    Verify the Clerk-issued JWT in the Authorization: Bearer <token> header
    and return the authenticated Clerk user ID (the JWT 'sub' claim).

    get_current_user() is the FastAPI dependency used by all protected routes.
    It replaces the old API-key-based verify_api_key().

THREE TIERS (checked in order):
    1. CLERK (CLERK_JWKS_URL set): full multi-user auth — the JWT is
       verified against Clerk's public keys; the 'sub' claim is the
       user_id.  Invalid/missing tokens → 401.
    2. API KEY (API_KEY set, no Clerk): single-tenant shared-secret auth
       for self-hosted deployments exposed beyond localhost.  Requests
       must send `X-API-Key: <key>` (or `Authorization: Bearer <key>`).
       user_id is "" (single tenant).  Wrong/missing key → 401.
    3. DEV MODE (neither set): verification skipped entirely, "" returned
       as user_id.  Local development only — main.py logs a loud warning.

HOW TO CONFIGURE:
    1. Go to Clerk Dashboard → API Keys → Advanced → JWKS URL
    2. Set CLERK_JWKS_URL=https://<your-domain>/.well-known/jwks.json in .env
    3. Set VITE_CLERK_PUBLISHABLE_KEY=pk_... in the frontend .env.local
"""

import logging
import secrets

from fastapi import Header, HTTPException
import jwt
from jwt import PyJWKClient, PyJWKClientError

from config import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton — PyJWKClient caches public keys so we don't
# fetch them on every request.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        _jwks_client = PyJWKClient(settings.clerk_jwks_url, cache_keys=True)
    return _jwks_client


def verify_api_key(provided: str | None) -> bool:
    """Constant-time comparison of a provided key against settings.api_key."""
    expected = get_settings().api_key
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided, expected)


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency — returns the authenticated user_id.

    Usage (endpoint-level injection, value available in handler):
        @router.get("/foo")
        async def foo(user_id: str = Depends(get_current_user)):
            ...

    Usage (router-level guard only, value not needed):
        router = APIRouter(dependencies=[Depends(get_current_user)])
    """
    settings = get_settings()

    # Tier 2: API-key auth (single tenant) when Clerk is not configured
    if not settings.clerk_jwks_url:
        if not settings.api_key:
            return ""  # Tier 3: dev mode — fully open
        bearer = (
            authorization.split(" ", 1)[1]
            if authorization and authorization.startswith("Bearer ")
            else None
        )
        if verify_api_key(x_api_key) or verify_api_key(bearer):
            return ""  # single-tenant: authenticated, no per-user identity
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key (send X-API-Key header)",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing or malformed (expected: Bearer <token>)",
        )

    token = authorization.split(" ", 1)[1]

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # Clerk doesn't set 'aud' by default in its JWT template.
            # Enable audience verification in Clerk if you add a custom template.
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except (jwt.InvalidTokenError, PyJWKClientError) as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token is missing subject claim")

    return user_id
