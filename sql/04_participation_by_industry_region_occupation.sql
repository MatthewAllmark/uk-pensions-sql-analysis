-- Business question: where is eligible participation still lowest in 2025,
-- once small samples are set aside?
--
-- DWP note 6 marks estimates based on fewer than 500 responses as relatively
-- uncertain. Those cells are kept, with sample_quality = 'high_uncertainty',
-- and are not ranked. Industry labels are the published SIC 2007 text,
-- including the source spelling of accommodation.
-- Occupation labels are not compared across 2009-2025: DWP note 13 records
-- SOC 2000, SOC 2010 and SOC 2020 breaks. Only 2025 is ranked here.
-- Technique: CASE for the quality flag, RANK over the usable subset.

WITH latest AS (
    SELECT
        'industry' AS dimension,
        sector,
        category,
        participation_pct,
        participating_employees,
        sample_size,
        sample_status
    FROM dwp_participation
    WHERE breakdown = 'industry'
      AND population = 'Eligible employees'
      AND sector = 'Private'
      AND year = 2025
      AND participation_status = 'observed'
    UNION ALL
    SELECT
        'region',
        sector,
        category,
        participation_pct,
        participating_employees,
        sample_size,
        sample_status
    FROM dwp_participation
    WHERE breakdown = 'region'
      AND population = 'Eligible employees'
      AND sector = 'Overall'
      AND year = 2025
      AND participation_status = 'observed'
    UNION ALL
    SELECT
        'occupation',
        sector,
        category,
        participation_pct,
        participating_employees,
        sample_size,
        sample_status
    FROM dwp_participation
    WHERE breakdown = 'occupation'
      AND population = 'Eligible employees'
      AND sector = 'Overall'
      AND year = 2025
      AND participation_status = 'observed'
),
flagged AS (
    SELECT
        dimension,
        sector,
        category,
        participation_pct,
        participating_employees,
        sample_size,
        CASE
            WHEN sample_status <> 'observed' OR sample_size IS NULL THEN 'sample_not_published'
            WHEN sample_size < 500 THEN 'high_uncertainty'
            ELSE 'usable'
        END AS sample_quality
    FROM latest
)
SELECT
    dimension,
    sector,
    category,
    participation_pct,
    participating_employees,
    sample_size,
    sample_quality,
    CASE
        WHEN sample_quality = 'usable' THEN RANK() OVER (
            PARTITION BY dimension, sample_quality
            ORDER BY participation_pct
        )
    END AS rank_lowest_participation
FROM flagged
ORDER BY dimension, rank_lowest_participation, category;
