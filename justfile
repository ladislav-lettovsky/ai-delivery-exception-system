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

# Lint Markdown (.md + .mdc). Uses the version pinned in .pre-commit-config.yaml.
lint-md:
    uv run pre-commit run markdownlint-cli2 --all-files

# Auto-fix Markdown lint violations. Version inline-pinned to match
# .pre-commit-config.yaml -- bump both together.
lint-md-fix:
    npx --yes markdownlint-cli2@0.22.1 --fix "**/*.md" "**/*.mdc"

type:
    uv run ty check

test:
    uv run pytest

# Full quality gate: all pre-commit hooks + type check + tests
check: pre-commit
    uv run ty check && uv run pytest
