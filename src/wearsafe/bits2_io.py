"""BITS-2 CSV parser (format verified in reports/D00a_data_inventory.md §3 and the paper, Nandi et al. 2024).

A BITS-2 file is a stack of sensor blocks under header 't,x,y,z,a,':
  IMU rows: t, x, y, z, <axis count / accuracy>, <sensor>   sensor in {acc, acg, gyro, mgm}
  HR rows : t, bpm, <status>, hrt, ,                        (block header may be 't,bpm,a,,,')
Quirks handled: UTF-8 BOM, CR or CRLF line endings, header 'a,x,y,z,a,', repeated header lines
between blocks, blank ',,,,,' rows, rows with a missing value or sensor tag (kept as 'malformed').
Timestamps are kept as the original strings as well as floats, because most were rounded to
2-3 significant digits before publication and the rounding step matters for rate estimation.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

IMU_STREAMS = ("acc", "acg", "gyro", "mgm")
STREAMS = IMU_STREAMS + ("hrt",)
_SCI = re.compile(r"^(\d)(?:\.(\d+))?E\+(\d+)$", re.IGNORECASE)
_NAME = re.compile(r"^user(\d+)_(\.?)(adl|fall)(\d+)\.csv$")


def parse_name(name: str):
    """'user31_.fall1.csv' -> (31, 'fall', 1, True). Returns None if the name does not match."""
    m = _NAME.match(name)
    if not m:
        return None
    return int(m.group(1)), m.group(3), int(m.group(4)), bool(m.group(2))


def sig_digits(t: str):
    """Significant digits of a timestamp as written ('1.82E+11' -> 3, '53000000000000' -> 2)."""
    m = _SCI.match(t)
    if m:
        return 1 + len(m.group(2) or "")
    if t.isdigit():
        return len(t.lstrip("0").rstrip("0")) or 1
    try:
        float(t)
    except ValueError:
        return None
    return len(t.replace(".", "").replace("-", "").lstrip("0").rstrip("0")) or 1


def rounding_step(t: str) -> float | None:
    """Size of one unit in the last written significant digit, in the timestamp's own unit."""
    d = sig_digits(t)
    if d is None:
        return None
    v = abs(float(t))
    if v == 0:
        return None
    return 10.0 ** (math.floor(math.log10(v)) - (d - 1))


@dataclass
class Bits2File:
    path: str
    sha1: str
    bom: bool
    crlf: bool
    lone_cr: bool
    header: str
    inner_headers: int
    blank_rows: int
    malformed: list = field(default_factory=list)          # (line_no, text)
    blocks: list = field(default_factory=list)             # (stream, first_line, last_line, n_rows)
    streams: dict = field(default_factory=dict)            # stream -> DataFrame

    @property
    def block_order(self) -> str:
        return " ".join(b[0] for b in self.blocks)


def parse_bytes(raw: bytes, path: str = "") -> Bits2File:
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    f = Bits2File(path=path, sha1=hashlib.sha1(raw).hexdigest(),
                  bom=raw.startswith(b"\xef\xbb\xbf"), crlf=b"\r\n" in raw,
                  lone_cr=b"\r" in raw.replace(b"\r\n", b""), header=lines[0],
                  inner_headers=0, blank_rows=0)
    rows = {s: [] for s in STREAMS}
    cur, block_id = None, -1
    for ln, line in enumerate(lines[1:], start=2):
        if line.strip(", ") == "":
            if line != "":
                f.blank_rows += 1
            continue
        p = line.split(",")
        if p[0] in ("t", "a") and (p[1:4] == ["x", "y", "z"] or p[1:3] == ["bpm", "a"]):
            f.inner_headers += 1
            continue
        if len(p) >= 4 and p[3] == "hrt" and p[1] != "":
            s, vals, aux = "hrt", [p[1]], p[2]
        elif len(p) >= 6 and p[5] in IMU_STREAMS and "" not in p[1:4]:
            s, vals, aux = p[5], p[1:4], p[4]
        else:
            f.malformed.append((ln, line[:80]))
            continue
        try:
            t = float(p[0])
            vals = [float(v) for v in vals]
        except ValueError:
            f.malformed.append((ln, line[:80]))
            continue
        if s != cur:
            block_id += 1
            f.blocks.append([s, ln, ln, 0])
            cur = s
        f.blocks[-1][2] = ln
        f.blocks[-1][3] += 1
        rows[s].append([ln, block_id, p[0], t, *vals, aux])
    f.blocks = [tuple(b) for b in f.blocks]
    for s in STREAMS:
        cols = ["line", "block", "t_raw", "t"] + (["x", "y", "z"] if s in IMU_STREAMS else ["bpm"]) + \
               (["accuracy"] if s in IMU_STREAMS else ["status"])
        f.streams[s] = pd.DataFrame(rows[s], columns=cols)
    return f


def parse_file(path: Path | str) -> Bits2File:
    path = Path(path)
    return parse_bytes(path.read_bytes(), str(path))


def values_hash(df: pd.DataFrame) -> str:
    """Hash of a stream's VALUES only (no timestamps), to find copies whose timestamps differ."""
    cols = [c for c in ("x", "y", "z", "bpm") if c in df.columns]
    return hashlib.sha1(np.ascontiguousarray(df[cols].to_numpy(dtype=float)).tobytes()).hexdigest()
