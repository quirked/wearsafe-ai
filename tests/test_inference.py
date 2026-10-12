"""The streaming engine reproduces the offline F01 predictions for one subject (skips if data/models are absent)."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe.inference import EngineConfig, StreamingEngine  # noqa: E402

F01 = REPO / "results/2026-10-12_F01_demo_v0"
SIG = REPO / "data/interim/ppg_dalia/normalized_signals_v1/PPGDALIA_S03"
MOTION = REPO / "results/2026-10-12_M01_demo_v0_run2/motion/e4_clipped_v2/models/rf_deploy.joblib"
SID, SECONDS = "PPGDALIA_S03", 900

pytestmark = pytest.mark.skipif(not (F01.exists() and SIG.exists() and MOTION.exists()), reason="F01 outputs not present")


@pytest.fixture(scope="module")
def run():
    thr = json.loads((F01 / "thresholds.json").read_text())
    motion = joblib.load(MOTION)
    context = joblib.load(F01 / "models/context_rf_deploy.joblib")
    cfg = EngineConfig(motion_threshold=motion["threshold"], gate_threshold=thr["gate_threshold_loso"][SID],
                       features_cfg=yaml.safe_load(open(REPO / "config/features_v1.yaml")))
    eng = StreamingEngine(motion, context, cfg)
    acc = pd.read_parquet(SIG / "wrist_acc.parquet", columns=["x", "y", "z"]).to_numpy()[: SECONDS * 32]
    bvp = pd.read_parquet(SIG / "wrist_bvp.parquet", columns=["scalar_value"]).scalar_value.to_numpy()[: SECONDS * 64]
    out = []
    for k in range(SECONDS):                                   # stream 1 s at a time
        out += eng.push(acc[k * 32:(k + 1) * 32], bvp[k * 64:(k + 1) * 64])
    on = pd.DataFrame(out).set_index("t")
    off = pd.read_parquet(F01 / "ppg_dalia_decisions.parquet")
    off = off[(off.subject_id == SID) & (off.t <= SECONDS)].set_index("t")
    return on, off, context


def test_motion_probability_and_alarm_match_offline(run):
    on, off, _ = run
    common = off.index.intersection(on.index)
    assert len(common) == SECONDS - 1
    assert np.allclose(on.loc[common, "p_motion"], off.loc[common, "p_motion"], atol=1e-12)
    assert (on.loc[common, "alarm"] == off.loc[common, "alarm"]).all()


def test_physiology_status_matches_offline(run):
    on, off, _ = run
    common = off.index.intersection(on.index)
    assert (on.loc[common, "phys_status"].astype(str) == off.loc[common, "phys_status"].astype(str)).all()


def test_prompts_match_offline(run):
    on, off, _ = run
    assert set(on.index[on.prompt_base]) == set(off.index[off.prompt_base])
    on_still = set(on.loc[on.prompt_stillness, "stillness_alarm_t"].astype(int))
    off_still = {t for t in off.index[off.prompt_stillness] if t + 5 <= SECONDS}
    assert on_still == off_still


def test_context_matches_deploy_model_on_offline_features(run):
    on, _, context = run
    cw = pd.read_parquet(REPO / "data/processed/context/ppg_dalia_features_v1.parquet")
    cw = cw[(cw.subject_id == SID) & (cw.window_end <= SECONDS) & (cw.window_end % 1 == 0)]
    pred = context["model"].predict(cw[context["features"]])
    assert (on.loc[cw.window_end.astype(int).to_numpy(), "context"].to_numpy() == pred).all()
