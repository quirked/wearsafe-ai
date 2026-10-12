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

## 5. Compute and environment rules
- Use the dedicated conda environment **`wearsafe`** (Python 3.11). Every dependency is pinned in `requirements.txt`, and the environment is rebuilt from that file. Never install packages into the user's `sao` environment or into `base`. Run code as `~/miniconda3/envs/wearsafe/bin/python ...` or `conda run -n wearsafe ...`.
- Run every experiment, training job or long-running script inside the tmux session named **`sao`**. Create it if missing (`tmux new-session -d -s sao`). Never kill that session or any other tmux session. Save stdout/stderr to `logs/<YYYY-MM-DD>_<milestone>_<name>.log`.
- Before any experiment:
  1. Run `nvidia-smi`.
  2. Choose a GPU that is currently free (low memory use, no other processes).
  3. Set `CUDA_VISIBLE_DEVICES` to it.
  4. Record the GPU choice and the `nvidia-smi` snapshot in `PROJECT_LOG.md`.
- If no GPU is free, say so and use CPU (`CUDA_VISIBLE_DEVICES=""`). Classical models are fine on CPU. Never kill or interfere with other users' processes.

## 6. Verified dataset facts (from `reports/D00a_data_inventory.md`; re-verify before relying on anything marked UNVERIFIED)

### PPG-DaLiA
15 subjects (S1–S15), `SX.pkl` (load with `encoding="latin1"`).
- **Wrist (Empatica E4, non-dominant):** ACC 32 Hz, **stored in g in the pkl** (raw E4 CSV is 1/64 g; saturates at ±2 g). BVP 64 Hz. EDA and TEMP 4 Hz.
- **Chest (RespiBAN):** 700 Hz. EDA, EMG and Temp are dummy constants; discard them.
- **Labels:**
  - `activity` at 4 Hz: 0 transient, 1 sitting, 2 stairs, 3 table soccer, 4 cycling, 5 driving, 6 lunch, 7 walking, 8 working. `CLEAN_BASELINE` in the CSV is coded 0.
  - `label` is the ECG-derived HR ground truth, one value per 8 s window with a 2 s shift.
- **Timing:** all pkl signals share a common start and duration. There are no timestamps; time = index / rate.
- S6 is valid only to 5250 s; its activity CSV extends beyond that.

### WESAD
15 subjects (S2–S11, S13–S17; S1 and S12 are absent by design), `SX.pkl` (latin1).
- **Wrist E4:** same rates as PPG-DaLiA, but **ACC is stored as raw 1/64 g integer counts. Divide by 64 to get g.** This is the same device as PPG-DaLiA, with a 64× scale difference.
- **Labels** at 700 Hz: 0 transient, 1 baseline, 2 stress, 3 amusement, 4 meditation (×2 sessions), 5/6/7 ignore (inferred: reading periods).
- There is no HR ground truth.
- quest.csv times are offset from the pkl by a constant 33–155 s per subject. **Use the pkl labels only.**
- S3 chest Temp contains −273.15.

### BITS-2
41 subjects (user1–41) × 24 activity files each = 984 CSVs: 16 ADL (`adl1–16`) + 8 falls (`fall1–8`).
- **Format:** each file contains **IMU and HR together** (blocks `acc`, `acg`, `gyro`, `mgm`, `hrt`). There are no separate HR files.
- **Units (inferred):** m/s², with `acc` gravity-removed and `acg` including gravity. Gyro in rad/s. Magnetometer in µT. HR in bpm with an Android status code (3 / 0 / −1).
- **Timestamp damage:** about 99% of timestamps were saved with ≤3 significant digits, so the IMU sampling rate is **unverified and appears irregular** (evidence ranges from ~5 to 50 Hz). HR is ≈1 Hz. Do not assume a fixed IMU rate.
- **No activity names or device documentation are in the download.**
- **"Each activity repeated 5 times": UNVERIFIED.** The user reported this from a paper. However, `docs/papers/BITS2-paper.pdf` is actually the PerHeart dataset paper (Kołakowski et al., Data 2026). It cites BITS-2 only in a summary table (41 participants, age 27.9 ± 8.6, lab falls) and does not mention repetitions. The files hold one CSV per subject × activity, with no trial field.
- **Known defects:** user28 fall4 == fall8 (byte-identical). user5_adl2 and user40_adl4 share an identical `mgm` block. user7_fall3 contains two recordings. Four files are named `user31_.fallN.csv`. 181 files have fewer than 10 HR rows.

### Cross-dataset
Wrist ACC units differ by dataset (g / 1/64 g / m/s²). The canonical unit is m/s². Only BITS-2 has a gyroscope. Only PPG-DaLiA and WESAD have BVP/PPG.

Correction 2026-10-12: the 5-repetitions claim comes from the abstract of Nandi et al., Data in Brief 52 (2024) 109812 (PMC10709028), now saved as docs/papers/BITS2_DataInBrief_2024.pdf. docs/papers/BITS2-paper.pdf is the PerHeart paper, not BITS-2. Status: stated in paper, not yet verified in files.
