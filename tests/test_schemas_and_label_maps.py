"""Consistency checks for src/wearsafe/schemas.py and config/label_maps.yaml (no data needed)."""
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import schemas  # noqa: E402

MAPS = yaml.safe_load((REPO / "config" / "label_maps.yaml").read_text())
ALLOWED = {
    "context_class": set(schemas.CONTEXT_CLASSES),
    "motion_event_class": set(schemas.MOTION_EVENT_CLASSES),
    "arousal_class": set(schemas.AROUSAL_CLASSES),
}


def test_vocabularies_match_schema():
    for key, allowed in ALLOWED.items():
        assert set(MAPS["classes"][key]) == allowed


@pytest.mark.parametrize("dataset", ["ppg_dalia", "wesad", "bits2"])
def test_mapped_values_are_valid_or_null_or_todo(dataset):
    for key, allowed in ALLOWED.items():
        mapping = MAPS[dataset].get(key)
        if not isinstance(mapping, dict):
            assert mapping in (None, "TODO")
            continue
        for src, dst in mapping.items():
            assert dst is None or dst == "TODO" or dst in allowed, f"{dataset}.{key}.{src} -> {dst}"


def _all_keys_and_values(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys_and_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys_and_values(v)
    else:
        yield obj


def test_no_attack_label_anywhere():
    # Parsed YAML (comments excluded): no key or value may name an attack class (CLAUDE.md §2.3).
    tokens = [str(t).lower() for t in _all_keys_and_values(MAPS)]
    assert not [t for t in tokens if "attack" in t]
    for vocab in (schemas.CONTEXT_CLASSES, schemas.MOTION_EVENT_CLASSES, schemas.AROUSAL_CLASSES):
        assert not [c for c in vocab if "attack" in c]


def test_lunch_is_open_question():
    assert MAPS["ppg_dalia"]["context_class"]["lunch"] == "TODO"


def test_every_ppg_dalia_activity_has_a_context_entry():
    names = set(MAPS["ppg_dalia"]["original_label"].values())
    assert names == set(MAPS["ppg_dalia"]["context_class"].keys())


def test_wesad_acc_factor_is_g_over_64():
    f = MAPS["units"]["wesad"]["wrist_acc"]["factor"]
    assert f == pytest.approx(schemas.STANDARD_GRAVITY / 64)
    assert MAPS["units"]["ppg_dalia"]["wrist_acc"]["factor"] == pytest.approx(schemas.STANDARD_GRAVITY)


def test_subject_ids():
    assert schemas.namespaced_subject_id("ppg_dalia", 1) == "PPGDALIA_S01"
    assert schemas.namespaced_subject_id("wesad", 17) == "WESAD_S17"
    assert schemas.namespaced_subject_id("bits2", 41) == "BITS2_S41"
    assert schemas.is_valid_subject_id("BITS2_S41")
    assert not schemas.is_valid_subject_id("S1")
    with pytest.raises(ValueError):
        schemas.namespaced_subject_id("upfall", 1)


def test_label_columns_are_forbidden_features():
    for col in ("original_label", "context_class", "motion_event_class", "arousal_class", "subject_id"):
        assert col in schemas.FORBIDDEN_FEATURE_COLUMNS
        assert col not in schemas.ALL_FEATURES
