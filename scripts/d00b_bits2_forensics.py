"""D00b: BITS-2 forensics and exclusion list (read-only on data/raw/).

Implements the plan approved by the user on 2026-10-12, with the user's decisions and the operational
definitions logged in PROJECT_LOG.md ("User decisions D00b", "Operational definitions ...").

Inputs (read-only):
  data/raw/bits2/Dataset                          Zenodo copy (primary)
  data/raw/bits2_website/Dataset                  website full_dataset copy
  data/raw/bits2_website_nohr/Dataset_no_heart    website "without heart rate" copy (if downloaded)
  docs/papers/BITS2_DataInBrief_2024.pdf          paper (Table 1 parsed with pdftotext)
Outputs (refuses to overwrite):
  metadata/bits2_file_manifest.csv
  metadata/bits2_exclusions.csv
  reports/D00b_bits2_forensics_tables.md          auto-generated tables quoted by the D00b report

Usage (from repo root):  python scripts/d00b_bits2_forensics.py
"""
import collections
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wearsafe.bits2_io import IMU_STREAMS, STREAMS, parse_file, parse_name, rounding_step, sig_digits, values_hash  # noqa: E402

ZEN = Path("data/raw/bits2/Dataset")
WEB = Path("data/raw/bits2_website/Dataset")
NOHR = Path("data/raw/bits2_website_nohr/Dataset_no_heart")
PDF = Path("docs/papers/BITS2_DataInBrief_2024.pdf")
OUT_MANIFEST = Path("metadata/bits2_file_manifest.csv")
OUT_EXCL = Path("metadata/bits2_exclusions.csv")
OUT_TABLES = Path("reports/D00b_bits2_forensics_tables.md")

# ---- fixed criteria (PROJECT_LOG 2026-10-12, logged before running) ----
NS = 1e-9                     # timestamp unit: ns [inferred]
PAPER_RATE = 20.0
SPREAD_MAX = 0.15             # IQR/median
AB_AGREE_MAX = 0.15           # median per-file relative difference
PAPER_TOL = 0.10              # within ±10% of 20 Hz
DUR_BAND = (0.6, 1.6)         # duration cross-check band
GAP_STEPS = 5                 # forward jump > 5 rounding steps = gap ...
GAP_MIN_S = 1.0               # ... and > 1 s (amendment after trial run, PROJECT_LOG 2026-10-12)
MIN_GROUP = 3
HR_MIN, HR_MAX = 30, 220
HR_OK_FRAC, HR_OK_MIN = 0.80, 20
G = 9.80665
E4_LIMIT = 2 * G
MIN_HASH_ROWS = 20
PREFIX_ROWS = 50


def refuse_overwrite(*paths):
    for p in paths:
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite (CLAUDE.md §2.1)")


def sha1(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- paper Table 1
def paper_activities():
    text = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], check=True,
                          capture_output=True, text=True).stdout
    table = text[text.index("Activity list and details."):text.index("Fig. 4.")]
    row = re.compile(r"^\s*(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s*(min|s)\b(?:\s+(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s*(min|s)\b)?")
    acts = {}
    for line in table.splitlines():
        m = row.match(line)
        if not m:
            continue
        sec = int(m.group(4)) * (60 if m.group(5) == "min" else 1)
        acts[("adl", int(m.group(1)))] = dict(name=m.group(2).strip(), trials=int(m.group(3)), stated_s=sec)
        if m.group(6):
            sec2 = int(m.group(9)) * (60 if m.group(10) == "min" else 1)
            acts[("fall", int(m.group(6)))] = dict(name=m.group(7).strip(), trials=int(m.group(8)), stated_s=sec2)
    assert len([k for k in acts if k[0] == "adl"]) == 16 and len([k for k in acts if k[0] == "fall"]) == 8, acts
    return acts


# ---------------------------------------------------------------- rate estimators
def runs_of(df):
    """Consecutive runs of identical timestamp strings, per block: list of (block, t_raw, value, length)."""
    out = []
    for b, sub in df.groupby("block", sort=False):
        raw = sub["t_raw"].to_numpy()
        val = sub["t"].to_numpy()
        start = 0
        for i in range(1, len(raw) + 1):
            if i == len(raw) or raw[i] != raw[start]:
                out.append((b, raw[start], val[start], i - start))
                start = i
    return out


def rate_A(df):
    """Median rows per full rounding step / step seconds, over interior runs whose neighbours are exactly ±1 step."""
    runs = runs_of(df)
    rates = []
    for i in range(1, len(runs) - 1):
        b, raw, v, n = runs[i]
        if runs[i - 1][0] != b or runs[i + 1][0] != b:
            continue
        step = rounding_step(raw)
        if not step:
            continue
        tol = step * 1e-6
        if abs(runs[i - 1][2] - (v - step)) < tol and abs(runs[i + 1][2] - (v + step)) < tol:
            rates.append(n / (step * NS))
    return (float(np.median(rates)), len(rates)) if rates else (np.nan, 0)


