"""Download, load, query, chart and validate in one step."""

from pipeline.charts import main as charts
from pipeline.download import main as download
from pipeline.load import main as load
from pipeline.run_sql import main as run_sql
from pipeline.validate import main as validate


def main() -> None:
    download()
    load()
    run_sql()
    charts()
    validate()


if __name__ == "__main__":
    main()
