"""D08 diagnostic (read-only; prints only): is the failed edge-artefact check a resampling artefact or a property
of the raw recordings? Same comparison (median over cyclic-ADL clips of the window mean |a|, first/last 2 s window vs
interior windows) on (1) native 238 Hz raw counts — no filter — and (2) the unclipped 32 Hz output, for the smoke
subjects and for all wrist subjects. Also the per-window profile (start 0..18 s) to see where the deviation sits.
Usage (repo root):  python scripts/d08_edge_diagnostic.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402

cfg = yaml.safe_load(open(REPO / "config/fallalld_v1.yaml"))
w, _ = fio.wrist_records(REPO)
cyc = w[w.ActivityID.isin(cfg["cyclic_adl_ids"])]


def profile(recs, native):
    prof = []
    for c in recs.Acc:
        if native:
            mag = np.sqrt((mh.counts_to_g(c, 4096) ** 2).sum(1))
            fs = 238
        else:
            mag = np.sqrt((mh.resample_238_to_32(mh.counts_to_g(c, 4096)) ** 2).sum(1))
            fs = 32
        prof.append([mag[int(s * fs):int((s + 2) * fs)].mean() for s in range(19)])
    p = np.median(np.array(prof), axis=0)
    interior = np.median(np.array(prof)[:, 1:18])
    return p, interior


for name, recs in (("smoke S01+S04", cyc[cyc.SubjectID.isin([1, 4])]), ("all wrist subjects", cyc)):
    for native in (True, False):
        p, interior = profile(recs, native)
        lab = "native 238 Hz (no filter)" if native else "unclipped 32 Hz (resampled)"
        print(f"{name} | {lab} | clips {len(recs)} | first {100 * (p[0] / interior - 1):+.2f}% | "
              f"last {100 * (p[-1] / interior - 1):+.2f}% | profile (% vs interior, start 0..18 s): "
              + " ".join(f"{100 * (v / interior - 1):+.1f}" for v in p))
print("per activity (all subjects, native 238 Hz, last window % vs that activity's interior):")
for act, g in cyc.groupby("ActivityID"):
    p, interior = profile(g, True)
    print(f"  {act}: clips {len(g)}, first {100 * (p[0] / interior - 1):+.2f}%, last {100 * (p[-1] / interior - 1):+.2f}%")
