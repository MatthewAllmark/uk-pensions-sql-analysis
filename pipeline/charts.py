"""Charts drawn from the SQLite facts. Numbers match the SQL extracts."""

from __future__ import annotations

import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from pipeline.paths import CHART_DIR, DB_PATH

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "semibold",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.color": "#E6E8EB",
        "grid.linewidth": 0.7,
        "axes.axisbelow": True,
    }
)

SECTOR_COLOURS = {"Public": "#1D4E89", "Private": "#C46D32", "Overall": "#1B4332"}
SIZE_COLOURS = {
    "1 to 4": "#8C3A1E",
    "5 to 49": "#C46D32",
    "50 to 249": "#E0A106",
    "250 to 4999": "#2A9D8F",
    "5000+": "#1D4E89",
}
ACCESS_COLOURS = {
    "full_withdrawal": "#9B2226",
    "ufpls": "#E09F3E",
    "annuity": "#1D4E89",
    "drawdown": "#2A9D8F",
}
ACCESS_LABELS = {
    "full_withdrawal": "Full withdrawal",
    "ufpls": "UFPLS",
    "annuity": "Annuity",
    "drawdown": "Drawdown",
}
FAMILY_COLOURS = {
    "Defined benefit": "#1D4E89",
    "Defined contribution, including group personal pensions": "#2A9D8F",
    "No workplace pension": "#D0D5DD",
    "Unknown": "#98A2B3",
}
FAMILY_LABELS = {
    "Defined contribution, including group personal pensions": "Defined contribution, including group pensions",
}


def _footer(figure, text: str) -> None:
    figure.text(0.01, 0.01, text, fontsize=8, color="#52606D")


def _legend(axis, ncol: int) -> None:
    axis.legend(
        frameon=False,
        ncol=ncol,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
    )


def _save(figure, name: str) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(CHART_DIR / name, dpi=140, bbox_inches="tight")
    plt.close(figure)
    print(f"  {name}")


def participation_by_sector(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT year, sector, participation_pct
        FROM dwp_participation
        WHERE table_code = '1.1'
          AND population = 'Eligible employees'
          AND breakdown = 'sector'
        ORDER BY sector, year
        """
    ).fetchall()
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    for sector in ("Public", "Private", "Overall"):
        series = [row for row in rows if row[1] == sector]
        axis.plot(
            [row[0] for row in series],
            [row[2] for row in series],
            label=sector,
            color=SECTOR_COLOURS[sector],
            linewidth=2.2,
        )
    axis.axvline(2012, color="#98A2B3", linestyle="--", linewidth=1)
    axis.set_title("Eligible employees in a workplace pension")
    axis.set_ylabel("Participation (%)")
    axis.set_xlabel("Year")
    axis.set_ylim(30, 100)
    axis.xaxis.get_major_locator().set_params(integer=True)
    _legend(axis, 3)
    _footer(
        figure,
        "DWP estimates from ONS ASHE, Great Britain. Eligible employees are aged 22 to State Pension age and earn at least the trigger. Dashed line: 2012, when automatic enrolment duties began.",
    )
    _save(figure, "01_participation_by_sector.png")


def participation_by_employer_size(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT year, category, participation_pct
        FROM dwp_participation
        WHERE breakdown = 'employer_size'
          AND population = 'Eligible employees'
          AND sector = 'Private'
          AND participation_status = 'observed'
        ORDER BY year
        """
    ).fetchall()
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    for size in ("1 to 4", "5 to 49", "50 to 249", "250 to 4999", "5000+"):
        series = [row for row in rows if row[1] == size]
        axis.plot(
            [row[0] for row in series],
            [row[2] for row in series],
            label=f"{size} employees",
            color=SIZE_COLOURS[size],
            linewidth=2.1,
        )
    axis.axvline(2012, color="#98A2B3", linestyle="--", linewidth=1)
    axis.set_title("Private sector: eligible participation by employer size")
    axis.set_ylabel("Participation (%)")
    axis.set_xlabel("Year")
    axis.set_ylim(0, 100)
    axis.xaxis.get_major_locator().set_params(integer=True)
    _legend(axis, 3)
    _footer(
        figure,
        "DWP estimates from ONS ASHE, Great Britain. Employer size is the number of employees. Dashed line: 2012.",
    )
    _save(figure, "02_private_participation_by_employer_size.png")


