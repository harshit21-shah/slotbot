.PHONY: install run migrate seed-clinic tunnel simulate bench lint typecheck test clean

install:
	pip install -e ".[dev]"

run:
	uvicorn services.api.app:app --reload --host 0.0.0.0 --port 8000

migrate:
	python -c "import asyncio; from services.db.database import init_db; asyncio.run(init_db())"

seed-clinic:
	python scripts/seed_clinic.py

tunnel:
	ngrok http 8000 --config infra/ngrok.yml

simulate:
	python scripts/simulate_call.py

bench:
	python scripts/latency_bench.py

lint:
	ruff check services tests scripts
	black --check services tests scripts

typecheck:
	mypy services

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
