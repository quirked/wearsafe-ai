"""D00c — FallAllD (original FallAllD.pkl) and UP-Fall (wearable CSV) audit. LOOK-ONLY.

Reads only the extracted copies in data/interim/_unzipped/ (made by d00c_extract.py). The banned SMOTE pickle is
never opened (CLAUDE.md §2.3). Pickles are loaded with a restricted unpickler (pandas/numpy only).
Writes reports/D00c_fallalld_upfall_audit_tables.md (refuses to overwrite). No preprocessing of any kind.

Usage (repo root):  python scripts/inspect/d00c_audit.py
"""
import csv
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_pickle_restricted  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FAD = REPO / "data/interim/_unzipped/fallalld"
UPF = REPO / "data/interim/_unzipped/upfall"
OUT = REPO / "reports/D00c_fallalld_upfall_audit_tables.md"

# ---- transcribed from docs/papers/FallAllD-paper.pdf (documentation, not data) ----
STATED_DURATION_S = 20                       # §IV: "The length of each data file is 20 s"
STATED_FS = {"Acc": 238, "Gyr": 238, "Mag": 80, "Bar": 10}   # §III
STATED_ACC_RANGE_G = 8                       # §III: ±8 g
# Fig. 4: explicit IDs 1-44 (paper numbering)
FIG4 = {1: "walking slowly", 2: "walking quickly", 3: "jogging slowly", 4: "jogging quickly",
        5: "climbing stairs up slowly", 6: "climbing stairs up quickly", 7: "climbing stairs down slowly",
        8: "climbing stairs down quickly", 9: "clapping hands", 10: "waving hands", 11: "hand shaking",
        12: "sitting down (low/high chair)", 13: "standing up (low/high chair)",
        14: "fail to stand up after half standing", 15: "lying down on a bed", 16: "rising up from a bed",
        17: "changing position while lying", 18: "stumbling while walking without falling",
        19: "jumping slightly", 20: "jumping strongly", 21: "bending down", 22: "clap hands one time",
        23: "raising hand up", 24: "moving hand down", 25: "moving hand up then down immediately",
        26: "beating a table with your hand", 27: "walking start", 28: "walking stop", 29: "jogging start",
        30: "jogging stop", 31: "clapping hands start", 32: "clapping hands stop", 33: "waving hands start",
        34: "waving hands stop", 35: "climbing stairs up start", 36: "climbing stairs up stop",
        37: "climbing stairs down start", 38: "climbing stairs down stop", 39: "lifts ascending start",
        40: "lifts ascending stop", 41: "lifts descending start", 42: "lifts descending stop",
        43: "being standing in a moving bus/metro", 44: "being sitting in a moving bus/metro"}
FIG4_WRIST_ONLY = {9, 10, 11, 22, 23, 24, 25, 26, 31, 32, 33, 34}   # the 12 hand activities (paper §IV)
# Fig. 8: x-axis labels, left to right (no IDs printed in the paper)
FIG8_ADL = ["Start clap hands", "Clap hands", "Stop clap hands", "Clap hands 1 time", "Start wave hands",
            "wave hands", "Stop wave hands", "Raising hand up", "Moving hand down", "Move hand up then down",
            "Hand shaking", "Beating a table", "Sitting down", "Standing up", "Fail to stand up", "Lying down",
            "Turning while lying", "Rising up", "Start walking", "Walking slowly", "Stop walking",
            "Walking quickly", "Stumbling", "Jogging slowly", "Jogging quickly", "Jumping slightly",
            "Jumping strongly", "Bending down", "Start going upstairs", "Going upstairs", "Stop going upstairs",
            "Start going downstairs", "Going downstairs", "Stop going downstairs", "Upstairs quickly",
            "Downstairs quickly", "Start ascending, lifts", "Stop ascending, lifts", "Start descending, lifts",
            "Stop descending, lifts", "Standing, moving bus", "Sitting, moving bus", "Start jogging",
            "Stop jogging"]
