-- Business question: did the typical eligible saver contribute more after
-- automatic enrolment, or did the median fall because many new savers joined
-- at lower contribution rates?
--
-- median_pct_of_pay is the contribution as a percentage of total pay for the
-- median saver. It is not the automatic-enrolment minimum, which is a
-- percentage of qualifying earnings (a band of pay), so the two should not
-- be compared as if they used the same denominator.
-- The statutory minimum on qualifying earnings rose in stages, to 5% from
-- April 2018 and 8% from April 2019. That is policy context, not a column
-- in this table.
-- Technique: LAG, and a self-description of the private-sector path via CASE.

SELECT
    year,
    sector,
    saver_group,
    median_contribution_gbp,
    median_pct_of_pay,
    ROUND(
        median_pct_of_pay - LAG(median_pct_of_pay) OVER (
            PARTITION BY sector, saver_group
            ORDER BY year
        ),
        1
    ) AS yoy_percentage_points,
    ROUND(
        median_contribution_gbp - LAG(median_contribution_gbp) OVER (
            PARTITION BY sector, saver_group
            ORDER BY year
        ),
        0
    ) AS yoy_change_gbp,
    CASE
        WHEN sector = 'Private' AND saver_group = 'All' AND year = 2012 THEN 'staging_underway'
        WHEN sector = 'Private' AND saver_group = 'All' AND year BETWEEN 2013 AND 2017 THEN 'coverage_widened_median_fell'
        WHEN sector = 'Private' AND saver_group = 'All' AND year >= 2018 THEN 'after_minimum_rate_increases'
        ELSE NULL
    END AS private_median_phase
FROM dwp_median_contribution
WHERE population = 'Eligible savers'
  AND gbp_status = 'observed'
  AND pct_status = 'observed'
ORDER BY sector, saver_group, year;
