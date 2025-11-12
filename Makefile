run:
	uv run python -m lost_hiker.game

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run black --check .

hooks:
	uv run pre-commit install

fix:
	uv run ruff check . --fix
	uv run black .