def participation_by_age(connection: sqlite3.Connection) -> None:
    bands = ("22 to 25", "36 to 40", "51 to 55", "61 to 65")
    colours = {
        "22 to 25": "#C46D32",
        "36 to 40": "#E0A106",
        "51 to 55": "#2A9D8F",
        "61 to 65": "#1D4E89",
    }
    rows = connection.execute(
        """
        SELECT year, category, participation_pct
        FROM dwp_participation
        WHERE breakdown = 'age_band'
          AND population = 'Eligible employees'
          AND sector = 'Private'
          AND participation_status = 'observed'
        ORDER BY year
        """
    ).fetchall()
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    for band in bands:
        series = [row for row in rows if row[1] == band]
        axis.plot(
            [row[0] for row in series],
            [row[2] for row in series],
            label=band,
            color=colours[band],
            linewidth=2.1,
        )
    axis.axvline(2012, color="#98A2B3", linestyle="--", linewidth=1)
    axis.set_title("Private sector: eligible participation by age")
    axis.set_ylabel("Participation (%)")
    axis.set_xlabel("Year")
    axis.set_ylim(0, 100)
    axis.xaxis.get_major_locator().set_params(integer=True)
    _legend(axis, 4)
    _footer(figure, "DWP estimates from ONS ASHE, Great Britain. Eligible private-sector employees. Dashed line: 2012.")
    _save(figure, "03_private_participation_by_age.png")


def median_contribution_rate(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT year, sector, median_pct_of_pay
        FROM dwp_median_contribution
        WHERE population = 'Eligible savers'
          AND saver_group = 'All'
          AND pct_status = 'observed'
        ORDER BY sector, year
        """
    ).fetchall()
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    for sector in ("Public", "Private"):
        series = [row for row in rows if row[1] == sector]
        axis.plot(
            [row[0] for row in series],
            [row[2] for row in series],
            label=sector,
            color=SECTOR_COLOURS[sector],
            linewidth=2.2,
        )
    axis.axvline(2012, color="#98A2B3", linestyle="--", linewidth=1)
    axis.set_title("Median contribution as a percentage of total pay")
    axis.set_ylabel("Median contribution (% of pay)")
    axis.set_xlabel("Year")
    axis.xaxis.get_major_locator().set_params(integer=True)
    _legend(axis, 2)
    _footer(
        figure,
        "DWP estimates from ONS ASHE, Great Britain, eligible savers. This is total pay, not automatic-enrolment qualifying earnings. Dashed line: 2012.",
    )
    _save(figure, "04_median_contribution_rate.png")


def saving_components(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT year, component, amount_gbp / 1e9
        FROM dwp_saving
        WHERE population = 'Eligible savers'
          AND sector = 'Overall'
          AND component <> 'Total saved'
        ORDER BY year
        """
    ).fetchall()
    years = sorted({row[0] for row in rows})
    components = (
        ("Employer contributions", "#1D4E89"),
        ("Employee contributions", "#2A9D8F"),
        ("Tax relief", "#E0A106"),
    )
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    bottom = [0.0] * len(years)
    index = {year: position for position, year in enumerate(years)}
    for name, colour in components:
        heights = [0.0] * len(years)
        for year, component, value in rows:
            if component == name:
                heights[index[year]] = value
        axis.bar(years, heights, bottom=bottom, label=name, color=colour, width=0.8)
        bottom = [left + added for left, added in zip(bottom, heights)]
    axis.set_title("Workplace pension saving by eligible savers")
    axis.set_ylabel("£ billion, nominal")
    axis.set_xlabel("Year")
    axis.set_xlim(2008.5, 2025.5)
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    _legend(axis, 3)
    _footer(
        figure,
        "DWP estimates from ONS ASHE, Great Britain. Nominal pounds. The workbook displays these amounts in billions; the chart divides the stored pounds by one billion.",
    )
    _save(figure, "05_saving_by_component.png")


