# AI-powered Last Mile Delivery Exception Handling Automation

[![CI](https://github.com/ladislav-lettovsky/ai-delivery-exception-system/actions/workflows/ci.yml/badge.svg)](https://github.com/ladislav-lettovsky/ai-delivery-exception-system/actions/workflows/ci.yml)

An AI-powered multi-agent system that automates end-to-end handling of last-mile delivery exceptions — from detection and triage through resolution and personalized customer communication.

Built as part of the **Agentic AI Postgraduate Program at UT Austin / Great Learning**.

---

## Problem

In last-mile logistics, roughly 10% of all shipments encounter delivery exceptions — failed attempts, address mismatches, damaged packages, refused deliveries, and weather delays. Most organizations still handle exception triage and resolution manually: operations staff read through status logs and driver notes, cross-reference customer profiles and internal playbooks, decide on a resolution, and draft customer notifications — all under time pressure.

This manual process leads to:
- Slow exception resolution constrained by manual triage throughput
- Missed or unnecessary supervisor escalations
- Inconsistent customer communication quality
- High cost per exception (reattempt costs, spoilage write-offs, unnecessary truck rolls)
- Preventable customer churn

## Solution

**LangGraph-orchestrated multi-agent system** with five specialized agents, each with distinct responsibilities and guardrails:

| Agent | Role |
|:---|:---|
| **Preprocessor** | Ingests raw delivery logs, deduplicates events, performs input guardrailing against prompt injection, fetches context (customer profiles, locker availability, playbook rules), and filters routine operational noise |
| **Orchestrator** | Central traffic controller — deterministically manages workflow routing, revision loops, hard escalation rules, and guardrail enforcement |
| **Resolution Agent** | Classifies whether an event is an actionable exception or noise, then proposes the appropriate resolution (reschedule, reroute to locker, replace, or return to sender) based on playbook rules and customer context |
| **Communication Agent** | Generates personalized customer notifications calibrated to customer tier, preferred channel, and exception severity — the only agent with PII access |
| **Critic Agent** | Quality assurance layer operating in two modes: validates resolution decisions (ACCEPT / REVISE / ESCALATE) and evaluates communication quality (ACCEPT / ESCALATE) |

### Architecture

```
Delivery Logs ──► Preprocessor ──► Orchestrator ──► Resolution Agent ──► Critic (Resolution)
                                       │                                      │
                                       │              ◄── REVISE (up to 2x) ──┘
                                       │
                                       ├──► Communication Agent ──► Critic (Communication)
                                       │
                                       └──► Final Decision + Escalation (if required)
```

### Key Design Decisions

- **Guardrails at multiple layers** — prompt injection detection in the preprocessor before any LLM call; deterministic escalation rules as an authoritative backstop; Critic revision loops (up to 2 attempts) before forced escalation
- **RAG-grounded resolution** — playbook retrieval adds traceable document context and page-level citations to support recommendations
- **PII isolation** — only the Communication Agent has access to customer PII, and only where needed for personalization
- **Cost-effective model pairing** — `gpt-4o-mini` for generation, `gpt-4o` for validation/critic (~$0.005 per shipment)

## Project Structure

```
ai-delivery-exception-system/
├── src/delivery_exception_system/     # Production Python package (src layout)
│   ├── config.py                      # Centralized settings from environment variables
│   ├── models/
│   │   ├── state.py                   # UnifiedAgentState, 5 PII-controlled View dataclasses
│   │   └── schemas.py                 # Pydantic output schemas for all agents
│   ├── data/
│   │   ├── loader.py                  # CSV, SQLite, and PDF data loading
│   │   └── vectorstore.py             # ChromaDB with persistence and PDF hash caching
│   ├── tools/                         # LangChain @tool functions
│   │   ├── delivery_logs.py           # Read delivery log CSV
│   │   ├── customer_profile.py        # SQLite customer lookup with PII redaction
│   │   ├── locker_availability.py     # Smart locker eligibility check
│   │   ├── playbook_search.py         # ChromaDB vector search
│   │   └── escalation_rules.py        # Deterministic rule engine (single source of truth)
│   ├── guardrails/
│   │   ├── injection.py               # 90+ keyword prompt injection detection
│   │   └── noise.py                   # Routine status code filtering
│   ├── preprocessing/
│   │   └── preprocessor.py            # 6-step pipeline: dedup → consolidate → guardrails → context
│   ├── agents/
│   │   ├── orchestrator.py            # 9-step deterministic router
│   │   ├── resolution.py              # Exception classification and resolution
│   │   ├── communication.py           # Customer notification generation
│   │   ├── critic.py                  # Resolution and communication validation
│   │   └── finalize.py                # Final packaging with shared escalation logic
│   ├── evaluation/
│   │   ├── metrics.py                 # Task completion, escalation accuracy, tool call accuracy
│   │   ├── coherence.py               # LLM-as-judge coherence scoring
│   │   └── dashboard.py               # Aggregate metrics
│   ├── reporting/
│   │   ├── summary.py                 # Compact tabular output
│   │   ├── resolution.py              # Detailed box-formatted reports
│   │   └── json_writer.py             # Structured JSON results output
│   ├── langsmith_dashboard.py         # LangSmith cost and token dashboard
│   ├── graph.py                       # LangGraph workflow construction
│   └── runner.py                      # CLI entry point
├── data/                              # Data files
│   ├── customers.db                   # SQLite: 12 customers + smart lockers
│   ├── delivery_logs.csv              # 13 delivery log rows, 10 shipments
│   ├── ground_truth.csv               # Hand-labeled expected outcomes
│   └── exception_resolution_playbook.pdf  # 10-page operational playbook (v3.1)
├── results/                           # JSON results from each run (git-ignored)
├── tests/                             # 43 pytest tests
├── pyproject.toml                     # Project metadata and dependencies
├── .env.example                       # Environment variable template
└── .github/workflows/ci.yml           # GitHub Actions CI
```

## Data

| Dataset | Format | Description |
|:---|:---|:---|
| `customers.db` | SQLite | 12 customer records with tier, preferred channel, exception history, active credits |
| `delivery_logs.csv` | CSV | 13 rows across 10 unique shipments with status codes, driver notes, package attributes |
| `ground_truth.csv` | CSV | Hand-labeled expected resolution, tone, escalation, and step-by-step reasoning for each shipment |
| `exception_resolution_playbook.pdf` | PDF | 10-page operational playbook (v3.1) defining resolution rules, escalation policies, and communication guidelines |

## Results

Evaluated across 11 curated test cases covering noise filtering, VIP escalation, locker constraints, perishable handling, damaged packages, prompt injection, and discretionary escalation:

| Metric | Score |
|:---|:---|
| Task Completion Rate | 100% (11/11) |
| Escalation Accuracy | 100% |
| Tool Call Accuracy | 100% |
| Avg. Latency per Shipment | ~6s |
| Cost per Shipment | ~$0.005 |

### Notable Test Cases

- **SHP-001, SHP-010** — Routine noise correctly filtered by preprocessor guardrail, no unnecessary LLM processing
- **SHP-002** — VIP with 5 exceptions in 90 days, duplicate scan deduplicated, locker unavailable → rescheduled with escalation
- **SHP-005** — Third failed attempt, locker full → policy-correct reroute with mandatory escalation
- **SHP-007** — Perishable weather delay exceeding threshold for VIP → replacement initiated
- **SHP-011** — Prompt injection in driver notes detected and blocked at preprocessor → forced escalation for human review

## Tech Stack

- **Python 3.12+**
- **LangGraph** — multi-agent workflow orchestration
- **LangChain** — LLM integration and tool orchestration
- **OpenAI GPT-4o / GPT-4o-mini** — generation and validation models
- **LangSmith** — tracing and observability
- **SQLite** — customer data store
- **ChromaDB** — vector store for playbook retrieval (RAG) with persistence
- **HuggingFace** — `BAAI/bge-small-en-v1.5` embedding model

## Setup

```bash
# Clone the repository
git clone https://github.com/ladislav-lettovsky/ai-delivery-exception-system.git
cd ai-delivery-exception-system

# Install dependencies (using uv)
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys (OpenAI, HuggingFace, LangSmith)
```

## Usage

```bash
# Run the pipeline — writes JSON results to results/, prints compact summary
uv run python -m delivery_exception_system

# Include the detailed human-readable report in terminal output
uv run python -m delivery_exception_system --report

# Write JSON to a specific path
uv run python -m delivery_exception_system --json-output my_run.json

# Skip JSON output entirely (terminal only)
uv run python -m delivery_exception_system --no-json --report

# Process a specific shipment
uv run python -m delivery_exception_system --shipment-id SHP-005

# Verbose logging (all loggers including httpx, LangChain, etc.)
uv run python -m delivery_exception_system --verbose

# Save workflow diagram
uv run python -m delivery_exception_system --diagram

# Include LangSmith cost dashboard
uv run python -m delivery_exception_system --langsmith-dashboard
```

### Output Streams

The system separates three output streams:

| Stream | Default | Flag |
|:---|:---|:---|
| Compact summary table | Always printed | — |
| Structured JSON results | `results/run_<timestamp>.json` | `--json-output PATH` or `--no-json` |
| Detailed terminal report | Off | `--report` |
| Third-party log noise | Suppressed (WARNING) | `--verbose` or `LOG_LEVEL=DEBUG` |

## Testing

```bash
# Run all deterministic tests (no API keys required)
uv run pytest tests/ -v --ignore=tests/test_graph.py

# Run integration tests (requires API keys)
uv run pytest tests/test_graph.py --run-integration
```

## Business Recommendations

1. **Initiate a pilot program with real-time feeds** — consistent behavior at ~$0.005/shipment and ~6s latency supports a controlled live deployment
2. **Expand the evaluation set** — build 200+ shipment scenarios including adversarial injection, ambiguous descriptions, missing records, and edge-case escalation triggers
3. **Develop monitoring and human-in-the-loop workflows** — at ~70% escalation rate, supervisor dashboards should surface escalation reason, revision history, and Critic rationale
4. **Enable adjacent-zip locker rerouting** — query nearby zip codes to increase successful rerouting when same-zip locker is full

## License

This project was developed as part of the Agentic AI Postgraduate Program at UT Austin / Great Learning.

## Author

**Ladislav Lettovsky** — [GitHub](https://github.com/ladislav-lettovsky)
