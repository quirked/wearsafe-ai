"""D03 — PPG-DaLiA Layer C features (motion 2 s, context 5 s, physiology 30 s).

Reads Layer A data/interim/ppg_dalia/normalized_signals_<norm-tag>/ and Layer B windows_<windows-tag>/
(D02 v1, windowing config v2), one subject at a time. Writes
  <out-root>/motion/ppg_dalia_features_<tag>.parquet
  <out-root>/context/ppg_dalia_features_<tag>.parquet
  <out-root>/physiology/ppg_dalia_features_<tag>.parquet
  <out-root>/ppg_dalia_features_<tag>_run/{run_info.json, checks.json}
Every feature uses only samples inside its window, except hr_rel_baseline (strictly earlier windows).
The ECG reference HR is never read here. Invariant checks stop the run on failure. Refuses to overwrite.

Usage (repo root):  python scripts/d03_ppg_dalia_features.py --subjects 3 6 --tag smoke_v1 [--out-root data/processed]
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import features as F  # noqa: E402
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe.schemas import FORBIDDEN_FEATURE_COLUMNS, namespaced_subject_id  # noqa: E402

FEAT_CFG = REPO / "config/features_v1.yaml"
TASK_DIR = {"motion_2s": "motion", "context_5s": "context", "physiology_30s": "physiology"}
CARRY = ["window_id", "dataset", "subject_id", "recording_id", "trial_id", "task", "window_name", "window_start",
         "window_end", "duration", "original_label", "majority_code", "label_purity", "crosses_boundary",
         "seconds_to_nearest_boundary", "context_class", "motion_event_class", "arousal_class", "eval_role",
         "has_acc", "has_gyro", "has_bvp", "has_hr_ref", "n_hr_ref", "hr_ref_k0", "hr_ref_k1"]
STRICT_NAN = ["hr_mean", "hr_std", "hr_min", "hr_max", "ibi_mean", "ibi_std", "ppg_sqi"]


class InvariantError(RuntimeError):
    pass


def check(cond, msg, results, sid, task):
    results.append({"subject_id": sid, "task": task, "check": msg, "passed": bool(cond)})
    if not cond:
        raise InvariantError(f"{sid} {task}: FAILED {msg}")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def subject_features(sid, norm, wins, cfg):
    acc_df = pd.read_parquet(norm / sid / "wrist_acc.parquet", columns=["x", "y", "z", "acc_saturated"])
    acc = acc_df[["x", "y", "z"]].to_numpy()
    sat = acc_df["acc_saturated"].to_numpy()
    bvp = pd.read_parquet(norm / sid / "wrist_bvp.parquet", columns=["scalar_value"])["scalar_value"].to_numpy()
    out = {}
    for name in ("motion_2s", "context_5s"):
        w = wins[name][wins[name].subject_id == sid].reset_index(drop=True)
        rows = [F.motion_features(acc[a:b], io.FS_ACC, sat[a:b]) for a, b in zip(w.acc_i0, w.acc_i1)]
        out[name] = pd.concat([w[CARRY], pd.DataFrame(rows, columns=list(F.MOTION_FEATURE_NAMES))], axis=1)
    w = wins["physiology_30s"][wins["physiology_30s"].subject_id == sid].reset_index(drop=True)
    rows = [F.physiology_features(bvp[a:b], io.FS_BVP, cfg) for a, b in zip(w.bvp_i0, w.bvp_i1)]
    ph = pd.DataFrame(rows, columns=list(F.PHYSIOLOGY_FEATURE_NAMES))
    ph["physiology_uncertain"] = ph["physiology_uncertain"].astype(bool)
    ph["hr_rel_baseline"] = F.rel_baseline(w.window_start.to_numpy(), w.window_end.to_numpy(),
                                           ph.hr_mean.to_numpy(), ph.physiology_uncertain.to_numpy(),
                                           cfg["physiology"]["baseline_s"])
    out["physiology_30s"] = pd.concat([w[CARRY], ph], axis=1)
    return out


def feature_checks(df, wins_sub, name, results, sid):
    feats = list(F.PHYSIOLOGY_FEATURE_NAMES if name == "physiology_30s" else F.MOTION_FEATURE_NAMES)
    check(len(df) == len(wins_sub) and (df.window_id.to_numpy() == wins_sub.window_id.to_numpy()).all(),
          f"one feature row per D02 window, same order ({len(df)})", results, sid, name)
    check(not (set(feats) & set(FORBIDDEN_FEATURE_COLUMNS)), "no forbidden column among feature columns",
          results, sid, name)
    check("hr_ref_bpm" not in df.columns, "ECG reference HR not present in the feature table", results, sid, name)
    if name != "physiology_30s":
        n = int(df[feats].isna().sum().sum())
        check(n == 0, f"motion features have 0 NaN (got {n})", results, sid, name)
        check(df.dominant_freq.between(0, io.FS_ACC / 2).all(), "dominant_freq in [0, 16] Hz", results, sid, name)
        check(df.spectral_entropy.between(0, 1).all(), "spectral_entropy in [0, 1]", results, sid, name)
        check((df.acc_mag_std >= 0).all() and (df.acc_mag_max <= np.sqrt(3) * 2 * 9.80665 + 1e-6).all(),
              "acc magnitude within E4 range (<= sqrt(3)*2 g)", results, sid, name)
    else:
        bad = df.loc[~df.physiology_uncertain, STRICT_NAN].isna().sum().sum()
        check(bad == 0, f"strict physiology NaN only where physiology_uncertain (violations {int(bad)})",
              results, sid, name)
        hr = df.hr_mean.dropna()
        check(hr.between(30, 220).all(), "hr_mean within 30-220 bpm or NaN", results, sid, name)
        check(df.ppg_sqi.dropna().between(0, 1).all(), "ppg_sqi within [0, 1] or NaN", results, sid, name)
        early = df.window_start < 300
        check(df.loc[early, "hr_rel_baseline"].isna().all(), "hr_rel_baseline NaN before 300 s of history",
              results, sid, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--norm-tag", default="v1")
    ap.add_argument("--windows-tag", default="v1")
    ap.add_argument("--interim-root", default="data/interim/ppg_dalia")
    ap.add_argument("--out-root", default="data/processed")
    args = ap.parse_args()
    out_root = REPO / args.out_root
    outs = {n: out_root / d / f"ppg_dalia_features_{args.tag}.parquet" for n, d in TASK_DIR.items()}
    run_dir = out_root / f"ppg_dalia_features_{args.tag}_run"
    for p in list(outs.values()) + [run_dir]:
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite (CLAUDE.md §2.1)")
    cfg = yaml.safe_load(open(FEAT_CFG))
    norm = REPO / args.interim_root / f"normalized_signals_{args.norm_tag}"
    win_dir = REPO / args.interim_root / f"windows_{args.windows_tag}"
    win_info = json.loads((win_dir / "run_info.json").read_text())
    wins = {n: pd.read_parquet(win_dir / f"{n}.parquet") for n in TASK_DIR}
    results, parts = [], {n: [] for n in TASK_DIR}
    t0 = time.time()
    for n in args.subjects:
        sid = namespaced_subject_id("ppg_dalia", n)
        res = subject_features(sid, norm, wins, cfg)
        for name, df in res.items():
            sub = wins[name][wins[name].subject_id == sid].reset_index(drop=True)
            feature_checks(df, sub, name, results, sid)
            parts[name].append(df)
            extra = (f", physiology_uncertain {df.physiology_uncertain.mean():.1%}" if name == "physiology_30s" else "")
            print(f"{sid} {name}: {len(df)} rows{extra}, {time.time() - t0:.0f}s", flush=True)
    counts = {}
    for name, path in outs.items():
        df = pd.concat(parts[name], ignore_index=True)
        check(df.window_id.is_unique, "window_id unique across subjects", results, "ALL", name)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        counts[name] = len(df)
    run_dir.mkdir(parents=True)
    info = {"script": "scripts/d03_ppg_dalia_features.py",
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                         text=True).stdout.strip(),
            "tag": args.tag, "subjects": args.subjects, "layer_a": str(norm.relative_to(REPO)),
            "layer_b": str(win_dir.relative_to(REPO)), "windowing_config": win_info.get("windowing_config"),
            "features_config_sha256": sha(FEAT_CFG), "outputs": {k: str(v.relative_to(REPO)) if v.is_relative_to(REPO)
                                                                  else str(v) for k, v in outs.items()},
            "rows": counts, "seed": None, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (run_dir / "run_info.json").write_text(json.dumps(info, indent=2))
    (run_dir / "checks.json").write_text(json.dumps(results, indent=2))
    print(f"all {len(results)} checks passed; wrote {list(outs.values())}")


if __name__ == "__main__":
    main()