def pension_type_mix(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT
            year,
            CASE
                WHEN pension_type = 'Defined benefit' THEN 'Defined benefit'
                WHEN pension_type LIKE 'No pension%' THEN 'No workplace pension'
                WHEN pension_type LIKE 'Unknown%' THEN 'Unknown'
                ELSE 'Defined contribution, including group personal pensions'
            END AS scheme_family,
            SUM(value) AS pct_of_jobs
        FROM ons_pension_type
        WHERE table_name = 'Table 1'
          AND measure_group = 'percent'
        GROUP BY year, scheme_family
        ORDER BY year
        """
    ).fetchall()
    years = sorted({row[0] for row in rows})
    order = (
        "No workplace pension",
        "Unknown",
        "Defined benefit",
        "Defined contribution, including group personal pensions",
    )
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    bottom = [0.0] * len(years)
    index = {year: position for position, year in enumerate(years)}
    for family in order:
        heights = [0.0] * len(years)
        for year, name, value in rows:
            if name == family:
                heights[index[year]] = value
        axis.bar(
            [str(year) for year in years],
            heights,
            bottom=bottom,
            label=FAMILY_LABELS.get(family, family),
            color=FAMILY_COLOURS[family],
            width=0.72,
        )
        bottom = [left + added for left, added in zip(bottom, heights)]
    axis.set_title("Workplace pension type, all employee jobs")
    axis.set_ylabel("Share of employee jobs (%)")
    axis.set_ylim(0, 105)
    _legend(axis, 2)
    _footer(
        figure,
        "ONS ASHE pension summary, United Kingdom. Shares are rounded to whole percentage points and need not sum to 100. Group personal, stakeholder and group SIPP pensions are included with defined contribution.",
    )
    _save(figure, "06_pension_type_mix.png")


def retirement_access_mix(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        WITH annual AS (
            SELECT financial_year, access_method, SUM(plan_count) AS plans
            FROM fca_first_access
            WHERE access_method <> 'total'
            GROUP BY financial_year, access_method
        ),
        totals AS (
            SELECT financial_year, SUM(plan_count) AS total_plans
            FROM fca_first_access
            WHERE access_method = 'total'
            GROUP BY financial_year
        )
        SELECT annual.financial_year, annual.access_method, 100.0 * annual.plans / totals.total_plans
        FROM annual
        JOIN totals ON totals.financial_year = annual.financial_year
        ORDER BY annual.financial_year
        """
    ).fetchall()
    years = sorted({row[0] for row in rows})
    order = ("full_withdrawal", "ufpls", "annuity", "drawdown")
    figure, axis = plt.subplots(figsize=(9.2, 5.2))
    bottom = [0.0] * len(years)
    index = {year: position for position, year in enumerate(years)}
    for method in order:
        heights = [0.0] * len(years)
        for year, name, value in rows:
            if name == method:
                heights[index[year]] = value
        axis.bar(
            years,
            heights,
            bottom=bottom,
            label=ACCESS_LABELS[method],
            color=ACCESS_COLOURS[method],
            width=0.72,
        )
        bottom = [left + added for left, added in zip(bottom, heights)]
    axis.set_title("How contract-based plans were first accessed")
    axis.set_ylabel("Share of plans (%)")
    axis.set_xlabel("Financial year")
    axis.set_ylim(0, 100)
    _legend(axis, 4)
    _footer(
        figure,
        "FCA retirement income market data, April 2018 to March 2026. Plans, not people. Contract-based providers only. Half-years are summed to financial years.",
    )
    _save(figure, "07_retirement_access_mix.png")


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    participation_by_sector(connection)
    participation_by_employer_size(connection)
    participation_by_age(connection)
    median_contribution_rate(connection)
    saving_components(connection)
    pension_type_mix(connection)
    retirement_access_mix(connection)
    connection.close()


if __name__ == "__main__":
    main()
