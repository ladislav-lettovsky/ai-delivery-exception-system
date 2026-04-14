"""Preprocessor node: deduplicates, consolidates, assembles context, runs guardrails."""

import logging
import time

from langsmith import traceable

from delivery_exception_system.guardrails.injection import (
    scan_chunks_for_injection,
    scan_inputs_for_injection,
)
from delivery_exception_system.guardrails.noise import check_noise_override
from delivery_exception_system.models.state import (
    RouterView,
    UnifiedAgentState,
    merge_back,
    project_into,
)
from delivery_exception_system.tools.customer_profile import lookup_customer_profile
from delivery_exception_system.tools.escalation_rules import check_escalation_rules
from delivery_exception_system.tools.locker_availability import check_locker_availability
from delivery_exception_system.tools.playbook_search import search_playbook

logger = logging.getLogger(__name__)


def deduplicate_rows(raw_rows: list[dict]) -> list[dict]:
    """Remove duplicate scan events."""
    return [r for r in raw_rows if r.get("is_duplicate_scan", "False") != "True"]


def consolidate_event(unique_rows: list[dict], raw_rows: list[dict]) -> dict:
    """Consolidate multi-row shipment into a single event using highest attempt number."""
    if unique_rows:
        primary = max(unique_rows, key=lambda r: int(r.get("attempt_number", 0)))
    else:
        primary = raw_rows[0]

    prior_notes = [
        f"Attempt {r['attempt_number']}: {r['status_description']}"
        for r in unique_rows
        if r is not primary
    ]

    return {
        "shipment_id": primary["shipment_id"],
        "timestamp": primary["timestamp"],
        "status_code": primary["status_code"],
        "status_description": primary["status_description"],
        "customer_id": primary["customer_id"],
        "delivery_address": primary["delivery_address"],
        "package_type": primary["package_type"],
        "package_size": primary["package_size"],
        "attempt_number": int(primary["attempt_number"]),
        "prior_attempt_notes": prior_notes,
        "total_rows": len(raw_rows),
        "duplicates_removed": len(raw_rows) - len(unique_rows),
    }


def fetch_context(consolidated: dict, tool_log: list[str]) -> dict:
    """Fetch all context via tools: customer profiles, lockers, playbook, escalation rules."""
    customer_id = consolidated["customer_id"]

    customer_profile = lookup_customer_profile.invoke(
        {"customer_id": customer_id, "include_pii": False}
    )
    tool_log.append(f"TOOL: lookup_customer_profile({customer_id}, pii=False)")

    customer_profile_full = lookup_customer_profile.invoke(
        {"customer_id": customer_id, "include_pii": True}
    )
    tool_log.append(f"TOOL: lookup_customer_profile({customer_id}, pii=True)")

    address_parts = consolidated["delivery_address"].split(",")
    zip_code = address_parts[-1].strip() if address_parts else ""
    locker_availability = check_locker_availability.invoke(
        {"zip_code": zip_code, "package_size": consolidated["package_size"]}
    )
    tool_log.append(
        f"TOOL: check_locker_availability({zip_code}, {consolidated['package_size']})"
    )

    query = (
        f"{consolidated['status_code']} {consolidated['package_type']} "
        f"{consolidated['status_description'][:100]}"
    )
    playbook_context = search_playbook.invoke({"query": query})
    tool_log.append("TOOL: search_playbook(query)")

    escalation_signals = check_escalation_rules.invoke(
        {
            "customer_tier": customer_profile.get("tier", "STANDARD"),
            "exceptions_last_90d": customer_profile.get("exceptions_last_90d", 0),
            "attempt_number": consolidated["attempt_number"],
            "package_type": consolidated["package_type"],
            "status_code": consolidated["status_code"],
            "status_description": consolidated["status_description"],
        }
    )
    tool_log.append("TOOL: check_escalation_rules(...)")

    return {
        "customer_profile": customer_profile,
        "customer_profile_full": customer_profile_full,
        "locker_availability": locker_availability,
        "playbook_context": playbook_context,
        "escalation_signals": escalation_signals,
    }


