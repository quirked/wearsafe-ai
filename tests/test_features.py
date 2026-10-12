"""D03 feature functions on synthetic data (no raw data needed)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import features as F  # noqa: E402
from wearsafe import windowing as wn  # noqa: E402
from wearsafe.schemas import FORBIDDEN_FEATURE_COLUMNS  # noqa: E402

CFG = yaml.safe_load((REPO / "config/features_v1.yaml").read_text())


def pulse_train(hr_bpm, dur_s, fs=64, seed=0):
    t = np.arange(int(dur_s * fs)) / fs
    beats = np.arange(0.3, dur_s, 60.0 / hr_bpm)
    x = sum(np.exp(-0.5 * ((t - b) / 0.06) ** 2) for b in beats)
    return x + 0.01 * np.random.default_rng(seed).normal(size=len(t))


def test_dominant_frequency_of_2hz_sine():
    t = np.arange(64) / 32
    acc = np.column_stack([np.zeros(64), np.zeros(64), 9.81 + 2 * np.sin(2 * np.pi * 2 * t)])
    f = F.motion_features(acc, 32, np.zeros(64, bool))
    assert f["dominant_freq"] == pytest.approx(2.0)
    assert 0 <= f["spectral_entropy"] < 0.5


def test_constant_signal():
    acc = np.tile([0.0, 0.0, 9.81], (64, 1))
    f = F.motion_features(acc, 32, np.zeros(64, bool))
    assert f["jerk_mean"] == 0 and f["jerk_max"] == 0 and f["motion_energy"] == 0
    assert f["dominant_freq"] == 0 and f["spectral_entropy"] == 0 and f["spectral_energy"] == 0
    assert f["acc_mag_mean"] == pytest.approx(9.81) and f["acc_mag_range"] == 0
    assert all(np.isfinite(v) for v in f.values())


def test_saturation_fraction_and_names():
    acc = np.tile([0.0, 0.0, 9.81], (64, 1))
    sat = np.zeros(64, bool)
    sat[:16] = True
    f = F.motion_features(acc, 32, sat)
    assert f["acc_saturated_frac"] == 0.25
    assert set(f) == set(F.MOTION_FEATURE_NAMES)


def test_hr_from_synthetic_ppg():
    x = pulse_train(72, 30)
    f = F.physiology_features(x, 64, CFG)
    assert f["hr_mean"] == pytest.approx(72, abs=1.5)
    assert f["ppg_sqi"] > 0.9 and not f["physiology_uncertain"]
    hr, sqi, n = F.hr_estimate(pulse_train(90, 8), 64, CFG)
    assert hr == pytest.approx(90, abs=2.0) and n >= 2


def test_noise_is_uncertain():
    x = np.random.default_rng(1).normal(size=30 * 64)
    f = F.physiology_features(x, 64, CFG)
    assert f["physiology_uncertain"]


def test_feature_names_not_forbidden():
    assert not (set(F.MOTION_FEATURE_NAMES) | set(F.PHYSIOLOGY_FEATURE_NAMES)) & set(FORBIDDEN_FEATURE_COLUMNS)
    for col in ("seconds_to_nearest_boundary", "eval_role", "label_purity", "hr_ref_bpm"):
        assert col in FORBIDDEN_FEATURE_COLUMNS


def test_rel_baseline_uses_only_strictly_past_windows():
    starts = np.arange(0, 600, 15.0)
    ends = starts + 30
    hr = np.full(len(starts), 70.0)
    unc = np.zeros(len(starts), bool)
    base = F.rel_baseline(starts, ends, hr, unc, 300)
    assert np.isnan(base[starts < 300]).all()
    assert np.allclose(base[starts >= 300], 0.0)
    hr2 = hr.copy()
    hr2[starts >= 450] = 150.0                          # change the future only
    base2 = F.rel_baseline(starts, ends, hr2, unc, 300)
    assert np.allclose(base2[starts < 450][starts[starts < 450] >= 300], 0.0)


def test_end_to_end_causality(tmp_path):
    """Perturbing samples after time T leaves every feature of windows ending at or before T unchanged."""
    from d03_ppg_dalia_features import CARRY, subject_features
    dur, sid = 420, "PPGDALIA_S01"
    rng = np.random.default_rng(0)
    acc = rng.normal(0, 1, (dur * 32, 3)) + [0, 0, 9.81]
    bvp = pulse_train(75, dur)
    d = tmp_path / sid
    d.mkdir()

    def write(acc_, bvp_):
        pd.DataFrame({"x": acc_[:, 0], "y": acc_[:, 1], "z": acc_[:, 2],
                      "acc_saturated": np.zeros(len(acc_), bool)}).to_parquet(d / "wrist_acc.parquet")
        pd.DataFrame({"scalar_value": bvp_}).to_parquet(d / "wrist_bvp.parquet")

    wins = {}
    for name, (w, st) in {"motion_2s": (2, 1), "context_5s": (5, 2.5), "physiology_30s": (30, 15)}.items():
        rows = []
        for i, (s, e) in enumerate(wn.window_bounds(dur, w, st)):
            r = {c: None for c in CARRY}
            r.update(window_id=f"{sid}_{name}_{i}", subject_id=sid, window_start=float(s), window_end=float(e),
                     acc_i0=int(s * 32), acc_i1=int(e * 32), bvp_i0=int(s * 64), bvp_i1=int(e * 64))
            rows.append(r)
        wins[name] = pd.DataFrame(rows)
    write(acc, bvp)
    a = subject_features(sid, tmp_path, wins, CFG)
    T = 360
    acc2, bvp2 = acc.copy(), bvp.copy()
    acc2[T * 32:] += 50.0
    bvp2[T * 64:] = rng.normal(size=len(bvp2) - T * 64) * 100
    write(acc2, bvp2)
    b = subject_features(sid, tmp_path, wins, CFG)
    for name in a:
        past = a[name].window_end <= T
        cols = list(F.PHYSIOLOGY_FEATURE_NAMES if name == "physiology_30s" else F.MOTION_FEATURE_NAMES)
        pd.testing.assert_frame_equal(a[name].loc[past, cols], b[name].loc[past, cols])
        assert not a[name].loc[~past, cols].equals(b[name].loc[~past, cols])
    assert a["physiology_30s"].loc[a["physiology_30s"].window_end <= T, "hr_rel_baseline"].notna().any()
