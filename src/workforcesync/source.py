"""Deterministic fixtures written as immutable source versions."""

from psycopg.types.json import Jsonb

from workforcesync.config import Settings
from workforcesync.database import SOURCE_LOCK, connect


def append_changes(db, changes: list[tuple[str, str, dict]]) -> None:
    db.execute("SELECT pg_advisory_xact_lock(%s)", (SOURCE_LOCK,))
    timestamp = db.execute("SELECT clock_timestamp() AS ts").fetchone()["ts"]
    values = []
    for entity, source_id, payload in changes:
        payload = {**payload, "updated_at": timestamp.isoformat()}
        values.append((entity, source_id, timestamp, Jsonb(payload)))
    with db.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO source.change
            (entity_name, source_record_id, updated_at, payload) VALUES (%s,%s,%s,%s)""",
            values,
        )


def person(key: str, **overrides) -> dict:
    return {
        "person_id": key,
        "first_name": "  Ada ",
        "last_name": "Lovelace  ",
        "email": f" {key.upper()}@EXAMPLE.TEST ",
        "status": " Active ",
        "is_deleted": False,
        **overrides,
    }


def employment(key: str, person_id: str, **overrides) -> dict:
    return {
        "employment_id": key,
        "person_id": person_id,
        "classification_id": "C1",
        "employment_type": "FULL_TIME",
        "status": "active",
        "start_date": "2025-01-15",
        "end_date": "N/A",
        "is_deleted": False,
        **overrides,
    }


def initial_changes() -> list[tuple[str, str, dict]]:
    return [
        (
            "classification",
            "C1",
            {
                "classification_id": "C1",
                "name": "Engineer",
                "department": "Technology",
                "is_deleted": False,
            },
        ),
        (
            "classification",
            "C2",
            {
                "classification_id": "C2",
                "name": "Analyst",
                "department": "Operations",
                "is_deleted": False,
            },
        ),
        ("person", "P1", person("P1")),
        ("person", "P2", person("P2")),
        ("person", "P3", person("P3", email="not-an-email")),
        ("person", "P4", person("P4", first_name=" ")),
        ("person", "P2-duplicate", person("P2")),
        ("employment", "E1", employment("E1", "P1")),
        ("employment", "E2", employment("E2", "P2")),
        ("employment", "E3", employment("E3", "missing")),
        ("employment", "E4", employment("E4", "P1", classification_id="missing")),
        ("employment", "E5", employment("E5", "P1", end_date="2024-01-01")),
    ]


def seed(config: Settings, scenario: str = "initial") -> bool:
    with connect(config) as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (SOURCE_LOCK,))
        if db.execute("SELECT 1 FROM source.scenario WHERE name=%s", (scenario,)).fetchone():
            return False
        if scenario == "initial":
            changes = initial_changes()
        elif scenario == "incremental":
            if not db.execute("SELECT 1 FROM source.scenario WHERE name='initial'").fetchone():
                raise ValueError("Seed initial data first")
            changes = [
                ("person", "P1", person("P1", last_name="Byron")),
                ("person", "P5", person("P5", first_name="Grace", last_name="Hopper")),
                ("employment", "E1", employment("E1", "P1", classification_id="C2")),
                ("employment", "E2", employment("E2", "P2", is_deleted=True)),
                ("employment", "E6", employment("E6", "P5")),
            ]
        else:
            raise ValueError("Unknown seed scenario")
        append_changes(db, changes)
        db.execute("INSERT INTO source.scenario(name) VALUES (%s)", (scenario,))
    return True
