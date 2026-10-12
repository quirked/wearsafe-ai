"""LOSO split helpers (synthetic) and the real FallAllD manifest if present."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wearsafe.splits import check_folds, loso_folds  # noqa: E402

MANIFEST = REPO / "splits/fallalld_v1.json"


def test_loso_folds():
    subs = ["A", "B", "C"]
    folds = loso_folds(subs)
    assert check_folds(folds, subs) == []
    assert [f["test"] for f in folds] == [["A"], ["B"], ["C"]]
    bad = [{"fold": 0, "test": ["A"], "train": ["A", "B", "C"]}]
    assert check_folds(bad, subs)


@pytest.mark.skipif(not MANIFEST.exists(), reason="splits/fallalld_v1.json not built")
def test_fallalld_manifest():
    m = json.loads(MANIFEST.read_text())
    assert check_folds(m["folds"], m["subjects"]) == []
    assert len(m["subjects"]) == 13 and len(m["subjects_with_falls"]) == 9 and len(m["subjects_without_falls"]) == 4
    for f in m["folds"]:
        assert set(f["inner_validation_subjects"]) <= set(f["train"]) & set(m["subjects_with_falls"])
