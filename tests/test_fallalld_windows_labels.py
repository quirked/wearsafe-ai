"""D08 window table and labels on synthetic records (no raw data needed)."""
import sys
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import features as F  # noqa: E402
from wearsafe.fallalld_windows import record_windows  # noqa: E402
from wearsafe.schemas import FORBIDDEN_FEATURE_COLUMNS  # noqa: E402

CFG = yaml.safe_load((REPO / "config/fallalld_v1.yaml").read_text())


def rec(kind, act):
    return {"record_id": f"FALLALLD_S01_A{act:03d}_T01", "subject_id": "FALLALLD_S01", "activity_id": act,
            "trial_no": 1, "original_label": f"{act}: x", "kind": kind}


def test_fall_clip_windows():
    w = record_windows(rec("fall", 101), CFG, 32, 640)
    assert len(w) == 19 and ((w.i1 - w.i0) == 64).all() and w.i1.max() == 640
    pos = w[w.window_role == "fall_positive"]
    assert pos.window_start.tolist() == [9.0] and pos.motion_event_class.tolist() == ["abrupt_event_proxy"]
    assert (w[w.window_start == 10.0].window_role == "fall_clip_context").all()       # user CHANGE to decision 4
    ctx = w[w.window_role == "fall_clip_context"]
    assert len(ctx) == 18 and (ctx.eval_role == "excluded_ambiguous").all() and ctx.motion_event_class.isna().all()
    assert w.loc[w.position_matched, "window_start"].tolist() == [9.0]
    assert w.loc[w.contains_impact_time, "window_start"].tolist() == [9.0, 10.0]


def test_adl_and_probe_windows():
    a = record_windows(rec("adl", 20), CFG, 32, 640)
    assert (a.window_role == "adl").all() and (a.eval_role == "train_candidate").all()
    assert (a.motion_event_class == "normal_adl").all()
    for act in (15, 23):
        p = record_windows(rec("adl", act), CFG, 32, 640)
        assert (p.window_role == "hard_negative_probe").all() and not (p.eval_role == "train_candidate").any()


def test_position_and_meta_columns_are_forbidden():
    for c in ("window_start", "record_id", "activity_id", "trial_no", "window_role", "eval_role", "kind"):
        assert c in FORBIDDEN_FEATURE_COLUMNS
    assert not set(F.MOTION_FEATURE_NAMES_V2) & set(FORBIDDEN_FEATURE_COLUMNS)


def test_saturation_features_v2():
    acc = np.tile([0.0, 0.0, 9.81], (64, 1))
    sat = np.zeros((64, 3), bool)
    sat[10:15, 2] = True
    sat[20:30, :2] = True
    acc[40] = [0, 0, 30.0]                                   # peak at sample 40
    acc[5] = [0, 0, 1.0]                                     # low-g dip before the peak
    f = F.saturation_features_v2(acc, 32, sat)
    assert f["sat_longest_run_s"] == 10 / 32 and f["sat_n_runs"] == 2 and f["sat_max_axes"] == 2
    assert f["pre_peak_min_mag"] == 1.0 and f["post_peak_stillness"] == 0.0
    late = acc.copy()
    late[40] = [0, 0, 9.81]
    late[60] = [0, 0, 30.0]                                  # peak with < 8 samples after it
    assert np.isnan(F.saturation_features_v2(late, 32, sat)["post_peak_stillness"])
    first = acc.copy()
    first[40] = [0, 0, 9.81]
    first[0] = [0, 0, 30.0]
    assert np.isnan(F.saturation_features_v2(first, 32, sat)["pre_peak_min_mag"])
    none = F.saturation_features_v2(acc, 32, np.zeros((64, 3), bool))
    assert none["sat_longest_run_s"] == 0 and none["sat_n_runs"] == 0 and none["sat_max_axes"] == 0
