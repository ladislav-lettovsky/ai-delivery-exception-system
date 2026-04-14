"""CLI entry point and main execution logic."""

import argparse
import logging
from collections import defaultdict

from delivery_exception_system.config import settings
from delivery_exception_system.data.loader import load_ground_truth
from delivery_exception_system.evaluation.coherence import compute_coherence_score
from delivery_exception_system.evaluation.dashboard import print_aggregate_metrics
from delivery_exception_system.evaluation.metrics import (
    compute_escalation_accuracy,
    compute_task_completion,
    compute_tool_call_accuracy,
)
from delivery_exception_system.graph import build_graph
from delivery_exception_system.reporting.resolution import shipment_resolution
from delivery_exception_system.reporting.summary import shipment_summary
from delivery_exception_system.tools.delivery_logs import read_delivery_logs

logger = logging.getLogger(__name__)


def process_shipment(app, shipment_id: str, raw_rows: list[dict], ground_truth: dict) -> dict:
    """Process a single shipment through the workflow and compute evaluation metrics."""
    initial_state = {
        "raw_rows": raw_rows,
        "shipment_id": shipment_id,
        "consolidated_event": {},
        "customer_profile": {},
        "customer_profile_full": {},
        "locker_availability": [],
        "playbook_context": [],
        "escalation_signals": {},
        "resolution_output": {},
        "critic_resolution_output": {},
        "resolution_revision_count": 0,
        "critic_feedback": "",
        "communication_output": {},
        "critic_communication_output": {},
        "next_agent": "resolution_agent",
        "max_loops": settings.max_loops,
        "escalated": False,
        "escalation_reason": "",
        "tool_calls_log": [],
        "trajectory_log": [],
        "start_time": None,
        "latency_sec": None,
        "final_actions": [],
        "noise_override": False,
        "guardrail_triggered": False,
    }

    result = app.invoke(initial_state)
    task = compute_task_completion(ground_truth, result)
    esc_acc = compute_escalation_accuracy(ground_truth, result)
    tool_acc = compute_tool_call_accuracy(ground_truth, result)
    coherence = compute_coherence_score(result)
    citations = {c["page"] for c in result.get("playbook_context", [])}

    return {
        "state": result,
        "task_completion": task,
        "escalation_correct": esc_acc,
        "tool_call_correct": tool_acc,
        "coherence": coherence,
        "latency": result.get("latency_sec", 0.0),
        "citations": citations,
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-powered delivery exception handling system"
    )
    parser.add_argument(
        "--shipment-id",
        type=str,
        default=None,
        help="Process a specific shipment ID only",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--diagram",
        action="store_true",
        help="Save the workflow diagram to workflow.png",
    )
    parser.add_argument(
        "--langsmith-dashboard",
        action="store_true",
        help="Print LangSmith cost dashboard after processing",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Apply environment variables
    settings.apply_env()

    # Build the graph
    app = build_graph()

    # Optional: save diagram
    if args.diagram:
        try:
            png_bytes = app.get_graph().draw_mermaid_png()
            with open("workflow.png", "wb") as f:
                f.write(png_bytes)
            logger.info("Workflow diagram saved to workflow.png")
        except Exception as e:
            logger.warning("Could not generate diagram: %s", e)

    # Load data
    all_logs = read_delivery_logs.invoke({})
    shipment_groups = defaultdict(list)
    for row in all_logs:
        shipment_groups[row["shipment_id"]].append(row)

    unique_shipment_ids = list(dict.fromkeys(row["shipment_id"] for row in all_logs))

    # Filter to specific shipment if requested
    if args.shipment_id:
        if args.shipment_id not in shipment_groups:
            logger.error("Shipment %s not found in delivery logs", args.shipment_id)
            return
        unique_shipment_ids = [args.shipment_id]

    # Load and consolidate ground truth
    gt_df = load_ground_truth()
    gt_by_shipment = defaultdict(list)
    for _, row in gt_df.iterrows():
        gt_by_shipment[row["shipment_id"]].append(row.to_dict())

    gt_consolidated = {}
    for sid, rows in gt_by_shipment.items():
        exc_rows = [r for r in rows if r["is_exception"] == "YES"]
        gt_consolidated[sid] = exc_rows[-1] if exc_rows else rows[0]

    # Process shipments
    all_results = {}
    print_header = True
    for shipment_id in unique_shipment_ids:
        ground_truth = gt_consolidated[shipment_id]
        shipment_group = shipment_groups[shipment_id]
        result = process_shipment(app, shipment_id, shipment_group, ground_truth)
        all_results[shipment_id] = result
        shipment_summary(shipment_id, result, ground_truth, print_header)
        print_header = False

    # Print detailed reports
    for shipment_id in unique_shipment_ids:
        result = all_results[shipment_id]
        gt = gt_consolidated[shipment_id]
        shipment_resolution(shipment_id, result, gt)

    # Print aggregate metrics
    print_aggregate_metrics(all_results, gt_consolidated)

    # Optional: LangSmith dashboard
    if args.langsmith_dashboard:
        try:
            from delivery_exception_system.langsmith_dashboard import (
                compute_aggregate_metrics as ls_agg,
                fetch_langsmith_runs,
                parse_run_metadata,
                print_efficiency_dashboard,
            )

            raw_runs = fetch_langsmith_runs(max_runs=len(all_results))
            run_records = parse_run_metadata(raw_runs)
            agg_metrics = ls_agg(run_records)
            print_efficiency_dashboard(agg_metrics)
        except Exception as e:
            logger.warning("LangSmith dashboard unavailable: %s", e)


if __name__ == "__main__":
    main()
