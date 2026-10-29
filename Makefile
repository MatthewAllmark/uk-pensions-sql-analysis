PYTHON ?= python3

.PHONY: all download load query charts test clean

all: download load query charts test

download:
	$(PYTHON) -m pipeline.download

load:
	$(PYTHON) -m pipeline.load

query:
	$(PYTHON) -m pipeline.run_sql

charts:
	$(PYTHON) -m pipeline.charts

test:
	$(PYTHON) -m pytest -q tests

clean:
	rm -rf data/processed/*.sqlite outputs/csv outputs/charts
	mkdir -p data/processed outputs/csv outputs/charts
