"""A01 post-event definitions on synthetic windows."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wearsafe.post_event import event_measures, recovery, window_median  # noqa: E402

ENDS = np.arange(8, 400, 2.0)


def test_recovery_time_and_not_recovered():
    rel = ENDS >= 230
    assert recovery(ENDS, rel, 200) == (30.0, 230.0)
    assert np.isnan(recovery(ENDS, np.zeros(len(ENDS), bool), 200)[0])           # never reliable -> not recovered
    assert np.isnan(recovery(ENDS, ENDS >= 330, 200)[0])                           # beyond 120 s -> not recovered
    assert recovery(ENDS, ENDS == 200, 200)[0] != 0 and np.isnan(recovery(ENDS, ENDS == 200, 200)[0])  # end == ta is not "after"


def test_pre_missing_and_no_future_data():
    hr = np.where(ENDS < 200, 70.0, 120.0)
    rel = np.ones(len(ENDS), bool)
    m = event_measures(ENDS, hr, rel, hr, 200)
    assert m["pre_wrist"] == 70.0 and m["post_wrist"] == 120.0 and m["change_wrist"] == 50.0
    # changing anything after ta - 5 s must not change the pre value
    hr2 = hr.copy()
    hr2[ENDS > 195] = 999.0
    assert event_measures(ENDS, hr2, rel, hr2, 200)["pre_wrist"] == 70.0
    rel_pre_missing = ENDS > 196
    m2 = event_measures(ENDS, hr, rel_pre_missing, hr, 200)
    assert np.isnan(m2["pre_wrist"]) and np.isnan(m2["change_wrist"]) and m2["pre_ecg"] == 70.0


def test_window_median_bounds():
    v = ENDS.copy()
    assert window_median(ENDS, v, np.ones(len(v), bool), 10, 14) == 12.0
