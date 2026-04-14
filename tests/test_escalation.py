"""Tests for the deterministic escalation rule engine."""

from delivery_exception_system.tools.escalation_rules import should_escalate


class TestAutomaticEscalation:
    def test_third_attempt(self):
        result = should_escalate("STANDARD", 0, 3, "STANDARD", "ATTEMPTED_DELIVERY", "3rd attempt failed")
        assert result["has_triggers"]
        assert any("3rd failed" in t for t in result["triggers"])

    def test_vip_three_exceptions(self):
        result = should_escalate("VIP", 3, 1, "STANDARD", "ATTEMPTED_DELIVERY", "First attempt")
        assert result["has_triggers"]
        assert any("VIP" in t for t in result["triggers"])

    def test_damaged_perishable(self):
        result = should_escalate("STANDARD", 0, 1, "PERISHABLE", "DAMAGED", "Severe water damage")
        assert result["has_triggers"]
        assert any("Damaged perishable" in t for t in result["triggers"])

    def test_weather_delay_perishable_over_4hr(self):
        result = should_escalate("STANDARD", 0, 1, "PERISHABLE", "WEATHER_DELAY", "Delay of 5hr due to storm")
        assert result["has_triggers"]
        assert any("5.0hr delay" in t for t in result["triggers"])

    def test_weather_delay_perishable_under_4hr(self):
        result = should_escalate("STANDARD", 0, 1, "PERISHABLE", "WEATHER_DELAY", "Delay of 3hr due to storm")
        assert not result["has_triggers"]

    def test_fraud_address(self):
        result = should_escalate("STANDARD", 0, 1, "STANDARD", "ADDRESS_ISSUE", "Address appears vacant")
        assert result["has_triggers"]
        assert any("fraud" in t.lower() for t in result["triggers"])


class TestDiscretionaryEscalation:
    def test_standard_high_exceptions(self):
        result = should_escalate("STANDARD", 6, 1, "STANDARD", "ATTEMPTED_DELIVERY", "First attempt")
        assert result["has_triggers"]
        assert any("DISCRETIONARY" in t for t in result["triggers"])

    def test_premium_perishable_weather(self):
        result = should_escalate("PREMIUM", 0, 1, "PERISHABLE", "WEATHER_DELAY", "Delay of 2hr")
        assert result["has_triggers"]
        assert any("Premium" in t for t in result["triggers"])


class TestNoEscalation:
    def test_routine_first_attempt(self):
        result = should_escalate("STANDARD", 0, 1, "STANDARD", "ATTEMPTED_DELIVERY", "Customer not home")
        assert not result["has_triggers"]
        assert result["trigger_count"] == 0

    def test_vip_low_exceptions(self):
        result = should_escalate("VIP", 2, 1, "STANDARD", "ATTEMPTED_DELIVERY", "First attempt")
        assert not result["has_triggers"]
