-- Observed versions at successful extractions, not a complete source event ledger.
WITH versions AS (
    SELECT employment_id, updated_at, classification_id, is_deleted,
           lag(classification_id) OVER (
               PARTITION BY employment_id ORDER BY updated_at
           ) AS previous_classification_id
    FROM analytics.employment_history
)
SELECT employment_id, updated_at, previous_classification_id, classification_id
FROM versions
WHERE previous_classification_id IS NOT NULL
  AND classification_id <> previous_classification_id AND NOT is_deleted
ORDER BY employment_id, updated_at;
