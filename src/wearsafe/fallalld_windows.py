"""FallAllD window table and labels (D08; config/fallalld_v1.yaml). Index references into the 32 Hz Layer A.

Roles (user decisions on the D08 plan):
  fall clip, window starting at 9 s  -> fall_positive        / abrupt_event_proxy / train_candidate
  fall clip, any other window        -> fall_clip_context    / (no class)         / excluded_ambiguous
  ADL clip, IDs 15 and 23            -> hard_negative_probe  / normal_adl         / hard_negative_probe
  ADL clip, other IDs                -> adl                  / normal_adl         / train_candidate
  fall clip listed as label-uncertain -> label_uncertain_fall / (no class)        / excluded_label_uncertain
      (all 19 windows; excluded from training and window-level metrics; still a fall clip in clip-level metrics)
Every window also carries the record's overlap_group_id and dedup_representative (user decision 4).
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
        if record["kind"] == "fall" and record.get("label_uncertain", False):
            role = "label_uncertain_fall"
        elif record["kind"] == "fall":
            role = "fall_positive" if start in pos else "fall_clip_context"
        else:
            role = "hard_negative_probe" if int(record["activity_id"]) in probes else "adl"
        rows.append({
            "window_id": f"{record['record_id']}_W{k:02d}", "dataset": "fallalld",
            "subject_id": record["subject_id"], "record_id": record["record_id"],
            "activity_id": int(record["activity_id"]), "trial_no": int(record["trial_no"]),
            "original_label": record["original_label"], "kind": record["kind"],
            "window_start": start, "window_end": float(e), "i0": i0, "i1": i1, "window_role": role,
            "motion_event_class": {"fall_positive": "abrupt_event_proxy", "fall_clip_context": None,
                                   "label_uncertain_fall": None}.get(role, "normal_adl"),
            "eval_role": {"fall_positive": "train_candidate", "adl": "train_candidate",
                          "fall_clip_context": "excluded_ambiguous", "hard_negative_probe": "hard_negative_probe",
                          "label_uncertain_fall": "excluded_label_uncertain"}[role],
            "clip_level_class": "fall" if record["kind"] == "fall" else "adl",
            "overlap_group_id": record.get("overlap_group_id", record["record_id"]),
            "dedup_representative": bool(record.get("dedup_representative", True)),
            "position_matched": start in matched,
            "contains_impact_time": start <= w["impact_time_s"] < float(e),
        })
    return pd.DataFrame(rows)
