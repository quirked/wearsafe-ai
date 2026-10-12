"""Identical-overlap search between records and overlap groups (D08; config/fallalld_v1.yaml overlap_groups).

Two records overlap if they share >= min_run consecutive identical samples (all axes) at some lag. Candidates come
from a sampled key of each block of length `block` (5 sample codes + block sum) and are verified exactly. Runs of
>= 2*block - 1 samples are always found; shorter runs only if they cover an indexed block.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

PICK = (0, 59, 118, 177, 237)


def sample_codes(acc: np.ndarray) -> np.ndarray:
    a = np.asarray(acc).astype(np.int64) + 32768
    return (a[:, 0] << 32) | (a[:, 1] << 16) | a[:, 2]


def block_keys(v: np.ndarray, block: int = 238) -> list:
    pick = np.array([p for p in PICK if p < block] + [block - 1])
    cs = np.concatenate([[0], np.cumsum(v % 1000003)])
    n = len(v) - block + 1
    if n <= 0:
        return []
    sums = cs[block:block + n] - cs[:n]
    cols = np.stack([v[p:p + n] for p in pick], axis=1)
    return [tuple(r) + (s,) for r, s in zip(cols.tolist(), sums.tolist())]


def longest_identical_run(a: np.ndarray, b: np.ndarray, lag: int) -> int:
    """a[t] == b[t - lag]; longest run of equal codes over the overlap."""
    oa, ob = (a[lag:], b[:len(a) - lag]) if lag >= 0 else (a[:len(a) + lag], b[-lag:])
    eq = np.concatenate([[False], oa == ob, [False]]).astype(np.int8)
    d = np.diff(eq)
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return int((ends - starts).max()) if len(starts) else 0


def overlap_pairs(records: dict, block: int = 238, min_run: int = 238) -> list[tuple[str, str, int, int]]:
    """records: {record_id: codes}. Returns (record_a, record_b, lag, longest_run) with record_a < record_b."""
    index = defaultdict(list)
    for r, v in records.items():
        for off, k in enumerate(block_keys(v, block)[::block]):
            index[k].append((r, off * block))
    found = {}
    for r, v in records.items():
        for off, k in enumerate(block_keys(v, block)):
            for (r2, off2) in index.get(k, ()):
                if r2 == r:
                    continue
                a, b = sorted((r, r2))
                lag = (off - off2) if a == r else (off2 - off)
                found.setdefault((a, b, lag), None)
    best = {}
    for (a, b, lag) in found:
        run = longest_identical_run(records[a], records[b], lag)
        if run >= min_run and run > best.get((a, b), (0, 0))[1]:
            best[(a, b)] = (lag, run)
    return sorted((a, b, lag, run) for (a, b), (lag, run) in best.items())


def overlap_groups(record_ids: list[str], pairs) -> dict[str, str]:
    """Union-find over pairs; group id = lowest record_id in the connected component."""
    parent = {r: r for r in record_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, *_ in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    members = defaultdict(list)
    for r in record_ids:
        members[find(r)].append(r)
    return {r: min(m) for m in members.values() for r in m}
