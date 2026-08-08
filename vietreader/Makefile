.PHONY: install test lint typecheck run eval

VENV := .venv
ifeq ($(OS),Windows_NT)
	PY := $(VENV)/Scripts/python.exe
else
	PY := $(VENV)/bin/python
endif

install:
	python -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	$(PY) --version

test:
	$(PY) -m pytest -q --cov=vietreader --cov-report=term-missing

lint:
	$(PY) -m ruff check src tests

typecheck:
	$(PY) -m mypy src/vietreader/core

run:
	$(PY) -m uvicorn vietreader.api.app:app --reload --host 0.0.0.0 --port 8000

eval:
	$(PY) evals/run_eval.py
