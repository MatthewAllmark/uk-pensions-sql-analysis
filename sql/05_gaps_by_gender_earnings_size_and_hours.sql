-- Business question: among eligible employees, how large are the 2025
-- participation gaps by gender, pay, employer size and hours, and how did
-- the private-sector employer-size gap move after 2012?
--
-- Earnings bands are DWP's 2024-earnings-terms bands (note 9). They are not
-- the HMRC opt-out earnings bands and should not be joined to them.
-- Technique: conditional aggregation (MAX CASE) to put the two groups of a
-- gap on one row, then a window for the employer-size series.

WITH gender_gap AS (
    SELECT
        year,
        sector,
        MAX(CASE WHEN category = 'Female' THEN participation_pct END) AS female_pct,
        MAX(CASE WHEN category = 'Male' THEN participation_pct END) AS male_pct,
        MAX(CASE WHEN category = 'Female' THEN participating_employees END) AS female_employees,
        MAX(CASE WHEN category = 'Male' THEN participating_employees END) AS male_employees
    FROM dwp_participation
    WHERE breakdown = 'gender'
      AND population = 'Eligible employees'
      AND participation_status = 'observed'
    GROUP BY year, sector
),
earnings_gap AS (
    SELECT
        year,
        sector,
        MAX(CASE WHEN category = '£70,000+' THEN participation_pct END) AS high_pct,
        MAX(CASE WHEN category = '£10,000 - under £20,000' THEN participation_pct END) AS low_pct
    FROM dwp_participation
    WHERE breakdown = 'earnings_band'
      AND population = 'Eligible employees'
      AND participation_status = 'observed'
    GROUP BY year, sector
),
size_series AS (
    SELECT
        year,
        category AS employer_size,
        participation_pct
    FROM dwp_participation
    WHERE breakdown = 'employer_size'
      AND population = 'Eligible employees'
      AND sector = 'Private'
      AND participation_status = 'observed'
),
hours_gap AS (
    SELECT
        year,
        sector,
        MAX(CASE WHEN category = 'Full-time' THEN participation_pct END) AS full_time_pct,
        MAX(CASE WHEN category = 'Part-time' THEN participation_pct END) AS part_time_pct
    FROM dwp_participation
    WHERE breakdown = 'working_pattern'
      AND population = 'Eligible employees'
      AND participation_status = 'observed'
    GROUP BY year, sector
)
SELECT
    'gender' AS topic,
    year,
    sector,
    'Female minus male' AS comparison,
    female_pct AS group_a_pct,
    male_pct AS group_b_pct,
    ROUND(female_pct - male_pct, 1) AS gap_percentage_points,
    female_employees AS group_a_employees,
    male_employees AS group_b_employees
FROM gender_gap
UNION ALL
SELECT
    'earnings',
    year,
    sector,
    '£70,000+ minus £10,000 to £20,000',
    high_pct,
    low_pct,
    ROUND(high_pct - low_pct, 1),
    NULL,
    NULL
FROM earnings_gap
UNION ALL
SELECT
    'working_pattern',
    year,
    sector,
    'Part-time minus full-time',
    part_time_pct,
    full_time_pct,
    ROUND(part_time_pct - full_time_pct, 1),
    NULL,
    NULL
FROM hours_gap
UNION ALL
SELECT
    'private_employer_size',
    year,
    'Private',
    employer_size,
    participation_pct,
    NULL,
    ROUND(
        participation_pct - FIRST_VALUE(participation_pct) OVER (
            PARTITION BY employer_size
            ORDER BY year
        ),
        1
    ),
    NULL,
    NULL
FROM size_series
ORDER BY topic, sector, comparison, year;
