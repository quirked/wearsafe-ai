"""M02 shortcut baselines (gyro-peak-only, baro-change-only), LR, same run_model as M01. Run once (refuses existing dirs)."""
import json, sys
from pathlib import Path
import pandas as pd
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import m02_extra_sensors as m
from m01_demo_motion import lr, run_model
split = json.loads((REPO / "splits/fallalld_v1.json").read_text())
X = pd.read_parquet(m.EXTRA)
df = pd.read_parquet(REPO / "data/processed/motion/fallalld_unclipped_features-v2_v1.parquet").merge(X, on="window_id")
for s, cols in (("base_gyro_peak", ["gyro_mag_max"]), ("base_baro_change", ["baro_change"])):
    out = m.OUT / f"unclipped_{s}"
    out.mkdir(parents=True)
    oof, fold_of, thr = run_model("lr", lr, df, cols, split["folds"], out, save_models=False)
    res = df[m.KEEP].copy(); res["score"], res["fold"] = oof, fold_of
    res["threshold"] = res.fold.map({r["fold"]: r["threshold"] for r in thr})
    res.to_parquet(out / "oof_lr.parquet", index=False); (out / "thresholds_lr.json").write_text(json.dumps(thr, indent=2))
    print(s, "done", flush=True)
