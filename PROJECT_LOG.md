# PROJECT_LOG — WearSafe AI

## Current status
- **Current milestone:** D00c — FallAllD + UP-Fall audit (look-only) — DONE, waiting for user review (report §7, decisions 1–9). D02 is DONE (15 subjects). D03 is not started.
- **Environment:** conda env `wearsafe` (Python 3.11.17), `requirements.txt` + `requirements-lock.txt`.
- **Data version:** PPG-DaLiA Layer A `data/interim/ppg_dalia/normalized_signals_v1/`; Layer B `windows_v1/` (built with `config/windowing_v2.yaml`: purity 1.0 + 10 s boundary margin). Smoke versions `*_smoke_v1` and `windows_smoke_v2` are kept. Raw checksum manifest **v3** `metadata/raw_checksums_v3.csv` (3,112 files; v1 and v2 kept). BITS-2: `metadata/bits2_file_manifest.csv`, `metadata/bits2_exclusions.csv` (v1; the Q5 rule is defined for v2).
- **Split version:** none.
- **Last validated result:** D02 full run, 2026-10-12. Train candidates (motion/context/physiology): 65079 / 25920 / 4155. Deterministic re-run identical. Tests 42 passed / 1 skipped.
- **Open items:** D00c decisions (design change: FallAllD main motion source / UP-Fall low-rate stress test; unit factor 4,096 counts/g; label source; harmonised rate); optional D03 report-only distance-to-boundary table.
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

## 2026-10-12 00:55 — D00 — User decisions 2026-10-12
**What I did:** Recorded the user's label and evaluation decisions in `config/label_maps.yaml` and in this log. I also appended a correction note to CLAUDE.md §6, as the user explicitly allowed. Nothing else was changed, and no data was read or processed.

**Decisions (user, 2026-10-12) and how they are encoded:**
- **General rule:** ambiguous segments are EXCLUDED from component-model training but INCLUDED in false-alert-per-hour evaluation. This is in the YAML header comment. Training sets are built only from the new `training_v1` lists; `eval_role` says why an excluded label is kept.
1. **WESAD v1 arousal training = baseline (low_arousal) vs stress (high_arousal) only.** Encoded as `wesad.training_v1.arousal: [baseline, stress]`, with all other labels in `excluded`.
2. **WESAD amusement and meditation:** not used for v1 training; kept as evaluation probes. Encoded in `wesad.eval_role`:
   - amusement = probe, expected high_arousal ("non-danger high arousal probe").
   - meditation = probe, expected low_arousal ("expected-low probe").
   - Their `arousal_class` stays `TODO` (no training class assigned).
3. **PPG-DaLiA lunch:** excluded from context training; included in false-alert evaluation. Encoded in `ppg_dalia.training_v1.excluded` and `eval_role.lunch: false_alert_eval`. `context_class.lunch` stays `TODO`, because its class is still undecided.
4. **PPG-DaLiA transient:** excluded from context training; included in false-alert evaluation. Encoded in `ppg_dalia.training_v1.excluded` and `eval_role.transient: false_alert_eval`.
5. **BITS-2 context classes stay TODO** until the activity table from the paper is available. No guessing. Recorded in a comment on `bits2.context_class`.
6. **Added to the D02 TODO list:** a per-sample `acc_saturated` flag for the ±2 g watch range. There is no decision yet on how to handle it. Encoded as top-level `open_items` in the YAML.
7. **"Each activity repeated 5 times"** comes from the abstract of Nandi et al., *Data in Brief* 52 (2024) 109812 (PMC10709028). Status: **stated in paper, not yet verified in files.** Encoded as `bits2.repetitions_per_activity` (value 5, status, source).

**Files created/changed:**
- `config/label_maps.yaml`: header rule, `training_v1`, `eval_role`, `repetitions_per_activity`, `open_items`, updated comments. No existing class mapping value was changed.
- `CLAUDE.md`: one correction line appended at the end of §6. No line removed or rewritten.
- `PROJECT_LOG.md`: this entry plus the Current status block.
- `docs/papers/BITS2_DataInBrief_2024.pdf`: added to git as saved by the user. Its existence was confirmed only; it has not been read.

**Checks run and results:**
- YAML parses.
- Every label named in `training_v1` and `eval_role` exists in that dataset's `original_label`, and every original label appears in exactly one `training_v1` list (read-only check).
- `pytest -q` in env `wearsafe`: 12 passed, 1 skipped (unchanged).

**Problems / surprises:**
- Leftover note updated: the correct BITS-2 paper is now on disk as `docs/papers/BITS2_DataInBrief_2024.pdf`. `docs/papers/BITS2-paper.pdf` remains the PerHeart paper, not BITS-2. CLAUDE.md §6 now carries a correction note saying so.

**Open questions for the user:** none new.

**Next step (waiting for user approval):** D00b — BITS-2 forensics plan, using `docs/papers/BITS2_DataInBrief_2024.pdf`. D01 (PPG-DaLiA ingestion audit) is to be marked as largely covered by D00a.

