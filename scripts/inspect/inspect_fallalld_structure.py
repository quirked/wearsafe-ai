"""D00c — FallAllD structure (FallAllD.pkl, extracted copy) + activity_info.pkl. Look-only.

The banned SMOTE pickle is never opened (CLAUDE.md §2.3). Pickles are loaded with a restricted unpickler.
Usage (repo root):  python scripts/inspect/inspect_fallalld_structure.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_pickle_restricted  # noqa: E402

D = Path("data/interim/_unzipped/fallalld")
info = load_pickle_restricted(D / "activity_info.pkl")
print("activity_info type:", type(info))
print(repr(info)[:3000])
df = load_pickle_restricted(D / "FallAllD.pkl")
print("FallAllD type:", type(df), "shape:", getattr(df, "shape", None))
print(df.dtypes)
print(df.head(3).T)
for c in df.columns:
    v = df[c].iloc[0]
    print(c, type(v).__name__, getattr(v, "shape", None), getattr(v, "dtype", None))
for c in df.columns:
    if df[c].map(lambda v: np.isscalar(v)).all():
        print(c, "unique:", df[c].nunique(), sorted(df[c].unique().tolist())[:60])
