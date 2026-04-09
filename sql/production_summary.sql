-- Daily rollup with rolling 7-day OEE average
WITH daily AS (
    SELECT
        date,
        COUNT(*)                        AS total_runs,
        SUM(total_units)                AS total_units,
        SUM(good_units)                 AS good_units,
        SUM(CASE WHEN failure = 1 THEN 1 ELSE 0 END) AS failure_count,
        ROUND(AVG(oee), 4)             AS avg_oee,
        ROUND(AVG(availability), 4)    AS avg_availability,
        ROUND(AVG(performance), 4)     AS avg_performance,
        ROUND(AVG(quality), 4)         AS avg_quality
    FROM production_runs
    GROUP BY date
)
SELECT
    date,
    total_runs,
    total_units,
    good_units,
    failure_count,
    avg_oee,
    ROUND(
        AVG(avg_oee) OVER (
            ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 4
    ) AS rolling_7d_oee,
    avg_availability,
    avg_performance,
    avg_quality
FROM daily
ORDER BY date;
