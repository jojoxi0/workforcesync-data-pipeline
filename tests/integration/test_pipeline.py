import pytest
from fastapi.testclient import TestClient

from api.main import app, settings
from workforcesync import audit
from workforcesync.database import connect
from workforcesync.pipeline import run_pipeline
from workforcesync.source import append_changes, person, seed

pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(db_config):
    app.dependency_overrides[settings] = lambda: db_config
    yield lambda: TestClient(app)
    app.dependency_overrides.clear()


def warehouse(config):
    with connect(config) as db:
        return {
            table: db.execute(f"SELECT * FROM analytics.{table} ORDER BY 1").fetchall()
            for table in (
                "dim_person",
                "dim_classification",
                "fact_employment",
                "employment_history",
            )
        }


def test_initial_incremental_and_idempotency(db_config, api_client):
    assert seed(db_config)
    assert not seed(db_config)
    first = run_pipeline(db_config, client=api_client())
    assert first["status"] == "SUCCESS"
    assert sum(e["rows_extracted"] for e in first["entities"]) == 12
    assert sum(e["rows_loaded"] for e in first["entities"]) == 6
    assert sum(e["rows_rejected"] for e in first["entities"]) == 6
    original = warehouse(db_config)
    second = run_pipeline(db_config, client=api_client())
    assert sum(e["rows_extracted"] for e in second["entities"]) == 0
    assert warehouse(db_config) == original
    replay = run_pipeline(db_config, full=True, client=api_client())
    assert sum(e["rows_loaded"] for e in replay["entities"]) == 0
    assert warehouse(db_config) == original
    assert seed(db_config, "incremental")
    changed = run_pipeline(db_config, client=api_client())
    assert sum(e["rows_extracted"] for e in changed["entities"]) == 5
    assert sum(e["rows_inserted"] for e in changed["entities"]) == 2
    assert sum(e["rows_updated"] for e in changed["entities"]) == 2
    assert sum(e["rows_deleted"] for e in changed["entities"]) == 1
    target = warehouse(db_config)
    assert target["dim_person"][0]["last_name"] == "Byron"
    assert target["fact_employment"][1]["is_deleted"] is True
    assert len(target["employment_history"]) == 5
    run_pipeline(db_config, client=api_client())
    assert warehouse(db_config) == target
    with connect(db_config) as db:
        assert len(audit.watermarks(db)) == 3
        codes = {r["error_code"] for r in db.execute("SELECT error_code FROM quarantine.record")}
        assert {
            "DUPLICATE_KEY",
            "INVALID_EMAIL",
            "MISSING_REQUIRED_FIELD",
            "REFERENTIAL_INTEGRITY_FAILURE",
            "UNKNOWN_CLASSIFICATION",
            "INVALID_DATE_RANGE",
        } <= codes


@pytest.mark.parametrize("failure", ["extraction", "validation", "load"])
def test_failure_rolls_back_and_recovers(db_config, api_client, failure):
    seed(db_config)
    run_pipeline(db_config, client=api_client())
    before = warehouse(db_config)
    with connect(db_config) as db:
        watermark_before = audit.watermarks(db)
    seed(db_config, "incremental")
    with pytest.raises(RuntimeError, match="failed"):
        run_pipeline(db_config, client=api_client(), fail_at=failure)
    assert warehouse(db_config) == before
    with connect(db_config) as db:
        assert audit.watermarks(db) == watermark_before
        failed = db.execute("SELECT * FROM audit.pipeline_run ORDER BY started_at DESC LIMIT 1")
        assert failed.fetchone()["status"] == "FAILED"
    assert run_pipeline(db_config, client=api_client())["status"] == "SUCCESS"


def test_strict_quality_persists_evidence_without_advancing(db_config, api_client):
    seed(db_config)
    strict = db_config.model_copy(update={"max_rejected_fraction": 0})
    with pytest.raises(RuntimeError, match="QualityThresholdError"):
        run_pipeline(strict, client=api_client())
    with connect(db_config) as db:
        assert audit.watermarks(db) == {}
        assert db.execute("SELECT count(*) AS n FROM quarantine.record").fetchone()["n"] == 6
        assert db.execute("SELECT count(*) AS n FROM raw.person").fetchone()["n"] == 5
        assert db.execute("SELECT count(*) AS n FROM analytics.dim_person").fetchone()["n"] == 0


