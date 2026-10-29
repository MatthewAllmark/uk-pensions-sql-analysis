-- Business question: how much was saved for eligible savers, who paid it,
-- and how much is that per participating eligible employee?
--
-- Amounts are nominal pounds. DWP displays them in billions; the database
-- stores pounds. The headcount join uses eligible employees who participate,
-- which is the ASHE population behind the saving total. It is a mean across
-- participants, not the median (see 07).
-- Technique: join of two facts, share of the published total via a window,
-- and a year-on-year percentage change.

WITH saving AS (
    SELECT year, sector, component, amount_gbp
    FROM dwp_saving
    WHERE population = 'Eligible savers'
      AND amount_status = 'observed'
),
heads AS (
    SELECT year, category AS sector, participating_employees
    FROM dwp_participation
    WHERE table_code = '1.1'
      AND population = 'Eligible employees'
      AND breakdown = 'sector'
      AND employees_status = 'observed'
)
SELECT
    saving.year,
    saving.sector,
    saving.component,
    saving.amount_gbp,
    heads.participating_employees,
    CASE
        WHEN saving.component = 'Total saved' AND heads.participating_employees > 0
            THEN ROUND(1.0 * saving.amount_gbp / heads.participating_employees, 0)
    END AS pounds_per_participating_employee,
    ROUND(
        100.0 * saving.amount_gbp / NULLIF(
            MAX(CASE WHEN saving.component = 'Total saved' THEN saving.amount_gbp END) OVER (
                PARTITION BY saving.year, saving.sector
            ),
            0
        ),
        1
    ) AS share_of_published_total_pct,
    CASE
        WHEN saving.component = 'Total saved' THEN ROUND(
            100.0 * (
                saving.amount_gbp - LAG(saving.amount_gbp) OVER (
                    PARTITION BY saving.sector, saving.component
                    ORDER BY saving.year
                )
            ) / NULLIF(
                LAG(saving.amount_gbp) OVER (
                    PARTITION BY saving.sector, saving.component
                    ORDER BY saving.year
                ),
                0
            ),
            1
        )
    END AS total_yoy_percent
FROM saving
JOIN heads
    ON heads.year = saving.year
   AND heads.sector = saving.sector
ORDER BY saving.sector, saving.year, saving.component;
