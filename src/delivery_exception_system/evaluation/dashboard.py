"""Aggregate evaluation metrics dashboard."""

import logging

logger = logging.getLogger(__name__)


def print_aggregate_metrics(all_results: dict, gt_consolidated: dict) -> None:
    """Compute and print aggregated evaluation metrics."""
    from delivery_exception_system.evaluation.metrics import compute_escalation_accuracy

    total_shipments = len(all_results)
    completed_tasks = 0
    correct_escalations = 0
    total_escalations_evaluated = 0
    correct_tool_calls = 0
    total_coherence_score = 0
    total_latency = 0.0

    for sid, result in all_results.items():
        if result["task_completion"]["task_complete"]:
            completed_tasks += 1

        gt = gt_consolidated[sid]
        esc_correct_live = compute_escalation_accuracy(gt, result["state"])
        result["escalation_correct"] = esc_correct_live

        if esc_correct_live is not None:
            total_escalations_evaluated += 1
            if esc_correct_live:
                correct_escalations += 1

        if result["tool_call_correct"]:
            correct_tool_calls += 1

        total_coherence_score += result["coherence"]["score"]
        total_latency += result["latency"]

    task_completion_rate = (completed_tasks / total_shipments) * 100
    escalation_accuracy = (
        (correct_escalations / total_escalations_evaluated) * 100
        if total_escalations_evaluated > 0
        else 0
    )
    tool_call_accuracy = (correct_tool_calls / total_shipments) * 100
    average_coherence_score = total_coherence_score / total_shipments
    average_latency = total_latency / total_shipments

    print(
        f"\nAggregated Evaluation Metrics: {total_shipments} Shipments\n"
        f"{'─' * 49}\n"
        f"Task Completion Rate:          {task_completion_rate:.0f}%\n"
        f"Escalation Accuracy:           {escalation_accuracy:.0f}% "
        f"({total_escalations_evaluated} evaluated)\n"
        f"Tool Call Accuracy:            {tool_call_accuracy:.0f}%\n"
        f"Average Coherence:             {average_coherence_score:.2f}/5\n"
        f"Average Latency:               {average_latency:.0f}s"
    )
