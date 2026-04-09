-- Pareto analysis: downtime by category and detail with cumulative %
WITH ranked AS (
    SELECT
        category,
        detail,
        COUNT(*)                     AS event_count,
        ROUND(SUM(duration_min), 1)  AS total_minutes,
        ROUND(SUM(duration_hrs), 2)  AS total_hours
    FROM downtime_events
    GROUP BY category, detail
),
totals AS (
    SELECT SUM(total_minutes) AS grand_total FROM ranked
)
SELECT
    r.category,
    r.detail,
    r.event_count,
    r.total_minutes,
    r.total_hours,
    ROUND(r.total_minutes * 100.0 / t.grand_total, 2) AS pct_of_total,
    ROUND(
        SUM(r.total_minutes) OVER (ORDER BY r.total_minutes DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        * 100.0 / t.grand_total,
    2) AS cumulative_pct
FROM ranked r
CROSS JOIN totals t
ORDER BY r.total_minutes DESC;
