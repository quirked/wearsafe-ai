"""A02 response-window and causality rules on synthetic EDA."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wearsafe.eda import artefact_mask, causal_split, event_eda  # noqa: E402

FS = 4


def test_quick_response_window():
    tonic, phasic = np.ones(400), np.zeros(400)
    art = np.zeros(400, bool)
    assert event_eda(50, FS, tonic, phasic, [53.0], art)["quick_response"]
    assert not event_eda(50, FS, tonic, phasic, [50.5], art)["quick_response"]    # < t+1
    assert not event_eda(50, FS, tonic, phasic, [55.5], art)["quick_response"]    # > t+5
    assert event_eda(50, FS, tonic, phasic, [51.0, 70.0], art)["quick_response"]


def test_causal_split_pre_values_ignore_future():
    rng = np.random.default_rng(0)
    x = 2 + 0.1 * rng.normal(size=800)
    t1, p1 = causal_split(x, FS)
    y = x.copy()
    y[400:] += 5.0                                                               # change the future only
    t2, p2 = causal_split(y, FS)
    assert np.allclose(t1[:400], t2[:400]) and np.allclose(p1[:400], p2[:400])
    art = np.zeros(800, bool)
    a = event_eda(100, FS, t1, p1, [], art)["pre_phasic_area"]
    b = event_eda(100, FS, t2, p2, [], art)["pre_phasic_area"]
    assert a == b


def test_artefact_rules():
    x = np.array([2.0, 2.0, 0.01, 2.0, 2.0, 9.0])
    m = artefact_mask(x, FS)
    assert m[2] and m[5] and not m[0]
