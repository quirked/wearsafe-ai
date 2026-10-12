"""Heart-check replay (demo v3) for the everyday-life demo subject (PPG-DaLiA TEST partition), M03 v2 gate,
logistic regression (M03 headline model). The deploy model is refitted with identical data/settings
(scripts/m03_v2_sqi.py rules) and its scores must match the offline file results/.../ppg_dalia_lr_scores_v2.parquet.
Writes results/2026-10-12_M03_v2_demo_replay/heart.joblib."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from m03_still_racing import COLS, checkins, lr  # noqa: E402
from m03_v2_sqi import gate  # noqa: E402

OUT = REPO / "results/2026-10-12_M03_v2_demo_replay"


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    c2 = json.loads((REPO / "results/2026-10-12_SQI_v2_demo_v0/selection.json").read_text())["chosen_cutoff"]
    tl = joblib.load(REPO / "results/2026-10-12_demo_app_v0/timelines.joblib")
    sid = tl["meta"]["everyday_subject"]
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    assert sid in part["ppg_dalia"]["test"]
    W = pd.read_parquet(REPO / "results/2026-10-12_M03_still_racing_demo_v0/wesad_windows.parquet")
    W["gated"] = gate(W, c2)
    tr = W.gated & (W.purity == 1.0) & W.label.isin(["baseline", "stress"])
    mdl = lr().fit(W.loc[tr, COLS], (W.label == "stress").astype(int)[tr])
    off = pd.read_parquet(REPO / "results/2026-10-12_M03_v2_sqi_demo_v0/ppg_dalia_lr_scores_v2.parquet")
    off = off[off.subject_id == sid].sort_values("window_start").reset_index(drop=True)
    ph = pd.read_parquet(REPO / "data/processed/physiology/ppg_dalia_features_v1.parquet")
    g = pd.read_parquet(REPO / "results/2026-10-12_SQI_v2_demo_v0/gated_windows.parquet")[["window_id", "acc_mag_std"]]
    ph = ph.merge(g, on="window_id")
    ph = ph[ph.subject_id == sid].set_index("window_id").loc[off.window_id].reset_index()
    s = mdl.predict_proba(ph[COLS])[:, 1]
    diff = float(np.max(np.abs(s - off.s.to_numpy())))
    assert diff < 1e-9 and (gate(ph, c2).to_numpy() == off.gated.to_numpy()).all(), f"replay != offline ({diff})"
    T = float(off.threshold.iloc[0])
    off["fire"] = checkins(off.assign(score=s), "score", T)
    off["status"] = np.where(~off.gated, "moving", np.where(s >= T, "racing", "calm"))
    OUT.mkdir(parents=True)
    joblib.dump({"subject": sid, "threshold": T, "cutoff": c2, "max_abs_diff_vs_offline": diff,
                 "windows": off[["window_start", "window_end", "original_label", "gated", "s", "status", "fire"]]},
                OUT / "heart.joblib", compress=3)
    print("check ok", diff, "fires at", off.window_end[off.fire].tolist())


if __name__ == "__main__":
    main()
