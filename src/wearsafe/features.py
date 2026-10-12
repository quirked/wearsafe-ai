"""Layer C feature functions (D03). Pure functions of ONE window's samples (no future, no labels).

Parameters come from config/features_v1.yaml (fixed before any D03 run). Definitions:
  - |a| = Euclidean norm of the 3-axis ACC in m/s^2.
  - jerk = ||a[i+1] - a[i]|| * fs (m/s^3), vector difference within the window.
  - motion_energy = mean((|a| - mean|a|)^2)  (equals the population variance of |a|; kept because §14 lists it).
  - spectrum: rfft of de-meaned |a| times a Hann window; DC bin excluded; power = |X|^2.
    dominant_freq = frequency of the max-power bin; spectral_entropy = Shannon entropy of the normalised power,
    divided by log(n_bins) (0..1); spectral_energy = sum(power) / n_samples.
    If the de-meaned signal is exactly 0 (constant window): dominant_freq = 0, entropy = 0, energy = 0.
  - BVP: bandpass Butterworth (order 2, zero-phase filtfilt) on the window's own samples only; peaks with
    neurokit2 ppg_findpeaks (Elgendi); IBIs outside the valid HR range are discarded; the stored BVP polarity
    is used as is (fixed a priori, never chosen from results).
  - ppg_sqi = mean of neurokit2 ppg_quality(method="templatematch") over the window (0..1).
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.signal import butter, filtfilt

MOTION_FEATURE_NAMES = (
    "acc_mag_mean", "acc_mag_std", "acc_mag_max", "acc_mag_p95", "acc_mag_rms", "acc_mag_range",
    "jerk_mean", "jerk_std", "jerk_max", "motion_energy", "dominant_freq", "spectral_entropy",
    "spectral_energy", "acc_saturated_frac",
)
PHYSIOLOGY_FEATURE_NAMES = (
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_delta", "hr_slope", "hr_rel_baseline",
    "bvp_peak_rate", "ibi_mean", "ibi_std", "ppg_sqi", "physiology_uncertain",
)


def motion_features(acc: np.ndarray, fs: float, saturated: np.ndarray) -> dict:
    """acc: (n, 3) m/s^2 for one window; saturated: (n,) bool per-sample E4 rail flag."""
    acc = np.asarray(acc, dtype=float)
    mag = np.sqrt((acc ** 2).sum(axis=1))
    jerk = np.sqrt((np.diff(acc, axis=0) ** 2).sum(axis=1)) * fs
    dm = mag - mag.mean()
    out = {
        "acc_mag_mean": float(mag.mean()), "acc_mag_std": float(mag.std()), "acc_mag_max": float(mag.max()),
        "acc_mag_p95": float(np.percentile(mag, 95)), "acc_mag_rms": float(np.sqrt(np.mean(mag ** 2))),
        "acc_mag_range": float(mag.max() - mag.min()),
        "jerk_mean": float(jerk.mean()), "jerk_std": float(jerk.std()), "jerk_max": float(jerk.max()),
        "motion_energy": float(np.mean(dm ** 2)),
        "acc_saturated_frac": float(np.mean(saturated)),
    }
    spec = np.fft.rfft(dm * np.hanning(len(dm)))
    power = (np.abs(spec) ** 2)[1:]
    freqs = np.fft.rfftfreq(len(dm), d=1.0 / fs)[1:]
    total = power.sum()
    if total <= 0:
        out.update(dominant_freq=0.0, spectral_entropy=0.0, spectral_energy=0.0)
    else:
        p = power / total
        nz = p[p > 0]
        out.update(dominant_freq=float(freqs[int(np.argmax(power))]),
                   spectral_entropy=float(-(nz * np.log(nz)).sum() / np.log(len(p))),
                   spectral_energy=float(total / len(dm)))
    return out


def bandpass(x: np.ndarray, fs: float, band: tuple[float, float], order: int = 2) -> np.ndarray:
    b, a = butter(order, list(band), btype="band", fs=fs)
    return filtfilt(b, a, np.asarray(x, dtype=float))


def bvp_beats(bvp: np.ndarray, fs: float, band, hr_valid) -> dict:
    """Filter one window, find peaks, return peaks (sample idx), valid IBIs (s), their beat times and SQI."""
    import neurokit2 as nk
    f = bandpass(bvp, fs, band)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            peaks = np.asarray(nk.ppg_findpeaks(f, sampling_rate=int(fs), method="elgendi")["PPG_Peaks"], dtype=int)
        except Exception:
            peaks = np.array([], dtype=int)
        sqi = np.nan
        if len(peaks) >= 2:
            try:
                q = nk.ppg_quality(f, peaks=peaks, sampling_rate=int(fs), method="templatematch")
                sqi = float(np.nanmean(q))
            except Exception:
                sqi = np.nan
    ibi = np.diff(peaks) / fs
    t = peaks[1:] / fs
    lo, hi = 60.0 / hr_valid[1], 60.0 / hr_valid[0]
    ok = (ibi >= lo) & (ibi <= hi)
    return {"filtered": f, "peaks": peaks, "ibi": ibi[ok], "beat_t": t[ok], "sqi": sqi}


def physiology_features(bvp: np.ndarray, fs: float, cfg: dict) -> dict:
    """30 s window physiology features from BVP only. hr_rel_baseline is filled later (past windows only)."""
    ph, sq = cfg["physiology"], cfg["ppg_sqi"]
    r = bvp_beats(bvp, fs, ph["bandpass_hz"], ph["hr_valid_bpm"])
    dur = len(bvp) / fs
    out = {k: np.nan for k in PHYSIOLOGY_FEATURE_NAMES}
    out["bvp_peak_rate"] = float(len(r["peaks"]) / dur * 60.0)
    out["ppg_sqi"] = r["sqi"]
    ibi, t = r["ibi"], r["beat_t"]
    if len(ibi) >= 2:
        hr = 60.0 / ibi
        out.update(hr_mean=float(hr.mean()), hr_std=float(hr.std()), hr_min=float(hr.min()), hr_max=float(hr.max()),
                   ibi_mean=float(ibi.mean()), ibi_std=float(ibi.std()))
        first, last = hr[t < 10.0], hr[t >= dur - 10.0]
        if len(first) and len(last):
            out["hr_delta"] = float(last.mean() - first.mean())
        if np.ptp(t) > 0:
            out["hr_slope"] = float(np.polyfit(t, hr, 1)[0])
    lo, hi = ph["hr_valid_bpm"]
    out["physiology_uncertain"] = bool(
        not (out["ppg_sqi"] >= sq["threshold"]) or len(ibi) < 2 or not (lo <= out["hr_mean"] <= hi))
    return out


def hr_estimate(bvp: np.ndarray, fs: float, cfg: dict) -> tuple[float, float, int]:
    """(HR bpm = 60 / median valid IBI, SQI, n valid IBIs) for one short window (8 s reference windows)."""
    ph = cfg["physiology"]
    r = bvp_beats(bvp, fs, ph["bandpass_hz"], ph["hr_valid_bpm"])
    hr = 60.0 / float(np.median(r["ibi"])) if len(r["ibi"]) >= 2 else np.nan
    return hr, r["sqi"], int(len(r["ibi"]))


def rel_baseline(starts: np.ndarray, ends: np.ndarray, hr_mean: np.ndarray, uncertain: np.ndarray,
                 baseline_s: float) -> np.ndarray:
    """hr_mean minus median good-quality hr_mean of windows lying fully in [start - baseline_s, start).

    Uses only windows that END at or before the current window STARTS (strictly past data).
    NaN if the current window starts before baseline_s of history exists or no good past window exists.
    """
    out = np.full(len(starts), np.nan)
    good = ~uncertain & np.isfinite(hr_mean)
    for i, s in enumerate(starts):
        if s < baseline_s or not np.isfinite(hr_mean[i]):
            continue
        m = good & (ends <= s) & (starts >= s - baseline_s)
        if m.any():
            out[i] = hr_mean[i] - float(np.median(hr_mean[m]))
    return out
