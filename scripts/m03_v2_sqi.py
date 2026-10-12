"""M03 v2 (demo_v0, PRELIMINARY): M03-lite re-run with the SQI v2 cut-off in the gate (config/sqi_v2.yaml).
Same features (saved M03 WESAD windows), models, LOSO, inner threshold rule, check-in rule and deploy rule
(functions imported from scripts/m03_still_racing.py). Writes results/2026-10-12_M03_v2_sqi_demo_v0/ + reports/M03_v2_tables.md.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from m03_still_racing import COLS, GATE, checkins, lr, rf, thr_recall  # noqa: E402
from d02_smoke_report import md  # noqa: E402

M03 = REPO / "results/2026-10-12_M03_still_racing_demo_v0"
OUT = REPO / "results/2026-10-12_M03_v2_sqi_demo_v0"


def gate(df, c):
    return (df.ppg_sqi >= c) & df.hr_mean.between(30, 220) & (df.acc_mag_std <= GATE)


def run(W, ph, H, part, c, label):
    W = W.copy()
    if c == 0.9:
        W["gated"] = W["gated_v1"]
    else:
        W["gated"] = gate(W, c)
    tr = W.gated & (W.purity == 1.0) & W.label.isin(["baseline", "stress"])
    y = (W.label == "stress").astype(int)
    subs = sorted(W.subject_id.unique())
    out = {"version": label, "cutoff": c}
    for cond in ("stress", "baseline", "amusement", "meditation"):
        out[f"gate_pass_{cond}_pct"] = 100 * float(W[(W.purity == 1.0) & (W.label == cond)].gated.mean())
    res = {}
    for name, make in (("lr", lr), ("rf", rf)):
        score, thrs = np.full(len(W), np.nan), []
        for s in subs:
            train = [x for x in subs if x != s]
            pos = []
            for v in train:
                m = tr & W.subject_id.isin([x for x in train if x != v])
                mv = tr & (W.subject_id == v) & (y == 1)
                if mv.any():
                    pos.append(make().fit(W.loc[m, COLS], y[m]).predict_proba(W.loc[mv, COLS])[:, 1])
            t = thr_recall(np.concatenate(pos))
            mt = tr & W.subject_id.isin(train)
            te = (W.subject_id == s).to_numpy()
            score[te] = make().fit(W.loc[mt, COLS], y[mt]).predict_proba(W.loc[te, COLS])[:, 1]
            thrs.append(t)
        W["s"], W["t"] = score, W.subject_id.map(dict(zip(subs, thrs)))
        e = W[tr]
        pred = e.s >= e.t
        stress_subj = 0
        for s, g in W.groupby("subject_id"):
            g = g.sort_values("window_start").reset_index(drop=True)
            f = checkins(g, "s", g.t.iloc[0])
            stress_subj += int(f[(g.label == "stress").to_numpy()].any())
        r = {"pr_auc": average_precision_score(y[tr], e.s), "roc_auc": roc_auc_score(y[tr], e.s),
             "stress_caught_pct": 100 * float(pred[e.label == "stress"].mean()),
             "people_with_stress_checkin": stress_subj}
        for p in ("amusement", "meditation"):
            g = W[W.gated & (W.purity == 1.0) & (W.label == p)]
            r[f"{p}_flagged_pct"] = 100 * float((g.s >= g.t).mean()) if len(g) else np.nan
        T = float(np.median(thrs))
        mdl = make().fit(W.loc[tr, COLS], y[tr])
        P = ph.copy()
        P["gated"] = P["gated_v1"] if c == 0.9 else gate(P, c)
        P["s"] = mdl.predict_proba(P[COLS])[:, 1]
        fires = []
        for sid, g in P.groupby("subject_id"):
            g = g.sort_values("window_start").reset_index(drop=True)
            f = checkins(g, "s", T)
            fires.append(g.loc[f, ["subject_id", "original_label"]])
        fz = pd.concat(fires)
        for nm, subjects in (("test", part["ppg_dalia"]["test"]), ("all15", list(H.columns))):
            h = float(H[subjects].values.sum())
            r[f"everyday_checkins_per_hour_{nm}"] = int(fz.subject_id.isin(subjects).sum()) / h
        r["everyday_gate_pass_pct"] = 100 * float(P.gated.mean())
        r["deploy_threshold"] = T
        res[name] = r
        if name == "lr":
            P[["window_id", "subject_id", "window_start", "window_end", "original_label", "gated", "s"]].assign(threshold=T).to_parquet(
                OUT / f"ppg_dalia_lr_scores_{label}.parquet", index=False)
    # device check
    a = W[W.gated & (W.purity == 1.0) & (W.label == "baseline")][["subject_id"] + COLS].assign(dev=1)
    Pg = ph[(ph.gated_v1 if c == 0.9 else gate(ph, c)) & (ph.original_label == "sitting") & (ph.eval_role == "train_candidate")]
    b = Pg[["subject_id"] + COLS].assign(dev=0)
    dd = pd.concat([a, b], ignore_index=True)
    sc = np.full(len(dd), np.nan)
    for trn, te in GroupKFold(5).split(dd, dd.dev, dd.subject_id):
        sc[te] = lr().fit(dd.loc[trn, COLS], dd.dev[trn]).predict_proba(dd.loc[te, COLS])[:, 1]
    out["device_auc_lr"] = roc_auc_score(dd.dev, sc)
    return [{**out, "model": k, **v} for k, v in res.items()]


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    c2 = json.loads((REPO / "results/2026-10-12_SQI_v2_demo_v0/selection.json").read_text())["chosen_cutoff"]
    W = pd.read_parquet(M03 / "wesad_windows.parquet").rename(columns={"gated": "gated_v1"})
    ph = pd.read_parquet(REPO / "data/processed/physiology/ppg_dalia_features_v1.parquet")
    g = pd.read_parquet(REPO / "results/2026-10-12_SQI_v2_demo_v0/gated_windows.parquet")[["window_id", "acc_mag_std"]]
    ph = ph.merge(g, on="window_id")
    ph["gated_v1"] = (~ph.physiology_uncertain.astype(bool)) & (ph.acc_mag_std <= GATE)
    hours = {}
    for sid in ph.subject_id.unique():
        a = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/activity.parquet", columns=["original_label"])
        hours[sid] = a.original_label.value_counts() / 4 / 3600
    H = pd.DataFrame(hours).fillna(0)
    rows = run(W, ph, H, part, 0.9, "v1") + run(W, ph, H, part, c2, "v2")
    T = pd.DataFrame(rows)
    T.to_csv(OUT / "side_by_side.csv", index=False)
    (REPO / "reports/M03_v2_tables.md").write_text(
        "# M03 v2 tables (demo_v0, PRELIMINARY) — auto-generated by scripts/m03_v2_sqi.py\n\n"
        f"v1 = SQI 0.90 (M03); v2 = SQI {c2} (chosen on PPG-DaLiA dev). Everyday per hour: TEST subjects (dev used for the choice) and all 15.\n\n"
        + md(T.round(3).T.reset_index()) + "\n")
    print(T.round(3).T.to_string())


if __name__ == "__main__":
    main()
