.PHONY: install dev test lint format migrate migration db-up db-down db-check

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(name)"

db-up:
	docker compose up -d

db-down:
	docker compose down

db-check:
	python -c "from app.database.session import engine; print(engine.url.render_as_string(hide_password=True))"

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

integration-test:
	RUN_INTEGRATION_TESTS=1 pytest tests/integration -m integration
