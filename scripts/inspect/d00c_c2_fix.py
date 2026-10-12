"""D00c fix: corrected table C2 (FallAllD wrist trial numbers), APPENDED as Part D to
reports/D00c_fallalld_upfall_audit_tables.md. The original (empty) C2 is left in place.

Bug: d00c_followup.py ended the C2 table expression with `.head(0)`, which kept the header and dropped every row.
Look-only: reads the extracted FallAllD.pkl / activity_info.pkl (restricted unpickler). Refuses to append twice.
Usage (repo root):  python scripts/inspect/d00c_c2_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_pickle_restricted  # noqa: E402
from d00c_audit import md  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports/D00c_fallalld_upfall_audit_tables.md"
MARK = "# Part D — corrected table C2"


def main():
    if MARK in OUT.read_text():
        raise RuntimeError("Part D already present; refusing to append twice")
    df = load_pickle_restricted(REPO / "data/interim/_unzipped/fallalld/FallAllD.pkl")
    info = load_pickle_restricted(REPO / "data/interim/_unzipped/fallalld/activity_info.pkl")
    w = df[df.Device == "Wrist"]
    S = ["\n" + MARK + " (appended by scripts/inspect/d00c_c2_fix.py; replaces the empty C2 above)\n",
         "Bug in C2: a stray `.head(0)` in d00c_followup.py dropped all rows. The distribution line under C2 was "
         "computed separately and is correct.\n"]
    t = (w.groupby("ActivityID")
         .agg(records=("TrialNo", "size"), subjects=("SubjectID", "nunique"),
              trial_min=("TrialNo", "min"), trial_median=("TrialNo", "median"), trial_max=("TrialNo", "max"))
         .reset_index())
    t.insert(1, "name", t.ActivityID.map(info))
    S.append("## D1. FallAllD wrist: TrialNo per activity [verified in files]\n\n" + md(t) + "\n")
    s = (w.groupby("SubjectID")
         .agg(records=("TrialNo", "size"), activities=("ActivityID", "nunique"), max_trial=("TrialNo", "max"))
         .reset_index())
    S.append("## D2. FallAllD wrist: max TrialNo per subject [verified in files]\n\n" + md(s) + "\n")
    gaps = (w.groupby(["SubjectID", "ActivityID"]).TrialNo
            .agg(lambda x: sorted(x.tolist()) != list(range(1, len(x) + 1))))
    S.append(f"(subject, activity) groups whose TrialNo values are not exactly 1..n: {int(gaps.sum())} of {len(gaps)}\n")
    with open(OUT, "a") as f:
        f.write("\n".join(S))
    print("appended Part D")


if __name__ == "__main__":
    main()
