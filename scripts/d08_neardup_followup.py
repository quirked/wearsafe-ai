"""D08 pre-check follow-up (read-only): do the flagged near-duplicate pairs share IDENTICAL raw samples?

For each pair flagged in reports/D08_fallalld_prechecks_tables.md, find the lag (native 238 Hz) that maximises the
cross-correlation of |a| counts, then count raw (x, y, z) samples that are exactly equal over the overlap.
Appends section 5 to the pre-checks tables (append only; refuses to append twice).
Usage (repo root):  python scripts/d08_neardup_followup.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from wearsafe import fallalld_io as fio  # noqa: E402
from d02_smoke_report import md  # noqa: E402

OUT = REPO / "reports/D08_fallalld_prechecks_tables.md"
MARK = "## 5. Near-duplicate follow-up"


def main():
    text = OUT.read_text()
    if MARK in text:
        raise RuntimeError("section 5 already present")
    pairs = re.findall(r"^\| (FALLALLD_S\d+_A\d+_T\d+) \| (FALLALLD_S\d+_A\d+_T\d+) \| ([\d.]+) \|", text, re.M)
    w, _ = fio.wrist_records(REPO)
    acc = dict(zip(w.record_id, w.Acc))
    rows = []
    for a, b, xc in pairs:
        A, B = acc[a].astype(np.int64), acc[b].astype(np.int64)
        ma, mb = np.sqrt((A ** 2).sum(1)), np.sqrt((B ** 2).sum(1))
        ma, mb = ma - ma.mean(), mb - mb.mean()
        n = 2 * len(ma)
        cc = np.fft.irfft(np.fft.rfft(ma, n) * np.conj(np.fft.rfft(mb, n)), n)
        lag = int(np.argmax(np.abs(cc)))
        lag = lag if lag < len(ma) else lag - n            # A[t] ~ B[t - lag]
        if lag >= 0:
            oa, ob = A[lag:], B[:len(A) - lag]
        else:
            oa, ob = A[:len(A) + lag], B[-lag:]
        eq = (oa == ob).all(axis=1)
        rows.append({"record_a": a, "record_b": b, "xcorr_32hz": float(xc), "best_lag_s_238hz": round(lag / 238, 3),
                     "overlap_s": round(len(oa) / 238, 2), "identical_samples": int(eq.sum()),
                     "identical_frac_of_overlap": round(float(eq.mean()), 4)})
    t = pd.DataFrame(rows)
    S = [f"\n{MARK} (appended by scripts/d08_neardup_followup.py): identical raw samples at the best lag\n",
         f"Pairs checked: {len(t)}; pairs with ≥ 1 s (238 samples) of identical raw (x, y, z) samples: "
         f"{int((t.identical_samples >= 238).sum())}.\n", md(t) + "\n"]
    with open(OUT, "a") as f:
        f.write("\n".join(S))
    print(t.to_string())


if __name__ == "__main__":
    main()
