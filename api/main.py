from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query

from workforcesync.config import Settings
from workforcesync.database import ENTITIES, SOURCE_LOCK, connect

app = FastAPI(title="Workforce source", version="1.0.0")


def settings() -> Settings:
    return Settings()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/snapshot")
def snapshot(config: Annotated[Settings, Depends(settings)]):
    with connect(config) as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (SOURCE_LOCK,))
        return db.execute("""SELECT coalesce(max(change_id), 0) AS snapshot_id,
            clock_timestamp() AS watermark_end FROM source.change""").fetchone()


def page(
    entity: str,
    config: Settings,
    snapshot_id: int,
    updated_since: datetime | None,
    offset: int,
    limit: int,
):
    if updated_since is not None and updated_since.tzinfo is None:
        raise HTTPException(422, "updated_since must include a timezone")
    with connect(config) as db:
        records = db.execute(
            """WITH latest AS (
            SELECT DISTINCT ON (source_record_id) source_record_id, payload, updated_at
            FROM source.change WHERE entity_name = %s AND change_id <= %s
            ORDER BY source_record_id, change_id DESC)
            SELECT source_record_id, payload FROM latest
            WHERE (%s::timestamptz IS NULL OR updated_at >= %s)
            ORDER BY source_record_id LIMIT %s OFFSET %s""",
            (entity, snapshot_id, updated_since, updated_since, limit + 1, offset),
        ).fetchall()
    return {
        "items": records[:limit],
        "snapshot_id": snapshot_id,
        "next_offset": offset + limit if len(records) > limit else None,
    }


def endpoint(entity: str):
    def get_records(
        config: Annotated[Settings, Depends(settings)],
        snapshot_id: Annotated[int, Query(ge=0)],
        updated_since: datetime | None = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ):
        return page(entity, config, snapshot_id, updated_since, offset, limit)

    return get_records


for entity in ENTITIES:
    app.get(f"/api/v1/{entity}s", name=f"list_{entity}s")(endpoint(entity))
