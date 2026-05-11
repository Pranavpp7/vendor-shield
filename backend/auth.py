"""
Authentication via Clerk JWT.

RESPONSIBILITY:
    Verify the Clerk-issued JWT in the Authorization: Bearer <token> header
    and return the authenticated Clerk user ID (the JWT 'sub' claim).

    get_current_user() is the FastAPI dependency used by all protected routes.
    It replaces the old API-key-based verify_api_key().

DEV MODE (CLERK_JWKS_URL is empty):
    Verification is skipped entirely. An empty string is returned as the
    user_id. Storage functions treat "" as "no filter", so all data remains
    visible — identical to pre-auth behaviour.

PRODUCTION (CLERK_JWKS_URL is set):
    The JWT is verified against Clerk's public keys fetched from the JWKS URL.
    The 'sub' claim (e.g. "user_2abc123") is returned as the user_id.
    Requests without a valid token receive HTTP 401.

HOW TO CONFIGURE:
    1. Go to Clerk Dashboard → API Keys → Advanced → JWKS URL
    2. Set CLERK_JWKS_URL=https://<your-domain>/.well-known/jwks.json in .env
    3. Set VITE_CLERK_PUBLISHABLE_KEY=pk_... in the frontend .env.local
"""

import logging
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


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """FastAPI dependency — returns the Clerk user_id from the JWT.

    Usage (endpoint-level injection, value available in handler):
        @router.get("/foo")
        async def foo(user_id: str = Depends(get_current_user)):
            ...

    Usage (router-level guard only, value not needed):
        router = APIRouter(dependencies=[Depends(get_current_user)])
    """
    settings = get_settings()

    # Dev mode: skip verification, return empty user_id
    if not settings.clerk_jwks_url:
        return ""

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
