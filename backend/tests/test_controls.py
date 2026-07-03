"""Framework loader, custom framework persistence, and score calculation."""

import json

import pytest

from models.controls import (
    DEFAULT_FRAMEWORK_ID,
    calculate_scores,
    delete_custom_framework,
    effective_score,
    get_all_controls,
    get_domains,
    get_framework,
    is_builtin_framework,
    list_frameworks,
    resolve_framework_id,
    save_custom_framework,
    _load_frameworks,
)
from tests.conftest import VALID_FRAMEWORK_DEF


class TestLoader:
    def test_builtin_frameworks_load(self):
        ids = {f["id"] for f in list_frameworks()}
        assert {"nist-800-53", "soc2-tsc"} <= ids

    def test_nist_has_20_controls_4_domains(self):
        assert len(get_all_controls("nist-800-53")) == 20
        assert len(get_domains("nist-800-53")) == 4

    def test_soc2_has_10_controls(self):
        assert len(get_all_controls("soc2-tsc")) == 10

    def test_default_framework_is_nist(self):
        assert resolve_framework_id(None) == DEFAULT_FRAMEWORK_ID
        assert resolve_framework_id("") == DEFAULT_FRAMEWORK_ID
        assert get_all_controls() == get_all_controls("nist-800-53")

    def test_unknown_framework_raises(self):
        with pytest.raises(KeyError):
            resolve_framework_id("does-not-exist")

    def test_controls_have_nist_ref_alias(self):
        # Backward compat: every control exposes both "ref" and "nist_ref"
        for control in get_all_controls("soc2-tsc"):
            assert control["nist_ref"] == control["ref"]

    def test_every_control_has_required_fields(self):
        required = {
            "id", "domain", "title", "description", "search_query",
            "what_to_look_for", "what_good_looks_like", "scoring_guide",
        }
        for fw in list_frameworks():
            for control in get_all_controls(fw["id"]):
                missing = required - control.keys()
                assert not missing, f"{fw['id']}/{control.get('id')}: missing {missing}"


class TestCustomFrameworks:
    def test_save_and_load_roundtrip(self, tmp_custom_frameworks):
        saved = save_custom_framework(dict(VALID_FRAMEWORK_DEF))
        assert saved["custom"] is True
        assert get_framework("test-questionnaire")["name"] == "Test Internal Questionnaire"
        assert not is_builtin_framework("test-questionnaire")

    def test_cannot_shadow_builtin(self, tmp_custom_frameworks):
        with pytest.raises(ValueError):
            save_custom_framework({**VALID_FRAMEWORK_DEF, "id": "nist-800-53"})

    def test_bad_slug_rejected(self, tmp_custom_frameworks):
        with pytest.raises(ValueError):
            save_custom_framework({**VALID_FRAMEWORK_DEF, "id": "Bad Slug!"})

    def test_delete_custom(self, tmp_custom_frameworks):
        save_custom_framework(dict(VALID_FRAMEWORK_DEF))
        assert delete_custom_framework("test-questionnaire") is True
        with pytest.raises(KeyError):
            resolve_framework_id("test-questionnaire")

    def test_delete_builtin_raises(self, tmp_custom_frameworks):
        with pytest.raises(ValueError):
            delete_custom_framework("soc2-tsc")

    def test_delete_missing_returns_false(self, tmp_custom_frameworks):
        assert delete_custom_framework("never-existed") is False

    def test_malformed_custom_file_skipped(self, tmp_custom_frameworks):
        (tmp_custom_frameworks / "broken.json").write_text("{not json", encoding="utf-8")
        _load_frameworks.cache_clear()
        ids = {f["id"] for f in list_frameworks()}  # must not raise
        assert "nist-800-53" in ids


class TestEffectiveScore:
    def test_ai_score_when_no_override(self):
        assert effective_score({"score": "FAIL"}) == "FAIL"

    def test_override_wins(self):
        assert effective_score({"score": "FAIL", "analyst_score": "PASS"}) == "PASS"

    def test_cleared_override_falls_back(self):
        assert effective_score({"score": "PARTIAL", "analyst_score": None}) == "PARTIAL"


class TestCalculateScores:
    def test_all_pass_soc2(self):
        results = [
            {"control_id": c["id"], "score": "PASS"}
            for c in get_all_controls("soc2-tsc")
        ]
        scores = calculate_scores(results, "soc2-tsc")
        assert scores["overall_score"] == 100
        assert scores["risk_level"] == "Low"
        assert all(v == 100 for v in scores["domain_scores"].values())

    def test_all_fail_is_high_risk(self):
        results = [
            {"control_id": c["id"], "score": "FAIL"}
            for c in get_all_controls("soc2-tsc")
        ]
        scores = calculate_scores(results, "soc2-tsc")
        assert scores["overall_score"] == 0
        assert scores["risk_level"] == "High"

    def test_partial_counts_half(self):
        results = [
            {"control_id": c["id"], "score": "PARTIAL"}
            for c in get_all_controls("soc2-tsc")
        ]
        assert calculate_scores(results, "soc2-tsc")["overall_score"] == 50

    def test_missing_controls_count_as_zero(self):
        soc2 = get_all_controls("soc2-tsc")
        results = [{"control_id": soc2[0]["id"], "score": "PASS"}]
        assert calculate_scores(results, "soc2-tsc")["overall_score"] == 10

    def test_overrides_change_the_math(self):
        results = [
            {"control_id": c["id"], "score": "FAIL", "analyst_score": "PASS"}
            for c in get_all_controls("soc2-tsc")
        ]
        assert calculate_scores(results, "soc2-tsc")["overall_score"] == 100

    def test_risk_level_boundaries(self):
        # >= 70 Low, >= 40 Medium, else High (per calculate_scores)
        soc2_ids = [c["id"] for c in get_all_controls("soc2-tsc")]
        def score_for(n_pass):
            results = [
                {"control_id": cid, "score": "PASS" if i < n_pass else "FAIL"}
                for i, cid in enumerate(soc2_ids)
            ]
            return calculate_scores(results, "soc2-tsc")
        assert score_for(7)["risk_level"] == "Low"      # 70
        assert score_for(4)["risk_level"] == "Medium"   # 40
        assert score_for(3)["risk_level"] == "High"     # 30
