"""M02 (EXPERIMENT, PRELIMINARY): FallAllD wrist gyroscope + barometer (config/m02_extra_sensors.yaml).
--phase features : gyro/baro window features -> data/processed/motion/fallalld_extra_sensors_m02.parquet
--phase train    : RF (M01 run_model, identical settings) per configuration, saved one by one
--phase eval     : metrics as M01 + per fall type / activity, STOP check -> reports/M02_tables.md
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import features as F  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402
from m01_demo_motion import lr, rf, run_model  # noqa: E402
from m01_demo_eval import clip_metrics, per_subject, window_metrics  # noqa: E402
from d02_smoke_report import md  # noqa: E402

EXTRA = REPO / "data/processed/motion/fallalld_extra_sensors_m02.parquet"
OUT = REPO / "results/2026-10-12_M02_extra_sensors"
M01 = REPO / "results/2026-10-12_M01_demo_v0_run2/motion"
GYRO_DPS_PER_COUNT = 2000 / 32768
KEEP = ["window_id", "subject_id", "record_id", "activity_id", "kind", "window_start", "window_role", "eval_role",
        "position_matched", "clip_level_class", "overlap_group_id", "dedup_representative"]


def gname(k):
    return f"gyro_mag_{k[8:]}" if k.startswith("acc_mag_") else f"gyro_{k}"


def gyro_cols():
    return [gname(c) for c in F.MOTION_FEATURE_NAMES if c != "acc_saturated_frac"] + ["gyro_rotation_energy"]


def phase_features():
    if EXTRA.exists():
        raise FileExistsError(EXTRA)
    from wearsafe.safe_pickle import load_pickle_restricted
    raw = load_pickle_restricted(fio.guard(REPO / fio.UNZIPPED / "FallAllD.pkl"))
    raw = raw[raw.Device == "Wrist"]
    raw["record_id"] = [fio.record_id(int(s), int(a), int(t)) for s, a, t in zip(raw.SubjectID, raw.ActivityID, raw.TrialNo)]
    win = pd.read_parquet(REPO / "data/interim/fallalld/windows_v1/windows.parquet")
    rows = []
    for r in raw.itertuples():
        g32 = mh.resample_238_to_32(r.Gyr.astype(float) * GYRO_DPS_PER_COUNT)
        p = r.Bar[:, 0]
        for w in win[win.record_id == r.record_id].itertuples():
            gw = g32[w.i0:w.i1]
            f = F.motion_features(gw, 32, np.zeros(len(gw), bool))
            out = {"window_id": w.window_id}
            for k, v in f.items():
                if k != "acc_saturated_frac":
                    out[gname(k)] = v
            out["gyro_rotation_energy"] = float(np.mean((gw ** 2).sum(1)))
            e = int(round(w.window_end * 10))
            seg = p[max(0, e - 40):e]
            out["baro_change"] = float(np.median(seg[-5:]) - np.median(seg[:5])) if len(seg) >= 10 else np.nan
            out["baro_std"] = float(seg.std()) if len(seg) >= 2 else np.nan
            rows.append(out)
    X = pd.DataFrame(rows)
    assert len(X) == len(win) and X.window_id.is_unique
    X.to_parquet(EXTRA, index=False)
    print("extra features", X.shape, flush=True)


def phase_train(n_jobs):
    split = json.loads((REPO / "splits/fallalld_v1.json").read_text())
    X = pd.read_parquet(EXTRA)
    sets = {"gyro": gyro_cols(), "baro": ["baro_change", "baro_std"], "gyro_baro": gyro_cols() + ["baro_change", "baro_std"]}
    jobs = [(v, s) for v in ("e4_clipped", "unclipped") for s in sets] + [("unclipped", "base_gyro_peak"), ("unclipped", "base_baro_change")]
    t0 = time.time()
    for v, s in jobs:
        out = OUT / f"{v}_{s}"
        if out.exists():
            continue
        out.mkdir(parents=True)
        df = pd.read_parquet(REPO / f"data/processed/motion/fallalld_{v}_features-v2_v1.parquet").merge(X, on="window_id")
        if s == "base_gyro_peak":
            name, make, cols = "lr", lr, ["gyro_mag_max"]
        elif s == "base_baro_change":
            name, make, cols = "lr", lr, ["baro_change"]
        else:
            name, make, cols = "rf", (lambda: rf(n_jobs)), list(F.MOTION_FEATURE_NAMES_V2) + sets[s]
        oof, fold_of, thr = run_model(name, make, df, cols, split["folds"], out, save_models=False)
        res = df[KEEP].copy()
        res["score"], res["fold"] = oof, fold_of
        res["threshold"] = res.fold.map({r["fold"]: r["threshold"] for r in thr})
        res.to_parquet(out / f"oof_{name}.parquet", index=False)
        (out / f"thresholds_{name}.json").write_text(json.dumps(thr, indent=2))
        print(f"{v}_{s} done, {time.time() - t0:.0f}s", flush=True)


def phase_eval():
    info = pd.read_parquet(REPO / "data/interim/fallalld/windows_v1/windows.parquet")[["record_id", "original_label"]].drop_duplicates()
    lab = dict(zip(info.record_id, info.original_label))
    runs = {}
    for v in ("unclipped", "e4_clipped"):
        runs[(v, "ACC-only (M01)")] = M01 / f"{v}_v2/oof_rf.parquet"
        for s, nm in (("gyro", "ACC+gyro"), ("baro", "ACC+baro"), ("gyro_baro", "ACC+gyro+baro")):
            runs[(v, nm)] = OUT / f"{v}_{s}/oof_rf.parquet"
    runs[("any", "gyro-peak-only")] = OUT / "unclipped_base_gyro_peak/oof_lr.parquet"
    runs[("any", "baro-change-only")] = OUT / "unclipped_base_baro_change/oof_lr.parquet"
    rows, fall_type, act_rows, missing = [], [], [], []
    for (v, nm), p in runs.items():
        if not p.exists():
            missing.append(f"{v} {nm}")
            continue
        d = pd.read_parquet(p)
        cm, cmd = clip_metrics(d), clip_metrics(d, dedup=True)
        ps = per_subject(d)
        c = d.groupby("record_id").agg(score=("score", "max"), thr=("threshold", "first"), act=("activity_id", "first"),
                                       kind=("kind", "first"), role=("window_role", lambda s: s.iloc[0] if s.nunique() == 1 else "fall"))
        c["det"] = c.score >= c.thr
        rows.append({"accelerometer": v, "sensor_set": nm, **window_metrics(d), **cm,
                     "dedup_clip_false_alarm_pct": cmd["clip_false_alarm_pct"],
                     "probe_fail_to_stand_up_pct": 100 * c.det[c.act == 15].mean(), "probe_stumbling_pct": 100 * c.det[c.act == 23].mean(),
                     "subj_pr_auc": f"{ps.pr_auc.mean():.3f} ± {ps.pr_auc.std(ddof=0):.3f}",
                     "subj_clip_false_alarm": f"{ps.clip_false_alarm_pct.mean():.1f} ± {ps.clip_false_alarm_pct.std(ddof=0):.1f}"})
        for a, g in c[(c.kind == "fall") & (c.role != "label_uncertain_fall")].groupby("act"):
            fall_type.append({"accelerometer": v, "sensor_set": nm, "fall_type": lab[g.index[0]], "clips": len(g), "detected_pct": 100 * g.det.mean()})
        for a, g in c[(c.kind == "adl")].groupby("act"):
            act_rows.append({"accelerometer": v, "sensor_set": nm, "activity": lab[g.index[0]], "clips": len(g), "false_alarm_pct": 100 * g.det.mean()})
    s = pd.DataFrame(rows)
    stop = []
    for v in ("unclipped", "e4_clipped"):
        best = s[(s.accelerometer == v)].pr_auc.max()
        for r in s.itertuples():
            if r.accelerometer == v and r.pr_auc > 0.98:
                stop.append(f"{v} {r.sensor_set}: PR-AUC {r.pr_auc:.3f} > 0.98")
        for r in s[s.accelerometer == "any"].itertuples():
            if r.pr_auc >= best - 0.05:
                stop.append(f"{r.sensor_set} PR-AUC {r.pr_auc:.3f} within 0.05 of best {v} model {best:.3f}")
    OUT.mkdir(parents=True, exist_ok=True)
    s.to_csv(OUT / "summary.csv", index=False)
    FT, AC = pd.DataFrame(fall_type), pd.DataFrame(act_rows)
    S = ["# M02 tables (EXPERIMENT, PRELIMINARY) — auto-generated by scripts/m02_extra_sensors.py\n",
         f"STOP check: {'**STOP**: ' + '; '.join(stop) if stop else 'pass'}. Missing configurations: {missing or 'none'}.\n",
         "## 1. All configurations\n", md(s.round(3)) + "\n",
         "## 2. Fall detection per fall type (clip level)\n",
         md(FT.pivot_table(index="fall_type", columns=["accelerometer", "sensor_set"], values="detected_pct").round(1).reset_index()) + "\n",
         "## 3. Everyday-clip false alarms per activity (clip level)\n",
         md(AC.pivot_table(index="activity", columns=["accelerometer", "sensor_set"], values="false_alarm_pct").round(1).reset_index()) + "\n"]
    (REPO / "reports/M02_tables.md").write_text("\n".join(S))
    print(s[["accelerometer", "sensor_set", "pr_auc", "roc_auc", "recall", "precision", "clip_fall_detect_pct", "clip_false_alarm_pct",
             "dedup_clip_false_alarm_pct"]].round(3).to_string())
    print("STOP:", stop, "missing:", missing)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["features", "train", "eval"])
    ap.add_argument("--n-jobs", type=int, default=4)
    a = ap.parse_args()
    {"features": phase_features, "train": lambda: phase_train(a.n_jobs), "eval": phase_eval}[a.phase]()
