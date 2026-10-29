"""Clean the published workbooks and load a SQLite database.

Excel display formats are not the stored units. DWP headcounts use the
format ``#,##0,`` (shown in thousands) and pension saving uses ``0.0,,,``
(shown in billions). The stored cell values are people and pounds. Rates
use Excel's percentage format, so 0.89 is 89%. This loader keeps the stored
units and records a status when a cell is a disclosure marker rather than
a number.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl

from pipeline.download import SOURCES
from pipeline.paths import DB_PATH, RAW, SCHEMA_PATH

DWP_ID = "dwp_wpp_2009_2025"
ONS_ID = "ons_ashe_pension_summary"
FCA_ID = "fca_rim_2025_26"
HMRC_ID = "hmrc_private_pension_statistics"

SECTORS = ("Public", "Private", "Overall")
POPULATIONS = {
    "Eligible Employees": "Eligible employees",
    "Ineligible Employees": "Ineligible employees",
    "All Employees": "All employees",
}
PARTICIPATION_SHEETS = (
    ("1.1", "sector"),
    ("1.2", "employer_size"),
    ("1.3a", "earnings_band"),
    ("1.4", "age_band"),
    ("1.5", "gender"),
    ("1.6", "working_pattern"),
    ("1.7", "industry"),
    ("1.8", "occupation"),
    ("1.9a", "region"),
)
SAVING_COMPONENTS = {
    "Total saved": "Total saved",
    "Employee contributions": "Employee contributions",
    "Employer contributions": "Employer contributions",
    "Tax relief": "Tax relief",
}
MEDIAN_GROUPS = {
    "For the median eligible saver": "All",
    "For the median saver": "All",
    "For the median male eligible saver": "Male",
    "For the median female eligible saver": "Female",
    "For the median male saver": "Male",
    "For the median female saver": "Female",
}
FY_RE = re.compile(r"^20\d{2}-\d{2}$")
QUARTER_RE = re.compile(r"^(20\d{2}-\d{2}) Q([1-4])$")
PERIOD_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4} - "
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}$"
)
MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def clean(value) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").replace("\n", " ").split())
    return text or None


def disclosure(value) -> tuple[float | None, str]:
    """Return (number, status). Status is 'observed' or the published marker."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "missing"
    if isinstance(value, str):
        token = value.strip()
        lowered = token.lower()
        if lowered in {"low", "[low]"}:
            return None, "low"
        if token.startswith("[") or lowered in {"n/a", "na", "..", ".", "*", "**", "^^"}:
            return None, token
        token = token.replace(",", "")
        try:
            return float(token), "observed"
        except ValueError:
            return None, f"unparsed:{token}"
    if isinstance(value, bool):
        return None, "unparsed:bool"
    if isinstance(value, (int, float)):
        return float(value), "observed"
    return None, f"unparsed:{type(value).__name__}"


def as_percent(value) -> tuple[float | None, str]:
    number, status = disclosure(value)
    if status != "observed":
        return None, status
    if number > 1.5:
        raise ValueError(f"Expected an Excel percentage, found {number}")
    return round(number * 100, 2), "observed"


def as_count(value) -> tuple[int | None, str]:
    number, status = disclosure(value)
    if status != "observed":
        return None, status
    return int(round(number)), "observed"


def cell(row, index: int):
    if index < 0 or index >= len(row):
        return None
    return row[index]


def sheet_rows(workbook, name: str) -> list[tuple]:
    worksheet = workbook[name]
    return [tuple(row) for row in worksheet.iter_rows(values_only=True)]


