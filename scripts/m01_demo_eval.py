"""M01-demo (demo_v0, PRELIMINARY) — metrics for the FallAllD motion grid from saved out-of-fold scores.

Reads results/<date>_M01_demo_v0/motion/<config>/oof_<name>.parquet and writes
  results/<date>_M01_demo_v0/motion/{summary.csv, per_subject.csv, stop_check.json}
  reports/M01_demo_v0_motion_tables.md
STOP rule (PROJECT_LOG M01-demo entry): any model PR-AUC > 0.98, or a shortcut baseline (peak / saturation;
position-only on the position-matched subset) within 0.05 PR-AUC of the best model of the same configuration.
Usage (repo root):  python scripts/m01_demo_eval.py --date 2026-10-12
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from d02_smoke_report import md  # noqa: E402

CONFIGS = ["unclipped_v1", "unclipped_v2", "e4_clipped_v1", "e4_clipped_v2"]
NAMES = ["lr", "rf", "base_position", "base_peak", "base_saturation"]


def window_metrics(d):
    tc = d[d.eval_role == "train_candidate"]
    y = (tc.window_role == "fall_positive").astype(int)
    pred = tc.score >= tc.threshold
    tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    pm = tc[tc.window_start == 9.0]
    ypm = (pm.window_role == "fall_positive").astype(int)
    return {"pr_auc": average_precision_score(y, tc.score), "roc_auc": roc_auc_score(y, tc.score),
            "base_rate": float(y.mean()), "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / (prec + rec) if prec and rec else np.nan,
            "adl_window_fp_rate": float(pred[y == 0].mean()),
            "pm_pr_auc": average_precision_score(ypm, pm.score), "pm_base_rate": float(ypm.mean())}


def clip_metrics(d, dedup=False):
    c = d.groupby("record_id").agg(score=("score", "max"), thr=("threshold", "first"), kind=("kind", "first"),
                                   role=("window_role", lambda s: s.iloc[0] if s.nunique() == 1 else "fall"),
                                   activity_id=("activity_id", "first"), rep=("dedup_representative", "first"),
                                   subject_id=("subject_id", "first"))
    if dedup:
        c = c[c.rep]
    det = c.score >= c.thr
    fall = (c.kind == "fall") & (c.role != "label_uncertain_fall")
    unc = c.role == "label_uncertain_fall"
    probe = c.role == "hard_negative_probe"
    adl = (c.kind == "adl") & ~probe
    return {"clip_fall_detect_pct": 100 * det[fall].mean(), "clip_false_alarm_pct": 100 * det[adl].mean(),
            "probe_clip_trigger_pct": 100 * det[probe].mean(),
            "label_uncertain_detect_pct": 100 * det[unc].mean() if unc.any() else np.nan,
            "n_fall_clips": int(fall.sum()), "n_adl_clips": int(adl.sum()), "n_probe_clips": int(probe.sum()),
            "n_label_uncertain_clips": int(unc.sum())}


def per_subject(d):
    rows = []
    for sid, g in d.groupby("subject_id"):
        tc = g[g.eval_role == "train_candidate"]
        y = (tc.window_role == "fall_positive").astype(int)
        pred = tc.score >= tc.threshold
        cm = clip_metrics(g)
        rows.append({"subject_id": sid, "has_falls": bool(y.sum() > 0),
                     "pr_auc": average_precision_score(y, tc.score) if y.sum() else np.nan,
                     "fall_window_recall": float(pred[y == 1].mean()) if y.sum() else np.nan,
                     "adl_window_fp_rate": float(pred[y == 0].mean()),
                     "clip_fall_detect_pct": cm["clip_fall_detect_pct"] if cm["n_fall_clips"] else np.nan,
                     "clip_false_alarm_pct": cm["clip_false_alarm_pct"],
                     "probe_window_trigger_pct": 100 * (g[g.window_role == "hard_negative_probe"].score
                                                         >= g[g.window_role == "hard_negative_probe"].threshold).mean(),
                     "threshold": float(g.threshold.iloc[0])})
    return pd.DataFrame(rows)


def ms(x):
    x = pd.Series(x).dropna()
    return f"{x.mean():.3f} ± {x.std(ddof=0):.3f}" if len(x) else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-12")
    ap.add_argument("--run", default="")
    args = ap.parse_args()
    root = REPO / f"results/{args.date}_M01_demo_v0{args.run}/motion"
    out_md = REPO / "reports/M01_demo_v0_motion_tables.md"
    for p in (out_md, root / "summary.csv"):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite")
    rows, subj = [], []
    for cfg in CONFIGS:
        for name in NAMES:
            p = root / cfg / f"oof_{name}.parquet"
            if not p.exists():
                continue
            d = pd.read_parquet(p)
            thr = json.loads((root / cfg / f"thresholds_{name}.json").read_text())
            r = {"config": cfg, "model": name, **window_metrics(d), **clip_metrics(d),
                 **{f"dedup_{k}": v for k, v in clip_metrics(d, dedup=True).items() if k.endswith("pct")},
                 "probe_window_trigger_pct": 100 * (d[d.window_role == "hard_negative_probe"].score
                                                    >= d[d.window_role == "hard_negative_probe"].threshold).mean(),
                 "threshold_median": float(np.median([t["threshold"] for t in thr])),
                 "threshold_min": float(min(t["threshold"] for t in thr)),
                 "threshold_max": float(max(t["threshold"] for t in thr))}
            ps = per_subject(d)
            for k in ("pr_auc", "fall_window_recall", "adl_window_fp_rate", "clip_fall_detect_pct", "clip_false_alarm_pct"):
                r[f"subj_{k}"] = ms(ps[k])
            rows.append(r)
            subj.append(ps.assign(config=cfg, model=name))
    s = pd.DataFrame(rows)
    ps = pd.concat(subj)
    s.to_csv(root / "summary.csv", index=False)
    ps.to_csv(root / "per_subject.csv", index=False)
    # STOP rule
    reasons = []
    for cfg, g in s.groupby("config"):
        best = g[g.model.isin(["lr", "rf"])].pr_auc.max()
        for r in g.itertuples():
            if r.model in ("lr", "rf") and r.pr_auc > 0.98:
                reasons.append(f"{cfg} {r.model}: PR-AUC {r.pr_auc:.3f} > 0.98")
            if r.model in ("base_peak", "base_saturation") and r.pr_auc >= best - 0.05:
                reasons.append(f"{cfg} {r.model}: PR-AUC {r.pr_auc:.3f} within 0.05 of best model {best:.3f}")
            if r.model == "base_position" and r.pm_pr_auc >= g[g.model.isin(['lr', 'rf'])].pm_pr_auc.max() - 0.05:
                reasons.append(f"{cfg} base_position (position-matched): PR-AUC {r.pm_pr_auc:.3f} close to models")
    stop = {"stop": bool(reasons), "reasons": reasons}
    (root / "stop_check.json").write_text(json.dumps(stop, indent=2))
    S = ["# M01 demo_v0 — FallAllD motion tables (PRELIMINARY) — auto-generated by scripts/m01_demo_eval.py\n",
         "Window metrics: test subjects' train_candidate windows, pooled out-of-fold. Threshold: per outer fold, "
         "recall ≥ 0.90 on inner-validation fall windows (training subjects only). pm_* = position-matched subset "
         "(windows starting at 9 s). Clip level: any window ≥ threshold.\n"]
    S.append(f"## STOP check: {'**STOP**' if stop['stop'] else 'pass'}\n\n" + ("\n".join(f"- {x}" for x in reasons) or "- no trigger") + "\n")
    S.append("## 1. Window level (pooled out-of-fold)\n")
    S.append(md(s[["config", "model", "pr_auc", "roc_auc", "base_rate", "precision", "recall", "f1", "adl_window_fp_rate",
                   "pm_pr_auc", "pm_base_rate", "threshold_median", "threshold_min", "threshold_max"]].round(4)) + "\n")
    S.append("## 2. Clip level (c), probes, label-uncertain clips; dedup check (one clip per overlap group)\n")
    S.append(md(s[["config", "model", "clip_fall_detect_pct", "clip_false_alarm_pct", "probe_clip_trigger_pct",
                   "probe_window_trigger_pct", "label_uncertain_detect_pct", "dedup_clip_fall_detect_pct",
                   "dedup_clip_false_alarm_pct", "dedup_probe_clip_trigger_pct", "n_fall_clips", "n_adl_clips",
                   "n_probe_clips", "n_label_uncertain_clips"]].round(2)) + "\n")
    S.append("## 3. Per subject, mean ± std (PR-AUC, fall recall and clip detection over subjects with falls; "
             "false-positive rates over all subjects)\n")
    S.append(md(s[["config", "model", "subj_pr_auc", "subj_fall_window_recall", "subj_adl_window_fp_rate",
                   "subj_clip_fall_detect_pct", "subj_clip_false_alarm_pct"]]) + "\n")
    S.append("## 4. Per subject (models only)\n")
    S.append(md(ps[ps.model.isin(["lr", "rf"])][["config", "model", "subject_id", "has_falls", "pr_auc", "fall_window_recall",
                                                  "adl_window_fp_rate", "clip_fall_detect_pct", "clip_false_alarm_pct",
                                                  "probe_window_trigger_pct", "threshold"]].round(3)) + "\n")
    out_md.write_text("\n".join(S))
    print(json.dumps(stop, indent=2))
    print(s[["config", "model", "pr_auc", "roc_auc", "recall", "precision", "clip_fall_detect_pct",
             "clip_false_alarm_pct", "pm_pr_auc"]].round(3).to_string())


if __name__ == "__main__":
    main()
