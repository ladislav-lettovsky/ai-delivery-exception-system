# Install pre-commit hooks into .git/hooks/ (run once after cloning)
install-hooks:
    uv run pre-commit install

# Run all pre-commit hooks against every file in the repo
pre-commit:
    uv run pre-commit run --all-files

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

# Full quality gate: all pre-commit hooks + type check + tests
check: pre-commit
    uv run ty check && uv run pytest