def is_year_run(row, start: int, first: int = 2009, last: int = 2025) -> bool:
    for offset, year in enumerate(range(first, last + 1)):
        value = cell(row, start + offset)
        if isinstance(value, float) and value == int(value):
            value = int(value)
        if value != year:
            return False
    return True


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def insert_sources(connection: sqlite3.Connection) -> None:
    rows = []
    for source in SOURCES:
        rows.append(
            (
                source["source_id"],
                source["publisher"],
                source["title"],
                source["publication_url"],
                source["download_url"],
                source["licence"],
                source["licence_url"],
                source["published"],
                source["geography"],
                source["notes"],
            )
        )
    connection.executemany(
        """
        INSERT INTO source (
            source_id, publisher, title, publication_url, download_url,
            licence, licence_url, published, geography, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.executemany(
        "INSERT INTO sector (sector, sort_order) VALUES (?, ?)",
        [("Public", 1), ("Private", 2), ("Overall", 3)],
    )


def audit(connection: sqlite3.Connection, table: str, source_id: str) -> int:
    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    connection.execute(
        """
        INSERT INTO load_audit (table_name, source_id, row_count, loaded_at)
        VALUES (?, ?, ?, ?)
        """,
        (table, source_id, count, datetime.now().isoformat(timespec="seconds")),
    )
    print(f"  {table}: {count:,} rows")
    return count


def parse_participation_sheet(rows: list[tuple], table_code: str, breakdown: str) -> list[dict]:
    anchors = []
    for row_index, row in enumerate(rows):
        for start in range(1, len(row) - 16):
            if is_year_run(row, start):
                label = clean(cell(row, start - 1))
                anchors.append((row_index, start, label))
    if not anchors:
        raise ValueError(f"Sheet {table_code} has no 2009-2025 year header")

    by_column: dict[int, list[tuple]] = {}
    for anchor in anchors:
        by_column.setdefault(anchor[1], []).append(anchor)

    block_kinds = {kind for _, _, label in anchors if (kind := _block_kind(label))}
    if block_kinds == {"population"}:
        layout = "population"
    elif block_kinds == {"sector"}:
        layout = "sector"
    else:
        raise ValueError(f"Sheet {table_code} mixes block labels: {block_kinds}")

    collected: dict[tuple, dict] = {}
    for start_col, column_anchors in by_column.items():
        header_row = min(anchor[0] for anchor in column_anchors)
        title = _block_title(rows, header_row, start_col - 1)
        measure = _measure_from_title(title, table_code)
        column_population = _population_from_title(title) if layout == "sector" else None
        ordered = sorted(column_anchors)
        for index, (row_index, _, block_label) in enumerate(ordered):
            end = ordered[index + 1][0] if index + 1 < len(ordered) else len(rows)
            for data_index in range(row_index + 1, end):
                category_label = clean(cell(rows[data_index], start_col - 1))
                if category_label is None:
                    continue
                if is_year_run(rows[data_index], start_col):
                    break
                population, sector, category = _participation_key(layout, block_label, category_label, table_code)
                if column_population is not None:
                    population = column_population
                for offset, year in enumerate(range(2009, 2026)):
                    raw = cell(rows[data_index], start_col + offset)
                    key = (population, sector, category, year)
                    bucket = collected.setdefault(key, {})
                    if measure in bucket:
                        raise ValueError(f"{table_code} duplicate {measure} for {key}")
                    bucket[measure] = raw

    parsed = []
    for (population, sector, category, year), measures in collected.items():
        rate, rate_status = (None, "missing")
        employees, employees_status = (None, "missing")
        sample, sample_status = (None, "not_in_source")
        if "rate" in measures:
            rate, rate_status = as_percent(measures["rate"])
            if rate_status == "observed":
                rate = round(rate, 1)
        if "employees" in measures:
            employees, employees_status = as_count(measures["employees"])
        if "sample" in measures:
            sample, sample_status = as_count(measures["sample"])
        parsed.append(
            {
                "table_code": table_code,
                "breakdown": breakdown,
                "population": population,
                "sector": sector,
                "category": category,
                "year": year,
                "participation_pct": rate,
                "participation_status": rate_status,
                "participating_employees": employees,
                "employees_status": employees_status,
                "sample_size": sample,
                "sample_status": sample_status,
            }
        )
    if not parsed:
        raise ValueError(f"Sheet {table_code} produced no participation rows")
    return parsed


def _block_title(rows: list[tuple], header_row: int, label_col: int) -> str:
    for row_index in range(header_row - 1, max(-1, header_row - 6), -1):
        text = clean(cell(rows[row_index], label_col))
        if text and any(token in text.lower() for token in ("participat", "sample", "number of")):
            return text
    raise ValueError(f"No block title above row {header_row}, column {label_col}")


def _measure_from_title(title: str, table_code: str) -> str:
    lowered = title.lower()
    if "sample" in lowered:
        return "sample"
    if "percentage" in lowered:
        return "rate"
    if "number of" in lowered:
        return "employees"
    raise ValueError(f"{table_code}: cannot classify '{title}'")


def _population_from_title(title: str) -> str:
    lowered = title.lower()
    if "all employees" in lowered:
        return "All employees"
    if "eligible" in lowered:
        return "Eligible employees"
    raise ValueError(f"Cannot read population from '{title}'")


def _block_kind(label: str | None) -> str | None:
    if label in POPULATIONS:
        return "population"
    if label in SECTORS:
        return "sector"
    return None


def _participation_key(layout: str, block_label: str | None, category_label: str, table_code: str):
    if layout == "population":
        if block_label not in POPULATIONS:
            raise ValueError(f"{table_code}: unexpected population '{block_label}'")
        if category_label not in SECTORS:
            raise ValueError(f"{table_code}: unexpected sector '{category_label}'")
        return POPULATIONS[block_label], category_label, category_label
    if block_label not in SECTORS:
        raise ValueError(f"{table_code}: unexpected sector block '{block_label}'")
    return "Eligible employees", block_label, category_label


def load_participation(connection: sqlite3.Connection, workbook) -> None:
    rows = []
    for table_code, breakdown in PARTICIPATION_SHEETS:
        parsed = parse_participation_sheet(sheet_rows(workbook, table_code), table_code, breakdown)
        rows.extend(parsed)
        print(f"  parsed {table_code} {breakdown}: {len(parsed):,} cells")
    connection.executemany(
        """
        INSERT INTO dwp_participation (
            source_id, table_code, breakdown, population, sector, category, year,
            geography, underlying_source, participation_pct, participation_status,
            participating_employees, employees_status, sample_size, sample_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Great Britain', 'ONS ASHE', ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                DWP_ID,
                row["table_code"],
                row["breakdown"],
                row["population"],
                row["sector"],
                row["category"],
                row["year"],
                row["participation_pct"],
                row["participation_status"],
                row["participating_employees"],
                row["employees_status"],
                row["sample_size"],
                row["sample_status"],
            )
            for row in rows
        ],
    )


