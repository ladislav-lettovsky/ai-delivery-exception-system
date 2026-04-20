"""Agent state definitions and PII access control views."""

from dataclasses import dataclass, fields
from typing import TypedDict


class UnifiedAgentState(TypedDict):
    """State object passed through the LangGraph pipeline."""

    # Input
    raw_rows: list[dict]
    shipment_id: str

    # Preprocessor output
    consolidated_event: dict
    customer_profile: dict
    customer_profile_full: dict
    locker_availability: list[dict]
    playbook_context: list[dict]
    escalation_signals: dict
    noise_override: bool
    guardrail_triggered: bool

    # Resolution Agent output
    resolution_output: dict

    # Critic — resolution validation
    critic_resolution_output: dict
    resolution_revision_count: int
    critic_feedback: str

    # Communication Agent output
    communication_output: dict

    # Critic — communication validation
    critic_communication_output: dict

    # Routing
    next_agent: str
    max_loops: int

    # Final
    escalated: bool
    escalation_reason: str  # FIX: was used but never declared in original
    tool_calls_log: list[str]
    trajectory_log: list[str]
    start_time: float | None
    latency_sec: float | None
    final_actions: list[dict]


# ---------------------------------------------------------------------------
# View dataclasses — field-level PII access control
# ---------------------------------------------------------------------------


@dataclass
class RouterView:
    """Fields accessible to the Router Agent (preprocessor, orchestrator, finalize)."""

    raw_rows: list[dict]
    shipment_id: str
    consolidated_event: dict
    customer_profile: dict
    customer_profile_full: dict
    locker_availability: list[dict]
    playbook_context: list[dict]
    escalation_signals: dict
    noise_override: bool
    guardrail_triggered: bool
    resolution_output: dict
    critic_resolution_output: dict
    resolution_revision_count: int
    critic_feedback: str
    communication_output: dict
    critic_communication_output: dict
    next_agent: str
    max_loops: int
    escalated: bool
    escalation_reason: str | None
    tool_calls_log: list[str]
    trajectory_log: list[str]
    start_time: float | None
    latency_sec: float | None
    final_actions: list[dict]


@dataclass
class ResolutionAgentView:
    """Fields accessible to the Resolution Agent. No PII."""

    consolidated_event: dict
    customer_profile: dict  # Redacted — no name
    locker_availability: list[dict]
    playbook_context: list[dict]
    escalation_signals: dict
    critic_feedback: str
    resolution_output: dict


@dataclass
class CommunicationAgentView:
    """Fields accessible to the Communication Agent. Includes PII for personalization."""

    consolidated_event: dict
    customer_profile_full: dict  # Includes name — only agent with PII access
    locker_availability: list[dict]
    resolution_output: dict
    communication_output: dict


@dataclass
class CriticResolutionView:
    """Fields accessible to the Critic Agent for resolution validation. No PII."""

    consolidated_event: dict
    customer_profile: dict  # Redacted — no name
    locker_availability: list[dict]
    playbook_context: list[dict]
    escalation_signals: dict
    resolution_output: dict
    critic_resolution_output: dict


@dataclass
class CriticCommunicationView:
    """Fields accessible to the Critic Agent for communication validation. No PII."""

    consolidated_event: dict
    customer_profile: dict  # Redacted — no name
    resolution_output: dict
    communication_output: dict
    critic_communication_output: dict


# ---------------------------------------------------------------------------
# State projection utilities
# ---------------------------------------------------------------------------


def project_into(state: UnifiedAgentState, view_class: type) -> dict:
    """Extract only the fields defined in the agent's view from the global state."""
    view_fields = {f.name for f in fields(view_class)}
    return {k: state.get(k) for k in view_fields if k in state}


def merge_back(state: UnifiedAgentState, agent_output: dict, view_class: type) -> UnifiedAgentState:
    """Write back only the fields owned by the agent's view into the global state."""
    view_fields = {f.name for f in fields(view_class)}
    for k, v in agent_output.items():
        if k in view_fields:
            state[k] = v
    return state
