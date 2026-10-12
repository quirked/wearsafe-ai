"""Subject-independent split manifests (CLAUDE.md §2.3; config/evaluation_v1.yaml)."""
from __future__ import annotations


def loso_folds(subjects: list[str]) -> list[dict]:
    subjects = sorted(subjects)
    return [{"fold": i, "test": [s], "train": [t for t in subjects if t != s]} for i, s in enumerate(subjects)]


def check_folds(folds: list[dict], subjects: list[str]) -> list[str]:
    """Returns a list of problems (empty = OK)."""
    problems, tested = [], []
    for f in folds:
        if set(f["test"]) & set(f["train"]):
            problems.append(f"fold {f['fold']}: subject in both train and test")
        if set(f["test"]) | set(f["train"]) != set(subjects):
            problems.append(f"fold {f['fold']}: union of train and test != subject set")
        tested += f["test"]
    if sorted(tested) != sorted(subjects):
        problems.append("not every subject is the test subject exactly once")
    return problems
