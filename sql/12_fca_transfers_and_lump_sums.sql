-- Business question: are defined-benefit to defined-contribution transfers
-- still falling, and how much cash was taken as a pension commencement lump
-- sum or by fully encashing a plan?
--
-- FCA Tables 17 and 18. Values were published in £000 and are stored in pounds.
-- Full encashment here is every plan fully encashed in the half-year, which
-- is wider than the first-access full withdrawal in query 11.
-- Technique: sum half-years, year-on-year change, running total of transfers.

WITH annual AS (
    SELECT
        financial_year,
        metric,
        SUM(value) AS value
    FROM fca_flow
    WHERE value_status = 'observed'
    GROUP BY financial_year, metric
)
SELECT
    financial_year,
    metric,
    value,
    value - LAG(value) OVER (
        PARTITION BY metric
        ORDER BY financial_year
    ) AS yoy_change,
    ROUND(
        100.0 * (
            value - LAG(value) OVER (
                PARTITION BY metric
                ORDER BY financial_year
            )
        ) / NULLIF(
            LAG(value) OVER (
                PARTITION BY metric
                ORDER BY financial_year
            ),
            0
        ),
        1
    ) AS yoy_percent,
    CASE
        WHEN metric = 'db_dc_transfers' THEN SUM(value) OVER (
            PARTITION BY metric
            ORDER BY financial_year
        )
    END AS cumulative_transfers
FROM annual
ORDER BY metric, financial_year;
