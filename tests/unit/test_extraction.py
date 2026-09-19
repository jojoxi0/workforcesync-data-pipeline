import httpx
import pytest

from workforcesync.extraction import Snapshot, SourceProtocolError, extract, get_snapshot


def test_pagination_and_incremental_parameter(timestamp):
    calls = []

    def respond(request):
        calls.append(request)
        offset = int(request.url.params["offset"])
        return httpx.Response(
            200,
            json={
                "snapshot_id": 3,
                "items": [{"source_record_id": str(offset), "payload": {"person_id": str(offset)}}],
                "next_offset": 1 if offset == 0 else None,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://source") as client:
        rows = extract(
            client, "person", Snapshot(snapshot_id=3, watermark_end=timestamp), timestamp, 1
        )
    assert len(rows) == 2
    assert calls[0].url.params["updated_since"] == timestamp.isoformat()
    assert calls[1].url.params["offset"] == "1"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"snapshot_id": 2, "items": [], "next_offset": 0},
        {"snapshot_id": 3, "items": [], "next_offset": 0},
    ],
)
def test_invalid_pages_fail(timestamp, body):
    with httpx.Client(
        base_url="http://source",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
    ) as client:
        with pytest.raises(SourceProtocolError):
            extract(client, "person", Snapshot(snapshot_id=3, watermark_end=timestamp), None, 2)


def test_api_unavailable():
    with httpx.Client(
        base_url="http://source", transport=httpx.MockTransport(lambda _: httpx.Response(503))
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            get_snapshot(client)
