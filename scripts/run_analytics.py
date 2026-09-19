"""Run the repository's reviewed, read-only SQL analytics package."""

import json
from pathlib import Path

from workforcesync.config import Settings
from workforcesync.database import connect

with connect(Settings()) as db:
    db.execute("SET TRANSACTION READ ONLY")
    for path in sorted(Path("sql/analytics").glob("*.sql")):
        rows = db.execute(path.read_text()).fetchall()
        print(json.dumps({"query": path.stem, "rows": rows}, default=str))
