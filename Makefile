.PHONY: install dev test lint format migrate test-cov uat build

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

build:
	cd frontend && pnpm build

uat:
	@test -d frontend/node_modules/playwright || \
		(echo "Installing playwright..." && cd frontend && pnpm add -D playwright && pnpm exec playwright install chromium)
	node tests/uat/routes.mjs
