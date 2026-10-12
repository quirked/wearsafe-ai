"""Identical-overlap search and overlap groups on synthetic records (no raw data needed)."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe.overlap import longest_identical_run, overlap_groups, overlap_pairs, sample_codes  # noqa: E402


def make():
    rng = np.random.default_rng(0)
    stream = rng.integers(-3000, 3000, size=(20000, 3))            # one continuous recording
    a = stream[0:4760]
    b = stream[3000:7760]                                          # overlaps a by 1760 samples (lag 3000)
    c = stream[7000:11760]                                         # overlaps b by 760 samples
    d = rng.integers(-3000, 3000, size=(4760, 3))                  # unrelated
    e = d.copy()
    e[:4000] = rng.integers(-3000, 3000, size=(4000, 3))           # shares only 760 samples with d
    return {"r_a": a, "r_b": b, "r_c": c, "r_d": d, "r_e": e}


def test_pairs_and_runs():
    recs = {k: sample_codes(v) for k, v in make().items()}
    pairs = overlap_pairs(recs)
    found = {(a, b): (lag, run) for a, b, lag, run in pairs}
    assert found[("r_a", "r_b")] == (3000, 1760)
    assert found[("r_b", "r_c")] == (4000, 760)
    assert found[("r_d", "r_e")] == (0, 760)
    assert ("r_a", "r_c") not in found and ("r_a", "r_d") not in found


def test_groups_are_connected_components():
    recs = {k: sample_codes(v) for k, v in make().items()}
    g = overlap_groups(list(recs), overlap_pairs(recs))
    assert g["r_a"] == g["r_b"] == g["r_c"] == "r_a"               # chained a-b-c -> one group, lowest id
    assert g["r_d"] == g["r_e"] == "r_d"
    assert overlap_groups(["x", "y"], []) == {"x": "x", "y": "y"}


def test_longest_run_short_is_not_counted():
    a = np.arange(1000)
    b = np.arange(1000)
    b[500] = -1
    assert longest_identical_run(a, b, 0) == 500                   # runs 0..499 (500) and 501..999 (499)
    pairs = overlap_pairs({"p": np.arange(300) * 7, "q": np.concatenate([np.arange(100) * 7, np.full(200, -5)])})
    assert pairs == []                                             # 100 identical samples < 238
