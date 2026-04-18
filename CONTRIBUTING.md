# Contributing

## Development Setup

```bash
# Clone the repository
git clone https://github.com/ladislav-lettovsky/ai-delivery-exception-system.git
cd ai-delivery-exception-system

# Install with dev dependencies
uv sync --extra dev

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Project Layout

This project uses the [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — all production code lives under `src/delivery_exception_system/`.

| Directory | Purpose |
|:---|:---|
| `src/delivery_exception_system/models/` | State definitions, Pydantic schemas |
| `src/delivery_exception_system/tools/` | LangChain @tool functions |
| `src/delivery_exception_system/guardrails/` | Security: injection detection, noise filtering |
| `src/delivery_exception_system/agents/` | LLM-backed agent nodes |
| `src/delivery_exception_system/preprocessing/` | Deterministic preprocessing pipeline |
| `src/delivery_exception_system/evaluation/` | Metrics and scoring |
| `src/delivery_exception_system/reporting/` | Output formatting |
| `tests/` | Pytest test suite |

## Branch Conventions

| Branch | Purpose |
|:---|:---|
| `main` | Production-ready code. All CI must pass before merging. |
| `feature/<name>` | New features (e.g., `feature/adjacent-zip-lockers`) |
| `fix/<name>` | Bug fixes (e.g., `fix/escalation-threshold`) |
| `refactor/<name>` | Internal restructuring with no behavior change (e.g., `refactor/extract-pii-view`) |
| `chore/<name>` | Tooling, config, dependencies — no runtime behavior change (e.g., `chore/claude-code-setup`) |
| `docs/<name>` | Documentation-only updates (README, CONTRIBUTING, inline docs) |

## Running Tests

```bash
# Run all deterministic tests (no API keys needed)
uv run pytest tests/ -v --ignore=tests/test_graph.py

# Run a specific test file
uv run pytest tests/test_escalation.py -v

# Run with coverage
uv run pytest tests/ --cov=delivery_exception_system --ignore=tests/test_graph.py
```

The test suite is organized by component:

| Test File | Tests | What It Covers |
|:---|:---|:---|
| `test_guardrails.py` | 15 | Injection detection, noise override |
| `test_escalation.py` | 10 | All escalation rule branches |
| `test_state.py` | 7 | PII view projection, state merge |
| `test_preprocessing.py` | 6 | Deduplication, event consolidation |
| `test_tools.py` | 5 | Tool functions against real data |
| `test_graph.py` | — | Integration tests (requires LLM API) |

## Key Architecture Rules

1. **Escalation logic lives in ONE place** — `tools/escalation_rules.py:should_escalate()`. Both `finalize.py` and `evaluation/metrics.py` call this function instead of reimplementing the rules.

2. **PII access is enforced by view dataclasses** — only `CommunicationAgentView` includes `customer_profile_full`. All other agents get `customer_profile` (redacted).

3. **Configuration comes from environment variables** — never hardcode API keys, model names, or file paths. Use `config.settings`.

4. **Logging, not printing** — use `logging.getLogger(__name__)` in every module.

## CI

GitHub Actions runs on every push to `main` and on pull requests. The workflow:
1. Installs dependencies with `uv`
2. Runs all deterministic tests (no API keys required)
3. Tests run against Python 3.12

See `.github/workflows/ci.yml` for the full configuration.
