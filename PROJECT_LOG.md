# PROJECT_LOG — WearSafe AI

## Current status
- **Current milestone:** D00 — Repository setup + rule updates — DONE, waiting for user review. Next milestone (D01) not started.
- **Environment:** conda env `wearsafe` (Python 3.11.17), pinned in `requirements.txt` (+ full `requirements-lock.txt`).
- **Data version:** raw only. Checksum manifest `metadata/raw_checksums.csv` (2,126 files, SHA-256). No interim/processed data yet.
- **Split version:** none.
- **Last validated result:** D00 tests 12 passed / 1 skipped (fast mode); full SHA-256 raw check 3/3 passed (2026-10-12).
- **Open blockers:** BITS-2 documentation (activity names, device, "5 repetitions" claim) still missing; label-map TODOs (lunch, amusement, meditation, BITS-2 context).

---

## 2026-10-11 23:55 — D00a — Data inventory (look-only)
**What I did:**
- Read CLAUDE.md. `docs/` is empty: neither `docs/WearSafe_AI_Context.md` nor `docs/WearSafe_AI_Full_Context_for_Claude.docx` exists, and no copy was found under /home.
- Initialised git with a `.gitignore` excluding `data/` and large outputs. Made a baseline commit before the milestone.
- Wrote read-only inspection scripts and inspected all three datasets. Pickles were loaded one subject at a time.
- Read all documentation: PPG-DaLiA readme.pdf (including the appendix tables, rendered as images), WESAD readme.pdf, the 15 WESAD per-subject readmes, and the E4 info.txt. BITS-2 ships with no docs.

**Files created/changed:**
- `.gitignore`
- `scripts/inspect/common.py`
- `scripts/inspect/folder_map.py`
- `scripts/inspect/check_archives.py`
- `scripts/inspect/inspect_ppg_dalia.py`
- `scripts/inspect/inspect_wesad.py`
- `scripts/inspect/inspect_bits2.py`
- `reports/D00a_data_inventory.md`
- `PROJECT_LOG.md`

Nothing under `data/` was created or modified. No unzipping was needed.

**Checks run and results:**
- Archive check: all 1,138 archive members are identical (size + CRC32) to the extracted files.
- PPG-DaLiA (15 subjects):
  - Every pkl signal has an identical duration at the documented rates (0.000 s spread).
  - The HR label count equals floor((dur−8)/2)+1 for all subjects.
  - No NaNs.
  - Wrist ACC × 64 is integer-valued in 100% of samples, so the pkl stores g.
- WESAD (15 subjects):
  - Identical durations, no NaNs.
  - Wrist ACC is stored as integer 1/64 g counts.
  - Labels sit at a constant per-subject offset from quest.csv (−33 to −155 s) and are 20 s shorter.
- BITS-2 (984 files, 41 users × (16 ADL + 8 fall)):
  - Every file contains acc/acg/gyro/mgm + hrt blocks.
  - ~99% of timestamps are rounded to ≤3 significant digits.
  - HR is ≈1 Hz where resolvable. The IMU rate is unverifiable and appears irregular.

**Decisions made (and why):**
- Used the existing conda env `sao` (Python 3.11.16, numpy 2.4.6, pandas 3.0.5, h5py 3.16.0) because base Python lacks h5py. No packages were installed. A pinned `requirements.txt` is deferred to a later milestone, pending user approval.
- E4 zips were read in memory instead of being unzipped, which keeps D00a strictly look-only.
- Pickles were loaded with `encoding="latin1"`. All 30 needed it (Python-2 era).

**Problems / surprises:**
- BITS-2 has **no separate HR files**. HR is embedded in every file, which contradicts the task description.
- BITS-2 has no docs, so the activity names for adl1–16 and fall1–8 are unknown.
- BITS-2 timestamps were destroyed by rounding.
- BITS-2 duplicate content:
  - user28 fall4 == fall8 (byte-identical).
  - user5_adl2 and user40_adl4 share an identical mgm block (cross-subject).
  - user7_fall3 holds two recordings.
  - Four files are named `user31_.fallN.csv`.
