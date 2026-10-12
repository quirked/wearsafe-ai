"""PPG-DaLiA Layer A normalisation on a synthetic subject (D02; no raw data needed)."""
import sys
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe import ppg_dalia_io as io  # noqa: E402

MAPS = yaml.safe_load((REPO / "config" / "label_maps.yaml").read_text())


def synthetic(dur_s=12):
    rng = np.random.default_rng(0)
    counts = rng.integers(-60, 60, size=(dur_s * 32, 3))
    counts[5] = [-128, 0, 0]
    counts[6] = [0, 127, 0]
    counts[7] = [-127, 126, 0]          # one count inside the rails -> not saturated
    act = np.repeat([0, 1, 1, 6], dur_s)     # 4 Hz codes, 3 s each
    return io.Subject(number=3, subject_id="PPGDALIA_S03", acc_g=counts / 64.0,
                      bvp=rng.normal(size=dur_s * 64), activity=act,
                      hr_ref=np.full(io.expected_hr_ref_count(dur_s), 70.0), questionnaire={"Gender": " m"})


def test_units_and_saturation():
    s = synthetic()
    t = io.normalize(s, MAPS)
    acc = t["wrist_acc"]
    assert np.array_equal(acc["x"].to_numpy(), s.acc_g[:, 0] * 9.80665)
    assert (acc["original_unit"] == "g").all() and (acc["canonical_unit"] == "m/s^2").all()
    assert acc["acc_saturated"].tolist()[5:8] == [True, True, False]
    counts, dev = io.acc_counts(s.acc_g)
    assert dev < 1e-12 and counts[5, 0] == -128


def test_durations_ids_labels():
    s = synthetic()
    assert io.durations(s) == {"acc": 12.0, "bvp": 12.0, "activity": 12.0}
    assert io.expected_hr_ref_count(12) == 3
    t = io.normalize(s, MAPS)
    for df in t.values():
        assert (df["subject_id"] == "PPGDALIA_S03").all()
        assert (df["recording_id"] == "PPGDALIA_S03_main").all()
    act = t["activity"]
    assert act["original_label"].tolist()[:1] == ["transient"]
    assert dict(zip(act["original_label"], act["eval_role"])) == {
        "transient": "false_alert_eval", "sitting": "train_candidate", "lunch": "false_alert_eval"}
    # acc sample i carries the label of activity sample floor(i / 8)
    assert t["wrist_acc"]["original_label"].iat[12 * 8] == "sitting"
    assert t["wrist_bvp"]["original_label"].iat[12 * 16 - 1] == "transient"
    hr = t["hr_ref"]
    assert hr["ref_window_start"].tolist() == [0.0, 2.0, 4.0] and (hr["ref_window_end"] - hr["ref_window_start"] == 8).all()


def test_subject_row_strips_gender():
    r = io.subject_row(synthetic())
    assert r["gender"] == "m" and r["gender_original"] == "' m'"
    assert r["use"] == "analysis_only_never_model_input"
