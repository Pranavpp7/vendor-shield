"""
Layer 3: Assessment Progress Tracking — in-memory state for SSE streaming.

RESPONSIBILITY:
    Provides a lightweight in-memory store for assessment run progress.
    Graph nodes call set_progress() as they complete; the SSE endpoint
    in routers/assessments.py streams these updates to the frontend.

    Thread-safe for single-process use — Python's GIL protects dict
    reads and writes.  Progress entries are cleared after streaming ends.

IMPORTS FROM: nothing
IMPORTED BY:  chains/assessment_graph.py, routers/assessments.py
"""

import asyncio
import json

_progress: dict[str, dict] = {}


def set_progress(assessment_id: str, stage: str, message: str, percent: int) -> None:
    """Update progress for an in-flight assessment.

    Called by graph nodes (sync-safe — just updates a dict).
    """
    _progress[assessment_id] = {
        "stage": stage,
        "message": message,
        "percent": percent,
    }


def get_progress(assessment_id: str) -> dict:
    """Return current progress, or idle sentinel if not tracked."""
    return _progress.get(
        assessment_id,
        {"stage": "idle", "message": "", "percent": 0},
    )


def clear_progress(assessment_id: str) -> None:
    """Remove a finished assessment's progress entry."""
    _progress.pop(assessment_id, None)


async def stream_progress(assessment_id: str):
    """Async generator yielding SSE text events until assessment completes.

    Polls every 0.5 s and yields only on state change.
    Terminates when percent reaches 100 or after a 5-minute timeout.
    """
    last_sent: dict | None = None
    idle_ticks = 0

    while True:
        current = get_progress(assessment_id)

        if current != last_sent:
            last_sent = dict(current)
            idle_ticks = 0
            yield f"data: {json.dumps(current)}\n\n"
            if current.get("percent", 0) >= 100:
                break
        else:
            idle_ticks += 1
            if idle_ticks > 600:  # 5 min × 2 ticks/s
                break

        await asyncio.sleep(0.5)
