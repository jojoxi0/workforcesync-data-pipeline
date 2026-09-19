# Local operations

## Native Python and PostgreSQL

Install Python 3.13, uv, and PostgreSQL 17. Create a local database and login, copy `.env.example` to `.env`, and set its connection values. The project does not install a system database service.

```bash
uv sync --frozen --extra dev
uv run alembic upgrade head
uv run workforcesync seed
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another terminal in the repository:

```bash
uv run workforcesync pipeline --full
uv run python scripts/prepare_test_database.py
# Bash:
TEST_POSTGRES_DB=workforcesync_test uv run pytest -q
```

PowerShell test equivalent: `$env:TEST_POSTGRES_DB='workforcesync_test'; uv run pytest -q`.
The test database creator needs local CREATEDB privilege. It creates only a missing `_test` database and applies migrations. The tests truncate its data.

## Demonstration A: initial load

Use the README's Compose setup with a new PostgreSQL volume. Seed then run `workforcesync pipeline --full`. Inspect actual per-entity output or the queries below. Repeating `seed` is a no-op. Keep a separate Compose project/volume when you need another clean demonstration; do not erase a populated database just to reproduce screenshots.

## Demonstration B: incremental changes

```bash
docker compose run --rm runner workforcesync seed --scenario incremental
docker compose run --rm runner workforcesync pipeline
docker compose run --rm runner workforcesync pipeline
```

The fixture changes P1's surname, adds P5, reclassifies E1, tombstones E2, and adds E6 for P5. The second pipeline should have no changes; integration tests also assert warehouse rows and history are identical after replay.

## Demonstration C: failure and recovery

```bash
docker compose run --rm runner workforcesync status
docker compose run --rm runner workforcesync pipeline --fail-at load
# The previous command must exit nonzero.
docker compose run --rm runner workforcesync status
docker compose run --rm runner workforcesync pipeline
```

Compare successful watermarks before/after failure. To fail with pending changes, apply the incremental seed after A and invoke `--fail-at load` before B's pipeline. `--fail-at extraction` fails before source reads; `--fail-at validation` fails after durable rejection evidence. Strict source acceptance can also be demonstrated with `docker compose run --rm -e MAX_REJECTED_FRACTION=0 runner workforcesync pipeline --full`.

## Inspect the database

Open SQL using `docker compose exec db psql -U workforcesync -d workforcesync` (adjust names if customized).

```sql
SELECT run_id, status, duration_ms, error_message
FROM audit.pipeline_run ORDER BY started_at DESC;
SELECT * FROM audit.entity_run ORDER BY pipeline_run_id, entity_name;
SELECT * FROM audit.pipeline_watermark;
SELECT entity_name, error_code, count(*) FROM quarantine.record GROUP BY 1, 2;
SELECT employment_id, classification_id, is_deleted FROM analytics.fact_employment;
```

To inspect HTTP manually, first GET `/api/v1/snapshot`; pass its `snapshot_id` into `/api/v1/persons`, `/api/v1/employments`, or `/api/v1/classifications`. Follow `next_offset` until null. `updated_since` is optional and must include a timezone. The Python extractor implements this protocol.

## Daily Prefect schedule

Run a local Prefect server in one terminal: `uv run prefect server start --host 127.0.0.1`.
Set `PREFECT_API_URL=http://127.0.0.1:4200/api` in the process environment of the next terminal (Bash `export`, PowerShell `$env:PREFECT_API_URL='http://127.0.0.1:4200/api'`). Run:

```bash
uv run python -m orchestration.flows
```

The serving process registers `workforce-daily` at `0 6 * * *` (06:00 UTC), with one flow at a time. Keep the source API, server, and serving process alive. Inspect deployments and runs at `http://127.0.0.1:4200`. This is a local always-running process, not a cloud deployment. In containers, use a reachable server hostname rather than container localhost.

## Shutdown and maintenance

`docker compose down` stops services and preserves the database volume. Migration rollback is available through Alembic but `downgrade base` destroys these schemas; use it only in a disposable test database. Raw/source/quarantine retention is manual in this portfolio version. A process crash can leave RUNNING: verify no runner owns the advisory lock, inspect evidence, mark the interrupted run failed, and rerun without changing successful watermarks.
