from itertools import batched

from psycopg import sql
from psycopg.types.json import Jsonb

from workforcesync.database import TARGETS
from workforcesync.transformation import FIELDS


def load_raw(db, run_id, entity: str, records: list[dict]) -> None:
    with db.cursor() as cursor:
        cursor.executemany(
            sql.SQL("""INSERT INTO raw.{} (pipeline_run_id,source_record_id,payload)
            VALUES (%s,%s,%s)""").format(sql.Identifier(entity)),
            [(run_id, r["source_record_id"], Jsonb(r["payload"])) for r in records],
        )


def load_quarantine(db, run_id, entity: str, rejected: list[dict]) -> None:
    with db.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO quarantine.record
            (pipeline_run_id,entity_name,source_record_id,error_code,error_message,payload)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            [
                (
                    run_id,
                    entity,
                    r["source_record_id"],
                    r["error_code"],
                    r["error_message"],
                    Jsonb(r["payload"]),
                )
                for r in rejected
            ],
        )


def insert_batch(db, schema: str, table: str, columns: tuple, rows: list[dict], suffix=None):
    if not rows:
        return
    values = sql.SQL(",").join(
        sql.SQL("({})").format(sql.SQL(",").join(sql.Placeholder() for _ in columns)) for _ in rows
    )
    statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES {}").format(
        sql.Identifier(schema),
        sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        values,
    )
    if suffix is not None:
        statement += suffix
    db.execute(statement, [r[column] for r in rows for column in columns])


def load_staging(db, run_id, entity: str, records: list[dict], batch_size: int):
    columns = (*FIELDS[entity], "updated_at", "is_deleted", "pipeline_run_id")
    db.execute(sql.SQL("TRUNCATE staging.{}").format(sql.Identifier(entity)))
    for group in batched(records, batch_size):
        rows = [{**r["row"], "pipeline_run_id": run_id} for r in group]
        insert_batch(db, "staging", entity, columns, rows)


def upsert(db, run_id, entity: str, records: list[dict], batch_size: int) -> dict:
    target, key = TARGETS[entity], f"{entity}_id"
    columns = (*FIELDS[entity], "updated_at", "is_deleted", "pipeline_run_id")
    counts = {"rows_inserted": 0, "rows_updated": 0, "rows_deleted": 0, "rows_loaded": 0}
    for group in batched(records, batch_size):
        rows = [{**r["row"], "pipeline_run_id": run_id} for r in group]
        previous = db.execute(
            sql.SQL("SELECT * FROM analytics.{} WHERE {} = ANY(%s)").format(
                sql.Identifier(target), sql.Identifier(key)
            ),
            ([r[key] for r in rows],),
        ).fetchall()
        existing = {r[key]: r for r in previous}
        changed = []
        for row in rows:
            old = existing.get(row[key])
            if old and row["updated_at"] <= old["updated_at"]:
                continue
            changed.append(row)
            metric = (
                "rows_inserted"
                if old is None
                else (
                    "rows_deleted"
                    if row["is_deleted"] and not old["is_deleted"]
                    else "rows_updated"
                )
            )
            counts[metric] += 1
        assignments = sql.SQL(",").join(
            sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
            for c in columns
            if c != key
        )
        suffix = sql.SQL(
            " ON CONFLICT ({}) DO UPDATE SET {} WHERE EXCLUDED.updated_at > {}.updated_at"
        )
        suffix = suffix.format(sql.Identifier(key), assignments, sql.Identifier(target))
        insert_batch(db, "analytics", target, columns, changed, suffix)
        if entity == "employment":
            history = (
                "employment_id",
                "classification_id",
                "updated_at",
                "is_deleted",
                "pipeline_run_id",
            )
            insert_batch(
                db,
                "analytics",
                "employment_history",
                history,
                changed,
                sql.SQL(" ON CONFLICT DO NOTHING"),
            )
        counts["rows_loaded"] += len(changed)
    return counts