def parse_saving_sheet(rows: list[tuple], population: str) -> tuple[list[dict], list[dict]]:
    sector = None
    mode = None
    amounts = []
    medians: dict[tuple, dict] = {}
    for row in rows:
        marker = clean(cell(row, 17))
        if marker and "Billion" in marker:
            mode = "amount"
        elif marker and marker.startswith("Median contributions (£)"):
            mode = "median_gbp"
        elif marker and "Median" in marker and "%" in marker:
            mode = "median_pct"

        label = clean(cell(row, 0))
        second = cell(row, 1)
        if label in SECTORS and second == 2009:
            sector = label
            continue
        if sector is None or mode is None or label is None:
            continue
        if not is_year_run(row, 1):
            # Data row. A sector header also has a year run, and those are skipped above.
            pass
        if mode == "amount":
            if label not in SAVING_COMPONENTS:
                raise ValueError(f"Unexpected saving component '{label}' on {population}")
            for offset, year in enumerate(range(2009, 2026)):
                number, status = as_count(cell(row, 1 + offset))
                amounts.append(
                    {
                        "population": population,
                        "sector": sector,
                        "year": year,
                        "component": SAVING_COMPONENTS[label],
                        "amount_gbp": number,
                        "amount_status": status,
                    }
                )
        else:
            if label not in MEDIAN_GROUPS:
                raise ValueError(f"Unexpected median row '{label}' on {population}")
            group = MEDIAN_GROUPS[label]
            for offset, year in enumerate(range(2009, 2026)):
                raw = cell(row, 1 + offset)
                key = (population, sector, year, group)
                bucket = medians.setdefault(
                    key,
                    {
                        "population": population,
                        "sector": sector,
                        "year": year,
                        "saver_group": group,
                        "median_contribution_gbp": None,
                        "gbp_status": "missing",
                        "median_pct_of_pay": None,
                        "pct_status": "missing",
                    },
                )
                if mode == "median_gbp":
                    number, status = as_count(raw)
                    bucket["median_contribution_gbp"] = number
                    bucket["gbp_status"] = status
                else:
                    number, status = as_percent(raw)
                    bucket["median_pct_of_pay"] = round(number, 1) if number is not None else None
                    bucket["pct_status"] = status
    if not amounts or not medians:
        raise ValueError(f"Saving sheet for {population} was not parsed")
    return amounts, list(medians.values())


