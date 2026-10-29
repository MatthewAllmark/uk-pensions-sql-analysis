"""Repository paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
DB_PATH = PROCESSED / "uk_pensions.sqlite"
SCHEMA_PATH = ROOT / "schema.sql"
SQL_DIR = ROOT / "sql"
CSV_DIR = ROOT / "outputs" / "csv"
CHART_DIR = ROOT / "outputs" / "charts"
MANIFEST_PATH = RAW / "manifest.csv"
