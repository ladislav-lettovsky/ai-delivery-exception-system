"""Write structured JSON results to disk.

Separates machine-readable evaluation data from human-readable terminal
reports.  Every run produces a timestamped JSON file under ``results/``
that downstream tooling (dashboards, CI checks, monitoring) can consume
without parsing terminal output.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from delivery_exception_system.config import settings

logger = logging.getLogger(__name__)


def _serialize_shipment(sid: str, result: dict, ground_truth: dict) -> dict:
    """Convert a single shipment result into a JSON-safe dictionary."""
    state = result["state"]
    event = state.get("consolidated_event") or {}
    cust = state.get("customer_profile") or {}
    res = state.get("resolution_output") or {}
    comm = state.get("communication_output") or {}
    tc = result["task_completion"]
    coh = result["coherence"]

    def _safe(val):
        """Coerce NaN / None to null-safe values."""
        import pandas as pd

        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return val

    return {
        "shipment_id": sid,
        "event": {
            "status_code": event.get("status_code"),
            "status_description": event.get("status_description"),
            "package_size": event.get("package_size"),
            "package_type": event.get("package_type"),
            "attempt_number": event.get("attempt_number"),
        },
        "customer": {
            "tier": cust.get("tier"),
            "preferred_channel": cust.get("preferred_channel"),
            "exceptions_last_90d": cust.get("exceptions_last_90d"),
        },
        "predictions": {
            "is_exception": res.get("is_exception"),
            "resolution": res.get("resolution"),
            "tone": comm.get("tone_label"),
            "escalated": state.get("escalated", False),
            "rationale": res.get("rationale"),
            "communication_message": comm.get("communication_message"),
        },
        "ground_truth": {
            "is_exception": _safe(ground_truth.get("is_exception")),
            "expected_resolution": _safe(ground_truth.get("expected_resolution")),
            "expected_tone": _safe(ground_truth.get("expected_tone")),
            "should_escalate": _safe(ground_truth.get("should_escalate")),
        },
        "evaluation": {
            "task_complete": tc.get("task_complete"),
            "exception_correct": tc.get("exception_correct"),
            "resolution_correct": tc.get("resolution_correct"),
            "tone_correct": tc.get("tone_correct"),
            "escalation_correct": result.get("escalation_correct"),
            "tool_call_correct": result.get("tool_call_correct"),
            "coherence_score": coh.get("score"),
            "coherence_justification": coh.get("justification"),
        },
        "metadata": {
            "latency_sec": result.get("latency", 0.0),
            "noise_override": state.get("noise_override", False),
            "guardrail_triggered": state.get("guardrail_triggered", False),
            "escalation_reason": state.get("escalation_reason"),
            "playbook_pages_cited": sorted(result.get("citations", set())),
            "trajectory": state.get("trajectory_log", []),
        },
    }


def _compute_aggregate(all_results: dict, gt_consolidated: dict) -> dict:
    """Compute aggregate metrics as a plain dict."""
    total = len(all_results)
    completed = sum(
        1 for r in all_results.values() if r["task_completion"]["task_complete"]
    )
    esc_evaluated = 0
    esc_correct = 0
    tool_correct = 0
    total_coherence = 0
    total_latency = 0.0

    for r in all_results.values():
        ec = r.get("escalation_correct")
        if ec is not None:
            esc_evaluated += 1
            if ec:
                esc_correct += 1
        if r.get("tool_call_correct"):
            tool_correct += 1
        total_coherence += r["coherence"]["score"]
        total_latency += r.get("latency", 0.0)

    return {
        "total_shipments": total,
        "task_completion_rate": round(completed / total * 100, 1) if total else 0,
        "escalation_accuracy": (
            round(esc_correct / esc_evaluated * 100, 1) if esc_evaluated else None
        ),
        "escalations_evaluated": esc_evaluated,
        "tool_call_accuracy": round(tool_correct / total * 100, 1) if total else 0,
        "average_coherence": round(total_coherence / total, 2) if total else 0,
        "average_latency_sec": round(total_latency / total, 1) if total else 0,
    }


def write_json_results(
    all_results: dict,
    gt_consolidated: dict,
    output_path: Path | None = None,
) -> Path:
    """Serialize all results to a timestamped JSON file.

    Returns the path of the written file.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    if output_path is None:
        output_dir = settings.results_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"run_{timestamp}.json"

    shipments = []
    for sid in all_results:
        gt = gt_consolidated[sid]
        shipments.append(_serialize_shipment(sid, all_results[sid], gt))

    payload = {
        "run_timestamp": datetime.now(UTC).isoformat(),
        "config": {
            "gen_model": settings.gen_model,
            "val_model": settings.val_model,
            "embedding_model": settings.embedding_model,
            "max_loops": settings.max_loops,
            "max_retries": settings.max_retries,
        },
        "aggregate": _compute_aggregate(all_results, gt_consolidated),
        "shipments": shipments,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info("Results written to %s", output_path)
    return output_path
