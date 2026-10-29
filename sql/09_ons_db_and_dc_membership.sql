-- Business question: of UK employee jobs in 2021-2024, what share are in a
-- defined benefit scheme, a defined contribution arrangement (including group
-- personal, stakeholder and group SIPP pensions), or have no workplace pension?
--
-- ONS Table 1 is all employee jobs. Table 2 is jobs that already have a
-- workplace pension, so its shares are a composition, not a participation rate.
-- Group personal, stakeholder and group SIPP pensions are contract-based
-- defined contribution. The family roll-up below treats them that way.
-- Technique: CASE to a scheme family, then a windowed year-on-year change.
-- Percentages are rounded by ONS to whole points and need not sum to 100.

WITH typed AS (
    SELECT
        table_name,
        population,
        year,
        pension_type,
        value AS pct_of_jobs,
        CASE
            WHEN pension_type = 'Defined benefit' THEN 'Defined benefit'
            WHEN pension_type LIKE 'No pension%' THEN 'No workplace pension'
            WHEN pension_type LIKE 'Unknown%' THEN 'Unknown'
            ELSE 'Defined contribution, including group personal pensions'
        END AS scheme_family
    FROM ons_pension_type
    WHERE measure_group = 'percent'
),
family AS (
    SELECT
        table_name,
        population,
        year,
        scheme_family,
        SUM(pct_of_jobs) AS pct_of_jobs
    FROM typed
    GROUP BY table_name, population, year, scheme_family
)
SELECT
    table_name,
    population,
    year,
    'family' AS grain,
    scheme_family AS category,
    pct_of_jobs,
    ROUND(
        pct_of_jobs - LAG(pct_of_jobs) OVER (
            PARTITION BY table_name, scheme_family
            ORDER BY year
        ),
        1
    ) AS yoy_percentage_points
FROM family
UNION ALL
SELECT
    table_name,
    population,
    year,
    'pension_type',
    pension_type,
    pct_of_jobs,
    ROUND(
        pct_of_jobs - LAG(pct_of_jobs) OVER (
            PARTITION BY table_name, pension_type
            ORDER BY year
        ),
        1
    )
FROM typed
ORDER BY table_name, grain, year, category;
