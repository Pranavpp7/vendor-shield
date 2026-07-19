"""
Layer 2b: Local SQLite Storage.

RESPONSIBILITY:
    Structured data persistence using a single SQLite database file.
    Stores assessments, document metadata, and chat history in three tables.

    This file handles ONLY database I/O — no business logic, no validation
    beyond basic typing, no vector operations.

DATABASE LAYOUT:
    data/vendorshield.db
        ├── assessments      — id, vendor_name, status, score,
        │                       domain_scores (JSON), control_results (JSON),
        │                       gaps_summary, created_at, updated_at, extra (JSON)
        ├── documents        — id, assessment_id, filename, file_type,
        │                       chunk_count, uploaded_at, extra (JSON)
        ├── chat_messages    — id, assessment_id, role, content,
        │                       citations (JSON), created_at
        └── eval_runs        — golden-gate history: agreement, threshold,
                                passed, duration, detail (JSON w/ model +
                                prompt hash)

    The `extra` columns hold any additional fields from the input dict
    (e.g. run_history, notes, chat_history, upload_path) so callers
    that round-trip arbitrary data through save/get keep working.

IMPORTS FROM: config.py (for data_dir)
IMPORTED BY:  services/ingestion.py, routers/*, mcp/server.py, main.py
"""

import json
import uuid
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _db_path() -> Path:
    """Resolve the SQLite database file path as an absolute path.

    Path is relative to the backend/ folder.  The parent directory
    is created if it doesn't exist.
    """
    settings = get_settings()
    base = Path(__file__).resolve().parent.parent  # backend/
    db_dir = base / settings.data_dir
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "vendorshield.db"


def _connect() -> sqlite3.Connection:
    """Open a SQLite connection with row-as-dict access enabled."""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    """Generate a unique ID (UUID4 hex, no dashes)."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id              TEXT PRIMARY KEY,
    vendor_name     TEXT,
    status          TEXT,
    score           REAL,
    domain_scores   TEXT,
    control_results TEXT,
    gaps_summary    TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    user_id         TEXT DEFAULT '',
    extra           TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    assessment_id TEXT,
    filename      TEXT,
    file_type     TEXT,
    chunk_count   INTEGER,
    uploaded_at   TEXT,
    extra         TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id            TEXT PRIMARY KEY,
    assessment_id TEXT,
    role          TEXT,
    content       TEXT,
    citations     TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    agreed      INTEGER,
    total       INTEGER,
    agreement   INTEGER,
    threshold   INTEGER,
    passed      INTEGER,
    duration_s  REAL,
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_assessment
    ON documents(assessment_id);

CREATE INDEX IF NOT EXISTS idx_chat_assessment
    ON chat_messages(assessment_id);
"""


def init_db() -> None:
    """Create all tables and indexes if they don't already exist.

    Called once on application startup from main.py lifespan.
    Idempotent — safe to call repeatedly.
    """
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # Add user_id column to existing databases that predate the Clerk migration.
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we try/ignore.
        try:
            conn.execute(
                "ALTER TABLE assessments ADD COLUMN user_id TEXT DEFAULT ''"
            )
            logger.info("Migrated: added user_id column to assessments table")
        except Exception:
            pass  # column already exists — nothing to do
        # Drop the never-populated llm_calls table from databases created
        # while it existed (per-call telemetry went to Langfuse instead).
        conn.execute("DROP TABLE IF EXISTS llm_calls")
    logger.info(f"SQLite database ready at {_db_path()}")


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------


# Columns that have their own dedicated SQL field.  Anything else in the
# input dict gets serialized into the `extra` JSON column.
_ASSESSMENT_COLUMNS = {
    "id", "vendor_name", "status", "overall_score",
    "domain_scores", "control_results", "gaps_summary",
    "created_at", "updated_at", "user_id",
}