- Wrist ACC units differ: DaLiA pkl in g, WESAD pkl in 1/64 g.
- DaLiA `CLEAN_BASELINE` segments are coded 0 in the pkl. S6 is truncated at 5250 s, as documented. Duplicate R-peak indices: S6 ×3, S14 ×1.
- WESAD S3 chest Temp contains −273.15. Raw E4 TEMP.csv contains 382 °C start-up values.

**Open questions for the user:** see `reports/D00a_data_inventory.md` §6. In short:
- Provide the context doc.
- Provide the BITS-2 docs and explain where the "two files per activity" description came from.
- Decide how to handle the BITS-2 duplicates and HR rows with status −1.
- Confirm CLEAN_BASELINE = transient.
- Confirm WESAD codes 5/6/7 stay excluded.
- Approve a dedicated environment and `requirements.txt`.

**Next step (waiting for user approval):** user reviews the D00a report and answers the open questions. Next milestone not started.

## 2026-10-12 00:45 — D00 — Repository setup, environment, contracts, rule updates
**What I did:**
- Read CLAUDE.md, PROJECT_LOG.md, reports/D00a_data_inventory.md and the newly added docs/WearSafe_AI_Context.md. Made a pre-milestone commit adding the context doc and docs/papers/BITS2-paper.pdf.
- Appended to CLAUDE.md (nothing removed):
  - §5 "Compute and environment rules".
  - §6 "Verified dataset facts".
- Created the conda env `wearsafe` (Python 3.11.17) with numpy, pandas, scipy, h5py, pyarrow, scikit-learn, xgboost, neurokit2, matplotlib, pytest and PyYAML. Wrote the pinned `requirements.txt` and the full `requirements-lock.txt` (pip freeze).
- Re-ran `scripts/inspect/inspect_bits2.py` in the new env (tmux `sao`, log `logs/2026-10-12_D00_inspect_bits2_wearsafe_env.log`). Its output is **byte-identical** to the D00a run.
- Created the folder structure from context doc §21 plus logs/, reports/, results/, tests/, src/wearsafe/ and config/.
- Added data contracts:
  - `src/wearsafe/schemas.py`: Layer A/B/C, BITS-2 event record, class vocabularies, canonical units, namespaced subject IDs, forbidden feature columns.
  - `config/label_maps.yaml`: original→derived labels and unit factors.
- Created `metadata/raw_checksums.csv` (path, size, mtime, SHA-256 for all 2,126 files in data/raw/) with `scripts/make_raw_manifest.py` (tmux `sao`, log `logs/2026-10-12_D00_raw_manifest.log`).
- Added tests:
  - `tests/test_raw_data_unchanged.py`: fast mode checks file set + size + mtime; full SHA-256 mode runs with `WEARSAFE_FULL_CHECKSUM=1`.
  - `tests/test_schemas_and_label_maps.py`.
- Appended §9 "Differences from the context document" to reports/D00a_data_inventory.md.

