"""D00a: read-only inspection of BITS-2 (data/raw/bits2/Dataset).

What the files turned out to be (verified, see reports/D00a_data_inventory.md):
  Dataset/{adl,fall}/user<N>/user<N>_{adl,fall}<K>.csv, header 't,x,y,z,a,'.
  Each file is a stack of sensor blocks. IMU rows: t,x,y,z,accuracy,<sensor> with
  sensor in {acc, acg, gyro, mgm}. Heart-rate rows: t,<bpm>,<status>,hrt,,  .

For every file this script records: naming pattern, header variant, line endings,
rows per stream, block order, repeated header lines, malformed rows, timestamp
precision (significant digits as written), timestamp span and monotonicity per
stream, value stats, HR status codes, and whether the HR and IMU time spans overlap.
It then prints summary tables (users, files per user, naming anomalies, per-index
stats, rate estimates, duplicate-content checks).

Usage (from repo root):  python scripts/inspect/inspect_bits2.py
"""
import collections
import hashlib
import itertools
import re
from pathlib import Path

import numpy as np

ROOT = Path("data/raw/bits2/Dataset")
IMU = ("acc", "acg", "gyro", "mgm")
NAME_RE = re.compile(r"^user(\d+)_(\.?)(adl|fall)(\d+)\.csv$")
SCI_RE = re.compile(r"^(\d)(?:\.(\d+))?E\+(\d+)$")


def sig_digits(t):
    """Significant digits of a timestamp string as written in the file."""
    m = SCI_RE.match(t)
    if m:
        return 1 + len(m.group(2) or "")
    if t.isdigit():
        return len(t.rstrip("0"))
    return None


def parse_file(path):
    raw = path.read_bytes()
    info = {"bom": raw.startswith(b"\xef\xbb\xbf"),
            "crlf": b"\r\n" in raw,
            "lone_cr": b"\r" in raw.replace(b"\r\n", b""),
            "sha1": hashlib.sha1(raw).hexdigest()}
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    info["header"] = lines[0]
    streams = {s: [] for s in IMU + ("hrt",)}
    status = {s: collections.Counter() for s in IMU + ("hrt",)}
    digits = collections.Counter()
    order, malformed, inner_headers, blank = [], [], 0, 0
    for i, line in enumerate(lines[1:], start=2):
        if line == "":
            blank += 1
            continue
        p = line.split(",")
        # IMU block header 't,x,y,z,a,' or HR block header 't,bpm,a,,,'
        if p[0] in ("t", "a") and (p[1:4] == ["x", "y", "z"] or p[1:3] == ["bpm", "a"]):
            inner_headers += 1
            info.setdefault("inner_header_kinds", collections.Counter())[",".join(p[:3])] += 1
            order.append("HEADER")
            continue
        if len(p) >= 4 and p[3] == "hrt":
            s, vals, st = "hrt", (p[1], p[2] or "nan"), p[2]
        elif len(p) >= 6 and p[5] in IMU:
            s, vals, st = p[5], (p[1], p[2], p[3]), p[4]
        else:
            malformed.append((i, line[:60]))
            continue
        try:
            row = [float(p[0])] + [float(v) for v in vals]
        except ValueError:
            malformed.append((i, line[:60]))
            continue
        streams[s].append(row)
        status[s][st] += 1
        digits[(s, sig_digits(p[0]))] += 1
        order.append(s)
    info["order"] = [k for k, _ in itertools.groupby(order)]
    info["inner_headers"] = inner_headers
    info["malformed"] = malformed
    info["blank"] = blank
    info["digits"] = digits
    info["status"] = status
    info["streams"] = {s: np.array(v) if v else np.empty((0, 4 if s in IMU else 3))
                       for s, v in streams.items()}
    return info


