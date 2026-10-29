-- Business question: are eligible members leaving schemes at the point of
-- enrolment (opt-out) or later (stopping saving), and does that depend on age?
--
-- Source: HMRC Real Time Information inside the DWP publication. United Kingdom.
-- 2025-26 is published only to quarter 3, so quarter_count is not 4 and the
-- mean for that year is not a full-year figure.
-- Technique: average across quarters, then LAG on the annual mean, and RANK
-- of age bands within the latest complete year.

WITH quarterly AS (
    SELECT
        measure,
        breakdown,
        category,
        financial_year,
        quarter,
        rate_pct
    FROM dwp_opt_out
    WHERE rate_status = 'observed'
      AND breakdown IN ('all', 'age_band')
),
annual AS (
    SELECT
        measure,
        breakdown,
        category,
        financial_year,
        COUNT(*) AS quarter_count,
        ROUND(AVG(rate_pct), 2) AS mean_quarterly_rate_pct,
        ROUND(MIN(rate_pct), 2) AS min_quarter_pct,
        ROUND(MAX(rate_pct), 2) AS max_quarter_pct
    FROM quarterly
    GROUP BY measure, breakdown, category, financial_year
),
complete_age AS (
    SELECT financial_year
    FROM annual
    WHERE measure = 'opt_out'
      AND breakdown = 'age_band'
      AND quarter_count = 4
    GROUP BY financial_year
    ORDER BY financial_year DESC
    LIMIT 1
)
SELECT
    annual.measure,
    annual.breakdown,
    annual.category,
    annual.financial_year,
    annual.quarter_count,
    annual.mean_quarterly_rate_pct,
    annual.min_quarter_pct,
    annual.max_quarter_pct,
    ROUND(
        annual.mean_quarterly_rate_pct - LAG(annual.mean_quarterly_rate_pct) OVER (
            PARTITION BY annual.measure, annual.breakdown, annual.category
            ORDER BY annual.financial_year
        ),
        2
    ) AS yoy_percentage_points,
    CASE
        WHEN annual.breakdown = 'age_band'
         AND annual.measure = 'opt_out'
         AND annual.financial_year = (SELECT financial_year FROM complete_age)
            THEN RANK() OVER (
                PARTITION BY annual.measure, annual.breakdown, annual.financial_year
                ORDER BY annual.mean_quarterly_rate_pct DESC
            )
    END AS opt_out_rank_in_latest_full_year
FROM annual
ORDER BY annual.measure, annual.breakdown, annual.category, annual.financial_year;
