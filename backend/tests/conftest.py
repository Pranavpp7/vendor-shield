"""Shared fixtures: isolate SQLite and custom-framework storage per test.

Every test runs against a throwaway database file and a throwaway
custom-frameworks directory, so the suite never touches dev data and
needs no Qdrant, no LLM key, and no network.
"""

import os

# Unit tests must never emit Langfuse traces, even when the developer's
# .env has real keys: real env vars beat .env in pydantic-settings, so
# blanking them here (before any get_settings() call) forces the tracing
# shim into its no-op path for the whole suite.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

import pytest

import models.controls as controls_mod
import storage.local_store as store_mod


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point local_store at a fresh SQLite file and initialize the schema."""
    db_file = tmp_path / "test-vendorshield.db"
    monkeypatch.setattr(store_mod, "_db_path", lambda: db_file)
    store_mod.init_db()
    return db_file


@pytest.fixture
def tmp_custom_frameworks(tmp_path, monkeypatch):
    """Point the framework loader's custom dir at a fresh temp folder."""
    custom_dir = tmp_path / "frameworks"
    custom_dir.mkdir()
    monkeypatch.setattr(controls_mod, "custom_frameworks_dir", lambda: custom_dir)
    controls_mod._load_frameworks.cache_clear()
    yield custom_dir
    controls_mod._load_frameworks.cache_clear()


@pytest.fixture
def client(tmp_db, tmp_custom_frameworks):
    """TestClient wired to the isolated storage fixtures."""
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


# ── Shared test data ─────────────────────────────────────────────────────────


def make_control_result(control_id: str, score: str, **extra) -> dict:
    """A minimal stored control_result dict as the pipeline produces it."""
    return {
        "control_id": control_id,
        "score": score,
        "confidence": extra.pop("confidence", 0.9),
        "reasoning": "test",
        "domain": extra.pop("domain", "Governance & Risk"),
        "title": f"Control {control_id}",
        "citations": [],
        **extra,
    }


VALID_CONTROL_DEF = {
    "id": "TQ-001",
    "ref": "Q1.2",
    "domain": "Access Control",
    "title": "MFA required for remote access",
    "description": (
        "All remote access to production systems requires multi-factor "
        "authentication with no exceptions for any user role."
    ),
    "search_query": "multi-factor authentication MFA remote access VPN two-factor",
    "what_to_look_for": (
        "Mentions of MFA, 2FA, authenticator apps, or hardware tokens applied "
        "to remote or VPN access paths."
    ),
    "what_good_looks_like": (
        "MFA enforced for every remote access path including VPN and admin "
        "consoles, using phishing-resistant factors."
    ),
    "scoring_guide": {
        "pass": "MFA clearly required for all remote access",
        "partial": "MFA mentioned but scope or enforcement unclear",
        "fail": "Remote access allowed with password only",
        "no_evidence": "No mention of remote access authentication",
    },
}


VALID_FRAMEWORK_DEF = {
    "id": "test-questionnaire",
    "name": "Test Internal Questionnaire",
    "description": "Framework used by the test suite",
    "version": "2026",
    "controls": [VALID_CONTROL_DEF],
}
