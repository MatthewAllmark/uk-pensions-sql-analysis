"""Structural checks and the data-quality query.

The numbered SQL file is the check a reviewer can read. This module runs it
and also guards the unit conversions: participation is stored as a percentage,
headcounts as people, and workplace saving as pounds.
"""

from __future__ import annotations

import sqlite3
import sys

from pipeline.paths import DB_PATH, SQL_DIR
from pipeline.run_sql import statements

MINIMUM_ROWS = {
    "dwp_participation": 6000,
    "dwp_saving": 400,
    "dwp_median_contribution": 300,
    "dwp_opt_out": 1000,
    "dwp_pension_income": 400,
    "ons_pension_type": 100,
    "ons_participation_by_sex": 50,
    "ons_employer_contribution": 40,
    "fca_first_access": 80,
    "fca_flow": 80,
    "hmrc_personal_pension": 20,
    "hmrc_relief_component": 100,
    "hmrc_tax_relief": 50,
    "hmrc_annual_allowance": 30,
    "hmrc_flexible_payment": 150,
    "source": 4,
}


def run_checks(db_path=DB_PATH) -> list[str]:
    failures: list[str] = []
    if not db_path.exists():
        return [f"Database not found at {db_path}"]
    connection = sqlite3.connect(db_path)
    for table, minimum in MINIMUM_ROWS.items():
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count < minimum:
            failures.append(f"{table} has {count} rows, expected at least {minimum}")

    quality_sql = (SQL_DIR / "01_data_quality_checks.sql").read_text(encoding="utf-8")
    for query in statements(quality_sql):
        cursor = connection.execute(query)
        if cursor.description is None:
            continue
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            if record.get("status") == "FAIL":
                failures.append(
                    f"{record['check_name']} failed (metric={record['metric']}): {record['detail']}"
                )

    # Unit sentinels. These ranges are wide on purpose: they catch a missed
    # Excel percentage or thousands conversion without freezing one publication.
    sentinel = connection.execute(
        """
        SELECT participation_pct
        FROM dwp_participation
        WHERE table_code = '1.1'
          AND population = 'Eligible employees'
          AND sector = 'Public'
          AND year = 2025
        """
    ).fetchone()
    if sentinel is None or not 80 <= sentinel[0] <= 100:
        failures.append(f"Public eligible participation in 2025 was {sentinel}, expected a percentage between 80 and 100")

    saving = connection.execute(
        """
        SELECT amount_gbp
        FROM dwp_saving
        WHERE population = 'Eligible savers'
          AND sector = 'Overall'
          AND year = 2025
          AND component = 'Total saved'
        """
    ).fetchone()
    if saving is None or saving[0] < 100_000_000_000:
        failures.append(f"Overall eligible saving in 2025 was {saving}, expected pounds above £100 billion")

    headcount = connection.execute(
        """
        SELECT participating_employees
        FROM dwp_participation
        WHERE table_code = '1.1'
          AND population = 'Eligible employees'
          AND sector = 'Private'
          AND year = 2025
        """
    ).fetchone()
    if headcount is None or not 5_000_000 <= headcount[0] <= 30_000_000:
        failures.append(f"Private eligible headcount in 2025 was {headcount}, expected people not thousands")

    connection.close()
    return failures


def main() -> None:
    failures = run_checks()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        raise SystemExit(1)
    print("validation passed")


if __name__ == "__main__":
    main()
