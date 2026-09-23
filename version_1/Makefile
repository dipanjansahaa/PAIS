.PHONY: install dev test lint format migrate migration db-up db-down

install:
	@echo 'Install dependencies'

dev:
	@echo 'Start development environment'

test:
	pytest

lint:
	@echo 'Run linting'

format:
	@echo 'Run formatting'

migrate:
	@echo 'Run database migrations'

migration:
	@echo 'Create a database migration'

db-up:
	docker compose up -d

db-down:
	docker compose down