def load_saving(connection: sqlite3.Connection, workbook) -> None:
    amounts = []
    medians = []
    for sheet, population in (("2.1", "Eligible savers"), ("2.2", "All savers")):
        sheet_amounts, sheet_medians = parse_saving_sheet(sheet_rows(workbook, sheet), population)
        amounts.extend(sheet_amounts)
        medians.extend(sheet_medians)
        print(f"  parsed {sheet} {population}: {len(sheet_amounts):,} amounts, {len(sheet_medians):,} medians")
    connection.executemany(
        """
        INSERT INTO dwp_saving (
            source_id, population, sector, year, component, amount_gbp,
            amount_status, geography, underlying_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Great Britain', 'ONS ASHE')
        """,
        [
            (
                DWP_ID,
                row["population"],
                row["sector"],
                row["year"],
                row["component"],
                row["amount_gbp"],
                row["amount_status"],
            )
            for row in amounts
        ],
    )
    connection.executemany(
        """
        INSERT INTO dwp_median_contribution (
            source_id, population, sector, year, saver_group,
            median_contribution_gbp, gbp_status, median_pct_of_pay, pct_status,
            geography, underlying_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Great Britain', 'ONS ASHE')
        """,
        [
            (
                DWP_ID,
                row["population"],
                row["sector"],
                row["year"],
                row["saver_group"],
                row["median_contribution_gbp"],
                row["gbp_status"],
                row["median_pct_of_pay"],
                row["pct_status"],
            )
            for row in medians
        ],
    )


def parse_opt_out(rows: list[tuple], measure: str) -> list[dict]:
    header_index = None
    periods = []
    for index, row in enumerate(rows):
        found = []
        for column, value in enumerate(row):
            text = clean(value)
            if text and QUARTER_RE.match(text):
                found.append((column, text))
        if len(found) > 10:
            header_index = index
            periods = found
            break
    if header_index is None:
        raise ValueError(f"No quarterly header for {measure}")

    section = "all"
    section_names = {
        "By Age Band": "age_band",
        "By Gender": "gender",
        "By Earnings Band": "earnings_band",
    }
    parsed = []
    for row in rows[header_index + 1 :]:
        label = clean(cell(row, 0))
        if label is None:
            continue
        if label in section_names:
            section = section_names[label]
            continue
        breakdown = "all" if label == "All" else section
        category = "All" if label == "All" else label
        for column, period in periods:
            financial_year, quarter = QUARTER_RE.match(period).groups()
            number, status = as_percent(cell(row, column))
            parsed.append(
                {
                    "measure": measure,
                    "breakdown": breakdown,
                    "category": category,
                    "financial_year": financial_year,
                    "quarter": int(quarter),
                    "rate_pct": number,
                    "rate_status": status,
                }
            )
    if not parsed:
        raise ValueError(f"No opt-out rows for {measure}")
    return parsed


def load_opt_out(connection: sqlite3.Connection, workbook) -> None:
    rows = []
    for sheet, measure in (("3.1a", "opt_out"), ("3.1b", "stopped_saving")):
        parsed = parse_opt_out(sheet_rows(workbook, sheet), measure)
        rows.extend(parsed)
        print(f"  parsed {sheet} {measure}: {len(parsed):,}")
    connection.executemany(
        """
        INSERT INTO dwp_opt_out (
            source_id, measure, breakdown, category, financial_year, quarter,
            rate_pct, rate_status, geography, underlying_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'United Kingdom', 'HMRC RTI')
        """,
        [
            (
                DWP_ID,
                row["measure"],
                row["breakdown"],
                row["category"],
                row["financial_year"],
                row["quarter"],
                row["rate_pct"],
                row["rate_status"],
            )
            for row in rows
        ],
    )


