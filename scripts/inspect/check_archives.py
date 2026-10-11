"""D00a: check that the extracted dataset folders match their zip archives (read-only).

For each archive, every member is compared with the already-extracted file on disk:
existence, size, and CRC32 (computed from the disk file, compared with the CRC stored
in the zip header, so nothing is decompressed or written). Also reports extracted
files that are not in the archive.

Usage (from repo root):  python scripts/inspect/check_archives.py
"""
import zipfile
import zlib
from pathlib import Path

RAW = Path("data/raw")
# (archive, folder the archive's member paths are relative to)
ARCHIVES = [
    (RAW / "ppg_dalia/ppg+dalia.zip", RAW / "ppg_dalia"),
    (RAW / "ppg_dalia/data.zip", RAW / "ppg_dalia"),
    (RAW / "wesad/WESAD.zip", RAW / "wesad"),
    (RAW / "bits2/full_dataset.zip", RAW / "bits2"),
]


def crc32_of(path, chunk=16 * 1024 * 1024):
    crc = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return crc & 0xFFFFFFFF
            crc = zlib.crc32(b, crc)


def main():
    for arc, base in ARCHIVES:
        print("=" * 78)
        print(f"{arc}  (members compared against {base}/)")
        with zipfile.ZipFile(arc) as zf:
            members = [i for i in zf.infolist() if not i.is_dir()]
        ok, missing, size_diff, crc_diff = 0, [], [], []
        top_dirs = set()
        for m in members:
            p = base / m.filename
            top_dirs.add(m.filename.split("/")[0])
            if not p.exists():
                missing.append(m.filename)
                continue
            if p.stat().st_size != m.file_size:
                size_diff.append((m.filename, p.stat().st_size, m.file_size))
                continue
            if crc32_of(p) != m.CRC:
                crc_diff.append(m.filename)
                continue
            ok += 1
        names = {m.filename for m in members}
        extra = []
        for d in top_dirs:
            root = base / d
            if root.is_dir():
                extra += [str(f.relative_to(base)) for f in root.rglob("*")
                          if f.is_file() and str(f.relative_to(base)) not in names]
        print(f"members={len(members)} identical={ok} missing_on_disk={len(missing)} "
              f"size_mismatch={len(size_diff)} crc_mismatch={len(crc_diff)} "
              f"extra_on_disk_not_in_archive={len(extra)}")
        for label, lst in (("missing", missing), ("size", size_diff), ("crc", crc_diff), ("extra", extra)):
            if lst:
                print(f"  {label}: {lst[:20]}")


if __name__ == "__main__":
    main()
