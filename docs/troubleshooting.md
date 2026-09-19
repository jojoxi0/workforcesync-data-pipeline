# Troubleshooting

| Symptom | Check / recovery |
|---|---|
| Configuration fails before any audit | Set required password; check port and field types in `.env` |
| Missing relation | Run `alembic upgrade head` against the intended database |
| Source 500 response | Check API stderr and migration state; raw records already fetched remain available |
| Connection refused | Start API/database; within Compose use `db` / `api`, not localhost |
| Another pipeline running | Allow the current writer to finish; the DB releases its session lock on disconnect |
| FAILED validation | Inspect quarantine codes and rejection fraction; correct source or choose a deliberate tolerance |
| Failure with unchanged watermark | Expected; repair the dependency and rerun |
| No incremental records after fixing a validator | Old quarantined records are behind watermark; use `--full` or update source with a new timestamp |
| Tests skipped | Set TEST_POSTGRES_DB to an isolated migrated `_test` database |
| Prefect server cannot start | Use `--direct` for diagnosis, or configure a reachable local Prefect server |
| RUNNING audit after process kill | Reconcile manually after confirming the process is gone; retry from previous watermark |

Application logs intentionally exclude raw exception messages and payloads. Identify failures by run ID, stage, and exception class, then inspect raw/quarantine tables locally. Do not paste production payloads or database credentials into issue reports.