def parse_pension_income(rows: list[tuple], series: str) -> list[dict]:
    headers = []
    for index, row in enumerate(rows):
        # Keep the contiguous financial-year run that starts in column B.
        # Later columns on the same row are a single-year age-by-sex snapshot.
        first = clean(cell(row, 1))
        if not first or not FY_RE.match(first):
            continue
        years = []
        column = 1
        while True:
            text = clean(cell(row, column))
            if not text or not FY_RE.match(text):
                break
            years.append((column, text))
            column += 1
        if len(years) >= 5:
            headers.append((index, clean(cell(row, 0)), years))
    if not headers:
        raise ValueError(f"No financial-year header for {series}")

    section_for = {
        None: "all",
        "Product type": "product",
        "Age Band": "age_band",
        "Gender": "gender",
    }
    parsed = []
    for position, (row_index, section_label, years) in enumerate(headers):
        if section_label not in section_for:
            raise ValueError(f"{series}: unexpected section '{section_label}'")
        breakdown = section_for[section_label]
        end = headers[position + 1][0] if position + 1 < len(headers) else len(rows)
        for data_index in range(row_index + 1, end):
            category = clean(cell(rows[data_index], 0))
            if category is None or category in section_for:
                continue
            for column, financial_year in years:
                number, status = as_count(cell(rows[data_index], column))
                parsed.append(
                    {
                        "series": series,
                        "financial_year": financial_year,
                        "breakdown": breakdown,
                        "category": category,
                        "individuals": number,
                        "individuals_status": status,
                    }
                )
    if not parsed:
        raise ValueError(f"No pension-income rows for {series}")
    return parsed


def load_pension_income(connection: sqlite3.Connection, workbook) -> None:
    rows = []
    for sheet, series in (
        ("4.1", "all_recipients"),
        ("4.2", "first_time"),
        ("4.3", "also_employed"),
    ):
        parsed = parse_pension_income(sheet_rows(workbook, sheet), series)
        rows.extend(parsed)
        print(f"  parsed {sheet} {series}: {len(parsed):,}")
    connection.executemany(
        """
        INSERT INTO dwp_pension_income (
            source_id, series, financial_year, breakdown, category,
            individuals, individuals_status, geography, underlying_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'United Kingdom', 'HMRC RTI')
        """,
        [
            (
                DWP_ID,
                row["series"],
                row["financial_year"],
                row["breakdown"],
                row["category"],
                row["individuals"],
                row["individuals_status"],
            )
            for row in rows
        ],
    )


def measure_group(measure: str) -> str:
    lowered = measure.lower()
    if "percentage" in lowered or lowered.startswith("median"):
        return "percent"
    if "thousand" in lowered:
        return "jobs_thousands"
    if lowered == "count":
        return "sample_count"
    return "other"


def short_population(title: str) -> str:
    lowered = title.lower()
    if "with a workplace pension" in lowered:
        return "Employees with a workplace pension"
    if "all employee" in lowered:
        return "All employees"
    return clean(title) or "Unspecified"


def _year_number(value) -> int | None:
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, int) and 1990 <= value <= 2035:
        return value
    text = clean(value)
    if text and text.isdigit() and 1990 <= int(text) <= 2035:
        return int(text)
    return None


def parse_ons_grid(rows: list[tuple]) -> tuple[str, list[str], list[tuple]]:
    title = clean(rows[0][0]) or ""
    header_index = None
    for index, row in enumerate(rows):
        years = [year for value in row if (year := _year_number(value)) in (2021, 2022, 2023, 2024)]
        if len(years) >= 3:
            header_index = index
            break
    if header_index is None:
        raise ValueError(f"No year header in ONS sheet '{title}'")
    header = rows[header_index]
    year_columns = [(index, year) for index, value in enumerate(header) if (year := _year_number(value)) in (2021, 2022, 2023, 2024)]
    dimension_indexes = list(range(year_columns[0][0]))
    dimension_names = [clean(header[index]) or f"dimension_{index}" for index in dimension_indexes]
    records = []
    for row in rows[header_index + 1 :]:
        dimensions = [clean(cell(row, index)) for index in dimension_indexes]
        if not any(dimensions):
            continue
        for column, year in year_columns:
            number, status = disclosure(cell(row, column))
            if status != "observed":
                raise ValueError(f"ONS {title} {dimensions} {year} is {status}")
            records.append((dimensions, year, number))
    return title, dimension_names, records