**Files created/changed:**
- CLAUDE.md (appended §5, §6)
- .gitignore (logs/*.log)
- requirements.txt, requirements-lock.txt
- src/wearsafe/__init__.py, src/wearsafe/schemas.py, src/wearsafe/raw_manifest.py
- config/label_maps.yaml
- scripts/make_raw_manifest.py
- metadata/raw_checksums.csv
- tests/test_raw_data_unchanged.py, tests/test_schemas_and_label_maps.py
- reports/D00a_data_inventory.md (appended §9)
- empty folders: data/interim/<ds>/{normalized_signals,windows}, data/processed/{context,arousal,motion,fusion_validation}, metadata/, splits/, logs/, results/, tests/, config/
- PROJECT_LOG.md

**Checks run and results:**
- `pytest -v` (fast): first run 11 passed, **1 failed**, 1 skipped.
  - The failure was a bug in my test: `test_no_attack_label_anywhere` searched raw YAML text and matched the word "attacks" in a comment.
  - Fixed the test to check parsed keys/values only. Rerun: **12 passed, 1 skipped** (log `logs/2026-10-12_D00_pytest_rerun.log`).
- `WEARSAFE_FULL_CHECKSUM=1 pytest tests/test_raw_data_unchanged.py`: **3 passed** in 163 s. data/raw is unchanged.
- Negative check: against a copy of the manifest with one size altered (scratchpad only), the size/mtime test correctly fails.
- GPU check (CLAUDE.md §5) at 00:27. No experiment was run in this milestone; CPU only. nvidia-smi snapshot (index, name, mem used, mem total, util):
```
0, NVIDIA RTX A6000, 16103 MiB, 49140 MiB, 100 %
1, NVIDIA RTX A5000, 20955 MiB, 24564 MiB, 78 %
2, NVIDIA RTX A5000, 17321 MiB, 24564 MiB, 63 %
3, NVIDIA RTX A6000, 13527 MiB, 49140 MiB, 97 %
```
  At 00:27 all 4 GPUs held other users' python processes (12.7–20.2 GB each, 66–100 % util). **No GPU was free → CPU.** No processes were touched.

**Decisions made (and why):**
- requirements.txt pins the direct dependencies; requirements-lock.txt pins everything, for exact reproducibility. pandas resolved to 2.3.3 (pip's choice alongside neurokit2 0.2.13).
- The raw-data test defaults to fast mode (size + mtime), because a full SHA-256 pass over ~46 GB takes ~3 min. Full mode is opt-in through an env var and was run once here.
- Did **not** create data/raw/upfall or data/raw/fallalld (from context doc §21), because raw is read-only. They can be created when those datasets are downloaded.
- Label maps:
  - Followed context doc §16 exactly. `lunch` is **TODO**, as instructed.
  - PPG-DaLiA transient (0) → null (excluded from context training, kept in storage).
  - WESAD baseline → low_arousal, stress → high_arousal. `amusement` and `meditation` → **TODO** (the doc does not decide them). 5/6/7 → null.
  - BITS-2: adl → normal_adl, fall → abrupt_event_proxy (doc §9/§15). BITS-2 context_class → TODO (activity names unknown).
  - PPG-DaLiA motion_event_class = normal_adl is marked **PROPOSED**.
- Unit factors: DaLiA ACC × 9.80665 (g→m/s²); WESAD ACC × 9.80665/64; BITS-2 × 1 (inferred m/s²).

**Problems / surprises:**
- **docs/papers/BITS2-paper.pdf is not the BITS-2 paper.** It is the PerHeart dataset paper (Kołakowski et al., Data 2026, older heart-failure patients). It cites BITS-2 only in a comparison table (41 participants, 27.9 ± 8.6 y, HR + acc/gyro/mag, lab, falls) and **does not say activities were repeated 5 times**. CLAUDE.md §6 therefore records "5 repetitions" as UNVERIFIED. Our files contain one CSV per subject × activity, with no trial field.

**Open questions for the user:**
1. Can you provide the actual BITS-2 data paper or Zenodo readme? It is needed for activity names, device/placement, intended sampling rate and the 5-repetitions claim. If the 5 repeats are real, are they concatenated inside each CSV?
2. Label-map TODOs: PPG-DaLiA `lunch`; WESAD `amusement` (the doc calls it a "non-danger high arousal" hard negative: high_arousal, or excluded?) and `meditation`; BITS-2 context classes.
3. Should PPG-DaLiA transient (code 0) windows count toward false-alert-per-hour evaluation even though they are excluded from context training? (Proposed: yes.)
4. Open items from D00a §6 remain: BITS-2 duplicates, HR rows with status −1.

**Next step (waiting for user approval):** D01 — PPG-DaLiA ingestion audit. Not started.
