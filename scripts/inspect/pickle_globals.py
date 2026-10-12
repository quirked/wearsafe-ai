"""List every global (module.name) a pickle would import, WITHOUT loading it (pickletools opcode scan).

Used before loading third-party pickles: anything outside pandas/numpy/builtins/copyreg/collections is a red flag.
Usage (repo root):  python scripts/inspect/pickle_globals.py FILE [FILE ...]
"""
import pickletools
import sys
from collections import Counter

SAFE_PREFIXES = ("pandas", "numpy", "builtins", "__builtin__", "copyreg", "copy_reg", "collections", "datetime",
                 "_codecs")


def globals_in(path):
    found, recent = Counter(), []
    with open(path, "rb") as f:
        for op, arg, _ in pickletools.genops(f):
            if op.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "BINUNICODE8"):
                recent = (recent + [arg])[-2:]
            elif op.name == "GLOBAL":
                found[arg.replace(" ", ".")] += 1
            elif op.name == "STACK_GLOBAL" and len(recent) == 2:
                found[f"{recent[0]}.{recent[1]}"] += 1
            elif op.name in ("REDUCE", "BUILD", "INST", "OBJ", "NEWOBJ", "NEWOBJ_EX"):
                pass
    return found


if __name__ == "__main__":
    bad = False
    for p in sys.argv[1:]:
        g = globals_in(p)
        print(f"== {p}")
        for k, n in sorted(g.items()):
            ok = k.split(".")[0] in SAFE_PREFIXES
            bad |= not ok
            print(f"  {'ok ' if ok else 'BAD'} {k} x{n}")
    sys.exit(1 if bad else 0)
