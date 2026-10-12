"""FallAllD loading (D08). Original FallAllD.pkl only, via the restricted unpickler; wrist ACC only.

The SMOTE pickle FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl is BANNED (CLAUDE.md §2.3): any path containing
its name is refused before anything is opened.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from wearsafe.safe_pickle import load_pickle_restricted
from wearsafe.schemas import namespaced_subject_id

BANNED_NAME = "FallAllD_40SamplesPerSec_ActivityIdsFiltered"
UNZIPPED = Path("data/interim/_unzipped/fallalld")
FALL_IDS = range(101, 136)
ADL_IDS = range(1, 45)


def guard(path) -> Path:
    if BANNED_NAME.lower() in str(path).lower():
        raise PermissionError(f"refusing to open banned file {path} (CLAUDE.md §2.3)")
    return Path(path)


def record_id(subject: int, activity: int, trial: int) -> str:
    return f"{namespaced_subject_id('fallalld', subject)}_A{activity:03d}_T{trial:02d}"


def wrist_records(repo: Path) -> tuple[pd.DataFrame, dict]:
    """(wrist DataFrame with subject_id/record_id/original_label/kind, activity_info dict)."""
    info = load_pickle_restricted(guard(repo / UNZIPPED / "activity_info.pkl"))
    df = load_pickle_restricted(guard(repo / UNZIPPED / "FallAllD.pkl"))
    w = df[df.Device == "Wrist"][["SubjectID", "ActivityID", "TrialNo", "Acc"]].copy()
    w["subject_id"] = [namespaced_subject_id("fallalld", int(s)) for s in w.SubjectID]
    w["record_id"] = [record_id(int(s), int(a), int(t)) for s, a, t in zip(w.SubjectID, w.ActivityID, w.TrialNo)]
    w["original_label"] = [f"{int(a)}: {info[int(a)]}" for a in w.ActivityID]
    w["kind"] = ["fall" if int(a) in FALL_IDS else "adl" for a in w.ActivityID]
    if not w.record_id.is_unique:
        raise ValueError("duplicate wrist record ids")
    return w.sort_values(["SubjectID", "ActivityID", "TrialNo"]).reset_index(drop=True), info
