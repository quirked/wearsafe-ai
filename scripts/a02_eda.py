"""A02 (ANALYSIS ONLY): wrist EDA after jolts (PPG-DaLiA) and during stress (WESAD). config/a02_eda.yaml.
Writes results/2026-10-12_A02_eda/, reports/A02_tables.md, reports/figures/A02/. Refuses to overwrite.
"""
import json
import pickle
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import neurokit2 as nk  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe.eda import artefact_mask, causal_split, event_eda  # noqa: E402
from d02_smoke_report import md  # noqa: E402

OUT, MD, FIG = REPO / "results/2026-10-12_A02_eda", REPO / "reports/A02_tables.md", REPO / "reports/figures/A02"
A01 = REPO / "results/2026-10-12_A01_post_event_hr"
FS = 4
MIN_AMP = 0.01


def load_eda(path):
    with open(path, "rb") as f:
        o = pickle.load(f, encoding="latin1")
    eda = np.asarray(o["signal"]["wrist"]["EDA"], float).reshape(-1)
    return o, eda


def scrs(phasic, art):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, info = nk.eda_peaks(phasic, sampling_rate=FS, method="neurokit", amplitude_min=0)
    on, amp = np.asarray(info["SCR_Onsets"]), np.asarray(info["SCR_Amplitude"], float)
    ok = np.isfinite(on) & np.isfinite(amp) & (amp >= MIN_AMP)
    on, amp = on[ok].astype(int), amp[ok]
    keep = ~art[np.clip(on, 0, len(art) - 1)]
    return on[keep] / FS, amp[keep]


def verify(name, eda, dur_s):
    return {"dataset": name, "samples": len(eda), "fs_from_length": len(eda) / dur_s, "min_uS": float(eda.min()),
            "p1_uS": float(np.percentile(eda, 1)), "median_uS": float(np.median(eda)), "max_uS": float(eda.max()),
            "nan": int(np.isnan(eda).sum()), "near_zero_lt_0.05_pct": 100 * float((eda < 0.05).mean())}


