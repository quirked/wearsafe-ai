"""F02-demo (demo_v1, PRELIMINARY; post-hoc but held-out): fusion v1 candidates (config/fusion_v1.yaml).

--phase measures : change/stillness measures at every alarm second (PPG-DaLiA all subjects; FallAllD all windows with
                   an alarm) — no metric is computed.
--phase dev      : grid on the DEV partition only; selection rule; writes selection.json (choices) + dev tables.
--phase test     : evaluates EVERY variant with the dev-selected parameters on the TEST partition only.
Writes results/<date>_F02_demo_v1/ and reports/F02_demo_v1_{dev,test}_tables.md. Refuses to overwrite.
"""
import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fusion_v1 as fv1  # noqa: E402
from d02_smoke_report import md  # noqa: E402

FS = 32
M01 = REPO / "results/2026-10-12_M01_demo_v0_run2/motion/e4_clipped_v2/oof_rf.parquet"
F01 = REPO / "results/2026-10-12_F01_demo_v0"
VARIANTS = ["V0-base", "V0-stillness", "V1-merge", "V1-tiered", "V1-change", "V1-combined"]


def out_dir(date):
    return REPO / f"results/{date}_F02_demo_v1"


def phase_measures(out):
    thr = json.loads((F01 / "thresholds.json").read_text())
    T_ppg = thr["motion_threshold"]
    dec = pd.read_parquet(F01 / "ppg_dalia_decisions.parquet")
    rows = []
    for sid, d in dec.groupby("subject_id"):
        acc = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/wrist_acc.parquet",
                              columns=["x", "y", "z"]).to_numpy()
        for r in d[d.p_motion >= T_ppg].itertuples():
            rows.append({"subject_id": sid, "t": r.t, **fv1.change_measures(acc, int(round(r.t * FS)), FS)})
    pd.DataFrame(rows).to_parquet(out / "measures_ppg_dalia.parquet", index=False)
    oof = pd.read_parquet(M01)
    oof["t"] = oof.window_start + 2
    rows = []
    sig = REPO / "data/interim/fallalld/normalized_signals_v1/e4_clipped"
    gate_all = thr["gate_threshold_all"]
    for sid, g in oof.groupby("subject_id"):
        la = pd.read_parquet(sig / f"{sid}.parquet", columns=["record_id", "x", "y", "z"])
        accs = {r: x[["x", "y", "z"]].to_numpy() for r, x in la.groupby("record_id")}
        for r in g[g.score >= g.threshold].itertuples():
            a = accs[r.record_id]
            e = int(round(r.t * FS))
            m = fv1.change_measures(a, e, FS)
            mag = np.sqrt((a[e:e + 5 * FS] ** 2).sum(1))
            still = bool(e + 5 * FS <= len(a) and mag.std() <= gate_all)
            rows.append({"window_id": r.window_id, **m, "still_ok": still})
    pd.DataFrame(rows).to_parquet(out / "measures_fallalld.parquet", index=False)
    print("measures written", flush=True)


def load(out):
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    thr = json.loads((F01 / "thresholds.json").read_text())
    dec = pd.read_parquet(F01 / "ppg_dalia_decisions.parquet")
    mp = pd.read_parquet(out / "measures_ppg_dalia.parquet")
    dec = dec.merge(mp, on=["subject_id", "t"], how="left")
    dec["T"] = thr["motion_threshold"]
    oof = pd.read_parquet(M01)
    oof["t"] = oof.window_start + 2
    oof = oof.merge(pd.read_parquet(out / "measures_fallalld.parquet"), on="window_id", how="left")
    oof["still_ok"] = oof.still_ok.fillna(False).astype(bool)
    hours = {}
    for sid in dec.subject_id.unique():
        a = pd.read_parquet(REPO / f"data/interim/ppg_dalia/normalized_signals_v1/{sid}/activity.parquet",
                            columns=["original_label"])
        hours[sid] = a.original_label.value_counts().div(4 * 3600)
    return part, thr, dec, oof, pd.DataFrame(hours).fillna(0)


def change_col(df, tol):
    return np.array([fv1.is_change(r, tol) if isinstance(r.get("pre_ok"), (bool, np.bool_)) else False
                     for r in df[["pre_ok", "post_ok", "std_pre", "std_post", "f_pre", "f_post"]].to_dict("records")])


