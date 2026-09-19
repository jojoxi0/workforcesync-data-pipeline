-- Keep classifications with zero active contracts in the result.
SELECT c.classification_id, c.name,
       count(e.employment_id) FILTER (WHERE p.person_id IS NOT NULL) AS active_contracts
FROM analytics.dim_classification c
LEFT JOIN analytics.fact_employment e
  ON e.classification_id = c.classification_id AND e.status = 'active' AND NOT e.is_deleted
LEFT JOIN analytics.dim_person p
  ON p.person_id = e.person_id AND p.status = 'active' AND NOT p.is_deleted
WHERE NOT c.is_deleted
GROUP BY c.classification_id, c.name
ORDER BY c.classification_id;
