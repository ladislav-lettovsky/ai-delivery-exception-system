"""Evaluation metrics: task completion, escalation accuracy, tool call accuracy."""

import logging
import sqlite3

import pandas as pd

from delivery_exception_system.config import settings
from delivery_exception_system.tools.escalation_rules import should_escalate

logger = logging.getLogger(__name__)


def compute_task_completion(gt: dict, pred: dict) -> dict:
    """Compute task completion for a single shipment."""

    def gtv_eval(val):
        if pd.isna(val):
            return "N/A"
        s = str(val).strip().upper()
        return "N/A" if s in ("", "NAN", "NONE") else s

    def compare(gt_val, pred_val):
        g = gtv_eval(gt_val)
        p = gtv_eval(pred_val)
        if g == "N/A" and p == "N/A":
            return None
        return g == p

    res = pred.get("resolution_output", {})
    comm = pred.get("communication_output", {})

    exception_correct = compare(gt.get("is_exception"), res.get("is_exception"))

    if gtv_eval(gt.get("is_exception")) == "YES":
        resolution_correct = compare(gt.get("expected_resolution"), res.get("resolution"))
        if pred.get("guardrail_triggered"):
            tone_correct = None
        else:
            tone_correct = compare(gt.get("expected_tone"), comm.get("tone_label", "N/A"))
    else:
        resolution_correct = None
        tone_correct = None

    all_criteria = [exception_correct, resolution_correct, tone_correct]
    applicable = [c for c in all_criteria if c is not None]
    task_complete = all(applicable) if applicable else None

    return {
        "exception_correct": exception_correct,
        "resolution_correct": resolution_correct,
        "tone_correct": tone_correct,
        "task_complete": task_complete,
    }


def _policy_should_escalate(pred: dict) -> bool:
    """Deterministic policy escalation from consolidated event + customer profile.

    Uses the shared should_escalate() as the SINGLE SOURCE OF TRUTH,
    with a SQLite fallback for partially-populated state.
    """
    ev = pred.get("consolidated_event", {})
    cp = dict(pred.get("customer_profile", {}) or {})

    # Fallback: if profile fields are missing in state, load from DB
    if ("tier" not in cp or "exceptions_last_90d" not in cp) and ev.get("customer_id"):
        try:
            with sqlite3.connect(settings.customers_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT tier, exceptions_last_90d FROM customers WHERE customer_id = ?",
                    (ev.get("customer_id"),),
                )
                row = cur.fetchone()
                if row:
                    cp.setdefault("tier", row["tier"])
                    cp.setdefault("exceptions_last_90d", row["exceptions_last_90d"])
        except Exception:
            pass

    tier = str(cp.get("tier", "STANDARD") or "STANDARD")
    exc90 = int(cp.get("exceptions_last_90d", 0) or 0)
    attempt = int(ev.get("attempt_number", 0) or 0)
    status_code = str(ev.get("status_code", "") or "")
    package_type = str(ev.get("package_type", "") or "")
    desc = str(ev.get("status_description", "") or "")

    # Use shared escalation logic
    result = should_escalate(
        customer_tier=tier,
        exceptions_last_90d=exc90,
        attempt_number=attempt,
        package_type=package_type,
        status_code=status_code,
        status_description=desc,
    )
    if result["has_triggers"]:
        return True

    # Additional checks not in the rule engine
    if pred.get("guardrail_triggered"):
        return True

    reason = str(pred.get("escalation_reason") or "")
    return "Max Retries" in reason


def compute_escalation_accuracy(gt: dict, pred: dict) -> bool | None:
    """Compare GT escalation to deterministic policy escalation computed from state context."""
    if gt.get("should_escalate") not in ("YES", "NO"):
        return None

    pred_flag = _policy_should_escalate(pred)

    if pred.get("resolution_output", {}).get("is_exception") == "NO":
        pred_flag = False

    return gt.get("should_escalate") == ("YES" if pred_flag else "NO")


def compute_tool_call_accuracy(gt: dict, pred: dict) -> bool | None:
    """Check if correct tools were invoked for a single shipment."""
    tool_log_str = " ".join(pred.get("tool_calls_log", []))
    is_exception = gt.get("is_exception", "NO")
    noise_override = pred.get("noise_override", False)
    guardrail_triggered = pred.get("guardrail_triggered", False)

    if guardrail_triggered:
        skip_tools = [
            "lookup_customer_profile",
            "check_locker_availability",
            "search_playbook",
            "check_escalation_rules",
            "resolution_agent",
            "communication_agent",
        ]
        return not any(t in tool_log_str for t in skip_tools)

    if noise_override:
        skip_tools = [
            "lookup_customer_profile",
            "check_locker_availability",
            "search_playbook",
            "check_escalation_rules",
            "resolution_agent",
            "communication_agent",
        ]
        return not any(t in tool_log_str for t in skip_tools)

    required = [
        "lookup_customer_profile",
        "check_locker_availability",
        "search_playbook",
        "check_escalation_rules",
        "resolution_agent",
    ]

    if is_exception == "YES":
        required.append("communication_agent")

    return all(t in tool_log_str for t in required)
