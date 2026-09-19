"""Source history, ingestion layers, warehouse, and run metadata."""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

ENTITY_COLUMNS = {
    "person": """person_id text PRIMARY KEY, first_name text NOT NULL,
        last_name text NOT NULL, email text NOT NULL, status text NOT NULL
        CHECK (status IN ('active','inactive'))""",
    "classification": """classification_id text PRIMARY KEY, name text NOT NULL,
        department text NOT NULL""",
    "employment": """employment_id text PRIMARY KEY, person_id text NOT NULL,
        classification_id text NOT NULL, employment_type text NOT NULL
        CHECK (employment_type IN ('full_time','part_time','contract')),
        status text NOT NULL CHECK (status IN ('active','ended','leave')),
        start_date date NOT NULL, end_date date,
        CHECK (end_date IS NULL OR end_date >= start_date)""",
}
TARGETS = {
    "person": "dim_person",
    "classification": "dim_classification",
    "employment": "fact_employment",
}


def upgrade():
    for schema in ("source", "raw", "staging", "analytics", "audit", "quarantine"):
        op.execute(f"CREATE SCHEMA {schema}")
    op.execute("""CREATE TABLE source.change (
        change_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        entity_name text NOT NULL CHECK (entity_name IN ('person','employment','classification')),
        source_record_id text NOT NULL, updated_at timestamptz NOT NULL,
        payload jsonb NOT NULL);
        CREATE INDEX source_incremental ON source.change(entity_name, updated_at, change_id);
        CREATE INDEX source_versions
            ON source.change(entity_name, source_record_id, change_id DESC);
        CREATE TABLE source.scenario (name text PRIMARY KEY, applied_at timestamptz DEFAULT now());
        CREATE TABLE audit.pipeline_run (
            run_id uuid PRIMARY KEY, pipeline_name text NOT NULL,
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            finished_at timestamptz, status text NOT NULL
                CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
            full_load boolean NOT NULL, watermark_end timestamptz,
            duration_ms bigint, error_message text);
        CREATE TABLE audit.entity_run (
            pipeline_run_id uuid REFERENCES audit.pipeline_run(run_id), entity_name text NOT NULL,
            watermark_start timestamptz, watermark_end timestamptz,
            rows_extracted integer NOT NULL DEFAULT 0, rows_loaded integer NOT NULL DEFAULT 0,
            rows_inserted integer NOT NULL DEFAULT 0, rows_updated integer NOT NULL DEFAULT 0,
            rows_deleted integer NOT NULL DEFAULT 0, rows_rejected integer NOT NULL DEFAULT 0,
            PRIMARY KEY (pipeline_run_id, entity_name));
        CREATE TABLE audit.pipeline_watermark (
            pipeline_name text NOT NULL, entity_name text NOT NULL,
            last_successful_watermark timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY(pipeline_name, entity_name));
        CREATE TABLE quarantine.record (
            quarantine_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            pipeline_run_id uuid NOT NULL REFERENCES audit.pipeline_run(run_id),
            entity_name text NOT NULL, source_record_id text,
            error_code text NOT NULL, error_message text NOT NULL, payload jsonb NOT NULL,
            detected_at timestamptz NOT NULL DEFAULT clock_timestamp());
        CREATE INDEX quarantine_run ON quarantine.record(pipeline_run_id, entity_name);
    """)
    for entity, columns in ENTITY_COLUMNS.items():
        op.execute(f"""CREATE TABLE raw.{entity} (
            pipeline_run_id uuid NOT NULL REFERENCES audit.pipeline_run(run_id),
            source_record_id text NOT NULL, payload jsonb NOT NULL,
            extracted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY(pipeline_run_id, source_record_id));""")
        for schema, table in (("staging", entity), ("analytics", TARGETS[entity])):
            op.execute(f"""CREATE TABLE {schema}.{table} ({columns},
                updated_at timestamptz NOT NULL, is_deleted boolean NOT NULL,
                pipeline_run_id uuid NOT NULL REFERENCES audit.pipeline_run(run_id));
                CREATE INDEX ON {schema}.{table}(updated_at);""")
    op.execute("""ALTER TABLE analytics.fact_employment
        ADD FOREIGN KEY(person_id) REFERENCES analytics.dim_person(person_id),
        ADD FOREIGN KEY(classification_id)
            REFERENCES analytics.dim_classification(classification_id);
        CREATE INDEX employment_person ON analytics.fact_employment(person_id);
        CREATE INDEX employment_classification ON analytics.fact_employment(classification_id);
        CREATE TABLE analytics.employment_history (
            employment_id text NOT NULL REFERENCES analytics.fact_employment(employment_id),
            classification_id text NOT NULL
                REFERENCES analytics.dim_classification(classification_id),
            updated_at timestamptz NOT NULL, is_deleted boolean NOT NULL,
            pipeline_run_id uuid NOT NULL REFERENCES audit.pipeline_run(run_id),
            PRIMARY KEY(employment_id, updated_at));""")


def downgrade():
    for schema in ("quarantine", "analytics", "staging", "raw", "source", "audit"):
        op.execute(f"DROP SCHEMA {schema} CASCADE")
