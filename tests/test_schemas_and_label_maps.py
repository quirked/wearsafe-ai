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


@pytest.mark.parametrize("dataset", ["ppg_dalia", "wesad", "bits2", "fallalld", "upfall"])
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


def test_window_meta_columns_are_forbidden_features():
    for col in ("label_purity", "crosses_boundary", "eval_role", "hr_ref_bpm", "majority_code",
                "n_hr_ref", "acc_i0", "recording_id"):
        assert col in schemas.FORBIDDEN_FEATURE_COLUMNS
        assert col not in schemas.ALL_FEATURES


def test_bits2_context_proposal_values_valid():
    prop = MAPS["bits2"]["context_class_proposal"]["mapping"]
    assert set(prop) == {f"adl{k}" for k in range(1, 17)}
    for src, dst in prop.items():
        assert dst is None or dst in schemas.CONTEXT_CLASSES, f"{src} -> {dst}"
    assert MAPS["bits2"]["context_class"] == "TODO"          # not used for v1 context training (Q6)
    assert MAPS["bits2"]["training_v1"]["motion"] == [] and MAPS["bits2"]["training_v1"]["context"] == []


def test_ppg_dalia_has_no_arousal_and_all_normal_adl():
    m = MAPS["ppg_dalia"]
    assert m["arousal_class"] is None                       # user decision B after D00b
    assert m["motion_event_class"]["default"] == "normal_adl"
    assert set(m["motion_event_class"].values()) == {"normal_adl"}


def test_evaluation_rule_recorded():
    ev = yaml.safe_load((REPO / "config" / "evaluation_v1.yaml").read_text())
    assert "NOT used to train or tune ANY" in ev["false_alerts_per_user_hour"]["rule"]
    assert "EVALUATION RULE" in (REPO / "CLAUDE.md").read_text()


def test_decisions_after_d00c_recorded():
    fad, upf = MAPS["fallalld"], MAPS["upfall"]
    assert fad["devices_used"] == ["Wrist"] and upf["devices_used"] == ["Wrist"]          # decision 5
    assert fad["training_v1"]["excluded_ids"] == [15, 23]                                 # decision 4
    assert {k: v["role"] for k, v in fad["eval_role"].items()} == {15: "hard_negative_probe", 23: "hard_negative_probe"}
    assert MAPS["units"]["fallalld"]["wrist_acc"]["counts_per_g"] == 4096                  # decision 2
    assert MAPS["units"]["fallalld"]["wrist_acc"]["factor"] == pytest.approx(schemas.STANDARD_GRAVITY / 4096)
    assert "[inferred]" in MAPS["units"]["fallalld"]["wrist_acc"]["status"]
    assert set(upf["original_label"]) == set(range(1, 12))
    assert set(upf["motion_event_class"]) == set(upf["original_label"].values())
    assert fad["gyro_used_v1"] is False and upf["gyro_used_v1"] is False                    # decision 10
    h = yaml.safe_load((REPO / "config" / "motion_harmonisation_v1.yaml").read_text())
    assert h["rate_hz"] == 32 and set(h["versions"]) == {"unclipped", "e4_clipped"}        # decision 8
    assert h["versions"]["e4_clipped"]["clip_g"] == [-2.0, 127 / 64]
    assert h["versions"]["e4_clipped"]["clip_m_s2"] == pytest.approx(
        [g * schemas.STANDARD_GRAVITY for g in h["versions"]["e4_clipped"]["clip_g"]])
    ev = yaml.safe_load((REPO / "config" / "evaluation_v1.yaml").read_text())
    assert ev["fallalld_motion"]["cv"] == "leave_one_subject_out"                          # decision 11
    rules = (REPO / "CLAUDE.md").read_text()
    assert "CLIP-POSITION RULE" in rules and "DEVICE-DISCRIMINATION RULE" in rules           # decisions 6, 9
    assert "## 44. Design changes after audits (2026-10-12)" in (REPO / "docs/WearSafe_AI_Context.md").read_text()
