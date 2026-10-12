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
CFG2 = yaml.safe_load((REPO / "config" / "windowing_v2.yaml").read_text())


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
    assert CFG["tasks"] == CFG2["tasks"]
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


def test_window_roles_v1_config_purity_only():
    from d02_ppg_dalia_windows import window_role
    assert CFG["eval_role"]["purity_threshold"] == 1.0
    assert window_role("sitting", 1.0, 0.0, MAPS, CFG) == "train_candidate"      # v1 config has no margin
    assert window_role("sitting", 0.875, 0.0, MAPS, CFG) == "false_alert_eval_only"
    assert window_role("lunch", 1.0, 99.0, MAPS, CFG) == "false_alert_eval"


def test_window_roles_v2_boundary_margin():
    from d02_ppg_dalia_windows import window_role
    assert CFG2["eval_role"]["boundary_margin_s"] == 10
    assert window_role("sitting", 1.0, 10.0, MAPS, CFG2) == "train_candidate"
    assert window_role("sitting", 1.0, 9.75, MAPS, CFG2) == "false_alert_eval"     # fails only the margin: kept
    assert window_role("sitting", 0.875, 0.0, MAPS, CFG2) == "false_alert_eval_only"
    assert window_role("sitting", 1.0, float("inf"), MAPS, CFG2) == "train_candidate"
    assert window_role("transient", 1.0, 50.0, MAPS, CFG2) == "false_alert_eval"
    assert window_role("lunch", 1.0, 50.0, MAPS, CFG2) == "false_alert_eval"
    for lab in MAPS["ppg_dalia"]["original_label"].values():
        assert window_role(lab, 1.0, 50.0, MAPS, CFG2) in ("train_candidate", "false_alert_eval")


def test_change_times_and_boundary_distance():
    codes = np.array([0] * 8 + [1] * 40 + [0] * 8)        # 4 Hz: changes at 2 s and 12 s
    ch = wn.change_times(codes, 4)
    assert ch.tolist() == [2.0, 12.0]
    d = wn.seconds_to_nearest_boundary
    assert d(4.0, 6.0, ch) == 2.0          # 2 s after the first change
    assert d(5.0, 10.0, ch) == 2.0         # 2 s before the second change
    assert d(1.0, 3.0, ch) == 0.0          # change inside
    assert d(2.0, 4.0, ch) == 0.0          # change exactly at the start
    assert d(10.0, 12.0, ch) == 0.0        # change exactly at the end
    assert d(0.0, 2.0, ch) == 0.0
    assert d(0.0, 1.0, np.array([])) == float("inf")
    assert d(13.0, 14.0, ch) == 1.0        # after the last change


def test_boundary_distance_matches_brute_force():
    rng = np.random.default_rng(1)
    codes = np.repeat(rng.integers(0, 3, 30), rng.integers(1, 60, 30))
    ch = wn.change_times(codes, 4)
    for start in np.arange(0, len(codes) / 4 - 5, 0.25):
        end = start + 5
        inside = ((ch > start) & (ch < end)).any()
        brute = 0.0 if inside else min([start - c for c in ch if c <= start] + [c - end for c in ch if c >= end]
                                       + [float("inf")])
        assert wn.seconds_to_nearest_boundary(start, end, ch) == brute