FIG8_FALL = ["Fall F, walking, trip", "Fall F, walking, trip, rec", "Fall F, walking, slip",
             "Fall F, walking, slip, rec", "Fall F, walking, slip, rot", "Fall F, walking, slip, rot, rec",
             "Fall B, walking, slip", "Fall B, walking, slip, rec", "Fall B, walking, slip, rot",
             "Fall B, walking, slip, rot, rec", "Fall F, walking, syncope", "Fall B, walking, syncope",
             "Fall L, walking, syncope", "Fall, syncope, attempt protection", "Fall F, attempt sit/lye down",
             "Fall F, attempt sit/lye down, rec", "Fall B, attempt sit/lye down",
             "Fall B, attempt sit/lye down, rec", "Fall L, attempt sit/lye down",
             "Fall L, attempt sit/lye down, rec", "Fall F, jog, trip", "Fall F, jog, trip, rec",
             "Fall F, jog, slip", "Fall F, jog, slip, rec", "Fall F, jog, slip, rot",
             "Fall F, jog, slip, rot, rec", "Fall L, bed", "Fall L, bed, rec", "Fall F, chair, syncope",
             "Fall B, chair, syncope", "Fall L, chair, syncope", "Fall F, syncope", "Fall B, syncope",
             "Fall L, syncope", "Fall, syncope, ending sitting"]
FIG8_WRIST = {"falls": 523, "adls": 1992}   # Fig. 8 legends (wrist); also waist 466/1332, neck 733/1559
FIG8_ALL = {"Waist": (466, 1332), "Neck": (733, 1559), "Wrist": (523, 1992)}

# ---- transcribed from docs/papers/upfall-paper.pdf ----
UP_ACTIVITIES = {1: ("Falling forward using hands", 10, "fall"), 2: ("Falling forward using knees", 10, "fall"),
                 3: ("Falling backwards", 10, "fall"), 4: ("Falling sideward", 10, "fall"),
                 5: ("Falling sitting in empty chair", 10, "fall"), 6: ("Walking", 60, "adl"),
                 7: ("Standing", 60, "adl"), 8: ("Sitting", 60, "adl"), 9: ("Picking up an object", 10, "adl"),
                 10: ("Jumping", 30, "adl"), 11: ("Laying", 60, "adl")}           # Table 5
UP_MISSING_TABLE7 = [(2, "5", "all", 6), (5, "all", "all", 2), (6, "10", "2", 14), (8, "11", "2, 3", "all"),
                     (9, "all", "all", 2)]                                          # Table 7 (subject, act, trial, device)
G = 9.80665


def md(df, floatfmt=None):
    df = df.copy()
    if floatfmt:
        for c in df.select_dtypes("float").columns:
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if (isinstance(v, float) and pd.isna(v)) else str(v) for v in r) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join(out)


