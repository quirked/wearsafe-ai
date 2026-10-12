"""fusion_v1 streaming reproduces the offline F02 result on one TEST subject (PPGDALIA_S03); skips without outputs."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fusion_v1 as fv1  # noqa: E402

F02 = REPO / "results/2026-10-12_F02_demo_v1"
F01 = REPO / "results/2026-10-12_F01_demo_v0"
SID = "PPGDALIA_S03"
pytestmark = pytest.mark.skipif(not (F02 / "test_per_subject.csv").exists(), reason="F02 outputs not present")


def test_streaming_change_decision_reproduces_offline():
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    assert SID in part["ppg_dalia"]["test"]
    sel = json.loads((F02 / "selection.json").read_text())
    cfg = yaml.safe_load(open(REPO / "config/fusion_v1.yaml"))
    T = json.loads((F01 / "thresholds.json").read_text())["motion_threshold"]
    dec = pd.read_parquet(F01 / "ppg_dalia_decisions.parquet")
    dec = dec[dec.subject_id == SID].sort_values("t").reset_index(drop=True)
    acc = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{SID}/wrist_acc.parquet",
                          columns=["x", "y", "z"]).to_numpy()
    hours = len(pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{SID}/activity.parquet",
                                columns=["original_code"])) / 4 / 3600
    per = pd.read_csv(F02 / "test_per_subject.csv")
    for variant in ("V1-change", "V1-tiered"):
        prm = sel["chosen"][variant]["params"]
        # streaming: the buffer only ever holds data up to the current second; a change decision for alarm time t is
        # taken at t + 5 s with the samples available then
        buf_end, change = 0, np.zeros(len(dec), bool)
        pending = []
        for i, (t, p) in enumerate(zip(dec.t.to_numpy(), dec.p_motion.to_numpy())):
            buf_end = int(round(t * 32))
            if p >= T:
                pending.append((i, t))
            ready = [(j, ta) for j, ta in pending if (ta + 5) * 32 <= buf_end]
            pending = [(j, ta) for j, ta in pending if (ta + 5) * 32 > buf_end]
            for j, ta in ready:
                m = fv1.change_measures(acc[:buf_end], int(round(ta * 32)), 32)
                change[j] = fv1.is_change(m, prm["tol"])
        prompts, _ = fv1.decide(variant, dec.t.to_numpy(), dec.p_motion.to_numpy(), np.full(len(dec), T),
                                prm.get("T_high"), change, None, cfg["refractory_s"])
        offline = per[(per.variant == variant) & (per.subject_id == SID)].prompts_per_hour.iloc[0]
        assert prompts.sum() / hours == pytest.approx(offline, rel=1e-9)
