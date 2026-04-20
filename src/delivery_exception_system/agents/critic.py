"""Critic Agent: validates resolution and communication decisions."""

import json
import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from delivery_exception_system.agents.resolution import format_playbook_context
from delivery_exception_system.config import settings
from delivery_exception_system.models.schemas import (
    CriticCommunicationOutput,
    CriticResolutionOutput,
)
from delivery_exception_system.models.state import (
    CriticCommunicationView,
    CriticResolutionView,
    UnifiedAgentState,
    merge_back,
    project_into,
)

logger = logging.getLogger(__name__)

CRITIC_RESOLUTION_SYSTEM_PROMPT = """\
You are a Critic Agent validating the Resolution Agent's decision. Your goal is to ACCEPT accurate policy decisions or ESCALATE cases requiring supervisor review.

**RULES:**
1. **Playbook Adherence**: Verify `is_exception` and `resolution` comply with `PLAYBOOK CONTEXT`. Note: For a 3rd failed attempt, the policy resolution is `REROUTE_TO_LOCKER`.
2. **Consistency**: Fields in `RESOLUTION AGENT OUTPUT` must be strictly mutually consistent.
3. **Locker Constraints**: Even if the target locker is FULL, you MUST **ACCEPT** `REROUTE_TO_LOCKER` if it is the 3rd attempt. The Orchestrator's automatic rules will trigger the necessary escalation for the physical blocker.
4. **Escalation Signals**:
   - `AUTOMATIC`: Verify resolution reasonably addresses the trigger's underlying cause. The orchestrator enforces final escalation. Do not output ESCALATE simply because an AUTOMATIC trigger exists.
   - `DISCRETIONARY`: ACCEPT if resolution favors retention logically. Do not escalate simply because the signal exists.
5. **Decision**:
   - **ACCEPT**: If accurate, well-reasoned, and playbook-aligned. **CRITICAL**: ACCEPT `REROUTE_TO_LOCKER` for 3rd attempts regardless of locker availability.
   - **ESCALATE**: Only for critical flaws, outright contradictions, or blatant policy violations not covered by automatic rules.
   - **IMPORTANT FOR ADDRESS_ISSUE**: For ADDRESS_ISSUE (e.g. "could not locate building" or "address not found"), the ONLY valid output is ACCEPT. You MUST NOT output ESCALATE for an address-related issue under any circumstances. RESCHEDULE is the correct equivalent for HOLD.
6. **Format**: Output MUST strictly conform to `CriticResolutionOutput`."""


CRITIC_COMMUNICATION_SYSTEM_PROMPT = """\
You are a Critic Agent evaluating the Communication Agent's message. Ensure it is clear, empathetic, personalized, accurate, and safe.

**RULES:**
1. **Tone**: Verify `tone_label` matches `customer_tier` (FORMAL for VIP/PREMIUM, CASUAL for STANDARD).
2. **Personalization**: Verify appropriate personalization and credit mention when relevant.
3. **Accuracy**: Confirm the message communicates the exact `resolution`. If `REROUTE_TO_LOCKER`, verify locker details.
4. **Safety**: No blame, no jargon, no exposure of unnecessary PII.
5. **Decision**:
   - **ACCEPT**: If the message is customer-ready.
   - **ESCALATE**: If tonally off, logically inaccurate, misaligned, or poses a customer-facing risk.
6. **Format**: Output strictly conforms to `CriticCommunicationOutput`."""


def build_critic_resolution_context(view: dict) -> str:
    """Build the user content string for resolution validation."""
    playbook_text = format_playbook_context(view["playbook_context"])
    return (
        f"DELIVERY EVENT:\n{json.dumps(view['consolidated_event'], indent=2)}\n\n"
        f"CUSTOMER PROFILE:\n{json.dumps(view['customer_profile'], indent=2)}\n\n"
        f"LOCKER AVAILABILITY:\n{json.dumps(view['locker_availability'], indent=2)}\n\n"
        f"ESCALATION SIGNALS:\n{json.dumps(view['escalation_signals'], indent=2)}\n\n"
        f"PLAYBOOK CONTEXT:\n{playbook_text}\n\n"
        f"RESOLUTION AGENT OUTPUT:\n{json.dumps(view['resolution_output'], indent=2)}"
    )