def run_variant(variant, dec, oof, params, cfg):
    """Prompt flags + latency for PPG-DaLiA (per subject sequence) and FallAllD (per clip)."""
    T_high, tol = params.get("T_high"), params.get("tol")
    pp, pl = np.zeros(len(dec), bool), np.zeros(len(dec))
    ch_p = change_col(dec, tol) if tol is not None else None
    for sid, idx in dec.groupby("subject_id").indices.items():
        d = dec.iloc[idx]
        pr, lat = fv1.decide(variant, d.t.to_numpy(), d.p_motion.to_numpy(), d["T"].to_numpy(), T_high,
                             None if ch_p is None else ch_p[idx], d.still_ok.fillna(False).to_numpy(), cfg["refractory_s"])
        pp[idx], pl[idx] = pr, lat
    fp, fl = np.zeros(len(oof), bool), np.zeros(len(oof))
    ch_f = change_col(oof, tol) if tol is not None else None
    for rid, idx in oof.groupby("record_id").indices.items():
        d = oof.iloc[idx]
        pr, lat = fv1.decide(variant, d.t.to_numpy(), d.score.to_numpy(), d.threshold.to_numpy(), T_high,
                             None if ch_f is None else ch_f[idx], d.still_ok.to_numpy(), cfg["refractory_s"])
        fp[idx], fl[idx] = pr, lat
    return pp, pl, fp, fl


def metrics(dec, oof, pp, pl, fp, fl, ppg_subjects, fad_subjects, hours):
    d = dec[dec.subject_id.isin(ppg_subjects)]
    m = pp[dec.subject_id.isin(ppg_subjects).to_numpy()]
    hs = hours[ppg_subjects].sum(axis=0)
    per = d[m].groupby("subject_id").size().reindex(ppg_subjects, fill_value=0) / hs
    o = oof[oof.subject_id.isin(fad_subjects)].assign(prompt=fp[oof.subject_id.isin(fad_subjects).to_numpy()],
                                                     lat=fl[oof.subject_id.isin(fad_subjects).to_numpy()])
    c = o.groupby("record_id").agg(kind=("kind", "first"), act=("activity_id", "first"), rep=("dedup_representative", "first"),
                                   role=("window_role", lambda s: s.iloc[0] if s.nunique() == 1 else "fall"),
                                   det=("prompt", "any"))
    first_lat = o[o.prompt].groupby("record_id").lat.first()
    fall = (c.kind == "fall") & (c.role != "label_uncertain_fall")
    adl = (c.kind == "adl") & (c.role != "hard_negative_probe")
    lat_all = np.concatenate([pl[pp & dec.subject_id.isin(ppg_subjects).to_numpy()], first_lat.reindex(c.index[fall & c.det]).dropna().to_numpy()])
    return {"ppg_hours": float(hs.sum()), "ppg_prompts": int(m.sum()), "prompts_per_hour": float(m.sum() / hs.sum()),
            "prompts_per_hour_subj_mean": float(per.mean()), "prompts_per_hour_subj_std": float(per.std(ddof=0)),
            "fall_detect_pct": float(100 * c.det[fall].mean()), "n_fall_clips": int(fall.sum()),
            "adl_clip_prompt_pct": float(100 * c.det[adl].mean()),
            "adl_clip_prompt_pct_dedup": float(100 * c.det[adl & c.rep].mean()),
            "probe_fail_to_stand_up_pct": float(100 * c.det[c.act == 15].mean()) if (c.act == 15).any() else np.nan,
            "probe_stumbling_pct": float(100 * c.det[c.act == 23].mean()) if (c.act == 23).any() else np.nan,
            "label_uncertain_detect_pct": float(100 * c.det[c.role == "label_uncertain_fall"].mean()) if (c.role == "label_uncertain_fall").any() else np.nan,
            "delayed_prompts_pct": float(100 * np.mean(lat_all > 0)) if len(lat_all) else np.nan,
            "median_added_latency_s": float(np.median(lat_all)) if len(lat_all) else np.nan}, per


def grid(variant, T_highs, tols):
    if variant in ("V0-base", "V0-stillness", "V1-merge"):
        return [{}]
    if variant == "V1-change":
        return [{"tol": t} for t in tols]
    return [{"T_high": h, "tol": t} for h, t in itertools.product(T_highs, tols)]


