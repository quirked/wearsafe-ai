"""D08 harmonisation on synthetic data (no raw data needed)."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402

N, FS_IN = 4760, 238


def tone(f_hz, amp_g=0.5, offset_g=1.0):
    t = np.arange(N) / FS_IN
    z = (offset_g + amp_g * np.sin(2 * np.pi * f_hz * t)) * 4096
    return np.column_stack([np.zeros(N), np.zeros(N), z]).round().astype(np.int16)


def test_counts_to_g():
    assert mh.counts_to_g(np.array([4096, -8192]), 4096).tolist() == [1.0, -2.0]


def test_resample_length_dc_and_edges():
    out = mh.resample_238_to_32(mh.counts_to_g(tone(0, amp_g=0), 4096))
    assert out.shape == (640, 3)
    assert np.allclose(out[:, 2], 1.0, atol=1e-4)          # DC preserved, including both clip ends ('line' padding)


def test_passband_and_alias_rejection():
    def amp(f):
        out = mh.resample_238_to_32(mh.counts_to_g(tone(f), 4096))[:, 2]
        seg = out[64:-64] - out[64:-64].mean()
        return np.sqrt(2) * seg.std()
    assert amp(5) == pytest.approx(0.5, rel=0.02)            # 5 Hz passes
    assert 20 * np.log10(amp(50) / 0.5) < -40                # 50 Hz (would alias) attenuated > 40 dB


def test_e4_clip_quantise_and_flags():
    x = tone(2, amp_g=3.0, offset_g=0.0)                     # swings to ±3 g
    r = mh.harmonise(x, "e4_clipped", 4096)
    a = r["acc_m_s2"]
    assert a.min() >= -2.0 * mh.G - 1e-9 and a.max() <= 127 / 64 * mh.G + 1e-9
    c = a / mh.G * 64
    assert np.allclose(c, np.round(c), atol=1e-9)
    assert np.array_equal(r["sat_axes"], (np.round(c) == -128) | (np.round(c) == 127))
    assert r["sat_axes"][:, 2].any()


def test_reclip_catches_filter_overshoot():
    x = np.zeros((N, 3), dtype=np.int64)
    x[:, 2] = 4096 * 6                                       # +6 g step plateau -> clipped at 238 Hz
    x[: N // 2, 2] = 0
    g = mh.e4_clip(mh.counts_to_g(x, 4096))
    ring = mh.resample_238_to_32(g)[:, 2]
    assert ring.max() > mh.E4_HI_G                           # the FIR overshoots the flat plateau ...
    out = mh.harmonise(x, "e4_clipped", 4096)["acc_m_s2"][:, 2]
    assert out.max() <= mh.E4_HI_G * mh.G + 1e-9             # ... and the re-clip removes it


def test_unclipped_never_altered_by_e4_step():
    x = tone(3, amp_g=4.0)
    before = x.copy()
    u1 = mh.harmonise(x, "unclipped", 4096)["acc_m_s2"]
    mh.harmonise(x, "e4_clipped", 4096)
    u2 = mh.harmonise(x, "unclipped", 4096)["acc_m_s2"]
    assert np.array_equal(x, before) and np.array_equal(u1, u2)
    assert u1.max() > 3 * mh.G                               # unclipped keeps the > 2 g peaks


def test_gravity_check_pass_and_fail():
    rng = np.random.default_rng(0)
    quiet = [np.column_stack([np.zeros(N), np.zeros(N), 4096 + rng.normal(0, 5, N)]) for _ in range(3)]
    assert mh.gravity_check(quiet, 4096)["median_g"] == pytest.approx(1.0, abs=0.01)
    low = [np.column_stack([np.zeros(N), np.zeros(N), 3800 + rng.normal(0, 5, N)]) for _ in range(3)]
    assert not (0.95 <= mh.gravity_check(low, 4096)["median_g"] <= 1.05)
    moving = [tone(2, amp_g=0.5)]
    assert mh.gravity_check(moving, 4096)["n_records"] == 0


def test_banned_file_guard():
    with pytest.raises(PermissionError):
        fio.guard("data/interim/_unzipped/fallalld/FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl")
    assert fio.guard("data/interim/_unzipped/fallalld/FallAllD.pkl").name == "FallAllD.pkl"
