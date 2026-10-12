"""Fusion v1 candidates (config/fusion_v1.yaml; demo_v1, PRELIMINARY). Pure functions shared by offline F02 and a
later streaming use. Only data up to the decision time are used; 'change' and 'stillness' decisions are delayed until
5 s after the alarm window (latency +5 s).
"""
from __future__ import annotations

import numpy as np

from wearsafe import features as F
from wearsafe import fusion

STD_FLOOR, FREQ_FLOOR = 0.05, 0.5


def change_measures(acc: np.ndarray, t_end: int, fs: int = 32) -> dict:
    """acc: (n, 3) m/s^2 of one recording/clip; t_end: alarm-window end in samples. Pre [t_end-12 s, t_end-2 s) (>= 5 s),
    post [t_end, t_end+5 s). Returns std/dominant frequency of |a| for both segments and validity flags."""
    pre0, pre1, post1 = max(0, t_end - 12 * fs), t_end - 2 * fs, t_end + 5 * fs
    out = {"pre_ok": pre1 - pre0 >= 5 * fs, "post_ok": post1 <= len(acc)}
    for name, (a, b), ok in (("pre", (pre0, pre1), out["pre_ok"]), ("post", (t_end, post1), out["post_ok"])):
        if ok:
            seg = acc[a:b]
            f = F.motion_features(seg, fs, np.zeros(len(seg), bool))
            out[f"std_{name}"], out[f"f_{name}"] = f["acc_mag_std"], f["dominant_freq"]
        else:
            out[f"std_{name}"], out[f"f_{name}"] = np.nan, np.nan
    return out


def is_change(m: dict, tol: float) -> bool:
    if not (m["pre_ok"] and m["post_ok"]):
        return False
    ds = abs(m["std_post"] - m["std_pre"]) / max(m["std_pre"], STD_FLOOR)
    df = abs(m["f_post"] - m["f_pre"]) / max(m["f_pre"], FREQ_FLOOR)
    return bool(ds > tol or df > tol)


def candidates(variant: str, p, T, T_high=None, change=None, still=None):
    """(candidate alarm mask, added latency in s) per decision second."""
    p = np.asarray(p, dtype=float)
    alarm = p >= np.asarray(T, dtype=float)
    if variant in ("V0-base", "V1-merge"):
        return alarm, np.zeros(len(p))
    if variant == "V0-stillness":
        return alarm & np.asarray(still, dtype=bool), np.full(len(p), 5.0)
    if variant == "V1-change":
        return alarm & np.asarray(change, dtype=bool), np.full(len(p), 5.0)
    if variant in ("V1-tiered", "V1-combined"):
        hi = p >= T_high
        return hi | (alarm & np.asarray(change, dtype=bool)), np.where(hi, 0.0, 5.0)
    raise ValueError(variant)


def decide(variant, t, p, T, T_high=None, change=None, still=None, refractory_s: float = 30.0):
    """Prompts (bool) and added latency per decision second; refractory keyed on the alarm time (as v0).
    V1-merge / V1-combined: a new alarm cannot start a prompt while a prompt is open or within 30 s after one
    (15 s countdown + 15 s cooldown) -- the same as the 30 s refractory."""
    cand, lat = candidates(variant, p, T, T_high, change, still)
    return fusion.prompts(np.asarray(t, dtype=float), cand, refractory_s), lat
