"""M01-demo (demo_v0, PRELIMINARY) — FallAllD wrist motion models, one grid configuration per call.

Config = (version in {unclipped, e4_clipped}) × (feature set in {v1, v2}); models LR and RF, fixed hyperparameters
(PROJECT_LOG M01-demo entry). Outer LOSO from splits/fallalld_v1.json; per outer fold an inner LOSO over the
fold's training subjects with falls sets the threshold (highest score with recall >= 0.90 on inner fall windows),
before any outer-test prediction is used. Trains on eval_role == train_candidate windows only.
Shortcut baselines (LR): position-only, peak-only, saturation-only (e4_clipped only).

Writes results/<date>_M01_demo_v0/motion/<version>_<fs>/: oof_<model>.parquet (every window of every subject scored
by the fold that held that subject out), thresholds_<model>.json, models/<model>_fold<k>.joblib,
models/<model>_deploy.joblib (+ deploy threshold = median of fold thresholds). Refuses to overwrite.
Usage (repo root):  python scripts/m01_demo_motion.py --version e4_clipped --features v2 [--n-jobs 8]
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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import features as F  # noqa: E402
from wearsafe.schemas import FORBIDDEN_FEATURE_COLUMNS  # noqa: E402

SEED = 0
RECALL_TARGET = 0.90


def lr():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(class_weight="balanced", max_iter=5000))


def rf(n_jobs):
    return make_pipeline(SimpleImputer(strategy="median"),
                         RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                                random_state=SEED, n_jobs=n_jobs))


def position_only():
    return make_pipeline(OneHotEncoder(handle_unknown="ignore"),
                         LogisticRegression(class_weight="balanced", max_iter=5000))


def threshold_for_recall(pos_scores, target=RECALL_TARGET):
    """Highest threshold t such that the share of positives with score >= t is >= target."""
    s = np.sort(np.asarray(pos_scores))[::-1]
    k = int(np.ceil(target * len(s)))
    return float(s[k - 1])


def run_model(name, make, df, cols, folds, out_dir, save_models):
    tc = df.eval_role == "train_candidate"
    y = (df.window_role == "fall_positive").astype(int).to_numpy()
    X = df[cols]
    oof = np.full(len(df), np.nan)
    fold_of = np.full(len(df), -1)
    thr_rows = []
    for f in folds:
        train, test = f["train"], f["test"][0]
        inner_pos = []
        for v in f["inner_validation_subjects"]:
            m_tr = tc & df.subject_id.isin([s for s in train if s != v])
            m_v = tc & (df.subject_id == v) & (y == 1)
            mdl = make().fit(X[m_tr], y[m_tr])
            inner_pos.append(mdl.predict_proba(X[m_v])[:, 1])
        thr = threshold_for_recall(np.concatenate(inner_pos))
        m_tr = tc & df.subject_id.isin(train)
        mdl = make().fit(X[m_tr], y[m_tr])                 # outer model; threshold already fixed above
        m_te = (df.subject_id == test).to_numpy()
        oof[m_te] = mdl.predict_proba(X[m_te])[:, 1]
        fold_of[m_te] = f["fold"]
        thr_rows.append({"fold": f["fold"], "test": test, "threshold": thr,
                         "inner_subjects": f["inner_validation_subjects"], "n_inner_pos": int(sum(map(len, inner_pos)))})
        if save_models:
            joblib.dump({"model": mdl, "threshold": thr, "features": cols}, out_dir / "models" / f"{name}_fold{f['fold']:02d}.joblib",
                        compress=3)
    return oof, fold_of, thr_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, choices=["unclipped", "e4_clipped"])
    ap.add_argument("--features", required=True, choices=["v1", "v2"])
    ap.add_argument("--n-jobs", type=int, default=8)
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--run", default="", help="suffix of the results folder, e.g. _run2")
    args = ap.parse_args()
    out = REPO / f"results/{args.date}_M01_demo_v0{args.run}/motion/{args.version}_{args.features}"
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    (out / "models").mkdir(parents=True)
    df = pd.read_parquet(REPO / f"data/processed/motion/fallalld_{args.version}_features-{args.features}_v1.parquet")
    split = json.loads((REPO / "splits/fallalld_v1.json").read_text())
    cols = list(F.MOTION_FEATURE_NAMES if args.features == "v1" else F.MOTION_FEATURE_NAMES_V2)
    assert not set(cols) & set(FORBIDDEN_FEATURE_COLUMNS)
    assert sorted(df.subject_id.unique()) == split["subjects"]
    t0 = time.time()
    models = {"lr": lr, "rf": lambda: rf(args.n_jobs)}
    baselines = {"base_position": (position_only, ["window_start"]), "base_peak": (lr, ["acc_mag_max"])}
    if args.version == "e4_clipped":
        baselines["base_saturation"] = (lr, ["acc_saturated_frac"] + (["sat_longest_run_s", "sat_n_runs"]
                                                                       if args.features == "v2" else []))
    keep = ["window_id", "subject_id", "record_id", "activity_id", "kind", "window_start", "window_role", "eval_role",
            "position_matched", "clip_level_class", "overlap_group_id", "dedup_representative"]
    for name, make in list(models.items()) + [(k, v[0]) for k, v in baselines.items()]:
        c = cols if name in models else baselines[name][1]
        oof, fold_of, thr = run_model(name, make, df, c, split["folds"], out, save_models=name in models)
        res = df[keep].copy()
        res["score"], res["fold"] = oof, fold_of
        res["threshold"] = res.fold.map({r["fold"]: r["threshold"] for r in thr})
        assert res.score.notna().all() and (res.fold >= 0).all()
        res.to_parquet(out / f"oof_{name}.parquet", index=False)
        (out / f"thresholds_{name}.json").write_text(json.dumps(thr, indent=2))
        if name in models:                                   # deploy model on all subjects
            tc = df.eval_role == "train_candidate"
            y = (df.window_role == "fall_positive").astype(int)
            mdl = make().fit(df.loc[tc, c], y[tc])
            joblib.dump({"model": mdl, "threshold": float(np.median([r["threshold"] for r in thr])), "features": c,
                         "version": args.version, "feature_set": args.features, "tag": "demo_v0",
                         "note": "PRELIMINARY; trained on all FallAllD wrist subjects; threshold = median inner-validation threshold"},
                        out / "models" / f"{name}_deploy.joblib", compress=3)
        print(f"{args.version}_{args.features} {name}: done, {time.time() - t0:.0f}s", flush=True)
    (out / "run_info.json").write_text(json.dumps({"version": args.version, "features": args.features, "cols": cols,
                                                   "seed": SEED, "recall_target": RECALL_TARGET,
                                                   "created": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2))


if __name__ == "__main__":
    main()
