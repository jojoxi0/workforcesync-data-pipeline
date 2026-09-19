import re
from datetime import datetime

from workforcesync.transformation import FIELDS

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
STATUSES = {"person": {"active", "inactive"}, "employment": {"active", "ended", "leave"}}
TYPES = {"full_time", "part_time", "contract"}


class QualityThresholdError(RuntimeError):
    """Row-level rejections exceeded the configured tolerance."""


def validate_row(
    entity: str, row: dict, upper: datetime, references: dict[str, set[str]]
) -> tuple[str, str] | None:
    required = set(FIELDS[entity]) - {"end_date"}
    if any(row[field] is None for field in required):
        return "MISSING_REQUIRED_FIELD", "A required field is missing or blank"
    if row["updated_at"] > upper:
        return "INVALID_TIMESTAMP", "updated_at is beyond the extraction boundary"
    if entity in STATUSES and row["status"] not in STATUSES[entity]:
        return "INVALID_STATUS", "Unrecognized status"
    if entity == "person" and not EMAIL.fullmatch(row["email"]):
        return "INVALID_EMAIL", "Email must contain a local part and dotted domain"
    if entity == "employment":
        if row["employment_type"] not in TYPES:
            return "INVALID_EMPLOYMENT_TYPE", "Unrecognized employment type"
        if row["end_date"] is not None and row["end_date"] < row["start_date"]:
            return "INVALID_DATE_RANGE", "end_date precedes start_date"
        if row["person_id"] not in references["person"]:
            return "REFERENTIAL_INTEGRITY_FAILURE", "Person does not exist in the warehouse"
        if row["classification_id"] not in references["classification"]:
            return "UNKNOWN_CLASSIFICATION", "Classification does not exist in the warehouse"
    return None


def validate(
    entity: str, records: list[dict], upper: datetime, references: dict[str, set[str]]
) -> tuple[list[dict], list[dict]]:
    valid, rejected = [], []
    for record in records:
        issue = validate_row(entity, record["row"], upper, references)
        if issue:
            rejected.append({**record, "error_code": issue[0], "error_message": issue[1]})
        else:
            valid.append(record)
    return valid, rejected