def load_ons(connection: sqlite3.Connection, workbook) -> None:
    title, names, records = parse_ons_grid(sheet_rows(workbook, "Table 1"))
    title2, names2, records2 = parse_ons_grid(sheet_rows(workbook, "Table 2"))
    if names[:2] != ["Measure", "Pension type"] or names2[:2] != ["Measure", "Pension type"]:
        raise ValueError(f"Unexpected ONS pension-type headers: {names} / {names2}")
    pension_rows = []
    for table_name, table_title, table_records in (
        ("Table 1", title, records),
        ("Table 2", title2, records2),
    ):
        for dimensions, year, value in table_records:
            pension_rows.append(
                (
                    ONS_ID,
                    table_name,
                    short_population(table_title),
                    dimensions[0],
                    measure_group(dimensions[0]),
                    dimensions[1],
                    year,
                    value,
                    "United Kingdom",
                )
            )
    connection.executemany(
        """
        INSERT INTO ons_pension_type (
            source_id, table_name, population, measure, measure_group,
            pension_type, year, value, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        pension_rows,
    )

    for sheet, table in (
        ("Table 3", "ons_participation_by_sex"),
        ("Table 4", "ons_employer_contribution"),
    ):
        title, names, records = parse_ons_grid(sheet_rows(workbook, sheet))
        if names[:3] != ["Measure", "Sector", "Sex"]:
            raise ValueError(f"{sheet} headers {names}")
        connection.executemany(
            f"""
            INSERT INTO {table} (
                source_id, measure, measure_group, sector, sex, year, value, geography
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'United Kingdom')
            """,
            [
                (ONS_ID, dimensions[0], measure_group(dimensions[0]), dimensions[1], dimensions[2], year, value)
                for dimensions, year, value in records
            ],
        )
        print(f"  parsed {sheet}: {len(records):,}")


def parse_half_year(label: str) -> tuple[str, str, str]:
    start_text, end_text = label.split(" - ")
    start_month, start_year = start_text.split()
    end_month, end_year = end_text.split()
    start = date(int(start_year), MONTHS[start_month], 1)
    end_month_number = MONTHS[end_month]
    end_year_number = int(end_year)
    if end_month_number == 12:
        end = date(end_year_number, 12, 31)
    else:
        end = date(end_year_number, end_month_number + 1, 1) - timedelta(days=1)
    fy_start = start.year if start.month >= 4 else start.year - 1
    financial_year = f"{fy_start}-{str(fy_start + 1)[-2:]}"
    return start.isoformat(), end.isoformat(), financial_year


def access_method(label: str) -> str | None:
    lowered = label.lower()
    if lowered.startswith("total pots"):
        return "total"
    if lowered.startswith("annuit"):
        return "annuity"
    if lowered.startswith("new drawdown"):
        return "drawdown"
    if lowered.startswith("pots where first"):
        return "ufpls"
    if lowered.startswith("full cash"):
        return "full_withdrawal"
    return None


def period_columns(row) -> list[tuple[int, str]]:
    found = []
    for index, value in enumerate(row):
        text = clean(value)
        if text and PERIOD_RE.match(text):
            found.append((index, text))
    return found


def load_fca(connection: sqlite3.Connection, workbook) -> None:
    rows = sheet_rows(workbook, "2018-26 Data Tables")
    table_starts = []
    for index, row in enumerate(rows):
        label = clean(cell(row, 1))
        if label and label.startswith("Table "):
            table_starts.append((index, label))
    bounds = {label.split(":")[0].strip(): (index, table_starts[position + 1][0] if position + 1 < len(table_starts) else len(rows)) for position, (index, label) in enumerate(table_starts)}

    start, end = bounds["Table 1"]
    header = next(row for row in rows[start:end] if len(period_columns(row)) >= 8)
    periods = period_columns(header)
    subhead = rows[rows.index(header) + 1]
    first_col = periods[0][0]
    if clean(cell(subhead, first_col)) != "Number" or "%" not in (clean(cell(subhead, first_col + 3)) or ""):
        raise ValueError("FCA Table 1 sub-headers are not Number / value / firms / share")

    access_rows = []
    for row in rows[start:end]:
        label = clean(cell(row, 1))
        if not label:
            continue
        method = access_method(label)
        if method is None:
            continue
        for column, period in periods:
            count, count_status = as_count(cell(row, column))
            value_number, value_status = disclosure(cell(row, column + 1))
            firms, _ = as_count(cell(row, column + 2))
            share, share_status = disclosure(cell(row, column + 3))
            value_gbp = round(value_number * 1000, 2) if value_status == "observed" else None
            share_pct = round(share * 100, 2) if share_status == "observed" else None
            if share_status == "observed" and share > 1.5:
                raise ValueError(f"FCA share {share} is not a proportion")
            period_start, period_end, financial_year = parse_half_year(period)
            access_rows.append(
                (
                    FCA_ID,
                    period,
                    period_start,
                    period_end,
                    financial_year,
                    method,
                    count,
                    value_gbp,
                    firms,
                    share_pct,
                    count_status,
                    value_status if value_status == "observed" else value_status,
                    "United Kingdom",
                )
            )
    connection.executemany(
        """
        INSERT INTO fca_first_access (
            source_id, period_label, period_start, period_end, financial_year,
            access_method, plan_count, value_gbp, firm_count, share_pct,
            count_status, value_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        access_rows,
    )
    print(f"  parsed FCA Table 1: {len(access_rows):,}")

    flow_specs = (
        ("Table 17", "Number of DB-DC transfers received", "db_dc_transfers", 1),
        ("Table 17", "Number of firms that received DB-DC transfers", "db_dc_firms", 1),
        ("Table 18", "Value withdrawn via PCLS", "pcls_gbp", 1000),
        ("Table 18", "Value withdrawn by all plans fully encashed", "full_encashment_gbp", 1000),
        ("Table 18", "Total number of plans fully encashed", "full_encashment_plans", 1),
    )
    flow_rows = []
    for table_name, label_prefix, metric, scale in flow_specs:
        start, end = bounds[table_name]
        block = rows[start:end]
        header = next(row for row in block if period_columns(row))
        periods = period_columns(header)
        data = next(row for row in block if (clean(cell(row, 1)) or "").startswith(label_prefix))
        for column, period in periods:
            number, status = disclosure(cell(data, column))
            value = round(number * scale, 2) if status == "observed" else None
            period_start, period_end, financial_year = parse_half_year(period)
            flow_rows.append(
                (FCA_ID, metric, period, period_start, period_end, financial_year, value, status, "United Kingdom")
            )
    connection.executemany(
        """
        INSERT INTO fca_flow (
            source_id, metric, period_label, period_start, period_end,
            financial_year, value, value_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        flow_rows,
    )
    print(f"  parsed FCA Tables 17-18: {len(flow_rows):,}")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{clean(key): clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def load_hmrc(connection: sqlite3.Connection) -> None:
    folder = RAW / "hmrc"
    personal = []
    for row in read_csv(folder / "Table_2.csv"):
        members, members_status = disclosure(row["number_of_members"])
        individuals, individuals_status = disclosure(row["number_of_individuals"])
        contributions, contributions_status = disclosure(row["value_of_contributions"])
        personal.append(
            (
                HMRC_ID,
                row["tax_year"],
                row["employment_status"],
                members,
                members_status,
                individuals,
                individuals_status,
                contributions,
                contributions_status,
                "United Kingdom",
            )
        )
    connection.executemany(
        """
        INSERT INTO hmrc_personal_pension (
            source_id, tax_year, employment_status, number_of_members, members_status,
            number_of_individuals, individuals_status, contributions_gbp_million,
            contributions_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        personal,
    )

    components = []
    for row in read_csv(folder / "Table_6.csv"):
        value, status = disclosure(row["value"])
        components.append(
            (
                HMRC_ID,
                row["tax_year"],
                row["income_tax_nics"],
                row["relief_charge"],
                row["breakdown"],
                row["nics_relief_class"],
                value,
                status,
                "United Kingdom",
            )
        )
    connection.executemany(
        """
        INSERT INTO hmrc_relief_component (
            source_id, tax_year, income_tax_or_nics, relief_or_charge, breakdown,
            nics_relief_class, value_gbp_million, value_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        components,
    )

    relief = []
    for row in read_csv(folder / "Tables_6_1_and_6_2.csv"):
        value, status = disclosure(row["value_of_relief"])
        relief.append(
            (
                HMRC_ID,
                row["tax_year"],
                row["income_tax_nics"],
                row["contribution_type"],
                row["nics_relief_class"],
                row["sector_scheme"],
                row["scheme_type"],
                row["tax_rate"],
                value,
                status,
                "United Kingdom",
            )
        )
    connection.executemany(
        """
        INSERT INTO hmrc_tax_relief (
            source_id, tax_year, income_tax_or_nics, contribution_type, nics_relief_class,
            sector_scheme, scheme_type, tax_rate, value_gbp_million, value_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        relief,
    )

    allowances = []
    for row in read_csv(folder / "Table_7.csv"):
        allowance, allowance_status = disclosure(row["allowance_value"])
        charges, charges_status = disclosure(row["number_of_charges"])
        charge_value, charge_value_status = disclosure(row["value_of_charges"])
        individuals, individuals_status = disclosure(row["individuals_reporting_excess_contributions"])
        excess, excess_status = disclosure(row["value_of_excess_contributions"])
        allowances.append(
            (
                HMRC_ID,
                row["tax_year"],
                row["reporting_method"],
                allowance,
                allowance_status,
                charges,
                charges_status,
                charge_value,
                charge_value_status,
                individuals,
                individuals_status,
                excess,
                excess_status,
                "United Kingdom",
            )
        )
    connection.executemany(
        """
        INSERT INTO hmrc_annual_allowance (
            source_id, tax_year, reporting_method, allowance_gbp, allowance_status,
            number_of_charges, charges_status, value_of_charges_gbp_million,
            value_of_charges_status, individuals_reporting_excess, individuals_status,
            excess_contributions_gbp_million, excess_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        allowances,
    )

    payments = []
    for row in read_csv(folder / "Table_9.csv"):
        number, number_status = disclosure(row["number_of_payments"])
        individuals, individuals_status = disclosure(row["number_of_individuals"])
        value, value_status = disclosure(row["value_of_payments"])
        payments.append(
            (
                HMRC_ID,
                row["year_type"],
                row["year"],
                row["quarter"],
                row["age"],
                row["gender"],
                number,
                number_status,
                individuals,
                individuals_status,
                value,
                value_status,
                "United Kingdom",
            )
        )
    connection.executemany(
        """
        INSERT INTO hmrc_flexible_payment (
            source_id, year_type, year_label, quarter, age, gender, number_of_payments,
            payments_status, number_of_individuals, individuals_status,
            value_gbp_million, value_status, geography
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payments,
    )


def main() -> None:
    print("building", DB_PATH)
    connection = connect()
    insert_sources(connection)
    dwp = openpyxl.load_workbook(RAW / "dwp" / "workplace-pension-participation-2009-2025.xlsx", read_only=True, data_only=True)
    ons = openpyxl.load_workbook(RAW / "ons" / "ashe-pension-summary-2024-provisional.xlsx", read_only=True, data_only=True)
    fca = openpyxl.load_workbook(RAW / "fca" / "retirement-income-underlying-data-2025-26.xlsx", read_only=True, data_only=True)
    try:
        load_participation(connection, dwp)
        load_saving(connection, dwp)
        load_opt_out(connection, dwp)
        load_pension_income(connection, dwp)
        load_ons(connection, ons)
        load_fca(connection, fca)
        load_hmrc(connection)
    finally:
        dwp.close()
        ons.close()
        fca.close()

    for table, source_id in (
        ("dwp_participation", DWP_ID),
        ("dwp_saving", DWP_ID),
        ("dwp_median_contribution", DWP_ID),
        ("dwp_opt_out", DWP_ID),
        ("dwp_pension_income", DWP_ID),
        ("ons_pension_type", ONS_ID),
        ("ons_participation_by_sex", ONS_ID),
        ("ons_employer_contribution", ONS_ID),
        ("fca_first_access", FCA_ID),
        ("fca_flow", FCA_ID),
        ("hmrc_personal_pension", HMRC_ID),
        ("hmrc_relief_component", HMRC_ID),
        ("hmrc_tax_relief", HMRC_ID),
        ("hmrc_annual_allowance", HMRC_ID),
        ("hmrc_flexible_payment", HMRC_ID),
    ):
        audit(connection, table, source_id)
    connection.commit()
    connection.close()


if __name__ == "__main__":
    main()
