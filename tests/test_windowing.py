"""Windowing logic on synthetic data (D02; no raw data needed)."""
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import windowing as wn  # noqa: E402

MAPS = yaml.safe_load((REPO / "config" / "label_maps.yaml").read_text())
CFG = yaml.safe_load((REPO / "config" / "windowing_v1.yaml").read_text())


@pytest.mark.parametrize("dur,w,step,exp", [
    (10, 2, 1, 9), (10, 5, 2.5, 3), (10.25, 5, 2.5, 3), (12.5, 5, 2.5, 4), (60, 30, 15, 3),
    (5250, 30, 15, 349), (29.75, 30, 15, 0), (2, 2, 1, 1)])
def test_expected_count(dur, w, step, exp):
    assert wn.expected_count(dur, w, step) == exp
    b = wn.window_bounds(dur, w, step)
    assert len(b) == exp
    assert all(e - s == Fraction(str(w)) for s, e in b)
    assert all(e <= Fraction(str(dur)) for _, e in b)


def test_config_tasks_are_half_overlap():
    for spec in CFG["tasks"].values():
        assert Fraction(str(spec["step_s"])) * 2 == Fraction(str(spec["length_s"]))


def test_sample_range_exact_and_aligned():
    assert wn.sample_range(Fraction(5, 2), Fraction(15, 2), 32) == (80, 240)
    assert wn.sample_range(Fraction(5, 2), Fraction(15, 2), 4) == (10, 30)
    with pytest.raises(ValueError):
        wn.sample_range(Fraction(1, 8), Fraction(9, 8), 4)


def test_majority_purity_and_ties():
    assert wn.majority_label(np.array([1, 1, 1, 1])) == (1, 1.0, 1)
    assert wn.majority_label(np.array([0, 1, 1, 1])) == (1, 0.75, 2)
    # tie: label of the last sample wins
    assert wn.majority_label(np.array([0, 0, 1, 1])) == (1, 0.5, 2)
    assert wn.majority_label(np.array([1, 1, 0, 0])) == (0, 0.5, 2)
    # 3 labels, tie between 0 and 1, last sample is 2 (not tied): tied label occurring last wins
    assert wn.majority_label(np.array([0, 0, 1, 1, 2])) == (1, 0.4, 3)


def test_hr_ref_range():
    # ref windows [2k, 2k+8); 30 s window [0,30) holds k=0..11 -> 12 refs
    assert wn.hr_ref_range(Fraction(0), Fraction(30), 8, 2, 100) == (0, 12)
    assert wn.hr_ref_range(Fraction(15), Fraction(45), 8, 2, 100) == (8, 19)
    assert wn.hr_ref_range(Fraction(0), Fraction(5), 8, 2, 100) == (0, 0)     # too short
    k0, k1 = wn.hr_ref_range(Fraction(15), Fraction(45), 8, 2, 10)          # clipped at n_ref
    assert (k0, k1) == (8, 10)


def test_window_roles():
    from d02_ppg_dalia_windows import window_role
    thr = CFG["eval_role"]["purity_threshold"]
    assert thr == 1.0
    assert window_role("sitting", 1.0, MAPS, thr) == "train_candidate"
    assert window_role("sitting", 0.875, MAPS, thr) == "false_alert_eval_only"
    assert window_role("lunch", 1.0, MAPS, thr) == "false_alert_eval"
    assert window_role("transient", 1.0, MAPS, thr) == "false_alert_eval"
    for lab in MAPS["ppg_dalia"]["original_label"].values():
        assert window_role(lab, 1.0, MAPS, thr) in ("train_candidate", "false_alert_eval")
