-- UK workplace pensions analysis
-- Physical tables are facts, each attributed to a publication in `source`.
-- Sector labels on the DWP tables are constrained by `sector`.
-- Analytical joins (year, sector, category) are not foreign keys: the
-- publications do not share a single coding frame.

PRAGMA foreign_keys = ON;

CREATE TABLE source (
    source_id TEXT PRIMARY KEY,
    publisher TEXT NOT NULL,
    title TEXT NOT NULL,
    publication_url TEXT NOT NULL,
    download_url TEXT NOT NULL,
    licence TEXT NOT NULL,
    licence_url TEXT NOT NULL,
    published TEXT NOT NULL,
    geography TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE sector (
    sector TEXT PRIMARY KEY,
    sort_order INTEGER NOT NULL
);

CREATE TABLE dwp_participation (
    participation_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    table_code TEXT NOT NULL,
    breakdown TEXT NOT NULL,
    population TEXT NOT NULL,
    sector TEXT NOT NULL REFERENCES sector (sector),
    category TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2035),
    geography TEXT NOT NULL,
    underlying_source TEXT NOT NULL,
    participation_pct REAL CHECK (
        participation_pct IS NULL
        OR (participation_pct >= 0 AND participation_pct <= 100)
    ),
    participation_status TEXT NOT NULL,
    participating_employees INTEGER CHECK (
        participating_employees IS NULL OR participating_employees >= 0
    ),
    employees_status TEXT NOT NULL,
    sample_size INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
    sample_status TEXT NOT NULL,
    UNIQUE (table_code, population, sector, category, year)
);

CREATE TABLE dwp_saving (
    saving_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    population TEXT NOT NULL,
    sector TEXT NOT NULL REFERENCES sector (sector),
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2035),
    component TEXT NOT NULL,
    amount_gbp INTEGER CHECK (amount_gbp IS NULL OR amount_gbp >= 0),
    amount_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    underlying_source TEXT NOT NULL,
    UNIQUE (population, sector, year, component)
);

CREATE TABLE dwp_median_contribution (
    median_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    population TEXT NOT NULL,
    sector TEXT NOT NULL REFERENCES sector (sector),
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2035),
    saver_group TEXT NOT NULL,
    median_contribution_gbp REAL CHECK (
        median_contribution_gbp IS NULL OR median_contribution_gbp >= 0
    ),
    gbp_status TEXT NOT NULL,
    median_pct_of_pay REAL CHECK (
        median_pct_of_pay IS NULL
        OR (median_pct_of_pay >= 0 AND median_pct_of_pay <= 100)
    ),
    pct_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    underlying_source TEXT NOT NULL,
    UNIQUE (population, sector, year, saver_group)
);

CREATE TABLE dwp_opt_out (
    opt_out_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    measure TEXT NOT NULL CHECK (measure IN ('opt_out', 'stopped_saving')),
    breakdown TEXT NOT NULL,
    category TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    rate_pct REAL CHECK (rate_pct IS NULL OR (rate_pct >= 0 AND rate_pct <= 100)),
    rate_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    underlying_source TEXT NOT NULL,
    UNIQUE (measure, breakdown, category, financial_year, quarter)
);

CREATE TABLE dwp_pension_income (
    pension_income_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    series TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    breakdown TEXT NOT NULL,
    category TEXT NOT NULL,
    individuals INTEGER CHECK (individuals IS NULL OR individuals >= 0),
    individuals_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    underlying_source TEXT NOT NULL,
    UNIQUE (series, financial_year, breakdown, category)
);

CREATE TABLE ons_pension_type (
    pension_type_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    table_name TEXT NOT NULL,
    population TEXT NOT NULL,
    measure TEXT NOT NULL,
    measure_group TEXT NOT NULL,
    pension_type TEXT NOT NULL,
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (table_name, measure, pension_type, year)
);

CREATE TABLE ons_participation_by_sex (
    participation_sex_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    measure TEXT NOT NULL,
    measure_group TEXT NOT NULL,
    sector TEXT NOT NULL,
    sex TEXT NOT NULL,
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (measure, sector, sex, year)
);

