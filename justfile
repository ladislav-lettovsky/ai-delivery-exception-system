fmt:  # format code
    uv run ruff format .

lint:
    uv run ruff check .

lint-fix:
    uv run ruff check --fix .

type:
    uv run ty check

test:
    uv run pytest

check:
    uv run ruff check . && uv run ty check && uv run pytest

