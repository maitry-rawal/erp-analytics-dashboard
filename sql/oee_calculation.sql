-- OEE by machine, date, shift with classification tier
WITH daily_oee AS (
    SELECT
        machine,
        date,
        shift,
        ROUND(AVG(availability), 4) AS avg_availability,
        ROUND(AVG(performance), 4)  AS avg_performance,
        ROUND(AVG(quality), 4)      AS avg_quality,
        ROUND(AVG(oee), 4)          AS avg_oee,
        COUNT(*)                     AS run_count
    FROM production_runs
    GROUP BY machine, date, shift
)
SELECT
    machine,
    date,
    shift,
    avg_availability,
    avg_performance,
    avg_quality,
    avg_oee,
    run_count,
    CASE
        WHEN avg_oee >= 0.85 THEN 'World Class'
        WHEN avg_oee >= 0.65 THEN 'Typical'
        WHEN avg_oee >= 0.50 THEN 'Below Average'
        ELSE 'Critical'
    END AS oee_class
FROM daily_oee
ORDER BY machine, date, shift;
