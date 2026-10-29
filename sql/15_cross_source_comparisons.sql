-- Business question: do the independent publications agree where they
-- ought to, and where must they be kept apart?
--
-- 1. DWP all-employee participation (Great Britain, people, ASHE) against
--    ONS ASHE Table 1 (United Kingdom, employee jobs). ONS "no workplace
--    pension" is the complement of participation. Geography and the
--    people/jobs unit still differ, so a small gap is informative rather
--    than a failure.
-- 2. HMRC gross Income Tax relief against DWP tax relief for eligible
--    savers. Coverage differs (all UK pension tax relief, including relief
--    on fund investment income, against Great Britain eligible-saver
--    contributions). The rows are placed together so the difference in
--    definition is visible. They are not a reconciliation.

WITH dwp AS (
    SELECT year, participation_pct AS dwp_all_employee_pct
    FROM dwp_participation
    WHERE table_code = '1.1'
      AND population = 'All employees'
      AND category = 'Overall'
      AND participation_status = 'observed'
      AND year BETWEEN 2021 AND 2024
),
ons AS (
    SELECT
        year,
        MAX(CASE WHEN pension_type LIKE 'No pension%' THEN value END) AS ons_no_workplace_pension_pct
    FROM ons_pension_type
    WHERE table_name = 'Table 1'
      AND measure_group = 'percent'
    GROUP BY year
)
SELECT
    'ashe_participation' AS comparison,
    CAST(dwp.year AS TEXT) AS period,
    'DWP all employees, Great Britain, percent' AS left_measure,
    dwp.dwp_all_employee_pct AS left_value,
    'ONS share of UK employee jobs with a workplace pension, 100 minus no-pension share' AS right_measure,
    ROUND(100 - ons.ons_no_workplace_pension_pct, 1) AS right_value,
    ROUND(dwp.dwp_all_employee_pct - (100 - ons.ons_no_workplace_pension_pct), 1) AS left_minus_right
FROM dwp
JOIN ons ON ons.year = dwp.year
UNION ALL
SELECT
    'tax_relief_different_coverage',
    tax_year,
    'HMRC gross Income Tax relief, £ million',
    value_gbp_million,
    NULL,
    NULL,
    NULL
FROM hmrc_relief_component
WHERE income_tax_or_nics = 'Income Tax'
  AND relief_or_charge = 'Gross relief'
  AND breakdown = 'Total'
  AND value_status = 'observed'
UNION ALL
SELECT
    'tax_relief_different_coverage',
    CAST(year AS TEXT),
    'DWP tax relief for eligible savers, Great Britain, £ million',
    ROUND(amount_gbp / 1000000.0, 1),
    NULL,
    NULL,
    NULL
FROM dwp_saving
WHERE population = 'Eligible savers'
  AND sector = 'Overall'
  AND component = 'Tax relief'
  AND amount_status = 'observed'
  AND year BETWEEN 2019 AND 2025
ORDER BY comparison, period, left_measure;
