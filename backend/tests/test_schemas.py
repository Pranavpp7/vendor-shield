"""FrameworkDefinition validation — the quality gate for extracted frameworks."""

import pytest
from pydantic import ValidationError

from models.schemas import FrameworkDefinition
from tests.conftest import VALID_CONTROL_DEF, VALID_FRAMEWORK_DEF


def test_valid_framework_passes():
    fw = FrameworkDefinition(**VALID_FRAMEWORK_DEF)
    assert fw.id == "test-questionnaire"
    assert fw.controls[0].scoring_guide.pass_.startswith("MFA")


def test_serializes_with_pass_key():
    # "pass" is a Python keyword — the alias must round-trip in JSON output
    fw = FrameworkDefinition(**VALID_FRAMEWORK_DEF)
    dumped = fw.model_dump(by_alias=True)
    assert "pass" in dumped["controls"][0]["scoring_guide"]


@pytest.mark.parametrize("field,value", [
    ("search_query", ""),               # empty retrieval query
    ("description", "too short"),       # under min length
    ("what_to_look_for", ""),
    ("id", "has spaces in it!"),        # bad control id format
])
def test_weak_control_fields_rejected(field, value):
    bad = {**VALID_FRAMEWORK_DEF, "controls": [{**VALID_CONTROL_DEF, field: value}]}
    with pytest.raises(ValidationError):
        FrameworkDefinition(**bad)


def test_empty_scoring_guide_entry_rejected():
    bad_control = {
        **VALID_CONTROL_DEF,
        "scoring_guide": {**VALID_CONTROL_DEF["scoring_guide"], "fail": ""},
    }
    with pytest.raises(ValidationError):
        FrameworkDefinition(**{**VALID_FRAMEWORK_DEF, "controls": [bad_control]})


@pytest.mark.parametrize("fw_id", ["Has Spaces", "UPPER-CASE", "-leading-hyphen", "x"])
def test_bad_framework_ids_rejected(fw_id):
    with pytest.raises(ValidationError):
        FrameworkDefinition(**{**VALID_FRAMEWORK_DEF, "id": fw_id})


def test_zero_controls_rejected():
    with pytest.raises(ValidationError):
        FrameworkDefinition(**{**VALID_FRAMEWORK_DEF, "controls": []})