def _row_to_assessment(row: sqlite3.Row | None) -> dict | None:
    """Inflate a DB row back to the dict shape callers expect."""
    if row is None:
        return None
    record: dict = {
        "id": row["id"],
        "vendor_name": row["vendor_name"] or "",
        "status": row["status"] or "",
        "overall_score": row["score"] if row["score"] is not None else 0,
        "domain_scores": json.loads(row["domain_scores"]) if row["domain_scores"] else {},
        "control_results": json.loads(row["control_results"]) if row["control_results"] else [],
        "gaps_summary": row["gaps_summary"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
        "user_id": row["user_id"] or "",
    }
    if row["extra"]:
        try:
            for k, v in json.loads(row["extra"]).items():
                if k not in record:
                    record[k] = v
        except json.JSONDecodeError:
            logger.warning(f"Corrupt extra JSON for assessment {row['id']}")
    return record


def save_assessment(assessment_id: str, data: dict) -> dict:
    """Insert or replace an assessment record.

    Adds id, created_at, and updated_at fields automatically.
    Returns the saved record (same shape as get_assessment).
    """
    record = {**data, "id": assessment_id}
    record.setdefault("created_at", _now_iso())
    record["updated_at"] = _now_iso()

    extra = {k: v for k, v in record.items() if k not in _ASSESSMENT_COLUMNS}

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO assessments
                (id, vendor_name, status, score,
                 domain_scores, control_results, gaps_summary,
                 created_at, updated_at, user_id, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                record.get("vendor_name", ""),
                record.get("status", ""),
                record.get("overall_score", 0),
                json.dumps(record.get("domain_scores", {}), default=str),
                json.dumps(record.get("control_results", []), default=str),
                record.get("gaps_summary", ""),
                record["created_at"],
                record["updated_at"],
                record.get("user_id", ""),
                json.dumps(extra, default=str),
            ),
        )

    logger.info(f"Saved assessment {assessment_id}")
    return record


def get_assessment(assessment_id: str) -> dict | None:
    """Load an assessment by ID.  Returns None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
    return _row_to_assessment(row)


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
    save_assessment(assessment_id, existing)
    logger.info(f"Updated assessment {assessment_id}")
    return existing


def delete_assessment(assessment_id: str) -> bool:
    """Delete an assessment row.  Returns True if a row was removed."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM assessments WHERE id = ?",
            (assessment_id,),
        )
        deleted = cursor.rowcount > 0
    if deleted:
        logger.info(f"Deleted assessment {assessment_id}")
    return deleted


def list_assessments(user_id: str = "") -> list[dict]:
    """Return assessments sorted newest first.

    When user_id is non-empty (production mode) only rows owned by that user
    are returned.  When user_id is "" (dev mode) all rows are returned so
    existing data is still visible without auth configured.
    """
    with _connect() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assessments ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_assessment(r) for r in rows]


def get_assessments_by_vendor(vendor_name: str, user_id: str = "") -> list[dict]:
    """Return every assessment recorded for a vendor, oldest first.

    Used by the vendor trend view to chart score improvement over time.
    Filtered by user_id when provided (production mode).
    """
    with _connect() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE vendor_name = ? AND user_id = ? "
                "ORDER BY created_at ASC",
                (vendor_name, user_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE vendor_name = ? "
                "ORDER BY created_at ASC",
                (vendor_name,),
            ).fetchall()
    return [_row_to_assessment(r) for r in rows]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


# Field names from the input dict that map to dedicated SQL columns.
# Everything else is serialized into the `extra` column.
_DOCUMENT_COLUMNS = {
    "id", "assessment_id", "file_name", "source_type",
    "chunks_created", "created_at",
}


def _row_to_document(row: sqlite3.Row | None) -> dict | None:
    """Inflate a DB row back to the dict shape callers expect.

    The output keys match what callers in routers/ already use
    (file_name, source_type, chunks_created — not filename/file_type/chunk_count).
    """
    if row is None:
        return None
    record: dict = {
        "id": row["id"],
        "assessment_id": row["assessment_id"] or "",
        "file_name": row["filename"] or "",
        "source_type": row["file_type"] or "",
        "chunks_created": row["chunk_count"] if row["chunk_count"] is not None else 0,
        "created_at": row["uploaded_at"] or "",
    }
    if row["extra"]:
        try:
            for k, v in json.loads(row["extra"]).items():
                if k not in record:
                    record[k] = v
        except json.JSONDecodeError:
            logger.warning(f"Corrupt extra JSON for document {row['id']}")
    return record


def save_document_meta(document_id: str, data: dict) -> dict:
    """Insert or replace a document metadata row.

    Returns the saved record (same shape as get_document_meta).
    """
    record = {**data, "id": document_id}
    record.setdefault("created_at", _now_iso())
    record["updated_at"] = _now_iso()

    extra = {k: v for k, v in record.items() if k not in _DOCUMENT_COLUMNS}

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO documents
                (id, assessment_id, filename, file_type,
                 chunk_count, uploaded_at, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                record.get("assessment_id", ""),
                record.get("file_name", ""),
                record.get("source_type", ""),
                record.get("chunks_created", 0),
                record["created_at"],
                json.dumps(extra, default=str),
            ),
        )

    logger.info(f"Saved document metadata {document_id}")
    return record


