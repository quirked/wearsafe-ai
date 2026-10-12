"""F01-demo (demo_v0, PRELIMINARY): rule-based fusion v0 (config/fusion_v0.yaml) and false prompts per user-hour on
PPG-DaLiA (all 15 subjects; the motion model never saw PPG-DaLiA; context = M01 out-of-fold predictions), plus
FallAllD held-out clip-level detection for both variants. Also trains the deploy context RF (all PPG-DaLiA) for the app.

Writes results/<date>_F01_demo_v0/ and reports/F01_demo_v0_tables.md. Refuses to overwrite.
Usage (repo root):  OMP_NUM_THREADS=8 python scripts/f01_demo.py --n-jobs 8
"""
import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import features as F  # noqa: E402
from wearsafe import fusion  # noqa: E402
from d02_smoke_report import md  # noqa: E402

M01 = REPO / "results/2026-10-12_M01_demo_v0_run2"
MOTION_BUNDLE = M01 / "motion/e4_clipped_v2/models/rf_deploy.joblib"
FS = 32


def ppg_motion_scores(sid, wins, bundle):
    """Same feature code as FallAllD (motion_features + saturation_features_v2) on PPG-DaLiA 2 s windows."""
    la = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/wrist_acc.parquet",
                         columns=["x", "y", "z"])
    acc = la.to_numpy()
    sat = fusion.e4_sat_axes(acc)
    mag = np.sqrt((acc ** 2).sum(axis=1))
    rows = []
    for r in wins.itertuples():
        a, s = acc[r.acc_i0:r.acc_i1], sat[r.acc_i0:r.acc_i1]
        f = {**F.motion_features(a, FS, s.any(axis=1)), **F.saturation_features_v2(a, FS, s)}
        e = r.acc_i1
        still = float(mag[e:e + 5 * FS].std()) if e + 5 * FS <= len(mag) else np.nan
        rows.append({**f, "std_next5": still})
    X = pd.DataFrame(rows)
    p = bundle["model"].predict_proba(X[bundle["features"]])[:, 1]
    return p, X.std_next5.to_numpy(), mag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=8)
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    args = ap.parse_args()
    out = REPO / f"results/{args.date}_F01_demo_v0"
    out_md = REPO / "reports/F01_demo_v0_tables.md"
    for p in (out, out_md):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite")
    (out / "models").mkdir(parents=True)
    cfg = fusion.load_config(REPO)
    bundle = joblib.load(MOTION_BUNDLE)
    thr = bundle["threshold"]
    mw = pd.read_parquet(REPO / "data/interim/ppg_dalia/windows_v1/motion_2s.parquet")
    phys = pd.read_parquet(REPO / "data/processed/physiology/ppg_dalia_features_v1.parquet")
    ctx = pd.read_parquet(M01 / "context/oof_context_rf.parquet")
    pw_all = pd.read_parquet(REPO / "data/interim/ppg_dalia/windows_v1/physiology_30s.parquet")
    t0 = time.time()

    # 30 s motion intensity (acc_mag_std over the physiology window, same code) for the gate
    decisions, phys_rows = [], []
    subjects = sorted(mw.subject_id.unique())
    mags = {}
    for sid in subjects:
        w = mw[mw.subject_id == sid].reset_index(drop=True)
        p, std5, mag = ppg_motion_scores(sid, w, bundle)
        mags[sid] = mag
        ph = phys[phys.subject_id == sid].reset_index(drop=True)
        pw = pw_all[pw_all.subject_id == sid].reset_index(drop=True)
        assert (ph.window_id.to_numpy() == pw.window_id.to_numpy()).all()
        ph["acc_mag_std_30s"] = [float(mag[a:b].std()) for a, b in zip(pw.acc_i0, pw.acc_i1)]
        phys_rows.append(ph)
        decisions.append(pd.DataFrame({"subject_id": sid, "t": w.window_end.to_numpy(), "window_id": w.window_id,
                                       "activity": w.original_label, "eval_role": w.eval_role, "p_motion": p,
                                       "std_next5": std5}))
        print(f"{sid}: {len(w)} decisions, {time.time() - t0:.0f}s", flush=True)
    dec = pd.concat(decisions, ignore_index=True)
    ph = pd.concat(phys_rows, ignore_index=True)

    # gate thresholds: sitting 30 s windows (train_candidate) of TRAINING subjects only (LOSO); deploy = all 15
    sit = ph[(ph.original_label == "sitting") & (ph.eval_role == "train_candidate")]
    gate = {s: float(np.percentile(sit[sit.subject_id != s].acc_mag_std_30s, 95)) for s in subjects}
    gate_all = float(np.percentile(sit.acc_mag_std_30s, 95))

    # fuse per subject
    fused = []
    for sid in subjects:
        d = dec[dec.subject_id == sid].sort_values("t").reset_index(drop=True)
        p_ = ph[ph.subject_id == sid].sort_values("window_end")
        status = fusion.physiology_status(p_.ppg_sqi.to_numpy(), p_.acc_mag_std_30s.to_numpy(),
                                          p_.hr_rel_baseline.to_numpy(), gate[sid], cfg)
        d["phys_status"] = fusion.latest_before(p_.window_end.to_numpy(), status, d.t.to_numpy(), default="unknown")
        c_ = ctx[ctx.subject_id == sid].sort_values("window_end")
        d["context"] = fusion.latest_before(c_.window_end.to_numpy(), c_.pred_context.to_numpy(), d.t.to_numpy(),
                                            default="unknown")
        d["alarm"] = d.p_motion >= thr
        d["still_ok"] = d.std_next5 <= gate[sid]
        for v in ("base", "stillness"):
            cand = d.alarm if v == "base" else (d.alarm & d.still_ok.fillna(False))
            d[f"prompt_{v}"] = fusion.prompts(d.t.to_numpy(), cand.to_numpy(), cfg["alert_state"]["refractory_s"])
            d[f"risk_{v}"] = np.where(~d[f"prompt_{v}"], "NONE", np.where(d.phys_status == "elevated", "HIGH", "CHECK"))
        d["gate_threshold"] = gate[sid]
        fused.append(d)
    fz = pd.concat(fused, ignore_index=True)
    fz.to_parquet(out / "ppg_dalia_decisions.parquet", index=False)

    # rates
    act = []
    for sid in subjects:
        a = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/activity.parquet",
                            columns=["original_label"])
        act.append(a.original_label.value_counts().div(4 * 3600).rename(sid))
    hours_act = pd.concat(act, axis=1).fillna(0)
    hours_subj = hours_act.sum(axis=0)
    rows, subj_rows, act_rows = [], [], []
    for v in ("base", "stillness"):
        pr = fz[fz[f"prompt_{v}"]]
        per = pd.DataFrame({"hours": hours_subj, "prompts": pr.groupby("subject_id").size().reindex(subjects, fill_value=0),
                            "high": pr[pr[f"risk_{v}"] == "HIGH"].groupby("subject_id").size().reindex(subjects, fill_value=0)})
        per["prompts_per_hour"] = per.prompts / per.hours
        per["high_per_hour"] = per.high / per.hours
        rows.append({"variant": f"V0-{v}", "total_hours": per.hours.sum(), "prompts": int(per.prompts.sum()),
                     "prompts_per_hour_overall": per.prompts.sum() / per.hours.sum(),
                     "prompts_per_hour_subject_mean": per.prompts_per_hour.mean(),
                     "prompts_per_hour_subject_std": per.prompts_per_hour.std(ddof=0),
                     "high_per_hour_overall": per.high.sum() / per.hours.sum(),
                     "alarm_seconds_pct": 100 * fz.alarm.mean(),
                     "phys_status_at_prompts": pr.phys_status.value_counts().to_dict()})
        subj_rows.append(per.reset_index(names="subject_id").assign(variant=f"V0-{v}"))
        ah = hours_act.sum(axis=1)
        pa = pr.groupby("activity").size().reindex(ah.index, fill_value=0)
        act_rows.append(pd.DataFrame({"activity": ah.index, "hours": ah.values, "prompts": pa.values,
                                      "prompts_per_hour": pa.values / ah.values, "variant": f"V0-{v}"}))
    summary = pd.DataFrame(rows)
    per_subject = pd.concat(subj_rows)
    per_activity = pd.concat(act_rows)
    ctx_at = pd.crosstab(fz[fz.prompt_base].activity, fz[fz.prompt_base].context)

    # FallAllD held-out folds: clip-level detection, both variants
    oof = pd.read_parquet(M01 / "motion/e4_clipped_v2/oof_rf.parquet")
    still = []
    sig_root = REPO / "data/interim/fallalld/normalized_signals_v1/e4_clipped"
    for sid, g in oof.groupby("subject_id"):
        la = pd.read_parquet(sig_root / f"{sid}.parquet", columns=["record_id", "x", "y", "z"])
        m = {r: np.sqrt((x[["x", "y", "z"]].to_numpy() ** 2).sum(1)) for r, x in la.groupby("record_id")}
        for r in g.itertuples():
            e = int(round((r.window_start + 2) * FS))
            mg = m[r.record_id]
            still.append(float(mg[e:e + 5 * FS].std()) if e + 5 * FS <= len(mg) else np.nan)
    oof = oof.assign(std_next5=still)
    oof["alarm"] = oof.score >= oof.threshold
    oof["still_ok"] = oof.std_next5 <= gate_all
    clip = oof.groupby("record_id").agg(kind=("kind", "first"), role=("window_role", lambda s: s.iloc[0] if s.nunique() == 1 else "fall"),
                                        rep=("dedup_representative", "first"), base=("alarm", "any"),
                                        stillness=("alarm", lambda s: bool((s & oof.loc[s.index, "still_ok"].fillna(False)).any())))
    fall_rows = []
    for v in ("base", "stillness"):
        for dd, lab in ((clip, "all clips"), (clip[clip.rep], "dedup (one per overlap group)")):
            fall = (dd.kind == "fall") & (dd.role != "label_uncertain_fall")
            probe = dd.role == "hard_negative_probe"
            adl = (dd.kind == "adl") & ~probe
            fall_rows.append({"variant": f"V0-{v}", "set": lab, "fall_clip_detect_pct": 100 * dd[v][fall].mean(),
                              "label_uncertain_detect_pct": 100 * dd[v][dd.role == "label_uncertain_fall"].mean(),
                              "adl_clip_false_alarm_pct": 100 * dd[v][adl].mean(),
                              "probe_clip_trigger_pct": 100 * dd[v][probe].mean(), "n_fall": int(fall.sum()),
                              "n_adl": int(adl.sum())})
    fall_tab = pd.DataFrame(fall_rows)

    # deploy context model for the app (all PPG-DaLiA train_candidate context windows)
    cw = pd.read_parquet(REPO / "data/processed/context/ppg_dalia_features_v1.parquet")
    tc = cw.eval_role == "train_candidate"
    cm = make_pipeline(SimpleImputer(strategy="median"),
                       RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                              random_state=0, n_jobs=args.n_jobs))
    cm.fit(cw.loc[tc, list(F.MOTION_FEATURE_NAMES)], cw.loc[tc, "context_class"])
    joblib.dump({"model": cm, "features": list(F.MOTION_FEATURE_NAMES), "tag": "demo_v0",
                 "note": "PRELIMINARY; RF on all PPG-DaLiA train_candidate 5 s windows"}, out / "models/context_rf_deploy.joblib",
                compress=3)
    json.dump({"gate_threshold_loso": gate, "gate_threshold_all": gate_all, "motion_threshold": thr,
               "motion_bundle": str(MOTION_BUNDLE.relative_to(REPO))}, open(out / "thresholds.json", "w"), indent=2)
    summary.to_csv(out / "summary.csv", index=False)
    per_subject.to_csv(out / "per_subject.csv", index=False)
    per_activity.to_csv(out / "per_activity.csv", index=False)
    fall_tab.to_csv(out / "fallalld_clip_level.csv", index=False)
    dev = json.loads((M01 / "device_check/auc.json").read_text())["auc"]
    S = ["# F01 demo_v0 tables (PRELIMINARY) — auto-generated by scripts/f01_demo.py\n",
         f"Motion model: `{MOTION_BUNDLE.relative_to(REPO)}`, deploy threshold {thr:.4f}. Gate (sitting p95 of 30 s "
         f"acc_mag_std, training subjects only): {min(gate.values()):.4f}–{max(gate.values()):.4f} m/s² (LOSO); all-subject "
         f"value {gate_all:.4f}. Refractory {cfg['alert_state']['refractory_s']} s. Device-discrimination AUC (M01): "
         f"LR {dev['lr']:.3f}, RF {dev['rf']:.3f}.\n",
         "## 1. PPG-DaLiA false prompts per user-hour (all 15 subjects)\n",
         md(summary.round(3).astype(str)) + "\n",
         "## 2. Per subject\n", md(per_subject.round(3)) + "\n",
         "## 3. Per activity (prompts attributed to the alarm window's activity; rate per hour of that activity)\n",
         md(per_activity.round(3)) + "\n",
         "## 4. Context predicted at V0-base prompts (shown, never suppresses)\n", md(ctx_at.reset_index()) + "\n",
         "## 5. FallAllD held-out folds, clip level (M01 out-of-fold scores, fold thresholds)\n", md(fall_tab.round(2)) + "\n"]
    out_md.write_text("\n".join(S))
    print(summary.round(3).to_string())
    print(fall_tab.round(2).to_string())


if __name__ == "__main__":
    main()
