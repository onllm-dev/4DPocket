.PHONY: install dev test lint format migrate test-cov

install:
	uv sync --all-extras

dev:
	uv run uvicorn fourdpocket.main:app --reload --host 0.0.0.0 --port 4040

test:
	uv run pytest -x -q

test-cov:
	uv run pytest --cov=fourdpocket --cov-report=term-missing

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

migrate:
	uv run alembic upgrade head

migrate-gen:
	uv run alembic revision --autogenerate -m "$(msg)"
