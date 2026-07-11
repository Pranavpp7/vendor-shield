"""Auth tiers (dev-open / API-key) and DEMO_MODE read-only guard."""

import pytest

from config import get_settings


@pytest.fixture
def api_key_mode(monkeypatch):
    """Enable API-key auth for the duration of one test."""
    monkeypatch.setenv("API_KEY", "test-secret-key")
    get_settings.cache_clear()
    yield "test-secret-key"
    get_settings.cache_clear()


@pytest.fixture
def demo_mode(monkeypatch):
    """Enable read-only demo mode for the duration of one test.

    Also blanks API_KEY so a developer's .env value can't leak the
    key-auth tier into these tests (pydantic reads .env at construction).
    """
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestApiKeyTier:
    def test_requests_rejected_without_key(self, client, api_key_mode):
        assert client.get("/api/assessments").status_code == 401

    def test_requests_accepted_with_key_header(self, client, api_key_mode):
        r = client.get("/api/assessments", headers={"X-API-Key": api_key_mode})
        assert r.status_code == 200

    def test_bearer_form_also_accepted(self, client, api_key_mode):
        r = client.get("/api/assessments",
                       headers={"Authorization": f"Bearer {api_key_mode}"})
        assert r.status_code == 200

    def test_wrong_key_rejected(self, client, api_key_mode):
        r = client.get("/api/assessments", headers={"X-API-Key": "nope"})
        assert r.status_code == 401

    def test_mcp_endpoint_guarded(self, client, api_key_mode):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        assert client.post("/mcp", json=body).status_code == 401
        r = client.post("/mcp", json=body, headers={"X-API-Key": api_key_mode})
        assert r.status_code == 200

    def test_health_stays_open(self, client, api_key_mode):
        assert client.get("/api/health").status_code == 200


class TestDemoMode:
    def test_reads_allowed(self, client, demo_mode):
        assert client.get("/api/assessments").status_code == 200
        assert client.get("/api/frameworks").status_code == 200

    def test_mutations_blocked_with_friendly_message(self, client, demo_mode):
        r = client.post("/api/assessments/run",
                        json={"vendor_name": "X", "assessment_id": "x"})
        assert r.status_code == 403
        assert "read-only demo" in r.json()["detail"]
        assert client.delete("/api/assessments/anything").status_code == 403
        assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                                         "method": "tools/list"}).status_code == 403

    def test_exports_still_work(self, client, demo_mode):
        # GET-based exports are part of the read-only demo experience
        from tests.test_api import seed_assessment
        seed_assessment("demo-ro", {"GR-001": "PASS"})
        assert client.get("/api/assessments/demo-ro/export.csv").status_code == 200
        assert client.get("/api/assessments/demo-ro/report.pdf").status_code == 200
