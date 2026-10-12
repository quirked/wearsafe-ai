"""D08 — FallAllD wrist: Layer A (unclipped + e4_clipped, 32 Hz, m/s^2) and the window table, per subject.

Reads only the extracted original FallAllD.pkl (restricted unpickler; banned file refused). Writes
  <out-root>/normalized_signals_<tag>/{unclipped,e4_clipped}/FALLALLD_Sxx.parquet
  <out-root>/windows_<tag>/windows.parquet (+ run_info.json, checks.json)
  <meta-dir>/fallalld_records_<tag>.csv
Invariant checks stop the run on failure. Refuses to overwrite.
Usage (repo root):  python scripts/d08_fallalld_build.py --subjects 1 4 --tag smoke_v1
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402
from wearsafe.fallalld_windows import record_windows  # noqa: E402
from wearsafe.schemas import namespaced_subject_id  # noqa: E402

CFG = REPO / "config/fallalld_v1.yaml"
VERSIONS = ("unclipped", "e4_clipped")


class InvariantError(RuntimeError):
    pass


def check(cond, msg, results, scope):
    results.append({"scope": scope, "check": msg, "passed": bool(cond)})
    if not cond:
        raise InvariantError(f"{scope}: FAILED {msg}")


def h(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def audit_counts():
    """Per-subject wrist (adl, fall) counts parsed from the D00c tables (A6), for cross-checking."""
    text = (REPO / "reports/D00c_fallalld_upfall_audit_tables.md").read_text()
    sec = text[text.index("## A6."):text.index("## A7.")]
    return {int(m[0]): (int(m[1]), int(m[2])) for m in re.findall(r"^\| (\d+) \| (\d+) \| (\d+) \| \d+ \|$", sec, re.M)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-root", default="data/interim/fallalld")
    ap.add_argument("--meta-dir", default="metadata")
    args = ap.parse_args()
    root = REPO / args.out_root
    out_sig, out_win = root / f"normalized_signals_{args.tag}", root / f"windows_{args.tag}"
    meta = REPO / args.meta_dir / f"fallalld_records_{args.tag}.csv"
    for p in (out_sig, out_win, meta):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite (CLAUDE.md §2.1)")
    cfg = yaml.safe_load(open(CFG))
    cpg, fs, n_in, n_out = cfg["counts_per_g"], cfg["resample"]["target_hz"], cfg["samples_per_record"], cfg["resample"]["samples_out"]
    rkw = {"up": cfg["resample"]["up"], "down": cfg["resample"]["down"], "beta": cfg["resample"]["kaiser_beta"],
           "padtype": cfg["resample"]["padtype"]}
    results = []
    w, info = fio.wrist_records(REPO)
    lu = pd.read_csv(REPO / cfg["label_uncertain"]["file"])
    uncertain = set(lu.loc[lu.status == "label_uncertain_fall", "record_id"])
    og = pd.read_csv(REPO / cfg["overlap_groups"]["file"]).set_index("record_id")
    check(len(uncertain) == 25, f"25 label_uncertain_fall clips in {cfg['label_uncertain']['file']}", results, "ALL")
    check(set(og.index) == set(w.record_id), "every wrist record has an overlap_group_id", results, "ALL")
    check(len(w) == 2515 and (w.kind == "fall").sum() == 523 and (w.kind == "adl").sum() == 1992,
          f"wrist record counts equal the D00c audit (2515 / 523 falls / 1992 ADLs; got {len(w)})", results, "ALL")
    aud = audit_counts()
    got = {int(s): (int((g.kind == "adl").sum()), int((g.kind == "fall").sum())) for s, g in w.groupby("SubjectID")}
    check(got == aud, "per-subject (adl, fall) counts equal D00c table A6", results, "ALL")
    tmp_sig, tmp_win = out_sig.with_name(out_sig.name + ".partial"), out_win.with_name(out_win.name + ".partial")
    for p in (tmp_sig, tmp_win):
        if p.exists():
            raise FileExistsError(f"{p} exists from an interrupted run; inspect it, do not overwrite")
    for v in VERSIONS:
        (tmp_sig / v).mkdir(parents=True)
    tmp_win.mkdir(parents=True)
    lo_m, hi_m = mh.E4_LO_G * mh.G, mh.E4_HI_G * mh.G
    win_parts, rec_rows, t0 = [], [], time.time()
    for n in args.subjects:
        sid = namespaced_subject_id("fallalld", n)
        sub = w[w.subject_id == sid]
        check(len(sub) > 0, f"{sid} has wrist records", results, sid)
        layer = {v: [] for v in VERSIONS}
        for r in sub.itertuples():
            counts = r.Acc
            h_in = h(counts)
            if counts.shape != (n_in, 3):
                check(False, f"{r.record_id}: input shape {counts.shape} != ({n_in}, 3)", results, sid)
            un = mh.harmonise(counts, "unclipped", cpg, rkw)
            h_un = h(un["acc_m_s2"])
            e4 = mh.harmonise(counts, "e4_clipped", cpg, rkw)
            un2 = mh.harmonise(counts, "unclipped", cpg, rkw)
            if not (h(un2["acc_m_s2"]) == h_un and h(counts) == h_in):
                check(False, f"{r.record_id}: unclipped / input altered by the e4 step", results, sid)
            for v, res in (("unclipped", un), ("e4_clipped", e4)):
                a = res["acc_m_s2"]
                if a.shape != (n_out, 3) or not np.isfinite(a).all():
                    check(False, f"{r.record_id} {v}: shape {a.shape} / NaN", results, sid)
                if v == "e4_clipped":
                    c = a / mh.G * mh.E4_COUNTS_PER_G
                    ok = (a.min() >= lo_m - 1e-9 and a.max() <= hi_m + 1e-9 and np.allclose(c, np.round(c), atol=1e-9)
                          and np.array_equal(res["sat_axes"], (np.round(c) == -128) | (np.round(c) == 127)))
                    if not ok:
                        check(False, f"{r.record_id}: e4 rails / 1/64 g grid / saturation flag", results, sid)
                idx = np.arange(n_out)
                layer[v].append(pd.DataFrame({
                    "record_id": r.record_id, "subject_id": sid, "activity_id": int(r.ActivityID),
                    "trial_no": int(r.TrialNo), "original_label": r.original_label, "kind": r.kind, "version": v,
                    "sample_idx": idx, "timestamp": idx / fs,
                    "x": a[:, 0], "y": a[:, 1], "z": a[:, 2],
                    "sat_x": res["sat_axes"][:, 0], "sat_y": res["sat_axes"][:, 1], "sat_z": res["sat_axes"][:, 2],
                    "acc_saturated": res["sat_axes"].any(axis=1),
                    "original_unit": f"int16 counts ({cpg} counts/g, inferred; verified by D08 gravity check)",
                    "canonical_unit": "m/s^2", "sampling_rate": float(fs)}))
            mag = np.sqrt((un["acc_m_s2"] ** 2).sum(axis=1))
            t_pk = float(np.argmax(mag)) / fs
            rec = {"record_id": r.record_id, "subject_id": sid, "activity_id": int(r.ActivityID),
                   "trial_no": int(r.TrialNo), "original_label": r.original_label, "kind": r.kind,
                   "label_uncertain": r.record_id in uncertain,
                   "overlap_group_id": og.at[r.record_id, "overlap_group_id"],
                   "dedup_representative": bool(og.at[r.record_id, "dedup_representative"])}
            win_parts.append(record_windows(rec, cfg, fs, n_out))
            rec_rows.append({**rec, "raw_acc_sha256": h_in, "n_in": n_in, "n_out": n_out,
                             "peak_t_unclipped_32hz": t_pk,
                             "peak_outside_positive_window": bool(r.kind == "fall" and not (9 <= t_pk < 11)),
                             "e4_saturated_frac": float(e4["sat_axes"].any(axis=1).mean())})
        for v in VERSIONS:
            pd.concat(layer[v], ignore_index=True).to_parquet(tmp_sig / v / f"{sid}.parquet", index=False)
        check(True, f"{len(sub)} records: input {n_in} → output {n_out} samples, no NaN, unclipped/input unaltered by "
              "the e4 step, e4 within rails, on the 1/64 g grid, saturation flag ⇔ rails", results, sid)
        print(f"{sid}: {len(sub)} records, {time.time() - t0:.0f}s", flush=True)
    win = pd.concat(win_parts, ignore_index=True)
    recs = pd.DataFrame(rec_rows)
    per = cfg["windows"]["per_record"]
    check((win.groupby("record_id").size() == per).all() and win.record_id.nunique() == len(recs),
          f"exactly {per} windows per record", results, "windows")
    check(((win.i1 - win.i0) == fs * cfg["windows"]["length_s"]).all() and win.i0.min() >= 0 and win.i1.max() <= n_out,
          "every window has 64 samples within [0, 640)", results, "windows")
    check(win.window_id.is_unique, "window_id unique", results, "windows")
    check(win.groupby("window_id").record_id.nunique().max() == 1, "no window spans two records", results, "windows")
    fallw = win[(win.kind == "fall") & ~win.record_id.isin(uncertain)]
    check(set(fallw.loc[fallw.window_role == "fall_positive", "window_start"]) <= {9.0}
          and (fallw.groupby("record_id").window_role.apply(lambda s: (s == "fall_positive").sum()) == 1).all(),
          "exactly one positive window per (non-label-uncertain) fall clip, starting at 9 s", results, "labels")
    unc_w = win[win.record_id.isin(uncertain)]
    check((unc_w.window_role == "label_uncertain_fall").all() and not unc_w.eval_role.eq("train_candidate").any()
          and (unc_w.clip_level_class == "fall").all() and (win.window_role == "label_uncertain_fall").sum() == len(unc_w),
          "label-uncertain clips: all windows label_uncertain_fall, never train_candidate, clip-level fall",
          results, "labels")
    check(win.overlap_group_id.notna().all() and
          (win.groupby("record_id").overlap_group_id.nunique() == 1).all(),
          "every window carries its record's overlap_group_id", results, "labels")
    check(not win.loc[win.activity_id.isin(cfg["probe_ids"]), "eval_role"].eq("train_candidate").any()
          and (win.loc[win.activity_id.isin(cfg["probe_ids"]), "window_role"] == "hard_negative_probe").all(),
          "probes 15/23: all windows hard_negative_probe, never train_candidate", results, "labels")
    check(not win.loc[win.window_role == "fall_clip_context", "eval_role"].eq("train_candidate").any()
          and win.loc[win.window_role == "fall_clip_context", "motion_event_class"].isna().all(),
          "fall_clip_context never train_candidate and has no motion class", results, "labels")
    for sid, g in win.groupby("subject_id"):
        r = recs[recs.subject_id == sid]
        nu = int(r.record_id.isin(uncertain).sum())
        nf = int((r.kind == "fall").sum()) - nu
        na = int(((r.kind == "adl") & ~r.activity_id.isin(cfg["probe_ids"])).sum())
        npb = int(r.activity_id.isin(cfg["probe_ids"]).sum())
        exp = {"fall_positive": nf, "fall_clip_context": nf * (per - 1), "adl": na * per,
               "hard_negative_probe": npb * per, "label_uncertain_fall": nu * per}
        got_c = {k: int((g.window_role == k).sum()) for k in exp}
        check(got_c == exp, f"window role counts equal the formula {exp}", results, sid)
    tmp_sig.rename(out_sig)
    win.to_parquet(tmp_win / "windows.parquet", index=False)
    info_d = {"script": "scripts/d08_fallalld_build.py",
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                           text=True).stdout.strip(),
              "tag": args.tag, "subjects": args.subjects, "config_sha256": hashlib.sha256(CFG.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256((REPO / fio.UNZIPPED / "FallAllD.pkl").read_bytes()).hexdigest(),
              "n_records": len(recs), "n_windows": len(win), "seed": None, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (tmp_win / "run_info.json").write_text(json.dumps(info_d, indent=2))
    (tmp_win / "checks.json").write_text(json.dumps(results, indent=2))
    tmp_win.rename(out_win)
    meta.parent.mkdir(parents=True, exist_ok=True)
    recs.to_csv(meta, index=False)
    print(f"all {len(results)} checks passed; {len(recs)} records, {len(win)} windows")


if __name__ == "__main__":
    main()
