# Marks evals/ as a package so tests/ can import the pure gate helpers
# (from evals.run_evals import quote_is_faithful, ...).  The eval scripts
# themselves are still run directly: uv run python evals/run_evals.py
