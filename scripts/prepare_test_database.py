"""Create and migrate the isolated database; tests themselves reset its data."""

import os

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql

from workforcesync.config import Settings

config = Settings()
database = os.getenv("TEST_POSTGRES_DB", "workforcesync_test")
if not database.endswith("_test"):
    raise SystemExit("TEST_POSTGRES_DB must end in _test")
kwargs = config.connection_kwargs()
kwargs["dbname"] = "postgres"
with psycopg.connect(**kwargs, autocommit=True) as db:
    if not db.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
os.environ["POSTGRES_DB"] = database
command.upgrade(Config("alembic.ini"), "head")
print(f"Migrated {database}; set TEST_POSTGRES_DB={database} when running pytest.")
