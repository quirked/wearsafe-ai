"""D00a: folder map of data/raw/<dataset>/ (read-only).

Prints a depth-limited tree, file counts by extension, total size per dataset
and size per subject folder, and the contents listing of every .zip archive
(listing only; nothing is extracted).

Usage (from repo root):  python scripts/inspect/folder_map.py [--depth 3]
"""
import argparse
import collections
import os
import zipfile
from pathlib import Path

RAW = Path("data/raw")
DATASETS = ["ppg_dalia", "wesad", "bits2"]


def human(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def dir_size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def ext_of(name):
    suffix = Path(name).suffix.lower()
    return suffix if suffix else "(none)"


def print_tree(root, depth, max_entries=25):
    def walk(p, level):
        if level > depth:
            return
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        for i, e in enumerate(entries):
            if i == max_entries:
                print("  " * level + f"... ({len(entries) - max_entries} more entries)")
                break
            tag = "/" if e.is_dir() else f"  [{human(e.stat().st_size)}]"
            print("  " * level + e.name + tag)
            if e.is_dir():
                walk(e, level + 1)
    print(root.name + "/")
    walk(root, 1)


def subject_folders(ds_root):
    """Folders that look like subject folders (S<n> or user<n>), anywhere below ds_root."""
    out = []
    for p in sorted(ds_root.rglob("*")):
        if p.is_dir() and (p.name[:1] == "S" and p.name[1:].isdigit() or p.name.startswith("user")):
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=3)
    args = ap.parse_args()

    for ds in DATASETS:
        root = RAW / ds
        print("=" * 78)
        print(f"DATASET {ds}   total size on disk: {human(dir_size(root))}")
        print("=" * 78)
        print_tree(root, args.depth)

        exts = collections.Counter(ext_of(f.name) for f in root.rglob("*") if f.is_file())
        print("\nFile counts by extension:", dict(sorted(exts.items())))

        print("\nSize per subject folder:")
        for s in subject_folders(root):
            n_files = sum(1 for f in s.iterdir() if f.is_file())
            print(f"  {s.relative_to(root)}: {n_files} files, {human(dir_size(s))}")

        print("\nZip archives (listing only, not extracted):")
        for z in sorted(root.rglob("*.zip")):
            with zipfile.ZipFile(z) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
                total = sum(i.file_size for i in infos)
                zexts = collections.Counter(ext_of(i.filename) for i in infos)
                print(f"  {z.relative_to(root)}: {len(infos)} files, uncompressed {human(total)}, "
                      f"by ext {dict(sorted(zexts.items()))}")
        print()


if __name__ == "__main__":
    main()
