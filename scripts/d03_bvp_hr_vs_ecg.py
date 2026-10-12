"""D03 — wrist-PPG (BVP) HR vs ECG reference HR, PPG-DaLiA. ANALYSIS OUTPUT ONLY (never a model feature).

Primary (user decision P4): the dataset's own 8 s / 2 s reference windows. For reference window k = [2k, 2k+8),
BVP HR = 60 / median valid IBI (same filter/peak/SQI pipeline as the features, config/features_v1.yaml).
Secondary: 30 s physiology windows — feature hr_mean vs mean hr_ref over reference windows fully inside.
SQI sensitivity at 0.80/0.85/0.90/0.95 is REPORT-ONLY (P5); the v1 threshold stays 0.9.

Writes results/<date>_D03_bvp_hr_vs_ecg_<tag>/ (per-window CSVs + summary CSVs + run_info.json). Refuses to overwrite.
Usage (repo root):  python scripts/d03_bvp_hr_vs_ecg.py --subjects 3 6 --tag smoke_v1 [--date 2026-10-12]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import skew

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import features as F  # noqa: E402
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe import windowing as wn  # noqa: E402
from wearsafe.schemas import namespaced_subject_id  # noqa: E402

SQI_BINS = [0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0001]
SAT_BINS = [-0.001, 0.0, 0.05, 1.0]


def metrics(err):
    err = np.asarray(err, dtype=float)
    err = err[np.isfinite(err)]
    if len(err) == 0:
        return {"n": 0, "mae": np.nan, "rmse": np.nan, "bias": np.nan, "pct_within_5": np.nan, "pct_within_10": np.nan}
    return {"n": len(err), "mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))),
            "bias": float(np.mean(err)), "pct_within_5": float(100 * np.mean(np.abs(err) <= 5)),
            "pct_within_10": float(100 * np.mean(np.abs(err) <= 10))}


def grouped(df, by, err_col="err"):
    rows = []
    for k, g in df.groupby(by, observed=True):
        k = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(by, k)), "windows": len(g), "coverage_pct": 100 * g[err_col].notna().mean(),
                     **metrics(g[err_col])})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--norm-tag", default="v1")
    ap.add_argument("--features-root", default="data/processed")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--interim-root", default="data/interim/ppg_dalia")
    args = ap.parse_args()
    out = REPO / args.out_root / f"{args.date}_D03_bvp_hr_vs_ecg_{args.tag}"
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    cfg = yaml.safe_load(open(REPO / "config/features_v1.yaml"))
    maps = yaml.safe_load(open(REPO / "config/label_maps.yaml"))
    names = {int(k): v for k, v in maps["ppg_dalia"]["original_label"].items()}
    norm = REPO / args.interim_root / f"normalized_signals_{args.norm_tag}"
    ph = cfg["physiology"]
    rows, t0 = [], time.time()
    for n in args.subjects:
        sid = namespaced_subject_id("ppg_dalia", n)
        bvp = pd.read_parquet(norm / sid / "wrist_bvp.parquet", columns=["scalar_value"])["scalar_value"].to_numpy()
        sat = pd.read_parquet(norm / sid / "wrist_acc.parquet", columns=["acc_saturated"])["acc_saturated"].to_numpy()
        act = pd.read_parquet(norm / sid / "activity.parquet", columns=["original_code"])["original_code"].to_numpy()
        ref = pd.read_parquet(norm / sid / "hr_ref.parquet", columns=["k", "hr_ref_bpm"])
        for k, hr_ref in zip(ref.k.to_numpy(), ref.hr_ref_bpm.to_numpy()):
            b0, b1 = k * io.HR_REF_SHIFT_S * io.FS_BVP, (k * io.HR_REF_SHIFT_S + io.HR_REF_WIN_S) * io.FS_BVP
            a0, a1 = k * io.HR_REF_SHIFT_S * io.FS_ACT, (k * io.HR_REF_SHIFT_S + io.HR_REF_WIN_S) * io.FS_ACT
            c0, c1 = k * io.HR_REF_SHIFT_S * io.FS_ACC, (k * io.HR_REF_SHIFT_S + io.HR_REF_WIN_S) * io.FS_ACC
            hr, sqi, n_ibi = F.hr_estimate(bvp[b0:b1], io.FS_BVP, cfg)
            maj, purity, _ = wn.majority_label(act[a0:a1])
            rows.append({"subject_id": sid, "k": int(k), "t_start": float(k * io.HR_REF_SHIFT_S),
                         "activity": names[maj], "label_purity": purity, "hr_ref": hr_ref, "hr_bvp": hr,
                         "err": hr - hr_ref, "ppg_sqi": sqi, "n_valid_ibi": n_ibi,
                         "skew_sqi": float(skew(F.bandpass(bvp[b0:b1], io.FS_BVP, ph["bandpass_hz"]))),
                         "acc_saturated_frac": float(sat[c0:c1].mean())})
        print(f"{sid}: {len(ref)} reference windows, {time.time() - t0:.0f}s", flush=True)
    pw = pd.DataFrame(rows)
    out.mkdir(parents=True)
    pw.to_csv(out / "per_window_8s.csv", index=False)
    pw["sqi_bin"] = pd.cut(pw.ppg_sqi, SQI_BINS, right=False)
    pw["sat_bin"] = pd.cut(pw.acc_saturated_frac, SAT_BINS, labels=["0", "(0, 5%]", "> 5%"])
    grouped(pw, ["activity"]).to_csv(out / "primary_by_activity.csv", index=False)
    grouped(pw, ["subject_id", "activity"]).to_csv(out / "primary_by_subject_activity.csv", index=False)
    grouped(pw, ["subject_id"]).to_csv(out / "primary_by_subject.csv", index=False)
    grouped(pw.assign(all="all"), ["all"]).to_csv(out / "primary_overall.csv", index=False)
    grouped(pw, ["sqi_bin"]).astype({"sqi_bin": str}).to_csv(out / "primary_by_sqi_bin.csv", index=False)
    grouped(pw, ["sat_bin"]).astype({"sat_bin": str}).to_csv(out / "primary_by_saturation.csv", index=False)
    sens = []
    for thr in cfg["ppg_sqi"]["sensitivity_report_only"]:
        keep = pw.ppg_sqi >= thr
        sens.append({"sqi_threshold": thr, "is_v1_threshold": thr == cfg["ppg_sqi"]["threshold"],
                     "windows_kept_pct": 100 * keep.mean(), **metrics(pw.err[keep])})
    pd.DataFrame(sens).to_csv(out / "sqi_sensitivity_report_only.csv", index=False)
    sens_act = []
    for thr in cfg["ppg_sqi"]["sensitivity_report_only"]:
        for a, g in pw.groupby("activity"):
            keep = g.ppg_sqi >= thr
            sens_act.append({"sqi_threshold": thr, "activity": a, "windows_kept_pct": 100 * keep.mean(),
                             **metrics(g.err[keep])})
    pd.DataFrame(sens_act).to_csv(out / "sqi_sensitivity_by_activity_report_only.csv", index=False)

    # secondary: 30 s physiology windows
    feat = pd.read_parquet(REPO / args.features_root / "physiology" / f"ppg_dalia_features_{args.tag}.parquet")
    sec = []
    for sid, g in feat.groupby("subject_id"):
        ref = pd.read_parquet(norm / sid / "hr_ref.parquet", columns=["hr_ref_bpm"])["hr_ref_bpm"].to_numpy()
        for r in g.itertuples():
            ref_mean = float(ref[r.hr_ref_k0:r.hr_ref_k1].mean()) if r.hr_ref_k1 > r.hr_ref_k0 else np.nan
            sec.append({"subject_id": sid, "window_id": r.window_id, "activity": r.original_label,
                        "label_purity": r.label_purity, "eval_role": r.eval_role, "hr_ref_mean": ref_mean,
                        "hr_mean_bvp": r.hr_mean, "err": r.hr_mean - ref_mean, "ppg_sqi": r.ppg_sqi,
                        "physiology_uncertain": r.physiology_uncertain})
    sec = pd.DataFrame(sec)
    sec.to_csv(out / "per_window_30s.csv", index=False)
    grouped(sec, ["activity"]).to_csv(out / "secondary_30s_by_activity.csv", index=False)
    grouped(sec, ["subject_id", "activity"]).to_csv(out / "secondary_30s_by_subject_activity.csv", index=False)
    grouped(sec[~sec.physiology_uncertain], ["activity"]).to_csv(out / "secondary_30s_certain_by_activity.csv",
                                                                  index=False)
    info = {"script": "scripts/d03_bvp_hr_vs_ecg.py",
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                         text=True).stdout.strip(),
            "tag": args.tag, "subjects": args.subjects, "layer_a": str(norm.relative_to(REPO)),
            "n_8s_windows": len(pw), "n_30s_windows": len(sec), "note": "analysis output; never a model feature",
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
