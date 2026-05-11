"""Layer 3: Assessment Progress Tracking — in-memory state for SSE streaming.

IMPORTS FROM: nothing
IMPORTED BY:  chains/assessment_graph.py, routers/assessments.py
"""

import asyncio
import json

_progress: dict[str, dict] = {}


def set_progress(assessment_id: str, step: str, message: str, percent: int) -> None:
    _progress[assessment_id] = {
        "step": step,
        "message": message,
        "percent": percent,
    }


def get_progress(assessment_id: str) -> dict:
    return _progress.get(
        assessment_id,
        {"step": "idle", "message": "", "percent": 0},
    )


def clear_progress(assessment_id: str) -> None:
    _progress.pop(assessment_id, None)


async def stream_progress(assessment_id: str):
    """Async generator yielding SSE text events until the assessment completes.

    Polls every 0.5 s and yields only on state change.
    Terminates when step is 'complete' or 'error', percent >= 100, or after
    10 minutes with no progress change (idle timeout).
    """
    last_sent: dict | None = None
    idle_ticks = 0
    max_idle_ticks = 1200  # 600 s idle ÷ 0.5 s per tick

    while idle_ticks < max_idle_ticks:
        current = get_progress(assessment_id)

        if current != last_sent:
            last_sent = dict(current)
            idle_ticks = 0
            yield f"data: {json.dumps(current)}\n\n"
            step = current.get("step", "")
            if current.get("percent", 0) >= 100 or step in ("complete", "error"):
                break
        else:
            idle_ticks += 1

        await asyncio.sleep(0.5)
