# Engineering requirement coverage

| Requirement | Implementation / evidence |
|---|---|
| PostgreSQL staging and migration scripts | `migrations/versions/001_initial.py`; clean upgrade and downgrade/upgrade checks |
| Person, Employment, Classification ingestion | Three API routes and dependency-ordered `ENTITIES` |
| Python ETL and Pandas | `pipeline.py`, `transformation.py`; DataFrame sort/deduplication |
| REST extraction and pagination | `extraction.py`; unit protocol tests and snapshot integration test |
| Cleaning, normalization, deduplication | Small normalization functions; rejected duplicate evidence |
| Warehouse loading, UPSERT | Batched guarded `INSERT ... ON CONFLICT DO UPDATE` in `loading.py` |
| Full and incremental strategies | `--full` current-state replay; timestamp watermarks and pinned snapshots |
| CDC awareness | Source versions and full tombstones; documented polling/event-history limits |
| Idempotency | Full replay, unchanged reruns, stale-version and history assertions |
| Daily orchestration and retries | Prefect stage tasks; `.serve()` daily cron; selective network retry tests |
| Monitoring and logging | Structured logs, run/entity audit tables, `status` CLI, optional local Prefect UI |
| Null and uniqueness checks | Required-field/sentinel rules; Pandas and PostgreSQL keys |
| Referential integrity | Parent lookup validation plus warehouse foreign keys |
| Range/date checks | Date parser and ordered start/end dates, bounded aware modification timestamp |
| Failure handling | Durable rejection evidence, transactional target/watermarks, FAILED audit and recovery tests |
| Data lineage | `docs/data-lineage.md`; run IDs on every persisted layer |
| Batching, indexes, query optimization | Bounded multi-row SQL, pipelined inserts, join/version indexes, real EXPLAIN |
| Environment variables and setup | `.env.example`, validated Settings, Docker/native commands |
| Handoff | README, operations, model, quality, troubleshooting, verification docs |
| Complex SQL and aggregations | Six analytics queries with INNER/LEFT JOIN, CASE, GROUP BY and CTEs |
| Window functions and ranking | Running hires, percent distribution, department dense rank, classification lag |
| Git usage and CI | Focused implementation commits; push/PR validation workflow |
| Validation testing | Unit, data-quality and real PostgreSQL integration suites |

No row-level rejection is silently discarded. Documentation distinguishes implemented mechanisms from unverified runtime environments and future work.
