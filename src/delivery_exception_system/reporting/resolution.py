"""Detailed shipment resolution report — box-formatted output."""

import re

import pandas as pd


def shipment_resolution(sid: str, result: dict, ground_truth: dict):
    """Print comprehensive shipment resolution summary."""
    state = result["state"]
    event = state.get("consolidated_event") or {}
    cust = state.get("customer_profile") or {}
    lockers = state.get("locker_availability", [])
    esc_sig = state.get("escalation_signals") or {}
    res = state.get("resolution_output") or {}
    critic = state.get("critic_resolution_output") or {}
    comm = state.get("communication_output") or {}
    tc = result["task_completion"]
    coh = result["coherence"]

    def gtv(key):
        v = ground_truth.get(key, "N/A")
        return "N/A" if pd.isna(v) else str(v)

    gt_exc = gtv("is_exception")
    gt_res = gtv("expected_resolution")
    gt_tone = gtv("expected_tone")
    gt_esc = gtv("should_escalate")

    is_noise = state.get("noise_override", False)
    is_guardrail = state.get("guardrail_triggered", False)
    is_escalated = state.get("escalated", False)
    esc_reason = state.get("escalation_reason") or (
        "Automatic Policy Rule(s)" if esc_sig.get("triggers") else ""
    )
    rev_count = state.get("resolution_revision_count", 0)
    latency = result.get("latency", 0.0) or 0.0

    # Lockers
    if not lockers:
        locker_line = "not checked"
    elif any(loc.get("eligible") for loc in lockers):
        loc = next(loc for loc in lockers if loc.get("eligible"))
        locker_line = f"AVAILABLE  {loc['locker_id']} \u00b7 {loc['address']}"
    else:
        reasons = " | ".join(dict.fromkeys(loc.get("reason", "?") for loc in lockers))
        ids = ", ".join(loc["locker_id"] for loc in lockers)
        locker_line = f"UNAVAILABLE  {ids}: {reasons}"

    triggers = esc_sig.get("triggers", [])
    esc_line = " \u00b7 ".join(t.split(": ", 1)[-1] for t in triggers) if triggers else "none"

    # N/A | Pass | Fail
    def NA_PF(b: bool) -> str:
        return "N/A " if b is None else "PASS" if b else "FAIL"

    def clean_traj(entry):
        cleaned = re.sub(r"actions=\{[^}]*(?:\{[^}]*\}[^}]*)?\};?\s*", "", entry)
        return cleaned.strip()

    W = 68
    print(f"\n\u2554{'\u2550' * W}\u2557")
    label = f"  TEST CASE  {sid}"
    if is_guardrail:
        label += "  X GUARDRAIL BLOCKED"
    elif is_noise:
        label += "  \u00b7  NOISE"
    else:
        label += (
            f"  {'\u2713 EXCEPTION' if res.get('is_exception') == 'YES' else '\u25cb NO EXCEPTION'}"
        )
    print(f"\u2551{label:<{W}}\u2551")
    print(f"\u255a{'\u2550' * W}\u255d")

    if event:
        description = event.get("status_description", "")
        print(
            f"\n  EVENT"
            f'\n    Status      {event.get("status_code", "?")}  \u00b7  "{description}"'
            f"\n    Package     {event.get('package_size', '?')}  \u00b7  "
            f"{event.get('package_type', '?')}  \u00b7  Attempt #{int(event.get('attempt_number', 0))}"
        )
        if cust.get("tier"):
            print(
                f"    Customer    {cust.get('tier', '?')} \u00b7 "
                f"{cust.get('preferred_channel', '?')} \u00b7 "
                f"{cust.get('exceptions_last_90d', 0)} exceptions/90d"
            )

    print(f"\n  PIPELINE CONTEXT    Locker      {locker_line}")
    print(f"    Esc signals {esc_line}")
    if is_escalated and esc_reason:
        print(f"    Esc reason  {esc_reason}")

    pred_exc = res.get("is_exception", "N/A")
    pred_res = res.get("resolution", "N/A")
    pred_tone = comm.get("tone_label", "N/A")
    pred_esc = (
        "N/A" if (gt_esc == "N/A" and not is_escalated) else ("YES" if is_escalated else "NO")
    )
    print(
        f"\n  PREDICTIONS vs GROUND TRUTH"
        f"\n    {'Field':<14}  {'Predicted':<18}  {'Ground Truth':<17}  {'Result'}"
        f"\n    {'\u2500' * 14}  {'\u2500' * 18}  {'\u2500' * 17}  {'\u2500' * 6}"
        f"\n    {'Exception':<14}  {pred_exc:<18}  {gt_exc:<17}  {NA_PF(tc['exception_correct'])}"
        f"\n    {'Resolution':<14}  {pred_res:<18}  {gt_res:<17}  {NA_PF(tc['resolution_correct'])}"
        f"\n    {'Tone':<14}  {pred_tone:<18}  {gt_tone:<17}  {NA_PF(tc['tone_correct'])}"
        f"\n    {'Escalated':<14}  {pred_esc:<18}  {gt_esc:<17}  {NA_PF(result['escalation_correct'])}"
    )
    if rev_count:
        print(f"    {'Revisions':<14}  {rev_count:<18}  {'\u2014':<17}")

    if critic.get("decision"):
        print(
            f"\n  CRITIC (resolution)  \u2192  {critic['decision']}"
            f"\n    {critic.get('rationale', '')}"
        )

    if res.get("rationale") and not is_noise and not is_guardrail:
        print(f"\n  RESOLUTION RATIONALE\n    {res['rationale']}")

    print(
        f"\n  METRICS  \u00b7  Task: {NA_PF(tc['task_complete'])}  \u00b7  "
        f"Escalation: {NA_PF(result['escalation_correct'])}  \u00b7  "
        f"Tool Calls: {NA_PF(result['tool_call_correct'])}  \u00b7  "
        f"Coherence: {coh['score']}/5  \u00b7  "
        f"Latency: {latency:.0f}s"
    )
    if coh["score"] < 5:
        print(f"    Coherence justification: {coh.get('justification', '')}")

    traj = [clean_traj(e) for e in state.get("trajectory_log", []) if e.strip()]
    if traj:
        print("\n  TRAJECTORY")
        for entry in traj:
            print(f"    \u2192 {entry}")

    pages = sorted(result.get("citations", set()))
    pages_str = "  \u00b7  ".join(f"p.{p}" for p in pages) if pages else "none"
    print(f"\n  PLAYBOOK CITATIONS  {pages_str}")

    if comm.get("communication_message"):
        msg = comm["communication_message"].strip()
        lines = msg.split("\n")
        print("\n  CUSTOMER MESSAGE")
        for line in lines:
            print(f"    {line}")
