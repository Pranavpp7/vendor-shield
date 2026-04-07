"""Supabase client for backend operations."""

from supabase import create_client, Client
from config import get_settings
import logging

logger = logging.getLogger(__name__)

_client: Client | None = None

def get_supabase() -> Client:
    """Get or initialize the Supabase client."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase credentials not configured in backend!")
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        logger.info("Supabase client initialized.")
    return _client