def main():
    for p in (OUT, MD, FIG):
        if p.exists():
            raise FileExistsError(p)
    part = json.loads((REPO / "config/fusion_v1_partition.json").read_text())
    E, C = pd.read_csv(A01 / "events.csv"), pd.read_csv(A01 / "controls.csv")
    ver, ev_rows, ct_rows, rate_rows = [], [], [], []
    names = {0: "transient", 1: "sitting", 2: "stairs", 3: "table_soccer", 4: "cycling", 5: "driving", 6: "lunch",
             7: "walking", 8: "working"}
    for n in range(1, 16):
        sid = f"PPGDALIA_S{n:02d}"
        o, eda = load_eda(REPO / f"data/raw/ppg_dalia/PPG_FieldStudy/S{n}/S{n}.pkl")
        dur = len(np.asarray(o["signal"]["wrist"]["ACC"])) / 32
        ver.append({"subject": sid, **verify("PPG-DaLiA", eda, dur)})
        act = np.asarray(o["activity"]).reshape(-1).astype(int)
        del o
        art = artefact_mask(eda, FS)
        tonic, phasic = causal_split(eda, FS)
        on, amp = scrs(phasic, art)
        for df, rows in ((E[E.subject_id == sid], ev_rows), (C[C.subject_id == sid], ct_rows)):
            for r in df.itertuples():
                rows.append({"subject_id": sid, "ta": r.ta, "activity": r.activity, "event_tags": getattr(r, "tag_V1_tiered", None),
                             **event_eda(r.ta, FS, tonic, phasic, on, art)})
        lab = np.array([names[c] for c in act[: len(eda)]])
        on_lab = lab[np.clip((on * FS).astype(int), 0, len(lab) - 1)]
        for a in np.unique(lab):
            minutes = ((lab == a) & ~art).sum() / FS / 60
            rate_rows.append({"subject_id": sid, "activity": a, "minutes": minutes, "scrs": int((on_lab == a).sum()),
                              "scr_per_min": (on_lab == a).sum() / minutes if minutes > 0 else np.nan,
                              "artefact_pct": 100 * art[lab == a].mean()})
        print(sid, "done", flush=True)
    w_rows, w_seg = [], []
    for n in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17]:
        sid = f"WESAD_S{n:02d}"
        o, eda = load_eda(REPO / f"data/raw/wesad/WESAD/S{n}/S{n}.pkl")
        lab = np.asarray(o["label"]).reshape(-1)[::175][: len(eda)]
        dur = len(np.asarray(o["signal"]["wrist"]["ACC"])) / 32
        ver.append({"subject": sid, **verify("WESAD", eda, dur)})
        del o
        art = artefact_mask(eda, FS)
        tonic, phasic = causal_split(eda, FS)
        on, amp = scrs(phasic, art)
        on_i = np.clip((on * FS).astype(int), 0, len(lab) - 1)
        for c, cname in {1: "baseline", 2: "stress", 3: "amusement", 4: "meditation"}.items():
            m = (lab == c) & ~art
            minutes = m.sum() / FS / 60
            sel = lab[on_i] == c
            w_rows.append({"subject_id": sid, "condition": cname, "minutes": minutes,
                           "scr_per_min": sel.sum() / minutes if minutes else np.nan,
                           "scr_amp_mean_uS": float(amp[sel].mean()) if sel.any() else np.nan,
                           "tonic_mean_uS": float(tonic[m].mean()) if m.any() else np.nan,
                           "artefact_pct": 100 * float(art[lab == c].mean())})
            idx = np.flatnonzero(lab == c)
            if c in (1, 2) and len(idx):
                for s0 in range(idx[0], idx[-1] - 60 * FS, 60 * FS):
                    seg = np.arange(s0, s0 + 60 * FS)
                    if (lab[seg] == c).all():
                        w_seg.append({"subject_id": sid, "condition": cname, "scrs": int(((on_i >= s0) & (on_i < s0 + 60 * FS)).sum())})
        print(sid, "done", flush=True)
    OUT.mkdir(parents=True)
    FIG.mkdir(parents=True)
    V, EV, CT, R, W, WS = map(pd.DataFrame, (ver, ev_rows, ct_rows, rate_rows, w_rows, w_seg))
    for name, df in (("verify", V), ("events", EV), ("controls", CT), ("scr_rate_activity", R), ("wesad", W), ("wesad_minutes", WS)):
        df.to_csv(OUT / f"{name}.csv", index=False)
    S = ["# A02 tables (ANALYSIS ONLY, PRELIMINARY) — auto-generated by scripts/a02_eda.py\n",
         "## 0. Data check (wrist EDA)\n", md(V.groupby("dataset").agg(subjects=("subject", "size"), fs_min=("fs_from_length", "min"),
                                                                      fs_max=("fs_from_length", "max"), min_uS=("min_uS", "min"),
                                                                      median_uS=("median_uS", "median"), max_uS=("max_uS", "max"),
                                                                      nan=("nan", "sum"), near_zero_pct_mean=("near_zero_lt_0.05_pct", "mean"),
                                                                      near_zero_pct_max=("near_zero_lt_0.05_pct", "max")).round(3).reset_index()) + "\n",
         "Per subject:\n\n" + md(V.round(3)) + "\n"]
    for pn in ("test", "dev"):
        subs = part["ppg_dalia"][pn]
        e, c = EV[EV.subject_id.isin(subs)], CT[CT.subject_id.isin(subs)]
        rows = []
        for a in sorted(set(e.activity)):
            ea, ca = e[e.activity == a], c[c.activity == a]
            rows.append({"activity": a, "events": len(ea), "controls": len(ca),
                         "quick_response_events_pct": 100 * ea.quick_response.mean(),
                         "quick_response_controls_pct": 100 * ca.quick_response.mean() if len(ca) else np.nan,
                         "phasic_change_median_events": ea.phasic_change.median(), "phasic_change_median_controls": ca.phasic_change.median(),
                         "tonic_change_median_events": ea.tonic_change.median(), "tonic_change_median_controls": ca.tonic_change.median(),
                         "artefact_events_pct": 100 * ea.artefact.mean()})
        rows.append({"activity": "ALL", "events": len(e), "controls": len(c),
                     "quick_response_events_pct": 100 * e.quick_response.mean(), "quick_response_controls_pct": 100 * c.quick_response.mean(),
                     "phasic_change_median_events": e.phasic_change.median(), "phasic_change_median_controls": c.phasic_change.median(),
                     "tonic_change_median_events": e.tonic_change.median(), "tonic_change_median_controls": c.tonic_change.median(),
                     "artefact_events_pct": 100 * e.artefact.mean()})
        S.append(f"## Part 1 — PPG-DaLiA {pn.upper()} subjects {subs}\n\n" + md(pd.DataFrame(rows).round(2)) + "\n")
        rr = R[R.subject_id.isin(subs)].groupby("activity").agg(minutes=("minutes", "sum"), scrs=("scrs", "sum"),
                                                                artefact_pct=("artefact_pct", "mean"))
        rr["scr_per_min"] = rr.scrs / rr.minutes
        S.append(f"**{pn}: baseline SCR rate per minute by activity (whole recordings)**\n\n" + md(rr.round(2).reset_index()) + "\n")
    agg = W.groupby("condition").agg(scr_per_min_mean=("scr_per_min", "mean"), scr_per_min_std=("scr_per_min", lambda s: s.std(ddof=0)),
                                     scr_amp_mean=("scr_amp_mean_uS", "mean"), tonic_mean=("tonic_mean_uS", "mean"),
                                     tonic_std=("tonic_mean_uS", lambda s: s.std(ddof=0)), artefact_pct=("artefact_pct", "mean")).reset_index()
    d_rows = []
    for sid, g in WS.groupby("subject_id"):
        b, s = g[g.condition == "baseline"].scrs, g[g.condition == "stress"].scrs
        sp = np.sqrt((b.var(ddof=1) + s.var(ddof=1)) / 2) if len(b) > 1 and len(s) > 1 else np.nan
        d_rows.append({"subject_id": sid, "cohens_d_stress_vs_baseline": (s.mean() - b.mean()) / sp if sp and sp > 0 else np.nan,
                       "baseline_min": len(b), "stress_min": len(s)})
    D = pd.DataFrame(d_rows)
    S.append("## Part 2 — WESAD (all 15 subjects; descriptive)\n\n" + md(agg.round(3)) + "\n")
    S.append(f"Per-subject Cohen's d (per-minute SCR count, stress vs baseline): mean {D.cohens_d_stress_vs_baseline.mean():.2f} ± "
             f"{D.cohens_d_stress_vs_baseline.std(ddof=0):.2f}; subjects with d > 0: {(D.cohens_d_stress_vs_baseline > 0).sum()} of {len(D)}.\n\n"
             + md(D.round(2)) + "\n\nPer subject × condition:\n\n" + md(W.round(3)) + "\n")
    e = EV[EV.subject_id.isin(part["ppg_dalia"]["test"])]
    c = CT[CT.subject_id.isin(part["ppg_dalia"]["test"])]
    fig, ax = plt.subplots(figsize=(9, 4))
    acts = sorted(set(e.activity))
    x = np.arange(len(acts))
    ax.bar(x - 0.2, [100 * e[e.activity == a].quick_response.mean() for a in acts], 0.4, label="after a false alarm")
    ax.bar(x + 0.2, [100 * c[c.activity == a].quick_response.mean() if (c.activity == a).any() else 0 for a in acts], 0.4, label="random calm moment")
    ax.set_xticks(x, acts, rotation=30)
    ax.set_ylabel("% with a quick sweat response (1–5 s)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "a02_quick_response_by_activity_test.png", dpi=100)
    MD.write_text("\n".join(S))
    print("done")


if __name__ == "__main__":
    main()
