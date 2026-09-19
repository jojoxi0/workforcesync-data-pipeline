from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from workforcesync.config import Settings

ENTITIES = ("classification", "person", "employment")
TARGETS = {
    "classification": "dim_classification",
    "person": "dim_person",
    "employment": "fact_employment",
}
PIPELINE_LOCK = 7142001
SOURCE_LOCK = 7142002


@contextmanager
def connect(settings: Settings):
    with psycopg.connect(**settings.connection_kwargs(), row_factory=dict_row) as connection:
        yield connection
