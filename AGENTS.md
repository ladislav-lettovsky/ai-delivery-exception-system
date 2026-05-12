# ai-delivery-exception-system — AI Agent Memory

## What this is

An AI-powered multi-agent system (LangGraph) that automates last-mile delivery
exception handling — triage, resolution, and customer communication — with
deterministic guardrails and RAG-grounded playbook retrieval.

## Stack

- Python 3.12+, `uv` for dependency management, `just` as the task runner
- LangGraph (multi-agent orchestration), LangChain, LangSmith
- OpenAI GPT-4o / GPT-4o-mini (generation + critic)
- ChromaDB + HuggingFace `BAAI/bge-small-en-v1.5` (RAG over the playbook PDF)
- SQLite (customer profiles), pandas (tabular data)
- Testing: pytest 8, with `integration` marker for live-LLM tests
- Linting: ruff; Type checking: `ty` (Astral); Pre-commit hooks enabled

## Commands you can run without asking

- `just fmt` — format code
- `just lint` — ruff check
- `just lint-fix` — ruff check with --fix
- `just type` — ty check
- `just test` — full pytest run
- `just check` — lint + type + test (the same command CI runs)
- `uv sync`, `uv sync --extra dev`
- `uv run python -m delivery_exception_system [--flags]`
- Read-only git: `git status`, `git diff`, `git log`, `git branch`

## Commands with preconditions

- `git commit` is allowed on a non-`main` branch **only after `just check`
  passes with no errors**. On `main`, always ask first.
- After any update to local `main` (PR merge, `git pull`, fast-forward, etc.),
  immediately `git switch` to a parking branch — by convention `scratch`,
  forked from the new `main` tip. This keeps the working copy off `main` so
  no edits or commits land there by accident. Create real work branches
  (`feat/<name>`, `fix/<name>`, `chore/<name>`, ...) from `main`, not from
  `scratch`. If `scratch` is missing or stale, recreate it with
  `git switch -c scratch` from the current `main`.

## Commands that need explicit approval

- `uv add`, `uv remove` (dependency changes)
- `git push`, `git reset --hard`
- `gh pr create`, `gh pr merge`
- Anything touching `.env`, `.github/workflows/`, or `data/`

## Architectural invariants (do not violate without explicit discussion)

1. **Escalation logic lives in ONE place** — `src/delivery_exception_system/tools/escalation_rules.py::should_escalate()`.
   Both `agents/finalize.py` and `evaluation/metrics.py` must call this function
   rather than re-implementing rules. If you find yourself writing escalation
   logic elsewhere, stop and refactor into this module.

2. **PII access is enforced by view dataclasses** —
   `src/delivery_exception_system/models/state.py` defines five agent-scoped
   views. Only `CommunicationAgentView` contains `customer_profile_full`;
   every other agent gets `customer_profile` (redacted). Never bypass this
   by accessing raw state fields inside an agent.

3. **Configuration comes from environment variables** — API keys, model names,
   file paths, thresholds all live in `.env` and are read via `config.settings`.
   Never hardcode these in source files.

4. **Logging, not printing** — every module uses
   `logger = logging.getLogger(__name__)` at the top. Do not introduce `print()`
   calls into production code paths. Reporting modules under `reporting/` are
   the only exception (they format terminal output).

## Where things live

- `src/delivery_exception_system/` — production package (src layout)
  - `models/` — `state.py` (UnifiedAgentState + 5 View dataclasses), `schemas.py` (Pydantic output schemas)
  - `tools/` — LangChain `@tool` functions (delivery logs, customer profile, locker, playbook search, escalation rules)
  - `guardrails/` — `injection.py` (prompt injection keywords), `noise.py` (routine status filtering)
  - `preprocessing/` — deterministic 6-step pipeline
  - `agents/` — LLM-backed nodes (orchestrator, resolution, communication, critic, finalize)
  - `evaluation/` — metrics, LLM-as-judge coherence, dashboard
  - `reporting/` — summary, resolution detail, JSON writer
  - `graph.py` — LangGraph workflow construction
  - `runner.py` — CLI entry point
  - `config.py` — centralized settings from env vars
- `data/` — CSV, SQLite, PDF (playbook v3.1), ground truth
- `tests/` — 43 pytest tests, organized by component
- `results/` — JSON output per run (git-ignored)

## LangGraph conventions for this repo

- State is `UnifiedAgentState` in `models/state.py`. Agents never receive raw
  state; they receive one of the five view dataclasses.
- Graph definition lives in `graph.py`. Subgraphs, not inline mega-nodes.
- Checkpointing is not currently used (single-pass pipeline per shipment).
- Every agent logs `logger.info` at entry with shipment_id bound via structlog
  contextvars when applicable.

## Testing conventions

- Deterministic tests (no API) are the default. Run with
  `uv run pytest tests/ -v --ignore=tests/test_graph.py` or `just test`.
- LLM-integration tests live in `test_graph.py` and are marked `integration`.
  Skip with `-m "not integration"` when offline.
- New features require at least one deterministic test in the matching
  `test_<component>.py` file. See CONTRIBUTING.md for the full test matrix.

## Ephemeral / scratch work

Use `.scratch/` at the repo root for any exploratory, diagnostic, or
throwaway work — quick Python snippets, draft queries, debug logs, or
scratch notes. The directory is git-ignored, so nothing here is ever
committed.

- Create on demand: `mkdir -p .scratch`
- Preferred file names: `<topic>.py`, `<topic>.md`, `<topic>.sql`, etc.
- Do NOT place exploratory files at the repo root — always use `.scratch/`
- Clean up periodically (nothing persists beyond your working session)

Examples of good `.scratch/` use:

- `.scratch/try_new_prompt.py` — testing an agent prompt variation
- `.scratch/debug_chroma.py` — poking at the vector store interactively
- `.scratch/sql_exploration.md` — draft SQL before moving to `tools/`

## Before saying "done"

1. `just check` passes (ruff + ty + pytest, no integration tests)
2. Any new public function has a test and a type-annotated signature
3. No new `print()` calls; logging used throughout (reporting/ excepted)
4. If the change affects behavior, `README.md` and `CONTRIBUTING.md` reviewed
5. Diff against `main` looks like what you'd want in a PR review
