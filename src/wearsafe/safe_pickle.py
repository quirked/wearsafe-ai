"""Restricted unpickler for third-party pickles (moved from scripts/inspect/common.py, D08).

Only pandas/numpy classes and a few harmless builtins can be resolved; anything else raises.
"""
from __future__ import annotations

import pickle


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