def norm(s):
    s = s.lower().replace(".", "").replace("->", "then").replace("1 time", "one time")
    return re.sub(r"[\s,]+", " ", s).strip()


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def fallalld(S):
    S.append("# Part A — FallAllD (original FallAllD.pkl only)\n")
    man = pd.read_csv(REPO / "metadata/fallalld_file_manifest.csv")
    S.append("## A1. Zip members [verified in files]\n")
    S.append(md(man[["member", "size_bytes", "compressed_bytes", "crc32", "status", "sha256_match", "crc_match"]]) + "\n")

    info = load_pickle_restricted(FAD / "activity_info.pkl")
    df = load_pickle_restricted(FAD / "FallAllD.pkl")
    S.append("## A2. Structure [verified in files]\n")
    rows = [{"column": c, "pandas dtype": str(df[c].dtype),
             "element": type(df[c].iloc[0]).__name__,
             "element shapes": ", ".join(f"{k}×{n}" for k, n in df[c].map(
                 lambda v: str(getattr(v, "shape", "scalar"))).value_counts().items()),
             "element dtype": ", ".join(df[c].map(lambda v: str(getattr(v, "dtype", type(v).__name__)))
                                         .value_counts().index)} for c in df.columns]
    S.append(md(pd.DataFrame(rows)) + "\n")
    key = ["SubjectID", "Device", "ActivityID", "TrialNo"]
    S.append(f"- records: {len(df)}; records × 4 sensors = {len(df) * 4} (paper: 26 420 files)\n"
             f"- duplicate (SubjectID, Device, ActivityID, TrialNo) keys: {int(df.duplicated(key).sum())}\n"
             f"- subjects: {sorted(df.SubjectID.unique().tolist())}\n"
             f"- records per device: {df.Device.value_counts().to_dict()}\n"
             f"- TrialNo range: {df.TrialNo.min()}–{df.TrialNo.max()}\n")
    lens = []
    for c, fs in STATED_FS.items():
        n = df[c].map(len)
        lens.append({"sensor": c, "stated Hz": fs, "samples per record (unique)": sorted(n.unique().tolist()),
                     "samples ÷ 20 s": sorted((n / STATED_DURATION_S).unique().tolist()),
                     "records": len(n), "axes": sorted(df[c].map(lambda a: a.shape[1]).unique().tolist())})
    S.append("## A3. Sampling rate = samples ÷ stated 20 s duration (no timestamps in the file)\n")
    S.append(md(pd.DataFrame(lens)) + "\n")

    is_fall = df.ActivityID >= 101
    S.append("## A4. Falls/ADLs per device vs paper Fig. 8 legend counts\n")
    rows = []
    for dev, (pf, pa) in FIG8_ALL.items():
        d = df[df.Device == dev]
        rows.append({"device": dev, "fall records (ID ≥ 101)": int((d.ActivityID >= 101).sum()), "paper falls": pf,
                     "ADL records (ID ≤ 44)": int((d.ActivityID <= 44).sum()), "paper ADLs": pa,
                     "subjects with ADLs": d[d.ActivityID <= 44].SubjectID.nunique(),
                     "subjects with falls": d[d.ActivityID >= 101].SubjectID.nunique()})
    S.append(md(pd.DataFrame(rows)) + "\n")
    S.append("Paper §IV: wrist — 13 subjects simulated ADLs, 10 simulated falls; waist/neck — 14 ADLs, 12 falls.\n")

    S.append("## A5. Activity ID scheme: which numbering does the data use?\n")
    dev_ids = df.groupby("ActivityID")["Device"].agg(lambda s: sorted(set(s)))
    wrist_only = sorted(i for i, d in dev_ids.items() if d == ["Wrist"])
    S.append(f"- IDs present ONLY for the wrist device in the data: {wrist_only}\n"
             f"- Paper Fig. 4 numbering would put the 12 wrist-only hand activities at {sorted(FIG4_WRIST_ONLY)}\n"
             f"- activity_info.pkl puts hand activities at 1–12: "
             f"{'MATCHES the data' if wrist_only == list(range(1, 13)) else 'does NOT match'}\n")
    rows = []
    for k in range(1, 45):
        rows.append({"ID": k, "activity_info.pkl": info[k], "Fig. 8 label (position k)": FIG8_ADL[k - 1],
                     "names agree": norm(info[k]) == norm(FIG8_ADL[k - 1]),
                     "Fig. 4 name for ID k": FIG4[k], "devices in data": "/".join(dev_ids.get(k, []))})
    for j, k in enumerate(range(101, 136)):
        rows.append({"ID": k, "activity_info.pkl": info[k], "Fig. 8 label (position k)": FIG8_FALL[j],
                     "names agree": norm(info[k]) == norm(FIG8_FALL[j]), "Fig. 4 name for ID k": "(falls not numbered)",
                     "devices in data": "/".join(dev_ids.get(k, []))})
    t = pd.DataFrame(rows)
    S.append(f"activity_info.pkl has {len(info)} keys; {sum(v != 'Unknown activity' for v in info.values())} named; "
             f"keys 45–100 are 'Unknown activity' and IDs 45–100 occur in the data: "
             f"{sorted(set(df.ActivityID) & set(range(45, 101)))}.\n")
    S.append(f"Exact (normalised) name agreement with Fig. 8: {int(t['names agree'].sum())}/{len(t)}; "
             "rows marked False are listed in the text report.\n")
    S.append(md(t) + "\n")

    w = df[df.Device == "Wrist"].reset_index(drop=True)
    wf = w.ActivityID >= 101
    S.append("## A6. Wrist records per subject [verified in files]\n")
    t = w.assign(kind=np.where(wf, "fall", "adl")).groupby(["SubjectID", "kind"]).size().unstack(fill_value=0)
    t["total"] = t.sum(1)
    S.append(md(t.reset_index()) + "\n")
    S.append("Subjects absent from the wrist device: "
             f"{sorted(set(range(1, 16)) - set(w.SubjectID))}\n")
    S.append("## A7. Wrist records per activity [verified in files; names from activity_info.pkl]\n")
    t = w.groupby("ActivityID").agg(records=("TrialNo", "size"), subjects=("SubjectID", "nunique"),
                                    max_trial=("TrialNo", "max")).reset_index()
    t.insert(1, "name", t.ActivityID.map(info))
    t.insert(2, "kind", np.where(t.ActivityID >= 101, "fall", "ADL"))
    S.append(md(t) + "\n")

    S.append("## A8. Units and range (wrist ACC)\n")
    acc = np.concatenate(w.Acc.tolist()).astype(np.int64)
    S.append(f"- stored as int16 counts [verified in files]; per-axis min {acc.min(0).tolist()}, max {acc.max(0).tolist()}\n"
             f"- samples at the int16 rails (±32767/−32768) on any axis: {int((np.abs(acc) >= 32767).any(1).sum())}; "
             f"with |axis| ≥ 32000 counts: {int((np.abs(acc) >= 32000).any(1).sum())} of {len(acc)}\n")
    quiet = []
    for dev, d in df.groupby("Device"):
        for a in d.Acc:
            m = np.sqrt((a.astype(float) ** 2).sum(1))
            s = pd.Series(m).rolling(238).std().to_numpy()
            if np.nanmin(s) < 20:
                i = int(np.nanargmin(s))
                quiet.append({"device": dev, "g_counts": float(np.median(m[i - 237:i + 1]))})
    q = pd.DataFrame(quiet).groupby("device")["g_counts"].describe(percentiles=[0.25, 0.5, 0.75]).reset_index()
    S.append("Gravity check: median |acc| (counts) in the quietest 1 s of each record whose rolling std < 20 counts "
             "[verified in files]:\n\n" + md(q, ".1f") + "\n")
    S.append(f"Candidate factor from the paper's ±{STATED_ACC_RANGE_G} g full scale on int16: 32768/8 = 4096 counts/g "
             "[inferred]; the paper states no conversion factor [unknown]. Below, g = counts/4096 [inferred].\n")
    rows = []
    for name, d in (("falls (ID ≥ 101)", w[wf]), ("ADLs (ID ≤ 44)", w[~wf]), ("all wrist", w)):
        a = np.concatenate(d.Acc.tolist()).astype(float) / 4096
        mag = np.sqrt((a ** 2).sum(1))
        peaks = d.Acc.map(lambda x: np.sqrt(((x.astype(float) / 4096) ** 2).sum(1)).max())
        rows.append({"group": name, "records": len(d), "samples": len(a),
                     "% samples |a| > 2 g": round(100 * (mag > 2).mean(), 3),
                     "% samples any axis beyond ±2 g": round(100 * (np.abs(a) >= 2).any(1).mean(), 3),
                     "% records peak |a| > 2 g": round(100 * (peaks > 2).mean(), 1),
                     "median record peak (g)": round(float(peaks.median()), 2),
                     "max |axis| (g)": round(float(np.abs(a).max()), 3),
                     "max |a| (m/s²)": round(float(mag.max() * G), 1)})
    S.append(md(pd.DataFrame(rows)) + "\n")

    S.append("## A9. Duplicates (exact content hashes) [verified in files]\n")
    rows = []
    for c in ("Acc", "Gyr", "Mag", "Bar"):
        h = df[c].map(sha)
        g = df.assign(h=h).groupby("h")
        dup = [grp for _, grp in g if len(grp) > 1]
        cross = sum(grp.SubjectID.nunique() > 1 for grp in dup)
        rows.append({"sensor": c, "records": len(df), "unique": h.nunique(), "duplicate groups": len(dup),
                     "records in duplicate groups": int(sum(len(x) for x in dup)),
                     "groups spanning >1 subject": int(cross),
                     "groups spanning >1 device": int(sum(grp.Device.nunique() > 1 for grp in dup))})
    S.append(md(pd.DataFrame(rows)) + "\n")
    h1 = df.Acc.map(lambda a: sha(a[:238]))
    d1 = df.assign(h=h1)[df.assign(h=h1).duplicated("h", keep=False)]
    S.append(f"Partial check: records sharing an identical FIRST 1 s of ACC: {len(d1)}"
             f" (subjects involved: {sorted(d1.SubjectID.unique().tolist())[:20]})\n")
    if len(d1):
        S.append(md(d1[key].sort_values(key).head(40)) + "\n")
    allh = df.assign(h=df.Acc.map(sha))
    groups = [g[key] for _, g in allh.groupby("h") if len(g) > 1]
    if groups:
        S.append("Exact ACC duplicate groups (first 30):\n\n" + md(pd.concat(groups[:30])) + "\n")

    S.append("## A10. Where is the impact? Time of peak |acc| in wrist fall records [verified in files]\n")
    tpk = w[wf].Acc.map(lambda a: int(np.argmax((a.astype(float) ** 2).sum(1))) / 238)
    tpa = w[~wf].Acc.map(lambda a: int(np.argmax((a.astype(float) ** 2).sum(1))) / 238)
    qs = [0.05, 0.25, 0.5, 0.75, 0.95]
    S.append(md(pd.DataFrame([
        {"group": "wrist falls", "n": len(tpk), **{f"p{int(q * 100)} (s)": round(float(tpk.quantile(q)), 2) for q in qs},
         "% in 8–12 s": round(100 * tpk.between(8, 12).mean(), 1)},
        {"group": "wrist ADLs", "n": len(tpa), **{f"p{int(q * 100)} (s)": round(float(tpa.quantile(q)), 2) for q in qs},
         "% in 8–12 s": round(100 * tpa.between(8, 12).mean(), 1)}])) + "\n")
    hist = np.histogram(tpk, bins=np.arange(0, 21, 1))[0]
    S.append("Histogram of wrist-fall peak time (1 s bins, 0–20 s): " + ", ".join(map(str, hist.tolist())) + "\n")
    S.append("No event-time field exists in the file [verified in files: columns are only those in A2]. "
             "Paper §IV: falls and transient ADLs are 'centered around the transition moment' [stated in paper].\n")
    return {"records": len(df), "wrist": len(w), "wrist_falls": int(wf.sum()), "wrist_adls": int((~wf).sum()),
            "wrist_subjects": w.SubjectID.nunique()}


