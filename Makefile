.PHONY: install dev test lint format run docker-build docker-up clean

install:
	pip install -e ".[dev]"

test:
	HARNESS_MOCK_MODE=1 pytest --cov=app --cov-report=term-missing -q

lint:
	ruff check app tests
	mypy app

format:
	ruff check --fix app tests
	ruff format app tests

run:
	HARNESS_MOCK_MODE=1 uvicorn app.main:app --reload

docker-build:
	docker compose build

docker-up:
	docker compose --profile default up

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache data
