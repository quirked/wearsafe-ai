"""SQI v2 selection on PPG-DaLiA DEV (config/sqi_v2.yaml) + TEST coverage/error report. Writes
results/2026-10-12_SQI_v2_demo_v0/{gated_windows.parquet, selection.json, test_by_activity.csv}."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results/2026-10-12_SQI_v2_demo_v0"
GATE = 0.5671


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    w = pd.read_csv(REPO / "results/2026-10-12_D03_bvp_hr_vs_ecg_v1/per_window_30s.csv")
    pw = pd.read_parquet(REPO / "data/interim/ppg_dalia/windows_v1/physiology_30s.parquet")
    ph = pd.read_parquet(REPO / "data/processed/physiology/ppg_dalia_features_v1.parquet", columns=["window_id", "hr_mean"])
    std = []
    for sid, g in pw.groupby("subject_id", sort=False):
        acc = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/wrist_acc.parquet", columns=["x", "y", "z"]).to_numpy()
        mag = np.sqrt((acc ** 2).sum(1))
        std += [(i, float(mag[a:b].std())) for i, a, b in zip(g.window_id, g.acc_i0, g.acc_i1)]
    w = w.merge(pd.DataFrame(std, columns=["window_id", "acc_mag_std"]), on="window_id").merge(ph, on="window_id")
    w["has_hr"] = w.hr_mean.between(30, 220)
    w["base"] = (w.acc_mag_std <= GATE) & w.has_hr & w.hr_ref_mean.notna()
    w["abs_err"] = (w.hr_mean_bvp - w.hr_ref_mean).abs()
    OUT.mkdir(parents=True)
    w.to_parquet(OUT / "gated_windows.parquet", index=False)
    dev = w[w.subject_id.isin(part["ppg_dalia"]["dev"]) & w.base]
    rows = []
    for c in [0.5, 0.6, 0.7, 0.8, 0.9]:
        k = dev[dev.ppg_sqi >= c]
        rows.append({"cutoff": c, "windows": len(k), "coverage_pct_of_gated": 100 * len(k) / len(dev), "mae": k.abs_err.mean(),
                     "within10_pct": 100 * (k.abs_err <= 10).mean()})
    t = pd.DataFrame(rows)
    ok = t[(t.mae <= 5) & (t.within10_pct >= 85)]
    chosen = float(ok.cutoff.min()) if len(ok) else 0.9
    sel = {"chosen_cutoff": chosen, "qualified": bool(len(ok)), "dev_table": t.to_dict("records"),
           "note": "chosen on DEV only, before any further step"}
    (OUT / "selection.json").write_text(json.dumps(sel, indent=2))
    test = w[w.subject_id.isin(part["ppg_dalia"]["test"]) & w.base]
    rr = []
    for a, g in list(test.groupby("activity")) + [("ALL", test)]:
        r = {"activity": a, "gated_windows": len(g)}
        for nm, c in (("v1", 0.9), ("v2", chosen)):
            k = g[g.ppg_sqi >= c]
            r[f"{nm}_coverage_pct"] = 100 * len(k) / len(g) if len(g) else np.nan
            r[f"{nm}_mae"] = k.abs_err.mean()
            r[f"{nm}_within10_pct"] = 100 * (k.abs_err <= 10).mean() if len(k) else np.nan
        rr.append(r)
    pd.DataFrame(rr).to_csv(OUT / "test_by_activity.csv", index=False)
    print(t.round(2).to_string()); print("chosen", chosen); print(pd.DataFrame(rr).round(1).to_string())


if __name__ == "__main__":
    main()
