# Architecture decisions

The project deliberately uses one Python application and one PostgreSQL instance. Source and warehouse concerns have separate schemas. FastAPI represents an external operational system; the ingestion process accesses its records over HTTP, not by querying its tables.

The simulator writes append-only versions through `append_changes()`. Its writer lock serializes version timestamps and snapshot acquisition. A snapshot ID selects the latest version of each source identifier at a fixed point. Offset pagination is acceptable because this selected dataset cannot move beneath the reader.

`pipeline.py` coordinates the transaction boundaries. Raw extraction evidence and quarantine decisions are durable independently of the warehouse transaction. Parent classifications and people load before employments. A pipeline advisory lock serializes cooperating writers. Direct external writes to analytics are outside the model.

Prefect wraps the individual stages with no result persistence or caching. Live database handles remain in one process; this is intentionally not a distributed task execution design. Only network failures and HTTP 429/500/502/503/504 retry, twice with short delays. Deterministic validation and database writes have no task retry; the complete pipeline is safe to rerun.

An empty interval still advances the source-clock watermark on success. A full run replays current state through the same loader. Alembic owns schema changes; seeding is a separate operation.
