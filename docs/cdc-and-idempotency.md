# Incremental loading and idempotency

1. Acquire the pipeline's PostgreSQL session advisory lock.
2. Persist a RUNNING audit and read per-entity successful watermarks.
3. Obtain the source snapshot ID and source-clock upper boundary.
4. Extract latest source versions at that snapshot with `updated_at >= watermark`.
5. Persist raw evidence; normalize, deduplicate, validate and persist rejection evidence.
6. In one transaction, replace each accepted staging batch and UPSERT analytics in dependency order.
7. Mark SUCCESS and advance every watermark in that same transaction, then commit.

The source writer holds the same short lock used by snapshot acquisition and assigns timestamps inside it. Snapshot creation waits for pending writes. Later writes therefore cannot acquire an older timestamp under normal monotonic clock behavior. Backward clock jumps are an explicit limitation; a snapshot behind the previous watermark fails.

Pagination pins `change_id <= snapshot_id` and chooses the latest version per source ID before applying the incremental predicate. Inclusive lower bounds safely replay timestamp ties. UPSERT accepts only strictly newer timestamps. Replaying an interval cannot duplicate business keys, regress targets, or create repeated history rows. The snapshot also prevents page shifts caused by concurrent source updates.

Full load means current-state replay, not destructive replacement. Watermarks use `greatest(existing, new)` and never regress. Full replay does not reconstruct earlier source events omitted between successful snapshots.

Soft deletion requires a complete record with `is_deleted=true`. Physical deletion is intentionally not supported; absent records do not imply deleted records. Foreign keys remain valid against deleted parents. All current headcount queries filter parent/child tombstones.

Rejection tolerance defaults to allowing quarantine. Thus SUCCESS means all valid rows committed and invalid rows were durably recorded, not that the source contained no bad data. For strict acceptance use `MAX_REJECTED_FRACTION=0`. Correction requires a new source modification timestamp, or `--full` after validation rules change. Quarantine is an attempt log and can accumulate repeated rejections on explicit full replays.

If load or watermark update fails, all warehouse/staging/success writes roll back together. Raw and quarantine evidence remain. A separate transaction records FAILED. If the database is down, only the log can record the failure; no application can persist an audit row to an unavailable database.
