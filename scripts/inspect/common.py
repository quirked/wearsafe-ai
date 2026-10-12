"""Shared helpers for the D00a read-only inspection scripts."""
import io
import pickle
import zipfile

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


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only resolves pandas/numpy classes and a few harmless builtins (third-party pickles)."""

    ALLOWED_PREFIXES = ("pandas.", "numpy.")
    ALLOWED_EXACT = {("builtins", n) for n in ("dict", "list", "tuple", "set", "frozenset", "int", "float",
                                               "str", "bytes", "bytearray", "complex", "bool", "slice", "object")}
    ALLOWED_EXACT |= {("copyreg", "_reconstructor"), ("collections", "OrderedDict"), ("datetime", "datetime"),
                      ("datetime", "date"), ("datetime", "timedelta"), ("_codecs", "encode")}

    def find_class(self, module, name):
        if (module, name) in self.ALLOWED_EXACT or module == "pandas" or module == "numpy" \
                or module.startswith(self.ALLOWED_PREFIXES):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"blocked global {module}.{name}")


def load_pickle_restricted(path):
    with open(path, "rb") as f:
        return RestrictedUnpickler(f).load()
