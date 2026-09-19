.PHONY: setup migrate seed pipeline incremental test lint down
setup:
	docker compose up -d --build
migrate:
	docker compose run --rm runner alembic upgrade head
seed:
	docker compose run --rm runner workforcesync seed
pipeline:
	docker compose run --rm runner workforcesync pipeline
incremental:
	docker compose run --rm runner workforcesync seed --scenario incremental
	docker compose run --rm runner workforcesync pipeline
test:
	docker compose run --rm runner pytest -m 'not integration'
lint:
	docker compose run --rm runner ruff check .
	docker compose run --rm runner ruff format --check .
down:
	docker compose down
