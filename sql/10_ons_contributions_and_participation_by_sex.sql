-- Business question: how different are employer contribution rates, and
-- workplace-pension participation, for women and men in the public and
-- private sectors?
--
-- Contribution rates are medians, as a percentage of qualifying earnings,
-- for 2021-2024. ONS warns that the 2021 editing change breaks comparison
-- with earlier releases, which is why this workbook starts in 2021.
-- Participation here is the percentage of employee jobs, United Kingdom,
-- not the DWP eligible-employee rate for Great Britain.
-- Technique: conditional aggregation to a female-minus-male gap.

WITH contribution AS (
    SELECT
        year,
        sector,
        MAX(CASE WHEN sex = 'Male' THEN value END) AS male_median_pct,
        MAX(CASE WHEN sex = 'Female' THEN value END) AS female_median_pct
    FROM ons_employer_contribution
    WHERE measure_group = 'percent'
    GROUP BY year, sector
),
participation AS (
    SELECT
        year,
        sector,
        MAX(CASE WHEN sex = 'Male' THEN value END) AS male_participation_pct,
        MAX(CASE WHEN sex = 'Female' THEN value END) AS female_participation_pct
    FROM ons_participation_by_sex
    WHERE measure_group = 'percent'
    GROUP BY year, sector
)
SELECT
    contribution.year,
    contribution.sector,
    contribution.male_median_pct,
    contribution.female_median_pct,
    ROUND(contribution.female_median_pct - contribution.male_median_pct, 1) AS contribution_gap_female_minus_male_pp,
    participation.male_participation_pct,
    participation.female_participation_pct,
    ROUND(participation.female_participation_pct - participation.male_participation_pct, 1) AS participation_gap_female_minus_male_pp
FROM contribution
JOIN participation
    ON participation.year = contribution.year
   AND participation.sector = contribution.sector
ORDER BY contribution.sector, contribution.year;
