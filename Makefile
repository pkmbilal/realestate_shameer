# Shortcuts for common commands. Requires `make` (not installed by default on Windows;
# every target below is a plain `docker compose ...` command you can run directly).

.PHONY: up down logs migrate migrations superuser seed test lint format shell

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api python manage.py migrate

migrations:
	docker compose exec api python manage.py makemigrations

superuser:
	docker compose exec api python manage.py createsuperuser

seed:
	docker compose exec api python manage.py seed_demo

test:
	docker compose exec api pytest

lint:
	docker compose exec api ruff check .
	docker compose exec api ruff format --check .
	docker compose exec web npm run lint
	docker compose exec web npm run typecheck

format:
	docker compose exec api ruff format .
	docker compose exec api ruff check --fix .

shell:
	docker compose exec api python manage.py shell
