from datetime import datetime

import httpx
from pydantic import AwareDatetime, BaseModel, Field, StrictInt, ValidationError

from workforcesync.database import ENTITIES


class SourceProtocolError(RuntimeError):
    """The source response cannot safely support incremental progress."""


class Snapshot(BaseModel):
    snapshot_id: int = Field(ge=0, strict=True)
    watermark_end: AwareDatetime


class SourceRecord(BaseModel):
    source_record_id: str = Field(min_length=1)
    payload: dict


class Page(BaseModel):
    items: list[SourceRecord]
    snapshot_id: StrictInt
    next_offset: StrictInt | None


def get_snapshot(client: httpx.Client) -> Snapshot:
    response = client.get("/api/v1/snapshot")
    response.raise_for_status()
    try:
        return Snapshot.model_validate(response.json())
    except (ValueError, ValidationError) as error:
        raise SourceProtocolError("Invalid snapshot response") from error


def extract(
    client: httpx.Client,
    entity: str,
    snapshot: Snapshot,
    watermark: datetime | None,
    page_size: int,
) -> list[dict]:
    if entity not in ENTITIES:
        raise ValueError("Unknown entity")
    offset = 0
    records, seen = [], set()
    while True:
        params = {"snapshot_id": snapshot.snapshot_id, "offset": offset, "limit": page_size}
        if watermark is not None:
            params["updated_since"] = watermark.isoformat()
        response = client.get(f"/api/v1/{entity}s", params=params)
        response.raise_for_status()
        try:
            page = Page.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise SourceProtocolError("Invalid page response") from error
        if page.snapshot_id != snapshot.snapshot_id or len(page.items) > page_size:
            raise SourceProtocolError("Inconsistent page boundary")
        for item in page.items:
            if item.source_record_id in seen:
                raise SourceProtocolError("Repeated source record across pages")
            seen.add(item.source_record_id)
            records.append(item.model_dump())
        if page.next_offset is None:
            return records
        if not page.items or page.next_offset != offset + len(page.items):
            raise SourceProtocolError("Pagination did not advance correctly")
        offset = page.next_offset
