"""Atomic warehouse loads with separately durable raw evidence and failure audits."""

from uuid import uuid4

import httpx

from workforcesync import audit
from workforcesync.config import Settings
from workforcesync.database import ENTITIES, PIPELINE_LOCK, TARGETS, connect
from workforcesync.extraction import SourceProtocolError, extract, get_snapshot
from workforcesync.loading import load_quarantine, load_raw, load_staging, upsert
from workforcesync.logging import configure
from workforcesync.quality import QualityThresholdError, validate
from workforcesync.transformation import deduplicate, transform


def direct_stage(name, function, *args):
    return function(*args)


def run_pipeline(
    config: Settings,
    full: bool = False,
    *,
    client=None,
    stage=direct_stage,
    fail_at: str | None = None,
) -> dict:
    run_id = uuid4()
    logger = configure(config.log_level)
    context = {"run_id": str(run_id), "pipeline": audit.PIPELINE}
    active_stage = "startup"
    with connect(config) as lock:
        lock.autocommit = True
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(%s) AS acquired", (PIPELINE_LOCK,)
        ).fetchone()["acquired"]
        if not acquired:
            raise RuntimeError("Another workforce pipeline is running")
        try:
            with connect(config) as db:
                audit.start(db, run_id, full)
                previous = audit.watermarks(db)
            logger.info("pipeline_started", extra={"context": context})
            active_stage = "extraction"
            extracted = {}
            with client or httpx.Client(base_url=config.source_api_url, timeout=30) as http:
                if fail_at == "extraction":
                    raise SourceProtocolError("Controlled extraction failure")
                snapshot = stage("snapshot", get_snapshot, http)
                if any(wm > snapshot.watermark_end for wm in previous.values()):
                    raise SourceProtocolError("Source clock is behind the successful watermark")
                for entity in ENTITIES:
                    lower = None if full else previous.get(entity)
                    records = stage(
                        "extract", extract, http, entity, snapshot, lower, config.page_size
                    )
                    extracted[entity] = records
                    with connect(config) as db:
                        stage("raw_load", load_raw, db, run_id, entity, records)
                        db.execute(
                            """UPDATE audit.entity_run SET rows_extracted=%s,
                            watermark_start=%s,watermark_end=%s
                            WHERE pipeline_run_id=%s AND entity_name=%s""",
                            (len(records), lower, snapshot.watermark_end, run_id, entity),
                        )
                    logger.info(
                        "extraction_completed",
                        extra={
                            "context": {
                                **context,
                                "entity": entity,
                                "stage": active_stage,
                                "rows": len(records),
                            }
                        },
                    )
            with connect(config) as db:
                references = {
                    entity: {
                        r[f"{entity}_id"]
                        for r in db.execute(f"SELECT {entity}_id FROM analytics.{TARGETS[entity]}")
                    }
                    for entity in ("person", "classification")
                }
                valid_entities, reject_count = {}, 0
                for entity in ENTITIES:
                    active_stage = "transformation"
                    normalized, rejected = stage("transform", transform, entity, extracted[entity])
                    unique, duplicates = stage("deduplicate", deduplicate, entity, normalized)
                    active_stage = "validation"
                    valid, invalid = stage(
                        "validate", validate, entity, unique, snapshot.watermark_end, references
                    )
                    rejected += duplicates + invalid
                    valid_entities[entity] = valid
                    if entity in references:
                        references[entity].update(r["row"][f"{entity}_id"] for r in valid)
                    reject_count += len(rejected)
                    with connect(config) as evidence:
                        stage("quarantine", load_quarantine, evidence, run_id, entity, rejected)
                        evidence.execute(
                            """UPDATE audit.entity_run SET rows_rejected=%s
                            WHERE pipeline_run_id=%s AND entity_name=%s""",
                            (len(rejected), run_id, entity),
                        )
                    logger.info(
                        "validation_completed",
                        extra={
                            "context": {
                                **context,
                                "entity": entity,
                                "stage": active_stage,
                                "valid": len(valid),
                                "rejected": len(rejected),
                            }
                        },
                    )
                total = sum(map(len, extracted.values()))
                if fail_at == "validation" or (
                    total and reject_count / total > config.max_rejected_fraction
                ):
                    raise QualityThresholdError("Rejection tolerance exceeded")
                for entity in ENTITIES:
                    active_stage = "staging_load"
                    stage(
                        "staging_load",
                        load_staging,
                        db,
                        run_id,
                        entity,
                        valid_entities[entity],
                        config.batch_size,
                    )
                    active_stage = "analytics_upsert"
                    counts = stage(
                        "analytics_upsert",
                        upsert,
                        db,
                        run_id,
                        entity,
                        valid_entities[entity],
                        config.batch_size,
                    )
                    db.execute(
                        """UPDATE audit.entity_run SET rows_loaded=%s, rows_inserted=%s,
                        rows_updated=%s, rows_deleted=%s
                        WHERE pipeline_run_id=%s AND entity_name=%s""",
                        (
                            counts["rows_loaded"],
                            counts["rows_inserted"],
                            counts["rows_updated"],
                            counts["rows_deleted"],
                            run_id,
                            entity,
                        ),
                    )
                    logger.info(
                        "warehouse_upsert_prepared",
                        extra={
                            "context": {
                                **context,
                                "entity": entity,
                                "stage": active_stage,
                                **counts,
                            }
                        },
                    )
                if fail_at == "load":
                    raise RuntimeError("Controlled failure before commit")
                active_stage = "audit_completion"
                stage("audit_completion", audit.finish, db, run_id, "SUCCESS")
                db.execute(
                    "UPDATE audit.pipeline_run SET watermark_end=%s WHERE run_id=%s",
                    (snapshot.watermark_end, run_id),
                )
                active_stage = "watermark_update"
                for entity in ENTITIES:
                    stage("watermark_update", audit.advance, db, entity, snapshot.watermark_end)
            logger.info("pipeline_completed", extra={"context": {**context, "stage": "committed"}})
        except Exception as error:
            # Exception messages can contain payloads or credentials; retain only safe context.
            safe_error = f"{active_stage}: {type(error).__name__}"
            logger.error("pipeline_failed", extra={"context": {**context, "error": safe_error}})
            try:
                with connect(config) as db:
                    audit.finish(db, run_id, "FAILED", safe_error)
            except Exception:
                logger.error("failure_audit_unavailable", extra={"context": context})
            raise RuntimeError(f"Pipeline {run_id} failed ({safe_error})") from None
        finally:
            lock.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_LOCK,))
    with connect(config) as db:
        return audit.result(db, run_id)