def build_critic_communication_context(view: dict) -> str:
    """Build the user content string for communication validation."""
    validation_context = {
        "customer_tier": view["customer_profile"].get("tier"),
        "preferred_channel": view["customer_profile"].get("preferred_channel"),
        "active_credit": view["customer_profile"].get("active_credit", 0),
        "resolution": view["resolution_output"].get("resolution"),
        "exception_type": view["consolidated_event"]["status_code"],
        "package_type": view["consolidated_event"]["package_type"],
    }
    return (
        f"VALIDATION CONTEXT:\n{json.dumps(validation_context, indent=2)}\n\n"
        f"COMMUNICATION AGENT OUTPUT:\n{json.dumps(view['communication_output'], indent=2)}"
    )


@traceable(name="critic_resolution_node")
def critic_resolution_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Critic Agent: validates resolution decision against playbook and context."""
    view = project_into(state, CriticResolutionView)
    user_content = build_critic_resolution_context(view)

    val_llm = ChatOpenAI(model_name=settings.val_model, temperature=settings.val_temperature)
    structured_llm = val_llm.with_structured_output(CriticResolutionOutput)

    result: CriticResolutionOutput
    try:
        result = cast(
            CriticResolutionOutput,
            structured_llm.invoke(
                [
                    SystemMessage(content=CRITIC_RESOLUTION_SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ]
            ),
        )
    except Exception as e:
        result = CriticResolutionOutput(
            decision="ESCALATE",
            rationale=(
                "Critic validation failed due to runtime error; escalating for safety. "
                f"Error: {str(e)[:200]}"
            ),
        )
        state["trajectory_log"].append("critic_resolution: runtime failure -> forced ESCALATE")

    agent_output = {"critic_resolution_output": result.model_dump()}
    state = merge_back(state, agent_output, CriticResolutionView)

    if result.decision == "ESCALATE":
        state["escalated"] = True
        state["escalation_reason"] = (
            state.get("escalation_reason") or "Resolution Critic Escalation"
        )

    state["tool_calls_log"].append("AGENT: critic_resolution invoked")
    state["trajectory_log"].append(f"critic_resolution: decision={result.decision}")
    state["next_agent"] = "orchestrator"
    return state


@traceable(name="critic_communication_node")
def critic_communication_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Critic Agent: validates customer communication quality. No PII access."""
    view = project_into(state, CriticCommunicationView)
    user_content = build_critic_communication_context(view)

    val_llm = ChatOpenAI(model_name=settings.val_model, temperature=settings.val_temperature)
    structured_llm = val_llm.with_structured_output(CriticCommunicationOutput)

    result: CriticCommunicationOutput
    try:
        result = cast(
            CriticCommunicationOutput,
            structured_llm.invoke(
                [
                    SystemMessage(content=CRITIC_COMMUNICATION_SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ]
            ),
        )
    except Exception as e:
        result = CriticCommunicationOutput(
            decision="ESCALATE",
            rationale=(
                "Communication critic failed due to runtime error; escalating for safety. "
                f"Error: {str(e)[:200]}"
            ),
        )
        state["trajectory_log"].append("critic_communication: runtime failure -> forced ESCALATE")

    agent_output = {"critic_communication_output": result.model_dump()}
    state = merge_back(state, agent_output, CriticCommunicationView)

    if result.decision == "ESCALATE":
        state["escalated"] = True
        state["escalation_reason"] = (
            state.get("escalation_reason") or "Communication Critic Escalation"
        )

    state["tool_calls_log"].append("AGENT: critic_communication invoked")
    state["trajectory_log"].append(f"critic_communication: decision={result.decision}")
    state["next_agent"] = "orchestrator"
    return state