def select(rows):
    ok = [r for r in rows if r["prompts_per_hour"] <= 3.0]
    if ok:
        return sorted(ok, key=lambda r: (-r["fall_detect_pct"], r["prompts_per_hour"]))[0], "met <= 3/h"
    fb = [r for r in rows if r["fall_detect_pct"] >= 80.0]
    if fb:
        return sorted(fb, key=lambda r: r["prompts_per_hour"])[0], "FALLBACK: no setting met <= 3/h; lowest prompts/h with >= 80% falls"
    return sorted(rows, key=lambda r: r["prompts_per_hour"])[0], "FALLBACK2: no setting met <= 3/h or >= 80% falls; lowest prompts/h"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["measures", "dev", "test"])
    ap.add_argument("--date", default="2026-10-12")
    args = ap.parse_args()
    out = out_dir(args.date)
    cfg = yaml.safe_load(open(REPO / "config/fusion_v1.yaml"))
    if args.phase == "measures":
        if out.exists():
            raise FileExistsError(out)
        out.mkdir(parents=True)
        return phase_measures(out)
    part, thr, dec, oof, hours = load(out)
    if args.phase == "dev":
        if (out / "selection.json").exists():
            raise FileExistsError("selection.json exists")
        dev_f, dev_p = part["fallalld"]["dev"], part["ppg_dalia"]["dev"]
        fp_scores = oof[(oof.window_role == "fall_positive") & oof.subject_id.isin(dev_f)].score
        T_highs = [float(np.quantile(fp_scores, q)) for q in (0.70, 0.50, 0.30)]   # 30 / 50 / 70 % exceed
        rows, chosen = [], {}
        for v in VARIANTS:
            vr = []
            for prm in grid(v, T_highs, cfg["change"]["tol_grid"]):
                res = run_variant(v, dec, oof, prm, cfg)
                mt, _ = metrics(dec, oof, *res, dev_p, dev_f, hours)
                vr.append({"variant": v, **prm, **mt})
            rows += vr
            best, how = select(vr)
            chosen[v] = {"params": {k: best[k] for k in ("T_high", "tol") if k in best and not pd.isna(best.get(k))},
                         "dev_fall_detect_pct": best["fall_detect_pct"], "dev_prompts_per_hour": best["prompts_per_hour"],
                         "selection": how}
        cand = [{"variant": v, "fall_detect_pct": c["dev_fall_detect_pct"], "prompts_per_hour": c["dev_prompts_per_hour"]}
                for v, c in chosen.items() if v.startswith("V1")]
        rec, how = select(cand)
        sel = {"T_high_grid": T_highs, "chosen": chosen, "recommended": rec["variant"], "recommended_selection": how,
               "created": time.strftime("%Y-%m-%d %H:%M:%S"), "note": "chosen on DEV only, before any test evaluation"}
        (out / "selection.json").write_text(json.dumps(sel, indent=2))
        t = pd.DataFrame(rows)
        t.to_csv(out / "dev_grid.csv", index=False)
        (REPO / "reports/F02_demo_v1_dev_tables.md").write_text(
            "# F02 demo_v1 — DEV grid (selection only; PRELIMINARY) — auto-generated by scripts/f02_demo.py\n\n"
            f"T_high grid (30/50/70 % of dev fall-positive windows exceed): {[round(x, 4) for x in T_highs]}\n\n"
            + md(t.round(3)) + "\n\n## Choices\n\n" + md(pd.DataFrame([{"variant": v, **c} for v, c in chosen.items()]).astype(str))
            + f"\n\n**Recommended (dev rule): {rec['variant']}** ({how})\n")
        print(json.dumps(sel, indent=2))
        return
    sel = json.loads((out / "selection.json").read_text())
    if (out / "test_summary.csv").exists():
        raise FileExistsError("test results exist")
    test_f, test_p = part["fallalld"]["test"], part["ppg_dalia"]["test"]
    rows, subj, acts = [], [], []
    hs = hours[test_p]
    for v in VARIANTS:
        prm = sel["chosen"][v]["params"]
        pp, pl, fp, fl = run_variant(v, dec, oof, prm, cfg)
        mt, per = metrics(dec, oof, pp, pl, fp, fl, test_p, test_f, hours)
        rows.append({"variant": v, "params": json.dumps(prm), "recommended": v == sel["recommended"], **mt})
        subj.append(per.rename("prompts_per_hour").reset_index().assign(variant=v))
        d = dec[dec.subject_id.isin(test_p) & pp]
        ah = hs.sum(axis=1)
        acts.append(pd.DataFrame({"variant": v, "activity": ah.index, "hours": ah.values,
                                  "prompts_per_hour": d.groupby("activity").size().reindex(ah.index, fill_value=0).values / ah.values}))
    s = pd.DataFrame(rows)
    s.to_csv(out / "test_summary.csv", index=False)
    ps = pd.concat(subj)
    ps.to_csv(out / "test_per_subject.csv", index=False)
    pa = pd.concat(acts)
    pa.to_csv(out / "test_per_activity.csv", index=False)
    (REPO / "reports/F02_demo_v1_test_tables.md").write_text(
        "# F02 demo_v1 — TEST partition results (PRELIMINARY; post-hoc but held-out) — auto-generated by scripts/f02_demo.py\n\n"
        f"Test: PPG-DaLiA {test_p}; FallAllD {test_f}. Parameters chosen on dev only (selection.json). Recommended: "
        f"**{sel['recommended']}**.\n\n## 1. Trade-off table\n\n" + md(s.round(3)) +
        "\n\n## 2. Per activity (prompts per hour of that activity, test subjects)\n\n" +
        md(pa.pivot(index="activity", columns="variant", values="prompts_per_hour").round(2).reset_index()) +
        "\n\n## 3. Per subject (prompts per hour)\n\n" +
        md(ps.pivot(index="subject_id", columns="variant", values="prompts_per_hour").round(2).reset_index()) + "\n")
    print(s.round(3).to_string())


if __name__ == "__main__":
    main()
