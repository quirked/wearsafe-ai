"""Layer B windowing over sample indices (dataset-agnostic; D02).

Windows are index references into Layer A, not copies of the signal (user decision P7).
All arithmetic is exact (fractions), so window counts and sample ranges have no float drift.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np


def _frac(x) -> Fraction:
    return Fraction(str(x))


def expected_count(duration_s, length_s, step_s) -> int:
    """floor((D - w) / step) + 1, or 0 if the recording is shorter than one window."""
    d, w, st = _frac(duration_s), _frac(length_s), _frac(step_s)
    if d < w:
        return 0
    return int((d - w) // st) + 1


def window_bounds(duration_s, length_s, step_s) -> list[tuple[Fraction, Fraction]]:
    """[start, end) in seconds for every window that fits completely inside [0, duration)."""
    w, st = _frac(length_s), _frac(step_s)
    return [(k * st, k * st + w) for k in range(expected_count(duration_s, length_s, step_s))]


def sample_range(start: Fraction, end: Fraction, fs: int) -> tuple[int, int]:
    """Sample indices [i0, i1) covering [start, end) at rate fs; both must be exact integers."""
    a, b = start * fs, end * fs
    if a.denominator != 1 or b.denominator != 1:
        raise ValueError(f"window [{start}, {end}) is not aligned to {fs} Hz samples")
    return int(a), int(b)


def majority_label(codes: np.ndarray) -> tuple[int, float, int]:
    """(majority code, purity, n_distinct).

    purity = fraction of samples carrying the majority code. Tie rule (config/windowing_v1.yaml):
    among tied codes, take the one carried by the window's LAST sample if it is tied, otherwise the
    tied code that occurs last in the window (most recent state; causal).
    """
    values, counts = np.unique(codes, return_counts=True)
    top = counts.max()
    tied = set(values[counts == top].tolist())
    if len(tied) == 1:
        maj = next(iter(tied))
    else:
        maj = next(int(c) for c in codes[::-1] if int(c) in tied)
    return int(maj), float(top / len(codes)), int(len(values))


def hr_ref_range(start: Fraction, end: Fraction, ref_len_s: int, ref_shift_s: int, n_ref: int) -> tuple[int, int]:
    """Reference windows k (ref_start = k*shift, ref_end = ref_start + len) lying fully inside [start, end).

    Returns [k0, k1); k0 == k1 means none.
    """
    k0 = -(-start // ref_shift_s)                       # ceil(start / shift)
    k1 = (end - ref_len_s) // ref_shift_s + 1           # last k with k*shift + len <= end, +1
    k0, k1 = int(max(k0, 0)), int(min(max(k1, 0), n_ref))
    return k0, max(k0, k1)


def change_times(codes: np.ndarray, fs: int) -> np.ndarray:
    """Times (s) of label changes: t = i/fs where codes[i] != codes[i-1]."""
    return (np.flatnonzero(codes[1:] != codes[:-1]) + 1) / fs


def seconds_to_nearest_boundary(start: float, end: float, changes: np.ndarray) -> float:
    """Distance from window [start, end) to the nearest label change; 0 if one lies inside; inf if none."""
    if len(changes) == 0:
        return float("inf")
    i = int(np.searchsorted(changes, start, side="right"))   # changes[:i] <= start
    j = int(np.searchsorted(changes, end, side="left"))      # changes[j:] >= end
    if j > i:                                                # start < change < end
        return 0.0
    before = start - changes[i - 1] if i > 0 else float("inf")
    after = changes[j] - end if j < len(changes) else float("inf")
    return float(min(before, after))
