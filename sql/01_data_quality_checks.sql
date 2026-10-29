-- Data-quality checks over the loaded facts.
-- PASS/FAIL rows are the acceptance tests. INFO rows describe suppression
-- and known differences of coverage. They are not errors.
--
-- Headcounts are rounded by DWP to the nearest thousand (note 7), so
-- Public + Private can differ from Overall by £1,000 people. Saving
-- components are rounded to the nearest £100 million before they are
-- published, so their sum can differ from the published total by one
-- rounding step.

WITH headcount AS (
    SELECT
        population,
        year,
        SUM(CASE WHEN category = 'Public' THEN participating_employees END) AS public_n,
        SUM(CASE WHEN category = 'Private' THEN participating_employees END) AS private_n,
        SUM(CASE WHEN category = 'Overall' THEN participating_employees END) AS overall_n
    FROM dwp_participation
    WHERE table_code = '1.1'
      AND employees_status = 'observed'
      AND population IN ('Eligible employees', 'All employees')
    GROUP BY population, year
),
saving_gap AS (
    SELECT
        population,
        sector,
        year,
        SUM(CASE WHEN component = 'Total saved' THEN amount_gbp END)
            - SUM(CASE WHEN component <> 'Total saved' THEN amount_gbp END) AS gap_gbp
    FROM dwp_saving
    WHERE amount_status = 'observed'
    GROUP BY population, sector, year
),
ons_share AS (
    SELECT year, SUM(value) AS total_pct
    FROM ons_pension_type
    WHERE table_name = 'Table 1'
      AND measure_group = 'percent'
    GROUP BY year
),
fca_gap AS (
    SELECT
        financial_year,
        SUM(CASE WHEN access_method = 'total' THEN plan_count ELSE 0 END)
            - SUM(CASE WHEN access_method <> 'total' THEN plan_count ELSE 0 END) AS gap_plans
    FROM fca_first_access
    WHERE count_status = 'observed'
    GROUP BY financial_year
),
gender_gap AS (
    SELECT
        g.year,
        g.gender_n - s.overall_n AS gap_people
    FROM (
        SELECT year, SUM(participating_employees) AS gender_n
        FROM dwp_participation
        WHERE breakdown = 'gender'
          AND population = 'Eligible employees'
          AND sector = 'Overall'
          AND employees_status = 'observed'
        GROUP BY year
    ) AS g
    JOIN (
        SELECT year, participating_employees AS overall_n
        FROM dwp_participation
        WHERE table_code = '1.1'
          AND population = 'Eligible employees'
          AND category = 'Overall'
          AND employees_status = 'observed'
    ) AS s ON s.year = g.year
),
duplicate_participation AS (
    SELECT COUNT(*) AS n
    FROM (
        SELECT 1
        FROM dwp_participation
        GROUP BY table_code, population, sector, category, year
        HAVING COUNT(*) > 1
    )
),
duplicate_saving AS (
    SELECT COUNT(*) AS n
    FROM (
        SELECT 1
        FROM dwp_saving
        GROUP BY population, sector, year, component
        HAVING COUNT(*) > 1
    )
),
duplicate_fca AS (
    SELECT COUNT(*) AS n
    FROM (
        SELECT 1
        FROM fca_first_access
        GROUP BY period_label, access_method
        HAVING COUNT(*) > 1
    )
)
SELECT check_name, status, ROUND(metric, 2) AS metric, detail
FROM (
    SELECT
        'eligible_and_all_headcount_adds_across_sector' AS check_name,
        CASE WHEN MAX(ABS(public_n + private_n - overall_n)) <= 2000 THEN 'PASS' ELSE 'FAIL' END AS status,
        MAX(ABS(public_n + private_n - overall_n)) AS metric,
        'Maximum absolute gap, in people, between Public + Private and Overall. Tolerance is 2,000 because DWP rounds each cell to the nearest thousand.' AS detail
    FROM headcount
    UNION ALL
    SELECT
        'saving_components_reconcile_to_total',
        CASE WHEN MAX(ABS(gap_gbp)) <= 200000000 THEN 'PASS' ELSE 'FAIL' END,
        MAX(ABS(gap_gbp)),
        'Maximum absolute gap, in pounds, between employee + employer + tax relief and the published total. Tolerance is £200 million, two published rounding steps.'
    FROM saving_gap
    UNION ALL
    SELECT
        'ons_table1_percentages_sum_near_100',
        CASE WHEN MIN(total_pct) >= 98 AND MAX(total_pct) <= 102 THEN 'PASS' ELSE 'FAIL' END,
        MAX(ABS(total_pct - 100)),
        'ONS rounds pension-type shares to whole percentage points, so the parts need not sum to exactly 100.'
    FROM ons_share
    UNION ALL
    SELECT
        'fca_access_methods_sum_to_published_total',
        CASE WHEN SUM(ABS(gap_plans)) = 0 THEN 'PASS' ELSE 'FAIL' END,
        SUM(ABS(gap_plans)),
        'Sum of annuity, drawdown, UFPLS and full-withdrawal plan counts minus the published total, across financial years.'
    FROM fca_gap
    UNION ALL
    SELECT
        'gender_headcount_matches_sector_total',
        CASE WHEN MAX(ABS(gap_people)) <= 2000 THEN 'PASS' ELSE 'FAIL' END,
        MAX(ABS(gap_people)),
        'Eligible employees, Overall: male + female participating employees versus the sector total. Same nearest-thousand rounding.'
    FROM gender_gap
    UNION ALL
    SELECT
        'no_duplicate_participation_keys',
        CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END,
        n,
        'Duplicate natural keys in dwp_participation.'
    FROM duplicate_participation
    UNION ALL
    SELECT
        'no_duplicate_saving_keys',
        CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END,
        n,
        'Duplicate natural keys in dwp_saving.'
    FROM duplicate_saving
    UNION ALL
    SELECT
        'no_duplicate_fca_keys',
        CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END,
        n,
        'Duplicate natural keys in fca_first_access.'
    FROM duplicate_fca
    UNION ALL
    SELECT
        'participation_rate_disclosure_markers',
        'INFO',
        COUNT(*),
        'Participation cells that are disclosure markers, usually [x] for an unweighted sample below 20, rather than a rate.'
    FROM dwp_participation
    WHERE participation_status <> 'observed'
    UNION ALL
    SELECT
        'participation_rates_outside_0_100',
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
        COUNT(*),
        'Observed participation rates outside 0 to 100 percent.'
    FROM dwp_participation
    WHERE participation_status = 'observed'
      AND (participation_pct < 0 OR participation_pct > 100)
    UNION ALL
    SELECT
        'observed_rates_that_are_null',
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
        COUNT(*),
        'Rows marked observed but missing the numeric rate.'
    FROM dwp_participation
    WHERE participation_status = 'observed'
      AND participation_pct IS NULL
) AS checks
ORDER BY status DESC, check_name;
