import os
from datetime import UTC, datetime

import pytest

from workforcesync.config import Settings
from workforcesync.database import connect


@pytest.fixture
def timestamp():
    return datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def db_config():
    database = os.getenv("TEST_POSTGRES_DB")
    if not database:
        pytest.skip("Set TEST_POSTGRES_DB to an isolated migrated database ending in _test")
    if not database.endswith("_test"):
        pytest.fail("Integration tests only reset databases whose name ends in _test")
    config = Settings(postgres_db=database, page_size=2, batch_size=2)
    with connect(config) as db:
        db.execute("""TRUNCATE source.change, source.scenario, audit.pipeline_run,
            audit.pipeline_watermark, staging.person, staging.employment, staging.classification,
            analytics.dim_person, analytics.dim_classification, analytics.fact_employment,
            analytics.employment_history RESTART IDENTITY CASCADE""")
    return config
