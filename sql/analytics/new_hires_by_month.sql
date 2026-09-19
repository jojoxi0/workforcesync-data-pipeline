-- Employment starts, including rehiring; not unique first-time people.
WITH months AS (
    SELECT date_trunc('month', start_date)::date AS month, count(*) AS hires
    FROM analytics.fact_employment WHERE NOT is_deleted
    GROUP BY 1
)
SELECT month, hires, sum(hires) OVER (ORDER BY month) AS cumulative_hires
FROM months ORDER BY month;
