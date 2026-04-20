"""Resolution Agent: classifies exceptions and decides resolution actions."""

import json
import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from delivery_exception_system.config import settings
from delivery_exception_system.models.schemas import ResolutionOutput
from delivery_exception_system.models.state import (
    ResolutionAgentView,
    UnifiedAgentState,
    merge_back,
    project_into,
)

logger = logging.getLogger(__name__)

RESOLUTION_AGENT_SYSTEM_PROMPT = """\
You are a Delivery Exception Resolution Agent. Determine if an event is an actionable exception (`is_exception: "YES"`) or routine noise (`is_exception: "NO"`).
Propose resolutions: "RESCHEDULE", "REROUTE_TO_LOCKER", "REPLACE", "RETURN_TO_SENDER" or "N/A" (if NO exception).

**RULES:**
1. **Playbook**: Strictly adhere to `RELEVANT PLAYBOOK SECTIONS` and explicitly cite page numbers.
2. **Customer Tier**: Prioritize RESCHEDULE and retention for VIP/PREMIUM over RETURNS unless unresolvable.
3. **Escalations**: AUTOMATIC triggers strongly imply an exception needing customer-friendly resolution. DISCRETIONARY urges retention.
4. **Specifics**: DAMAGED -> REPLACE. DELAYED PERISHABLE ITEM -> REPLACE. REFUSED -> RETURN_TO_SENDER. ATTEMPTED -> RESCHEDULE. First-time ADDRESS_ISSUE -> RESCHEDULE. 3rd Attempt -> REROUTE_TO_LOCKER.
5. **Schema constraints**: Output strictly matches `ResolutionOutput`. Maintain mutual consistency between `is_exception` and `resolution`.
6. **Rationale**: Provide clear step-by-step reasoning referencing rules. If playbook requires HOLD for ADDRESS_ISSUE, output RESCHEDULE and state you are holding for contact. If the playbook dictates escalation (e.g. VIP >= 3 exceptions), explicitly acknowledge in the rationale that the Orchestrator will automatically handle the escalation.

**CRITIC FEEDBACK:**
{critic_feedback}

If `critic_feedback` is present, it means your previous attempt was rejected. Incorporate the feedback to revise your decision and rationale.
If no `critic_feedback` is provided, proceed with initial resolution."""


def format_playbook_context(playbook: list[dict]) -> str:
    """Format playbook chunks with page references for LLM context."""
    return "\n\n---\n\n".join([f"[Page {c['page']}] {c['content']}" for c in playbook])


@traceable(name="resolution_agent_node")
def resolution_agent_node(state: UnifiedAgentState) -> UnifiedAgentState:
    """Resolution Agent: classifies exception and decides resolution action."""
    view = project_into(state, ResolutionAgentView)

    feedback = view.get("critic_feedback", "")
    feedback_section = ""
    if feedback:
        escaped_feedback = feedback.replace("{", "{{").replace("}", "}}")
        feedback_section = (
            f"\n\nPREVIOUS ATTEMPT WAS REJECTED. Critic feedback:\n{escaped_feedback}\n"
            f"Revise your decision based on this feedback."
        )

    system_prompt = RESOLUTION_AGENT_SYSTEM_PROMPT.format(critic_feedback=feedback_section)

    playbook_text = format_playbook_context(view["playbook_context"])

    user_content = (
        f"DELIVERY EVENT:\n{json.dumps(view['consolidated_event'], indent=2)}\n\n"
        f"CUSTOMER PROFILE (redacted):\n{json.dumps(view['customer_profile'], indent=2)}\n\n"
        f"LOCKER AVAILABILITY:\n{json.dumps(view['locker_availability'], indent=2)}\n\n"
        f"ESCALATION SIGNALS:\n{json.dumps(view['escalation_signals'], indent=2)}\n\n"
        f"RELEVANT PLAYBOOK SECTIONS:\n{playbook_text}"
    )

    gen_llm = ChatOpenAI(model_name=settings.gen_model, temperature=settings.gen_temperature)
    structured_llm = gen_llm.with_structured_output(ResolutionOutput)
    max_retries = max(1, settings.max_retries)
    result: ResolutionOutput | None = None

    for attempt in range(max_retries):
        try:
            result = cast(
                ResolutionOutput,
                structured_llm.invoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_content),
                    ]
                ),
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                state["trajectory_log"].append(
                    f"resolution_agent: Validation failed (attempt {attempt + 1}), "
                    f"retrying - {str(e)[:100]}"
                )
            else:
                result = ResolutionOutput(
                    is_exception="YES",
                    resolution="RESCHEDULE",
                    rationale=(
                        f"Resolution agent failed after {max_retries} attempts. "
                        f"Defaulting to RESCHEDULE with escalation. Last error: {str(e)[:200]}"
                    ),
                )
                state["escalated"] = True
                state["trajectory_log"].append(
                    f"resolution_agent: All {max_retries} retries exhausted, "
                    f"defaulting to RESCHEDULE with forced escalation"
                )

    assert result is not None
    agent_output = {"resolution_output": result.model_dump()}
    state = merge_back(state, agent_output, ResolutionAgentView)

    state["tool_calls_log"].append("AGENT: resolution_agent invoked")
    state["trajectory_log"].append(
        f"resolution_agent: is_exception={result.is_exception}, resolution={result.resolution}"
    )
    state["next_agent"] = "orchestrator"
    return state
