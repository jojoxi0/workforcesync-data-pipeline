# Performance decisions

Pandas handles a complete extracted interval in memory. This is suitable for small workforce data and keeps deterministic deduplication readable. Pagination limits request size, not total memory. At much larger scale, land each page immediately, transform in SQL or streaming batches, use COPY, and replace source offset pagination with indexed keyset cursors.

Warehouse/staging inserts use multi-row statements bounded by BATCH_SIZE (default 500, maximum 2,000). Raw and quarantine writes use Psycopg `executemany` pipelining. The loader fetches existing rows once per batch to calculate honest insert/update/delete counts and avoid rewriting unchanged versions. It assumes the pipeline is the only analytics writer; its advisory lock enforces that among application runs.

Primary keys support conflict detection. Employment foreign-key indexes support common joins and person lookup. Source indexes support entity/version selection and timestamp access; current source snapshot queries may still scan history to select latest versions. Timestamp indexes support operational inspection and future retention. Query plans depend on data size and distribution.

Run `sql/explain_employment_lookup.sql` in psql after loading representative data. Tiny fixture tables legitimately use sequential scans; forcing an index would not establish a performance improvement. No speedup claim or benchmark is made. The recorded local plan is in `docs/examples/explain.txt`.

Longer-term improvements: raw/source retention, observed-history partitioning when justified, metrics export, and retryable quarantine remediation. Distributed compute is unnecessary at the demonstrated scale.
