"""D00c follow-up checks (look-only), APPENDED as Part C to reports/D00c_fallalld_upfall_audit_tables.md.

Appends only (existing content untouched); refuses if Part C is already present.
Usage (repo root):  python scripts/inspect/d00c_followup.py
"""
import csv
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_pickle_restricted  # noqa: E402
from d00c_audit import UP_ACTIVITIES, md  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports/D00c_fallalld_upfall_audit_tables.md"
MARK = "# Part C — follow-up checks"


def main():
    if MARK in OUT.read_text():
        raise RuntimeError("Part C already present; refusing to append twice")
    S = ["\n" + MARK + " (appended by scripts/inspect/d00c_followup.py)\n"]
    df = load_pickle_restricted(REPO / "data/interim/_unzipped/fallalld/FallAllD.pkl")
    info = load_pickle_restricted(REPO / "data/interim/_unzipped/fallalld/activity_info.pkl")
    h = df.Mag.map(lambda a: hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest())
    d = df[h.duplicated(keep=False)][["SubjectID", "Device", "ActivityID", "TrialNo"]]
    d = d.assign(name=d.ActivityID.map(info))
    S.append("## C1. FallAllD records with an identical magnetometer block\n\n" + md(d) + "\n")
    w = df[df.Device == "Wrist"]
    t = w.groupby("SubjectID").TrialNo.max()
    S.append("## C2. FallAllD wrist: max TrialNo per subject (trials per activity are not fixed)\n\n"
             + md(w.groupby(["ActivityID"]).TrialNo.agg(["min", "median", "max"]).reset_index()
                  .assign(name=lambda x: x.ActivityID.map(info)).head(0)) + "\n"
             + "Distribution of records per (subject, activity) on the wrist: "
             + str(w.groupby(["SubjectID", "ActivityID"]).size().value_counts().sort_index().to_dict()) + "\n")

    path = REPO / "data/interim/_unzipped/upfall/up-fail-complete-dataset.csv"
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        top, sub = next(r), next(r)
    names, cur = [], ""
    for a, b in zip(top, sub):
        cur = a or cur
        names.append(f"{cur}|{b}" if b else cur)
    u = pd.read_csv(path, skiprows=2, header=None, names=names, low_memory=False)
    u["ts"] = pd.to_datetime(u["TimeStamps"], format="ISO8601")
    key = ["Subject", "Activity", "Trial"]
    devs = ["Ankle", "RightPocket", "Belt", "Neck", "Wrist"]
    S.append("## C3. UP-Fall held (repeated) samples per wearable: rows where all 3 ACC axes equal the previous row "
             "of the same trial [verified in files]\n")
    rows = []
    for dv in devs:
        ax = [c for c in names if c.startswith(f"{dv}Accelerometer")]
        gy = [c for c in names if c.startswith(f"{dv}AngularVelocity")]
        same_a = u.groupby(key)[ax].diff().abs().sum(1).eq(0) & u.groupby(key)[ax[0]].shift().notna()
        same_g = u.groupby(key)[gy].diff().abs().sum(1).eq(0) & u.groupby(key)[gy[0]].shift().notna()
        rows.append({"device": dv, "% rows ACC held": round(100 * same_a.mean(), 2),
                     "% rows gyro held": round(100 * same_g.mean(), 2),
                     "% rows ACC and gyro both held": round(100 * (same_a & same_g).mean(), 2)})
    S.append(md(pd.DataFrame(rows)) + "\n")
    ax = [c for c in names if c.startswith("WristAccelerometer")]
    held = u.groupby(key)[ax].diff().abs().sum(1).eq(0) & u.groupby(key)[ax[0]].shift().notna()
    u["held"] = held
    g = u.groupby(key)
    eff = pd.DataFrame({"n": g.size(), "new": g.held.apply(lambda s: int((~s).sum())),
                        "dur": (g.ts.max() - g.ts.min()).dt.total_seconds()})
    eff["row_rate"] = (eff.n - 1) / eff.dur
    eff["new_value_rate"] = (eff.new - 1) / eff.dur
    S.append("## C4. UP-Fall wrist: row rate vs rate of NEW (non-repeated) ACC values per trial [verified in files]\n")
    q = eff[["row_rate", "new_value_rate"]].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).T.reset_index()
    S.append(md(q, ".2f") + "\n")
    t = u.assign(kind=np.where(u.Activity <= 5, "fall", "adl")).groupby("Activity").held.mean().mul(100).round(2)
    S.append("Wrist ACC held (%) by activity: " + ", ".join(f"{a} {UP_ACTIVITIES[a][0]}: {v}" for a, v in t.items())
             + "\n")
    runs = []
    for _, d in g:
        x = d.held.to_numpy()
        n = 0
        for v in x:
            if v:
                n += 1
            elif n:
                runs.append(n)
                n = 0
        if n:
            runs.append(n)
    runs = np.array(runs)
    S.append(f"Held-run lengths (consecutive repeated rows): n {len(runs)}, median {np.median(runs):.0f}, "
             f"p95 {np.percentile(runs, 95):.0f}, max {runs.max()}; runs ≥ 5 rows: {int((runs >= 5).sum())}\n")
    S.append("## C5. UP-Fall Tag 20 [verified in files; meaning not documented in the paper → unknown]\n")
    t20 = u[u.Tag == 20].groupby(key).size().rename("rows").reset_index()
    S.append(md(t20) + "\n")
    S.append("## C6. UP-Fall wrist fall trials: time of peak |acc| from trial start, and peak vs Tag [verified in files]\n")
    rows = []
    for k, d in u[u.Activity <= 5].groupby(key):
        m = np.sqrt((d[ax].to_numpy(float) ** 2).sum(1))
        i = int(np.argmax(m))
        rows.append({"t_peak_s": (d.ts.iloc[i] - d.ts.iloc[0]).total_seconds(), "tag_at_peak": int(d.Tag.iloc[i])})
    pk = pd.DataFrame(rows)
    S.append("Peak time quantiles (s): " + ", ".join(f"p{int(p*100)} {pk.t_peak_s.quantile(p):.2f}"
                                                    for p in (0.05, 0.25, 0.5, 0.75, 0.95)) + "\n")
    S.append("Tag at the peak sample: " + str(pk.tag_at_peak.value_counts().to_dict()) + "\n")
    with open(OUT, "a") as f:
        f.write("\n".join(S))
    print("appended Part C")


if __name__ == "__main__":
    main()