CREATE TABLE ons_employer_contribution (
    contribution_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    measure TEXT NOT NULL,
    measure_group TEXT NOT NULL,
    sector TEXT NOT NULL,
    sex TEXT NOT NULL,
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (measure, sector, sex, year)
);

CREATE TABLE fca_first_access (
    first_access_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    period_label TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    access_method TEXT NOT NULL,
    plan_count INTEGER,
    value_gbp REAL,
    firm_count INTEGER,
    share_pct REAL,
    count_status TEXT NOT NULL,
    value_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (period_label, access_method)
);

CREATE TABLE fca_flow (
    flow_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    metric TEXT NOT NULL,
    period_label TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    value REAL,
    value_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (metric, period_label)
);

CREATE TABLE hmrc_personal_pension (
    personal_pension_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    tax_year TEXT NOT NULL,
    employment_status TEXT NOT NULL,
    number_of_members REAL,
    members_status TEXT NOT NULL,
    number_of_individuals REAL,
    individuals_status TEXT NOT NULL,
    contributions_gbp_million REAL,
    contributions_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (tax_year, employment_status)
);

CREATE TABLE hmrc_relief_component (
    relief_component_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    tax_year TEXT NOT NULL,
    income_tax_or_nics TEXT NOT NULL,
    relief_or_charge TEXT NOT NULL,
    breakdown TEXT NOT NULL,
    nics_relief_class TEXT NOT NULL,
    value_gbp_million REAL,
    value_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (
        tax_year,
        income_tax_or_nics,
        relief_or_charge,
        breakdown,
        nics_relief_class
    )
);

CREATE TABLE hmrc_tax_relief (
    tax_relief_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    tax_year TEXT NOT NULL,
    income_tax_or_nics TEXT NOT NULL,
    contribution_type TEXT NOT NULL,
    nics_relief_class TEXT NOT NULL,
    sector_scheme TEXT NOT NULL,
    scheme_type TEXT NOT NULL,
    tax_rate TEXT NOT NULL,
    value_gbp_million REAL,
    value_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (
        tax_year,
        income_tax_or_nics,
        contribution_type,
        nics_relief_class,
        sector_scheme,
        scheme_type,
        tax_rate
    )
);

CREATE TABLE hmrc_annual_allowance (
    annual_allowance_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    tax_year TEXT NOT NULL,
    reporting_method TEXT NOT NULL,
    allowance_gbp REAL,
    allowance_status TEXT NOT NULL,
    number_of_charges REAL,
    charges_status TEXT NOT NULL,
    value_of_charges_gbp_million REAL,
    value_of_charges_status TEXT NOT NULL,
    individuals_reporting_excess REAL,
    individuals_status TEXT NOT NULL,
    excess_contributions_gbp_million REAL,
    excess_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (tax_year, reporting_method)
);

CREATE TABLE hmrc_flexible_payment (
    flexible_payment_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    year_type TEXT NOT NULL,
    year_label TEXT NOT NULL,
    quarter TEXT NOT NULL,
    age TEXT NOT NULL,
    gender TEXT NOT NULL,
    number_of_payments REAL,
    payments_status TEXT NOT NULL,
    number_of_individuals REAL,
    individuals_status TEXT NOT NULL,
    value_gbp_million REAL,
    value_status TEXT NOT NULL,
    geography TEXT NOT NULL,
    UNIQUE (year_type, year_label, quarter, age, gender)
);

CREATE TABLE load_audit (
    table_name TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    loaded_at TEXT NOT NULL
);

CREATE INDEX idx_participation_lookup
    ON dwp_participation (breakdown, population, sector, year);

CREATE INDEX idx_saving_lookup
    ON dwp_saving (population, sector, year);

CREATE INDEX idx_opt_out_lookup
    ON dwp_opt_out (measure, breakdown, financial_year);

CREATE INDEX idx_fca_access_year
    ON fca_first_access (financial_year, access_method);

CREATE INDEX idx_pension_income_series
    ON dwp_pension_income (series, breakdown, financial_year);
