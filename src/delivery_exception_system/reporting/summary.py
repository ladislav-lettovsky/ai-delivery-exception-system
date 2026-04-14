"""Compact shipment evaluation summary — tabular row output."""

import pandas as pd


def shipment_summary(sid: str, result: dict, gt: dict, print_header: bool = False):
    """Print a compact one-line summary row for a shipment."""
    col_w = {
        "sid": 9, "exc": 6, "res": 18, "tone": 8, "esc": 5,
        "task": 6, "tools": 6, "coh": 10, "lat": 4,
    }
    header = (
        f"{'Shipment':<{col_w['sid']}} "
        f"| "
        f"{'GT Exc':>{col_w['exc']}} "
        f"{'Resolution':<{col_w['res']}} "
        f"{'Tone':<{col_w['tone']}} "
        f"{'Esc':>{col_w['esc']}} "
        f"| "
        f"{'Pred Exc':>{col_w['exc']}} "
        f"{'Resolution':<{col_w['res']}} "
        f"{'Tone':<{col_w['tone']}} "
        f"{'Esc':>{col_w['esc']}} "
        f"| "
        f"{'Task':>{col_w['task']}} "
        f"{'Tools':>{col_w['tools']}} "
        f"{'Coherance':>{col_w['coh']}} "
        f"{'\u23f1':>{col_w['lat']}} "
    )
    divider = "\u2500" * len(header)
    if print_header:
        print(header)
        print(divider)

    state = result["state"]
    tc = result["task_completion"]
    res = state.get("resolution_output", {})
    comm = state.get("communication_output", {})

    def gtv_simple(val):
        return "N/A" if pd.isna(val) else str(val)

    is_esc = state.get("escalated", False)

    gt_exc = gtv_simple(gt.get("is_exception", "N/A"))
    gt_res = gtv_simple(gt.get("expected_resolution", "N/A"))
    gt_tone = gtv_simple(gt.get("expected_tone", "N/A"))
    gt_esc = gtv_simple(gt.get("should_escalate", "N/A"))

    pr_exc = res.get("is_exception", "N/A")
    pr_res = str(res.get("resolution", "N/A"))
    pr_tone = comm.get("tone_label", "N/A")
    pr_esc = "N/A" if (gt_esc == "N/A" and not is_esc) else ("YES" if is_esc else "NO")

    task = "\u2713" if tc.get("task_complete") else "\u2717"
    tools = "\u2713" if result.get("tool_call_correct") else "\u2717"
    coh = result["coherence"]["score"]
    lat = f"{result['latency']:>4.0f}s"

    print(
        f"{sid:<{col_w['sid']}} "
        f"| "
        f"{gt_exc:>{col_w['exc']}} "
        f"{gt_res:<{col_w['res']}} "
        f"{gt_tone:<{col_w['tone']}} "
        f"{gt_esc:>{col_w['esc']}} "
        f"|   "
        f"{pr_exc:>{col_w['exc']}} "
        f"{pr_res:<{col_w['res']}} "
        f"{pr_tone:<{col_w['tone']}} "
        f"{pr_esc:>{col_w['esc']}} "
        f"| "
        f"{task:>{col_w['task']}} "
        f"{tools:>{col_w['tools']}} "
        f"{coh:>{col_w['coh']-2}}/5 "
        f"{lat:>{col_w['lat']}}"
    )
