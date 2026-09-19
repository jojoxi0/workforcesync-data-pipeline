-- Execute after loading a representative dataset. Tiny fixtures often favor sequential scans.
EXPLAIN (ANALYZE, BUFFERS)
SELECT e.employment_id, e.status, c.name
FROM analytics.fact_employment e
JOIN analytics.dim_classification c USING (classification_id)
WHERE e.person_id = 'P1' AND NOT e.is_deleted;
