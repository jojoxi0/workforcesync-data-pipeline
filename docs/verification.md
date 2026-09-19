# Verification record

Validated on 2026-09-19 with Python 3.13.15 and portable PostgreSQL 17.11 on Windows. PostgreSQL listened only on loopback; credentials and runtime files were kept in ignored local files.

- Installed locked dependencies with uv and validated package imports.
- Applied migrations to clean application and isolated test databases.
- Exercised Alembic downgrade-to-base and upgrade-to-head on the disposable test database.
- Passed 39 tests covering normalization, quality, pagination, source snapshots, raw/quarantine persistence, incremental changes, UPSERTs, idempotency, failure audits, concurrency and watermark rollback.
- Passed `ruff check .` and `ruff format --check .`.
- Built wheel/source distributions and inspected package contents for missing modules and accidental local files.
- Started Uvicorn and executed the complete Prefect flow against the real HTTP API.
- Executed the deterministic incremental scenario and an unchanged-source rerun.
- Executed all six analytical SQL queries and captured an actual EXPLAIN ANALYZE plan.

The installed FastAPI/Starlette stack emits test-client deprecation warnings; tests pass. These warnings are dependency compatibility notices, not suppressed failures.

Docker Engine/Desktop was not installed on the development host. Container validation was completed on GitHub's Ubuntu runner instead. [CI run 35466837133](https://github.com/jojoxi0/workforcesync-data-pipeline/actions/runs/35466837133) passed on 2026-09-19 against implementation commit `80c807581dd0f27ef4631860826bb04f5088a357`:

- Locked dependency installation, all 39 tests, lint, formatting, migration round trip and package build.
- Actual HTTP extraction and Prefect orchestration smoke test.
- Clean Docker Compose build/start, migration and seed.
- Initial, incremental and unchanged-source pipeline executions inside containers.
- Expected nonzero controlled load failure followed by successful recovery.
- All analytics SQL queries inside the container environment.

The subsequent documentation-only commit records this result; it does not change the tested implementation.

Recorded application run data is in `examples/runs.json`. Durations are observational and not benchmarks. The snapshot protocol assumes source clock monotonicity and full tombstones; observed employment history is not an event-complete CDC log.
