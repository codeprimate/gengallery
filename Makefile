.PHONY: help install-dev build clean format lint typecheck test test-unit test-integration coverage check check-all

help:
	@echo "Targets: install-dev build clean format lint typecheck test test-unit test-integration coverage check check-all"
	@echo "Requires uv: https://docs.astral.sh/uv/"

install-dev:
	uv sync --extra dev

build:
	uv run python -m build

clean:
	rm -rf build dist .pytest_cache htmlcov .coverage
	-find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true

format:
	uv run ruff format src tests/python

lint:
	uv run ruff check src tests/python

typecheck:
	uv run mypy src/gengallery

test: test-unit

test-unit:
	uv run pytest tests/python -m "not integration"

test-integration:
	GENGALLERY_INTEGRATION=1 uv run pytest tests/python -m integration

coverage:
	uv run pytest tests/python --cov=gengallery --cov-report=term-missing -m "not integration"

check: lint typecheck test-unit

check-all: lint typecheck test-unit coverage build
