"""D08 — final checks of splits/fallalld_v1.json against the built window table and metadata (read-only).
Usage (repo root):  python scripts/d08_check_splits.py --tag v1
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe.splits import check_folds  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    m = json.loads((REPO / "splits/fallalld_v1.json").read_text())
    win = pd.read_parquet(REPO / f"data/interim/fallalld/windows_{args.tag}/windows.parquet")
    og = pd.read_csv(REPO / "metadata/fallalld_overlap_groups_v1.csv")
    res = []

    def chk(cond, msg):
        res.append((msg, bool(cond)))
    chk(check_folds(m["folds"], m["subjects"]) == [], "no subject in two splits; every subject tested exactly once")
    chk(sorted(win.subject_id.unique()) == m["subjects"], "manifest subjects == subjects in the window table")
    roles = win.groupby(["subject_id", "window_role"]).size().unstack(fill_value=0)
    key = {"positive_windows": "fall_positive", "fall_clip_context_windows": "fall_clip_context",
           "label_uncertain_windows": "label_uncertain_fall", "adl_windows": "adl", "probe_windows": "hard_negative_probe"}
    ok = all((int(roles.at[s, r]) if r in roles.columns else 0) == c[k] for s, c in m["per_subject_counts"].items()
             for k, r in key.items())
    chk(ok, "per-subject window counts in the manifest == window table")
    chk(all(m["per_subject_counts"][s]["overlap_groups"] == og[og.subject_id == s].overlap_group_id.nunique()
            for s in m["subjects"]), "per-subject overlap-group counts == metadata")
    chk(set(m["subjects_with_falls"]) == set(win.loc[win.window_role == "fall_positive", "subject_id"]),
        "subjects_with_falls == subjects with positive windows")
    chk(all(set(f["inner_validation_subjects"]) == set(f["train"]) & set(m["subjects_with_falls"]) for f in m["folds"]),
        "inner validation subjects = training subjects with falls")
    chk(og.groupby("overlap_group_id").subject_id.nunique().max() == 1, "no overlap group spans two subjects")
    src = hashlib.sha256((REPO / "data/interim/_unzipped/fallalld/FallAllD.pkl").read_bytes()).hexdigest()
    chk(src == m["source_sha256"], "manifest source_sha256 == extracted FallAllD.pkl")
    for msg, p in res:
        print(("PASS " if p else "FAIL ") + msg)
    if not all(p for _, p in res):
        sys.exit(1)


if __name__ == "__main__":
    main()
