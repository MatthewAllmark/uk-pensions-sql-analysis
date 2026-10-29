-- Business question: within the private sector, which eligible age bands
-- closed the participation gap after automatic enrolment, and which still
-- sit below the middle age bands?
--
-- Eligible employees are 22 to State Pension age, so 18-21 and 66-plus
-- appear only in the all-employee tables and are excluded here.
-- Technique: RANK within the year, and LAG for the year-on-year change.

WITH private_age AS (
    SELECT
        year,
        category AS age_band,
        participation_pct,
        participating_employees
    FROM dwp_participation
    WHERE breakdown = 'age_band'
      AND population = 'Eligible employees'
      AND sector = 'Private'
      AND participation_status = 'observed'
)
SELECT
    year,
    age_band,
    participation_pct,
    participating_employees,
    ROUND(
        participation_pct - LAG(participation_pct) OVER (
            PARTITION BY age_band
            ORDER BY year
        ),
        1
    ) AS yoy_percentage_points,
    RANK() OVER (
        PARTITION BY year
        ORDER BY participation_pct DESC, age_band
    ) AS rank_by_participation
FROM private_age
ORDER BY year, rank_by_participation;
