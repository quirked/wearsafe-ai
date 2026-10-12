"""D02 smoke report: auto-generated tables + boundary plots (no hand-typed numbers).

Reads data/interim/ppg_dalia/{normalized_signals,windows}_<tag>/ and writes
  reports/D02_ppg_dalia_<tag>_tables.md
  reports/figures/D02_<tag>/<subject>_boundary.png
Optionally compares every output table with a second, independent run (--compare-root) for determinism.
Refuses to overwrite.

Usage (repo root):  python scripts/d02_smoke_report.py --tag smoke_v1 [--compare-root DIR]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import ppg_dalia_io as io  # noqa: E402
from wearsafe import windowing as wn  # noqa: E402

BOUNDARY_LABEL = "stairs"     # boundary shown = first onset of this activity (present in every subject)
HALF_SPAN_S = 120             # ±2 min around the boundary (user request C)
WINDOW_NAMES = ("motion_2s", "context_5s", "physiology_30s")


def md(df, floatfmt=None):
    df = df.copy()
    if floatfmt:
        for c in df.select_dtypes("float").columns:
            df[c] = df[c].map(lambda v: format(v, floatfmt))
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def d00a_label_seconds():
    """Per-subject label seconds from the D00a report table (§1.4), parsed, for cross-checking."""
    text = (REPO / "reports/D00a_data_inventory.md").read_text()
    sec = text[text.index("Seconds per activity code (pkl)"):]
    rows = {}
    for line in sec.splitlines()[2:]:
        if not line.startswith("| S"):
            if rows:
                break
            continue
        cells = [c.strip().strip("*") for c in line.strip("|").split("|")]
        rows[int(cells[0][1:])] = [int(c) for c in cells[1:10]]
    return rows


def compare_dirs(a: Path, b: Path):
    out = []
    for pa in sorted(a.rglob("*.parquet")) + sorted(a.rglob("*.csv")):
        pb = b / pa.relative_to(a)
        if not pb.exists():
            out.append((str(pa.relative_to(a)), "missing in comparison run"))
            continue
        da = pd.read_parquet(pa) if pa.suffix == ".parquet" else pd.read_csv(pa)
        db = pd.read_parquet(pb) if pb.suffix == ".parquet" else pd.read_csv(pb)
        out.append((str(pa.relative_to(a)), "identical" if da.equals(db) else "DIFFERENT"))
    return out


def boundary_plot(subject_dir, windows, sid, maps, fig_path):
    act = pd.read_parquet(subject_dir / "activity.parquet", columns=["timestamp", "original_code", "original_label"])
    codes = act["original_code"].to_numpy()
    names = {int(k): v for k, v in maps["ppg_dalia"]["original_label"].items()}
    target = [c for c, n in names.items() if n == BOUNDARY_LABEL][0]
    onset_idx = int(np.flatnonzero((codes[1:] == target) & (codes[:-1] != target))[0] + 1)
    t_b = onset_idx / io.FS_ACT
    t0, t1 = max(0.0, t_b - HALF_SPAN_S), t_b + HALF_SPAN_S
    acc = pd.read_parquet(subject_dir / "wrist_acc.parquet", columns=["timestamp", "x", "y", "z", "acc_saturated"])
    acc = acc[(acc.timestamp >= t0) & (acc.timestamp < t1)]
    mag = np.sqrt(acc.x ** 2 + acc.y ** 2 + acc.z ** 2)
    a = act[(act.timestamp >= t0) & (act.timestamp < t1)]
    prev_label = names[int(codes[onset_idx - 1])]

    cmap = plt.get_cmap("tab10")
    color = {lab: cmap(i % 10) for i, lab in enumerate(sorted(names.values()))}

    fig, axes = plt.subplots(5, 1, figsize=(13, 9), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1, 1.2, 1.2, 1.2]})
    axes[0].plot(acc.timestamp, mag, lw=0.5, color="0.2")
    sat = acc.acc_saturated.to_numpy()
    axes[0].plot(acc.timestamp[sat], mag[sat], "r.", ms=3, label="acc_saturated")
    axes[0].set_ylabel("|ACC| m/s²")
    axes[0].legend(loc="upper right", fontsize=8)
    for lab in sorted(set(a.original_label)):
        m = a.original_label == lab
        axes[1].scatter(a.timestamp[m], np.zeros(m.sum()), s=4, color=color[lab], label=lab, marker="|")
    axes[1].set_yticks([])
    axes[1].set_ylabel("activity\n(4 Hz)")
    axes[1].legend(loc="upper right", fontsize=8, ncol=4)
    for ax, name in zip(axes[2:], WINDOW_NAMES):
        w = windows[name]
        w = w[(w.subject_id == sid) & (w.window_end > t0) & (w.window_start < t1)]
        for i, r in enumerate(w.itertuples()):
            y = i % 2
            ax.plot([r.window_start, r.window_end], [y, y], lw=5, color=color[r.original_label],
                    solid_capstyle="butt")
            if r.crosses_boundary:
                ax.plot([r.window_start, r.window_end], [y, y], lw=1.2, color="k", ls=":")
        ax.set_ylim(-0.7, 1.7)
        ax.set_yticks([])
        ax.set_ylabel(name.replace("_", "\n"), fontsize=8)
    for ax in axes:
        ax.axvline(t_b, color="r", lw=0.8, ls="--")
    axes[-1].set_xlabel("time from recording start (s); red dashed line = activity boundary; "
                        "dotted black = crosses_boundary")
    fig.suptitle(f"{sid}: {prev_label} → {BOUNDARY_LABEL} boundary at {t_b:.2f} s (±{HALF_SPAN_S} s); "
                 "window colour = majority label")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=110)
    plt.close(fig)
    return t_b, prev_label


def boundary_table(windows, sid, t_b, name, span):
    w = windows[name]
    w = w[(w.subject_id == sid) & (w.window_end > t_b - span) & (w.window_start < t_b + span)]
    return w[["window_id", "window_start", "window_end", "original_label", "label_purity", "crosses_boundary",
              "context_class", "eval_role", "acc_saturated_frac"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="smoke_v1")
    ap.add_argument("--root", default="data/interim/ppg_dalia")
    ap.add_argument("--compare-root", default=None, help="root of an independent re-run, for determinism")
    args = ap.parse_args()
    root = REPO / args.root
    norm, win = root / f"normalized_signals_{args.tag}", root / f"windows_{args.tag}"
    out_md = REPO / f"reports/D02_ppg_dalia_{args.tag}_tables.md"
    fig_dir = REPO / f"reports/figures/D02_{args.tag}"
    for p in (out_md, fig_dir):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite")
    fig_dir.mkdir(parents=True)
    maps = yaml.safe_load(open(REPO / "config/label_maps.yaml"))
    cfg = yaml.safe_load(open(REPO / "config/windowing_v1.yaml"))
    names = {int(k): v for k, v in maps["ppg_dalia"]["original_label"].items()}
    windows = {n: pd.read_parquet(win / f"{n}.parquet") for n in WINDOW_NAMES}
    run_n = json.loads((norm / "run_info.json").read_text())
    checks = json.loads((norm / "checks.json").read_text()) + json.loads((win / "checks.json").read_text())
    d00a = d00a_label_seconds()
    S = []
    S.append(f"# D02 smoke tables ({args.tag}) — auto-generated by scripts/d02_smoke_report.py\n")
    S.append(f"Inputs: `{norm.relative_to(REPO)}`, `{win.relative_to(REPO)}`. "
             f"Normalisation commit {run_n['git_commit'][:7]}.\n")

    S.append("## 1. Invariant checks\n")
    ck = pd.DataFrame(checks)
    S.append(f"{int(ck.passed.sum())} of {len(ck)} checks passed.\n")
    S.append(md(ck.assign(passed=ck.passed.map({True: "pass", False: "FAIL"}))[["subject_id", "check", "passed"]]
                .drop_duplicates()) + "\n")

    S.append("## 2. Recordings\n")
    rows = []
    for subj in run_n["subjects_summary"]:
        rows.append({"subject_id": subj["subject_id"], "duration_s": subj["duration_s"], "acc samples": subj["n_acc"],
                     "bvp samples": subj["n_bvp"], "activity samples": subj["n_activity"],
                     "hr_ref values": subj["n_hr_ref"],
                     "expected hr_ref": io.expected_hr_ref_count(subj["duration_s"]),
                     "acc_saturated (% samples)": round(100 * subj["acc_saturated_frac"], 4)})
    S.append(md(pd.DataFrame(rows)) + "\n")

    S.append("## 3. Label seconds: Layer A vs D00a report table\n")
    rows = []
    for subj in run_n["subjects_summary"]:
        n = int(subj["subject_id"][-2:])
        for code in range(9):
            lab = names[code]
            got = subj["label_seconds"].get(lab, 0.0)
            ref = d00a[n][code]
            rows.append({"subject_id": subj["subject_id"], "label": lab, "Layer A (s)": got, "D00a table (s)": ref,
                         "abs diff (s)": round(abs(got - ref), 2)})
    t = pd.DataFrame(rows)
    S.append(f"Max abs difference: {t['abs diff (s)'].max()} s (D00a rounded to whole seconds).\n")
    S.append(md(t) + "\n")

    S.append("## 4. Window counts (expected = floor((D − w)/step) + 1)\n")
    rows = []
    for subj in run_n["subjects_summary"]:
        for name, spec in cfg["tasks"].items():
            w = windows[name][windows[name].subject_id == subj["subject_id"]]
            rows.append({"subject_id": subj["subject_id"], "window": name, "n": len(w),
                         "expected": wn.expected_count(subj["duration_s"], spec["length_s"], spec["step_s"]),
                         "crosses_boundary (%)": round(100 * w.crosses_boundary.mean(), 2),
                         "min purity": round(w.label_purity.min(), 3),
                         "has_hr_ref (%)": round(100 * w.has_hr_ref.mean(), 2)})
    S.append(md(pd.DataFrame(rows)) + "\n")

    S.append("## 5. Windows per eval_role\n")
    for name in WINDOW_NAMES:
        t = windows[name].groupby(["subject_id", "eval_role"]).size().unstack(fill_value=0).reset_index()
        S.append(f"**{name}**\n\n" + md(t) + "\n")

    S.append("## 6. Windows per majority label (per subject)\n")
    for name in WINDOW_NAMES:
        t = windows[name].groupby(["subject_id", "original_label"]).size().unstack(fill_value=0).reset_index()
        S.append(f"**{name}**\n\n" + md(t) + "\n")

    S.append("## 7. Saturation summary (fraction of ACC samples at the E4 rail)\n")
    rows = []
    for d in sorted(p for p in norm.iterdir() if p.is_dir()):
        acc = pd.read_parquet(d / "wrist_acc.parquet", columns=["original_label", "acc_saturated"])
        g = acc.groupby("original_label")["acc_saturated"].agg(["mean", "size"]).reset_index()
        for r in g.itertuples():
            rows.append({"subject_id": d.name, "label": r.original_label, "acc samples": int(r[3]),
                         "saturated (%)": round(100 * r[2], 3)})
    S.append(md(pd.DataFrame(rows)) + "\n")
    t = windows["motion_2s"].groupby("subject_id")["acc_saturated_frac"].agg(
        windows_with_any=lambda s: round(100 * (s > 0).mean(), 2), max_frac="max").reset_index()
    S.append("Motion 2 s windows containing ≥1 saturated sample (%):\n\n" + md(t) + "\n")

    S.append("## 8. Boundary views (user request C)\n")
    S.append(f"Boundary = first onset of `{BOUNDARY_LABEL}`; plot spans ±{HALF_SPAN_S} s; tables list windows "
             "overlapping ±10 s (motion, context) or ±30 s (physiology) of the boundary.\n")
    for d in sorted(p for p in norm.iterdir() if p.is_dir()):
        fig = fig_dir / f"{d.name}_boundary.png"
        t_b, prev = boundary_plot(d, windows, d.name, maps, fig)
        S.append(f"### {d.name}: {prev} → {BOUNDARY_LABEL} at {t_b:.2f} s\n")
        S.append(f"![{d.name} boundary](figures/D02_{args.tag}/{fig.name})\n")
        for name, span in (("motion_2s", 10), ("context_5s", 10), ("physiology_30s", 30)):
            S.append(f"**{name}**\n\n" + md(boundary_table(windows, d.name, t_b, name, span), ".3f") + "\n")

    if args.compare_root:
        S.append("## 9. Determinism (independent re-run compared table by table)\n")
        cr = Path(args.compare_root)
        res = compare_dirs(norm, cr / norm.name) + compare_dirs(win, cr / win.name)
        S.append(md(pd.DataFrame(res, columns=["file", "result"])) + "\n")
        sm = pd.read_csv(REPO / f"metadata/ppg_dalia_subjects_{args.tag}.csv").equals(
            pd.read_csv(cr / f"ppg_dalia_subjects_{args.tag}.csv"))
        S.append(f"metadata/ppg_dalia_subjects_{args.tag}.csv: {'identical' if sm else 'DIFFERENT'}\n")

    out_md.write_text("\n".join(S))
    print(f"wrote {out_md} and {fig_dir}")


if __name__ == "__main__":
    main()
