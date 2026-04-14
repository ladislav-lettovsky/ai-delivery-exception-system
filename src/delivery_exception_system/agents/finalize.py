"""Finalize node: packages final results and records end time."""

import json
import logging
import re
import time

from langsmith import traceable

from delivery_exception_system.models.state import (
    RouterView,
    UnifiedAgentState,
    merge_back,
    project_into,
)
from delivery_exception_system.tools.escalation_rules import should_escalate

logger = logging.getLogger(__name__)


@traceable(name="finalize_node")
def finalize_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Packages final results and records end time."""
    view = project_into(state, RouterView)

    if view.get("guardrail_triggered"):
        final = {
            "shipment_id": view["shipment_id"],
            "is_exception": "BLOCKED",
            "resolution": "ESCALATED",
            "escalated": True,
            "tone": "N/A",
            "message": "This shipment was flagged by the input guardrail and requires human review.",
            "revision_count": 0,
            "guardrail_blocked": True,
        }
    else:
        ev = view.get("consolidated_event", {})
        cp = view.get("customer_profile", {})

        # Use the shared escalation logic — SINGLE SOURCE OF TRUTH
        tier = str(cp.get("tier", "STANDARD") or "STANDARD")
        exc90 = int(cp.get("exceptions_last_90d", 0) or 0)
        attempt = int(ev.get("attempt_number", 0) or 0)
        status_code = str(ev.get("status_code", "") or "")
        package_type = str(ev.get("package_type", "") or "")
        desc = str(ev.get("status_description", "") or "")

        esc_result = should_escalate(
            customer_tier=tier,
            exceptions_last_90d=exc90,
            attempt_number=attempt,
            package_type=package_type,
            status_code=status_code,
            status_description=desc,
        )
        auto = esc_result["has_triggers"] and any(
            t.startswith("AUTOMATIC") for t in esc_result["triggers"]
        )

        # Also check STANDARD + high exception count rule
        auto = auto or (tier == "STANDARD" and exc90 > 5 and attempt >= 2)

        reason = str(view.get("escalation_reason") or "")
        forced_retry_failure = "Max Retries" in reason

        is_exception = view.get("resolution_output", {}).get("is_exception", "ERROR")
        policy_escalated = auto or forced_retry_failure or view.get("escalated", False)
        if is_exception == "NO":
            policy_escalated = False

        state["escalated"] = policy_escalated

        final = {
            "shipment_id": view["shipment_id"],
            "is_exception": is_exception,
            "resolution": view.get("resolution_output", {}).get("resolution", "ERROR"),
            "escalated": policy_escalated,
            "tone": view.get("communication_output", {}).get("tone_label", "N/A"),
            "message": view.get("communication_output", {}).get(
                "communication_message", ""
            ),
            "revision_count": view.get("resolution_revision_count", 0),
            "guardrail_blocked": False,
        }

    latency = time.time() - view["start_time"] if view.get("start_time") else 0.0

    output = {
        "final_actions": [final],
        "escalated": final["escalated"],
        "latency_sec": latency,
        "next_agent": "END",
    }

    state["trajectory_log"].append(
        f"finalize: actions={json.dumps(final)}; latency={latency:.3f}s"
    )

    return merge_back(state, output, RouterView)
