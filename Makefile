PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install install-dev test test-cov test-cov-html clean help log

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

test:
	PYTHONPATH=src pytest -q tests

test-cov:
	PYTHONPATH=src pytest tests --cov=src --cov-report=term-missing

test-cov-html:
	PYTHONPATH=src pytest tests --cov=src --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

clean:
	rm -rf .coverage htmlcov/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

log:
	@echo "Usage: make log LOG=artifacts/backtests/<run_name>/run_log.json" && \
	if [ -n "$(LOG)" ]; then \
		PYTHONPATH=src $(PYTHON) -m cli.log_inspect $(LOG); \
	else \
		echo "LOG variable not set"; \
	fi

help:
	@echo "Available targets:"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install dev dependencies"
	@echo "  test           - Run all  tests"
	@echo "  test-cov       - Run tests with coverage report"
	@echo "  test-cov-html  - Generate HTML coverage report"
	@echo "  clean          - Remove coverage artifacts"
