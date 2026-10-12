"""Fails if anything under data/raw/ was added, removed or modified since metadata/raw_checksums.csv.

Default (fast): exact file set + size + mtime for every file.
Full: set WEARSAFE_FULL_CHECKSUM=1 to also re-hash every file with SHA-256 (~46 GB, several minutes).
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe.raw_manifest import CURRENT_MANIFEST, file_entry, list_raw_files, read_manifest, sha256_of  # noqa: E402

MANIFEST = REPO / CURRENT_MANIFEST
RAW = REPO / "data" / "raw"
FULL = os.environ.get("WEARSAFE_FULL_CHECKSUM") == "1"


@pytest.fixture(scope="module")
def manifest():
    if not RAW.is_dir():
        pytest.skip("data/raw/ not present on this machine")
    assert MANIFEST.exists(), f"{CURRENT_MANIFEST} missing; run scripts/make_raw_manifest.py --out {CURRENT_MANIFEST}"
    return read_manifest(MANIFEST)


def test_same_file_set(manifest):
    on_disk = {p.relative_to(REPO).as_posix() for p in list_raw_files(RAW)}
    added = sorted(on_disk - manifest.keys())
    removed = sorted(manifest.keys() - on_disk)
    assert not added and not removed, f"added: {added[:20]} removed: {removed[:20]}"


def test_size_and_mtime_unchanged(manifest):
    changed = []
    for path, row in manifest.items():
        p = REPO / path
        if not p.exists():
            continue  # reported by test_same_file_set
        e = file_entry(p, REPO, with_hash=False)
        if str(e["size_bytes"]) != row["size_bytes"] or str(e["mtime_ns"]) != row["mtime_ns"]:
            changed.append(path)
    assert not changed, f"size/mtime changed: {changed[:20]}"


@pytest.mark.skipif(not FULL, reason="set WEARSAFE_FULL_CHECKSUM=1 for full SHA-256 check")
def test_sha256_unchanged(manifest):
    bad = [path for path, row in manifest.items()
           if (REPO / path).exists() and sha256_of(REPO / path) != row["sha256"]]
    assert not bad, f"content changed: {bad[:20]}"
