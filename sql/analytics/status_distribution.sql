SELECT CASE WHEN is_deleted THEN 'deleted' ELSE status END AS employment_status,
       count(*) AS contracts,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS percent_of_contracts
FROM analytics.fact_employment
GROUP BY CASE WHEN is_deleted THEN 'deleted' ELSE status END
ORDER BY contracts DESC, employment_status;
