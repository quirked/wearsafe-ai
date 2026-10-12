"""FallAllD window table and labels (D08; config/fallalld_v1.yaml). Index references into the 32 Hz Layer A.

Roles (user decisions on the D08 plan):
  fall clip, window starting at 9 s  -> fall_positive        / abrupt_event_proxy / train_candidate
  fall clip, any other window        -> fall_clip_context    / (no class)         / excluded_ambiguous
  ADL clip, IDs 15 and 23            -> hard_negative_probe  / normal_adl         / hard_negative_probe
  ADL clip, other IDs                -> adl                  / normal_adl         / train_candidate
Identical procedure for every clip; window_start is a forbidden feature column.
"""
from __future__ import annotations

import pandas as pd

from wearsafe import windowing as wn


def record_windows(record: dict, cfg: dict, fs: int, n_samples: int) -> pd.DataFrame:
    w = cfg["windows"]
    probes = set(cfg.get("probe_ids", [15, 23]))
    pos = set(float(s) for s in w["positive_window_start_s"])
    matched = set(float(s) for s in w["position_matched_subset_start_s"])
    rows = []
    for k, (s, e) in enumerate(wn.window_bounds(n_samples / fs, w["length_s"], w["step_s"])):
        i0, i1 = wn.sample_range(s, e, fs)
        start = float(s)
        if record["kind"] == "fall":
            role = "fall_positive" if start in pos else "fall_clip_context"
        else:
            role = "hard_negative_probe" if int(record["activity_id"]) in probes else "adl"
        rows.append({
            "window_id": f"{record['record_id']}_W{k:02d}", "dataset": "fallalld",
            "subject_id": record["subject_id"], "record_id": record["record_id"],
            "activity_id": int(record["activity_id"]), "trial_no": int(record["trial_no"]),
            "original_label": record["original_label"], "kind": record["kind"],
            "window_start": start, "window_end": float(e), "i0": i0, "i1": i1, "window_role": role,
            "motion_event_class": {"fall_positive": "abrupt_event_proxy", "fall_clip_context": None}.get(role, "normal_adl"),
            "eval_role": {"fall_positive": "train_candidate", "adl": "train_candidate",
                          "fall_clip_context": "excluded_ambiguous", "hard_negative_probe": "hard_negative_probe"}[role],
            "position_matched": start in matched,
            "contains_impact_time": start <= w["impact_time_s"] < float(e),
        })
    return pd.DataFrame(rows)
