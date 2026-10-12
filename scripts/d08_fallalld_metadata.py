"""D08 — FallAllD record metadata from user decisions on the smoke stop (read-only on data; writes metadata):
  metadata/fallalld_label_uncertain_v1.csv : fall clips whose peak lies outside [9, 11) s at BOTH 32 Hz and
      native 238 Hz (status label_uncertain_fall), clips outside at 238 Hz only (status info_238hz_outside_32hz_inside,
      normal labels, listed for information), plus the clips kept because only the 32 Hz conversion moved the peak
      (status kept_conversion_moved_peak), with evidence (peak times at 238 and 32 Hz, peak g).
  metadata/fallalld_overlap_groups_v1.csv  : overlap_group_id for every wrist record (connected components of
      >= 1 s identical raw-sample overlaps within a subject; id = lowest record_id), plus a pairs file.
Cross-checks: pair count vs the pre-checks (1570), and 25 / 14 clip counts. Refuses to overwrite.
Usage (repo root):  python scripts/d08_fallalld_metadata.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import fallalld_io as fio  # noqa: E402
from wearsafe import motion_harmonise as mh  # noqa: E402
from wearsafe.overlap import overlap_groups, overlap_pairs, sample_codes  # noqa: E402

LU = REPO / "metadata/fallalld_label_uncertain_v1.csv"
OG = REPO / "metadata/fallalld_overlap_groups_v1.csv"
OGP = REPO / "metadata/fallalld_overlap_pairs_v1.csv"


def main():
    for p in (LU, OG, OGP):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite")
    cfg = yaml.safe_load(open(REPO / "config/fallalld_v1.yaml"))
    w, _ = fio.wrist_records(REPO)
    rows = []
    for r in w[w.kind == "fall"].itertuples():
        g = mh.counts_to_g(r.Acc, cfg["counts_per_g"])
        m238 = np.sqrt((g ** 2).sum(1))
        m32 = np.sqrt((mh.resample_238_to_32(g) ** 2).sum(1))
        t238, t32 = m238.argmax() / cfg["native_hz"], m32.argmax() / cfg["resample"]["target_hz"]
        in238, in32 = 9 <= t238 < 11, 9 <= t32 < 11
        if in238 and in32:
            continue
        if not in32 and not in238:
            status = "label_uncertain_fall"              # the 25 truly off-centre clips (user decision 3)
        elif not in32:
            status = "kept_conversion_moved_peak"        # the 14 kept clips: 238 Hz peak inside, 32 Hz outside
        else:
            status = "info_238hz_outside_32hz_inside"    # not among the 39 reviewed; normal labels; listed for info
        rows.append({"record_id": r.record_id, "subject_id": r.subject_id, "original_label": r.original_label,
                     "status": status,
                     "peak_t_238hz": round(float(t238), 4), "peak_t_32hz": round(float(t32), 4),
                     "peak_g_238hz": round(float(m238.max()), 3), "peak_g_32hz": round(float(m32.max()), 3),
                     "rule": cfg["label_uncertain"]["rule"], "decided_by": "user decision 3 on the D08 smoke stop"})
    lu = pd.DataFrame(rows).sort_values(["status", "record_id"])
    n_lu, n_keep = int((lu.status == "label_uncertain_fall").sum()), int((lu.status == "kept_conversion_moved_peak").sum())
    n_info = int((lu.status == "info_238hz_outside_32hz_inside").sum())
    print(f"label_uncertain_fall {n_lu}, kept_conversion_moved_peak {n_keep}, info_238hz_outside_32hz_inside {n_info}")
    if (n_lu, n_keep) != (25, 14):
        raise RuntimeError(f"expected 25 / 14 clips as reported to the user, got {n_lu} / {n_keep}; STOP")
    pairs = []
    for sid, g in w.groupby("subject_id"):
        pairs += overlap_pairs({r: sample_codes(a) for r, a in zip(g.record_id, g.Acc)})
        print(sid, len(pairs), flush=True)
    if len(pairs) != 1570:
        raise RuntimeError(f"expected 1570 overlap pairs (pre-checks section 6), got {len(pairs)}; STOP")
    groups = overlap_groups(w.record_id.tolist(), pairs)
    og = pd.DataFrame({"record_id": w.record_id, "subject_id": w.subject_id,
                       "overlap_group_id": [groups[r] for r in w.record_id]})
    og["group_size"] = og.groupby("overlap_group_id").record_id.transform("size")
    og["dedup_representative"] = og.record_id == og.overlap_group_id
    if og.groupby("overlap_group_id").subject_id.nunique().max() != 1:
        raise RuntimeError("an overlap group spans two subjects; STOP")
    LU.parent.mkdir(exist_ok=True)
    lu.to_csv(LU, index=False)
    og.to_csv(OG, index=False)
    pd.DataFrame(pairs, columns=["record_a", "record_b", "lag_samples_238hz", "longest_identical_run_samples"]).to_csv(OGP, index=False)
    print(f"groups: {og.overlap_group_id.nunique()} (records {len(og)}; largest group {og.group_size.max()}; "
          f"records in groups of size > 1: {(og.group_size > 1).sum()})")


if __name__ == "__main__":
    main()
