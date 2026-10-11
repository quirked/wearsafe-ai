"""D00a: read-only inspection of WESAD (data/raw/wesad/WESAD).

Loads ONE subject pickle at a time. For every subject prints:
  - pickle key tree (shapes, dtypes) and how the pickle had to be loaded
  - per-signal length, implied duration at the documented rate, value stats, NaNs
  - label (700 Hz) seconds per code, contiguous label segments
  - protocol schedule from SX_quest.csv (ORDER / START / END, [minutes.seconds])
  - raw E4 zip headers (read in memory) and the SX_respiban.txt header + line count
Ends with compact summary tables.

Usage (from repo root):  python scripts/inspect/inspect_wesad.py [S2 S3 ...]
"""
import collections
import gc
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import key_tree, load_pickle, read_e4_zip, stats  # noqa: E402

ROOT = Path("data/raw/wesad/WESAD")
# Documented sampling rates (wesad_readme.pdf)
FS = {"chest": 700, ("wrist", "ACC"): 32, ("wrist", "BVP"): 64,
      ("wrist", "EDA"): 4, ("wrist", "TEMP"): 4, "label": 700}
LABEL_DOC = {0: "not defined/transient", 1: "baseline", 2: "stress", 3: "amusement",
             4: "meditation", 5: "ignore", 6: "ignore", 7: "ignore"}


def fs_of(loc, name):
    return FS["chest"] if loc == "chest" else FS[(loc, name)]


def min_sec_to_s(x):
    """quest.csv times are [minutes.seconds], e.g. 39.55 = 39 min 55 s."""
    m, _, s = x.partition(".")
    return int(m) * 60 + (int(s.ljust(2, "0")) if s else 0)


def read_quest(path):
    rows = {}
    for line in path.read_text().splitlines():
        parts = [p for p in line.lstrip("#").strip().split(";")]
        if parts and parts[0] in ("Subj", "ORDER", "START", "END"):
            rows[parts[0]] = [p for p in parts[1:] if p != ""]
    sched = []
    for name, st, en in zip(rows["ORDER"], rows["START"], rows["END"]):
        sched.append((name, st, en, min_sec_to_s(st), min_sec_to_s(en)))
    return rows.get("Subj"), sched


def label_segments(lab, fs):
    """Contiguous runs of the same label: (code, start_s, end_s)."""
    change = np.flatnonzero(np.diff(lab)) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [lab.shape[0]]])
    return [(int(lab[s]), s / fs, e / fs) for s, e in zip(starts, ends)]


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
    lab = np.asarray(obj["label"]).ravel()
    durations["label"] = lab.shape[0] / FS["label"]
    row["durations"] = durations
    spread = max(durations.values()) - min(durations.values())
    print(f"  duration spread across all signals: {spread:.3f}s")
    acc = obj["signal"]["wrist"]["ACC"]
    row["acc_is_int"] = bool(np.all(np.round(acc) == acc))
    print(f"  wrist/ACC integer-valued (raw 1/64 g counts?): {row['acc_is_int']}")

    codes, counts = np.unique(lab, return_counts=True)
    print(f"\nlabel: n={lab.shape[0]} dtype={lab.dtype} codes={codes.tolist()}")
    secs = {int(c): n / FS["label"] for c, n in zip(codes, counts)}
    for c, s in secs.items():
        print(f"  code {c} ({LABEL_DOC.get(c, '??')}): {s:.1f}s = {s / 60:.1f} min")
    row["label_secs"] = secs
    segs = [s for s in label_segments(lab, FS["label"]) if s[0] != 0]
    print("  non-zero label segments (code, start s, end s):")
    for c, a, b in segs:
        print(f"    {c} ({LABEL_DOC.get(c)}): {a:8.1f} -> {b:8.1f}  ({b - a:7.1f}s)")
    row["segments"] = segs
    del obj, lab, acc
    gc.collect()

    subj, sched = read_quest(d / f"{sid}_quest.csv")
    print(f"\n{sid}_quest.csv schedule (Subj={subj}); [min.sec] -> seconds:")
    for name, st, en, s0, s1 in sched:
        print(f"  {name:7s} {st:>6s}-{en:>6s}  = {s0:5d}s -> {s1:5d}s ({s1 - s0}s)")
    row["sched"] = sched

    e4 = read_e4_zip(d / f"{sid}_E4_Data.zip")
    print("\nRaw E4 zip:")
    for k in ("ACC", "BVP", "EDA", "TEMP", "HR"):
        e = e4[k]
        print(f"  {k}.csv: start_unix={e['start_unix']:.0f} fs={e['fs']} rows={e['n_rows']} "
              f"cols={e['ncols']} dur={e['n_rows'] / e['fs']:.1f}s min={e['data'].min(0).round(2).tolist()} "
              f"max={e['data'].max(0).round(2).tolist()}")
    row["e4_raw_dur"] = e4["ACC"]["n_rows"] / e4["ACC"]["fs"]
    row["e4_hr_fs"] = e4["HR"]["fs"]
    print(f"  tags.csv: {e4['tags']['text'].strip()!r}")

    # RespiBAN text file: JSON header on line 2, then tab-separated rows
    with open(d / f"{sid}_respiban.txt") as f:
        header = [next(f) for _ in range(3)]
        n_rows = sum(1 for _ in f)
    meta = json.loads(header[1].lstrip("# ").strip())
    dev = next(iter(meta.values()))
    print(f"\nrespiban.txt: rows={n_rows} ({n_rows / 700:.1f}s at 700 Hz) "
          f"sensors={dev.get('sensor')} fs={dev.get('sampling rate')} date={dev.get('date')} "
          f"time={dev.get('time')}")
    row["respiban_txt_dur"] = n_rows / 700
    summary.append(row)


