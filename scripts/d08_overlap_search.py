"""D08 pre-check follow-up (read-only): exhaustive search for wrist records that share an IDENTICAL stretch of
>= 1 s (238 consecutive raw samples, all three axes) with another record of the same subject, at any lag.

Candidate matches come from a sampled key of each 238-sample block (5 sample codes + block sum); every candidate
is then verified sample by sample, and the full identical run is measured. Appends section 6 to the pre-checks
tables (append only; refuses to append twice). Report only — nothing is excluded.
Usage (repo root):  python scripts/d08_overlap_search.py
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fallalld_io as fio  # noqa: E402
from d02_smoke_report import md  # noqa: E402

OUT = REPO / "reports/D08_fallalld_prechecks_tables.md"
MARK = "## 6. Exhaustive identical-overlap search"
L = 238
PICK = np.array([0, 59, 118, 177, 237])


def codes(acc):
    a = acc.astype(np.int64) + 32768
    return (a[:, 0] << 32) | (a[:, 1] << 16) | a[:, 2]


def block_keys(v):
    cs = np.concatenate([[0], np.cumsum(v % 1000003)])
    n = len(v) - L + 1
    sums = cs[L:L + n] - cs[:n]
    cols = np.stack([v[PICK[k]:PICK[k] + n] for k in range(len(PICK))], axis=1)
    return [tuple(r) + (s,) for r, s in zip(cols.tolist(), sums.tolist())]


def main():
    if MARK in OUT.read_text():
        raise RuntimeError("section 6 already present")
    w, _ = fio.wrist_records(REPO)
    rows = []
    for sid, g in w.groupby("subject_id"):
        recs = g.record_id.tolist()
        vs = {r: codes(a) for r, a in zip(g.record_id, g.Acc)}
        index = defaultdict(list)
        for r in recs:
            for off, k in enumerate(block_keys(vs[r])[::L]):          # non-overlapping blocks of r (stride L)
                index[k].append((r, off * L))
        found = {}
        for r in recs:
            for off, k in enumerate(block_keys(vs[r])):               # every offset of r
                for (r2, off2) in index.get(k, ()):
                    if r2 == r:
                        continue
                    pair = tuple(sorted((r, r2)))
                    lag = (off - off2) if pair[0] == r else (off2 - off)
                    if (pair, lag) not in found:
                        found[(pair, lag)] = None
        for (pair, lag), _ in found.items():
            a, b = vs[pair[0]], vs[pair[1]]
            # a[t] == b[t - lag]
            if lag >= 0:
                oa, ob = a[lag:], b[:len(a) - lag]
            else:
                oa, ob = a[:len(a) + lag], b[-lag:]
            eq = oa == ob
            best = cur = 0
            for e in eq:
                cur = cur + 1 if e else 0
                best = max(best, cur)
            if best >= L:
                la = g.loc[g.record_id == pair[0], "original_label"].iat[0]
                lb = g.loc[g.record_id == pair[1], "original_label"].iat[0]
                rows.append({"subject_id": sid, "record_a": pair[0], "record_b": pair[1], "label_a": la, "label_b": lb,
                             "lag_s": round(lag / L, 3), "longest_identical_run_s": round(best / L, 2),
                             "kind_a": "fall" if int(pair[0].split("_A")[1][:3]) > 100 else "adl",
                             "kind_b": "fall" if int(pair[1].split("_A")[1][:3]) > 100 else "adl"})
        print(sid, "pairs so far", len(rows), flush=True)
    t = pd.DataFrame(rows).drop_duplicates(["record_a", "record_b"]) if rows else pd.DataFrame()
    S = [f"\n{MARK} (appended by scripts/d08_overlap_search.py) — wrist records sharing ≥ 1 s of identical raw "
         "samples with another record of the same subject (any lag). Report only.\n"]
    if len(t):
        recs = set(t.record_a) | set(t.record_b)
        S.append(f"Pairs: **{len(t)}**; distinct records involved: {len(recs)} of {len(w)}; subjects: "
                 f"{t.subject_id.nunique()}; pairs with a fall record: {int(((t.kind_a == 'fall') | (t.kind_b == 'fall')).sum())}; "
                 f"pairs with different activity IDs: {int((t.label_a != t.label_b).sum())}.\n")
        S.append(f"Longest identical run (s): median {t.longest_identical_run_s.median():.2f}, min "
                 f"{t.longest_identical_run_s.min():.2f}, max {t.longest_identical_run_s.max():.2f}.\n")
        pairs_by = t.assign(activities=t.label_a.str.split(":").str[0] + "↔" + t.label_b.str.split(":").str[0]) \
            .groupby("activities").size().sort_values(ascending=False).rename("pairs").reset_index()
        S.append("Pairs by activity pair:\n\n" + md(pairs_by) + "\n")
        S.append(md(t.sort_values(["subject_id", "record_a"])) + "\n")
    else:
        S.append("No pairs found.\n")
    with open(OUT, "a") as f:
        f.write("\n".join(S))
    print("appended section 6;", len(t), "pairs")


if __name__ == "__main__":
    main()
