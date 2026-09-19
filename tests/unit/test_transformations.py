import pytest

from workforcesync.source import person
from workforcesync.transformation import deduplicate, normalize, transform


def test_normalization(timestamp):
    row = normalize("person", {**person("P1"), "updated_at": timestamp.isoformat()})
    assert row["email"] == "p1@example.test"
    assert row["first_name"] == "Ada"
    assert row["status"] == "active"
    assert row["updated_at"] == timestamp


@pytest.mark.parametrize(
    "field,value",
    [
        ("updated_at", "bad"),
        ("updated_at", "2026-01-01"),
        ("is_deleted", "nope"),
        ("first_name", 10),
    ],
)
def test_bad_types_are_rejected(timestamp, field, value):
    valid, rejected = transform(
        "person",
        [
            {
                "source_record_id": "P1",
                "payload": {**person("P1"), "updated_at": timestamp.isoformat(), field: value},
            }
        ],
    )
    assert not valid
    assert rejected[0]["error_code"] == "INVALID_TYPE_OR_DATE"
    assert rejected[0]["payload"][field] == value


def test_duplicate_winner_deterministic(timestamp):
    records = [
        {"source_record_id": key, "payload": {**person("P1"), "updated_at": timestamp.isoformat()}}
        for key in ["b", "a"]
    ]
    normalized, _ = transform("person", records)
    valid, rejected = deduplicate("person", normalized)
    assert [r["source_record_id"] for r in valid] == ["b"]
    assert rejected[0]["error_code"] == "DUPLICATE_KEY"


def test_valid_boolean_strings(timestamp):
    row = normalize(
        "person", {**person("P1"), "updated_at": timestamp.isoformat(), "is_deleted": " true "}
    )
    assert row["is_deleted"] is True