def main():
    sids = sys.argv[1:] or sorted((p.name for p in ROOT.iterdir() if p.is_dir()),
                                  key=lambda s: int(s[1:]))
    summary = []
    for sid in sids:
        inspect_subject(sid, summary)

    print("\n" + "=" * 78)
    print("SUMMARY: durations (s)")
    print("sid | chest ECG | wrist ACC | wrist BVP | wrist EDA | label | respiban.txt | E4 raw ACC | "
          "wrist ACC integer | pickle load")
    for r in summary:
        d = r["durations"]
        print(f"{r['sid']} | {d['chest/ECG']:.1f} | {d['wrist/ACC']:.1f} | {d['wrist/BVP']:.1f} | "
              f"{d['wrist/EDA']:.1f} | {d['label']:.1f} | {r['respiban_txt_dur']:.1f} | "
              f"{r['e4_raw_dur']:.1f} | {r['acc_is_int']} | {r['load']}")
    print("\nSUMMARY: label seconds per code")
    codes = sorted({c for r in summary for c in r["label_secs"]})
    print("sid | " + " | ".join(f"{c}:{LABEL_DOC.get(c)}" for c in codes))
    for r in summary:
        print(r["sid"] + " | " + " | ".join(f"{r['label_secs'].get(c, 0):.1f}" for c in codes))
    print("\nSUMMARY: protocol order (quest.csv) vs non-zero label segment order")
    for r in summary:
        print(r["sid"], [s[0] for s in r["sched"]], "| label segs:", [s[0] for s in r["segments"]])
    # INFERRED mapping quest name -> label code (5/6/7 inferred from protocol position)
    q2code = {"Base": 1, "TSST": 2, "Fun": 3, "Medi 1": 4, "Medi 2": 4,
              "bRead": 5, "sRead": 6, "fRead": 7}
    print("\nSUMMARY: quest.csv interval vs pkl label segment, matched in time order per code")
    print("sid | condition: (label start - quest start) s, (label dur - quest dur) s")
    for r in summary:
        out = []
        sched = sorted(r["sched"], key=lambda x: x[3])
        used = collections.Counter()
        for name, _, _, q0, q1 in sched:
            code = q2code.get(name)
            segs = [s for s in r["segments"] if s[0] == code]
            k = used[code]
            used[code] += 1
            if k < len(segs):
                _, l0, l1 = segs[k]
                out.append(f"{name}: {l0 - q0:+.1f}, {(l1 - l0) - (q1 - q0):+.1f}")
            else:
                out.append(f"{name}: no label segment")
        print(r["sid"] + " | " + "; ".join(out))
    print("\nSUMMARY: wrist TEMP / EDA ranges (pkl)")
    for r in summary:
        print(f"{r['sid']} TEMP min={r['wrist/TEMP']['min']} max={r['wrist/TEMP']['max']} | "
              f"EDA min={r['wrist/EDA']['min']} max={r['wrist/EDA']['max']}")
    print("\nSUMMARY: wrist ACC / BVP ranges")
    for r in summary:
        print(f"{r['sid']} ACC min={r['wrist/ACC']['min']} max={r['wrist/ACC']['max']} "
              f"mean={r['wrist/ACC']['mean']} | BVP min={r['wrist/BVP']['min']} max={r['wrist/BVP']['max']} "
              f"| E4 HR.csv fs={r['e4_hr_fs']}")
    print("\nSUMMARY: NaN counts per signal")
    for r in summary:
        print(r["sid"], {k: v["nan"] for k, v in r.items() if isinstance(v, dict) and "nan" in v})


if __name__ == "__main__":
    main()