def get_document_meta(document_id: str) -> dict | None:
    """Load document metadata by ID.  Returns None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    return _row_to_document(row)


def delete_document_meta(document_id: str) -> bool:
    """Delete a document metadata row.  Returns True if a row was removed."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,),
        )
        deleted = cursor.rowcount > 0
    if deleted:
        logger.info(f"Deleted document metadata {document_id}")
    return deleted


def list_documents(assessment_id: str | None = None) -> list[dict]:
    """Return document records, optionally filtered by assessment_id.

    Sorted by uploaded_at descending (newest first).
    """
    with _connect() as conn:
        if assessment_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE assessment_id = ? "
                "ORDER BY uploaded_at DESC",
                (assessment_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY uploaded_at DESC"
            ).fetchall()
    return [_row_to_document(r) for r in rows]


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------


def save_chat_message(
    assessment_id: str,
    role: str,
    content: str,
    citations: list | None = None,
) -> dict:
    """Append a chat message to an assessment's chat history.

    Args:
        assessment_id: Which assessment this conversation belongs to.
        role: "user" or "assistant".
        content: The message text.
        citations: Optional list of citation dicts to persist alongside the message.

    Returns:
        The message dict that was appended (role, content, timestamp).
    """
    timestamp = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages
                (id, assessment_id, role, content, citations, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, assessment_id, role, content,
             json.dumps(citations or [], default=str), timestamp),
        )

    return {
        "role": role,
        "content": content,
        "timestamp": timestamp,
    }


def get_chat_history(assessment_id: str) -> list[dict]:
    """Return the full chat history for an assessment, oldest first.

    Returns an empty list if no messages exist.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, citations, created_at
            FROM chat_messages
            WHERE assessment_id = ?
            ORDER BY created_at ASC
            """,
            (assessment_id,),
        ).fetchall()

    history: list[dict] = []
    for row in rows:
        msg = {
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["created_at"],
        }
        if row["citations"] and row["citations"] != "[]":
            try:
                msg["citations"] = json.loads(row["citations"])
            except json.JSONDecodeError:
                pass
        history.append(msg)
    return history


# ---------------------------------------------------------------------------
# One-time JSON → SQLite migration
# ---------------------------------------------------------------------------


def migrate_legacy_json() -> None:
    """Import legacy JSON files (written by the old file-based store) into SQLite.

    Scans data/assessments/*.json and data/documents/*.json.  Each file that
    is successfully imported is renamed to *.migrated so this is idempotent —
    safe to call on every startup, only acts when unprocessed files exist.

    Called once from main.py lifespan after init_db().
    """
    settings = get_settings()
    base = Path(__file__).resolve().parent.parent  # backend/
    data_root = base / settings.data_dir

    assessments_dir = data_root / "assessments"
    documents_dir = data_root / "documents"

    assessment_count = 0
    document_count = 0

    # ── Assessments ──────────────────────────────────────────────────────────
    if assessments_dir.exists():
        for json_file in sorted(assessments_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                assessment_id = data.get("id") or json_file.stem
                # save_assessment uses INSERT OR REPLACE — safe to run even if
                # the record already exists in SQLite.
                save_assessment(assessment_id, data)
                json_file.rename(json_file.with_suffix(".migrated"))
                assessment_count += 1
                logger.info(f"Migrated assessment: {assessment_id}")
            except Exception as e:
                logger.warning(f"Could not migrate {json_file.name}: {e}")

    # ── Document metadata ─────────────────────────────────────────────────────
    if documents_dir.exists():
        for json_file in sorted(documents_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                document_id = data.get("id") or json_file.stem
                save_document_meta(document_id, data)
                json_file.rename(json_file.with_suffix(".migrated"))
                document_count += 1
                logger.info(f"Migrated document metadata: {document_id}")
            except Exception as e:
                logger.warning(f"Could not migrate {json_file.name}: {e}")

    if assessment_count or document_count:
        logger.info(
            f"Legacy JSON migration complete: "
            f"{assessment_count} assessment(s), {document_count} document(s) imported."
        )


# ---------------------------------------------------------------------------
# Eval-run history (populated by evals/run_evals.py; per-call LLM telemetry
# lives in Langfuse — see services/tracing.py)
# ---------------------------------------------------------------------------


def record_eval_run(run: dict) -> dict:
    """Persist one eval-suite run (from the CLI gate or the API trigger)."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO eval_runs
                (ts, agreed, total, agreement, threshold, passed, duration_s, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.get("ts") or _now_iso(),
                run.get("agreed", 0), run.get("total", 0),
                run.get("agreement", 0), run.get("threshold", 80),
                1 if run.get("passed") else 0, run.get("duration_s", 0.0),
                json.dumps(run.get("detail") or {}),
            ),
        )
    return run