@traceable(name="preprocessor_node")
def preprocessor_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Deduplicates, consolidates, assembles context, and runs input guardrails."""
    view = project_into(state, RouterView)
    tool_log = []
    trajectory = []
    start = time.time()

    # Step 1: Remove duplicate scan events
    unique_rows = deduplicate_rows(view["raw_rows"])
    tool_log.append("PREPROCESSOR: Deduplicated rows")
    trajectory.append(
        f"preprocessor: {len(view['raw_rows'])} raw rows -> {len(unique_rows)} after dedup"
    )

    # Step 2: Merge multi-row shipments into a single consolidated event
    consolidated = consolidate_event(unique_rows, view["raw_rows"])

    # Step 3: Scan driver notes for prompt injection — block before any LLM call
    if scan_inputs_for_injection(consolidated, view["raw_rows"]):
        tool_log.append("GUARDRAIL: Injection detected in delivery input")
        trajectory.append("preprocessor: Guardrail triggered - prompt injection detected")
        output = {
            "consolidated_event": consolidated,
            "customer_profile": {},
            "customer_profile_full": {},
            "locker_availability": [],
            "playbook_context": [],
            "escalation_signals": {},
            "tool_calls_log": tool_log,
            "trajectory_log": trajectory,
            "resolution_revision_count": 0,
            "critic_feedback": "",
            "noise_override": False,
            "guardrail_triggered": True,
            "escalated": True,
            "start_time": start,
            "next_agent": "finalize",
            "escalation_reason": "Input Guardrail Triggered",
        }
        return merge_back(state, output, RouterView)

    # Step 4: Check for routine noise before making any tool calls
    noise_override = check_noise_override(consolidated)
    if noise_override:
        tool_log.append("PREPROCESSOR: Noise guardrail - routine status with no anomaly")
        trajectory.append(
            f"preprocessor: {consolidated['status_code']} flagged as noise by guardrail, "
            "skipping tool calls"
        )
        output = {
            "consolidated_event": consolidated,
            "customer_profile": {},
            "customer_profile_full": {},
            "locker_availability": [],
            "playbook_context": [],
            "escalation_signals": {},
            "tool_calls_log": tool_log,
            "trajectory_log": trajectory,
            "resolution_revision_count": 0,
            "critic_feedback": "",
            "noise_override": True,
            "guardrail_triggered": False,
            "escalated": False,
            "start_time": start,
            "next_agent": "orchestrator",
            "escalation_reason": None,
        }
        return merge_back(state, output, RouterView)

    # Step 5: Fetch context via tools (only for non-noise cases)
    context = fetch_context(consolidated, tool_log)

    # Step 6: Scan retrieved playbook chunks for injection
    if scan_chunks_for_injection(context["playbook_context"]):
        tool_log.append("GUARDRAIL: Injection detected in retrieved playbook chunk")
        trajectory.append("preprocessor: Guardrail triggered - injection in RAG chunk")
        context["playbook_context"] = []  # Drop contaminated chunks
        output = {
            "consolidated_event": consolidated,
            **context,
            "tool_calls_log": tool_log,
            "trajectory_log": trajectory,
            "resolution_revision_count": 0,
            "critic_feedback": "",
            "noise_override": False,
            "guardrail_triggered": True,
            "escalated": True,
            "start_time": start,
            "next_agent": "finalize",
            "escalation_reason": "RAG Chunk Injection Detected",
        }
        return merge_back(state, output, RouterView)

    # Package all context and pass to orchestrator
    output = {
        "consolidated_event": consolidated,
        **context,
        "tool_calls_log": tool_log,
        "trajectory_log": trajectory,
        "resolution_revision_count": 0,
        "critic_feedback": "",
        "noise_override": noise_override,
        "guardrail_triggered": False,
        "escalated": False,
        "start_time": start,
        "next_agent": "orchestrator",
        "escalation_reason": None,
    }
    return merge_back(state, output, RouterView)
