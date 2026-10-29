-- Business question: how has the stock of people receiving a private pension
-- payment changed since pension freedoms, split by defined benefit or annuity
-- versus defined contribution lump sums?
--
-- HMRC Real Time Information, United Kingdom, inside the DWP workbook.
-- A person can receive both a defined-benefit or annuity payment and a
-- defined-contribution lump sum in the same year, so the product total is
-- larger than the count of individuals. The overlap column measures that.
-- first_time starts in 2016-17. also_employed counts people who received a
-- private pension payment and employment income in the same year.
-- Technique: join of the individual total to the product rows, and LAG.

WITH individuals AS (
    SELECT series, financial_year, individuals AS people
    FROM dwp_pension_income
    WHERE breakdown = 'all'
      AND category = 'Total Individuals'
      AND individuals_status = 'observed'
),
products AS (
    SELECT series, financial_year, category, individuals
    FROM dwp_pension_income
    WHERE breakdown = 'product'
      AND category <> 'Total'
      AND individuals_status = 'observed'
),
product_total AS (
    SELECT series, financial_year, individuals AS product_total
    FROM dwp_pension_income
    WHERE breakdown = 'product'
      AND category = 'Total'
      AND individuals_status = 'observed'
)
SELECT
    products.series,
    products.financial_year,
    products.category,
    products.individuals,
    individuals.people AS individuals_receiving_any_payment,
    product_total.product_total - individuals.people AS product_rows_above_individuals,
    ROUND(100.0 * products.individuals / individuals.people, 1) AS product_rows_per_100_individuals,
    products.individuals - LAG(products.individuals) OVER (
        PARTITION BY products.series, products.category
        ORDER BY products.financial_year
    ) AS yoy_change_in_product_rows
FROM products
JOIN individuals
    ON individuals.series = products.series
   AND individuals.financial_year = products.financial_year
JOIN product_total
    ON product_total.series = products.series
   AND product_total.financial_year = products.financial_year
ORDER BY products.series, products.financial_year, products.category;
