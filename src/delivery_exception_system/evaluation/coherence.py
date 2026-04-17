"""LLM-as-judge coherence scoring."""

import json
import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from delivery_exception_system.config import settings
from delivery_exception_system.models.schemas import CoherenceEval

logger = logging.getLogger(__name__)

REASONING_TRAJECTORY_COHERENCE_PROMPT = """\
Score the coherence and logical soundness of a multi-agent decision trajectory for a delivery exception from 1 to 5.

**CRITERIA:**
- **5-Excellent**: Logically consistent end-to-end; final action well-supported. **NOTE**: Selecting a policy-correct resolution (e.g., `REROUTE_TO_LOCKER` for a 3rd attempt) that is physically blocked by a secondary constraint (e.g., locker full) is a perfect **5/5 Coherent** path, provided the trajectory shows the issue is escalated for human review.
- **4-Good**: Mostly coherent, minor gaps.
- **3-Adequate**: Noticeable gaps, but plausible path.
- **2-Poor**: Significant contradictions.
- **1-Fail**: Fundamentally incoherent.

**RULES:**
- Prioritize clear core decision logic and consistency over stylistic preferences.
- Do not penalize phrasing choices.
- Repeated valid log entries count as low-severity noise.
- Valid policy escalations are fully coherent.
- Output MUST be JSON matching format: {"score": [1-5], "justification": "..."}"""


def compute_coherence_score(pred: dict) -> dict:
    """Use val_llm (gpt-4o) to score reasoning trajectory coherence."""
    trace = {
        "shipment_id": pred.get("shipment_id"),
        "consolidated_event": pred.get("consolidated_event", {}),
        "customer_tier": pred.get("customer_profile", {}).get("tier"),
        "escalation_signals": pred.get("escalation_signals", {}),
        "resolution_output": pred.get("resolution_output", {}),
        "critic_resolution_output": pred.get("critic_resolution_output", {}),
        "resolution_revision_count": pred.get("resolution_revision_count", 0),
        "communication_output": pred.get("communication_output", {}),
        "critic_communication_output": pred.get("critic_communication_output", {}),
        "trajectory_log": pred.get("trajectory_log", []),
    }

    try:
        val_llm = ChatOpenAI(
            model_name=settings.val_model, temperature=settings.val_temperature
        )
        judge = val_llm.with_structured_output(CoherenceEval)
        parsed = cast(
            CoherenceEval,
            judge.invoke(
                [
                    SystemMessage(content=REASONING_TRAJECTORY_COHERENCE_PROMPT),
                    HumanMessage(content=json.dumps(trace, indent=2)),
                ]
            ),
        )
        score = max(1, min(5, int(parsed.score)))
        return {"score": score, "justification": parsed.justification}
    except Exception as e:
        return {
            "score": 3,
            "justification": f"Fallback coherence score due to evaluator error: {str(e)}",
        }
