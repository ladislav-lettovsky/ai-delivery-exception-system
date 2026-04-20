"""Orchestrator node: central deterministic router."""

import logging

from langsmith import traceable

from delivery_exception_system.models.state import (
    RouterView,
    UnifiedAgentState,
    project_into,
)

logger = logging.getLogger(__name__)


def route_from_orchestrator(state: UnifiedAgentState) -> str:
    """Determine the next node in the LangGraph workflow based on the agent state."""
    return state.get("next_agent", "finalize")


@traceable(name="orchestrator_node")
def orchestrator_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Central router. Determines next_agent based on current state.

    Routing order:
      0. Guardrail triggered                   -> finalize
      1. Noise override from preprocessor      -> finalize (skip LLM)
      2. Resolution not yet run                -> resolution_agent
      3. Resolution done, critic not yet run   -> critic_resolution
      3.5 Critic returned REVISE               -> resolution_agent (up to max_loops)
      4. Critic returned ESCALATE              -> communication/finalize with escalation flag
      5. Enforce automatic escalation triggers -> rule engine is authoritative
      6. Not an exception                      -> finalize
      7. Communication not yet run             -> communication_agent
      8. Communication done, critic not yet run-> critic_communication
      9. All done                              -> finalize
    """
    view = project_into(state, RouterView)

    # 0. Guardrail triggered — no LLM, force escalation, go to finalize
    if view.get("guardrail_triggered"):
        state["resolution_output"] = {
            "is_exception": "YES",
            "resolution": "RESCHEDULE",
            "rationale": (
                "Input flagged by guardrail - prompt injection detected. "
                "Defaulting to RESCHEDULE with forced escalation for human review."
            ),
        }
        state["escalated"] = True
        if view.get("escalation_reason") == "RAG Chunk Injection Detected":
            state["escalation_reason"] = "RAG Chunk Injection Detected"
        else:
            state["escalation_reason"] = "Input Guardrail Triggered"
        state["next_agent"] = "finalize"
        state["trajectory_log"].append(
            "orchestrator: Guardrail triggered, forcing escalation to finalize"
        )
        return state

    # 1. Noise override — classify as non-exception, skip all agents
    if view.get("noise_override") and not view.get("resolution_output"):
        state["resolution_output"] = {
            "is_exception": "NO",
            "resolution": "N/A",
            "rationale": (
                f"Status code {view['consolidated_event']['status_code']} with routine "
                "description. No anomaly indicators. Classified as noise by preprocessor guardrail."
            ),
        }
        state["trajectory_log"].append(
            "orchestrator: Noise override from preprocessor, skipping to finalize"
        )
        state["next_agent"] = "finalize"
        return state

    # 2. Resolution Agent hasn't run yet
    if not view.get("resolution_output"):
        state["next_agent"] = "resolution_agent"
        return state

    # 3. Resolution done but Critic hasn't validated yet
    if not view.get("critic_resolution_output"):
        state["next_agent"] = "critic_resolution"
        return state

    critic_decision = view["critic_resolution_output"].get("decision")

    # 3.5 Critic returned REVISE — loop back to Resolution Agent (capped by max_loops)
    if critic_decision == "REVISE":
        revision_count = view.get("resolution_revision_count", 0)
        max_loops = view.get("max_loops", 2)
        if revision_count < max_loops:
            state["resolution_revision_count"] = revision_count + 1
            state["critic_feedback"] = view["critic_resolution_output"].get("rationale", "")
            state["resolution_output"] = {}
            state["critic_resolution_output"] = {}
            state["next_agent"] = "resolution_agent"
            state["trajectory_log"].append(
                f"orchestrator: Critic requested REVISE "
                f"(attempt {state['resolution_revision_count']}/{max_loops}), "
                f"routing back to resolution_agent"
            )
            return state
        else:
            state["escalated"] = True
            state["escalation_reason"] = f"Max revision loops ({max_loops}) exceeded without ACCEPT"
            state["trajectory_log"].append(
                f"orchestrator: Max revision loops ({max_loops}) reached, forcing escalation"
            )

    # 4. Critic escalation — preserve escalation signal, still notify customer if needed
    if critic_decision == "ESCALATE":
        state["escalated"] = True
        state["escalation_reason"] = (
            state.get("escalation_reason") or "Resolution Critic Escalation"
        )
        if view["resolution_output"].get("is_exception") == "YES":
            state["next_agent"] = (
                "communication_agent"
                if not view.get("communication_output")
                else (
                    "critic_communication"
                    if not view.get("critic_communication_output")
                    else "finalize"
                )
            )
        else:
            state["next_agent"] = "finalize"
        state["trajectory_log"].append("orchestrator: Critic requested supervisor escalation")
        return state

    # 5. Enforce automatic escalation triggers — rule engine is authoritative
    if view.get("escalation_signals", {}).get("has_triggers"):
        automatic = [
            t for t in view["escalation_signals"].get("triggers", []) if t.startswith("AUTOMATIC")
        ]
        if automatic:
            if view["resolution_output"].get("is_exception") == "NO":
                state["resolution_output"]["is_exception"] = "YES"
                state["resolution_output"]["resolution"] = "RESCHEDULE"
                state["resolution_output"]["rationale"] = (
                    view["resolution_output"].get("rationale", "")
                    + "\nOrchestrator forced is_exception to YES and RESCHEDULE "
                    "due to automatic escalation triggers."
                )
                state["trajectory_log"].append(
                    "orchestrator: Resolution Agent incorrectly classified as NO; "
                    "Orchestrator forced is_exception to YES and RESCHEDULE "
                    "due to automatic triggers."
                )

            state["escalated"] = True
            state["escalation_reason"] = "Automatic Policy Rule(s)"
            state["trajectory_log"].append(
                f"orchestrator: Forced escalation from rule engine - {automatic}"
            )

    # 6. Not an exception — no customer message needed
    if view["resolution_output"].get("is_exception") == "NO":
        state["next_agent"] = "finalize"
        state["trajectory_log"].append("orchestrator: Not an exception, skipping to finalize")
        return state

    # 7. Communication Agent hasn't run yet
    if not view.get("communication_output"):
        state["next_agent"] = "communication_agent"
        return state

    # 8. Communication done but Critic hasn't validated yet
    if not view.get("critic_communication_output"):
        state["next_agent"] = "critic_communication"
        return state

    # 9. Everything complete — finalize
    state["next_agent"] = "finalize"
    return state
