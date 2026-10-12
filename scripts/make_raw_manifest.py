"""Create metadata/raw_checksums.csv: path, size, mtime and SHA-256 of every file in data/raw/.

Refuses to overwrite an existing manifest (CLAUDE.md §2.1). Read-only on data/raw/.

Usage (from repo root):  python scripts/make_raw_manifest.py [--out metadata/raw_checksums.csv]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wearsafe.raw_manifest import file_entry, list_raw_files, write_manifest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="metadata/raw_checksums.csv")
    args = ap.parse_args()
    files = list_raw_files(REPO / "data" / "raw")
    total = sum(p.stat().st_size for p in files)
    print(f"{len(files)} files, {total / 1e9:.2f} GB", flush=True)
    t0, done, entries = time.time(), 0, []
    for i, p in enumerate(files, 1):
        entries.append(file_entry(p, REPO, with_hash=True))
        done += p.stat().st_size
        if p.stat().st_size > 100e6 or i == len(files):
            print(f"[{i}/{len(files)}] {done / 1e9:.1f} GB  {time.time() - t0:.0f}s  {p.relative_to(REPO)}",
                  flush=True)
    write_manifest(entries, REPO / args.out)
    print(f"wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
