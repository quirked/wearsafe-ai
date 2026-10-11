"""D00a: read-only inspection of PPG-DaLiA (data/raw/ppg_dalia/PPG_FieldStudy).

Loads ONE subject pickle at a time. For every subject prints:
  - pickle key tree (shapes, dtypes) and how the pickle had to be loaded
  - per-signal length, implied duration at the documented rate, value stats, NaNs
  - HR ground-truth ('label') count vs. the count implied by 8 s / 2 s windows
  - activity (4 Hz) seconds per code, compared with SX_activity.csv segments
  - SX_quest.csv, raw E4 zip headers (read in memory) and RespiBAN .h5 attributes
Ends with compact summary tables.

Usage (from repo root):  python scripts/inspect/inspect_ppg_dalia.py [S1 S2 ...]
"""
import gc
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import key_tree, load_pickle, read_e4_zip, stats  # noqa: E402

ROOT = Path("data/raw/ppg_dalia/PPG_FieldStudy")
# Documented sampling rates (PPG_FieldStudy_readme.pdf)
FS = {"chest": 700, ("wrist", "ACC"): 32, ("wrist", "BVP"): 64,
      ("wrist", "EDA"): 4, ("wrist", "TEMP"): 4, "activity": 4}
ACTIVITY_DOC = {0: "transient", 1: "sitting", 2: "stairs", 3: "table soccer", 4: "cycling",
                5: "driving", 6: "lunch", 7: "walking", 8: "working"}


def read_hash_csv(path):
    """SX_activity.csv / SX_quest.csv: lines '# NAME, value'."""
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip().lstrip("#").strip()
        if not line:
            continue
        k, v = [x.strip() for x in line.split(",", 1)]
        rows.append((k, v))
    return rows


def fs_of(loc, name):
    return FS["chest"] if loc == "chest" else FS[(loc, name)]


def inspect_subject(sid, summary):
    d = ROOT / sid
    print("=" * 78)
    print(f"SUBJECT {sid}")
    print("=" * 78)
    obj, how = load_pickle(d / f"{sid}.pkl")
    print(f"pickle loaded with: {how}")
    print("Key tree:")
    for line in key_tree(obj):
        print("  " + line)

    row = {"sid": sid, "load": how}
    durations = {}
    print("\nSignals (duration = n_samples / documented fs):")
    for loc in ("wrist", "chest"):
        for name, arr in obj["signal"][loc].items():
            fs = fs_of(loc, name)
            dur = arr.shape[0] / fs
            durations[f"{loc}/{name}"] = dur
            st = stats(arr)
            print(f"  {loc}/{name}: shape={arr.shape} dtype={arr.dtype} fs={fs} dur={dur:.2f}s "
                  f"min={st['min']} max={st['max']} mean={st['mean']} NaN={st['nan']}")
            row[f"{loc}/{name}"] = st
    act = np.asarray(obj["activity"]).ravel()
    durations["activity"] = act.shape[0] / FS["activity"]
    row["durations"] = durations
    spread = max(durations.values()) - min(durations.values())
    print(f"  duration spread across all signals: {spread:.3f}s")
    # Unit check: raw E4 ACC.csv is integer counts of 1/64 g. If pkl ACC * 64 is integer-valued,
    # the pkl stores the raw counts divided by 64, i.e. units of g.
    acc64 = obj["signal"]["wrist"]["ACC"] * 64
    frac_int = float(np.mean(np.isclose(acc64, np.round(acc64), atol=1e-6)))
    print(f"  wrist/ACC * 64 integer-valued fraction: {frac_int:.6f}")
    row["acc_x64_int_frac"] = frac_int

    # HR ground truth
    hr = np.asarray(obj["label"]).ravel()
    dur_ref = durations["chest/ECG"]
    expected = int(np.floor((dur_ref - 8) / 2)) + 1
    st = stats(hr)
    print(f"\nHR label: n={hr.shape[0]} (expected floor((dur-8)/2)+1 = {expected} from ECG duration) "
          f"min={st['min']} max={st['max']} mean={st['mean']} NaN={st['nan']}")
    row["hr"] = dict(n=int(hr.shape[0]), expected=expected, **st)

    rp = np.asarray(obj["rpeaks"]).ravel()
    print(f"rpeaks: n={rp.shape[0]} first={rp[:3].tolist()} last={rp[-1]} "
          f"(last/700={rp[-1] / 700:.1f}s); monotonic={bool(np.all(np.diff(rp) > 0))}")
    bad = np.flatnonzero(np.diff(rp) <= 0)
    if len(bad):
        print(f"  rpeaks non-increasing steps: {len(bad)} at index {bad[:10].tolist()} "
              f"values {[(int(rp[i]), int(rp[i + 1])) for i in bad[:5]]}")

    # Activity
    codes, counts = np.unique(act, return_counts=True)
    print(f"\nactivity: n={act.shape[0]} dtype={act.dtype} codes={codes.tolist()}")
    act_secs = {int(c): n / FS["activity"] for c, n in zip(codes, counts)}
    for c, s in act_secs.items():
        print(f"  code {c} ({ACTIVITY_DOC.get(c, '??')}): {s:.0f}s = {s / 60:.1f} min")
    row["activity_secs"] = act_secs

    # Activity CSV: segment durations, end of last segment = activity-signal duration
    segs = [(k, float(v)) for k, v in read_hash_csv(d / f"{sid}_activity.csv") if k != "SUBJECT_ID"]
    print(f"\n{sid}_activity.csv segments (start s -> end s):")
    csv_secs = {}
    for i, (name, t0) in enumerate(segs):
        t1 = segs[i + 1][1] if i + 1 < len(segs) else durations["activity"]
        csv_secs[name] = csv_secs.get(name, 0) + (t1 - t0)
        print(f"  {name:15s} {t0:8.0f} -> {t1:8.0f}  ({t1 - t0:6.0f}s)")
    row["csv_secs"] = csv_secs
    # Which pkl code does each CSV segment correspond to? Read pkl activity at segment midpoint.
    seg_codes = {}
    for i, (name, t0) in enumerate(segs):
        t1 = segs[i + 1][1] if i + 1 < len(segs) else durations["activity"]
        mid = int(((t0 + t1) / 2) * FS["activity"])
        if mid < act.shape[0]:
            seg_codes.setdefault(name, set()).add(int(act[mid]))
    print("  CSV name -> pkl activity code at segment midpoint:",
          {k: sorted(v) for k, v in seg_codes.items()})
    row["seg_codes"] = {k: sorted(v) for k, v in seg_codes.items()}

    print("\nquestionnaire (pkl):", obj.get("questionnaire"))
    print("quest.csv:", read_hash_csv(d / f"{sid}_quest.csv"))
    print("subject field:", obj.get("subject"))
    del obj
    gc.collect()

    # Raw E4 zip (in memory)
    e4 = read_e4_zip(d / f"{sid}_E4.zip")
    print("\nRaw E4 zip:")
    for k in ("ACC", "BVP", "EDA", "TEMP", "HR"):
        e = e4[k]
        dur = e["n_rows"] / e["fs"]
        print(f"  {k}.csv: start_unix={e['start_unix']:.0f} fs={e['fs']} rows={e['n_rows']} "
              f"cols={e['ncols']} dur={dur:.1f}s  min={e['data'].min(0).round(2).tolist()} "
              f"max={e['data'].max(0).round(2).tolist()}")
    row["e4_raw_dur"] = e4["ACC"]["n_rows"] / e4["ACC"]["fs"]
    row["e4_hr_fs"] = e4["HR"]["fs"]
    print(f"  tags.csv: {e4['tags']['text'].strip()!r}")
    print(f"  IBI.csv first lines: {e4['IBI']['text'].splitlines()[:2]}")

    # RespiBAN h5 (attributes and dataset shapes only)
    with h5py.File(d / f"{sid}_RespiBAN.h5", "r") as f:
        dev = list(f.keys())[0]
        a = f[dev].attrs
        sensors = {k: f[dev]["raw"][k].attrs.get("sensor", "") for k in f[dev]["raw"].keys()}
        n = int(a["nsamples"])
        print(f"\nRespiBAN.h5: device={dev} fs={a['sampling rate']} nsamples={n} "
              f"({n / a['sampling rate']:.1f}s) duration_attr={a['duration']} "
              f"date={a['date']} time={a['time']}")
        print(f"  raw channels: {sensors}")
        row["h5_dur"] = n / float(a["sampling rate"])
    summary.append(row)


