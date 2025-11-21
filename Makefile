PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install install-dev test

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

test:
	PYTHONPATH=src pytest -q
