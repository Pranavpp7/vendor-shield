"""
Layer 2b: Local JSON File Storage.

RESPONSIBILITY:
    Structured data persistence using local JSON files.  Replaces Supabase
    completely.  Stores assessments, document metadata, and chat history
    under the ./data/ folder.

    This file handles ONLY reading and writing JSON — no business logic,
    no validation beyond basic file I/O, no vector operations.

    Limitation: no file locking.  This is acceptable for a single-user
    laptop application.  For multi-user deployment, add locking or
    switch to SQLite.

FILE LAYOUT:
    data/
    ├── assessments/{assessment_id}.json
    ├── documents/{document_id}.json
    └── chat/{assessment_id}.json          (array of messages)

IMPORTS FROM: config.py (for data_dir)
IMPORTED BY:  services/ingestion.py, routers/*, mcp/server.py
"""

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

from config import get_settings

logger = logging.getLogger(__name__)

_dirs_created = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    """Resolve the data directory as an absolute path.

    Path is relative to the backend/ folder (where config.py lives).
    """
    settings = get_settings()
    base = Path(__file__).resolve().parent.parent  # backend/
    return base / settings.data_dir


def _ensure_dirs() -> None:
    """Create the data folder structure on first call.  Cached so the
    filesystem check only happens once per process lifetime."""
    global _dirs_created
    if _dirs_created:
        return
    root = _data_dir()
    for sub in ("assessments", "documents", "chat"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _dirs_created = True
    logger.info(f"Data directory ready at {root}")


def _read_json(path: Path):
    """Read and parse a JSON file.

    Returns the parsed data (dict or list), or None if the file does
    not exist or is corrupted.  Never raises on bad data — logs an
    error with the full file path instead.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON file at {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return None


def _write_json(path: Path, data) -> None:
    """Atomically write data as JSON.

    Writes to a .tmp file first, then renames.  This prevents a crash
    mid-write from leaving a corrupted file on disk.
    """
    _ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)  # atomic on most filesystems
    except Exception as e:
        logger.error(f"Error writing {path}: {e}")
        # Clean up temp file if it exists
        if tmp.exists():
            tmp.unlink()
        raise


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    """Generate a unique ID (UUID4 hex, no dashes)."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Assessments — data/assessments/{assessment_id}.json
# ---------------------------------------------------------------------------


def save_assessment(assessment_id: str, data: dict) -> dict:
    """Save a new assessment record.

    Adds id, created_at, and updated_at fields automatically.
    Returns the saved record.
    """
    _ensure_dirs()
    record = {
        "id": assessment_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        **data,
    }
    path = _data_dir() / "assessments" / f"{assessment_id}.json"
    _write_json(path, record)
    logger.info(f"Saved assessment {assessment_id}")
    return record


def get_assessment(assessment_id: str) -> dict | None:
    """Load an assessment by ID.  Returns None if not found."""
    path = _data_dir() / "assessments" / f"{assessment_id}.json"
    return _read_json(path)


def update_assessment(assessment_id: str, updates: dict) -> dict | None:
    """Merge updates into an existing assessment.

    Bumps updated_at automatically.  Returns the updated record,
    or None if the assessment does not exist.
    """
    existing = get_assessment(assessment_id)
    if existing is None:
        logger.warning(f"Cannot update assessment {assessment_id}: not found")
        return None
    existing.update(updates)
    existing["updated_at"] = _now_iso()
    path = _data_dir() / "assessments" / f"{assessment_id}.json"
    _write_json(path, existing)
    logger.info(f"Updated assessment {assessment_id}")
    return existing


def delete_assessment(assessment_id: str) -> bool:
    """Delete an assessment file.  Returns True if deleted, False if not found."""
    path = _data_dir() / "assessments" / f"{assessment_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted assessment {assessment_id}")
        return True
    return False


def list_assessments() -> list[dict]:
    """Return all assessments, sorted by created_at descending (newest first)."""
    _ensure_dirs()
    folder = _data_dir() / "assessments"
    results = []
    for f in folder.glob("*.json"):
        record = _read_json(f)
        if record is not None:
            results.append(record)
    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Documents — data/documents/{document_id}.json
# ---------------------------------------------------------------------------


def save_document_meta(document_id: str, data: dict) -> dict:
    """Save document metadata (file name, size, assessment_id, status, etc.).

    Returns the saved record.
    """
    _ensure_dirs()
    record = {
        "id": document_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        **data,
    }
    path = _data_dir() / "documents" / f"{document_id}.json"
    _write_json(path, record)
    logger.info(f"Saved document metadata {document_id}")
    return record


def get_document_meta(document_id: str) -> dict | None:
    """Load document metadata by ID.  Returns None if not found."""
    path = _data_dir() / "documents" / f"{document_id}.json"
    return _read_json(path)


def update_document(document_id: str, updates: dict) -> dict | None:
    """Merge updates into existing document metadata.

    Bumps updated_at.  Returns updated record or None if not found.
    """
    existing = get_document_meta(document_id)
    if existing is None:
        logger.warning(f"Cannot update document {document_id}: not found")
        return None
    existing.update(updates)
    existing["updated_at"] = _now_iso()
    path = _data_dir() / "documents" / f"{document_id}.json"
    _write_json(path, existing)
    logger.info(f"Updated document {document_id}")
    return existing


def delete_document_meta(document_id: str) -> bool:
    """Delete a document metadata file.  Returns True if deleted."""
    path = _data_dir() / "documents" / f"{document_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted document metadata {document_id}")
        return True
    return False


def list_documents(assessment_id: str | None = None) -> list[dict]:
    """Return all document records, optionally filtered by assessment_id.

    Reads all JSON files in documents/ and filters in memory.
    This is fine for single-laptop scale.
    """
    _ensure_dirs()
    folder = _data_dir() / "documents"
    results = []
    for f in folder.glob("*.json"):
        record = _read_json(f)
        if record is None:
            continue
        if assessment_id and record.get("assessment_id") != assessment_id:
            continue
        results.append(record)
    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Chat history — data/chat/{assessment_id}.json  (array of messages)
# ---------------------------------------------------------------------------


def save_chat_message(assessment_id: str, role: str, content: str) -> dict:
    """Append a chat message to an assessment's chat history.

    Args:
        assessment_id: Which assessment this conversation belongs to.
        role: "user" or "assistant".
        content: The message text.

    Returns:
        The message dict that was appended.
    """
    _ensure_dirs()
    path = _data_dir() / "chat" / f"{assessment_id}.json"
    history = _read_json(path)
    if not isinstance(history, list):
        history = []

    message = {
        "role": role,
        "content": content,
        "timestamp": _now_iso(),
    }
    history.append(message)
    _write_json(path, history)
    return message


def get_chat_history(assessment_id: str) -> list[dict]:
    """Return the full chat history for an assessment.

    Returns an empty list if no chat history exists.
    """
    path = _data_dir() / "chat" / f"{assessment_id}.json"
    history = _read_json(path)
    if not isinstance(history, list):
        return []
    return history
