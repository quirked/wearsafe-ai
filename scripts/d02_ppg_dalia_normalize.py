"""D02 — PPG-DaLiA Layer A normalisation (one subject at a time).

Writes, per subject, data/interim/ppg_dalia/normalized_signals_<tag>/PPGDALIA_Sxx/
  wrist_acc.parquet  wrist_bvp.parquet  activity.parquet  hr_ref.parquet
plus metadata/ppg_dalia_subjects_<tag>.csv and run_info.json / checks.json in the output folder.

Invariant checks run per subject BEFORE anything is written; any failure stops the run (CLAUDE.md §3).
Refuses to overwrite (CLAUDE.md §2.1). Read-only on data/raw/.

Usage (repo root):  python scripts/d02_ppg_dalia_normalize.py --subjects 3 6 --tag smoke_v1 [--out-root DIR]
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe.raw_manifest import CURRENT_MANIFEST  # noqa: E402

LABEL_MAPS = REPO / "config/label_maps.yaml"


class InvariantError(RuntimeError):
    pass


def check(cond, msg, results, subject):
    results.append({"subject_id": subject, "check": msg, "passed": bool(cond)})
    if not cond:
        raise InvariantError(f"{subject}: FAILED {msg}")


def git_hash():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()


def file_sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def subject_checks(s, tables, maps, results):
    sid = s.subject_id
    d = io.durations(s)
    check(d["acc"] == d["bvp"] == d["activity"], f"equal durations acc/bvp/activity {d}", results, sid)
    dur = d["activity"]
    check(len(s.hr_ref) == io.expected_hr_ref_count(dur),
          f"hr_ref count {len(s.hr_ref)} == floor((D-8)/2)+1 = {io.expected_hr_ref_count(dur)}", results, sid)
    counts, max_dev = io.acc_counts(s.acc_g)
    check(max_dev < 1e-9, f"acc*64 integer-valued (max deviation {max_dev:.2e})", results, sid)
    check(counts.min() >= -128 and counts.max() <= 127,
          f"acc counts within E4 range [-128, 127] (got {counts.min()}..{counts.max()})", results, sid)
    acc = tables["wrist_acc"]
    lim = 128 / 64 * maps["units"]["ppg_dalia"]["wrist_acc"]["factor"]
    check(acc[["x", "y", "z"]].abs().max().max() <= lim + 1e-9, f"|acc| <= {lim:.4f} m/s^2", results, sid)
    check(np.allclose(acc["x"].to_numpy(), s.acc_g[:, 0] * 9.80665, rtol=0, atol=0),
          "acc factor 9.80665 applied exactly", results, sid)
    for name, df, cols in (("wrist_acc", acc, ["x", "y", "z"]), ("wrist_bvp", tables["wrist_bvp"], ["scalar_value"]),
                           ("hr_ref", tables["hr_ref"], ["hr_ref_bpm"])):
        n_nan = int(df[cols].isna().sum().sum())
        check(n_nan == 0, f"{name}: NaN count {n_nan} == 0", results, sid)
    act = tables["activity"]
    check(act["original_label"].notna().all(), "every activity code maps to a label", results, sid)
    check(len(act) == len(s.activity) and len(acc) == len(s.acc_g) and len(tables["wrist_bvp"]) == len(s.bvp),
          "row counts equal raw sample counts", results, sid)
    # label seconds in Layer A == raw pkl counts / 4 (re-derived independently from the raw codes)
    names = {int(k): v for k, v in maps["ppg_dalia"]["original_label"].items()}
    raw_sec = {names[c]: n / io.FS_ACT for c, n in zip(*np.unique(s.activity, return_counts=True))}
    out_sec = (act["original_label"].value_counts() / io.FS_ACT).to_dict()
    check(raw_sec == out_sec, "label seconds in Layer A equal raw pkl label seconds", results, sid)
    if s.number == 6:
        check(dur == 5250.0, f"S6 duration {dur} == 5250 s (pkl valid only to 5250 s)", results, sid)
        missing = {"lunch", "walking", "working"} & set(out_sec)
        check(not missing, f"S6 has no lunch/walking/working (found {sorted(missing)})", results, sid)
    return dur, raw_sec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, nargs="+", required=True)
    ap.add_argument("--tag", required=True, help="e.g. smoke_v1 or v1")
    ap.add_argument("--out-root", default="data/interim/ppg_dalia", help="parent folder of the output")
    ap.add_argument("--meta-dir", default="metadata")
    args = ap.parse_args()

    out = REPO / args.out_root / f"normalized_signals_{args.tag}"
    meta_csv = REPO / args.meta_dir / f"ppg_dalia_subjects_{args.tag}.csv"
    for p in (out, meta_csv):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite (CLAUDE.md §2.1)")
    maps = yaml.safe_load(open(LABEL_MAPS))
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        raise FileExistsError(f"{tmp} exists from an interrupted run; inspect it, do not overwrite")
    tmp.mkdir(parents=True)

    results, subj_rows, summary = [], [], []
    t0 = time.time()
    for n in args.subjects:
        s = io.load_subject(n, REPO)
        tables = io.normalize(s, maps)
        dur, sec = subject_checks(s, tables, maps, results)
        d = tmp / s.subject_id
        d.mkdir()
        for name, df in tables.items():
            df.to_parquet(d / f"{name}.parquet", index=False)
        acc = tables["wrist_acc"]
        summary.append({"subject_id": s.subject_id, "duration_s": dur, "n_acc": len(acc),
                        "n_bvp": len(tables["wrist_bvp"]), "n_activity": len(tables["activity"]),
                        "n_hr_ref": len(tables["hr_ref"]), "acc_saturated_frac": float(acc["acc_saturated"].mean()),
                        "label_seconds": sec})
        subj_rows.append(io.subject_row(s))
        print(f"{s.subject_id}: {dur:.0f} s, {len(acc)} acc, saturated {acc['acc_saturated'].mean():.4%}, "
              f"{time.time() - t0:.0f}s", flush=True)
        del s, tables, acc

    info = {"script": "scripts/d02_ppg_dalia_normalize.py", "git_commit": git_hash(), "tag": args.tag,
            "subjects": args.subjects, "label_maps_sha256": file_sha256(LABEL_MAPS),
            "raw_manifest": CURRENT_MANIFEST, "seed": None, "subjects_summary": summary,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (tmp / "run_info.json").write_text(json.dumps(info, indent=2, default=str))
    (tmp / "checks.json").write_text(json.dumps(results, indent=2))
    tmp.rename(out)
    meta_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(subj_rows).to_csv(meta_csv, index=False)
    print(f"all {len(results)} checks passed; wrote {out} and {meta_csv}")


if __name__ == "__main__":
    main()
