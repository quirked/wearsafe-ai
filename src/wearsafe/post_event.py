"""A01 post-event heart-rate measures (config/a01_post_event_hr.yaml). Analysis only — never a model feature.

All functions take window END times `ends` (s), per-window values, and a per-window `reliable` mask.
"""
from __future__ import annotations

import numpy as np


def recovery(ends, reliable, ta, max_s=120.0):
    """(recovery_time_s, e_rec) for the first reliable window with ta < end <= ta + max_s; (nan, nan) if none."""
    ends, reliable = np.asarray(ends, float), np.asarray(reliable, bool)
    m = reliable & (ends > ta) & (ends <= ta + max_s)
    if not m.any():
        return np.nan, np.nan
    e = float(ends[m].min())
    return e - ta, e


def window_median(ends, values, mask, lo, hi):
    """Median of values for windows with end in [lo, hi] and mask True; nan if none."""
    ends, values, mask = np.asarray(ends, float), np.asarray(values, float), np.asarray(mask, bool)
    m = mask & (ends >= lo) & (ends <= hi) & np.isfinite(values)
    return float(np.median(values[m])) if m.any() else np.nan


def event_measures(ends, hr_wrist, reliable, hr_ecg, ta, max_s=120.0):
    rt, e = recovery(ends, reliable, ta, max_s)
    allw = np.ones(len(ends), bool)
    pre_w = window_median(ends, hr_wrist, reliable, ta - 60, ta - 5)
    pre_e = window_median(ends, hr_ecg, allw, ta - 60, ta - 5)
    post_w = window_median(ends, hr_wrist, reliable, e, e + 30) if np.isfinite(e) else np.nan
    post_e = window_median(ends, hr_ecg, allw, e, e + 30) if np.isfinite(e) else np.nan
    post_e_fixed = window_median(ends, hr_ecg, allw, ta, ta + 30)
    return {"recovery_s": rt, "recovered": bool(np.isfinite(rt)), "pre_wrist": pre_w, "post_wrist": post_w,
            "change_wrist": post_w - pre_w, "pre_ecg": pre_e, "post_ecg": post_e, "change_ecg": post_e - pre_e,
            "change_ecg_fixed30": post_e_fixed - pre_e}
