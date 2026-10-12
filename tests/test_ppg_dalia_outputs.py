"""Re-check D02 invariants on the real PPG-DaLiA outputs, if present (skips otherwise)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe import windowing as wn  # noqa: E402

ROOT = REPO / "data/interim/ppg_dalia"
TAGS = [t for t in ("smoke_v1", "v1") if (ROOT / f"windows_{t}").is_dir()]
CFG = yaml.safe_load((REPO / "config/windowing_v1.yaml").read_text())
MAPS = yaml.safe_load((REPO / "config/label_maps.yaml").read_text())

pytestmark = pytest.mark.skipif(not TAGS, reason="no D02 outputs on this machine")


@pytest.mark.parametrize("tag", TAGS)
def test_layer_a_and_windows(tag):
    norm, win = ROOT / f"normalized_signals_{tag}", ROOT / f"windows_{tag}"
    for name, spec in CFG["tasks"].items():
        w = pd.read_parquet(win / f"{name}.parquet")
        assert w["window_id"].is_unique
        assert w["arousal_class"].isna().all()                         # decision B
        assert (w["motion_event_class"] == "normal_adl").all()         # P3
        assert (w["crosses_boundary"] == (w["label_purity"] < 1)).all()
        tc = w["eval_role"] == "train_candidate"
        assert (w.loc[tc, "label_purity"] == 1.0).all()                # P2
        assert not w.loc[tc, "original_label"].isin(MAPS["ppg_dalia"]["training_v1"]["excluded"]).any()
        for sid, g in w.groupby("subject_id"):
            act = pd.read_parquet(norm / sid / "activity.parquet", columns=["original_code"])["original_code"].to_numpy()
            dur = len(act) / io.FS_ACT
            assert len(g) == wn.expected_count(dur, spec["length_s"], spec["step_s"])
            assert g["recording_id"].nunique() == 1 and g["window_end"].max() <= dur
            assert ((g["acc_i1"] - g["acc_i0"]) == spec["length_s"] * io.FS_ACC).all()
            pur = [np.mean(act[a:b] == c) for a, b, c in zip(g["act_i0"], g["act_i1"], g["majority_code"])]
            assert np.allclose(pur, g["label_purity"])
