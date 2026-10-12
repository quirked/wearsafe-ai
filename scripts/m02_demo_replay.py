"""Demo v2 replay outputs for the fall-demo clips with the M02 e4_clipped ACC+barometer random forest.
Fold model = the M02 fold that left the clip's subject out, refitted with identical data/columns/settings/seed
(M02 did not save fold models); threshold = that fold's saved inner-validation threshold. A check requires its
scores to equal M02's saved out-of-fold scores for every window of the subject. Alarm: score >= threshold, one
prompt at a time, 30 s pause (wearsafe.fusion.prompts). Writes results/2026-10-12_M02_demo_replay/replay.joblib.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fusion  # noqa: E402
from wearsafe import features as F  # noqa: E402
from wearsafe.safe_pickle import load_pickle_restricted  # noqa: E402
from wearsafe import fallalld_io as fio  # noqa: E402
from m01_demo_motion import rf  # noqa: E402

M02 = REPO / "results/2026-10-12_M02_extra_sensors/e4_clipped_baro"
OUT = REPO / "results/2026-10-12_M02_demo_replay"
HEIGHT_HPA = 0.06   # display only


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    tl = joblib.load(REPO / "results/2026-10-12_demo_app_v0/timelines.joblib")
    split = json.loads((REPO / "splits/fallalld_v1.json").read_text())
    thr = json.loads((M02 / "thresholds_rf.json").read_text())
    df = pd.read_parquet(REPO / "data/processed/motion/fallalld_e4_clipped_features-v2_v1.parquet").merge(
        pd.read_parquet(REPO / "data/processed/motion/fallalld_extra_sensors_m02.parquet"), on="window_id")
    cols = list(F.MOTION_FEATURE_NAMES_V2) + ["baro_change", "baro_std"]
    oof = pd.read_parquet(M02 / "oof_rf.parquet").set_index("window_id")
    sid = tl["meta"]["fall_subject"]
    fold = next(f for f in split["folds"] if f["test"] == [sid])
    T = next(t["threshold"] for t in thr if t["fold"] == fold["fold"])
    tc = (df.eval_role == "train_candidate") & df.subject_id.isin(fold["train"])
    y = (df.window_role == "fall_positive").astype(int)
    model = rf(4).fit(df.loc[tc, cols], y[tc])
    sub = df[df.subject_id == sid]
    score = model.predict_proba(sub[cols])[:, 1]
    diff = float(np.max(np.abs(score - oof.loc[sub.window_id, "score"].to_numpy())))
    assert diff < 1e-12, f"refitted fold model does not reproduce M02 out-of-fold scores (max diff {diff})"
    raw = load_pickle_restricted(fio.guard(REPO / fio.UNZIPPED / "FallAllD.pkl"))
    raw = raw[raw.Device == "Wrist"]
    raw.index = [fio.record_id(int(s), int(a), int(t)) for s, a, t in zip(raw.SubjectID, raw.ActivityID, raw.TrialNo)]
    out = {"meta": {"subject": sid, "fold": fold["fold"], "threshold": T, "max_abs_diff_vs_m02_oof": diff,
                    "height_change_display_hpa": HEIGHT_HPA, "model": "M02 e4_clipped ACC+barometer RF (fold refit, identical)",
                    "note": "Chosen post-hoc after comparing 8 configurations on the same held-out folds; optimistic; needs confirmation"}}
    for name, clip in tl["fall"].items():
        rid = clip["record_id"]
        w = sub[sub.record_id == rid].sort_values("window_start")
        s = model.predict_proba(w[cols])[:, 1]
        t = (w.window_start + 2).to_numpy()
        pr = fusion.prompts(t, s >= T, 30)
        d = pd.DataFrame({"t_abs": t, "score": s, "alarm": s >= T, "prompt": pr, "baro_change_hpa": w.baro_change.to_numpy(),
                          "height_change": np.abs(w.baro_change.to_numpy()) >= HEIGHT_HPA})
        out[name] = {"record_id": rid, "decisions": d, "pressure_hpa": raw.loc[rid, "Bar"][:, 0]}
        print(name, rid, "prompts at", list(t[pr]), "max score", round(float(s.max()), 3))
    OUT.mkdir(parents=True)
    joblib.dump(out, OUT / "replay.joblib", compress=3)
    print("check ok: max |diff| vs M02 oof =", diff)


if __name__ == "__main__":
    main()