def test_snapshot_stable_while_source_changes(db_config, api_client):
    seed(db_config)
    with api_client() as client:
        snap = client.get("/api/v1/snapshot").json()
        with connect(db_config) as db:
            append_changes(db, [("person", "P1", person("P1", last_name="Changed"))])
        old = client.get("/api/v1/persons", params={"snapshot_id": snap["snapshot_id"]}).json()
        assert old["items"][0]["payload"]["last_name"] == "Lovelace  "
        new = client.get("/api/v1/snapshot").json()
        delta = client.get(
            "/api/v1/persons",
            params={"snapshot_id": new["snapshot_id"], "updated_since": snap["watermark_end"]},
        ).json()
        assert len(delta["items"]) == 1
        assert delta["items"][0]["payload"]["last_name"] == "Changed"


def test_api_rejects_naive_watermark(db_config, api_client):
    with api_client() as client:
        result = client.get(
            "/api/v1/persons", params={"snapshot_id": 0, "updated_since": "2026-01-01"}
        )
    assert result.status_code == 422


def test_partial_watermark_write_rolls_back(db_config, api_client):
    seed(db_config)
    run_pipeline(db_config, client=api_client())
    before = warehouse(db_config)
    with connect(db_config) as db:
        old_watermarks = audit.watermarks(db)
    seed(db_config, "incremental")

    def interrupted_stage(name, function, *args):
        result = function(*args)
        if name == "watermark_update":
            raise RuntimeError("Fail after first watermark SQL statement")
        return result

    with pytest.raises(RuntimeError, match="failed"):
        run_pipeline(db_config, client=api_client(), stage=interrupted_stage)
    assert warehouse(db_config) == before
    with connect(db_config) as db:
        assert audit.watermarks(db) == old_watermarks
        assert (
            db.execute("""SELECT status FROM audit.pipeline_run
            ORDER BY started_at DESC LIMIT 1""").fetchone()["status"]
            == "FAILED"
        )


def test_actual_database_write_failure(db_config, api_client):
    seed(db_config)

    def broken_write(name, function, *args):
        if name == "analytics_upsert":
            args[0].execute("SELECT 1/0")
        return function(*args)

    with pytest.raises(RuntimeError, match="DivisionByZero"):
        run_pipeline(db_config, client=api_client(), stage=broken_write)
    with connect(db_config) as db:
        assert audit.watermarks(db) == {}
        assert db.execute("SELECT count(*) AS n FROM analytics.dim_person").fetchone()["n"] == 0


def test_concurrent_run_refused(db_config, api_client):
    from workforcesync.database import PIPELINE_LOCK

    with connect(db_config) as lock:
        lock.execute("SELECT pg_advisory_lock(%s)", (PIPELINE_LOCK,))
        try:
            with pytest.raises(RuntimeError, match="Another workforce pipeline"):
                run_pipeline(db_config, client=api_client())
        finally:
            lock.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_LOCK,))


def test_inclusive_timestamp_boundary_and_stale_upsert(db_config, api_client):
    from workforcesync.extraction import Snapshot, extract
    from workforcesync.loading import upsert
    from workforcesync.transformation import transform

    seed(db_config)
    first = run_pipeline(db_config, client=api_client())
    with connect(db_config) as db:
        stamp = db.execute("SELECT min(updated_at) AS ts FROM source.change").fetchone()["ts"]
    with api_client() as client:
        snapshot = Snapshot.model_validate(client.get("/api/v1/snapshot").json())
        records = extract(client, "person", snapshot, stamp, 2)
        assert len(records) == 5
    normalized, _ = transform("person", [r for r in records if r["source_record_id"] == "P1"])
    seed(db_config, "incremental")
    run_pipeline(db_config, client=api_client())
    target = warehouse(db_config)
    with connect(db_config) as db:
        counts = upsert(db, first["run_id"], "person", normalized, 2)
        assert counts["rows_loaded"] == 0
    assert warehouse(db_config) == target


def test_real_http_failure_is_audited(db_config):
    import httpx

    seed(db_config)
    client = httpx.Client(
        base_url="http://source", transport=httpx.MockTransport(lambda _: httpx.Response(503))
    )
    with pytest.raises(RuntimeError, match="HTTPStatusError"):
        run_pipeline(db_config, client=client)
    with connect(db_config) as db:
        assert audit.watermarks(db) == {}
        assert db.execute("SELECT status FROM audit.pipeline_run").fetchone()["status"] == "FAILED"
