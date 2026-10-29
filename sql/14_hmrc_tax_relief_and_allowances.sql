-- Business question: how large is Income Tax relief on pension contributions,
-- how is the latest year's individual and employer relief split between
-- public-sector and private arrangements, and how many people report annual
-- allowance excesses?
--
-- Units are £ million, as published. Table 6.1/6.2 is a cross-tab: sector
-- and scheme type are alternative slices, not dimensions to sum together.
-- This query keeps one non-overlapping slice at a time, identified by slice.
-- [z] and other markers stay out via value_status = 'observed'.
-- Technique: filter to a single slice, and a running total of reported
-- excess contributions where the self-assessment cell is observed.

WITH relief AS (
    SELECT
        'income_tax_gross_relief_total' AS slice,
        tax_year,
        breakdown AS category,
        value_gbp_million
    FROM hmrc_relief_component
    WHERE income_tax_or_nics = 'Income Tax'
      AND relief_or_charge = 'Gross relief'
      AND breakdown = 'Total'
      AND value_status = 'observed'
    UNION ALL
    SELECT
        'income_tax_by_sector_2024_25',
        tax_year,
        sector_scheme || ' | ' || contribution_type,
        value_gbp_million
    FROM hmrc_tax_relief
    WHERE tax_year = '2024 to 2025'
      AND income_tax_or_nics = 'Income Tax'
      AND tax_rate = 'Total'
      AND scheme_type = 'Total'
      AND sector_scheme <> 'Total'
      AND nics_relief_class = 'Not applicable'
      AND value_status = 'observed'
    UNION ALL
    SELECT
        'income_tax_by_scheme_2024_25',
        tax_year,
        scheme_type || ' | ' || contribution_type,
        value_gbp_million
    FROM hmrc_tax_relief
    WHERE tax_year = '2024 to 2025'
      AND income_tax_or_nics = 'Income Tax'
      AND tax_rate = 'Total'
      AND sector_scheme = 'Total'
      AND scheme_type <> 'Total'
      AND nics_relief_class = 'Not applicable'
      AND value_status = 'observed'
),
allowance AS (
    SELECT
        tax_year,
        individuals_reporting_excess,
        excess_contributions_gbp_million
    FROM hmrc_annual_allowance
    WHERE reporting_method = 'Self assessment'
      AND individuals_status = 'observed'
)
SELECT
    slice,
    tax_year AS period,
    category,
    value_gbp_million,
    NULL AS individuals,
    NULL AS running_excess_gbp_million
FROM relief
UNION ALL
SELECT
    'annual_allowance_self_assessment',
    tax_year,
    'Individuals reporting contributions above the annual allowance',
    excess_contributions_gbp_million,
    individuals_reporting_excess,
    SUM(excess_contributions_gbp_million) OVER (ORDER BY tax_year) AS running_excess_gbp_million
FROM allowance
ORDER BY slice, period, category;
