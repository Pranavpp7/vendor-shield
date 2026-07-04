"""
Layer 3: LLM usage metering — tokens and call counts per assessment run.

RESPONSIBILITY:
    An in-memory accumulator keyed by assessment_id.  The evaluation
    service records token usage after every LLM call; the assessment
    graph pops the totals when a run finishes and stamps them (plus
    duration and an estimated cost) onto the assessment record as
    `run_metrics`.

    Costs are estimates: token prices are configured in config.py
    (llm_price_in_per_m / llm_price_out_per_m, USD per million tokens)
    and should track the OpenRouter pricing of the configured model.

IMPORTS FROM: nothing
IMPORTED BY:  services/evaluation.py, chains/assessment_graph.py
"""

_usage: dict[str, dict] = {}


def record_usage(assessment_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Add one LLM call's token counts to an assessment's running total."""
    entry = _usage.setdefault(
        assessment_id,
        {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0},
    )
    entry["llm_calls"] += 1
    entry["prompt_tokens"] += max(0, prompt_tokens)
    entry["completion_tokens"] += max(0, completion_tokens)


def pop_usage(assessment_id: str) -> dict:
    """Return and clear the accumulated totals for a finished run."""
    return _usage.pop(
        assessment_id,
        {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0},
    )