def upfall(S):
    S.append("# Part B — UP-Fall (wearable sensor data only)\n")
    man = pd.read_csv(REPO / "metadata/upfall_file_manifest.csv")
    S.append("## B1. Zip members [verified in files]\n")
    S.append(md(man[["member", "size_bytes", "compressed_bytes", "crc32", "status", "sha256_match", "crc_match"]]) + "\n")
    feat = sorted(UPF.glob("Subject*Features*.csv"))
    for f in feat:
        h = pd.read_csv(f, nrows=3, header=None)
        n = sum(1 for _ in open(f))
        S.append(f"- `{f.name}`: {h.shape[1]} columns, {n} lines (feature windows; only Subject 1 / Activity 1 / "
                 "Trial 1 is present — a sample, not the feature dataset)\n")

    path = UPF / "up-fail-complete-dataset.csv"
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        top, sub = next(r), next(r)
    names, cur = [], ""
    for a, b in zip(top, sub):
        cur = a or cur
        names.append(f"{cur}|{b}" if b else cur)
    df = pd.read_csv(path, skiprows=2, header=None, names=names, low_memory=False)
    S.append("## B2. Complete CSV structure [verified in files]\n")
    S.append(f"- rows (samples): {len(df)}; columns: {len(names)} (paper: 296,364 samples; 1 timestamp + 42 signals "
             "+ subject/activity/trial)\n")
    S.append("Columns (header row 1 | header row 2): " + "; ".join(f"`{n}`" for n in names) + "\n")
    df["ts"] = pd.to_datetime(df["TimeStamps"], format="ISO8601", errors="coerce")
    S.append(f"- unparseable timestamps: {int(df.ts.isna().sum())}\n")
    for c in ("Subject", "Activity", "Trial", "Tag"):
        S.append(f"- `{c}` values: {sorted(pd.unique(df[c]).tolist())}\n")
    key = ["Subject", "Activity", "Trial"]
    present = df.groupby(key).size()
    S.append(f"- (subject, activity, trial) combinations present: {len(present)} of 17 × 11 × 3 = 561\n")
    allc = pd.MultiIndex.from_product([range(1, 18), range(1, 12), range(1, 4)], names=key)
    miss = [k for k in allc if k not in present.index]
    S.append(f"- missing combinations: {miss}\n")
    S.append(f"- paper Table 7 missing values (subject, activity, trial, device): {UP_MISSING_TABLE7} "
             "(device 5 = wrist IMU is not listed) [stated in paper]\n")

    S.append("## B3. Activity column vs per-sample Tag [verified in files]\n")
    t = df.groupby(["Activity", "Tag"]).size().unstack(fill_value=0)
    t.insert(0, "name", [UP_ACTIVITIES[a][0] for a in t.index])
    S.append(md(t.reset_index()) + "\n")

    S.append("## B4. Trial durations vs paper Table 5 [verified in files]\n")
    g = df.groupby(key)
    dur = (g.ts.max() - g.ts.min()).dt.total_seconds().rename("dur").reset_index()
    rows = []
    for a, d in dur.groupby("Activity"):
        rows.append({"Activity": a, "name": UP_ACTIVITIES[a][0], "stated s": UP_ACTIVITIES[a][1], "trials": len(d),
                     "min s": round(d.dur.min(), 2), "median s": round(d.dur.median(), 2), "max s": round(d.dur.max(), 2)})
    S.append(md(pd.DataFrame(rows)) + "\n")

    S.append("## B5. Sampling rate from timestamps, per trial [verified in files]\n")
    rows = []
    for k, d in g:
        dt = np.diff(d.ts.values.astype("datetime64[ns]").astype(np.int64)) / 1e9
        rows.append({"Subject": k[0], "Activity": k[1], "Trial": k[2], "n": len(d),
                     "median_dt": np.median(dt), "rate_hz": 1 / np.median(dt), "n_neg_dt": int((dt < 0).sum()),
                     "n_zero_dt": int((dt == 0).sum()), "n_gap_gt_2x": int((dt > 2 * np.median(dt)).sum()),
                     "max_dt": dt.max(), "p5_dt": np.percentile(dt, 5), "p95_dt": np.percentile(dt, 95)})
    rt = pd.DataFrame(rows)
    S.append(f"Per-trial median rate (Hz): min {rt.rate_hz.min():.2f}, p5 {rt.rate_hz.quantile(.05):.2f}, median "
             f"{rt.rate_hz.median():.2f}, p95 {rt.rate_hz.quantile(.95):.2f}, max {rt.rate_hz.max():.2f}; "
             f"IQR/median {(rt.rate_hz.quantile(.75) - rt.rate_hz.quantile(.25)) / rt.rate_hz.median():.3f}\n")
    alldt = np.concatenate([np.diff(d.ts.values.astype("datetime64[ns]").astype(np.int64)) / 1e9 for _, d in g])
    S.append(f"All within-trial steps: n {len(alldt)}, p1 {np.percentile(alldt, 1):.4f} s, p5 {np.percentile(alldt, 5):.4f}, "
             f"median {np.median(alldt):.4f}, p95 {np.percentile(alldt, 95):.4f}, p99 {np.percentile(alldt, 99):.4f}, "
             f"max {alldt.max():.3f} s; negative {int((alldt < 0).sum())}, zero {int((alldt == 0).sum())}; "
             f"steps > 2× trial median: {int(rt.n_gap_gt_2x.sum())}\n")
    S.append("Trials with the most irregular steps (top 15 by steps > 2× median):\n\n"
             + md(rt.sort_values("n_gap_gt_2x", ascending=False).head(15), ".4f") + "\n")

    S.append("## B6. Wrist sensor columns, units and range [verified in files]\n")
    wcols = [n for n in names if n.startswith("Wrist")]
    S.append("Wrist columns: " + ", ".join(f"`{c}`" for c in wcols) + "\n")
    ax = [c for c in wcols if c.startswith("WristAccelerometer")]
    gy = [c for c in wcols if c.startswith("WristAngularVelocity")]
    rows = []
    for c in wcols:
        v = pd.to_numeric(df[c], errors="coerce")
        rows.append({"column": c, "NaN": int(v.isna().sum()), "min": v.min(), "max": v.max(),
                     "n at min": int((v == v.min()).sum()), "n at max": int((v == v.max()).sum()),
                     "distinct values": v.nunique()})
    S.append(md(pd.DataFrame(rows), ".3f") + "\n")
    a = df[ax].apply(pd.to_numeric, errors="coerce").to_numpy()
    mag = np.sqrt((a ** 2).sum(1))
    still = df.Activity.isin([7, 8, 11]).to_numpy()      # standing, sitting, laying
    S.append(f"Gravity check: median |acc| during standing/sitting/laying = {np.nanmedian(mag[still]):.3f} "
             f"(IQR {np.nanpercentile(mag[still], 25):.3f}–{np.nanpercentile(mag[still], 75):.3f}); "
             "≈ 1 means the stored unit is g [inferred]. Range of the MetaSensor accelerometer: not stated in "
             "the paper [unknown].\n")
    fallmask = df.Activity.between(1, 5).to_numpy()
    rows = []
    for name, m in (("falls (Activity 1–5)", fallmask), ("ADLs (Activity 6–11)", ~fallmask), ("all", np.ones(len(df), bool))):
        tr = df[m].groupby(key)
        pk = tr.apply(lambda d: np.sqrt((d[ax].apply(pd.to_numeric, errors="coerce") ** 2).sum(1)).max(),
                      include_groups=False)
        rows.append({"group": name, "samples": int(m.sum()), "trials": len(pk),
                     "% samples |a| > 2 g": round(100 * np.nanmean(mag[m] > 2), 3),
                     "% samples any axis beyond ±2 g": round(100 * np.nanmean((np.abs(a[m]) >= 2).any(1)), 3),
                     "% trials peak |a| > 2 g": round(100 * (pk > 2).mean(), 1),
                     "median trial peak (g)": round(float(pk.median()), 2),
                     "max |axis| (g)": round(float(np.nanmax(np.abs(a[m]))), 3)})
    S.append(md(pd.DataFrame(rows)) + "\n")

    S.append("## B7. Duplicates and missing data [verified in files]\n")
    S.append(f"- fully duplicated rows: {int(df[names].duplicated().sum())}; duplicated timestamps: "
             f"{int(df.TimeStamps.duplicated().sum())}\n")
    nan = df[names].isna().sum()
    S.append("- columns with NaN: " + (", ".join(f"`{k}`: {v}" for k, v in nan[nan > 0].items()) or "none") + "\n")
    wh = g.apply(lambda d: sha(d[ax + gy].to_numpy(dtype=float)), include_groups=False)
    dupg = wh[wh.duplicated(keep=False)]
    S.append(f"- trials with an identical wrist ACC+gyro series to another trial: {len(dupg)} "
             f"{dupg.index.tolist()[:20]}\n")
    zero = g.apply(lambda d: bool((d[ax].apply(pd.to_numeric, errors='coerce').abs().sum(1) == 0).all()),
                   include_groups=False)
    S.append(f"- trials whose wrist ACC is all zeros: {int(zero.sum())} {zero[zero].index.tolist()[:20]}\n")
    const = g.apply(lambda d: int((d[ax].diff().abs().sum(1) == 0).sum()), include_groups=False)
    S.append(f"- wrist ACC samples identical to the previous sample (held values), all trials: {int(const.sum())} of "
             f"{len(df)} ({100 * const.sum() / len(df):.2f}%)\n")
    return {"rows": len(df), "trials": len(present), "rate_median": float(rt.rate_hz.median())}


def main():
    if OUT.exists():
        raise FileExistsError(f"{OUT} exists; refusing to overwrite")
    S = ["# D00c tables — auto-generated by scripts/inspect/d00c_audit.py (look-only)\n",
         "Tags: [verified in files] unless stated. Paper transcriptions are constants at the top of the script.\n"]
    fallalld(S)
    upfall(S)
    OUT.write_text("\n".join(S))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
