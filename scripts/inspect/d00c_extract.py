"""D00c — list the FallAllD and UP-Fall zips and extract only the allowed members (look-only milestone).

- Lists every zip member (name, size, compressed size, CRC32) WITHOUT extracting.
- Extracts allowed members into data/interim/_unzipped/{fallalld,upfall}/ (never into data/raw/).
- NEVER extracts the banned SMOTE file (CLAUDE.md §2.3); only its listing entry is recorded.
- SHA-256 of each extracted file is compared with the SHA-256 of the member streamed from the zip,
  and the zip's CRC32 is checked on extraction.
- Writes metadata/fallalld_file_manifest.csv and metadata/upfall_file_manifest.csv. Refuses to overwrite.

Usage (repo root):  python scripts/inspect/d00c_extract.py
"""
import csv
import hashlib
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BANNED = {"FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl"}
DATASETS = {
    "fallalld": {"zip": "data/raw/fallalld/fallalld.zip", "out": "data/interim/_unzipped/fallalld",
                 "manifest": "metadata/fallalld_file_manifest.csv"},
    "upfall": {"zip": "data/raw/upfall/upfall-data.zip", "out": "data/interim/_unzipped/upfall",
               "manifest": "metadata/upfall_file_manifest.csv"},
}
FIELDS = ["dataset", "zip_path", "member", "size_bytes", "compressed_bytes", "crc32", "status",
          "extracted_path", "sha256_zip_stream", "sha256_extracted", "sha256_match", "crc_match"]


def sha_stream(zf, name):
    h, crc = hashlib.sha256(), 0
    with zf.open(name) as f:
        while chunk := f.read(16 * 1024 * 1024):
            h.update(chunk)
            crc = zlib.crc32(chunk, crc)
    return h.hexdigest(), crc


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    for ds, cfg in DATASETS.items():
        out, man = REPO / cfg["out"], REPO / cfg["manifest"]
        for p in (out, man):
            if p.exists():
                raise FileExistsError(f"{p} exists; refusing to overwrite")
    for ds, cfg in DATASETS.items():
        out, rows = REPO / cfg["out"], []
        out.mkdir(parents=True)
        with zipfile.ZipFile(REPO / cfg["zip"]) as zf:
            for info in zf.infolist():
                row = {"dataset": ds, "zip_path": cfg["zip"], "member": info.filename,
                       "size_bytes": info.file_size, "compressed_bytes": info.compress_size,
                       "crc32": f"{info.CRC:08x}"}
                if info.filename in BANNED:
                    row.update(status="BANNED_not_extracted_not_loaded (CLAUDE.md §2.3)")
                    print(f"{ds}: {info.filename} {info.file_size} B — BANNED, listed only", flush=True)
                    rows.append(row)
                    continue
                if "/" in info.filename or info.filename.startswith(".."):
                    raise ValueError(f"unexpected member path {info.filename!r}")
                target = out / info.filename
                sha_zip, crc = sha_stream(zf, info.filename)
                with zf.open(info.filename) as src, open(target, "wb") as dst:
                    while chunk := src.read(16 * 1024 * 1024):
                        dst.write(chunk)
                sha_ex = sha_file(target)
                target.chmod(0o444)
                row.update(status="extracted", extracted_path=str(target.relative_to(REPO)),
                           sha256_zip_stream=sha_zip, sha256_extracted=sha_ex,
                           sha256_match=sha_zip == sha_ex, crc_match=crc == info.CRC)
                print(f"{ds}: {info.filename} {info.file_size} B sha256 match={sha_zip == sha_ex} "
                      f"crc match={crc == info.CRC}", flush=True)
                if sha_zip != sha_ex or crc != info.CRC:
                    raise RuntimeError(f"{ds}: checksum mismatch for {info.filename}")
                rows.append(row)
        with open(REPO / cfg["manifest"], "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {cfg['manifest']}", flush=True)


if __name__ == "__main__":
    main()
