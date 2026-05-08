"""
API Key authentication — shared admin key in the x-api-key header.

USAGE:
    from auth import verify_api_key
    from fastapi import Depends

    # Router-level (every endpoint protected):
    router = APIRouter(prefix="/api/...", dependencies=[Depends(verify_api_key)])

    # Per-endpoint (mixed public/protected routers):
    @router.get("/foo", dependencies=[Depends(verify_api_key)])

DEV MODE:
    If settings.api_key is the empty string, verification is skipped
    entirely — any request (with or without the header) is accepted.
"""

from fastapi import Header, HTTPException

from config import get_settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> bool:
    """Reject the request unless x-api-key matches settings.api_key.

    Returns True on success.  Raises 401 on mismatch.
    Returns True (skips verification) when settings.api_key is empty.
    """
    settings = get_settings()
    if not settings.api_key:
        return True
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