## 2026-10-12 01:10 — D00b — User decisions D00b (recorded before running)
**What I did:** Recorded the user's approval of the D00b plan, its changes and decisions 1–12 before any D00b code ran.

**Decisions made (user, 2026-10-12):**
- **Rate verdict, changed and fixed before results.**
  - (a) CONSISTENCY: the rate is "consistent" if the spread across files is under 15% (IQR/median) AND estimators A and B agree within 15% where both apply. This is reported overall, per activity and per subject.
  - (b) MATCH TO PAPER: the median estimate is reported against the stated 20 Hz.
  - Final verdict is one of three outcomes: "consistent and ≈20 Hz", "consistent but different from paper (rate stated)", or "inconsistent".
  - Time-dependent features are allowed only for the first two outcomes, and only after the user reviews the rate.
  - The report must include a section on what the rate means for abrupt-event detection (samples per 2 s window, whether impact peaks are captured).
1. user28 fall4 = fall8 → exclude BOTH (the true label is unknowable).
2. Only magnetometer shared → drop the `mgm` stream for both files and keep the files. Any shared acc/acg/gyro/hrt data → exclude both files.
3. HR is invalid if status −1, OR bpm = 0, OR bpm outside 30–220. Status 0 → keep but flag (`hr_unreliable=1`). Never impute.
4. A file is usable for HR/event analysis only if ≥80% of its HR rows are valid AND it has ≥20 valid HR rows. Files failing this remain usable for motion analysis (per-file scope: `motion_ok`, `hr_ok`).
5. adlK = paper Table 1 row K is accepted IF the duration cross-check agrees for most indices. Disagreeing indices (e.g. adl7/adl8) are flagged in the manifest and the report.
6. If the verdict is "inconsistent": no jerk or frequency features for BITS-2 v1, and no row-index proxy rate.
7. If files hold one trial each: accept ~984 published recordings, not 4,920. Never claim 4,920 anywhere.
8. Follow the data: `acg` includes gravity; record the paper conflict. The canonical BITS-2 ACC is the WITH-gravity stream (`acg`, which matches the E4).
9. Context proposal (report only; the user confirms before it goes into config):
   - adl1–2 → locomotion
   - adl3–4 → vigorous_activity
   - adl5–8 → vigorous_activity ("assumed stairs, not stated in paper")
   - adl13 → stationary
   - adl9–12 and adl14–16 → excluded from context training; included as motion hard negatives and in false-alert evaluation
10. Create `metadata/bits2_subjects.csv` from paper Table 2. Base HR may later feed relative-HR features. Health conditions are for analysis only, never model inputs.
11. Fetch the website's separate "without HR" data into a NEW folder `data/raw/bits2_website_nohr/` (existing raw folders untouched), add it to the checksum manifest, and compare its timestamps and values with the merged files. If it can't be downloaded from here, give the user the exact link.
12. Make `data/raw/bits2_website/` read-only like the other raw folders.

**Next step:** execute D00b as planned, in tmux `sao` and env `wearsafe`.

## 2026-10-12 01:30 — D00b — Operational definitions fixed before running the forensics script
**What I did:** Wrote down how each approved criterion is computed, before any rate, duration or repetition result was calculated. Where the user's wording left room, my interpretation is marked **[my interpretation]** so the user can overrule it.

**Decisions made (and why):**
- **Time unit:** BITS-2 `t` is taken as nanoseconds **[inferred]**. The paper does not state the unit. In D00a, resolvable HR steps were exactly 1e9, which matches the stated 1 Hz.
- **Estimator A, run length of rounded timestamps:** within one block of one stream, take runs of rows with an identical timestamp string. Only *interior* runs count: the previous run's value must be exactly v − step and the next run's v + step, where step = one unit of the last written significant digit. Each such run covers exactly one full step.
  - rate_A = median(run length) / step_seconds over those runs.
  - The primary stream is `acg` (the canonical ACC, decision 8). Other streams are reported too.
- **Estimator B:** `acg` rows ÷ HR rows (all HR rows, valid or not), i.e. IMU Hz if HR is 1 Hz and spans the same time.
- **(a) Consistency:**
  - Spread = IQR / median of the per-file rate_A (`acg`); must be < 15%.
  - A–B agreement **[my interpretation]**: per file, rel = |A − B| / ((A + B)/2). "Agree" if the median rel over files with both estimates is < 15%. The fraction of files with rel < 15% is also reported.
  - "Consistent" requires both. The same test is applied per activity and per subject (groups with ≥ 3 estimates).
- **(b) Match to paper:** median rate_A within ±10% of 20 Hz (18–22 Hz) counts as "≈20 Hz" (from the approved plan).
- **Duration cross-check (decision 5):** per index, median over files of (HR rows ≈ seconds) / stated single-trial duration. The index "agrees" if this is 0.6–1.6. The ratio against 5 × duration is also reported.
  - Disclosure: the per-index HR-row medians were already seen in D00a; the band was chosen to be generous.
