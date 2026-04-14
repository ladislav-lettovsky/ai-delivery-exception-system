"""Tests for state projection and merge utilities."""

from delivery_exception_system.models.state import (
    CommunicationAgentView,
    CriticCommunicationView,
    CriticResolutionView,
    ResolutionAgentView,
    RouterView,
    merge_back,
    project_into,
)


def _make_state():
    """Create a minimal test state."""
    return {
        "raw_rows": [{"shipment_id": "SHP-001"}],
        "shipment_id": "SHP-001",
        "consolidated_event": {"status_code": "DAMAGED"},
        "customer_profile": {"tier": "VIP"},
        "customer_profile_full": {"tier": "VIP", "name": "John Doe"},
        "locker_availability": [],
        "playbook_context": [],
        "escalation_signals": {},
        "noise_override": False,
        "guardrail_triggered": False,
        "resolution_output": {},
        "critic_resolution_output": {},
        "resolution_revision_count": 0,
        "critic_feedback": "",
        "communication_output": {},
        "critic_communication_output": {},
        "next_agent": "resolution_agent",
        "max_loops": 2,
        "escalated": False,
        "escalation_reason": "",
        "tool_calls_log": [],
        "trajectory_log": [],
        "start_time": None,
        "latency_sec": None,
        "final_actions": [],
    }


class TestProjectInto:
    def test_resolution_view_excludes_pii(self):
        state = _make_state()
        view = project_into(state, ResolutionAgentView)
        assert "customer_profile" in view
        assert "customer_profile_full" not in view

    def test_communication_view_includes_pii(self):
        state = _make_state()
        view = project_into(state, CommunicationAgentView)
        assert "customer_profile_full" in view
        assert view["customer_profile_full"]["name"] == "John Doe"

    def test_critic_resolution_view_no_pii(self):
        state = _make_state()
        view = project_into(state, CriticResolutionView)
        assert "customer_profile" in view
        assert "customer_profile_full" not in view

    def test_critic_communication_view_no_pii(self):
        state = _make_state()
        view = project_into(state, CriticCommunicationView)
        assert "customer_profile" in view
        assert "customer_profile_full" not in view

    def test_router_view_full_access(self):
        state = _make_state()
        view = project_into(state, RouterView)
        assert "customer_profile_full" in view
        assert "raw_rows" in view


class TestMergeBack:
    def test_merges_only_view_fields(self):
        state = _make_state()
        output = {
            "resolution_output": {"is_exception": "YES"},
            "some_random_field": "should_not_merge",
        }
        merged = merge_back(state, output, ResolutionAgentView)
        assert merged["resolution_output"] == {"is_exception": "YES"}
        assert "some_random_field" not in merged

    def test_does_not_overwrite_unrelated_fields(self):
        state = _make_state()
        state["escalated"] = False
        output = {"resolution_output": {"is_exception": "NO"}}
        merged = merge_back(state, output, ResolutionAgentView)
        assert merged["escalated"] is False  # Unchanged
