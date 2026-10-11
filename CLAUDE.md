# CLAUDE.md — WearSafe AI standing rules

Read this file, `docs/WearSafe_AI_Context.md`, and the latest entries of `PROJECT_LOG.md` at the start of EVERY session before doing anything else.

## 1. What this project is (one paragraph)
WearSafe AI is a wearable personal-safety research prototype. It uses wrist accelerometer (+ optional gyroscope) and PPG / heart-rate signals to estimate a **potential-danger / safety-anomaly score**. It is NOT a confirmed attack detector. The problem is split into three component models (motion: normal ADL vs abrupt-event proxy; arousal: low vs high; context: stationary / low_activity / locomotion / vigorous_activity) whose outputs are combined by rule-based late fusion that also accounts for signal quality. Full design: `docs/WearSafe_AI_Context.md`. Decisions marked FINAL / FROZEN there are fixed unless the user changes them.

## 2. Absolute rules — never break these

### 2.1 Never delete anything
- Never delete, move-to-trash, or truncate any file or folder. No `rm`, `rmdir`, `git clean`, `git reset --hard`, `git checkout -- <file>`, `git push --force`, or overwriting a file with empty content.
- Never overwrite a generated data/result artifact. Write a new versioned file instead (`features_v2.parquet`, `results/2026-10-12_motion_lr/`). Superseded outputs stay where they are; record in `PROJECT_LOG.md` which version is current.
- Editing source code you wrote is fine (git keeps history). Commit before and after every milestone.
- If something genuinely must be removed, STOP and ask the user. Do not do it yourself.

### 2.2 Raw data is read-only
- Never modify anything under `data/raw/`. Every derived file is written under `data/interim/`, `data/processed/`, `metadata/`, `splits/`, or `results/`.

### 2.3 No cheating to improve scores — this is a hard rule
Honest, lower numbers are always preferred over inflated ones. Specifically forbidden:
- Any subject appearing in more than one split (train/val/test). Splits are subject-independent; subject IDs are namespaced (`PPGDALIA_S01`, `WESAD_S02`, `BITS2_S03`, …).
- Random window-level splits. Overlapping windows from the same recording leaking across splits.
- Fitting scalers, imputers, feature selection, thresholds, or hyperparameters on test data. Everything is fit on training folds only; tuning uses validation folds only.
- Looking at test results and then going back to change features, labels, windows, or thresholds ("test-set peeking"). If that happens by accident, declare it in the log and treat that test set as burned.
- Relabelling stress, falls, or exercise as "attack". There is no attack label in this project.
- Pairing signals from different people or different datasets and presenting them as synchronous.
- Dropping difficult subjects, windows, activities, or hard negatives (table soccer, stairs, cycling, amusement…) to make metrics look better. Any exclusion must have a data-quality reason decided BEFORE seeing model results, and must be logged.
- Using label-derived or future information as a feature (e.g. activity ID, protocol timestamps, window position within a known event, post-event HR in a real-time feature).
- Changing a metric's definition, cherry-picking the best seed/fold, or reporting only the best run. Report mean ± std across folds/subjects and per-subject results.
- Hardcoding, fabricating, or estimating any number that appears in a report. Every reported number must come from a script in the repo that can be re-run.
- Generating synthetic data and mixing it into evaluation. Synthetic data, if ever used, is clearly separated and labelled.
- Using model performance to debug the dataset. Data is validated by audits and invariant checks first.

### 2.4 Scientific boundaries
- Claim: "potential danger / safety anomaly". Never claim attack detection.
- High HR alone ≠ danger. Stress ≠ fear/assault. Falls ≠ attacks.
- Poor PPG quality under strong motion means physiology is UNCERTAIN, not "calm".
- Never change a scientific assumption silently. If you think one should change, stop and propose it to the user.

## 3. Working process
- Work one milestone at a time (IDs in `docs/WearSafe_AI_Context.md` §32 and in `PROJECT_LOG.md`). Order: data → smoke test → full build → integrity audit → models → fusion → prototype.
- After each milestone: run its checks/tests, commit, update `PROJECT_LOG.md`, then STOP and report to the user. Do not start the next milestone on your own.
- If any invariant check fails (shapes, sampling rates, units, label counts, subject overlap, NaN rates beyond threshold), STOP and report. Do not "fix" it by silently dropping data.
- Do not invent dataset fields. When a dataset's format is unclear, inspect the real files and the dataset's README/paper; record what you found.
- Preserve original labels and source metadata alongside derived labels.
- Prefer simple, readable Python. Pin dependencies in `requirements.txt` (or `pyproject.toml`). Set and log random seeds.
- Use relative paths from the repo root. Never hardcode absolute machine paths.

## 4. PROJECT_LOG.md — keep it updated (mandatory)
`PROJECT_LOG.md` is the running memory of this project. Append to it (never rewrite or delete past entries) whenever you:
- start or finish a milestone,
- make or propose a design decision,
- find something surprising in the data,
- run an experiment (record config, data version, split version, and results, including failures),
- hit a blocker or an open question.

Each entry uses this format:

```
## YYYY-MM-DD HH:MM — <milestone ID> — <short title>
**What I did:**
**Files created/changed:**
**Checks run and results:**
**Decisions made (and why):**
**Problems / surprises:**
**Open questions for the user:**
**Next step (waiting for user approval):**
```

Keep a short "Current status" block at the TOP of the file (current milestone, current data/split versions, last validated result). Updating that block is the only allowed edit to existing text in the log.
