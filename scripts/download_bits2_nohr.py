"""Download the BITS-2 website's "Data without Heart Rate Readings" CSVs (D00b, user decision 11).

Source page: https://shamanx86.github.io/fall_detection_data/ . Its JavaScript builds per-file links as
  <base>/Dataset_no_heart/{adl,fall}/user<N>/user<N>_{adl,fall}<K>.csv
File names are taken from the existing Zenodo copy (data/raw/bits2/Dataset), so odd names such as
user31_.fall1.csv are requested exactly as they exist. The website's own JS would build
user31_fall1.csv for those; that name is also tried and its status recorded.

Writes ONLY into data/raw/bits2_website_nohr/ (new folder, never overwrites a file) and
metadata/bits2_nohr_download.csv (refuses to overwrite).

Usage (from repo root):  python scripts/download_bits2_nohr.py
"""
import csv
import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://shamanx86.github.io/fall_detection_data/Dataset_no_heart/"
SRC = Path("data/raw/bits2/Dataset")
DEST = Path("data/raw/bits2_website_nohr/Dataset_no_heart")
LOG = Path("metadata/bits2_nohr_download.csv")


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def main():
    if LOG.exists():
        raise FileExistsError(f"{LOG} exists; refusing to overwrite")
    rels = sorted(p.relative_to(SRC).as_posix() for p in SRC.rglob("*.csv"))
    rows = []
    for i, rel in enumerate(rels, 1):
        targets = [rel]
        name = rel.rsplit("/", 1)[1]
        if "_." in name:  # also try the name the website's JS would build
            targets.append(rel.replace("_.", "_"))
        for t in targets:
            out = DEST / t
            url = BASE + t
            if out.exists():
                raise FileExistsError(f"{out} exists; refusing to overwrite")
            status, body = fetch(url)
            if status == 200:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(body)
            rows.append({"zenodo_path": rel, "requested_path": t, "url": url, "http_status": status,
                         "bytes": len(body) if status == 200 else 0,
                         "sha1": hashlib.sha1(body).hexdigest() if status == 200 else ""})
            time.sleep(0.05)
        if i % 100 == 0 or i == len(rels):
            print(f"[{i}/{len(rels)}] last={rel} status={rows[-1]['http_status']}", flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["http_status"] == 200 for r in rows)
    print(f"requests={len(rows)} ok={ok} failed={len(rows) - ok}; wrote {LOG}", flush=True)


if __name__ == "__main__":
    main()