- **Unambiguous repetition split:** every stream (`acc`, `acg`, `gyro`, `mgm`, `hrt`) must show the same number of segments, separated by a timestamp reset (a decrease of more than one step) or a forward jump of more than 5 steps. Each piece must be 0.6–1.6 × the stated trial duration (by HR rows).
  - The low-motion (≥ 2 s) check needs a trustworthy rate. If the verdict is "inconsistent", that check cannot pass, so **no split** is made and the file is flagged.
- **Shared-data detection:** a values-only hash (no timestamps) of each stream in each file with ≥ 20 rows, plus a hash of the first 50 rows to catch partial copies. Compared across all files.
- **Saturation:** the fraction of samples with |axis| ≥ 0.999 × the stream's observed maximum |axis| over all files.
- **E4 comparison:** 2 g = 19.6133 m/s² (g = 9.80665).
- **motion_ok** = the file is not excluded and has `acg` rows.
- **hr_ok** (decision 4) = motion_ok AND ≥ 80% of HR rows valid AND ≥ 20 valid HR rows. HR rows dropped as malformed count as invalid.

## 2026-10-12 02:05 — D00b — Amendments after a trial run (disclosed)
**What I did:** Did a trial run of `scripts/d00b_bits2_forensics.py` with outputs written to scratchpad only. That run found a bug in one operational definition, so I amended it before the final run.

**Decisions made (and why):**
- **Gap rule:** "forward jump > 5 rounding steps" misfires on the few rows with full-precision timestamps, where one step is microseconds. Example: `fall/user16/user16_fall3.csv` `acg` was cut into 684 "segments".
  - Amended to: gap = forward jump > max(5 steps, **1 s**). At any plausible IMU rate (≥ 1 Hz), a jump over 1 s is a real gap.
  - This changes only which files get the `R4b_timestamp_discontinuity` flag. It does not change the rate verdict criteria or any exclusion rule.
- **Added a report-only column** `repeated_blocks_identical`: for files with repeated block sets (e.g. `user7_fall3`), whether the repeats are value-identical copies.
- **Disclosure:** the trial run's rate verdict was "inconsistent", and the fixed criteria above were not changed after seeing it.

## 2026-10-12 02:40 — D00b — BITS-2 forensics and exclusion list
**What I did:**
- Read the BITS-2 paper (Nandi et al. 2024).
- Made `data/raw/bits2_website/` read-only (decision 12).
- Downloaded the website's "without HR" files into the new, read-only folder `data/raw/bits2_website_nohr/` (decision 11).
- Built checksum manifest v2.
- Extracted paper Table 2 to `metadata/bits2_subjects.csv` (decision 10).
- Wrote the shared parser `src/wearsafe/bits2_io.py` (with tests) and `scripts/d00b_bits2_forensics.py`. Ran it in tmux `sao`, env `wearsafe`, on CPU. GPU not needed (CPU-only parsing); nvidia-smi not run, per user instruction.
- Wrote `reports/D00b_bits2_forensics.md`.

**Files created/changed:**
- New code: `src/wearsafe/bits2_io.py`, `scripts/download_bits2_nohr.py`, `scripts/make_bits2_subjects.py`, `scripts/d00b_bits2_forensics.py`, `tests/test_bits2_io.py`.
- Changed code: `src/wearsafe/raw_manifest.py` (adds `CURRENT_MANIFEST` = v2) and `tests/test_raw_data_unchanged.py` (now uses the current manifest).
- Metadata: `metadata/bits2_file_manifest.csv`, `metadata/bits2_exclusions.csv`, `metadata/bits2_subjects.csv`, `metadata/bits2_nohr_download.csv`, `metadata/raw_checksums_v2.csv`.
- Reports: `reports/D00b_bits2_forensics.md`, `reports/D00b_bits2_forensics_tables.md`.
- Raw data: added `data/raw/bits2_website_nohr/` (984 files, read-only); changed `data/raw/bits2_website/` permissions only.
- Logs: `logs/2026-10-12_D00b_*.log` (not committed).

**Checks run and results:**
- Parser tests: 4/4. The parser's per-stream totals equal D00a's (acc 637,950; acg 627,774; gyro 638,732; mgm 616,824; hrt 51,903).
- Manifest v2: all 2,126 v1 files have unchanged SHA-256; the 984 new entries are all in `bits2_website_nohr/`.
- `pytest`: 16 passed, 1 skipped. Full SHA-256 mode: 3/3 passed.
- Determinism: a second run of the forensics script reproduced all three outputs byte-for-byte.
- Every one of the 984 files appears once in the manifest, and every exclusion row has a rule_id.

