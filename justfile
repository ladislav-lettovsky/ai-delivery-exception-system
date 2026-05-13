# Install pre-commit hooks into .git/hooks/ (run once after cloning)
install-hooks:
    uv run pre-commit install

# Re-hydrate this checkout: sync dev dependencies and (re-)install pre-commit hooks.
# Run after a fresh clone, after `git worktree add`, or after pulling a branch
# that changed pyproject.toml / uv.lock. The .venv is per-checkout (git-ignored),
# so every worktree needs its own sync.
refresh:
    uv sync --extra dev
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
