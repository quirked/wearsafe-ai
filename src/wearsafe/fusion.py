"""Rule-based fusion v0 (config/fusion_v0.yaml; demo_v0, PRELIMINARY). Shared by offline F01 and the streaming engine.

The physiology rule is a PLACEHOLDER, not a trained arousal model.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

G = 9.80665


def load_config(repo: Path) -> dict:
    return yaml.safe_load(open(repo / "config/fusion_v0.yaml"))


def e4_sat_axes(acc_m_s2: np.ndarray) -> np.ndarray:
    """Per-axis E4 saturation: counts (1/64 g) at -128 or +127 (same definition as PPG-DaLiA D02 / FallAllD e4)."""
    c = np.round(np.asarray(acc_m_s2) / G * 64)
    return (c <= -128) | (c >= 127)


def physiology_status(sqi, acc_std_30s, hr_rel, gate: float, cfg: dict | None = None, elevated_bpm: float = 15.0,
                      sqi_thr: float = 0.9):
    """Per 30 s window: uncertain (SQI < 0.9 or acc_mag_std > gate) / elevated (hr_rel >= +15) / unknown (hr_rel NaN) / normal."""
    sqi, acc_std_30s, hr_rel = (np.asarray(x, dtype=float) for x in (sqi, acc_std_30s, hr_rel))
    out = np.where(np.isnan(hr_rel), "unknown", np.where(hr_rel >= elevated_bpm, "elevated", "normal")).astype(object)
    uncertain = ~(sqi >= sqi_thr) | (acc_std_30s > gate)
    out[uncertain] = "uncertain"
    return out


def latest_before(times, values, query, default="unknown"):
    """values[i] of the latest times[i] <= q for each q (times sorted ascending)."""
    times = np.asarray(times, dtype=float)
    idx = np.searchsorted(times, np.asarray(query, dtype=float), side="right") - 1
    vals = np.asarray(values, dtype=object)
    return np.where(idx >= 0, vals[np.clip(idx, 0, None)], default)


def prompts(t, candidate, refractory_s: float) -> np.ndarray:
    """A candidate alarm becomes a prompt if no prompt was created in the previous refractory_s seconds."""
    out = np.zeros(len(t), dtype=bool)
    last = -np.inf
    for i, (ti, c) in enumerate(zip(t, candidate)):
        if c and ti - last >= refractory_s:
            out[i] = True
            last = ti
    return out


def risk_level(prompt: bool, phys_status: str) -> str:
    """NONE / CHECK / HIGH. Physiology never suppresses a motion alarm; context never suppresses (v0)."""
    if not prompt:
        return "NONE"
    return "HIGH" if phys_status == "elevated" else "CHECK"
