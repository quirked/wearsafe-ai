"""Data contracts for the three storage layers (docs/WearSafe_AI_Context.md §11–§15, §19–§20).

Layer A: normalized raw signals (one row per sample, long format).
Layer B: synchronized windows (one record per window, per task).
Layer C: feature tables for classical ML (one row per window).

These are contracts only. No data is read or written here.
Label vocabularies and source->derived mappings live in config/label_maps.yaml.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from typing import Optional

# ---------------------------------------------------------------------------
# Vocabularies (context doc §15, §20)
# ---------------------------------------------------------------------------
DATASETS = ("ppg_dalia", "wesad", "bits2")
SUBJECT_PREFIX = {"ppg_dalia": "PPGDALIA", "wesad": "WESAD", "bits2": "BITS2"}

CONTEXT_CLASSES = ("stationary", "low_activity", "locomotion", "vigorous_activity")
MOTION_EVENT_CLASSES = ("normal_adl", "abrupt_event_proxy")
AROUSAL_CLASSES = ("low_arousal", "high_arousal")

SENSOR_LOCATIONS = ("wrist", "chest")
# Canonical units (§20). original_unit is always kept alongside.
CANONICAL_UNITS = {
    "acc": "m/s^2",
    "gyro": "rad/s",
    "mag": "uT",
    "hr": "bpm",
    "bvp": "a.u.",  # PPG/BVP has no physical unit in the source data
    "time": "s",
}
STANDARD_GRAVITY = 9.80665  # m/s^2 per g

_SUBJECT_RE = re.compile(r"^(PPGDALIA|WESAD|BITS2)_S\d{2}$")


def namespaced_subject_id(dataset: str, raw_number: int) -> str:
    """e.g. ('wesad', 2) -> 'WESAD_S02'; ('bits2', 41) -> 'BITS2_S41' (CLAUDE.md §2.3)."""
    if dataset not in SUBJECT_PREFIX:
        raise ValueError(f"unknown dataset {dataset!r}")
    if not 0 < raw_number < 100:
        raise ValueError(f"subject number out of range: {raw_number}")
    return f"{SUBJECT_PREFIX[dataset]}_S{raw_number:02d}"


def is_valid_subject_id(subject_id: str) -> bool:
    return bool(_SUBJECT_RE.match(subject_id))


# ---------------------------------------------------------------------------
# Layer A — normalized raw signal (§12)
# ---------------------------------------------------------------------------
@dataclass
class SignalRecord:
    """One sample of one sensor. Vector sensors fill x/y/z; scalar sensors fill scalar_value."""

    recording_id: str
    dataset: str
    subject_id: str              # namespaced, e.g. PPGDALIA_S01
    trial_id: str                # session/trial within the subject
    original_label: str          # untouched source label at this sample
    event_type: Optional[str]    # e.g. "fall" / "adl" for BITS-2; None if not applicable
    sensor_location: str         # wrist / chest
    sensor_name: str             # acc, acc_with_gravity, gyro, mag, bvp, hr, ...
    sampling_rate: Optional[float]  # Hz; None if irregular/unverified (BITS-2 IMU)
    timestamp: float             # seconds from recording start
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    scalar_value: Optional[float] = None
    original_unit: str = ""
    canonical_unit: str = ""
    quality_flag: Optional[str] = None  # source status code (e.g. BITS-2 HR status), kept verbatim
    acc_saturated: Optional[bool] = None  # acc only: any axis at the sensor rail (E4: -128/+127 counts)


# ---------------------------------------------------------------------------
# Layer B — synchronized window (§13)
# ---------------------------------------------------------------------------
@dataclass
class WindowRecord:
    window_id: str
    dataset: str
    subject_id: str
    trial_id: str
    task: str                    # motion / context / arousal (§18: task-specific windows)
    window_start: float          # s from recording start
    window_end: float
    duration: float
    original_label: str
    context_class: Optional[str] = None
    motion_event_class: Optional[str] = None
    arousal_class: Optional[str] = None
    acc: Optional[list] = None   # canonical m/s^2, shape (n, 3)
    gyro: Optional[list] = None
    bvp: Optional[list] = None
    hr: Optional[list] = None
    fs_acc: Optional[float] = None
    fs_gyro: Optional[float] = None
    fs_bvp: Optional[float] = None
    fs_hr: Optional[float] = None
    has_acc: bool = False
    has_gyro: bool = False
    has_bvp: bool = False
    has_hr: bool = False
    signal_quality: dict = field(default_factory=dict)  # e.g. {"ppg_sqi": 0.7, "acc_clipped_frac": 0.0}
    missing_fraction: dict = field(default_factory=dict)
    # D02 additions (config/windowing_v1.yaml). original_label = MAJORITY original label of the window.
    recording_id: str = ""
    label_purity: Optional[float] = None    # fraction of label samples carrying the majority label
    crosses_boundary: Optional[bool] = None
    eval_role: Optional[str] = None         # train_candidate / false_alert_eval / false_alert_eval_only
    acc_saturated_frac: Optional[float] = None


# ---------------------------------------------------------------------------
# Layer C — feature table (§14)
# ---------------------------------------------------------------------------
# Identity / label columns every feature table must carry (never used as features).
FEATURE_TABLE_ID_COLUMNS = (
    "window_id", "dataset", "subject_id", "trial_id", "task",
    "window_start", "window_end",
    "original_label", "context_class", "motion_event_class", "arousal_class",
    "has_acc", "has_gyro", "has_bvp", "has_hr",
)

MOTION_FEATURES = (
    "acc_mag_mean", "acc_mag_std", "acc_mag_max", "acc_mag_p95", "acc_mag_rms",
    "acc_mag_range",
    "jerk_mean", "jerk_std", "jerk_max",
    "motion_energy", "dominant_freq", "spectral_entropy", "spectral_energy",
)
GYRO_FEATURES = ("gyro_mag_mean", "gyro_mag_std", "gyro_mag_max", "rotation_energy")
PHYSIOLOGY_FEATURES = (
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_delta", "hr_slope", "hr_rel_baseline",
    "bvp_peak_rate", "ibi_mean", "ibi_std",
    "ppg_sqi", "physiology_uncertain",
)
ALL_FEATURES = MOTION_FEATURES + GYRO_FEATURES + PHYSIOLOGY_FEATURES

# Window metadata that is label-derived, an index reference, or ground truth (D02/D03).
WINDOW_META_COLUMNS = (
    "recording_id", "duration", "majority_code", "n_distinct_labels",
    "label_purity", "crosses_boundary", "eval_role",
    "acc_i0", "acc_i1", "bvp_i0", "bvp_i1", "act_i0", "act_i1",
    "hr_ref_k0", "hr_ref_k1", "n_hr_ref", "has_hr_ref", "hr_ref_bpm",
)

# Columns that must never be used as model inputs (CLAUDE.md §2.3: no label-derived features;
# hr_ref_bpm is ECG ground truth).
FORBIDDEN_FEATURE_COLUMNS = FEATURE_TABLE_ID_COLUMNS + WINDOW_META_COLUMNS


# ---------------------------------------------------------------------------
# BITS-2 event-centred record (§19)
# ---------------------------------------------------------------------------
@dataclass
class Bits2EventRecord:
    event_id: str
    subject_id: str
    activity: str                # original file label, e.g. "fall3" / "adl7"
    event_start: float
    event_peak: float
    event_end: float
    pre_event_hr_mean: Optional[float]
    event_hr_mean: Optional[float]
    post_event_hr_mean: Optional[float]
    hr_delta_pre_to_post: Optional[float]
    peak_acc: Optional[float]
    peak_jerk: Optional[float]
    motion_energy: Optional[float]
    gyro_energy: Optional[float]
    proxy_event_label: str       # normal_adl / abrupt_event_proxy — never "attack"


def column_names(record_cls) -> list[str]:
    """Field names of a schema dataclass, in order."""
    return [f.name for f in fields(record_cls)]