**Results (details in reports/D00b_bits2_forensics.md):**
- **Copies:** the website full copy is identical 984/984. The website "without HR" files are byte-identical to the merged files (984/984, they still contain HR). The 4 JS-built user31 names return 404.
- **Rate:**
  - acg estimator A: median 25.8 Hz, IQR/median 1.82 (n = 87 files).
  - Estimator B: median 20.2 Hz. A–B median relative difference 0.85.
  - The method check on HR gives exactly 1.00 Hz (142 files).
  - **Verdict: "inconsistent".** Best-resolved files cluster near ~50 Hz.
- **Repetitions:** ≈1 trial per file. No unambiguous split points, so no splits proposed. Under decision 7, ~984 recordings, never 4,920.
- **Duration cross-check:** 15/24 indices agree, so the index mapping is accepted. 9 indices (adl7, adl8, adl10, adl11, adl14, adl15, adl16, fall1, fall5) are flagged (R6).
- **Exclusions:**
  - R1: user28 fall4/fall8 (exact duplicate).
  - R2: user29 adl13/adl14 (identical HR series; **new finding**).
  - R4: user7 fall3 (two recordings, ambiguous).
  - Total 5 files excluded. R3: `mgm` dropped for user5_adl2 and user40_adl4. R5: user31 `_.fallN` mapped and flagged.
- **HR:** 10.1% of rows invalid (status −1: 5,246). hr_ok 437/984; motion_only 542.
- **ACC:**
  - `acg` includes gravity (lying still 9.87 vs `acc` 0.14), which contradicts the paper text. Canonical ACC = `acg`.
  - Full scale 78.45 m/s² = 8 g; saturation 0.009%.
  - 288/328 fall files peak above the E4's 2 g.

**Decisions made (and why):**
- All exclusion rules follow user decisions D00b-1 to D00b-12 and the operational definitions logged before running. The post-trial amendment (gap floor of 1 s) is disclosed above.
- No split was applied anywhere, and nothing was written to `config/`.

**Problems / surprises:**
- The paper's names for `acc`/`acg` are reversed relative to the data.
- The paper's "two CSVs per activity" are identical files on the website.
- The IMU often covers only the end part of the HR record.
- user29 adl13/adl14 share HR.

**Open questions for the user:** see report §10:
1. rate-free features only for BITS-2 v1?
2. BITS-2 windowing approach;
3. adl7/adl8 handling;
4. scope of event-centred HR analysis;
5. the 123 R4b-flagged files;
6. confirm the context map (§8);
7. subjects with cardiac conditions.

**Next step (waiting for user approval):** none started.

## 2026-10-12 04:20 — D00b — User decisions after D00b (recorded before any further work)
**What I did:** Recorded the user's answers to the D00b report §10 questions, a proposed design change, a permanent data ban, an evaluation rule, and the user's answers to the D02/D03 plan questions (P1–P8). No data was processed for this entry.

**Files created/changed:** `PROJECT_LOG.md`, `config/label_maps.yaml`, `config/evaluation_v1.yaml` (new), `CLAUDE.md` (§2.3: two bullets inserted, nothing removed).

**Checks run and results:** none needed for this entry (recording only). See the D00b-follow-up entry below for manifest v3 and tests.

