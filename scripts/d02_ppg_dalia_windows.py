"""D02 — PPG-DaLiA Layer B windows (index references into Layer A; user decision P7).

Reads data/interim/ppg_dalia/normalized_signals_<in-tag>/ and writes
data/interim/ppg_dalia/windows_<tag>/{motion_2s,context_5s,physiology_30s}.parquet
plus run_info.json, checks.json and summary tables (window counts, labels, roles, saturation).

Window rules: --config (default config/windowing_v2.yaml; v1 lacks the boundary margin). Label maps: config/label_maps.yaml.
No window is dropped. Invariant checks stop the run on failure (CLAUDE.md §3). Refuses to overwrite.

Usage (repo root):  python scripts/d02_ppg_dalia_windows.py --tag smoke_v2 --in-tag smoke_v1 \
                        [--config config/windowing_v2.yaml] [--root data/interim/ppg_dalia]
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
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe import windowing as wn  # noqa: E402
from wearsafe.schemas import is_valid_subject_id  # noqa: E402

LABEL_MAPS = REPO / "config/label_maps.yaml"
TASK_ABBR = {"motion_2s": "mot2", "context_5s": "ctx5", "physiology_30s": "phy30"}


class InvariantError(RuntimeError):
    pass


def check(cond, msg, results, subject, task):
    results.append({"subject_id": subject, "task": task, "check": msg, "passed": bool(cond)})
    if not cond:
        raise InvariantError(f"{subject} {task}: FAILED {msg}")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def window_role(label, purity, margin_s, maps, cfg):
    """eval_role per config/windowing_v2.yaml (margin_s is ignored if the config has no boundary_margin_s)."""
    m, r = maps["ppg_dalia"], cfg["eval_role"]
    if label not in m["training_v1"]["context"]:
        return m["eval_role"][label]
    if purity < r["purity_threshold"]:
        return "false_alert_eval_only"
    if "boundary_margin_s" in r and margin_s < r["boundary_margin_s"]:
        return "false_alert_eval"
    return "train_candidate"


def make_windows(subject_dir, name, spec, maps, cfg):
    act = pd.read_parquet(subject_dir / "activity.parquet", columns=["original_code", "original_label",
                                                                    "recording_id", "subject_id", "trial_id"])
    sat = pd.read_parquet(subject_dir / "wrist_acc.parquet", columns=["acc_saturated"])["acc_saturated"].to_numpy()
    n_bvp = len(pd.read_parquet(subject_dir / "wrist_bvp.parquet", columns=["sample_idx"]))
    n_ref = len(pd.read_parquet(subject_dir / "hr_ref.parquet", columns=["k"]))
    codes = act["original_code"].to_numpy()
    duration = len(codes) / io.FS_ACT
    m = maps["ppg_dalia"]
    names = {int(k): v for k, v in m["original_label"].items()}
    changes = wn.change_times(codes, io.FS_ACT)
    sid, rid, trial = act["subject_id"].iat[0], act["recording_id"].iat[0], act["trial_id"].iat[0]
    rows = []
    for i, (start, end) in enumerate(wn.window_bounds(duration, spec["length_s"], spec["step_s"])):
        a0, a1 = wn.sample_range(start, end, io.FS_ACT)
        c0, c1 = wn.sample_range(start, end, io.FS_ACC)
        b0, b1 = wn.sample_range(start, end, io.FS_BVP)
        k0, k1 = wn.hr_ref_range(start, end, io.HR_REF_WIN_S, io.HR_REF_SHIFT_S, n_ref)
        maj, purity, n_distinct = wn.majority_label(codes[a0:a1])
        margin = wn.seconds_to_nearest_boundary(float(start), float(end), changes)
        label = names[maj]
        ctx = m["context_class"][label]
        rows.append({
            "window_id": f"{sid}_{TASK_ABBR[name]}_{i:06d}", "dataset": "ppg_dalia", "subject_id": sid,
            "recording_id": rid, "trial_id": trial, "task": spec["task"], "window_name": name,
            "window_start": float(start), "window_end": float(end), "duration": float(end - start),
            "acc_i0": c0, "acc_i1": c1, "bvp_i0": b0, "bvp_i1": b1, "act_i0": a0, "act_i1": a1,
            "hr_ref_k0": k0, "hr_ref_k1": k1, "n_hr_ref": k1 - k0,
            "original_label": label, "majority_code": maj, "label_purity": purity,
            "n_distinct_labels": n_distinct, "crosses_boundary": n_distinct > 1,
            "seconds_to_nearest_boundary": margin,
            "context_class": ctx, "motion_event_class": m["motion_event_class"]["default"]
            if label not in m["motion_event_class"] else m["motion_event_class"][label],
            "arousal_class": None,                         # user decision B: PPG-DaLiA has no arousal labels
            "eval_role": window_role(label, purity, margin, maps, cfg),
            "has_acc": c1 <= len(sat), "has_gyro": False, "has_bvp": b1 <= n_bvp, "has_hr_ref": k1 > k0,
            "fs_acc": float(io.FS_ACC), "fs_bvp": float(io.FS_BVP),
            "acc_saturated_frac": float(sat[c0:c1].mean()),
            "acc_missing_frac": 0.0 if c1 <= len(sat) else float((c1 - len(sat)) / (c1 - c0)),
            "bvp_missing_frac": 0.0 if b1 <= n_bvp else float((b1 - n_bvp) / (b1 - b0)),
        })
    df = pd.DataFrame(rows)
    df["arousal_class"] = df["arousal_class"].astype(object)
    return df, duration, codes, len(sat), n_bvp


def window_checks(df, name, spec, duration, codes, n_acc, n_bvp, maps, cfg, results):
    sid = df["subject_id"].iat[0] if len(df) else "?"
    exp = wn.expected_count(duration, spec["length_s"], spec["step_s"])
    check(len(df) == exp, f"window count {len(df)} == floor((D-w)/step)+1 = {exp}", results, sid, name)
    w = spec["length_s"]
    for col, fs in (("acc", io.FS_ACC), ("bvp", io.FS_BVP), ("act", io.FS_ACT)):
        n = (df[f"{col}_i1"] - df[f"{col}_i0"]).unique().tolist()
        check(n == [int(w * fs)], f"{col}: every window has exactly {int(w * fs)} samples (got {n})",
              results, sid, name)
    check(df["acc_i1"].max() <= n_acc and df["bvp_i1"].max() <= n_bvp and df["act_i1"].max() <= len(codes),
          "no window extends past the recording end", results, sid, name)
    check(df["window_start"].min() >= 0 and df["window_end"].max() <= duration, "0 <= start, end <= D",
          results, sid, name)
    check(df["window_id"].is_unique, "window_id unique", results, sid, name)
    check(df["subject_id"].nunique() == 1 and df["recording_id"].nunique() == 1,
          "no window spans two subjects or recordings", results, sid, name)
    check(df["subject_id"].map(is_valid_subject_id).all(), "namespaced subject IDs valid", results, sid, name)
    check(((df["label_purity"] > 0) & (df["label_purity"] <= 1)).all(), "purity in (0, 1]", results, sid, name)
    check((df["crosses_boundary"] == (df["label_purity"] < 1)).all(), "crosses_boundary <=> purity < 1",
          results, sid, name)
    # purity recomputed independently from the raw code slices
    re = [np.mean(codes[a:b] == c) for a, b, c in zip(df["act_i0"], df["act_i1"], df["majority_code"])]
    check(np.allclose(re, df["label_purity"]), "purity recomputed from activity samples matches", results, sid, name)
    check(df["arousal_class"].isna().all(), "arousal_class is null for every PPG-DaLiA window (decision B)",
          results, sid, name)
    check((df["motion_event_class"] == "normal_adl").all(), "motion_event_class normal_adl for every window (P3)",
          results, sid, name)
    m = maps["ppg_dalia"]
    thr = cfg["eval_role"]["purity_threshold"]
    margin_cfg = cfg["eval_role"]["boundary_margin_s"]
    # seconds_to_nearest_boundary recomputed by brute force (windows x changes) from the raw codes
    ch = (np.flatnonzero(np.diff(codes) != 0) + 1) / io.FS_ACT
    st, en = df["window_start"].to_numpy()[:, None], df["window_end"].to_numpy()[:, None]
    if len(ch):
        inside = ((ch[None, :] > st) & (ch[None, :] < en)).any(axis=1)
        dist = np.where(ch[None, :] <= st, st - ch[None, :], np.where(ch[None, :] >= en, ch[None, :] - en, 0.0))
        brute = np.where(inside, 0.0, dist.min(axis=1))
    else:
        brute = np.full(len(df), np.inf)
    check(np.array_equal(brute, df["seconds_to_nearest_boundary"].to_numpy()),
          "seconds_to_nearest_boundary matches a brute-force recomputation", results, sid, name)
    check((df.loc[df["crosses_boundary"], "seconds_to_nearest_boundary"] == 0).all(),
          "boundary-crossing windows have distance 0", results, sid, name)
    tc = df["eval_role"] == "train_candidate"
    check((df.loc[tc, "seconds_to_nearest_boundary"] >= margin_cfg).all(),
          f"train_candidate only with seconds_to_nearest_boundary >= {margin_cfg} s", results, sid, name)
    near = (df["original_label"].isin(m["training_v1"]["context"]) & (df["label_purity"] >= thr)
            & (df["seconds_to_nearest_boundary"] < margin_cfg))
    check((df.loc[near, "eval_role"] == "false_alert_eval").all(),
          "pure training-label windows within the margin are false_alert_eval (kept)", results, sid, name)
    check(((df["eval_role"] == "train_candidate") == (df["original_label"].isin(m["training_v1"]["context"])
          & (df["label_purity"] >= thr) & (df["seconds_to_nearest_boundary"] >= margin_cfg))).all(),
          "train_candidate <=> training label & purity >= threshold & margin met", results, sid, name)
    check((df.loc[tc, "label_purity"] >= thr).all() and df.loc[tc, "original_label"].isin(m["training_v1"]["context"]).all(),
          "train_candidate only for training labels with purity >= threshold", results, sid, name)
    check(not df.loc[tc, "context_class"].isin([None, "TODO"]).any(), "no train_candidate with null/TODO context",
          results, sid, name)
    check(not df.loc[df["original_label"].isin(m["training_v1"]["excluded"]), "eval_role"].eq("train_candidate").any(),
          "lunch/transient never train_candidate", results, sid, name)
    check(df["eval_role"].notna().all(), "every window has an eval_role", results, sid, name)
    # reference HR windows fully inside each window, recomputed by brute force over all k
    n_ref = io.expected_hr_ref_count(duration)   # equals the hr_ref row count (checked in normalisation)
    ref_s = np.arange(n_ref) * io.HR_REF_SHIFT_S
    brute = [int(((ref_s >= s) & (ref_s + io.HR_REF_WIN_S <= e)).sum())
             for s, e in zip(df["window_start"], df["window_end"])]
    check(brute == df["n_hr_ref"].tolist() and (df["has_hr_ref"] == (df["n_hr_ref"] > 0)).all(),
          "n_hr_ref / has_hr_ref match a brute-force count", results, sid, name)
    check(df[["acc_missing_frac", "bvp_missing_frac"]].eq(0).all().all(), "no missing ACC/BVP samples",
          results, sid, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="output version, e.g. smoke_v2 or v1")
    ap.add_argument("--in-tag", required=True, help="Layer A version to read, e.g. smoke_v1 or v1")
    ap.add_argument("--config", default="config/windowing_v2.yaml")
    ap.add_argument("--root", default="data/interim/ppg_dalia")
    args = ap.parse_args()
    root = REPO / args.root
    src = root / f"normalized_signals_{args.in_tag}"
    win_cfg = REPO / args.config
    out = root / f"windows_{args.tag}"
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite (CLAUDE.md §2.1)")
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        raise FileExistsError(f"{tmp} exists from an interrupted run; inspect it, do not overwrite")
    maps = yaml.safe_load(open(LABEL_MAPS))
    cfg = yaml.safe_load(open(win_cfg))
    if "boundary_margin_s" not in cfg["eval_role"]:
        raise ValueError(f"{args.config} has no boundary_margin_s; use config/windowing_v2.yaml or later")
    subjects = sorted(p for p in src.iterdir() if p.is_dir())
    results, tables = [], {name: [] for name in cfg["tasks"]}
    t0 = time.time()
    for d in subjects:
        for name, spec in cfg["tasks"].items():
            df, duration, codes, n_acc, n_bvp = make_windows(d, name, spec, maps, cfg)
            window_checks(df, name, spec, duration, codes, n_acc, n_bvp, maps, cfg, results)
            tables[name].append(df)
            print(f"{d.name} {name}: {len(df)} windows, {df['crosses_boundary'].mean():.2%} cross a boundary, "
                  f"{time.time() - t0:.0f}s", flush=True)
    tmp.mkdir(parents=True)
    counts = []
    for name, parts in tables.items():
        df = pd.concat(parts, ignore_index=True)
        # cross-subject check on the combined table
        check(df["window_id"].is_unique, "window_id unique across subjects", results, "ALL", name)
        df.to_parquet(tmp / f"{name}.parquet", index=False)
        counts.append(df.groupby(["subject_id", "original_label", "eval_role"]).size().rename("n_windows")
                      .reset_index().assign(window_name=name))
    pd.concat(counts).to_csv(tmp / "window_counts_by_label_role.csv", index=False)
    info = {"script": "scripts/d02_ppg_dalia_windows.py",
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                         text=True).stdout.strip(),
            "tag": args.tag, "input": str(src.relative_to(REPO)) if src.is_relative_to(REPO) else str(src),
            "windowing_config": args.config, "windowing_config_sha256": sha(win_cfg), "label_maps_sha256": sha(LABEL_MAPS), "seed": None,
            "n_windows": {k: int(sum(len(p) for p in v)) for k, v in tables.items()},
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (tmp / "run_info.json").write_text(json.dumps(info, indent=2))
    (tmp / "checks.json").write_text(json.dumps(results, indent=2))
    tmp.rename(out)
    print(f"all {len(results)} checks passed; wrote {out}")


if __name__ == "__main__":
    main()
