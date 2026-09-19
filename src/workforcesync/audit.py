from workforcesync.database import ENTITIES

PIPELINE = "workforce_daily_sync"


def start(db, run_id, full: bool):
    db.execute(
        """INSERT INTO audit.pipeline_run(run_id,pipeline_name,status,full_load)
        VALUES (%s,%s,'RUNNING',%s)""",
        (run_id, PIPELINE, full),
    )
    for entity in ENTITIES:
        db.execute(
            "INSERT INTO audit.entity_run(pipeline_run_id,entity_name) VALUES (%s,%s)",
            (run_id, entity),
        )


def finish(db, run_id, status: str, error: str | None = None):
    db.execute(
        """UPDATE audit.pipeline_run SET status=%s, error_message=%s,
        finished_at=clock_timestamp(),
        duration_ms=(extract(epoch FROM clock_timestamp()-started_at)*1000)::bigint
        WHERE run_id=%s""",
        (status, error, run_id),
    )


def watermarks(db) -> dict:
    return {
        r["entity_name"]: r["last_successful_watermark"]
        for r in db.execute(
            "SELECT * FROM audit.pipeline_watermark WHERE pipeline_name=%s", (PIPELINE,)
        )
    }


def advance(db, entity: str, boundary):
    db.execute(
        """INSERT INTO audit.pipeline_watermark
        (pipeline_name,entity_name,last_successful_watermark) VALUES (%s,%s,%s)
        ON CONFLICT (pipeline_name,entity_name) DO UPDATE SET
        last_successful_watermark=greatest(pipeline_watermark.last_successful_watermark,
                                          EXCLUDED.last_successful_watermark),
        updated_at=clock_timestamp()""",
        (PIPELINE, entity, boundary),
    )


def result(db, run_id) -> dict:
    run = db.execute("SELECT * FROM audit.pipeline_run WHERE run_id=%s", (run_id,)).fetchone()
    run["entities"] = db.execute(
        """SELECT * FROM audit.entity_run
        WHERE pipeline_run_id=%s ORDER BY entity_name""",
        (run_id,),
    ).fetchall()
    return run
