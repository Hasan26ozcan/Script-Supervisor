.PHONY: install dev test lint format run docker-build docker-up phase5 phase6 clean

install:
	python -m pip install --upgrade pip
	python -m pip install -e .[dev]

test:
	HARNESS_MOCK_MODE=1 pytest --cov=app --cov-report=term-missing -q

lint:
	ruff check app tests
	mypy app

format:
	ruff format app tests

audit:
	python -m pip_audit --fail-on high

precommit:
	pre-commit install

ci: lint test audit

coverage:
	pytest --cov=app --cov-report=xml --cov-report=term-missing -q

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

phase8:
	python experiments/phase8_vision_routing.py

phase9:
	python training/export_dpo_dataset.py

phase10:
	python training/dpo_train.py --mock --dry-run

phase11:
	python training/migrate_preferences_to_db.py

fake-data:
	python training/generate_fake_preferences.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache data
