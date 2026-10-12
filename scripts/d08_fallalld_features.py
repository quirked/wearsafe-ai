"""D08 — FallAllD motion features: features_v1 (§14) and features_v2 (v1 + saturation-aware), for both the
unclipped and e4_clipped versions. Same code as PPG-DaLiA (wearsafe.features.motion_features); every feature uses
only the samples inside its window.

Writes <out-root>/motion/fallalld_{version}_features-{v1,v2}_<tag>.parquet and
<out-root>/fallalld_features_<tag>_run/{run_info.json, checks.json, edge_check.csv}. Refuses to overwrite.
Usage (repo root):  python scripts/d08_fallalld_features.py --tag smoke_v1
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
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import features as F  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402
from wearsafe.schemas import FORBIDDEN_FEATURE_COLUMNS  # noqa: E402

CFG = REPO / "config/fallalld_v1.yaml"
VERSIONS = ("unclipped", "e4_clipped")
CARRY = ["window_id", "dataset", "subject_id", "record_id", "activity_id", "trial_no", "original_label", "kind",
         "window_start", "window_end", "window_role", "motion_event_class", "eval_role", "position_matched",
         "contains_impact_time", "clip_level_class", "overlap_group_id", "dedup_representative"]


class InvariantError(RuntimeError):
    pass


def check(cond, msg, results, scope):
    results.append({"scope": scope, "check": msg, "passed": bool(cond)})
    if not cond:
        raise InvariantError(f"{scope}: FAILED {msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--interim-root", default="data/interim/fallalld")
    ap.add_argument("--out-root", default="data/processed")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(CFG))
    fs = cfg["resample"]["target_hz"]
    sig = REPO / args.interim_root / f"normalized_signals_{args.tag}"
    win = pd.read_parquet(REPO / args.interim_root / f"windows_{args.tag}" / "windows.parquet")
    out_root = REPO / args.out_root
    outs = {(v, fv): out_root / "motion" / f"fallalld_{v}_features-{fv}_{args.tag}.parquet"
            for v in VERSIONS for fv in ("v1", "v2")}
    run_dir = out_root / f"fallalld_features_{args.tag}_run"
    for p in list(outs.values()) + [run_dir]:
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite (CLAUDE.md §2.1)")
    results, tables, t0 = [], {}, time.time()
    v1_names, v2_names = list(F.MOTION_FEATURE_NAMES), list(F.MOTION_FEATURE_NAMES_V2)
    for v in VERSIONS:
        rows = []
        for sid, wsub in win.groupby("subject_id", sort=True):
            la = pd.read_parquet(sig / v / f"{sid}.parquet")
            by_rec = {r: g for r, g in la.groupby("record_id")}
            for r in wsub.itertuples():
                g = by_rec[r.record_id]
                acc = g[["x", "y", "z"]].to_numpy()[r.i0:r.i1]
                sat = g[["sat_x", "sat_y", "sat_z"]].to_numpy()[r.i0:r.i1]
                f1 = F.motion_features(acc, fs, sat.any(axis=1))
                f2 = F.saturation_features_v2(acc, fs, sat)
                mag = np.sqrt((acc ** 2).sum(axis=1))
                k = int(np.argmax(mag))
                rows.append({**f1, **f2, "_k": k, "_n": len(mag), "_wid": r.window_id})
        feats = pd.DataFrame(rows)
        base = win[CARRY].reset_index(drop=True)
        tables[(v, "v1")] = pd.concat([base, feats[v1_names]], axis=1)
        tables[(v, "v2")] = pd.concat([base, feats[v2_names]], axis=1)
        # checks
        check(len(feats) == len(win) and (feats._wid.to_numpy() == base.window_id.to_numpy()).all(),
              f"one feature row per window, aligned by window_id ({len(feats)})", results, v)
        check(int(feats[v1_names].isna().sum().sum()) == 0, "features_v1: 0 NaN", results, v)
        exp_post = (feats._n - feats._k - 1) < F.POST_PEAK_MIN_SAMPLES
        exp_pre = feats._k == 0
        check((feats.post_peak_stillness.isna() == exp_post).all() and (feats.pre_peak_min_mag.isna() == exp_pre).all()
              and int(feats[[c for c in F.SATURATION_FEATURE_NAMES_V2 if c not in ("post_peak_stillness", "pre_peak_min_mag")]]
                      .isna().sum().sum()) == 0,
              "features_v2: NaN only by the documented rules (post-peak < 8 samples; peak at first sample)", results, v)
        check(not (set(v2_names) & set(FORBIDDEN_FEATURE_COLUMNS)), "no forbidden column among feature columns", results, v)
        check(feats.dominant_freq.between(0, fs / 2).all() and feats.spectral_entropy.between(0, 1).all(),
              "dominant_freq in [0, 16] Hz and spectral_entropy in [0, 1]", results, v)
        if v == "unclipped":
            check((feats[["acc_saturated_frac", "sat_longest_run_s", "sat_n_runs", "sat_max_axes"]] == 0).all().all(),
                  "unclipped: no saturation (FallAllD ±8 g rails never reached)", results, v)
        else:
            check(feats.acc_mag_max.max() <= np.sqrt(3) * 2 * 9.80665 + 1e-6,
                  "e4_clipped: |a| <= sqrt(3) * 2 g", results, v)
        print(f"{v}: {len(feats)} windows, {time.time() - t0:.0f}s", flush=True)
    check((tables[("unclipped", "v1")].window_id.to_numpy() == tables[("e4_clipped", "v1")].window_id.to_numpy()).all(),
          "same rows in the same order for both versions", results, "ALL")
    # edge-artefact check (REDEFINED after the D08 smoke stop, user decision 1): converted edge window vs the SAME
    # window on the native 238 Hz signal (e4: clipped at 238 Hz, not quantised). Per version, median over cyclic-ADL
    # clips of |acc_mag_mean(converted) / acc_mag_mean(native) - 1|, first and last window, must be < 1%.
    w_all, _ = fio.wrist_records(REPO)
    raw = dict(zip(w_all.record_id, w_all.Acc))
    nat = cfg["native_hz"]
    edge_rows = []
    for v in VERSIONS:
        t = tables[(v, "v1")]
        c = t[t.activity_id.isin(cfg["cyclic_adl_ids"])]
        last = c.window_start.max()
        rel = {}
        for r in c.itertuples():
            g = mh.counts_to_g(raw[r.record_id], cfg["counts_per_g"])
            if v == "e4_clipped":
                g = mh.e4_clip(g)
            seg = g[int(round(r.window_start * nat)):int(round(r.window_end * nat))]
            native_mean = float(np.sqrt((seg ** 2).sum(axis=1)).mean() * mh.G)
            rel.setdefault(r.window_start, []).append(abs(r.acc_mag_mean / native_mean - 1))
        interior = np.concatenate([np.array(x) for k, x in rel.items() if 0 < k < last])
        for pos, name in ((0.0, "first"), (last, "last")):
            x = np.array(rel[pos])
            edge_rows.append({"version": v, "edge": name, "n_clips": len(x), "median_abs_rel_diff": float(np.median(x)),
                              "p95_abs_rel_diff": float(np.percentile(x, 95)),
                              "interior_median_abs_rel_diff": float(np.median(interior))})
            check(np.median(x) < cfg["prechecks"]["edge_artefact_max_rel_diff"],
                  f"edge-artefact (redefined): {name} window, converted vs native 238 Hz, median |rel diff| "
                  f"{np.median(x):.4%} < 1%", results, v)
    # clip-centre intensity pattern (dataset property, report only): median acc_mag_mean per window start / interior
    prof_rows = []
    for v in VERSIONS:
        t = tables[(v, "v1")]
        c = t[t.activity_id.isin(cfg["cyclic_adl_ids"])]
        interior = c[(c.window_start > 0) & (c.window_start < c.window_start.max())].acc_mag_mean.median()
        for st, g in c.groupby("window_start"):
            prof_rows.append({"version": v, "window_start": st, "median_acc_mag_mean": g.acc_mag_mean.median(),
                              "pct_vs_interior": 100 * (g.acc_mag_mean.median() / interior - 1)})
    out_root.joinpath("motion").mkdir(parents=True, exist_ok=True)
    for key, p in outs.items():
        tables[key].to_parquet(p, index=False)
    run_dir.mkdir(parents=True)
    pd.DataFrame(edge_rows).to_csv(run_dir / "edge_check.csv", index=False)
    pd.DataFrame(prof_rows).to_csv(run_dir / "clip_centre_profile.csv", index=False)
    info = {"script": "scripts/d08_fallalld_features.py",
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                         text=True).stdout.strip(),
            "tag": args.tag, "config_sha256": hashlib.sha256(CFG.read_bytes()).hexdigest(),
            "features_v1": v1_names, "features_v2": v2_names, "rows": len(win),
            "outputs": {f"{k[0]}/{k[1]}": str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)
                        for k, p in outs.items()},
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (run_dir / "run_info.json").write_text(json.dumps(info, indent=2))
    (run_dir / "checks.json").write_text(json.dumps(results, indent=2))
    print(f"all {len(results)} checks passed")


if __name__ == "__main__":
    main()
