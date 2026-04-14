"""Deterministic escalation rule engine — SINGLE SOURCE OF TRUTH.

Both the @tool wrapper (for LangChain preprocessing) and the bare
should_escalate() function (for finalize and evaluation) live here.
"""

import re

from langchain_core.tools import tool


def should_escalate(
    customer_tier: str,
    exceptions_last_90d: int,
    attempt_number: int,
    package_type: str,
    status_code: str,
    status_description: str,
) -> dict:
    """Evaluate deterministic escalation rules. Returns triggers dict.

    This is the single source of truth for all escalation decisions.
    """
    triggers = []

    # --- Automatic triggers ---

    if attempt_number >= 3:
        triggers.append("AUTOMATIC: 3rd failed delivery attempt")

    if customer_tier == "VIP" and exceptions_last_90d >= 3:
        triggers.append(
            f"AUTOMATIC: VIP customer with {exceptions_last_90d} exceptions in 90d (>=3)"
        )

    if status_code == "DAMAGED" and package_type == "PERISHABLE":
        triggers.append("AUTOMATIC: Damaged perishable package")

    if status_code == "WEATHER_DELAY" and package_type == "PERISHABLE":
        hour_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*(?:hr|hour|hours)", status_description.lower()
        )
        if hour_matches:
            hours = float(hour_matches[0])
            if hours > 4:
                triggers.append(
                    f"AUTOMATIC: Perishable with {hours}hr delay (>4hr threshold)"
                )

    fraud_keywords = ["vacant", "demolished", "construction site", "empty lot"]
    if status_code == "ADDRESS_ISSUE" and any(
        kw in status_description.lower() for kw in fraud_keywords
    ):
        triggers.append("AUTOMATIC: Potential fraud - address is vacant/demolished")

    # --- Discretionary triggers ---

    if customer_tier == "STANDARD" and exceptions_last_90d > 5:
        triggers.append(
            f"DISCRETIONARY: Standard customer with {exceptions_last_90d} exceptions in 90d (>5)"
        )

    if (
        customer_tier == "PREMIUM"
        and package_type == "PERISHABLE"
        and status_code == "WEATHER_DELAY"
    ):
        triggers.append(
            "DISCRETIONARY: Premium customer with perishable in weather delay"
        )

    return {
        "has_triggers": len(triggers) > 0,
        "trigger_count": len(triggers),
        "triggers": triggers,
    }


@tool
def check_escalation_rules(
    customer_tier: str,
    exceptions_last_90d: int,
    attempt_number: int,
    package_type: str,
    status_code: str,
    status_description: str,
) -> dict:
    """Deterministic escalation rule engine. Evaluates hard-coded business rules."""
    return should_escalate(
        customer_tier=customer_tier,
        exceptions_last_90d=exceptions_last_90d,
        attempt_number=attempt_number,
        package_type=package_type,
        status_code=status_code,
        status_description=status_description,
    )
