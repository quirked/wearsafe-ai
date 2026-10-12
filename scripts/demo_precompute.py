"""Demo app precompute (demo_v0/demo_v1, PRELIMINARY): run the REAL streaming engine (src/wearsafe/inference.py) and
the v1 rules (src/wearsafe/fusion_v1.py) over the demo recordings and save the per-second timelines the app replays.
No detection logic lives in the app; no model, threshold, rule or setting is changed here.

Recordings (people the models never saw):
  Everyday life : PPGDALIA_S03 (F02 test partition). Movement model = FallAllD deploy (never saw PPG-DaLiA); context =
                  the M01 context fold model that left S03 out; heart gate = F01 leave-S03-out value. Five 4-minute
                  segments (sitting, driving, walking, cycling, table soccer), each preceded by a 330 s warm-up of the
                  same recording (heart baseline needs 5 min of history).
  Fall event    : FALLALLD_S01 (F02 test partition), movement = M01 fold model that left S01 out (its fold threshold);
                  clips: the subject's first fall clip and an everyday jogging clip. No heart sensor in this dataset.
Writes results/<date>_demo_app_v0/timelines.joblib (refuses to overwrite).
Usage (repo root):  OMP_NUM_THREADS=8 python scripts/demo_precompute.py
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fusion  # noqa: E402
from wearsafe import fusion_v1 as fv1  # noqa: E402
from wearsafe.inference import EngineConfig, StreamingEngine  # noqa: E402

M01 = REPO / "results/2026-10-12_M01_demo_v0_run2"
F01 = REPO / "results/2026-10-12_F01_demo_v0"
F02 = REPO / "results/2026-10-12_F02_demo_v1"
FS, FS_BVP = 32, 64
SETTINGS = {"most_sensitive": "V0-base", "balanced": "V1-tiered", "fewer_interruptions": "V1-change", "quietest": "V0-stillness"}


def single_thread(bundle):
    """Prediction-time only: run the forest with one thread (no change to the fitted model)."""
    if bundle is not None:
        bundle["model"].steps[-1][1].n_jobs = 1
    return bundle


def run(acc, bvp, motion, context, gate, feat_cfg, sel, refractory):
    eng = StreamingEngine(motion, context, EngineConfig(motion_threshold=motion["threshold"], gate_threshold=gate,
                                                        features_cfg=feat_cfg))
    out = []
    n = len(acc) // FS
    for k in range(n):
        out += eng.push(acc[k * FS:(k + 1) * FS], None if bvp is None else bvp[k * FS_BVP:(k + 1) * FS_BVP])
    d = pd.DataFrame(out)
    T = motion["threshold"]
    # v1 settings: the same decide() used offline in F02, on the engine's movement scores
    for name, variant in SETTINGS.items():
        if variant == "V0-base":
            d[f"prompt_{name}"], d[f"lat_{name}"] = d.prompt_base, 0.0
            continue
        if variant == "V0-stillness":
            alarm_t = d.loc[d.prompt_stillness, "stillness_alarm_t"].astype(int).to_numpy()
            d[f"prompt_{name}"] = d.t.isin(alarm_t)
            d[f"lat_{name}"] = 5.0
            continue
        prm = sel["chosen"][variant]["params"]
        change = np.zeros(len(d), bool)
        for i, (t, p) in enumerate(zip(d.t, d.p_motion)):
            if p >= T:
                change[i] = fv1.is_change(fv1.change_measures(acc[: min(len(acc), (int(t) + 5) * FS)], int(t) * FS, FS), prm["tol"])
        pr, lat = fv1.decide(variant, d.t.to_numpy(), d.p_motion.fillna(0).to_numpy(), np.full(len(d), T),
                             prm.get("T_high"), change, None, refractory)
        d[f"prompt_{name}"], d[f"lat_{name}"] = pr, lat
    for name in SETTINGS:
        d[f"risk_{name}"] = [fusion.risk_level(bool(pr), str(ps)) for pr, ps in zip(d[f"prompt_{name}"], d.phys_status)]
    hr = pd.DataFrame(eng.phys_hist, columns=["start", "end", "hr_mean", "uncertain"])
    return d, hr


def main():
    out = REPO / "results/2026-10-12_demo_app_v0"
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    sel = json.loads((F02 / "selection.json").read_text())
    refractory = yaml.safe_load(open(REPO / "config/fusion_v1.yaml"))["refractory_s"]
    feat_cfg = yaml.safe_load(open(REPO / "config/features_v1.yaml"))
    thr = json.loads((F01 / "thresholds.json").read_text())
    timelines = {"everyday": {}, "fall": {}, "meta": {}}
    t0 = time.time()

    # ---- Everyday life: PPGDALIA_S03 (test partition) ----
    sid = "PPGDALIA_S03"
    assert sid in part["ppg_dalia"]["test"]
    ppg_split = json.loads((REPO / "splits/ppg_dalia_v1.json").read_text())
    fold = next(f["fold"] for f in ppg_split["folds"] if f["test"] == [sid])
    context = single_thread(joblib.load(M01 / f"context/models/rf_fold{fold:02d}.joblib"))
    motion = single_thread(joblib.load(M01 / "motion/e4_clipped_v2/models/rf_deploy.joblib"))
    sig = REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}"
    acc = pd.read_parquet(sig / "wrist_acc.parquet", columns=["x", "y", "z"]).to_numpy()
    bvp = pd.read_parquet(sig / "wrist_bvp.parquet", columns=["scalar_value"]).scalar_value.to_numpy()
    act = pd.read_parquet(sig / "activity.parquet", columns=["original_label"]).original_label.to_numpy()
    for label in ("sitting", "driving", "walking", "cycling", "table_soccer"):
        idx = np.flatnonzero(act == label)
        onset = idx[0] / 4
        end = (idx[np.flatnonzero(np.diff(idx) > 1)[0]] + 1) / 4 if (np.diff(idx) > 1).any() else (idx[-1] + 1) / 4
        seg0, seg1 = int(onset + 30), int(min(onset + 30 + 240, end))
        w0 = max(0, seg0 - 330)
        d, hr = run(acc[w0 * FS:seg1 * FS], bvp[w0 * FS_BVP:seg1 * FS_BVP], motion, context,
                    thr["gate_threshold_loso"][sid], feat_cfg, sel, refractory)
        d["t_abs"] = d.t + w0
        hr["end_abs"] = hr.end + w0
        mag = np.sqrt((acc[seg0 * FS:seg1 * FS] ** 2).sum(1))
        timelines["everyday"][label] = {
            "decisions": d[d.t_abs > seg0].reset_index(drop=True), "hr": hr[hr.end_abs > seg0 - 120].reset_index(drop=True),
            "mag": mag, "seg": (seg0, seg1), "warmup_start": w0,
            "activity": pd.Series(act[seg0 * 4:seg1 * 4]).iloc[::4].to_numpy()}
        print(f"everyday {label}: {seg1 - seg0} s shown (+{seg0 - w0} s warm-up), {time.time() - t0:.0f}s", flush=True)

    # ---- Fall event: FALLALLD_S01 (test partition), fold model that left S01 out ----
    fsid = "FALLALLD_S01"
    assert fsid in part["fallalld"]["test"]
    fsplit = json.loads((REPO / "splits/fallalld_v1.json").read_text())
    ffold = next(f["fold"] for f in fsplit["folds"] if f["test"] == [fsid])
    fmotion = single_thread(joblib.load(M01 / f"motion/e4_clipped_v2/models/rf_fold{ffold:02d}.joblib"))
    fcontext = single_thread(joblib.load(F01 / "models/context_rf_deploy.joblib"))
    la = pd.read_parquet(REPO / f"data/interim/fallalld/normalized_signals_v1/e4_clipped/{fsid}.parquet")
    lu = pd.read_csv(REPO / "metadata/fallalld_label_uncertain_v1.csv")
    bad = set(lu.loc[lu.status == "label_uncertain_fall", "record_id"])
    falls = sorted(r for r in la[la.kind == "fall"].record_id.unique() if r not in bad)
    jog = sorted(r for r in la[la.activity_id == 24].record_id.unique())
    clips = {"fall": falls[0], "jogging": jog[0]}
    for name, rid in clips.items():
        g = la[la.record_id == rid]
        a = g[["x", "y", "z"]].to_numpy()
        d, _ = run(a, None, fmotion, fcontext, thr["gate_threshold_all"], feat_cfg, sel, refractory)
        d["t_abs"] = d.t
        timelines["fall"][name] = {"decisions": d, "mag": np.sqrt((a ** 2).sum(1)), "record_id": rid,
                                   "label": g.original_label.iat[0]}
        print(f"fall demo {name}: {rid} ({g.original_label.iat[0]}), {time.time() - t0:.0f}s", flush=True)
    timelines["meta"] = {"everyday_subject": sid, "everyday_context_fold": fold, "fall_subject": fsid,
                         "fall_motion_fold": ffold, "fall_motion_threshold": fmotion["threshold"],
                         "everyday_motion_threshold": motion["threshold"], "settings": SETTINGS,
                         "selection": sel["chosen"], "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "note": "PRELIMINARY demo; real recordings, nothing mixed between people or recordings"}
    out.mkdir(parents=True)
    joblib.dump(timelines, out / "timelines.joblib", compress=3)
    print("wrote", out / "timelines.joblib")


if __name__ == "__main__":
    main()
