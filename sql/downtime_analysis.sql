-- Downtime Analysis — Pareto and Root Cause
-- Identifies top downtime causes for targeted improvement

WITH downtime_summary AS (
    SELECT
        dr.reason_category,
        dr.reason_detail,
        m.machine_name,
        m.production_line,
        COUNT(*) AS incident_count,
        SUM(de.duration_minutes) AS total_downtime_minutes,
        AVG(de.duration_minutes) AS avg_downtime_minutes,
        MAX(de.duration_minutes) AS max_downtime_minutes
    FROM downtime_events de
    JOIN dim_downtime_reason dr ON de.reason_id = dr.reason_id
    JOIN dim_machine m ON de.machine_id = m.machine_id
    WHERE de.event_date BETWEEN @start_date AND @end_date
      AND de.downtime_type = 'UNPLANNED'
    GROUP BY dr.reason_category, dr.reason_detail,
             m.machine_name, m.production_line
),

pareto AS (
    SELECT
        reason_category,
        reason_detail,
        machine_name,
        production_line,
        incident_count,
        total_downtime_minutes,
        avg_downtime_minutes,
        max_downtime_minutes,
        -- Cumulative percentage for Pareto chart
        SUM(total_downtime_minutes) OVER (
            ORDER BY total_downtime_minutes DESC
            ROWS UNBOUNDED PRECEDING
        ) * 100.0 / SUM(total_downtime_minutes) OVER () AS cumulative_pct,
        -- Rank by impact
        ROW_NUMBER() OVER (ORDER BY total_downtime_minutes DESC) AS impact_rank
    FROM downtime_summary
)

SELECT
    impact_rank,
    reason_category,
    reason_detail,
    machine_name,
    production_line,
    incident_count,
    ROUND(total_downtime_minutes / 60.0, 1) AS total_downtime_hours,
    ROUND(avg_downtime_minutes, 1) AS avg_minutes_per_incident,
    ROUND(max_downtime_minutes, 1) AS worst_case_minutes,
    ROUND(cumulative_pct, 1) AS cumulative_impact_pct,
    CASE WHEN cumulative_pct <= 80 THEN 'HIGH PRIORITY' ELSE 'MONITOR' END AS action_priority
FROM pareto
ORDER BY impact_rank;
