-- Current people, not employment contracts; people with two departments count in each.
SELECT c.department, count(DISTINCT e.person_id) AS headcount
FROM analytics.fact_employment e
INNER JOIN analytics.dim_person p USING (person_id)
INNER JOIN analytics.dim_classification c USING (classification_id)
WHERE e.status = 'active' AND p.status = 'active'
  AND NOT e.is_deleted AND NOT p.is_deleted AND NOT c.is_deleted
GROUP BY c.department
ORDER BY headcount DESC, c.department;
