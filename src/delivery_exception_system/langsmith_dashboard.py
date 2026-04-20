"""LangSmith cost and efficiency dashboard."""

import logging
import os
import statistics
from typing import Any

from langsmith import Client

logger = logging.getLogger(__name__)


def fetch_langsmith_runs(max_runs: int = 11) -> list:
    """Fetch recent top-level runs from LangSmith."""
    client = Client()
    project_name = os.environ.get("LANGCHAIN_PROJECT", "default")
    runs = list(
        client.list_runs(
            project_name=project_name,
            execution_order=1,
            limit=max_runs,
            error=None,
        )
    )
    return runs


def parse_run_metadata(runs: list) -> list:
    """Extract relevant fields from each LangSmith run object."""
    records = []
    for run in runs:
        prompt_tok = run.prompt_tokens or 0
        compl_tok = run.completion_tokens or 0
        total_cost = float(run.total_cost) if getattr(run, "total_cost", None) else 0.0
        prompt_cost = float(run.prompt_cost) if getattr(run, "prompt_cost", None) else 0.0
        completion_cost = (
            float(run.completion_cost) if getattr(run, "completion_cost", None) else 0.0
        )
        records.append(
            {
                "run_id": str(run.id),
                "run_name": run.name,
                "status": run.status,
                "error": run.error,
                "prompt_tokens": prompt_tok,
                "compl_tokens": compl_tok,
                "total_cost_usd": total_cost,
                "prompt_cost_usd": prompt_cost,
                "completion_cost_usd": completion_cost,
            }
        )
    return records


def compute_aggregate_metrics(records: list) -> dict[str, Any]:
    """Compute aggregated efficiency metrics from parsed run records."""
    if not records:
        logger.warning("No run records to aggregate.")
        return {}

    total_runs = len(records)
    prompt_tokens = [r["prompt_tokens"] for r in records if r["prompt_tokens"]]
    compl_tokens = [r["compl_tokens"] for r in records if r["compl_tokens"]]
    avg_prompt = statistics.mean(prompt_tokens) if prompt_tokens else 0
    avg_compl = statistics.mean(compl_tokens) if compl_tokens else 0

    costs = [r["total_cost_usd"] for r in records]
    prompt_costs = [r["prompt_cost_usd"] for r in records]
    completion_costs = [r["completion_cost_usd"] for r in records]

    return {
        "total_runs": total_runs,
        "avg_prompt_tokens": avg_prompt,
        "avg_output_tokens": avg_compl,
        "avg_cost_per_run_usd": sum(costs) / total_runs if total_runs else 0,
        "total_cost_usd": sum(costs),
        "total_prompt_cost_usd": sum(prompt_costs),
        "total_completion_cost_usd": sum(completion_costs),
    }


def print_efficiency_dashboard(metrics: dict[str, Any]) -> None:
    """Print a formatted efficiency dashboard."""
    if not metrics:
        print("No metrics to display.")
        return

    print(
        f"\n--- Cost Dashboard (from LangSmith) ---\n"
        f"\n    Token usage ({metrics['total_runs']} runs)"
        f"\n    {'\u2500' * 28}"
        f"\n    Avg Prompt Tokens:   {metrics['avg_prompt_tokens']:>7.0f}"
        f"\n    Avg Output Tokens:   {metrics['avg_output_tokens']:>7.0f}"
        f"\n    Avg Total Tokens:    {metrics['avg_prompt_tokens'] + metrics['avg_output_tokens']:>7.0f}"
        f"\n"
        f"\n    Token cost (USD)"
        f"\n    {'\u2500' * 28}"
        f"\n    Avg Cost per Run:     ${metrics['avg_cost_per_run_usd']:.3f}"
        f"\n"
        f"\n    Total Prompt Cost     ${metrics['total_prompt_cost_usd']:.3f}"
        f"\n    Total Output Cost:    ${metrics['total_completion_cost_usd']:.3f}"
        f"\n"
        f"\n    Total Cost:           ${metrics['total_cost_usd']:.3f}"
    )


# ..............................................................................................................................................
