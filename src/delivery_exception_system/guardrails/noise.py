"""Noise override guardrail — filters routine status codes."""

ROUTINE_CODES = {"DELIVERED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "SCANNED"}

ANOMALY_INDICATORS = [
    "damage",
    "wrong",
    "suspicious",
    "overdue",
    "missing",
    "unexpected",
    "misroute",
    "lost",
    "stolen",
    "abandoned",
    "leak",
    "crush",
    "broke",
    "delay",
    "late",
    "fraud",
]


def check_noise_override(consolidated: dict) -> bool:
    """Flag routine status codes with no anomaly indicators."""
    if consolidated["status_code"] not in ROUTINE_CODES:
        return False
    desc = consolidated["status_description"].lower()
    return not any(indicator in desc for indicator in ANOMALY_INDICATORS)
