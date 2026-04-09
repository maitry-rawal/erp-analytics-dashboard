-- Cost per unit (minutes/unit) by product type and machine, with waste
WITH unit_costs AS (
    SELECT
        product_type,
        machine,
        COUNT(*)                                          AS run_count,
        SUM(actual_run_min)                               AS total_run_min,
        SUM(total_units)                                  AS total_units,
        SUM(good_units)                                   AS good_units,
        SUM(total_units) - SUM(good_units)                AS wasted_units,
        ROUND(SUM(actual_run_min) * 1.0 / SUM(total_units), 3)  AS min_per_unit,
        ROUND(SUM(actual_run_min) * 1.0 / SUM(good_units), 3)   AS min_per_good_unit
    FROM production_runs
    GROUP BY product_type, machine
),
type_avg AS (
    SELECT
        product_type,
        ROUND(AVG(min_per_unit), 3) AS type_avg_cost
    FROM unit_costs
    GROUP BY product_type
)
SELECT
    uc.product_type,
    uc.machine,
    uc.run_count,
    uc.total_units,
    uc.good_units,
    uc.wasted_units,
    ROUND(uc.wasted_units * 100.0 / uc.total_units, 2) AS waste_pct,
    uc.min_per_unit,
    uc.min_per_good_unit,
    ta.type_avg_cost,
    ROUND(uc.min_per_unit - ta.type_avg_cost, 3) AS cost_variance
FROM unit_costs uc
JOIN type_avg ta USING (product_type)
ORDER BY uc.product_type, cost_variance DESC;
