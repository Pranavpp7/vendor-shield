"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Groq (LLM) ---
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Pinecone (Vector DB) ---
    pinecone_api_key: str
    pinecone_index_name: str = "vendor-shield"

    # --- Embedding ---
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimensions: int = 1024

    # --- Supabase (optional — frontend handles document metadata) ---
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # --- Chunking ---
    chunk_size: int = 500  # words
    chunk_overlap: int = 100  # words

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
