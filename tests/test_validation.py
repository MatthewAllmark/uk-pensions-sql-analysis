"""Row-count, reconciliation and checksum checks against the built database."""

import csv
import hashlib
from pathlib import Path

from pipeline.paths import MANIFEST_PATH, RAW
from pipeline.validate import run_checks


def test_quality_checks_pass():
    failures = run_checks()
    assert failures == []


def test_raw_files_match_manifest():
    assert MANIFEST_PATH.exists(), "data/raw/manifest.csv is missing; run the download step"
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 9
    for row in rows:
        path = RAW / row["path"]
        assert path.exists(), row["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == row["sha256"], row["path"]
        assert int(row["bytes"]) == path.stat().st_size
        assert row["licence"].startswith("Open Government Licence")
        assert row["download_url"].startswith("https://")