def segments(df):
    """Split a stream at timestamp resets (decrease > 1 step), forward jumps > GAP_STEPS steps, and block repeats."""
    if df.empty:
        return []
    cuts = [0]
    raw, t, blk = df["t_raw"].to_numpy(), df["t"].to_numpy(), df["block"].to_numpy()
    for i in range(1, len(t)):
        step = rounding_step(raw[i]) or 0
        if blk[i] != blk[i - 1] or t[i] < t[i - 1] - step or t[i] - t[i - 1] > max(GAP_STEPS * step, GAP_MIN_S / NS):
            cuts.append(i)
    cuts.append(len(t))
    return [(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1)]


def spread(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    if len(x) < MIN_GROUP:
        return np.nan, len(x), np.nan
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return (q3 - q1) / med, len(x), med


# ---------------------------------------------------------------- main
def main():
    global OUT_MANIFEST, OUT_EXCL, OUT_TABLES
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", help="write the three outputs here instead (trial runs)")
    args = ap.parse_args()
    if args.out_dir:
        d = Path(args.out_dir)
        OUT_MANIFEST, OUT_EXCL, OUT_TABLES = d / OUT_MANIFEST.name, d / OUT_EXCL.name, d / OUT_TABLES.name
    refuse_overwrite(OUT_MANIFEST, OUT_EXCL, OUT_TABLES)
    acts = paper_activities()
    paths = sorted(ZEN.rglob("*.csv"))
    print(f"files: {len(paths)}", flush=True)

    recs, parsed = [], {}
    for p in paths:
        rel = p.relative_to(ZEN).as_posix()
        user, group, idx, dot = parse_name(p.name)
        f = parse_file(p)
        parsed[rel] = f
        r = dict(path=f"data/raw/bits2/Dataset/{rel}", rel=rel, sha1=f.sha1, user=user,
                 subject_id=f"BITS2_S{user:02d}", group=group, file_index=idx,
                 original_label=f"{group}{idx}", name_anomaly=dot,
                 paper_activity=acts[(group, idx)]["name"], paper_trials=acts[(group, idx)]["trials"],
                 stated_trial_s=acts[(group, idx)]["stated_s"],
                 event_type=group,
                 motion_event_class_proposed="abrupt_event_proxy" if group == "fall" else "normal_adl",
                 header=f.header[:12], bom=f.bom, crlf=f.crlf, lone_cr=f.lone_cr,
                 inner_headers=f.inner_headers, blank_rows=f.blank_rows, malformed_rows=len(f.malformed),
                 block_order=f.block_order)
        for s in STREAMS:
            r[f"rows_{s}"] = len(f.streams[s])
            r[f"blocks_{s}"] = sum(1 for b in f.blocks if b[0] == s)
        # timestamp precision
        alld = [sig_digits(t) for s in STREAMS for t in f.streams[s]["t_raw"]]
        alld = [d for d in alld if d is not None]
        r["ts_sigdigits_min"], r["ts_sigdigits_median"], r["ts_sigdigits_max"] = min(alld), float(np.median(alld)), max(alld)
        tmin = min(f.streams[s]["t"].min() for s in STREAMS if len(f.streams[s]))
        r["ts_first_ns"] = tmin
        steps = [rounding_step(t) for t in f.streams["acg"]["t_raw"]]
        steps = [s for s in steps if s]
        r["ts_step_s_median_acg"] = float(np.median(steps)) * NS if steps else np.nan
        r["nonmonotonic_streams"] = " ".join(s for s in STREAMS if len(f.streams[s]) > 1 and (np.diff(f.streams[s]["t"]) < 0).any())
        # rates
        for s in IMU_STREAMS + ("hrt",):
            r[f"rateA_{s}_hz"], r[f"rateA_{s}_nruns"] = rate_A(f.streams[s])
        r["rateB_acg_hz"] = r["rows_acg"] / r["rows_hrt"] if r["rows_hrt"] else np.nan
        if np.isfinite(r["rateA_acg_hz"]) and np.isfinite(r["rateB_acg_hz"]):
            a, b = r["rateA_acg_hz"], r["rateB_acg_hz"]
            r["rateAB_reldiff"] = abs(a - b) / ((a + b) / 2)
        else:
            r["rateAB_reldiff"] = np.nan
        # HR validity (decision 3); malformed HR rows count as invalid
        h = f.streams["hrt"]
        bpm, st = h["bpm"].to_numpy(), h["status"].to_numpy()
        invalid = (st == "-1") | (bpm == 0) | (bpm < HR_MIN) | (bpm > HR_MAX)
        n_mal_hr = sum(1 for _, line in f.malformed if ",hrt" in line)
        r["hr_rows_total"] = len(h) + n_mal_hr
        r["hr_rows_valid"] = int((~invalid).sum())
        r["hr_rows_invalid"] = int(invalid.sum()) + n_mal_hr
        r["hr_rows_status_minus1"] = int((st == "-1").sum())
        r["hr_rows_bpm_zero"] = int((bpm == 0).sum())
        r["hr_rows_out_of_range"] = int(((bpm != 0) & ((bpm < HR_MIN) | (bpm > HR_MAX))).sum())
        r["hr_rows_unreliable_status0"] = int((st == "0").sum())
        r["hr_valid_frac"] = r["hr_rows_valid"] / r["hr_rows_total"] if r["hr_rows_total"] else 0.0
        # HR timing relative to the IMU (acg) span, at rounded-timestamp resolution: HR rows whose
        # timestamp is below the first / above the last acg timestamp value. Ties count as 'during'.
        if len(f.streams["acg"]) and len(h):
            g0, g1 = f.streams["acg"]["t"].min(), f.streams["acg"]["t"].max()
            ht = h["t"].to_numpy()
            r["hr_rows_before_imu"] = int((ht < g0).sum())
            r["hr_rows_during_imu"] = int(((ht >= g0) & (ht <= g1)).sum())
            r["hr_rows_after_imu"] = int((ht > g1).sum())
            r["acg_span_s_coarse"] = (g1 - g0) * NS
            r["hrt_span_s_coarse"] = (ht.max() - ht.min()) * NS
        # duration (HR rows ~ seconds at 1 Hz)
        r["dur_ratio_1trial"] = r["hr_rows_total"] / r["stated_trial_s"]
        r["dur_ratio_5trials"] = r["hr_rows_total"] / (5 * r["stated_trial_s"])
        # segments per stream
        segs = {s: segments(f.streams[s]) for s in STREAMS}
        r["segments_per_stream"] = " ".join(f"{s}:{len(segs[s])}" for s in STREAMS)
        # repeated block sets: are the repeats value-identical copies of the first block?
        rep = []
        for s in STREAMS:
            d_ = f.streams[s]
            blks = [values_hash(g) for _, g in d_.groupby("block", sort=True)] if len(d_) else []
            if len(blks) > 1:
                rep.append(f"{s}:{'identical' if len(set(blks)) == 1 else 'different'}")
        r["repeated_blocks_identical"] = " ".join(rep)
        r["_segs"] = segs
        # ACC (canonical = acg, decision 8)
        g = f.streams["acg"][["x", "y", "z"]].to_numpy()
        a = f.streams["acc"][["x", "y", "z"]].to_numpy()
        if len(g):
            mag = np.linalg.norm(g, axis=1)
            r["acg_mag_median"] = float(np.median(mag))
            r["acg_mag_max"] = float(mag.max())
            r["acg_frac_any_axis_gt_2g"] = float((np.abs(g) > E4_LIMIT).any(axis=1).mean())
            r["acg_frac_mag_gt_2g"] = float((mag > E4_LIMIT).mean())
            k = int(np.argmax(mag))
            half = 0.5 * mag[k]
            lo = k
            while lo > 0 and mag[lo - 1] > half:
                lo -= 1
            hi = k
            while hi < len(mag) - 1 and mag[hi + 1] > half:
                hi += 1
            r["acg_peak_width_rows_halfmax"] = hi - lo + 1
        r["acc_mag_median"] = float(np.median(np.linalg.norm(a, axis=1))) if len(a) else np.nan
        recs.append(r)
    df = pd.DataFrame(recs)
    print("parsed", flush=True)

    # ---------------- copies on disk
    df["website_identical"] = [ (WEB / rel).exists() and sha1(WEB / rel) == s for rel, s in zip(df.rel, df.sha1)]
    nohr_rows = []
    for rel, s in zip(df.rel, df.sha1):
        q = NOHR / rel
        if not q.exists():
            nohr_rows.append(dict(nohr_status="missing")); continue
        if sha1(q) == s:
            nohr_rows.append(dict(nohr_status="identical")); continue
        fz, fn = parsed[rel], parse_file(q)
        d = dict(nohr_status="different", nohr_rows_hrt=len(fn.streams["hrt"]))
        same_ts, same_vals, more_digits = True, True, False
        for st_ in IMU_STREAMS:
            A, B = fz.streams[st_], fn.streams[st_]
            d[f"nohr_rows_{st_}"] = len(B)
            if len(A) != len(B):
                same_ts = same_vals = False
                continue
            same_ts &= bool((A["t_raw"].to_numpy() == B["t_raw"].to_numpy()).all())
            same_vals &= bool(np.allclose(A[["x", "y", "z"]].to_numpy(), B[["x", "y", "z"]].to_numpy()))
            dz = [sig_digits(t) or 0 for t in A["t_raw"]]
            dn = [sig_digits(t) or 0 for t in B["t_raw"]]
            more_digits |= (np.median(dn) > np.median(dz)) if dn and dz else False
        d.update(nohr_same_imu_timestamps=same_ts, nohr_same_imu_values=same_vals, nohr_more_ts_digits=more_digits)
        nohr_rows.append(d)
    df = pd.concat([df, pd.DataFrame(nohr_rows)], axis=1)
    print("compared copies", flush=True)

    # ---------------- duplicates / shared data
    dup_groups = df.groupby("sha1")["rel"].apply(list)
    dup_groups = [g for g in dup_groups if len(g) > 1]
    shared = collections.defaultdict(set)  # (fileA, fileB) -> streams
    for kind in ("full", "prefix"):
        idx_map = collections.defaultdict(list)
        for rel, f in parsed.items():
            for s in STREAMS:
                d_ = f.streams[s]
                if len(d_) < MIN_HASH_ROWS:
                    continue
                key = values_hash(d_) if kind == "full" else values_hash(d_.iloc[:PREFIX_ROWS])
                idx_map[(s, key)].append(rel)
        for (s, _), rels in idx_map.items():
            rels = sorted(set(rels))
            for i in range(len(rels)):
                for j in range(i + 1, len(rels)):
                    shared[(rels[i], rels[j])].add(s if kind == "full" else f"{s}(first{PREFIX_ROWS})")
    print("hashed", flush=True)

    # ---------------- rate verdict (criteria fixed before running)
    A = df["rateA_acg_hz"].to_numpy()
    sp, nA, medA = spread(A)
    medB = float(np.nanmedian(df["rateB_acg_hz"]))
    rel = df["rateAB_reldiff"].dropna()
    ab_med = float(rel.median()) if len(rel) else np.nan
    ab_frac = float((rel < AB_AGREE_MAX).mean()) if len(rel) else np.nan
    consistent = bool(np.isfinite(sp) and sp < SPREAD_MAX and np.isfinite(ab_med) and ab_med < AB_AGREE_MAX)
    near_paper = bool(np.isfinite(medA) and abs(medA - PAPER_RATE) <= PAPER_TOL * PAPER_RATE)
    if consistent and near_paper:
        verdict = "consistent and ≈20 Hz"
    elif consistent:
        verdict = f"consistent but different from paper ({medA:.1f} Hz)"
    else:
        verdict = "inconsistent"
    print(f"VERDICT: {verdict}  (spread={sp:.3f}, n={nA}, medA={medA:.2f}, medB={medB:.2f}, AB median rel={ab_med:.3f})", flush=True)

    # ---------------- repetitions / splits
    rep_verdict, split_points = [], []
    for _, r in df.iterrows():
        segs = r["_segs"]
        counts = {s: len(segs[s]) for s in STREAMS}
        if all(c <= 1 for c in counts.values()):
            rep_verdict.append("single_segment"); split_points.append(""); continue
        same = len(set(counts.values())) == 1
        if not same:
            rep_verdict.append("ambiguous_segments_disagree_across_streams"); split_points.append(""); continue
        h = parsed[r["rel"]].streams["hrt"]
        pieces_ok = all(DUR_BAND[0] <= (b - a) / r["stated_trial_s"] <= DUR_BAND[1] for a, b in segs["hrt"])
        low_motion_ok = verdict != "inconsistent"   # low-motion >=2 s check needs a trustworthy rate
        if pieces_ok and low_motion_ok:
            rep_verdict.append(f"unambiguous_{counts['acg']}_segments")
            split_points.append(";".join(f"{s}:" + ",".join(str(int(parsed[r['rel']].streams[s]['line'].iloc[a])) for a, _ in segs[s][1:]) for s in STREAMS))
        else:
            why = []
            if not pieces_ok:
                why.append("piece_durations_outside_band")
            if not low_motion_ok:
                why.append("rate_untrustworthy_no_low_motion_check")
            rep_verdict.append(f"ambiguous_{counts['acg']}_segments(" + "+".join(why) + ")")
            split_points.append("")
    df["repetition_verdict"] = rep_verdict
    df["proposed_split_lines"] = split_points
    df["trials_evidence"] = np.where(df["dur_ratio_1trial"].between(*DUR_BAND), "≈1 trial",
                                     np.where(df["dur_ratio_5trials"].between(*DUR_BAND), "≈5 trials", "neither"))

    # ---------------- duration cross-check per index (decision 5)
    idx_tab = df.groupby(["group", "file_index"]).agg(
        paper_activity=("paper_activity", "first"), stated_s=("stated_trial_s", "first"),
        hr_rows_median=("hr_rows_total", "median"), acg_rows_median=("rows_acg", "median"),
        ratio_1trial=("dur_ratio_1trial", "median"), ratio_5trials=("dur_ratio_5trials", "median")).reset_index()
    idx_tab["agrees"] = idx_tab["ratio_1trial"].between(*DUR_BAND) | idx_tab["ratio_5trials"].between(*DUR_BAND)
    disagree = {(g, i) for g, i, a in zip(idx_tab.group, idx_tab.file_index, idx_tab.agrees) if not a}
    df["index_duration_flag"] = [(g, i) in disagree for g, i in zip(df.group, df.file_index)]

    # ---------------- name anomalies
    have = set(zip(df.user, df.group, df.file_index, df.name_anomaly))
    df["name_mapping"] = ""
    for k, r in df[df.name_anomaly].iterrows():
        conflict = (r.user, r.group, r.file_index, False) in have
        df.at[k, "name_mapping"] = "conflict" if conflict else f"maps_to_{r.group}{r.file_index}"

    # ---------------- exclusions (rules = user decisions)
    excl = []
    excluded = set()
    drop_streams = collections.defaultdict(set)
    for g in dup_groups:
        for rel_ in g:
            excl.append(dict(file=rel_, stream="all", rule_id="R1_exact_duplicate",
                             reason="byte-identical to another file; true activity label unknowable",
                             evidence="identical sha1 with " + ", ".join(x for x in g if x != rel_),
                             decision="exclude", decided_by="user decision D00b-1"))
            excluded.add(rel_)
    for (fa, fb), ss in sorted(shared.items()):
        if {fa, fb} <= excluded and any(set(g) == {fa, fb} for g in dup_groups):
            continue
        core = {s for s in ss if not s.startswith("mgm")}
        for rel_, other in ((fa, fb), (fb, fa)):
            if core:
                excl.append(dict(file=rel_, stream="all", rule_id="R2_shared_core_data",
                                 reason="acc/acg/gyro/hrt values shared with another file",
                                 evidence=f"shared with {other}: {' '.join(sorted(ss))}",
                                 decision="exclude", decided_by="user decision D00b-2"))
                excluded.add(rel_)
            else:
                excl.append(dict(file=rel_, stream="mgm", rule_id="R3_shared_mgm_only",
                                 reason="only magnetometer values shared with another file",
                                 evidence=f"shared with {other}: {' '.join(sorted(ss))}",
                                 decision="drop_stream", decided_by="user decision D00b-2"))
                drop_streams[rel_].add("mgm")
    for _, r in df.iterrows():
        rv = r["repetition_verdict"]
        if rv.startswith("ambiguous") and r["blocks_acg"] > 1:
            excl.append(dict(file=r.rel, stream="all", rule_id="R4_multi_recording_ambiguous",
                             reason="file contains repeated block sets; split not unambiguous",
                             evidence=f"{r.segments_per_stream}; {rv}",
                             decision="exclude", decided_by="approved plan step 4"))
            excluded.add(r.rel)
        elif rv.startswith("ambiguous"):
            excl.append(dict(file=r.rel, stream="all", rule_id="R4b_timestamp_discontinuity",
                             reason="timestamp resets/gaps inside streams; not split",
                             evidence=f"{r.segments_per_stream}; {rv}",
                             decision="keep_with_flag", decided_by="approved plan step 3"))
        elif rv.startswith("unambiguous"):
            excl.append(dict(file=r.rel, stream="all", rule_id="R4c_split_proposed",
                             reason="unambiguous segment boundaries", evidence=r.proposed_split_lines,
                             decision="pending_user", decided_by="approved plan step 3 (split only proposed)"))
        if r.name_anomaly:
            excl.append(dict(file=r.rel, stream="all", rule_id="R5_name_anomaly",
                             reason="filename has '_.' before the label", evidence=r.name_mapping,
                             decision="keep_with_flag" if r.name_mapping.startswith("maps_to") else "pending_user",
                             decided_by="approved plan step 4"))
        if r.index_duration_flag:
            excl.append(dict(file=r.rel, stream="all", rule_id="R6_index_duration_mismatch",
                             reason="per-index median duration disagrees with paper Table 1",
                             evidence=f"index {r.original_label}: stated {r.stated_trial_s}s",
                             decision="keep_with_flag", decided_by="user decision D00b-5"))
        if r.malformed_rows:
            excl.append(dict(file=r.rel, stream="all", rule_id="R8_malformed_rows",
                             reason="rows skipped by the parser", evidence=f"{r.malformed_rows} rows",
                             decision="keep_with_flag", decided_by="approved plan step 4"))
    df["excluded"] = df.rel.isin(excluded)
    df["dropped_streams"] = [" ".join(sorted(drop_streams[x])) for x in df.rel]
    df["motion_ok"] = (~df.excluded) & (df.rows_acg > 0)
    df["hr_ok"] = df.motion_ok & (df.hr_valid_frac >= HR_OK_FRAC) & (df.hr_rows_valid >= HR_OK_MIN)
    for _, r in df[df.motion_ok & ~df.hr_ok].iterrows():
        excl.append(dict(file=r.rel, stream="hrt", rule_id="R7_hr_insufficient",
                         reason=f"<{int(HR_OK_FRAC*100)}% valid HR rows or <{HR_OK_MIN} valid HR rows",
                         evidence=f"valid {r.hr_rows_valid}/{r.hr_rows_total}",
                         decision="motion_only", decided_by="user decision D00b-4"))
    excl_df = pd.DataFrame(excl)

    # ---------------- write outputs
    manifest_cols = [c for c in df.columns if not c.startswith("_") and c != "rel"]
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    df[manifest_cols].to_csv(OUT_MANIFEST, index=False)
    excl_df.to_csv(OUT_EXCL, index=False)
    write_tables(df, parsed, idx_tab, excl_df, dup_groups, shared, verdict,
                 dict(sp=sp, nA=nA, medA=medA, medB=medB, ab_med=ab_med, ab_frac=ab_frac,
                      consistent=consistent, near_paper=near_paper))
    print(f"wrote {OUT_MANIFEST}, {OUT_EXCL}, {OUT_TABLES}", flush=True)


def q(x, p):
    x = np.asarray([v for v in x if np.isfinite(v)])
    return np.percentile(x, p) if len(x) else np.nan


def write_tables(df, parsed, idx_tab, excl_df, dup_groups, shared, verdict, v):
    L = ["# D00b — BITS-2 forensics: auto-generated tables",
         "", "Generated by `scripts/d00b_bits2_forensics.py`. Do not edit by hand; numbers quoted in "
         "`reports/D00b_bits2_forensics.md` come from here.", ""]

    L += ["## 1. Files and copies", "",
          f"- Zenodo files parsed: {len(df)}; users: {df.user.nunique()}; ADL files: {(df.group=='adl').sum()}; fall files: {(df.group=='fall').sum()}",
          f"- Website full copy byte-identical: {int(df.website_identical.sum())}/{len(df)}",
          f"- Website 'without heart rate' copy: " + ", ".join(f"{k}={v_}" for k, v_ in df.nohr_status.value_counts().items()), ""]
    if (df.nohr_status == "different").any():
        d = df[df.nohr_status == "different"]
        L += [f"- 'different' no-HR files: {len(d)}; same IMU timestamps: {int(d.nohr_same_imu_timestamps.sum())}; "
              f"same IMU values: {int(d.nohr_same_imu_values.sum())}; more timestamp digits: {int(d.nohr_more_ts_digits.sum())}; "
              f"no-HR files still containing hrt rows: {int((d.nohr_rows_hrt > 0).sum())}", ""]
    tot = {s: int(df[f'rows_{s}'].sum()) for s in STREAMS}
    L += [f"- Rows per stream (all files): {tot}", ""]

    L += ["## 2. Sampling rate", "",
          "Estimator A per stream (rows per full rounding step / step seconds; interior runs only):", "",
          "| stream | files with estimate | median Hz | IQR/median | p5 | p25 | p75 | p95 | total qualifying runs |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in IMU_STREAMS + ("hrt",):
        x = df[f"rateA_{s}_hz"].to_numpy()
        sp_, n_, med_ = spread(x)
        L.append(f"| {s} | {n_} | {med_:.2f} | {sp_:.3f} | {q(x,5):.2f} | {q(x,25):.2f} | {q(x,75):.2f} | {q(x,95):.2f} | {int(df[f'rateA_{s}_nruns'].sum())} |")
    b = df["rateB_acg_hz"].to_numpy()
    L += ["", f"Estimator B (acg rows / HR rows): files={int(np.isfinite(b).sum())}, median={np.nanmedian(b):.2f}, "
          f"p25={q(b,25):.2f}, p75={q(b,75):.2f}, p5={q(b,5):.2f}, p95={q(b,95):.2f}", "",
          f"A–B agreement (files with both): n={int(df.rateAB_reldiff.notna().sum())}, median relative difference={v['ab_med']:.3f}, "
          f"fraction within 15%={v['ab_frac']:.3f}", "",
          "**Verdict (criteria fixed before running):**", "",
          f"- (a) consistency: spread IQR/median = {v['sp']:.3f} (needs < {SPREAD_MAX}); A–B median rel. diff = {v['ab_med']:.3f} (needs < {AB_AGREE_MAX}) → consistent = {v['consistent']}",
          f"- (b) match to paper: median rate_A(acg) = {v['medA']:.2f} Hz vs stated {PAPER_RATE} Hz (±{int(PAPER_TOL*100)}%) → ≈20 Hz = {v['near_paper']}",
          f"- **Final verdict: {verdict}**", ""]
    a_ = df[df.rateA_acg_hz.notna()]
    L += ["Per-file estimator A (acg) histogram, by acg rounding step:", "",
          "| step | n files | <1 Hz | 1–5 | 5–15 | 15–25 | 25–45 | 45–55 | 55–90 | 90–110 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for stp, g in a_.groupby(a_.ts_step_s_median_acg.round(3)):
        c = pd.cut(g.rateA_acg_hz, [0, 1, 5, 15, 25, 45, 55, 90, 110]).value_counts().sort_index().tolist()
        L.append(f"| {stp:g} s | {len(g)} | " + " | ".join(str(x) for x in c) + " |")
    L += ["", f"HR timing vs IMU (acg) span, rounded-timestamp resolution (files with both): "
          f"median HR rows before IMU start {df.hr_rows_before_imu.median():.0f}, during {df.hr_rows_during_imu.median():.0f}, "
          f"after {df.hr_rows_after_imu.median():.0f}; files with ≥10 HR rows before IMU: {int((df.hr_rows_before_imu >= 10).sum())}; "
          f"files with 0 HR rows during IMU span: {int((df.hr_rows_during_imu == 0).sum())}", ""]
    L += ["Timestamp precision: files by median significant digits: " +
          ", ".join(f"{k}: {v_}" for k, v_ in df.ts_sigdigits_median.value_counts().sort_index().items()),
          "", "Rounding step of acg timestamps (median per file, seconds): " +
          ", ".join(f"{k:g}s: {v_}" for k, v_ in df.ts_step_s_median_acg.round(6).value_counts().sort_index().items()), ""]
    for by, title in (("original_label", "activity"), ("subject_id", "subject")):
        L += [f"### Rate consistency per {title} (estimator A, acg)", "",
              f"| {title} | n files with A | median Hz | IQR/median | consistent (<{SPREAD_MAX}) | median B | median A–B rel |",
              "|---|---|---|---|---|---|---|"]
        keys = df[by].unique()
        if by == "original_label":
            keys = sorted(keys, key=lambda k: (k[:3] != "adl", int(re.sub(r"\D", "", k))))
        else:
            keys = sorted(keys)
        for k in keys:
            g = df[df[by] == k]
            sp_, n_, med_ = spread(g.rateA_acg_hz)
            L.append(f"| {k} | {n_} | {med_:.2f} | {sp_:.3f} | {bool(np.isfinite(sp_) and sp_ < SPREAD_MAX)} | "
                     f"{np.nanmedian(g.rateB_acg_hz):.2f} | {np.nanmedian(g.rateAB_reldiff) if g.rateAB_reldiff.notna().any() else float('nan'):.3f} |")
        L.append("")

    L += ["## 3. Duration cross-check per index (decision 5) and repetitions", "",
          "| index | paper activity | stated trial s | median HR rows | median acg rows | HR rows / stated | HR rows / (5×stated) | agrees |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in idx_tab.sort_values(["group", "file_index"], key=lambda c: c if c.name != "group" else c.map({"adl": 0, "fall": 1})).iterrows():
        L.append(f"| {r.group}{r.file_index} | {r.paper_activity} | {r.stated_s} | {r.hr_rows_median:.0f} | {r.acg_rows_median:.0f} | "
                 f"{r.ratio_1trial:.2f} | {r.ratio_5trials:.2f} | {r.agrees} |")
    L += ["", "Per-file trials evidence (HR rows vs stated duration): " +
          ", ".join(f"{k}: {v_}" for k, v_ in df.trials_evidence.value_counts().items()),
          "", "Repetition verdicts: " + ", ".join(f"{k}: {v_}" for k, v_ in df.repetition_verdict.value_counts().items()),
          "", "Files whose streams have more than one segment (reset / gap / repeated block):", ""]
    multi = df[df.repetition_verdict != "single_segment"]
    for _, r in multi.iterrows():
        L.append(f"- {r.rel}: {r.segments_per_stream} → {r.repetition_verdict}")
    L.append("")

    L += ["## 4. Duplicates and shared data", "",
          f"- Byte-identical groups: {dup_groups}", "", "Shared stream values between files (values-only hash, ≥20 rows; 'first50' = identical first 50 rows):", ""]
    for (fa, fb), ss in sorted(shared.items()):
        same_user = fa.split("/")[1] == fb.split("/")[1]
        L.append(f"- {fa} ↔ {fb}: {' '.join(sorted(ss))} ({'same' if same_user else 'different'} subject)")
    L += ["", "Name anomalies: " + "; ".join(f"{r.rel} → {r.name_mapping}" for _, r in df[df.name_anomaly].iterrows()), ""]

    L += ["## 5. Heart rate validity (decision 3, 4)", ""]
    t = df[["hr_rows_total", "hr_rows_valid", "hr_rows_invalid", "hr_rows_status_minus1", "hr_rows_bpm_zero",
            "hr_rows_out_of_range", "hr_rows_unreliable_status0"]].sum()
    L += [f"- Totals: {t.to_dict()}",
          f"- Overall invalid fraction: {t.hr_rows_invalid / t.hr_rows_total:.3f}",
          f"- Files hr_ok: {int(df.hr_ok.sum())}/{len(df)}; motion_ok: {int(df.motion_ok.sum())}/{len(df)}", "",
          "Invalid HR fraction per activity (pooled rows):", "", "| index | rows | invalid frac | files hr_ok |", "|---|---|---|---|"]
    for k in sorted(df.original_label.unique(), key=lambda k: (k[:3] != "adl", int(re.sub(r"\D", "", k)))):
        g = df[df.original_label == k]
        L.append(f"| {k} | {int(g.hr_rows_total.sum())} | {g.hr_rows_invalid.sum() / max(g.hr_rows_total.sum(), 1):.3f} | {int(g.hr_ok.sum())}/{len(g)} |")
    L += ["", "Invalid HR fraction per subject (pooled rows):", "", "| subject | rows | invalid frac | files hr_ok |", "|---|---|---|---|"]
    for k in sorted(df.subject_id.unique()):
        g = df[df.subject_id == k]
        L.append(f"| {k} | {int(g.hr_rows_total.sum())} | {g.hr_rows_invalid.sum() / max(g.hr_rows_total.sum(), 1):.3f} | {int(g.hr_ok.sum())}/{len(g)} |")
    L.append("")

    L += ["## 6. Accelerometer range and units", "", "| stream | min x,y,z | max x,y,z | median |v| | max |v| | frac at ≥0.999·max|axis| |",
          "|---|---|---|---|---|---|"]
    for s in IMU_STREAMS:
        arr = np.concatenate([f.streams[s][["x", "y", "z"]].to_numpy() for f in parsed.values() if len(f.streams[s])])
        mag = np.linalg.norm(arr, axis=1)
        fs = np.abs(arr).max()
        sat = (np.abs(arr) >= 0.999 * fs).any(axis=1).mean()
        L.append(f"| {s} | {arr.min(0).round(3).tolist()} | {arr.max(0).round(3).tolist()} | {np.median(mag):.3f} | {mag.max():.3f} | {sat:.5f} (full scale {fs:.3f}) |")
    lying = df[df.original_label == "adl13"]
    L += ["", f"- adl13 (lying on bed) per-file median |acg|: median {lying.acg_mag_median.median():.3f}, p5 {q(lying.acg_mag_median,5):.3f}, p95 {q(lying.acg_mag_median,95):.3f}; "
          f"median |acc|: {lying.acc_mag_median.median():.3f}", "",
          f"Fraction of acg samples beyond the E4 ±2 g (= {E4_LIMIT:.2f} m/s²) range, per activity (median over files):", "",
          "| index | any axis > 2 g | |a| > 2 g | median peak |acg| | median half-max peak width (rows) |", "|---|---|---|---|---|"]
    for k in sorted(df.original_label.unique(), key=lambda k: (k[:3] != "adl", int(re.sub(r"\D", "", k)))):
        g = df[df.original_label == k]
        L.append(f"| {k} | {g.acg_frac_any_axis_gt_2g.median():.3f} | {g.acg_frac_mag_gt_2g.median():.3f} | {g.acg_mag_max.median():.2f} | {g.acg_peak_width_rows_halfmax.median():.0f} |")
    falls = df[df.group == "fall"]
    L += ["", f"- Fall files with peak |acg| > 2 g: {int((falls.acg_mag_max > E4_LIMIT).sum())}/{len(falls)}; "
          f"half-max impact peak width (rows): median {falls.acg_peak_width_rows_halfmax.median():.0f}, "
          f"p10 {q(falls.acg_peak_width_rows_halfmax,10):.0f}, p90 {q(falls.acg_peak_width_rows_halfmax,90):.0f}; "
          f"files with peak width of 1 row: {int((falls.acg_peak_width_rows_halfmax == 1).sum())}", ""]

    L += ["## 7. Exclusions summary", "", "| rule | decision | files |", "|---|---|---|"]
    for (rid, dec), g in excl_df.groupby(["rule_id", "decision"]):
        L.append(f"| {rid} | {dec} | {g.file.nunique()} |")
    L += ["", f"- Files excluded entirely: {int(df.excluded.sum())}; motion_ok: {int(df.motion_ok.sum())}; hr_ok: {int(df.hr_ok.sum())}", ""]
    OUT_TABLES.parent.mkdir(parents=True, exist_ok=True)
    OUT_TABLES.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
