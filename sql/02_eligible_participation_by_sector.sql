-- Business question: how did automatic-enrolment eligible workplace pension
-- participation move after duties began in 2012, for public, private and
-- all employees in Great Britain?
--
-- Population: eligible employees (aged 22 to State Pension age and earning
-- at least the earnings trigger). Source: DWP estimates from ONS ASHE.
-- Technique: LAG for the year-on-year change, and a windowed baseline for
-- the change since 2012. Headcount is a stock, so it is not cumulated.

WITH eligible AS (
    SELECT
        year,
        sector,
        participation_pct,
        participating_employees
    FROM dwp_participation
    WHERE table_code = '1.1'
      AND population = 'Eligible employees'
      AND breakdown = 'sector'
      AND participation_status = 'observed'
      AND employees_status = 'observed'
)
SELECT
    year,
    sector,
    participation_pct,
    participating_employees,
    ROUND(
        participation_pct - LAG(participation_pct) OVER (
            PARTITION BY sector
            ORDER BY year
        ),
        1
    ) AS yoy_percentage_points,
    ROUND(
        participation_pct - MAX(CASE WHEN year = 2012 THEN participation_pct END) OVER (
            PARTITION BY sector
        ),
        1
    ) AS change_since_2012_pp,
    participating_employees - LAG(participating_employees) OVER (
        PARTITION BY sector
        ORDER BY year
    ) AS yoy_change_in_employees
FROM eligible
ORDER BY sector, year;
