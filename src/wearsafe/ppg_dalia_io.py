"""PPG-DaLiA loading and Layer A normalisation (D02).

Facts used (CLAUDE.md §6, reports/D00a_data_inventory.md §1):
  - SX.pkl, Python-2 era -> pickle.load(..., encoding="latin1").
  - wrist ACC 32 Hz stored in g (exact multiples of 1/64 g; E4 range ±2 g -> counts -128..127).
  - wrist BVP 64 Hz (arbitrary units), activity 4 Hz (codes 0..8).
  - 'label' = ECG-derived HR, one value per 8 s window shifted by 2 s.
  - All signals share a common start; time = index / rate.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from wearsafe.schemas import STANDARD_GRAVITY, namespaced_subject_id

RAW_DIR = Path("data/raw/ppg_dalia/PPG_FieldStudy")
DATASET = "ppg_dalia"
FS_ACC, FS_BVP, FS_ACT = 32, 64, 4
HR_REF_WIN_S, HR_REF_SHIFT_S = 8, 2
E4_COUNTS_PER_G = 64
E4_RAIL_COUNTS = (-128, 127)          # int8 rails of the E4 ±2 g accelerometer


@dataclass
class Subject:
    number: int
    subject_id: str
    acc_g: np.ndarray        # (n, 3) float64, g
    bvp: np.ndarray          # (m,) float64, a.u.
    activity: np.ndarray     # (k,) int64 codes
    hr_ref: np.ndarray       # (l,) float64 bpm
    questionnaire: dict


def load_subject(number: int, repo: Path) -> Subject:
    """Load wrist ACC, BVP, activity and the ECG HR label of one subject (chest signals are dropped)."""
    with open(repo / RAW_DIR / f"S{number}" / f"S{number}.pkl", "rb") as f:
        obj = pickle.load(f, encoding="latin1")
    act = np.asarray(obj["activity"]).reshape(-1)
    act_int = act.astype(np.int64)
    if not np.array_equal(act_int, act):
        raise ValueError(f"S{number}: non-integer activity codes")
    return Subject(
        number=number,
        subject_id=namespaced_subject_id(DATASET, number),
        acc_g=np.asarray(obj["signal"]["wrist"]["ACC"], dtype=np.float64),
        bvp=np.asarray(obj["signal"]["wrist"]["BVP"], dtype=np.float64).reshape(-1),
        activity=act_int,
        hr_ref=np.asarray(obj["label"], dtype=np.float64).reshape(-1),
        questionnaire=dict(obj["questionnaire"]),
    )


def durations(s: Subject) -> dict:
    return {"acc": len(s.acc_g) / FS_ACC, "bvp": len(s.bvp) / FS_BVP, "activity": len(s.activity) / FS_ACT}


def expected_hr_ref_count(duration_s: float) -> int:
    return int((duration_s - HR_REF_WIN_S) // HR_REF_SHIFT_S) + 1


def acc_counts(acc_g: np.ndarray) -> tuple[np.ndarray, float]:
    """Raw E4 counts (g * 64) and the max distance from an integer (0 if the pkl really stores g)."""
    c = acc_g * E4_COUNTS_PER_G
    r = np.round(c)
    return r.astype(np.int64), float(np.max(np.abs(c - r))) if c.size else 0.0


def saturated_mask(counts: np.ndarray) -> np.ndarray:
    """Per-sample flag: any axis at an E4 rail (-128 or +127 counts). +127 may be a genuine 1.984 g reading."""
    lo, hi = E4_RAIL_COUNTS
    return np.any((counts <= lo) | (counts >= hi), axis=1)


def _ids(s: Subject) -> dict:
    return {"recording_id": f"{s.subject_id}_main", "dataset": DATASET,
            "subject_id": s.subject_id, "trial_id": "main"}


def normalize(s: Subject, label_maps: dict) -> dict[str, pd.DataFrame]:
    """Layer A tables (long format, one row per sample) for one subject."""
    pd_maps = label_maps[DATASET]
    names = {int(k): v for k, v in pd_maps["original_label"].items()}
    unknown = sorted(set(np.unique(s.activity).tolist()) - set(names))
    if unknown:
        raise ValueError(f"{s.subject_id}: unknown activity codes {unknown}")
    factor = label_maps["units"][DATASET]["wrist_acc"]["factor"]
    assert factor == STANDARD_GRAVITY
    ids = _ids(s)
    label_name = np.array([names[c] for c in range(max(names) + 1)], dtype=object)

    counts, _ = acc_counts(s.acc_g)
    n_acc = len(s.acc_g)
    acc_idx = np.arange(n_acc)
    acc = pd.DataFrame({
        **ids, "sample_idx": acc_idx, "timestamp": acc_idx / FS_ACC,
        "original_label": label_name[s.activity[acc_idx * FS_ACT // FS_ACC]],
        "sensor_location": "wrist", "sensor_name": "acc", "sampling_rate": float(FS_ACC),
        "x": s.acc_g[:, 0] * factor, "y": s.acc_g[:, 1] * factor, "z": s.acc_g[:, 2] * factor,
        "acc_saturated": saturated_mask(counts),
        "original_unit": "g", "canonical_unit": "m/s^2",
    })

    bvp_idx = np.arange(len(s.bvp))
    bvp = pd.DataFrame({
        **ids, "sample_idx": bvp_idx, "timestamp": bvp_idx / FS_BVP,
        "original_label": label_name[s.activity[bvp_idx * FS_ACT // FS_BVP]],
        "sensor_location": "wrist", "sensor_name": "bvp", "sampling_rate": float(FS_BVP),
        "scalar_value": s.bvp, "original_unit": "a.u.", "canonical_unit": "a.u.",
    })

    ctx = pd_maps["context_class"]
    roles = sample_eval_roles(label_maps)
    act_idx = np.arange(len(s.activity))
    act_names = label_name[s.activity]
    activity = pd.DataFrame({
        **ids, "sample_idx": act_idx, "timestamp": act_idx / FS_ACT,
        "sensor_name": "activity", "sampling_rate": float(FS_ACT),
        "original_code": s.activity, "original_label": act_names,
        "context_class": [ctx[n] for n in act_names],
        "eval_role": [roles[n] for n in act_names],
    })

    k = np.arange(len(s.hr_ref))
    hr_ref = pd.DataFrame({
        **ids, "k": k, "ref_window_start": (k * HR_REF_SHIFT_S).astype(float),
        "ref_window_end": (k * HR_REF_SHIFT_S + HR_REF_WIN_S).astype(float),
        "timestamp": (k * HR_REF_SHIFT_S + HR_REF_WIN_S / 2).astype(float),
        "sensor_location": "chest", "sensor_name": "hr_ref",
        "hr_ref_bpm": s.hr_ref, "original_unit": "bpm", "canonical_unit": "bpm",
        "source": "ECG-derived HR (dataset 'label'; 8 s window, 2 s shift)",
    })
    return {"wrist_acc": acc, "wrist_bvp": bvp, "activity": activity, "hr_ref": hr_ref}


def sample_eval_roles(label_maps: dict) -> dict[str, str]:
    """Per original label: 'train_candidate' if in training_v1.context, else its eval_role from the YAML."""
    m = label_maps[DATASET]
    out = {}
    for name in m["original_label"].values():
        if name in m["training_v1"]["context"]:
            out[name] = "train_candidate"
        elif name in m["eval_role"]:
            out[name] = m["eval_role"][name]
        else:
            raise ValueError(f"label {name!r} has neither a training_v1 nor an eval_role entry")
    return out


def subject_row(s: Subject) -> dict:
    q = s.questionnaire
    g = q.get("Gender")
    return {
        "subject_id": s.subject_id, "raw_folder": f"S{s.number}",
        "age_years": q.get("AGE"), "height_cm": q.get("HEIGHT"), "weight_kg": q.get("WEIGHT"),
        "gender": g.strip() if isinstance(g, str) else g, "gender_original": repr(g),
        "skin_type": q.get("SKIN"), "sport_level": q.get("SPORT"),
        "use": "analysis_only_never_model_input",
        "source": f"{RAW_DIR.as_posix()}/S{s.number}/S{s.number}.pkl['questionnaire']",
    }
