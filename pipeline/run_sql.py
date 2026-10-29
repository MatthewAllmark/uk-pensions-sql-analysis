"""Run every file in sql/ and write the result of each to outputs/csv."""

from __future__ import annotations

import csv
import sqlite3

from pipeline.paths import CSV_DIR, DB_PATH, SQL_DIR


def statements(text: str) -> list[str]:
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        kept.append(line)
    return [chunk.strip() for chunk in "\n".join(kept).split(";") if chunk.strip()]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found at {DB_PATH}. Run python -m pipeline.load first.")
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    for path in sorted(SQL_DIR.glob("*.sql")):
        queries = statements(path.read_text(encoding="utf-8"))
        if not queries:
            raise SystemExit(f"{path.name} has no SQL")
        result = None
        for query in queries:
            cursor = connection.execute(query)
            if cursor.description is not None:
                result = (cursor.description, cursor.fetchall())
        if result is None:
            raise SystemExit(f"{path.name} did not return a result set")
        description, rows = result
        destination = CSV_DIR / f"{path.stem}.csv"
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([column[0] for column in description])
            writer.writerows(rows)
        print(f"  {destination.name}: {len(rows):,} rows")
    connection.close()


if __name__ == "__main__":
    main()
