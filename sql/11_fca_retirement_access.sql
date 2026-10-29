-- Business question: when contract-based pension plans were first accessed,
-- how did the mix of annuities, drawdown, UFPLS and full cash withdrawal
-- change from 2018-19 to 2025-26, and how large was the average plan?
--
-- Counts are plans, not people. Values were published in £000 and are stored
-- in pounds. Half-years are summed to financial years (April to March).
-- The four methods sum to the published total in every year (see check 01).
-- Pre-April 2018 returns were a sample of providers and are not loaded.
-- Trust-based occupational schemes are outside this FCA collection.
-- Technique: aggregation to a year, join back to the total, LAG, a running
-- total of a flow, and RANK.

WITH annual AS (
    SELECT
        financial_year,
        access_method,
        SUM(plan_count) AS plans,
        SUM(value_gbp) AS value_gbp
    FROM fca_first_access
    WHERE count_status = 'observed'
      AND access_method <> 'total'
    GROUP BY financial_year, access_method
),
totals AS (
    SELECT
        financial_year,
        SUM(plan_count) AS total_plans,
        SUM(value_gbp) AS total_value_gbp
    FROM fca_first_access
    WHERE access_method = 'total'
      AND count_status = 'observed'
    GROUP BY financial_year
)
SELECT
    annual.financial_year,
    annual.access_method,
    annual.plans,
    annual.value_gbp,
    ROUND(100.0 * annual.plans / totals.total_plans, 1) AS share_of_plans_pct,
    ROUND(annual.value_gbp / annual.plans, 0) AS pounds_per_plan,
    annual.plans - LAG(annual.plans) OVER (
        PARTITION BY annual.access_method
        ORDER BY annual.financial_year
    ) AS yoy_change_in_plans,
    ROUND(
        100.0 * (
            annual.plans - LAG(annual.plans) OVER (
                PARTITION BY annual.access_method
                ORDER BY annual.financial_year
            )
        ) / NULLIF(
            LAG(annual.plans) OVER (
                PARTITION BY annual.access_method
                ORDER BY annual.financial_year
            ),
            0
        ),
        1
    ) AS yoy_percent,
    SUM(annual.plans) OVER (
        PARTITION BY annual.access_method
        ORDER BY annual.financial_year
    ) AS cumulative_plans_since_2018_19,
    RANK() OVER (
        PARTITION BY annual.financial_year
        ORDER BY annual.plans DESC
    ) AS rank_by_plans,
    totals.total_plans,
    totals.total_value_gbp
FROM annual
JOIN totals ON totals.financial_year = annual.financial_year
ORDER BY annual.financial_year, rank_by_plans;
