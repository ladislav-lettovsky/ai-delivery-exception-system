"""Communication Agent: generates customer notifications."""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from delivery_exception_system.config import settings
from delivery_exception_system.models.schemas import CommunicationOutput
from delivery_exception_system.models.state import (
    CommunicationAgentView,
    UnifiedAgentState,
    merge_back,
    project_into,
)

logger = logging.getLogger(__name__)

COMMUNICATION_AGENT_SYSTEM_PROMPT = """\
You are a Customer Communication Agent. Generate personalized, clear, empathetic notifications based on the delivery exception `CONTEXT`.

**RULES:**
1. **Tone**: Match `tone_label` to tier (FORMAL for VIP/PREMIUM, CASUAL for STANDARD).
2. **Personalization**: Greet with `customer_name`. Tailor content using `customer_tier`, `preferred_channel`, and apply `active_credit` if appropriate.
3. **Clarity/Empathy**: Explain exception, state exact `resolution` determined by Resolution Agent without jargon or blame. Acknowledge inconvenience.
4. **Resolution specifics**: If `REROUTE_TO_LOCKER` and `LOCKER AVAILABILITY` is true, include locker details from `LOCKER FOR REROUTE`. If `LOCKER AVAILABILITY` is false, explain that we are attempting to reroute to a locker but it is currently full, so we will hold the package pending availability. If `ADDRESS_ISSUE`, politely ask the customer for address clarification.
5. **Format**: Output MUST strictly conform to `CommunicationOutput` Pydantic json schema."""


def build_communication_context(view: dict) -> tuple[dict, str]:
    """Build the context dict and locker info string for the Communication Agent."""
    event = view["consolidated_event"]
    profile = view["customer_profile_full"]
    resolution = view["resolution_output"]
    lockers = view["locker_availability"]

    locker_info = ""
    if resolution.get("resolution") == "REROUTE_TO_LOCKER":
        eligible = [loc for loc in lockers if loc.get("eligible")]
        if eligible:
            locker_info = f"\nLOCKER FOR REROUTE:\n{json.dumps(eligible[0], indent=2)}"

    comm_context = {
        "customer_name": profile.get("name", "Customer"),
        "customer_tier": profile.get("tier"),
        "preferred_channel": profile.get("preferred_channel"),
        "active_credit": profile.get("active_credit", 0),
        "exception_type": event["status_code"],
        "status_description": event["status_description"],
        "package_type": event["package_type"],
        "resolution": resolution.get("resolution"),
        "resolution_rationale": resolution.get("rationale"),
    }

    return comm_context, locker_info


@traceable(name="communication_agent_node")
def communication_agent_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Communication Agent: generates customer notification. Only agent with PII access."""
    view = project_into(state, CommunicationAgentView)

    comm_context, locker_info = build_communication_context(view)
    user_content = f"CONTEXT:\n{json.dumps(comm_context, indent=2)}\n{locker_info}"

    gen_llm = ChatOpenAI(model=settings.gen_model, temperature=settings.gen_temperature)
    structured_llm = gen_llm.with_structured_output(CommunicationOutput)
    max_retries = settings.max_retries
    result = None

    for attempt in range(max_retries):
        try:
            result = structured_llm.invoke(
                [
                    SystemMessage(content=COMMUNICATION_AGENT_SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ]
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                state["trajectory_log"].append(
                    f"communication_agent: Validation failed (attempt {attempt + 1}), "
                    f"retrying - {str(e)[:100]}"
                )
            else:
                tier = view["customer_profile_full"].get("tier", "STANDARD")
                result = CommunicationOutput(
                    tone_label="FORMAL" if tier in ("VIP", "PREMIUM") else "CASUAL",
                    communication_message=(
                        "We're aware of an issue with your delivery and are working to "
                        "resolve it. A team member will follow up shortly."
                    ),
                )
                state["escalated"] = True
                state["trajectory_log"].append(
                    f"communication_agent: All {max_retries} retries exhausted, "
                    f"defaulting to generic message with forced escalation"
                )

    agent_output = {"communication_output": result.model_dump()}
    state = merge_back(state, agent_output, CommunicationAgentView)

    state["tool_calls_log"].append("AGENT: communication_agent invoked")
    state["trajectory_log"].append(f"communication_agent: tone={result.tone_label}")
    state["next_agent"] = "orchestrator"
    return state
