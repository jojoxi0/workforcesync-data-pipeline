from datetime import timedelta

import pytest

from workforcesync.quality import validate_row
from workforcesync.source import employment, person
from workforcesync.transformation import normalize


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("email", "invalid", "INVALID_EMAIL"),
        ("first_name", " ", "MISSING_REQUIRED_FIELD"),
        ("person_id", "N/A", "MISSING_REQUIRED_FIELD"),
        ("status", "unknown", "INVALID_STATUS"),
    ],
)
def test_person_rules(timestamp, field, value, code):
    row = normalize("person", {**person("P1"), "updated_at": timestamp.isoformat(), field: value})
    assert validate_row("person", row, timestamp, {})[0] == code


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"person_id": "missing"}, "REFERENTIAL_INTEGRITY_FAILURE"),
        ({"classification_id": "missing"}, "UNKNOWN_CLASSIFICATION"),
        ({"end_date": "2024-01-01"}, "INVALID_DATE_RANGE"),
        ({"employment_type": "volunteer"}, "INVALID_EMPLOYMENT_TYPE"),
    ],
)
def test_employment_rules(timestamp, overrides, code):
    payload = {**employment("E1", "P1"), "updated_at": timestamp.isoformat(), **overrides}
    row = normalize("employment", payload)
    assert (
        validate_row("employment", row, timestamp, {"person": {"P1"}, "classification": {"C1"}})[0]
        == code
    )


def test_valid_employment_and_future_timestamp(timestamp):
    row = normalize("employment", {**employment("E1", "P1"), "updated_at": timestamp.isoformat()})
    refs = {"person": {"P1"}, "classification": {"C1"}}
    assert row["end_date"] is None
    assert validate_row("employment", row, timestamp, refs) is None
    row["updated_at"] += timedelta(days=1)
    assert validate_row("employment", row, timestamp, refs)[0] == "INVALID_TIMESTAMP"
