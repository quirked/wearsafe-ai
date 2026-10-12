"""A02 EDA helpers (config/a02_eda.yaml). Analysis only."""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, lfilter


def artefact_mask(eda, fs, lo=0.05, hi=60.0, slope=10.0):
    eda = np.asarray(eda, float)
    d = np.abs(np.diff(eda, prepend=eda[:1])) * fs
    return (eda < lo) | (eda > hi) | (d > slope)


def causal_split(eda, fs, cutoff=0.05):
    """tonic = forward-only 1st-order Butterworth low-pass; phasic = eda - tonic. Uses only past samples."""
    b, a = butter(1, cutoff, btype="low", fs=fs)
    eda = np.asarray(eda, float)
    tonic = lfilter(b, a, eda - eda[0]) + eda[0] if len(eda) else eda
    return tonic, eda - tonic


def area(x, fs, i0, i1):
    i0, i1 = max(0, i0), min(len(x), i1)
    return float(np.sum(x[i0:i1]) / fs) if i1 > i0 else np.nan


def mean_in(x, i0, i1):
    i0, i1 = max(0, i0), min(len(x), i1)
    return float(np.mean(x[i0:i1])) if i1 > i0 else np.nan


def event_eda(t, fs, tonic, phasic, onsets_s, artefact):
    """Measures for one time point t (s). onsets_s: SCR onset times (s) of kept SCRs."""
    i = int(round(t * fs))
    on = np.asarray(onsets_s, float)
    return {"quick_response": bool(((on >= t + 1) & (on <= t + 5)).any()),
            "phasic_change": area(phasic, fs, i, i + 10 * fs) - area(phasic, fs, i - 10 * fs, i),
            "tonic_change": mean_in(tonic, i + 5 * fs, i + 15 * fs) - mean_in(tonic, i - 15 * fs, i - 5 * fs),
            "pre_phasic_area": area(phasic, fs, i - 10 * fs, i),
            "artefact": bool(np.asarray(artefact)[max(0, i - 15 * fs):i + 15 * fs].any())}