**Decisions made (and why):**
User decisions on the D00b questions (user's wording kept):
- **Q1:** BITS-2 v1 uses only time-independent motion features: magnitude percentiles, peak magnitude (note: may be underestimated in low-rate files), and FRACTION (not count) of samples above thresholds such as 2 g. No jerk, no frequency, no sample-count features.
- **Q2:** BITS-2 is EXCLUDED from v1 motion-model training. Whole-file features are used only for a descriptive fall-vs-ADL analysis (compare percentiles and fractions, not just maxima, since ADL files are longer than fall files). No fixed-sample-count windows.
- **Q3:** adl7/adl8 are kept for motion (motion_ok) and excluded from HR analysis.
- **Q4:** The event-centred before/during/after HR analysis for BITS-2 is POSTPONED, because fall timing cannot be placed on the HR timeline. It is replaced by a coarse whole-file comparison of HR in fall vs ADL files, clearly labelled coarse.
- **Q5:** Timestamp-break files stay flagged; only files whose break shows two recordings joined are excluded.
  - **Operational definition (accepted by the user as P1):** "two recordings joined" = every stream (acc, acg, gyro, mgm, hrt) shows the same number (≥ 2) of segments. This uses the segment definition fixed before the D00b run (`repetition_verdict` starting `ambiguous_2_segments` in `metadata/bits2_file_manifest.csv`).
  - Eight files carry that verdict. user7_fall3 is already excluded (R4). The 7 others would be excluded: user20_adl2, user27_adl8, user29_adl12, user5_adl5, user8_adl13, user9_adl3, user9_adl5.
  - **Application is deferred** to the next BITS-2 processing milestone, which will write `metadata/bits2_exclusions_v2.csv`. v1 stays unchanged.
- **Q6:** The BITS-2 activity classes in D00b report §8 are confirmed as a proposal for analysis and hard negatives only. The v1 context model trains on PPG-DaLiA only.
- **Q7:** Subjects with health conditions stay in. Use relative-to-baseline HR, and report results per subject.
- **D01** is marked as covered by D00a.

**PROPOSED DESIGN CHANGE — status: proposed, pending audits (NOT applied to config):**
- BITS-2 is demoted from main abrupt-motion source to a supporting dataset (time-independent motion features, coarse HR comparisons).
- FallAllD is promoted to main motion-training candidate, and UP-Fall becomes external validation. Both are pending their audit (D00c).
- A "device harmonisation" experiment is added for the motion branch: resample to a common rate and clip to ±2 g, applied identically to all datasets. It is always reported alongside the unharmonised version.

**PERMANENT BAN (added to CLAUDE.md §2.3):** `data/raw/fallalld/FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl` must never be used for training, validation, testing or analysis. It contains SMOTE-generated synthetic samples, filtered activities and unknown downsampling. Only the original FallAllD.pkl may be used, and activity_info.pkl must be verified against the original paper before use.
- The user approved an added clause: the ban covers the copy inside `data/raw/fallalld/fallalld.zip` and any extracted copy. At present the folder holds only `fallalld.zip`; it was not opened.

**EVALUATION RULE (user, added to CLAUDE.md §2.3 and `config/evaluation_v1.yaml`):** "False alerts per user-hour may only be computed on subjects whose data was NOT used to train or tune ANY component model or fusion threshold involved in that evaluation. For PPG-DaLiA this means subject-held-out (e.g. LOSO) predictions only. Fusion thresholds are tuned on validation subjects only, never on the subjects used to report false alerts."

**User answers to the D02/D03 plan:**
- **P1:** see Q5.
- **P2:** The purity threshold for `train_candidate` is 1.0. Boundary windows stay in false-alert evaluation.
- **P3:** All PPG-DaLiA windows are `motion_event_class = normal_adl`, transient included. The "PROPOSED" mark is removed from label_maps.
- **P4:** The primary BVP-HR vs ECG comparison uses the dataset's 8 s / 2 s reference windows. A secondary table uses the 30 s physiology windows (hr_ref averaged over the reference windows fully inside each 30 s window).
- **P5:** The template-matching PPG SQI and the `physiology_uncertain` threshold of 0.9 are fixed now. A REPORT-ONLY sensitivity table at SQI thresholds 0.80/0.85/0.90/0.95 is added; it must not be used to change the v1 threshold.
- **P6:** Context-doc §14 features only; per-axis extras are a later ablation.
- **P7:** Windows are stored as index references into Layer A.
- **P8:** The smoke subjects are PPGDALIA_S03 and PPGDALIA_S06.
- **Additional rules:**
  - **B.** PPG-DaLiA has no arousal labels, so `arousal_class` is null for all PPG-DaLiA windows (never inferred from activity or HR). An invariant check enforces this.
  - **C.** The smoke report shows ACC magnitude, the activity timeline and window labels around one activity boundary per subject.

**Problems / surprises:** The banned .pkl is not a loose file on disk; only `fallalld.zip` is present.

**Open questions for the user:** none.

**Next step (waiting for user approval):** Approved: manifest v3 and read-only folders, then the D02 smoke test (S03 + S06) only. Then stop.

## 2026-10-12 04:45 — D00b follow-up — FallAllD/UP-Fall read-only, raw checksum manifest v3
**What I did:**
- Made `data/raw/fallalld/` and `data/raw/upfall/` read-only (`chmod -R a-w`; permissions only, mtimes unchanged). Contents not inspected (D00c).
- Built checksum manifest v3 in tmux `sao`, env `wearsafe` (log `logs/2026-10-12_D00b_raw_manifest_v3.log`). No GPU needed (hashing only).
- Pointed `CURRENT_MANIFEST` to v3. v1 and v2 are kept.

**Files created/changed:** `metadata/raw_checksums_v3.csv` (3,112 files), `src/wearsafe/raw_manifest.py`.

**Checks run and results:**
- v3 minus the two new files is identical to v2 (every path, size, mtime and SHA-256), so no existing raw file changed.
- New files: `data/raw/fallalld/fallalld.zip` (569,377,411 B), `data/raw/upfall/upfall-data.zip` (20,099,632 B).
- `WEARSAFE_FULL_CHECKSUM=1 pytest`: 17 passed (log `logs/2026-10-12_D00b_pytest_manifest_v3.log`).

**Decisions made (and why):** none new.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** D02 smoke test (approved).

## 2026-10-12 05:00 — D02 — Smoke test: PPG-DaLiA normalisation + windowing (S03, S06)
**What I did:**
- Wrote the Layer A normalisation and Layer B windowing code, configs and tests. These were committed before the run (1022b0a).
- Ran a trial into the scratchpad, then the official run in tmux `sao`, env `wearsafe`, on CPU. No GPU was needed, so no GPU was selected.
- The trial passed unchanged. No code changed between the trial and the official run, and the trial outputs served as the independent re-run for the determinism check.
- Generated tables and boundary plots with `scripts/d02_smoke_report.py`.
- Logs: `logs/2026-10-12_D02_smoke_trial.log`, `logs/2026-10-12_D02_smoke.log`.

**Files created/changed:**
- **Code:** `src/wearsafe/ppg_dalia_io.py`, `src/wearsafe/windowing.py`, `src/wearsafe/schemas.py` (`acc_saturated`, window fields, forbidden columns).
- **Config:** `config/windowing_v1.yaml`, `config/features_v1.yaml` (D03 parameters fixed now, not used yet).
- **Scripts:** `scripts/d02_ppg_dalia_normalize.py`, `scripts/d02_ppg_dalia_windows.py`, `scripts/d02_smoke_report.py`.
- **Tests:** `tests/test_ppg_dalia_normalize.py`, `tests/test_windowing.py`, `tests/test_ppg_dalia_outputs.py`, `tests/test_schemas_and_label_maps.py` (extended).
- **Outputs:**
  - data: `data/interim/ppg_dalia/normalized_signals_smoke_v1/`, `data/interim/ppg_dalia/windows_smoke_v1/`;
  - metadata: `metadata/ppg_dalia_subjects_smoke_v1.csv`;
  - reports: `reports/D02_ppg_dalia_smoke.md`, `reports/D02_ppg_dalia_smoke_v1_tables.md`, `reports/figures/D02_smoke_v1/`.

**Checks run and results:**
- **Invariant checks:** 149/149 passed (26 normalisation, 123 windowing). They cover:
  - durations and rates, the hr_ref count, units/E4 counts and NaN = 0;
  - label seconds against raw, and the S6 duration and missing activities;
  - window counts against the formula, exact samples per window, and recording bounds;
  - unique IDs, purity recomputed from raw, and crosses_boundary ⇔ purity < 1;
  - arousal null (decision B), normal_adl (P3), roles (P2), and n_hr_ref by brute force.
- **Label seconds** equal the D00a table (max difference 0 s).
- **Window counts:**
  - S03: 8740 / 3495 / 581;
  - S06: 5249 / 2099 / 349 (2 s / 5 s / 30 s).
- **Saturated ACC samples:** S03 0.29%, S06 0.38%. The highest rates are S03 cycling at 4.6% and S06 table soccer at 2.5%.
- **Determinism:** all 12 output tables and the subject metadata are identical across the two runs.
- **pytest:** 37 passed, 1 skipped (the full SHA-256 test, opt-in; it ran earlier with 17 passed on v3).

**Decisions made (and why):**
- **Window eval_role names:** `train_candidate`, `false_alert_eval` (lunch/transient) and `false_alert_eval_only` (training label with purity < 1), as in `config/windowing_v1.yaml`.
- **Saturation flag:** a sample is flagged when any axis is at −128 or +127 counts. A +127 reading may be genuine 1.984 g; it is flagged anyway, and this is documented.
- **Lunch:** `context_class` stays the literal `TODO` from label_maps. It is never `train_candidate` (checked).

**Problems / surprises:**
- **Label timing (visual observation only, no action):** activity labels follow the protocol, not the movement.
  - S03: the transient period before the stairs looks like walking.
  - S06: walking-like motion starts before the stairs label.
  - Transient windows can therefore contain real locomotion, and the edges of activities carry some label noise.

**Open questions for the user:** none blocking. Approval is needed for the full D02 run (15 subjects, tag `v1`).

**Next step (waiting for user approval):** full D02 run. D03 is not started.

## 2026-10-12 04:28 — D02 — Correction: entry timestamps
**What I did:** The headings of the two previous entries say 04:45 and 05:00, which is later than when they were written. The work actually finished at about 04:28 (system clock). The entries were not edited, because the log is append-only; this note corrects them. Their order is correct.
**Files created/changed:** PROJECT_LOG.md (this entry only).
**Checks run and results:** none.
**Decisions made (and why):** none.
**Problems / surprises:** none.
**Open questions for the user:** none.
**Next step (waiting for user approval):** full D02 run.

## 2026-10-12 04:30 — D02 — User decision: boundary margin for training windows (recorded before the full run)
**What I did:** Recorded a new training rule decided by the user before any model exists, and a new versioned windowing config.

**Files created/changed:** `PROJECT_LOG.md`, `config/windowing_v2.yaml` (new; `config/windowing_v1.yaml` is kept because `windows_smoke_v1` was built with it).

**Checks run and results:** none (recording only).

**Decisions made (and why):**
- **New per-window field `seconds_to_nearest_boundary`:** the distance from the window to the nearest change in the activity label, including changes to and from transient.
  - Label changes are at times i/4 s, where activity sample i differs from sample i−1.
  - For a window [start, end), the distance is 0 if a change lies inside it. Otherwise it is the smallest of (start − change) over changes before the window and (change − end) over changes after it.
  - The recording start and end are not label changes. If the recording has no change at all, the value is +inf.
- **New training rule (user):** a window is `train_candidate` only if purity = 1.0 AND `seconds_to_nearest_boundary` ≥ 10 s.
  - Windows that fail only the 10 s margin get eval_role `false_alert_eval`. They are kept, not dropped.
  - Boundary-crossing windows (purity < 1) stay `false_alert_eval_only`, and lunch/transient stay `false_alert_eval`.
- **Reason (user):** the D02 smoke test showed that labels follow the protocol schedule, not the actual movement, so activity edges are noisy.
- **The 10 s margin is fixed now and must not be tuned later based on model results.**
- **Versions:**
  - Windows built with `config/windowing_v2.yaml`: the smoke outputs as a new version, `windows_smoke_v2` (from `normalized_signals_smoke_v1`; `windows_smoke_v1` is kept), and the full run as `windows_v1` (from `normalized_signals_v1`).
  - Each `run_info.json` records which windowing config was used.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: apply the rule to the smoke outputs (smoke_v2), then run the full D02 on all 15 subjects, then stop. D03 is not started.

## 2026-10-12 04:40 — D02 — Full run (15 subjects) + boundary-margin rule; smoke re-versioned
**What I did:**
- Implemented `seconds_to_nearest_boundary` and the 10 s margin training rule (`config/windowing_v2.yaml`). The code was committed before any run (4d89fee).
- Ran in tmux `sao`, env `wearsafe`, on CPU (no GPU needed). Scratch trial runs of smoke_v2 and the full run went first, then the official runs. No code changed between them, and the trial outputs served as the independent re-run for determinism.
- Log: `logs/2026-10-12_D02_full.log`.

**Files created/changed:**
- **Code:** `src/wearsafe/windowing.py` (`change_times`, `seconds_to_nearest_boundary`); `scripts/d02_ppg_dalia_windows.py` (`--in-tag`, `--config`, margin rule and checks); `scripts/d02_smoke_report.py` (role tables, margin effect, saturation pivot).
- **Tests:** `tests/test_windowing.py`, `tests/test_ppg_dalia_outputs.py`.
- **Outputs:**
  - data: `data/interim/ppg_dalia/windows_smoke_v2/`, `data/interim/ppg_dalia/normalized_signals_v1/`, `data/interim/ppg_dalia/windows_v1/`;
  - metadata: `metadata/ppg_dalia_subjects_v1.csv`;
  - reports: `reports/D02_ppg_dalia_full.md`, `reports/D02_ppg_dalia_v1_tables.md`, `reports/D02_ppg_dalia_smoke_v2_tables.md`, `reports/figures/D02_v1/` (15 plots), `reports/figures/D02_smoke_v2/`.
- `windows_smoke_v1` is kept unchanged.

**Checks run and results:**
- **Invariant checks:** full run 1310/1310 passed (182 Layer A + 1128 Layer B); smoke_v2 179/179. The new checks are:
  - `seconds_to_nearest_boundary` equals a brute-force recomputation;
  - crossing windows have distance 0;
  - train_candidate ⇔ (training label & purity 1.0 & margin ≥ 10 s);
  - pure windows within the margin are `false_alert_eval`.
- **Label seconds** equal the D00a table for all 15 subjects (max difference 0 s). Window counts equal the formula everywhere.
- **Margin effect:** 3.07% of pure motion, 3.08% of context and 3.01% of physiology training-label windows moved to `false_alert_eval`.
- **Train candidates (motion/context/physiology):** 65079 / 25920 / 4155. All per-subject × activity tables are in `reports/D02_ppg_dalia_v1_tables.md` §5b.
- **Saturation:** 0.12–0.38% of ACC samples per subject; up to 5.8% in cycling (S02). 3.8–9.1% of motion windows contain ≥1 saturated sample.
- **Determinism:** all 65 output tables are identical to the scratch re-run.
- **pytest:** 42 passed, 1 skipped (the full SHA-256 test is opt-in).

**Decisions made (and why):**
- The smoke re-version is named `windows_smoke_v2` and built from `normalized_signals_smoke_v1`. The full run is `normalized_signals_v1` + `windows_v1`, built with windowing config v2. `run_info.json` records the config.

**Problems / surprises:**
- **Visual observation, no action:** in S01, walking-like motion starts while the label is still "sitting", earlier than the 10 s margin zone. So some edge noise remains beyond 10 s. The margin is fixed and was not changed.
- **Suggestion for the user (not done):** a report-only D03 table of motion features by distance-to-boundary bins, to measure this.

**Open questions for the user:** whether to add the report-only distance-to-boundary table in D03.

**Next step (waiting for user approval):** D03. Not started.

## 2026-10-12 04:52 — D00c — FallAllD and UP-Fall inventory and audit (look-only)
**What I did:**
- Listed both zips without extracting.
- Extracted only the allowed members into `data/interim/_unzipped/{fallalld,upfall}/` (read-only copies).
  - Every extracted file's SHA-256 equals the zip stream, and CRC32 matches.
  - The banned `FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl` (241,792,100 B) was listed only: not extracted, not loaded.
- Read both papers, rendering the FallAllD Fig. 4/Fig. 8 activity lists as images. There is no readme in either zip.
- Scanned the pickle opcodes, then loaded both FallAllD pickles with a restricted unpickler (pandas/numpy only).
- Audited the FallAllD wrist data and the UP-Fall wrist data.
- Ran in tmux `sao`, env `wearsafe`, CPU only. Logs: `logs/2026-10-12_D00c_*.log`.
- No preprocessing, windowing, features or models.

**Files created/changed:**
- **Scripts:** `scripts/inspect/d00c_extract.py`, `d00c_audit.py`, `d00c_followup.py`, `explore_fallalld.py`, `inspect_fallalld_structure.py`, `pickle_globals.py`; `scripts/inspect/common.py` (added `RestrictedUnpickler`).
- **Metadata:** `metadata/fallalld_file_manifest.csv`, `metadata/upfall_file_manifest.csv`.
- **Reports:** `reports/D00c_fallalld_upfall_audit.md`, `reports/D00c_fallalld_upfall_audit_tables.md`.
- **Extracted copies:** `data/interim/_unzipped/` (not in git). `data/raw/` was not touched.

**Checks run and results:**
- **FallAllD structure:** 6,605 records × 4 sensors = 26,420 (= the paper's "files").
  - Every record is 20 s: Acc/Gyr 4,760, Mag 1,600, Bar 200 samples, i.e. 238/80/10 Hz.
  - Falls/ADLs per device equal paper Fig. 8 exactly; wrist has 523 falls + 1,992 ADLs.
- **FallAllD wrist subjects:** 13 subjects, only **9 with falls** (the paper says 10). No S7/S8; S4, S10, S11 and S12 are ADL-only. Waist has 13/11 subjects (the paper says 14/12).
- **FallAllD activity IDs:** the data follows `activity_info.pkl` (= the Fig. 8 order); IDs 1–12 are wrist-only hand activities. **Paper Fig. 4's explicit numbering does not match the data.** 65/79 names match Fig. 8 exactly; the other 14 differ in wording only.
- **FallAllD units:** int16 counts. The paper gives no factor; 4,096 counts/g is inferred (±8 g on int16), and measured still-wrist gravity is 4,064 counts (0.992 g).
  - 0 samples at the rails.
  - 100% of wrist falls and 50.5% of wrist ADLs peak above 2 g (median fall peak 7.74 g).
- **FallAllD duplicates:** ACC/Gyr/Bar have no duplicates. One Mag pair is identical (S12 waist, falls 113/120 trial 1).
- **FallAllD impact timing:** wrist fall peaks sit at the clip centre (median 10.00 s; 96.6% in 8–12 s).
- **UP-Fall contents:** the complete CSV holds raw wearable data (not only features): 294,678 rows (the paper says 296,364), 559/561 trials. The missing S8 A11 T2–T3 match paper Table 7. The 3 feature CSVs cover one trial only.
- **UP-Fall wrist rate:** resampled to camera timestamps [stated in paper]; rows at 15–21 Hz per trial, irregular. ~33% of ACC rows repeat the previous row on every IMU (gyro repeats <1%), so **~11.9 new ACC values per second** (median per trial).
- **UP-Fall wrist range:** max 9.26 g; the range is not stated in the paper.
  - 95.7% of fall trials and 31.9% of ADL trials peak above 2 g.
  - Median fall peak 3.66 g (a mattress was used).
- **UP-Fall Tag 20:** occurs only in activity 2, for 4 subjects; undocumented.
- **pytest:** 42 passed, 1 skipped (the raw-data-unchanged fast test passes).

**Decisions made (and why):** none on the design. The recommendation is in the report (§5); the user decides.

**Problems / surprises:**
- Paper Fig. 4 numbering conflicts with the data and with `activity_info.pkl`.
- The FallAllD unit factor is not published.
- The fall-impact clip-centre position is a possible shortcut.
- UP-Fall's effective ACC rate is ~12 Hz.
- Table C2 in the tables file is empty (a `.head(0)` bug in `d00c_followup.py`; the line under it is correct).
- The tables file was appended once by the follow-up script (Part C); Parts A–B are unchanged.

**Open questions for the user:** report §7, decisions 1–9:
1. accept the design change;
2. the 4,096 counts/g factor;
3. `activity_info.pkl` as the label source;
4. near-fall ADLs 15/23;
5. neck/waist use;
6. the clip-position rule;
7. UP-Fall Tag 20 and trial vs sample labels;
8. harmonised rate (32 Hz + ~12 Hz variant);
9. the device-discrimination check.

**Next step (waiting for user approval):** none started. D03 is not started.
