"""Shared helpers for the D00a read-only inspection scripts."""
import io
import pickle
import sys
import zipfile
from pathlib import Path

import numpy as np


def load_pickle(path):
    """Load a (possibly Python-2 era) pickle. Returns (obj, how_it_was_loaded)."""
    with open(path, "rb") as f:
        try:
            return pickle.load(f), "default"
        except UnicodeDecodeError:
            pass
    with open(path, "rb") as f:
        return pickle.load(f, encoding="latin1"), "encoding='latin1'"


def key_tree(obj, prefix="", out=None):
    """Flatten a nested dict into lines 'path: type shape dtype'."""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_tree(v, f"{prefix}/{k}" if prefix else str(k), out)
    elif isinstance(obj, np.ndarray):
        out.append(f"{prefix}: ndarray shape={obj.shape} dtype={obj.dtype}")
    else:
        val = repr(obj)
        out.append(f"{prefix}: {type(obj).__name__} = {val[:80]}")
    return out


def stats(a):
    """min/max/mean/NaN-count of a numeric array (computed per column if 2-D)."""
    a = np.asarray(a, dtype=float)
    n_nan = int(np.isnan(a).sum())
    if a.ndim == 1:
        a = a[:, None]
    return {
        "min": np.nanmin(a, axis=0).round(4).tolist(),
        "max": np.nanmax(a, axis=0).round(4).tolist(),
        "mean": np.nanmean(a, axis=0).round(4).tolist(),
        "nan": n_nan,
    }


def read_e4_zip(path):
    """Read an Empatica E4 zip in memory (no extraction).

    Returns {name: dict(start_unix, fs, n_rows, ncols, data)} for the
    header-style files (ACC, BVP, EDA, TEMP, HR) plus raw text for IBI/tags/info.
    """
    out = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            raw = zf.read(name).decode("utf-8", errors="replace")
            stem = name.rsplit(".", 1)[0]
            if stem in ("ACC", "BVP", "EDA", "TEMP", "HR"):
                lines = raw.strip().splitlines()
                start = float(lines[0].split(",")[0])
                fs = float(lines[1].split(",")[0])
                data = np.loadtxt(io.StringIO("\n".join(lines[2:])), delimiter=",", ndmin=2)
                out[stem] = dict(start_unix=start, fs=fs, n_rows=data.shape[0],
                                 ncols=data.shape[1], data=data)
            else:
                out[stem] = dict(text=raw)
    return out


# Moved to src/wearsafe/safe_pickle.py in D08; re-exported here so the D00c scripts keep working.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from wearsafe.safe_pickle import RestrictedUnpickler, load_pickle_restricted  # noqa: E402,F401
