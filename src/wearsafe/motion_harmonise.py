"""Harmonised motion format (config/motion_harmonisation_v1.yaml, config/fallalld_v1.yaml), D08.

One code path for both versions; the e4 steps (clip at native rate, re-clip, quantise) are switched on only for
version "e4_clipped". All functions are pure and never modify their inputs.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import resample_poly

G = 9.80665
E4_LO_COUNTS, E4_HI_COUNTS, E4_COUNTS_PER_G = -128, 127, 64
E4_LO_G, E4_HI_G = E4_LO_COUNTS / E4_COUNTS_PER_G, E4_HI_COUNTS / E4_COUNTS_PER_G      # -2.0, +1.984375
FALLALLD_RAIL_G = 32767 / 4096


def counts_to_g(counts: np.ndarray, counts_per_g: float) -> np.ndarray:
    return np.asarray(counts, dtype=np.float64) / counts_per_g


def resample_238_to_32(x_g: np.ndarray, up: int = 16, down: int = 119, beta: float = 5.0,
                       padtype: str = "line") -> np.ndarray:
    """Polyphase anti-aliased resampling along axis 0 (Kaiser-windowed FIR low-pass at the new Nyquist)."""
    return resample_poly(np.asarray(x_g, dtype=np.float64), up, down, axis=0, window=("kaiser", beta),
                         padtype=padtype)


def e4_clip(x_g: np.ndarray) -> np.ndarray:
    return np.clip(x_g, E4_LO_G, E4_HI_G)


def e4_quantise(x_g: np.ndarray) -> np.ndarray:
    """Round to the E4 1/64 g grid and limit to the int8 rails; returns integer counts."""
    return np.clip(np.round(x_g * E4_COUNTS_PER_G), E4_LO_COUNTS, E4_HI_COUNTS).astype(np.int64)


def harmonise(counts: np.ndarray, version: str, counts_per_g: float, resample_kw: dict | None = None) -> dict:
    """counts (n, 3) at 238 Hz -> {'acc_m_s2': (m, 3) at 32 Hz, 'sat_axes': (m, 3) bool}."""
    kw = resample_kw or {}
    g = counts_to_g(counts, counts_per_g)
    if version == "unclipped":
        out = resample_238_to_32(g, **kw)
        sat = np.abs(out) >= FALLALLD_RAIL_G
        return {"acc_m_s2": out * G, "sat_axes": sat}
    if version == "e4_clipped":
        out = e4_clip(resample_238_to_32(e4_clip(g), **kw))
        c = e4_quantise(out)
        sat = (c == E4_LO_COUNTS) | (c == E4_HI_COUNTS)
        return {"acc_m_s2": c / E4_COUNTS_PER_G * G, "sat_axes": sat}
    raise ValueError(f"unknown version {version!r}")


def gravity_check(records_counts, counts_per_g: float, seg: int = 238, std_lt: float = 0.01,
                  range_lt: float = 0.05) -> dict:
    """Per-record median |a| (g) over low-motion 1 s segments; returns per-record medians and counts."""
    per_record, n_segments = [], 0
    for counts in records_counts:
        mag = np.sqrt((counts_to_g(counts, counts_per_g) ** 2).sum(axis=1))
        n = len(mag) // seg
        segs = mag[: n * seg].reshape(n, seg)
        quiet = (segs.std(axis=1) < std_lt) & ((segs.max(axis=1) - segs.min(axis=1)) < range_lt)
        if quiet.any():
            per_record.append(float(np.median(segs[quiet])))
            n_segments += int(quiet.sum())
        else:
            per_record.append(np.nan)
    arr = np.array(per_record)
    ok = arr[np.isfinite(arr)]
    return {"per_record": arr, "n_records": int(len(ok)), "n_segments": n_segments,
            "median_g": float(np.median(ok)) if len(ok) else np.nan}
