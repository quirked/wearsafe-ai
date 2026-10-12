"""Checksum manifest of data/raw/ (used to prove raw data is never modified)."""
from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

FIELDS = ["path", "size_bytes", "mtime_ns", "sha256"]

# Current manifest version. Older versions are kept, never overwritten (CLAUDE.md §2.1).
#   v1 metadata/raw_checksums.csv     (D00, 2,126 files)
#   v2 metadata/raw_checksums_v2.csv  (D00b, + data/raw/bits2_website_nohr/)
#   v3 metadata/raw_checksums_v3.csv  (after D00b, + data/raw/fallalld/ and data/raw/upfall/, not inspected)
CURRENT_MANIFEST = "metadata/raw_checksums_v3.csv"


def sha256_of(path: Path, chunk: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def list_raw_files(raw_root: Path) -> list[Path]:
    """All regular files under raw_root, sorted, as paths relative to raw_root's parent's parent (repo root)."""
    return sorted(p for p in raw_root.rglob("*") if p.is_file())


def file_entry(path: Path, repo_root: Path, with_hash: bool) -> dict:
    st = path.stat()
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": sha256_of(path) if with_hash else "",
    }


def read_manifest(manifest: Path) -> dict[str, dict]:
    with open(manifest, newline="") as f:
        return {row["path"]: row for row in csv.DictReader(f)}


def write_manifest(entries: list[dict], manifest: Path) -> None:
    if manifest.exists():
        raise FileExistsError(f"{manifest} exists; write a new versioned manifest instead (CLAUDE.md §2.1)")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    tmp = manifest.with_suffix(manifest.suffix + ".partial")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(entries)
    os.replace(tmp, manifest)
