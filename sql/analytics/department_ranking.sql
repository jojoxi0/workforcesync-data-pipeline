WITH departments AS (
    SELECT c.department, count(DISTINCT e.person_id) AS headcount
    FROM analytics.fact_employment e
    JOIN analytics.dim_classification c USING (classification_id)
    JOIN analytics.dim_person p USING (person_id)
    WHERE e.status = 'active' AND p.status = 'active'
      AND NOT e.is_deleted AND NOT p.is_deleted AND NOT c.is_deleted
    GROUP BY c.department
)
SELECT department, headcount, dense_rank() OVER (ORDER BY headcount DESC) AS headcount_rank
FROM departments ORDER BY headcount_rank, department;
