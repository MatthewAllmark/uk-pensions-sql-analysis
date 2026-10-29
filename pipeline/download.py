"""Download the public workbooks and record a checksum manifest.

Files already present with the checksum in data/raw/manifest.csv are left
in place, so a clone that contains the raw files can rebuild offline. Pass
--refresh to fetch every file again.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import urllib.request
from datetime import date

from pipeline.paths import MANIFEST_PATH, RAW

OGL = "Open Government Licence v3.0"
OGL_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
RETRIEVED = "2026-10-29"

SOURCES = [
    {
        "source_id": "dwp_wpp_2009_2025",
        "publisher": "Department for Work and Pensions",
        "title": "Workplace pension participation and savings trends: 2009 to 2025",
        "publication_url": "https://www.gov.uk/government/statistics/workplace-pension-participation-and-savings-trends-2009-to-2025",
        "download_url": "https://assets.publishing.service.gov.uk/media/6a68b23acc35a9471da4c1cf/workplace-pension-participation-2009-2025.xlsx",
        "licence": OGL,
        "licence_url": OGL_URL,
        "published": "2026-07-30",
        "geography": "Great Britain (ASHE tables); United Kingdom (HMRC RTI tables)",
        "path": "dwp/workplace-pension-participation-2009-2025.xlsx",
        "notes": "Official statistics. ASHE-derived tables cover Great Britain. Opt-out and pension-income tables are HMRC Real Time Information for the UK.",
    },
    {
        "source_id": "ons_ashe_pension_summary",
        "publisher": "Office for National Statistics",
        "title": "Annual Survey of Hours and Earnings: summary of pension results, 2024 provisional and 2021 to 2023 final",
        "publication_url": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/workplacepensions/datasets/summaryofpensionresultsannualsurveyofhoursandearnings",
        "download_url": "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/workplacepensions/datasets/summaryofpensionresultsannualsurveyofhoursandearnings/2024provisionaland2021to2023revised/summaryofpensionresults2024provisionaland2021to2023finalestimates.xlsx",
        "licence": OGL,
        "licence_url": OGL_URL,
        "published": "2026-03-10",
        "geography": "United Kingdom",
        "path": "ons/ashe-pension-summary-2024-provisional.xlsx",
        "notes": "Employee jobs, not people. Contribution-rate estimates from 2021 use an updated editing and imputation method and are not comparable with earlier releases.",
    },
    {
        "source_id": "fca_rim_2025_26",
        "publisher": "Financial Conduct Authority",
        "title": "Retirement income market data 2025/26",
        "publication_url": "https://www.fca.org.uk/data/retirement-income-market-data-2025-26",
        "download_url": "https://www.fca.org.uk/publication/data/retirement-income-underlying-data-2025-26.xlsx",
        "licence": OGL,
        "licence_url": OGL_URL,
        "published": "September 2026",
        "geography": "United Kingdom (contract-based providers)",
        "path": "fca/retirement-income-underlying-data-2025-26.xlsx",
        "notes": "Workbook cover is dated September 2026. Figures are plans, not people. The pipeline uses the April 2018 to March 2026 returns, which cover all regulated providers. Trust-based occupational schemes are out of scope.",
    },
    {
        "source_id": "hmrc_private_pension_statistics",
        "publisher": "HM Revenue and Customs",
        "title": "Private pension statistics",
        "publication_url": "https://www.gov.uk/government/statistics/personal-and-stakeholder-pensions-statistics",
        "download_url": "https://www.gov.uk/government/statistics/personal-and-stakeholder-pensions-statistics",
        "licence": OGL,
        "licence_url": OGL_URL,
        "published": "2026-07-30",
        "geography": "United Kingdom",
        "path": "hmrc/",
        "notes": "Tidy CSV extracts published alongside the HMRC commentary. Values in brackets are HMRC disclosure markers, not numbers.",
        "files": [
            (
                "hmrc/Table_2.csv",
                "https://assets.publishing.service.gov.uk/media/6a673e0df02dfa8e78093902/Table_2.csv",
            ),
            (
                "hmrc/Table_6.csv",
                "https://assets.publishing.service.gov.uk/media/6a673e0d5e87122783093900/Table_6.csv",
            ),
            (
                "hmrc/Table_7.csv",
                "https://assets.publishing.service.gov.uk/media/6a673e0d4ffe54a708aa3f49/Table_7.csv",
            ),
            (
                "hmrc/Table_9.csv",
                "https://assets.publishing.service.gov.uk/media/6a673e0eb9e28a4788aa3f3e/Table_9.csv",
            ),
            (
                "hmrc/Tables_6_1_and_6_2.csv",
                "https://assets.publishing.service.gov.uk/media/6a673e0e5e87122783093901/Tables_6_1_and_6_2.csv",
            ),
            (
                "hmrc/Metadata.csv",
                "https://assets.publishing.service.gov.uk/media/68874ca31e72aed40611af7b/Metadata.csv",
            ),
        ],
    },
]


def sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "uk-pensions-analysis/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        dest.write_bytes(response.read())


def file_list(source: dict) -> list[tuple[str, str]]:
    if "files" in source:
        return source["files"]
    return [(source["path"], source["download_url"])]


def read_manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
        return {row["path"]: row["sha256"] for row in csv.DictReader(handle)}


def write_manifest(rows: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path",
        "sha256",
        "bytes",
        "source_id",
        "publisher",
        "title",
        "publication_url",
        "download_url",
        "licence",
        "licence_url",
        "published",
        "retrieved_on",
    ]
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(refresh: bool = False) -> None:
    previous = read_manifest()
    manifest_rows = []
    for source in SOURCES:
        for relative, url in file_list(source):
            dest = RAW / relative
            known = previous.get(relative)
            if dest.exists() and not refresh and known and sha256(dest) == known:
                print(f"cached {relative}")
            else:
                print(f"download {relative}")
                fetch(url, dest)
            digest = sha256(dest)
            manifest_rows.append(
                {
                    "path": relative,
                    "sha256": digest,
                    "bytes": dest.stat().st_size,
                    "source_id": source["source_id"],
                    "publisher": source["publisher"],
                    "title": source["title"],
                    "publication_url": source["publication_url"],
                    "download_url": url,
                    "licence": source["licence"],
                    "licence_url": source["licence_url"],
                    "published": source["published"],
                    "retrieved_on": RETRIEVED if not refresh else date.today().isoformat(),
                }
            )
    write_manifest(manifest_rows)
    print(f"manifest {MANIFEST_PATH.relative_to(RAW.parent.parent)} ({len(manifest_rows)} files)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download UK pensions open data")
    parser.add_argument("--refresh", action="store_true", help="Re-download every file")
    args = parser.parse_args()
    try:
        main(refresh=args.refresh)
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"download failed: {exc}", file=sys.stderr)
        raise
