"""M03-lite (demo_v0, PRELIMINARY): "still but heart racing" check-in (config/m03_still_racing.yaml).
Writes results/2026-10-12_M03_still_racing_demo_v0/ and reports/M03_tables.md. Refuses to overwrite.
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import features as F  # noqa: E402
from d02_smoke_report import md  # noqa: E402

OUT, MDF = REPO / "results/2026-10-12_M03_still_racing_demo_v0", REPO / "reports/M03_tables.md"
GATE = 0.5671
COLS = ["hr_mean", "hr_std", "hr_min", "hr_max", "hr_delta", "hr_slope", "hr_rel_baseline", "bvp_peak_rate", "ibi_mean",
        "ibi_std", "ppg_sqi", "acc_mag_std"]
COND = {0: "transient", 1: "baseline", 2: "stress", 3: "amusement", 4: "meditation", 5: "ignore", 6: "ignore", 7: "ignore"}
FC = yaml.safe_load(open(REPO / "config/features_v1.yaml"))


def lr():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=5000))


def rf():
    return make_pipeline(SimpleImputer(strategy="median"), RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                         class_weight="balanced_subsample", random_state=0, n_jobs=4))


def thr_recall(pos, target=0.80):
    s = np.sort(np.asarray(pos))[::-1]
    return float(s[int(np.ceil(target * len(s))) - 1])


def windows_features(sid, acc, bvp, lab4, dur):
    rows = []
    for k in range(int((dur - 30) // 15) + 1):
        s0 = 15 * k
        f = F.physiology_features(bvp[s0 * 64:(s0 + 30) * 64], 64, FC)
        mag = np.sqrt((acc[s0 * 32:(s0 + 30) * 32] ** 2).sum(1))
        row = {"subject_id": sid, "window_start": float(s0), "window_end": float(s0 + 30), **f, "acc_mag_std": float(mag.std())}
        if lab4 is not None:
            seg = lab4[s0 * 4:(s0 + 30) * 4]
            v, c = np.unique(seg, return_counts=True)
            row["label"] = COND[int(v[c.argmax()])]
            row["purity"] = float(c.max() / len(seg))
        rows.append(row)
    d = pd.DataFrame(rows)
    d["hr_rel_baseline"] = F.rel_baseline(d.window_start.to_numpy(), d.window_end.to_numpy(), d.hr_mean.to_numpy(),
                                          d.physiology_uncertain.astype(bool).to_numpy(), FC["physiology"]["baseline_s"])
    d["gated"] = (~d.physiology_uncertain.astype(bool)) & (d.acc_mag_std <= GATE)
    return d


def checkins(d, score_col, thr, pause=300.0):
    d = d.sort_values("window_start").reset_index(drop=True)
    hit = (d.gated & (d[score_col] >= thr)).to_numpy()
    fire, last = np.zeros(len(d), bool), -np.inf
    for i in range(1, len(d)):
        if hit[i] and hit[i - 1] and d.window_start[i] - d.window_start[i - 1] == 15 and d.window_end[i] - last >= pause:
            fire[i], last = True, d.window_end[i]
    return fire


def main():
    if OUT.exists() or MDF.exists():
        raise FileExistsError(OUT)
    t0 = time.time()
    W, ver = [], []
    for n in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17]:
        with open(REPO / f"data/raw/wesad/WESAD/S{n}/S{n}.pkl", "rb") as f:
            o = pickle.load(f, encoding="latin1")
        acc = np.asarray(o["signal"]["wrist"]["ACC"], float) / 64 * 9.80665
        bvp = np.asarray(o["signal"]["wrist"]["BVP"], float).reshape(-1)
        lab = np.asarray(o["label"]).reshape(-1)
        d_acc, d_bvp, d_lab = len(acc) / 32, len(bvp) / 64, len(lab) / 700
        ver.append({"subject": f"WESAD_S{n:02d}", "dur_acc_s": d_acc, "dur_bvp_s": d_bvp, "dur_label_s": d_lab,
                    "aligned": bool(abs(d_acc - d_bvp) < 1e-9 and abs(d_acc - d_lab) < 1e-9)})
        if not ver[-1]["aligned"]:
            raise RuntimeError(f"S{n}: durations differ {ver[-1]}")
        W.append(windows_features(f"WESAD_S{n:02d}", acc, bvp, lab[::175], d_acc))
        del o
        print(n, f"{time.time() - t0:.0f}s", flush=True)
    W = pd.concat(W, ignore_index=True)
    OUT.mkdir(parents=True)
    W.to_parquet(OUT / "wesad_windows.parquet", index=False)
    tr = W.gated & (W.purity == 1.0) & W.label.isin(["baseline", "stress"])
    y = (W.label == "stress").astype(int)
    subs = sorted(W.subject_id.unique())
    res, thr_rows = {}, {}
    for name, make in (("lr", lr), ("rf", rf)):
        score = np.full(len(W), np.nan)
        thrs = []
        for s in subs:
            train = [x for x in subs if x != s]
            pos = []
            for v in train:
                m = tr & W.subject_id.isin([x for x in train if x != v])
                mdl = make().fit(W.loc[m, COLS], y[m])
                mv = tr & (W.subject_id == v) & (y == 1)
                if mv.any():
                    pos.append(mdl.predict_proba(W.loc[mv, COLS])[:, 1])
            t = thr_recall(np.concatenate(pos))
            mdl = make().fit(W.loc[tr & W.subject_id.isin(train), COLS], y[tr & W.subject_id.isin(train)])
            te = W.subject_id == s
            score[te.to_numpy()] = mdl.predict_proba(W.loc[te, COLS])[:, 1]
            thrs.append({"test": s, "threshold": t})
        W[f"score_{name}"] = score
        W[f"thr_{name}"] = W.subject_id.map({r["test"]: r["threshold"] for r in thrs})
        thr_rows[name] = thrs
        print(name, "done", f"{time.time() - t0:.0f}s", flush=True)
    # metrics
    S = ["# M03-lite tables (demo_v0, PRELIMINARY) — auto-generated by scripts/m03_still_racing.py\n",
         "## 0. WESAD alignment (durations equal for ACC/32, BVP/64, label/700)\n", md(pd.DataFrame(ver).round(3)) + "\n",
         "## 1. Gate pass rate per condition (WESAD, all windows with purity 1.0)\n",
         md(W[W.purity == 1.0].groupby("label").gated.agg(windows="size", gated_pct=lambda s: 100 * s.mean()).round(1).reset_index()) + "\n"]
    summ = []
    for name in ("lr", "rf"):
        e = W[tr]
        sc, th = e[f"score_{name}"], e[f"thr_{name}"]
        pred = sc >= th
        per = []
        for s, g in e.groupby("subject_id"):
            yy = (g.label == "stress").astype(int)
            per.append({"subject_id": s, "pr_auc": average_precision_score(yy, g[f"score_{name}"]) if 0 < yy.sum() < len(yy) else np.nan,
                        "stress_recall": float((g[f"score_{name}"] >= g[f"thr_{name}"])[yy == 1].mean()) if yy.sum() else np.nan,
                        "baseline_flag_rate": float((g[f"score_{name}"] >= g[f"thr_{name}"])[yy == 0].mean()) if (yy == 0).any() else np.nan})
        per = pd.DataFrame(per)
        probes = {}
        for p in ("amusement", "meditation"):
            g = W[W.gated & (W.purity == 1.0) & (W.label == p)]
            probes[f"{p}_window_flag_pct"] = 100 * float((g[f"score_{name}"] >= g[f"thr_{name}"]).mean()) if len(g) else np.nan
        fire_subj = {}
        for s, g in W.groupby("subject_id"):
            g = g.sort_values("window_start").reset_index(drop=True)
            f = checkins(g, f"score_{name}", g[f"thr_{name}"].iloc[0])
            fire_subj[s] = {c: int(f[(g.label == c).to_numpy()].sum()) for c in ("baseline", "stress", "amusement", "meditation")}
        fs = pd.DataFrame(fire_subj).T
        summ.append({"model": name, "pr_auc": average_precision_score(y[tr], sc), "roc_auc": roc_auc_score(y[tr], sc),
                     "precision": float((pred & (e.label == "stress")).sum() / max(1, pred.sum())),
                     "recall_stress_windows": float(pred[e.label == "stress"].mean()),
                     "baseline_windows_flagged_pct": 100 * float(pred[e.label == "baseline"].mean()), **probes,
                     "subjects_with_stress_checkin_pct": 100 * float((fs.stress > 0).mean()),
                     "subjects_with_baseline_checkin_pct": 100 * float((fs.baseline > 0).mean()),
                     "subjects_with_amusement_checkin_pct": 100 * float((fs.amusement > 0).mean()),
                     "subjects_with_meditation_checkin_pct": 100 * float((fs.meditation > 0).mean()),
                     "subj_pr_auc": f"{per.pr_auc.mean():.3f} ± {per.pr_auc.std(ddof=0):.3f}",
                     "subj_stress_recall": f"{per.stress_recall.mean():.3f} ± {per.stress_recall.std(ddof=0):.3f}",
                     "threshold_median": float(np.median([r["threshold"] for r in thr_rows[name]]))})
        S.append(f"**{name} per subject**\n\n" + md(per.round(3)) + "\n\n**{name} check-ins per subject and condition (WESAD)**\n\n" + md(fs.reset_index()) + "\n")
    SU = pd.DataFrame(summ)
    S.insert(4, "## 2. WESAD leave-one-subject-out (gated, purity 1.0 baseline vs stress)\n\n" + md(SU.round(3).astype(str)) + "\n")
    # deploy on PPG-DaLiA
    ph = pd.read_parquet(REPO / "data/processed/physiology/ppg_dalia_features_v1.parquet")
    pw = pd.read_parquet(REPO / "data/interim/ppg_dalia/windows_v1/physiology_30s.parquet")
    std = []
    for sid, g in pw.groupby("subject_id", sort=False):
        acc = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/wrist_acc.parquet", columns=["x", "y", "z"]).to_numpy()
        mag = np.sqrt((acc ** 2).sum(1))
        std += [(w, float(mag[a:b].std())) for w, a, b in zip(g.window_id, g.acc_i0, g.acc_i1)]
    ph = ph.merge(pd.DataFrame(std, columns=["window_id", "acc_mag_std"]), on="window_id")
    ph["gated"] = (~ph.physiology_uncertain.astype(bool)) & (ph.acc_mag_std <= GATE)
    hours = {}
    for sid in ph.subject_id.unique():
        a = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/activity.parquet", columns=["original_label"])
        hours[sid] = a.original_label.value_counts() / 4 / 3600
    H = pd.DataFrame(hours).fillna(0)
    ev_rows = []
    for name, make in (("lr", lr), ("rf", rf)):
        T = float(np.median([r["threshold"] for r in thr_rows[name]]))
        mdl = make().fit(W.loc[tr, COLS], y[tr])
        ph[f"score_{name}"] = mdl.predict_proba(ph[COLS])[:, 1]
        fires = []
        for sid, g in ph.groupby("subject_id"):
            g = g.sort_values("window_start").reset_index(drop=True)
            f = checkins(g, f"score_{name}", T)
            fires.append(g.loc[f, ["subject_id", "original_label"]])
        fz = pd.concat(fires)
        per = fz.groupby("subject_id").size().reindex(H.columns, fill_value=0) / H.sum(axis=0)
        act = fz.groupby("original_label").size().reindex(H.index, fill_value=0) / H.sum(axis=1)
        ev_rows.append({"model": name, "deploy_threshold": T, "checkins": len(fz), "hours": float(H.values.sum()),
                        "checkins_per_hour": len(fz) / float(H.values.sum()),
                        "per_subject": f"{per.mean():.2f} ± {per.std(ddof=0):.2f}", "gated_windows_pct": 100 * float(ph.gated.mean())})
        S.append(f"**{name} everyday check-ins per hour by activity (PPG-DaLiA)**\n\n" + md(pd.DataFrame({"activity": act.index, "hours": H.sum(axis=1).round(2).values,
                 "checkins_per_hour": act.round(3).values})) + "\n\nGated windows per activity (%):\n\n" +
                 md(ph.groupby("original_label").gated.mean().mul(100).round(1).reset_index()) + "\n")
    EVD = pd.DataFrame(ev_rows)
    S.insert(5, "## 3. Everyday life (PPG-DaLiA, never seen by this model)\n\n" + md(EVD.round(3).astype(str)) + "\n")
    # device check
    a = W[W.gated & (W.purity == 1.0) & (W.label == "baseline")][["subject_id"] + COLS].assign(dev=1)
    b = ph[ph.gated & (ph.original_label == "sitting") & (ph.eval_role == "train_candidate")][["subject_id"] + COLS].assign(dev=0)
    dd = pd.concat([a, b], ignore_index=True)
    aucs = {}
    for name, make in (("lr", lr), ("rf", rf)):
        sc = np.full(len(dd), np.nan)
        for trn, te in GroupKFold(5).split(dd, dd.dev, dd.subject_id):
            sc[te] = make().fit(dd.loc[trn, COLS], dd.dev[trn]).predict_proba(dd.loc[te, COLS])[:, 1]
        aucs[name] = roc_auc_score(dd.dev, sc)
    S.insert(6, f"## 4. Device check (WESAD baseline vs PPG-DaLiA sitting, gated windows: {len(a)} vs {len(b)})\n\nAUC LR {aucs['lr']:.3f}, RF {aucs['rf']:.3f}\n")
    SU.to_csv(OUT / "wesad_summary.csv", index=False)
    EVD.to_csv(OUT / "everyday_summary.csv", index=False)
    json.dump({"device_auc": aucs, "thresholds": thr_rows}, open(OUT / "extra.json", "w"), indent=2)
    MDF.write_text("\n".join(S))
    print(SU[["model", "pr_auc", "roc_auc", "precision", "recall_stress_windows", "amusement_window_flag_pct", "meditation_window_flag_pct",
              "subjects_with_stress_checkin_pct"]].round(3).to_string())
    print(EVD.round(3).to_string()); print("device", aucs)


if __name__ == "__main__":
    main()
