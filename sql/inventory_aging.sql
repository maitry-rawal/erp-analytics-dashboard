-- Tool wear buckets by machine with critical % and failure counts
WITH bucketed AS (
    SELECT
        machine,
        CASE
            WHEN tool_wear_min BETWEEN   0 AND  50 THEN '0-50 Fresh'
            WHEN tool_wear_min BETWEEN  51 AND 100 THEN '50-100 Mid'
            WHEN tool_wear_min BETWEEN 101 AND 175 THEN '100-175 Worn'
            ELSE '175+ Critical'
        END AS wear_bucket,
        CASE WHEN tool_wear_min > 175 THEN 1 ELSE 0 END AS is_critical,
        failure
    FROM production_runs
),
summary AS (
    SELECT
        machine,
        wear_bucket,
        COUNT(*)                                    AS run_count,
        SUM(failure)                                AS tool_failures,
        SUM(is_critical)                            AS critical_runs
    FROM bucketed
    GROUP BY machine, wear_bucket
),
machine_totals AS (
    SELECT
        machine,
        SUM(run_count)      AS total_runs,
        SUM(critical_runs)  AS total_critical
    FROM summary
    GROUP BY machine
)
SELECT
    s.machine,
    s.wear_bucket,
    s.run_count,
    s.tool_failures,
    ROUND(s.tool_failures * 100.0 / s.run_count, 2) AS failure_rate_pct,
    ROUND(mt.total_critical * 100.0 / mt.total_runs, 2) AS machine_critical_pct
FROM summary s
JOIN machine_totals mt USING (machine)
ORDER BY s.machine, s.wear_bucket;
