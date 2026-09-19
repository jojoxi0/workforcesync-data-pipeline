# Changelog

## 0.1.0 — 2026-09-19

- Added a versioned FastAPI workforce source with deterministic fixtures and snapshot pagination.
- Added PostgreSQL migrations, raw/staging/analytics schemas, quarantine, audit and watermarks.
- Implemented normalization, quality validation, guarded UPSERTs, soft deletes and observed history.
- Added local Prefect stages and a daily serving entrypoint, tests, Docker configuration and CI.
- Documented operations, lineage, failure recovery and known limits with real execution evidence.