def main():
    files = sorted(ROOT.glob("*/*/*.csv"))
    print(f"Total CSV files: {len(files)}")
    records = []
    name_anomalies, unparsed_names = [], []
    for f in files:
        group_dir, user_dir = f.parent.parent.name, f.parent.name
        m = NAME_RE.match(f.name)
        if not m:
            unparsed_names.append(str(f))
            continue
        uid, dot, group, idx = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
        if dot or group != group_dir or user_dir != f"user{uid}":
            name_anomalies.append(str(f.relative_to(ROOT)))
        info = parse_file(f)
        info.update(path=str(f.relative_to(ROOT)), user=uid, group=group, idx=idx)
        records.append(info)

    # ---------- users and files ----------
    print("\n== Users and files")
    for g in ("adl", "fall"):
        users = sorted({r["user"] for r in records if r["group"] == g})
        per_user = collections.Counter(r["user"] for r in records if r["group"] == g)
        idxs = sorted({r["idx"] for r in records if r["group"] == g})
        print(f"{g}: {len(users)} users {users[0]}..{users[-1]}; missing in range: "
              f"{sorted(set(range(1, max(users) + 1)) - set(users))}; indices {idxs}; "
              f"files/user distribution {dict(collections.Counter(per_user.values()))}")
        for u in users:
            have = sorted(r["idx"] for r in records if r["group"] == g and r["user"] == u)
            if have != idxs:
                print(f"  user{u} {g}: indices {have}")
    print(f"Filename anomalies (dot before label or folder mismatch): {name_anomalies}")
    print(f"Filenames not matching pattern: {unparsed_names}")

    # ---------- format ----------
    print("\n== File format variants")
    print("header variants:", collections.Counter(r["header"][:20] for r in records))
    print("BOM:", sum(r["bom"] for r in records), " CRLF:", sum(r["crlf"] for r in records),
          " lone CR:", [r["path"] for r in records if r["lone_cr"]])
    print("files with repeated header lines inside:", sum(r["inner_headers"] > 0 for r in records))
    kinds = collections.Counter()
    for r in records:
        kinds.update(r.get("inner_header_kinds", {}))
    print("inner header kinds:", dict(kinds))
    print("block-order patterns:")
    pat = collections.Counter(" ".join(r["order"]) for r in records)
    for k, v in pat.most_common():
        ex = next(r["path"] for r in records if " ".join(r["order"]) == k)
        print(f"  {v:4d} | {k} | e.g. {ex}")
    print("files with malformed rows:")
    for r in records:
        if r["malformed"]:
            print(f"  {r['path']}: {len(r['malformed'])} rows, first {r['malformed'][:2]}")
    blocks_repeated = [r["path"] for r in records
                       if any(r["order"].count(s) > 1 for s in IMU + ("hrt",))]
    print("files where a sensor block appears more than once:", blocks_repeated)

    # ---------- streams ----------
    print("\n== Streams: presence and row counts")
    for s in IMU + ("hrt",):
        n = np.array([len(r["streams"][s]) for r in records])
        print(f"{s}: present in {int((n > 0).sum())}/{len(records)} files; rows/file "
              f"min={n.min()} median={np.median(n):.0f} max={n.max()} total={n.sum()}")

    for g in ("adl", "fall"):
        h = np.array([len(r["streams"]["hrt"]) for r in records if r["group"] == g])
        a = np.array([len(r["streams"]["acc"]) for r in records if r["group"] == g])
        z = sum(int((r["streams"]["hrt"][:, 1] == 0).any()) for r in records if r["group"] == g)
        print(f"{g}: files with HR rows <5: {(h < 5).sum()}, <10: {(h < 10).sum()}; "
              f"files with acc rows <50: {(a < 50).sum()}; files containing a 0 bpm row: {z}")

    print("\n== Timestamp precision (significant digits as written in the CSV)")
    dig = collections.Counter()
    for r in records:
        dig.update(r["digits"])
    for s in IMU + ("hrt",):
        row = {d: c for (ss, d), c in dig.items() if ss == s}
        print(f"{s}: {dict(sorted(row.items(), key=lambda x: (x[0] is None, x[0] or 0)))}")
    full_prec = [r["path"] for r in records
                 if any(d is not None and d >= 9 for (_, d) in r["digits"])]
    print(f"files with any timestamp of >=9 significant digits: {len(full_prec)} {full_prec[:10]}")

    print("\n== Timestamp magnitude (raw t values; unit inferred as ns)")
    tmins = np.array([min(r["streams"][s][:, 0].min() for s in IMU + ("hrt",) if len(r["streams"][s]))
                      for r in records])
    print(f"per-file min t: min={tmins.min():.3g} median={np.median(tmins):.3g} max={tmins.max():.3g}")

    print("\n== Value statistics over all files (x, y, z / bpm)")
    for s in IMU:
        a = np.concatenate([r["streams"][s][:, 1:] for r in records if len(r["streams"][s])])
        mag = np.linalg.norm(a, axis=1)
        print(f"{s}: min={a.min(0).round(3).tolist()} max={a.max(0).round(3).tolist()} "
              f"mean={a.mean(0).round(3).tolist()} |v| median={np.median(mag):.3f} "
              f"|v| p99={np.percentile(mag, 99):.3f} NaN={int(np.isnan(a).sum())}")
    hr = np.concatenate([r["streams"]["hrt"][:, 1] for r in records])
    print(f"hrt bpm: min={hr.min()} max={hr.max()} mean={hr.mean():.1f} "
          f"n==0: {(hr == 0).sum()} n<30: {(hr < 30).sum()} n>220: {(hr > 220).sum()} NaN={int(np.isnan(hr).sum())}")
    st = collections.Counter()
    for r in records:
        st.update({f"hrt:{k}": v for k, v in r["status"]["hrt"].items()})
        for s in IMU:
            st.update({f"imu:{k}": v for k, v in r["status"][s].items()})
    print("status/accuracy column values:", dict(st))
    print("hrt rows with status -1 per group:",
          {g: sum(r["status"]["hrt"].get("-1", 0) for r in records if r["group"] == g) for g in ("adl", "fall")})

    print("\n== Time spans per stream (coarse: limited by timestamp precision)")
    nonmono = collections.Counter()
    rate_rows = []
    for r in records:
        spans = {}
        for s in IMU + ("hrt",):
            t = r["streams"][s][:, 0]
            if len(t) < 2:
                continue
            nonmono[s] += int((np.diff(t) < 0).any())
            spans[s] = ((t.max() - t.min()) / 1e9, len(t), t.min(), t.max())
        r["spans"] = spans
        if "hrt" in spans and "acc" in spans:
            hr_n = spans["hrt"][1]
            rate_rows.append((r["group"], r["idx"], {s: spans[s][1] / hr_n for s in IMU if s in spans}))
        # overlap of HR time range with acc time range
        if "hrt" in spans and "acc" in spans:
            a0, a1 = spans["acc"][2], spans["acc"][3]
            h0, h1 = spans["hrt"][2], spans["hrt"][3]
            r["overlap"] = min(a1, h1) >= max(a0, h0)
        else:
            r["overlap"] = None
    print("files with non-monotonic timestamps, per stream:", dict(nonmono))
    no_overlap = [r["path"] for r in records if r["overlap"] is False]
    print(f"files where HR time range does NOT overlap acc time range: {len(no_overlap)} {no_overlap[:20]}")

    print("\n== Rate estimates (INFERRED, see notes)")
    print("Estimate A: rows / timestamp span, only files where the 3-significant-digit rounding "
          "step is <= 10% of the span")
    for s in IMU + ("hrt",):
        est = []
        for r in records:
            if s not in r["spans"] or r["spans"][s][0] <= 0:
                continue
            span, n, t0, _ = r["spans"][s]
            step_s = 10 ** (np.floor(np.log10(max(t0, 1))) - 2) / 1e9
            if step_s <= 0.1 * span:
                est.append(n / span)
        est = np.array(est)
        if len(est):
            print(f"  {s}: qualifying files={len(est)}; Hz median={np.median(est):.2f} "
                  f"p10={np.percentile(est, 10):.2f} p90={np.percentile(est, 90):.2f}")
        else:
            print(f"  {s}: no qualifying files")
    print("Estimate B: IMU rows per HR row (= IMU Hz if HR is 1 Hz)")
    for s in IMU:
        v = np.array([d[s] for _, _, d in rate_rows if s in d])
        print(f"  {s}: median={np.median(v):.2f} p10={np.percentile(v, 10):.2f} "
              f"p90={np.percentile(v, 90):.2f} min={v.min():.2f} max={v.max():.2f}")
    print("Resolvable HR intervals (consecutive HR timestamps whose rounding step is <= 0.1 s):")
    dts = []
    for r in records:
        t = r["streams"]["hrt"][:, 0]
        # use only files with >=5 significant digits on hrt rows
        if r["digits"].get(("hrt", 6), 0) + r["digits"].get(("hrt", 5), 0) > 5:
            dts.extend(np.diff(np.sort(t)) / 1e9)
    if dts:
        dts = np.array(dts)
        print(f"  n={len(dts)} median dt={np.median(dts):.3f}s p10={np.percentile(dts, 10):.3f} "
              f"p90={np.percentile(dts, 90):.3f}")
    print("Resolvable IMU intervals (rows with >=5 significant digits, consecutive same stream):")
    for s in IMU:
        dts, srcs = [], []
        for r in records:
            n_hi = sum(c for (ss, d), c in r["digits"].items() if ss == s and d is not None and d >= 5)
            if n_hi > 50:
                t = r["streams"][s][:, 0]
                d = np.diff(t) / 1e9
                dts.extend(d[(d > 0) & (d < 1)])
                srcs.append(r["path"])
        if dts:
            dts = np.array(dts)
            print(f"  {s}: n={len(dts)} from {srcs}: median dt={np.median(dts) * 1000:.1f} ms "
                  f"(~{1 / np.median(dts):.1f} Hz) p10={np.percentile(dts, 10) * 1000:.1f} ms "
                  f"p90={np.percentile(dts, 90) * 1000:.1f} ms")
    print("HR coverage of the recording (hrt span / acc span; files where both spans >= 30 s):")
    cov = np.array([r["spans"]["hrt"][0] / r["spans"]["acc"][0] for r in records
                    if "hrt" in r["spans"] and "acc" in r["spans"]
                    and r["spans"]["hrt"][0] >= 30 and r["spans"]["acc"][0] >= 30])
    print(f"  n={len(cov)} median={np.median(cov):.2f} p10={np.percentile(cov, 10):.2f} "
          f"p90={np.percentile(cov, 90):.2f}")
    print("HR rows with status -1 / 0 / 3: bpm values")
    for code in ("-1", "0", "3"):
        n_files = sum(1 for r in records if r["status"]["hrt"].get(code))
        h = np.concatenate([r["streams"]["hrt"] for r in records])
        b = h[h[:, 2] == float(code), 1]
        print(f"  status {code}: {len(b)} rows in {n_files} files; bpm min={b.min()} "
              f"median={np.median(b)} max={b.max()} share==0: {(b == 0).mean():.3f}")

    print("\n== Per label index: files, HR rows (~seconds if HR is 1 Hz), acc rows")
    for g in ("adl", "fall"):
        for k in sorted({r["idx"] for r in records if r["group"] == g}):
            rs = [r for r in records if r["group"] == g and r["idx"] == k]
            h = np.array([len(r["streams"]["hrt"]) for r in rs])
            a = np.array([len(r["streams"]["acc"]) for r in rs])
            print(f"  {g}{k}: files={len(rs)} HR rows median={np.median(h):.0f} "
                  f"[{h.min()}-{h.max()}]  acc rows median={np.median(a):.0f} [{a.min()}-{a.max()}]")

    print("\n== Duplicate content")
    by_hash = collections.defaultdict(list)
    for r in records:
        by_hash[r["sha1"]].append(r["path"])
    dups = [v for v in by_hash.values() if len(v) > 1]
    print(f"byte-identical files: {len(dups)} groups {dups}")
    blk = collections.defaultdict(list)
    for r in records:
        for s in IMU + ("hrt",):
            a = r["streams"][s]
            if len(a) >= 20:
                blk[(s, hashlib.sha1(a.tobytes()).hexdigest())].append(r["path"])
    dup_blocks = [(k[0], v) for k, v in blk.items() if len(v) > 1]
    print(f"identical sensor blocks shared by >1 file: {len(dup_blocks)}")
    for s, v in dup_blocks[:40]:
        print(f"  {s}: {v}")

    print("\n== Per-file table (path | acc acg gyro mgm hrt rows | HR bpm min-max | "
          "inner headers | malformed | HR/acc overlap)")
    for r in records:
        n = [len(r["streams"][s]) for s in IMU + ("hrt",)]
        h = r["streams"]["hrt"][:, 1]
        hr_rng = f"{h.min():.0f}-{h.max():.0f}" if len(h) else "-"
        print(f"{r['path']} | {' '.join(map(str, n))} | {hr_rng} | {r['inner_headers']} | "
              f"{len(r['malformed'])} | {r['overlap']}")


if __name__ == "__main__":
    main()
