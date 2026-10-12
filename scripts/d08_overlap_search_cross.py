"""D08 pre-check follow-up (read-only): identical-overlap search ACROSS subjects (>= 1 s of identical raw samples,
any lag), same method as scripts/d08_overlap_search.py but indexing all wrist records together and keeping only
pairs from different subjects (these would leak across LOSO folds). Appends section 7 (append only).
Usage (repo root):  python scripts/d08_overlap_search_cross.py
"""
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fallalld_io as fio  # noqa: E402
from d02_smoke_report import md  # noqa: E402
from d08_overlap_search import L, block_keys, codes  # noqa: E402

OUT = REPO / "reports/D08_fallalld_prechecks_tables.md"
MARK = "## 7. Identical-overlap search ACROSS subjects"


def main():
    if MARK in OUT.read_text():
        raise RuntimeError("section 7 already present")
    w, _ = fio.wrist_records(REPO)
    subj = dict(zip(w.record_id, w.subject_id))
    vs = {r: codes(a) for r, a in zip(w.record_id, w.Acc)}
    index = defaultdict(list)
    for r, v in vs.items():
        for off, k in enumerate(block_keys(v)[::L]):
            index[k].append(r)
    cand = set()
    for r, v in vs.items():
        for k in block_keys(v):
            for r2 in index.get(k, ()):
                if subj[r2] != subj[r]:
                    cand.add(tuple(sorted((r, r2))))
    S = [f"\n{MARK} (appended by scripts/d08_overlap_search_cross.py)\n",
         f"Records indexed: {len(vs)}. Cross-subject candidate pairs sharing a 1 s block key: **{len(cand)}**.\n"]
    if cand:
        S.append(md(pd.DataFrame(sorted(cand), columns=["record_a", "record_b"])) + "\n")
    with open(OUT, "a") as f:
        f.write("\n".join(S))
    print("cross-subject candidate pairs:", len(cand))


if __name__ == "__main__":
    main()
