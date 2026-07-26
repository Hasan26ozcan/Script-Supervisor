.PHONY: install dev test lint format run docker-build docker-up phase5 phase6 clean

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

phase3:
	python experiments/phase3_correction_effectiveness.py

phase4:
	python experiments/phase4_vision_effectiveness.py

phase5:
	python scripts/generate_comparison_pairs.py

phase6:
	python experiments/phase6_calibration.py

phase7:
	python experiments/phase7_routing.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache data
