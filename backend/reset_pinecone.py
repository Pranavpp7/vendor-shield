"""One-time script: delete old Pinecone index (768d) so the app recreates it at 1024d.

Usage:  cd backend && uv run reset_pinecone.py
"""

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from config import get_settings

settings = get_settings()
pc = Pinecone(api_key=settings.pinecone_api_key)

index_name = settings.pinecone_index_name
existing = [idx.name for idx in pc.list_indexes()]

if index_name in existing:
    print(f"⚠  Deleting Pinecone index '{index_name}' (old 768-dim)...")
    pc.delete_index(index_name)
    print(f"✅ Deleted. Next server startup will auto-create it with {settings.embedding_dimensions} dimensions.")
else:
    print(f"ℹ  Index '{index_name}' doesn't exist. It will be created on next startup.")
