"""Small normalization functions; business validation lives in quality.py."""

from datetime import date, datetime

import pandas as pd

SENTINELS = {"", "n/a", "null", "none"}
FIELDS = {
    "person": ("person_id", "first_name", "last_name", "email", "status"),
    "classification": ("classification_id", "name", "department"),
    "employment": (
        "employment_id",
        "person_id",
        "classification_id",
        "employment_type",
        "status",
        "start_date",
        "end_date",
    ),
}


def clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Expected text")
    value = value.strip()
    return None if value.lower() in SENTINELS else value


def parse_boolean(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError("is_deleted must be a boolean")


def parse_timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("updated_at must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("updated_at requires a timezone")
    return parsed


def normalize(entity: str, payload: dict) -> dict:
    row = {field: clean_text(payload.get(field)) for field in FIELDS[entity]}
    row["updated_at"] = parse_timestamp(payload.get("updated_at"))
    row["is_deleted"] = parse_boolean(payload.get("is_deleted", False))
    for field in ("status", "employment_type", "email"):
        if row.get(field):
            row[field] = row[field].lower()
    if entity == "employment":
        for field in ("start_date", "end_date"):
            row[field] = date.fromisoformat(row[field]) if row[field] else None
    return row


def transform(entity: str, records: list[dict]) -> tuple[list[dict], list[dict]]:
    normalized, rejected = [], []
    for record in records:
        try:
            normalized.append({"row": normalize(entity, record["payload"]), **record})
        except (TypeError, ValueError):
            rejected.append(
                {
                    **record,
                    "error_code": "INVALID_TYPE_OR_DATE",
                    "error_message": "Invalid text, boolean, date or timestamp type",
                }
            )
    return normalized, rejected


def deduplicate(entity: str, records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Latest timestamp wins; stable source identifier breaks ties deterministically."""
    if not records:
        return [], []
    frame = pd.DataFrame(
        [
            {
                "key": r["row"][f"{entity}_id"],
                "updated_at": r["row"]["updated_at"],
                "source_id": r["source_record_id"],
                "position": i,
            }
            for i, r in enumerate(records)
        ]
    )
    frame = frame.sort_values(["updated_at", "source_id"], kind="stable")
    duplicates = frame.duplicated("key", keep="last") & frame["key"].notna()
    rejected = [
        {
            **records[i],
            "error_code": "DUPLICATE_KEY",
            "error_message": "Superseded duplicate business key in this interval",
        }
        for i in frame.loc[duplicates, "position"]
    ]
    valid = [records[i] for i in frame.loc[~duplicates, "position"]]
    return valid, rejected
