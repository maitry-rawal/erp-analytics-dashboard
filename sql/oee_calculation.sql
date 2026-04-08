-- OEE Calculation Query
-- Overall Equipment Effectiveness = Availability x Performance x Quality
-- Designed for manufacturing production tracking systems

WITH production_data AS (
    SELECT
        m.machine_id,
        m.machine_name,
        d.production_date,
        s.shift_name,
        -- Planned production time (minutes)
        COALESCE(SUM(pr.planned_production_time), 0) AS planned_time,
        -- Actual run time (excludes downtime)
        COALESCE(SUM(pr.actual_run_time), 0) AS run_time,
        -- Total units produced
        COALESCE(SUM(pr.total_units_produced), 0) AS total_produced,
        -- Good units (passed QC)
        COALESCE(SUM(pr.good_units), 0) AS good_units,
        -- Ideal cycle time per unit (seconds)
        m.ideal_cycle_time_seconds
    FROM production_runs pr
    JOIN dim_machine m ON pr.machine_id = m.machine_id
    JOIN dim_date d ON pr.date_key = d.date_key
    JOIN dim_shift s ON pr.shift_id = s.shift_id
    WHERE d.production_date BETWEEN @start_date AND @end_date
    GROUP BY m.machine_id, m.machine_name, d.production_date,
             s.shift_name, m.ideal_cycle_time_seconds
),

oee_components AS (
    SELECT
        machine_id,
        machine_name,
        production_date,
        shift_name,
        -- Availability = Run Time / Planned Production Time
        CASE
            WHEN planned_time > 0
            THEN CAST(run_time AS DECIMAL(10,4)) / planned_time
            ELSE 0
        END AS availability,
        -- Performance = (Ideal Cycle Time x Total Units) / Run Time
        CASE
            WHEN run_time > 0
            THEN (ideal_cycle_time_seconds * total_produced) / (run_time * 60.0)
            ELSE 0
        END AS performance,
        -- Quality = Good Units / Total Units
        CASE
            WHEN total_produced > 0
            THEN CAST(good_units AS DECIMAL(10,4)) / total_produced
            ELSE 0
        END AS quality,
        planned_time,
        run_time,
        total_produced,
        good_units
    FROM production_data
)

SELECT
    machine_id,
    machine_name,
    production_date,
    shift_name,
    ROUND(availability * 100, 2) AS availability_pct,
    ROUND(performance * 100, 2) AS performance_pct,
    ROUND(quality * 100, 2) AS quality_pct,
    ROUND(availability * performance * quality * 100, 2) AS oee_pct,
    planned_time AS planned_minutes,
    run_time AS actual_minutes,
    total_produced,
    good_units,
    total_produced - good_units AS defect_units,
    -- OEE Classification
    CASE
        WHEN availability * performance * quality >= 0.85 THEN 'World Class'
        WHEN availability * performance * quality >= 0.65 THEN 'Typical'
        WHEN availability * performance * quality >= 0.40 THEN 'Below Average'
        ELSE 'Critical - Needs Attention'
    END AS oee_class
FROM oee_components
ORDER BY production_date DESC, machine_name;
