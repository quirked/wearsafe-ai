"""D00c exploration (print-only): FallAllD ID scheme, counts, lengths, units, saturation. Look-only.
Usage (repo root):  python scripts/inspect/explore_fallalld.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_pickle_restricted  # noqa: E402

D = Path("data/interim/_unzipped/fallalld")
df = load_pickle_restricted(D / "FallAllD.pkl")
info = load_pickle_restricted(D / "activity_info.pkl")
dev_ids = df.groupby("ActivityID")["Device"].agg(lambda s: tuple(sorted(set(s))))
print("IDs present only for Wrist:", sorted(dev_ids[dev_ids == ("Wrist",)].index.tolist()))
print("IDs per device:", {d: sorted(g.ActivityID.unique().tolist()) for d, g in df.groupby("Device")})
print("records per device:", df.Device.value_counts().to_dict())
for c in ("Acc", "Gyr", "Mag", "Bar"):
    print(c, "lengths:", df[c].map(len).value_counts().to_dict(), "dtypes:", df[c].map(lambda a: str(a.dtype)).value_counts().to_dict())
w = df[df.Device == "Wrist"]
acc = np.concatenate(w.Acc.tolist()).astype(np.int64)
print("wrist acc count range per axis:", acc.min(0), acc.max(0))
for v in (32767, -32768, 32766, -32767):
    print(v, "count of axis values ==", int((acc == v).sum()))
mag = np.sqrt((acc.astype(float) ** 2).sum(1))
print("wrist |acc| counts quantiles:", np.quantile(mag, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).round(1))
# quiet samples: low local variation -> gravity magnitude in counts
med = []
for a in w.Acc:
    m = np.sqrt((a.astype(float) ** 2).sum(1))
    k = 238
    s = pd.Series(m).rolling(k).std().to_numpy()
    if np.nanmin(s) < 20:
        i = int(np.nanargmin(s))
        med.append(np.median(m[i - k + 1:i + 1]))
print("gravity magnitude in quiet 1 s segments (counts): n", len(med), "median", np.median(med), "IQR", np.percentile(med, [25, 75]))
g = df.groupby(["Device", "SubjectID"]).size().unstack(0)
print(g)
