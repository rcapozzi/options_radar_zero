# Options Radar Zero — Real-time 0DTE Option Chain Monitoring
# Makefile for development workflow
# Uses uv (https://docs.astral.sh/uv/) for dependency management

.PHONY: install sync test lint format typecheck run poller clean help

## install: Install dependencies (uv sync)
install:
	uv sync

## sync: Sync dependencies
sync: install

## test: Run tests with coverage
test:
	uv run pytest tests/ -v --cov=. --cov-report=term-missing --cov-fail-under=90

## lint: Run ruff linter
lint:
	uv run ruff check .

## format: Format code with ruff
format:
	uv run ruff format .

## typecheck: Run mypy type checker
typecheck:
	uv run mypy .

## run: Start the Dash development server
run:
	uv run python -m options_radar_zero.app

## poller: Run the market data poller with YAML config
poller:
	uv run python -m options_radar_zero.poller.cli --config examples/poller_config.yaml

## clean: Remove build artifacts
clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

## help: Show this help
help:
	@echo "Available targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | column -t -s ':'