def main():
    sids = sys.argv[1:] or sorted((p.name for p in ROOT.iterdir() if p.is_dir()),
                                  key=lambda s: int(s[1:]))
    summary = []
    for sid in sids:
        inspect_subject(sid, summary)

    print("\n" + "=" * 78)
    print("SUMMARY: durations (s)")
    print("sid | chest ECG | wrist ACC | wrist BVP | wrist EDA | activity | h5 raw | E4 raw ACC | "
          "HR n / expected | pickle load")
    for r in summary:
        d = r["durations"]
        print(f"{r['sid']} | {d['chest/ECG']:.1f} | {d['wrist/ACC']:.1f} | {d['wrist/BVP']:.1f} | "
              f"{d['wrist/EDA']:.1f} | {d['activity']:.1f} | {r['h5_dur']:.1f} | {r['e4_raw_dur']:.1f} | "
              f"{r['hr']['n']} / {r['hr']['expected']} | {r['load']}")
    print("\nSUMMARY: activity seconds per code (from pkl 4 Hz signal)")
    codes = sorted({c for r in summary for c in r["activity_secs"]})
    print("sid | " + " | ".join(f"{c}:{ACTIVITY_DOC.get(c, '?')}" for c in codes))
    for r in summary:
        print(r["sid"] + " | " + " | ".join(f"{r['activity_secs'].get(c, 0):.0f}" for c in codes))
    print("\nSUMMARY: CSV segment name -> pkl code (union over subjects)")
    m = {}
    for r in summary:
        for k, v in r["seg_codes"].items():
            m.setdefault(k, set()).update(v)
    print({k: sorted(v) for k, v in m.items()})
    print("\nSUMMARY: wrist value ranges (min / max / mean per column)")
    for r in summary:
        print(f"{r['sid']} ACC min={r['wrist/ACC']['min']} max={r['wrist/ACC']['max']} "
              f"mean={r['wrist/ACC']['mean']} NaN={r['wrist/ACC']['nan']} | "
              f"BVP min={r['wrist/BVP']['min']} max={r['wrist/BVP']['max']} NaN={r['wrist/BVP']['nan']} | "
              f"HR min={r['hr']['min']} max={r['hr']['max']} mean={r['hr']['mean']} | E4 HR.csv fs={r['e4_hr_fs']} | "
              f"ACC*64 integer fraction={r['acc_x64_int_frac']:.6f}")
    print("\nSUMMARY: NaN counts per signal")
    for r in summary:
        print(r["sid"], {k: v["nan"] for k, v in r.items() if isinstance(v, dict) and "nan" in v})


if __name__ == "__main__":
    main()
