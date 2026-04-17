"""LangGraph workflow construction."""

import logging

from langgraph.graph import END, StateGraph

from delivery_exception_system.agents.communication import communication_agent_node
from delivery_exception_system.agents.critic import (
    critic_communication_node,
    critic_resolution_node,
)
from delivery_exception_system.agents.finalize import finalize_node
from delivery_exception_system.agents.orchestrator import (
    orchestrator_node,
    route_from_orchestrator,
)
from delivery_exception_system.agents.resolution import resolution_agent_node
from delivery_exception_system.models.state import UnifiedAgentState
from delivery_exception_system.preprocessing.preprocessor import preprocessor_node

logger = logging.getLogger(__name__)


def build_graph():
    """Construct and compile the LangGraph workflow. Returns the compiled app."""
    workflow = StateGraph(UnifiedAgentState)  # ty: ignore[invalid-argument-type]

    workflow.add_node("preprocessor", preprocessor_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("resolution_agent", resolution_agent_node)
    workflow.add_node("critic_resolution", critic_resolution_node)
    workflow.add_node("communication_agent", communication_agent_node)
    workflow.add_node("critic_communication", critic_communication_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("preprocessor")

    workflow.add_edge("preprocessor", "orchestrator")
    workflow.add_edge("resolution_agent", "orchestrator")
    workflow.add_edge("critic_resolution", "orchestrator")
    workflow.add_edge("communication_agent", "orchestrator")
    workflow.add_edge("critic_communication", "orchestrator")

    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "resolution_agent": "resolution_agent",
            "critic_resolution": "critic_resolution",
            "communication_agent": "communication_agent",
            "critic_communication": "critic_communication",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("finalize", END)

    app = workflow.compile()
    logger.info("LangGraph compiled successfully")
    return app
