"""D08 — FallAllD wrist split manifest: outer leave-one-subject-out over all 13 wrist subjects (subject-level).

Writes splits/fallalld_v1.json (refuses to overwrite). Window counts per subject follow config/fallalld_v1.yaml
roles (1 positive per fall clip; 18 fall_clip_context; 19 per ADL clip; probes 15/23 separate).
Usage (repo root):  python scripts/d08_fallalld_splits.py
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe.splits import check_folds, loso_folds  # noqa: E402

OUT = REPO / "splits/fallalld_v1.json"


def main():
    if OUT.exists():
        raise FileExistsError(f"{OUT} exists; refusing to overwrite")
    cfg = yaml.safe_load(open(REPO / "config/fallalld_v1.yaml"))
    w, _ = fio.wrist_records(REPO)
    lu = pd.read_csv(REPO / cfg["label_uncertain"]["file"])
    uncertain = set(lu.loc[lu.status == "label_uncertain_fall", "record_id"])
    og = pd.read_csv(REPO / cfg["overlap_groups"]["file"])
    per = cfg["windows"]["per_record"]
    subjects = sorted(w.subject_id.unique())
    counts = {}
    for sid, g in w.groupby("subject_id"):
        nu = int(g.record_id.isin(uncertain).sum())
        nf = int((g.kind == "fall").sum())
        probes = int(g.ActivityID.isin(cfg["probe_ids"]).sum())
        nadl = int((g.kind == "adl").sum()) - probes
        ogs = og[og.subject_id == sid]
        counts[sid] = {"fall_clips": nf, "label_uncertain_fall_clips": nu, "adl_clips": nadl, "probe_clips": probes,
                       "positive_windows": nf - nu, "fall_clip_context_windows": (nf - nu) * (per - 1),
                       "label_uncertain_windows": nu * per, "adl_windows": nadl * per, "probe_windows": probes * per,
                       "overlap_groups": int(ogs.overlap_group_id.nunique())}
    with_f = [s for s in subjects if counts[s]["fall_clips"] > 0]
    without_f = [s for s in subjects if counts[s]["fall_clips"] == 0]
    folds = loso_folds(subjects)
    problems = check_folds(folds, subjects)
    if problems:
        raise RuntimeError(f"split check failed: {problems}")
    for f in folds:
        f["test_counts"] = counts[f["test"][0]]
        f["inner_validation_subjects"] = [s for s in f["train"] if s in with_f]
    manifest = {
        "name": "fallalld_v1", "dataset": "fallalld", "device": "Wrist", "scheme": "leave_one_subject_out",
        "subjects": subjects, "subjects_with_falls": with_f, "subjects_without_falls": without_f,
        "inner_validation_rule": "inner leave-one-subject-out among the TRAINING subjects with falls (tuning only); "
                                 "listed per fold as inner_validation_subjects",
        "metrics_rule": "fall detection metrics on subjects with falls; false-positive metrics on all subjects; pooled "
                        "out-of-fold predictions for overall PR-AUC (config/evaluation_v1.yaml)",
        "dedup_rule": "every evaluation also reports a deduplicated check: one clip per overlap_group_id (lowest record_id; "
                      "metadata/fallalld_overlap_groups_v1.csv). Overlap groups are within-subject only, so LOSO is leakage-safe.",
        "label_uncertain_rule": "label_uncertain_fall clips: excluded from training and window-level metrics; fall clips in "
                                "clip-level metrics (metadata/fallalld_label_uncertain_v1.csv)",
        "per_subject_counts": counts, "folds": folds,
        "checks": {"subject_in_two_splits": False, "every_subject_tested_once": True, "problems": problems},
        "source_sha256": hashlib.sha256((REPO / fio.UNZIPPED / "FallAllD.pkl").read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256((REPO / "config/fallalld_v1.yaml").read_bytes()).hexdigest(),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {OUT}: {len(folds)} folds; with falls {len(with_f)}, without {len(without_f)}")


if __name__ == "__main__":
    main()
