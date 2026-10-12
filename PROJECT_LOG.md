# PROJECT_LOG — WearSafe AI

## Current status
- **Current milestone:** M01-demo (demo sprint, tag demo_v0, PRELIMINARY) — DONE, waiting for the user. D08 DONE.
- **Environment:** conda env `wearsafe` (Python 3.11.17), `requirements.txt` + `requirements-lock.txt`.
- **Data version:** PPG-DaLiA Layer A `data/interim/ppg_dalia/normalized_signals_v1/`; Layer B `windows_v1/` (built with `config/windowing_v2.yaml`: purity 1.0 + 10 s boundary margin). Smoke versions `*_smoke_v1` and `windows_smoke_v2` are kept. Raw checksum manifest **v3** `metadata/raw_checksums_v3.csv` (3,112 files; v1 and v2 kept). BITS-2: `metadata/bits2_file_manifest.csv`, `metadata/bits2_exclusions.csv` (v1; the Q5 rule is defined for v2). PPG-DaLiA features v1: `data/processed/{motion,context,physiology}/ppg_dalia_features_v1.parquet` (config `features_v1.yaml`). FallAllD v1: `data/interim/fallalld/*_v1/`, features `data/processed/motion/fallalld_{unclipped,e4_clipped}_features-{v1,v2}_v1.parquet`.
- **Split version:** `splits/fallalld_v1.json` (FallAllD wrist LOSO, 13 folds); `splits/ppg_dalia_v1.json` (PPG-DaLiA LOSO, 15 folds).
- **Last validated result:** M01-demo 2026-10-12 (PRELIMINARY): FallAllD RF PR-AUC 0.83 (unclipped) / 0.77 (e4_clipped), ADL-clip false alarm 11–14%; PPG-DaLiA context RF macro-F1 0.72; device check AUC 0.72–0.84. Results in `results/2026-10-12_M01_demo_v0_run2/`.
- **Open items:** shortcut baselines (position-only (a)/(b comparative)/(c), peak-only, saturation-only) and dedup + clip-level metrics are required at the first motion-model milestone; findings for later 1–4 (v2 SQI threshold, 30 s margin experiment, motion-aware physiology gate, longer HR baseline).
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

## 2026-10-12 04:57 — D00c — User decisions after D00c (recorded; no data processed)
**What I did:**
- Recorded the user's decisions on D00c report §7.
- Added two rules to CLAUDE.md §2.3 (inserted, nothing removed).
- Appended §44 to `docs/WearSafe_AI_Context.md`.
- Added config entries.
- Wrote a corrected table C2 for the D00c tables file as a new appended section. The old empty table is kept.

**Files created/changed:** `PROJECT_LOG.md`, `CLAUDE.md`, `docs/WearSafe_AI_Context.md` (§44 appended), `config/label_maps.yaml` (new `fallalld` and `upfall` blocks), `config/motion_harmonisation_v1.yaml` (new), `config/evaluation_v1.yaml` (FallAllD evaluation added), `scripts/inspect/d00c_c2_fix.py` (new), `reports/D00c_fallalld_upfall_audit_tables.md` (Part D appended), `tests/test_schemas_and_label_maps.py`.

**Checks run and results:** see the commit; pytest is run after the edits.

**Decisions made (and why)** (user, after D00c):
1. **Design change ACCEPTED:**
   - FallAllD wrist is the main motion-training source.
   - UP-Fall is a separate low-rate stress test, not realistic validation.
   - BITS-2 is a supporting dataset (as decided after D00b).
   - Summarised in context doc §44; §8–§10 and §40 are not edited.
2. **FallAllD ACC conversion: 4096 counts/g, tagged [inferred].**
   - Verify it in the next FallAllD milestone: the median ACC magnitude in low-motion periods across many ADL records must be within 1 ± 0.05 g. Otherwise STOP and report.
3. **Label source:** `activity_info.pkl` is the FallAllD label source. Fig. 4 numbering is ignored; the differences from Fig. 8 are wording only.
4. **Near-fall ADLs:** "Stumbling" (ID 23) and "Fail to stand up" (ID 15) are excluded from motion training and kept as hard-negative evaluation probes.
5. **Devices:** wrist device only for FallAllD and UP-Fall. Neck/waist are not used.
6. **RULE (CLAUDE.md §2.3):** FallAllD clip position must not be revealed; every motion model is checked against a position-only baseline that must perform at chance level.
7. **UP-Fall labels:** trial-level labels only. Tag 20 is treated as part of its trial, and per-sample tags are not used in v1.
8. **Harmonised motion format:**
   - ACC in m/s² at 32 Hz, in two versions, `unclipped` and `e4_clipped` (±2 g). Any evaluation involving PPG-DaLiA or WESAD uses `e4_clipped`.
   - UP-Fall gets a separate ~12 Hz version.
   - **Note (user):** false-alert rates measured on PPG-DaLiA may be optimistic for wider-range watches, because PPG-DaLiA's own data is clipped at ±2 g.
9. **RULE (CLAUDE.md §2.3):** run and report a device-discrimination check before training or evaluating any model on data that mixes two datasets or devices.
10. **Gyroscope:** not used in v1 motion models (the E4 has none).
11. **FallAllD evaluation:**
    - leave-one-subject-out;
    - fall-detection metrics on the subjects who performed falls;
    - false-positive metrics on all subjects;
    - pooled out-of-fold predictions for overall PR-AUC.
    - Motion training is falls vs ADLs within FallAllD only; PPG-DaLiA is used only for false-alert evaluation.

**My interpretation, for the user to overrule:**
- In decision 8, "±2 g" for `e4_clipped` means the exact E4 rails [−2.0 g, +127/64 g = +1.984375 g] per axis, as observed in PPG-DaLiA (D00a).
- In decision 4, "excluded from motion training" means neither positive nor negative training examples.

**Problems / surprises:** the C2 bug was a stray `.head(0)` in `scripts/inspect/d00c_followup.py`. That script is left unchanged, so it still describes how Part C was produced. The corrected table comes from the new `scripts/inspect/d00c_c2_fix.py` (Part D).

**Open questions for the user:** none.

**Next step (waiting for user approval):** none started.

## 2026-10-12 05:05 — D00c — Checks after recording the D00c decisions
**What I did:**
- Ran the C2 fix (`scripts/inspect/d00c_c2_fix.py`, log `logs/2026-10-12_D00c_c2_fix.log`). It read the extracted FallAllD pickles only and appended Part D to the tables file.
- Added tests for the recorded decisions.

**Files created/changed:** as listed in the 04:57 entry.

**Checks run and results:**
- YAML parses.
- pytest: 45 passed, 1 skipped (the full SHA-256 test is opt-in).
- The new test caught an arithmetic slip in my first draft of `config/motion_harmonisation_v1.yaml` (`clip_m_s2` upper bound written as 19.45989). It is corrected to 127/64 × 9.80665 = 19.46007109375 m/s² before commit.
- Part D (corrected C2):
  - wrist trial numbers per activity, and max TrialNo per subject (6–14);
  - 72 of 811 wrist (subject, activity) groups have trial numbers that are not exactly 1..n, which suggests gaps in the trial numbering [inferred]. This is a note only; no action.

**Decisions made (and why):** none new.

**Problems / surprises:** the trial-numbering gaps above.

**Open questions for the user:** none.

**Next step (waiting for user approval):** none started.

## 2026-10-12 05:05 — D03 — Start: features + wrist-PPG vs ECG, SMOKE (S03, S06); parameters fixed before running
**What I did:** Wrote the D03 code and tests before any D03 run. Inputs are D02 v1 (`normalized_signals_v1`, `windows_v1`, windowing config v2 roles).

**Files created/changed:**
- **Code:** `src/wearsafe/features.py`; `scripts/d03_ppg_dalia_features.py`, `scripts/d03_bvp_hr_vs_ecg.py`, `scripts/d03_report.py`.
- **Tests:** `tests/test_features.py`.
- **Config/schema:** `config/features_v1.yaml` (additions below); `src/wearsafe/schemas.py` (`seconds_to_nearest_boundary` and `window_name` added to the forbidden feature columns).

**Checks run and results:** pytest passes before the run (see the commit).

**Decisions made (and why):**
- **User decisions applied:**
  - **P4:** primary comparison on 8 s/2 s reference windows, plus a secondary 30 s table.
  - **P5:** template-match SQI with the threshold fixed at 0.9, plus a report-only sensitivity table at 0.80/0.85/0.90/0.95.
  - **P6:** §14 features only.
  - **New report-only table** of motion features by `seconds_to_nearest_boundary` bins (0–5, 5–10, 10–20, 20–40, 40+ s) per activity. It must not change the 10 s rule or any v1 training role.
- **Parameters added to `config/features_v1.yaml` before the run** (none were tuned on results):
  - Butterworth order 2, zero-phase, applied to each window's own samples;
  - the stored BVP polarity is used as is;
  - the 8 s HR estimator is 60 / median valid IBI (NaN if < 2 valid IBIs, reported as coverage);
  - hr_delta and hr_slope definitions;
  - NaN rules;
  - boundary bins;
  - skewness SQI as a report-only secondary.
- **Window-HR estimator (my choice, overrulable):** the 8 s windows use the median IBI (robust to single missed or extra beats), while the 30 s features use the mean of instantaneous HR.
- **Constant windows:** dominant frequency, spectral entropy and spectral energy are 0, so motion features never produce NaN.
- **has_hr:** the feature table's `has_hr` contract column is left out, because PPG-DaLiA has no native wrist HR stream. The ECG reference is ground truth, not an input; `has_hr_ref` is carried as a forbidden meta column.

**Problems / surprises:** none yet.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: run the smoke test (trial run to scratch, then the official run), then stop.

## 2026-10-12 05:12 — D03 — Smoke test done: features + wrist-PPG vs ECG (S03, S06)
**What I did:**
- Ran the D03 smoke test in tmux `sao`, env `wearsafe`, on CPU (no GPU needed).
- A trial run into the scratchpad came first, then the official run, with no code changes in between. The trial outputs served as the determinism comparison. Log: `logs/2026-10-12_D03_smoke.log`.
- Generated the tables with `scripts/d03_report.py`.

**Files created/changed:**
- **Features:** `data/processed/{motion,context,physiology}/ppg_dalia_features_smoke_v1.parquet`, plus `data/processed/ppg_dalia_features_smoke_v1_run/`.
- **HR comparison:** `results/2026-10-12_D03_bvp_hr_vs_ecg_smoke_v1/`.
- **Reports:** `reports/D03_ppg_dalia_features_smoke.md`, `reports/D03_ppg_dalia_smoke_v1_tables.md`.

**Checks run and results:**
- **Invariant checks:** 45/45 passed:
  - one feature row per D02 window, in the same order;
  - 0 NaN in motion features;
  - dominant_freq and entropy in range;
  - no forbidden columns among the features;
  - no ECG HR in the feature tables;
  - physiology NaN only where `physiology_uncertain`;
  - HR within 30–220 bpm and SQI within [0, 1];
  - `hr_rel_baseline` NaN before 300 s.
- **Determinism:** all 3 feature tables and all 13 result CSVs are identical to the trial run.
- **pytest:** 53 passed, 1 skipped. This includes the end-to-end causality test and the strictly-past baseline test.
- **Wrist HR vs ECG (8 s/2 s, both subjects):**
  - overall MAE 11.18 bpm, bias −9.12 bpm, coverage 99.97%;
  - per activity MAE: sitting 2.70, working 4.32, driving 5.51, lunch 7.34, transient 11.47, walking 12.08, cycling 20.91, table soccer 25.44, stairs 32.82.
  - Per subject × activity results are in the tables §5.
- **SQI:** informative (Spearman −0.507 with |err|). MAE is 2.38 bpm at SQI ≥ 0.95 and 19.69 at 0.5–0.7.
- **SQI 0.9 threshold:** keeps 34.4% of 8 s windows (MAE 4.29). The report-only sensitivity was produced and not used to change anything.
- **physiology_uncertain:** 86.4% of 30 s windows for S03 and 59.9% for S06.
- **Label-edge table (report-only):** near activity edges, motion variability differs strongly from the activity core, beyond the 10 s margin. Relative to the ≥ 40 s core, 20–40 s from an edge: lunch 4.4×, driving 1.6×, sitting 1.3×, working 1.9×. This is written into the report's limitations; the 10 s rule and all training roles are unchanged.

**Decisions made (and why):** none new. All parameters were fixed before the run (see the D03 start entry).

**Problems / surprises:**
- The `physiology_uncertain` rate is high under the fixed 0.9 threshold.
- `hr_rel_baseline` is NaN in 34% of windows, mostly because there was no good-quality window in the previous 5 minutes.
- S06's vigorous-activity errors are 1.4–4.2× those of S03.
- The label-edge noise lasts up to 20–40 s.
- I corrected two figures in my report draft before committing (an S06/S03 ratio range and the bin sizes). Every number now matches the generated tables.

**Open questions for the user:** whether to run the full D03 (15 subjects, tag `v1`).

**Next step (waiting for user approval):** full D03 run. Not started.

## 2026-10-12 05:17 — D03 — Start: full run (15 subjects, tag v1)
**What I did:** Started the full D03 run (approved), with the same code and settings as the smoke test.
- The only code change is in the report script (`scripts/d03_report.py`), which now prints a per-activity table of mean ± std across subjects (MAE, bias, % within ±10 bpm) and the across-subject overall MAE. Feature and HR-comparison code is unchanged since the smoke test.
- An independent scratch re-run is used for the determinism check.

**Files created/changed:** `scripts/d03_report.py`, `PROJECT_LOG.md`.

**Checks run and results:** pytest passes before the run.

**Decisions made (and why):** none.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: the full D03 run, then stop.

## 2026-10-12 05:44 — D03 — Full run done: features + wrist-PPG vs ECG (15 subjects, v1)
**What I did:**
- Ran D03 on all 15 subjects in tmux `sao`, env `wearsafe`, on CPU (no GPU needed).
- A scratch trial run and the official run went in parallel, into separate outputs, with identical code. Logs: `logs/2026-10-12_D03_full.log`, `logs/2026-10-12_D03_full_trial.log`.
- Generated the tables with `scripts/d03_report.py`.

**Files created/changed:**
- **Features:** `data/processed/{motion,context,physiology}/ppg_dalia_features_v1.parquet`, plus `data/processed/ppg_dalia_features_v1_run/`.
- **HR comparison:** `results/2026-10-12_D03_bvp_hr_vs_ecg_v1/`.
- **Reports:** `reports/D03_ppg_dalia_features_full.md`, `reports/D03_ppg_dalia_v1_tables.md`.
- **Code:** `scripts/d03_report.py`, a heading text fix after the run (see Problems).

**Checks run and results:**
- **Invariant checks:** 318/318 passed.
- **Rows:** motion 129,474, context 51,777, physiology 8,612 (= the D02 v1 window counts).
- **Determinism:** 3/3 feature tables and 13/13 result CSVs are identical to the trial run.
- **pytest:** 53 passed, 1 skipped.
- **Wrist HR vs ECG (8 s/2 s):**
  - 64,697 reference windows, coverage 99.97%;
  - across subjects MAE 10.64 ± 4.83 bpm, bias −5.83 ± 6.80 bpm;
  - per activity (mean ± std across subjects): sitting 3.50 ± 2.09, working 4.83 ± 2.46, driving 6.55 ± 3.16, lunch 6.88 ± 2.50, transient 11.85 ± 6.22, walking 16.07 ± 10.69, table soccer 16.37 ± 11.29, cycling 21.91 ± 17.56, stairs 28.38 ± 14.72 bpm.
  - Per subject: best S07 at 5.77 bpm, worst S05 at 23.61.
- **SQI:** informative (Spearman −0.419). MAE by SQI bin is 15.61 (0.5–0.7) down to 2.15 bpm (≥ 0.95).
- **SQI 0.9:** keeps 26.4% of windows (MAE 3.96). The report-only sensitivity was produced and not used.
- **physiology_uncertain:** 59.3–99.8% of 30 s windows per subject.
- **hr_rel_baseline:** NaN in 50.35% of windows.
- **Label-edge table (report-only):** relative to the activity core, 10–20 s from an edge: lunch 8.2×, working 2.6×, driving 2.1×, sitting 1.5×; at 20–40 s: lunch 6.2×, driving 1.6×. Walking, stairs and table soccer are insensitive. The 10 s rule and roles are unchanged.

**Decisions made (and why):** none.
- Per user instruction, two "findings for later" were recorded in the report, with no changes now:
  1. a possible v2 SQI threshold chosen against ECG agreement on training subjects only;
  2. a 10 s vs 30 s label-edge margin experiment reported side by side.

**Problems / surprises:**
- Stairs stay poor even in windows not flagged uncertain (MAE 27.9 bpm, n = 28).
- Windows with ACC saturation have about twice the HR error.
- One heading in the generated tables file reads "both subjects pooled" (left over from the smoke test). The table pools all 15 subjects. The script text is fixed; the generated file is not edited, and the report notes it.
- My first report draft had wrong motion/context row totals. They were corrected against `run_info.json` and the D02 window tables before commit.

**Open questions for the user:** none blocking. Next milestone to be chosen by the user.

**Next step (waiting for user approval):** none started.

## 2026-10-12 05:54 — Findings for later (continued, user)
**What I did:** Recorded two more user findings. Items 1–2 are in `reports/D03_ppg_dalia_features_full.md` ("Findings for later"). Nothing else changed.

**Files created/changed:** `PROJECT_LOG.md` (this entry only).

**Checks run and results:** none (recording only).

**Decisions made (and why):** findings recorded as proposals; nothing decided.
3. **The SQI can be fooled by rhythmic motion.** Stair windows rated "certain" still have ~28 bpm error (D03: 27.9 bpm, n = 28), likely because step cadence is mistaken for pulse.
   - **Proposal for the fusion milestone**, to be decided before any fusion model or threshold exists: physiology is treated as uncertain when motion intensity is high, regardless of SQI (a fixed, motion-aware gate).
4. **hr_rel_baseline is missing in ~50% of windows** (D03: 50.35%), because 5-minute histories often lack a good-quality window.
   - **Proposal for a v2 feature version:** a longer or "last known good" baseline. Decided before modelling, not tuned on results.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** the D08 plan is approved; execution follows.

## 2026-10-12 05:55 — D08 — User decisions on the D08 plan (recorded before any D08 code runs)
**What I did:** Recorded the user's approval of the D08 plan, with one change and answers 1–12.

**Files created/changed:** `PROJECT_LOG.md`, `CLAUDE.md` (one bullet inserted under the clip-position rule; nothing removed), `config/evaluation_v1.yaml`, `config/label_maps.yaml`, `config/fallalld_v1.yaml` (new), `config/features_v2.yaml` (new).

**Checks run and results:** none (recording only).

**Decisions made (and why)** (user):
- **Milestone ID:** **D08 = "FallAllD wrist motion dataset"** (requested as D05; D05 stays "BITS-2 synchronized event dataset" per context doc §32).
- **CHANGE (decision 4):** positive windows = ONLY the window starting at 9 s, [9, 11).
  - **Reason (user):** it contains t* = 10.0 s with margin, while [10, 12) starts exactly at t* and would miss impacts slightly before 10 s (peak p5 = 9.44 s).
  - The window starting at 10 s becomes `fall_clip_context`, like the other non-positive fall-clip windows.
  - **Expected balance:** 523 positive windows; 523 × 18 = 9,414 fall-clip context windows; (1,992 − 70) × 19 = 36,518 ADL negative windows; 70 × 19 = 1,330 probe windows.
- **Answers:**
  1. D08 accepted.
  2. **Gravity check:** low-motion = non-overlapping 1 s segment (238 samples) of an ADL record (IDs 1–44) with std(|a|) < 0.01 g and max − min of |a| < 0.05 g. Statistic = the median over records of each record's median |a| over its low-motion segments. Pass = within [0.95, 1.05] g with ≥ 100 contributing ADL records; otherwise STOP.
  3. **Impact time:** protocol t* = 10.0 s, not the detected peak (avoids circularity).
  5. **fall_clip_context:** excluded from training, kept for analysis.
  6. **Position-only baseline, operational definition:**
     - **(a)** a position-matched subset: windows starting at 9 s from all clips; the position-only baseline must be at chance there, and every model is also reported on this subset;
     - **(b)** a features→position leakage test on cyclic-ADL clips (edge vs interior windows), which must be at chance;
     - **(c)** clip-level metrics: a fall clip is detected if any window fires; an ADL clip is a false alarm if any window fires.
     - Recorded in `config/evaluation_v1.yaml` and as a note under the clip-position rule in CLAUDE.md §2.3.
  7. **e4_clipped order:** clip each axis at 238 Hz to [−2.0, +1.984375] g → resample → re-clip → quantise to 1/64 g.
  8. **Resampling:** `scipy.signal.resample_poly(up=16, down=119, window=('kaiser', 5.0), padtype='line')`.
  9. **features_v2 APPROVED now** (before any model exists) = v1 (§14) + longest saturated run, number of saturated runs, axes saturated simultaneously, post-peak stillness, pre-peak low-g dip, all computed within the window.
     - Both feature versions are computed for both signal versions.
     - **Every later model must report results for both feature versions; never pick the better one silently.**
  10. **Smoke subjects:** FALLALLD_S01 + FALLALLD_S04.
  11. **Inner validation:** inner LOSO among the training subjects with falls (recorded in the split manifest and in `evaluation_v1.yaml`).
  12. **Report-only list** of fall clips whose detected peak lies outside the positive window [9, 11). The user decides any exclusion after seeing it, before any model is trained.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: pre-checks (STOP if gravity fails) → smoke build on S01 + S04 → commit → STOP.

## 2026-10-12 06:04 — D08 — Pre-checks done (gravity PASS); smoke build code ready
**What I did:**
- Ran the D08 pre-checks on all FallAllD wrist records in tmux `sao`, env `wearsafe`, on CPU. They were read-only; only report tables were written.
- Script: `scripts/d08_fallalld_prechecks.py`. Read-only follow-ups: `scripts/d08_neardup_followup.py`, `scripts/d08_overlap_search.py`, `scripts/d08_overlap_search_cross.py`.
- Logs: `logs/2026-10-12_D08_prechecks.log`, `_neardup_followup.log`, `_overlap_search.log`, `_overlap_search_cross.log`.
- Wrote the smoke-build code and tests.

**Files created/changed:**
- **Report:** `reports/D08_fallalld_prechecks_tables.md` (sections 1–4 from the pre-check script; 5–7 appended by the follow-ups).
- **Code:** `src/wearsafe/{safe_pickle,fallalld_io,motion_harmonise,fallalld_windows,splits}.py`, `src/wearsafe/features.py` (features_v2 functions), `src/wearsafe/schemas.py` (FALLALLD prefix, forbidden meta columns), `scripts/inspect/common.py` (now re-exports the moved `RestrictedUnpickler`).
- **Scripts:** `scripts/d08_fallalld_{build,features,splits}.py`, `scripts/d08_report.py`.
- **Tests:** `tests/test_fallalld_{harmonise,windows_labels,splits}.py`.
- **Config:** `config/fallalld_v1.yaml` gained `probe_ids` and `cyclic_adl_ids` (for the edge-artefact check), added before the smoke build.

**Checks run and results:**
- **Gravity check: PASS.**
  - Median of per-record low-motion |a| = 0.9904 g over 1,549 ADL records (14,725 low-motion segments); IQR 0.9858–0.9976 g.
  - All 13 subjects are within 1 ± 0.05 g (0.9845–1.0082).
  - 4096 counts/g is confirmed within the pre-set tolerance.
- **Peak time of wrist falls** (523):
  - unclipped 32 Hz: median 10.00 s, p5 9.19, p95 10.66; 92.5% in [9, 11);
  - native 238 Hz: median 10.00 s, p5 9.44, p95 10.75; 93.7% in [9, 11).
  - In some clips the 238 Hz peak sits at 10.0 s, but the 32 Hz maximum is elsewhere: the impact spike is attenuated by the anti-aliasing filter below other movement in the clip (e.g. jogging steps). Max |t32 − t238| is 9.2 s.
- **Decision-12 list:** 39 of 523 fall clips (7.46%) have their 32 Hz peak outside [9, 11). Report-only; the list is in tables §3.
- **Trial gaps:**
  - 72 groups, 112 missing trial numbers; 35 groups are missing only trial 1;
  - 4 groups have more trials than typical;
  - no gap record is involved in any flagged near-duplicate.
  - This looks like discarded trials, not mislabelling [inferred].
- **Near-duplicates and overlaps:**
  - 12 pairs had xcorr > 0.99. All are hand-activity clips that share 100% identical raw samples over 13.7–18.2 s at a time shift.
  - The exhaustive search found **1,570 within-subject pairs** sharing ≥ 1 s of identical raw samples (1,621 of 2,515 records). Mostly adjacent ADL clips cut from one continuous recording: start/during/stop clapping, waving, walking; sitting down/standing up/fail to stand up; lying down/turning/rising.
  - 10 pairs are fall–fall: the end of one fall clip overlaps the start of the next, in `fall_clip_context` windows only. **No fall–ADL overlap.**
  - 67 pairs involve the probe IDs 15/23.
  - **Cross-subject overlaps: 0**, so LOSO is unaffected.
  - Detection is guaranteed for identical runs of ≥ 2 s; runs of 1–2 s are found only if they cover an indexed block.
- **pytest:** 66 passed, 2 skipped.

**Decisions made (and why):** none.

**Problems / surprises:**
- The within-subject overlaps mean some ADL samples appear in several clips under different activity labels. Under LOSO this cannot leak between folds, but it double-counts windows in training and in evaluation.
- **Proposed for the user's decision** (not applied):
  - (a) keep everything (LOSO-safe);
  - (b) de-duplicate windows whose 32 Hz samples are identical to an earlier window of the same subject;
  - (c) count each overlap once in evaluation only.
- Also for the user: whether probe clips overlapping training ADLs need special handling. Under LOSO the probe's subject is held out, so this is within-subject only.

**Open questions for the user:** decision 12 (39 clips), and the overlap handling (a/b/c).

**Next step (waiting for user approval):** approved: the smoke build on S01 + S04, then stop.

## 2026-10-12 06:06 — D08 — Smoke run STOPPED: edge-artefact invariant failed (diagnosed; nothing changed)
**What I did:**
- Started the D08 smoke run (S01 + S04) in tmux `sao` (log `logs/2026-10-12_D08_smoke.log`).
- The scratch trial build passed all 15 build checks (344 records, 6,536 windows).
- The trial feature step then **failed the edge-artefact invariant**: on unclipped cyclic-ADL clips, the last window's median `acc_mag_mean` was 2.08% below the interior, against a limit of < 1%.
- Per CLAUDE.md §3 the run stopped. The official build, features and split manifest were **not** run, so nothing was written under `data/interim/fallalld/`, `data/processed/` or `splits/`. The trial outputs exist only in the scratchpad.
- Ran a read-only diagnostic (`scripts/d08_edge_diagnostic.py`, log `logs/2026-10-12_D08_edge_diagnostic.log`). It applies the same comparison to the native 238 Hz raw data (no filter) and to the 32 Hz output.

**Files created/changed:** `scripts/d08_edge_diagnostic.py`, `PROJECT_LOG.md`.

**Checks run and results:**
- **The deviation is in the raw recordings, not caused by resampling:**
  - smoke subjects: native 238 Hz last window −2.04% vs 32 Hz −2.08%;
  - all 13 wrist subjects (413 cyclic-ADL clips): native first −2.44% / last −2.59%, vs 32 Hz −2.39% / −2.58%.
  - Resampling changes the edge windows by ≤ ~0.15 percentage points.
- **Clip-centred structure in ADL clips too:**
  - the median window |a| profile over all cyclic-ADL clips (start 0..18 s, % vs interior) rises to **+4–5% at 8–10 s** and falls to −2.5% at both ends, at native rate as well;
  - per activity the edge deviation ranges from −3.2% (24 jogging slowly, 6 waving) to +3.4% (36 downstairs quickly, first window).
  - So FallAllD ADL clips also appear to be cut around a centre [inferred], not only the fall clips.

**Decisions made (and why):** none. The 1% threshold and the check were NOT changed after failing.

**Problems / surprises:** as written, the check cannot separate a resampling artefact from real structure in the clips.

**Open questions for the user:**
1. **Redefine the edge-artefact invariant?** Proposal: compare each edge window of the resampled signal with the same window of the native 238 Hz signal (a resampling-only artefact; limit < 1%). The real clip-centre structure is reported separately.
2. **Position-leakage test (b) will likely NOT be at chance**, because the clip-centre structure is in the data itself (ADL clips are more intense at the centre). The position-matched subset (a) and the clip-level metrics (c) are unaffected. How should (b) be interpreted or redefined?
3. Still pending from the pre-checks: decision 12 (39 clips), and the overlap handling (a/b/c).

**Next step (waiting for user approval):** STOPPED. No D08 data outputs written; awaiting the user's decision on the check.

## 2026-10-12 06:11 — D08 — User decisions on the smoke stop (recorded before the re-run)
**What I did:** Recorded the user's four decisions after the D08 smoke stop.

**Files created/changed:** `PROJECT_LOG.md`, `CLAUDE.md` (one note appended under the clip-position rule; nothing removed), `config/evaluation_v1.yaml`, `config/fallalld_v1.yaml`.

**Checks run and results:** none (recording only).

**Decisions made (and why)** (user):
1. **Edge-artefact check redefined.**
   - Compare each edge window (first and last 2 s) of the converted 32 Hz signal with the same window of the raw 238 Hz signal. The limit is unchanged: < 1% difference.
   - The clip-centre intensity pattern (ADL clips are +4–5% more intense at 8–11 s than at the ends, also at native rate) is reported separately as a dataset property, in the report and its limitations section.
   - **My operationalisation (overrulable):** for each version, the median over cyclic-ADL clips of |relative difference| in window `acc_mag_mean` (converted vs native), computed separately for the first and last windows. Both must be < 1%. The native reference for `e4_clipped` is the clipped 238 Hz signal (no quantisation). The p95 and the same statistic for interior windows are reported for context.
2. **Position test (b) becomes COMPARATIVE.**
   - The same position classifier (edge vs interior windows, cyclic ADLs) is trained on (i) the converted features and (ii) the same features computed on the raw 238 Hz signal.
   - **Pass if AUC(converted) − AUC(raw) ≤ 0.02**, and both AUCs are reported. Tests (a) and (c) are unchanged.
   - Recorded in `config/evaluation_v1.yaml` and as a note under the clip-position rule in CLAUDE.md §2.3. It runs with the other shortcut checks at the first modelling milestone.
3. **The 39 off-window clips:**
   - **14 kept, with normal labels.** Their 238 Hz peak is ≈ 10.0 s; only the 32 Hz conversion moved the maximum. Finding (limitations): at watch-like sampling rates part of a brief impact can be lost.
   - **25 truly off-centre clips:** role `label_uncertain_fall` (238 Hz peak also outside [9, 11)).
     - Excluded from training and from window-level metrics.
     - INCLUDED as fall clips in clip-level metrics (c).
     - The list and its evidence are stored in `metadata/fallalld_label_uncertain_v1.csv`.
   - **My operationalisation:** label_uncertain = fall clip whose native 238 Hz peak lies outside [9, 11). The kept 14 = 32 Hz peak outside but 238 Hz peak inside.
4. **Overlapping clips: keep all.**
   - Every record gets an `overlap_group_id`: records connected by any shared identical raw samples (≥ 1 s, same search as the pre-checks) form one group.
   - The ID is the group's lowest `record_id`, so it is deterministic.
   - Every evaluation reports the main result **plus a deduplicated check counting one clip per overlap group** (the lowest `record_id` in the group).
   - **Overlaps are within-subject only** (the cross-subject search found 0), so LOSO is leakage-safe.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: re-run the smoke build on S01 + S04 with the redefined checks, commit, STOP.

## 2026-10-12 06:12 — D08 — Correction: label-uncertain rule (caught by a cross-check, before any output)
**What I did:** Corrected my operationalisation of the label-uncertain rule.
- My first rule ("native 238 Hz peak outside [9, 11)") gave **33** clips. The metadata script's cross-check (it expects the 25 the user reviewed) stopped the run, and nothing was written.
- The 8 extra clips have a 238 Hz peak just outside [9, 11) but a 32 Hz peak inside, so they were not among the 39 clips the user decided on.
- **Corrected rule:** label_uncertain_fall = peak outside [9, 11) at BOTH 32 Hz and 238 Hz (= the 25).
- The 8 extra clips keep normal labels and are listed in `metadata/fallalld_label_uncertain_v1.csv` with status `info_238hz_outside_32hz_inside`, for the user's information.

**Files created/changed:** `config/fallalld_v1.yaml` (rule text + correction note), `scripts/d08_fallalld_metadata.py`, `PROJECT_LOG.md`.

**Checks run and results:** the cross-check expects 25 / 14 clips.

**Decisions made (and why):** none new.
- The decision log entry above (D08 user decisions on the smoke stop, item 3, "my operationalisation") is superseded by this rule.

**Problems / surprises:** the 8 extra clips.

**Open questions for the user:** whether the 8 clips need any handling (currently normal labels).

**Next step (waiting for user approval):** re-run the metadata script, then the smoke build.

## 2026-10-12 06:17 — D08 — Smoke re-run done (S01 + S04): all checks pass
**What I did:**
- Generated `metadata/fallalld_label_uncertain_v1.csv` and `metadata/fallalld_overlap_groups_v1.csv` (+ pairs) for all wrist records (`scripts/d08_fallalld_metadata.py`).
- Re-ran the smoke build with the redefined checks in tmux `sao`, env `wearsafe`, on CPU: a scratch trial, then the official run, with no code changes in between.
- Built the split manifest.
- Logs: `logs/2026-10-12_D08_metadata_rerun.log`, `logs/2026-10-12_D08_smoke_rerun.log`.

**Files created/changed:**
- **Data:** `data/interim/fallalld/{normalized_signals,windows}_smoke_v1/`, `data/processed/motion/fallalld_*_features-{v1,v2}_smoke_v1.parquet`, `data/processed/fallalld_features_smoke_v1_run/`.
- **Metadata and splits:** `metadata/fallalld_records_smoke_v1.csv`, `splits/fallalld_v1.json`.
- **Reports:** `reports/D08_fallalld_smoke.md`, `reports/D08_fallalld_smoke_v1_tables.md`, `reports/figures/D08_smoke_v1/`.
- **Code:** `src/wearsafe/overlap.py` (new), `fallalld_windows.py`, `schemas.py`; `scripts/d08_fallalld_{metadata,build,features,splits}.py`, `d08_report.py`; `tests/test_overlap.py` (new), `tests/test_fallalld_windows_labels.py`.

**Checks run and results:**
- **Metadata:** 25 label_uncertain_fall clips + 14 kept + 8 info-only clips. 1,570 overlap pairs (= the pre-checks), 1,343 groups; no group spans two subjects.
- **Smoke checks:** 36/36 passed (19 build + 17 features).
- **Edge check (redefined):** converted vs native 238 Hz, median |rel diff| first/last window = 0.065% / 0.057% (unclipped) and 0.187% / 0.148% (e4_clipped); limit 1%.
- **Determinism:** 10/10 output files identical to the scratch trial.
- **Splits:** 13 folds, 9 subjects with falls and 4 without; no subject in two splits.
- **pytest:** 70 passed, 2 skipped.
- **Class balance:** S01 has 73 positive : 2,983 ADL windows. S04 has 1,976 ADL windows and no positives.
- **e4_clipped:** 72.6% of fall-positive windows contain saturation vs 7.8% of ADL windows. The median fall-window peak falls from 40.9 (unclipped) to 24.7 m/s².
- **Clip-centre profile** (cyclic ADLs, smoke subjects): +2.9 to +4.1% at 7–10 s, about −2% near the edges. Reported as a dataset property.

**Decisions made (and why):** none new.

**Problems / surprises:** the 8 info-only clips (238 Hz peak outside, 32 Hz inside) keep normal labels pending the user.

**Open questions for the user:** handling of the 8 info-only clips; approval of the full D08 build.

**Next step (waiting for user approval):** full D08 build on all 13 wrist subjects (tag `v1`). Not started.

## 2026-10-12 06:21 — D08 — User decisions: 8 info-only clips; full build approved
**What I did:**
- Recorded the user's decision on the 8 info-only clips.
- Added a per-subject saturation table to `scripts/d08_report.py` before the full run (report only; no change to data code).

**Files created/changed:** `PROJECT_LOG.md`, `scripts/d08_report.py`.

**Checks run and results:** none (recording only).

**Decisions made (and why):**
1. **The 8 "for information" clips keep normal labels** (user). These are status `info_238hz_outside_32hz_inside` in `metadata/fallalld_label_uncertain_v1.csv`. Their 32 Hz peak (what the model sees) is inside [9, 11).
2. **Full D08 build approved:** all 13 wrist subjects, tag `v1`; same code and checks; both versions (unclipped, e4_clipped); both feature sets (v1, v2). It includes:
   - the determinism re-run;
   - per-subject class-balance, saturation and overlap-group tables;
   - the final checks of `splits/fallalld_v1.json`.

**Problems / surprises:** none.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: run the full build, then stop.

## 2026-10-12 06:25 — D08 — Full build done: FallAllD wrist, 13 subjects (v1)
**What I did:**
- Ran the full D08 build in tmux `sao`, env `wearsafe`, on CPU.
- A scratch trial and the official run went in parallel with identical code; the official run then ran `scripts/d08_check_splits.py`.
- Generated the tables with `scripts/d08_report.py --tag v1`.
- Logs: `logs/2026-10-12_D08_full.log`, `logs/2026-10-12_D08_full_trial.log`.

**Files created/changed:**
- **Data:** `data/interim/fallalld/{normalized_signals,windows}_v1/`, `data/processed/motion/fallalld_*_features-{v1,v2}_v1.parquet`, `data/processed/fallalld_features_v1_run/`.
- **Metadata:** `metadata/fallalld_records_v1.csv`.
- **Reports:** `reports/D08_fallalld_full.md`, `reports/D08_fallalld_v1_tables.md`, `reports/figures/D08_v1/`.
- **Code:** `scripts/d08_report.py`, a heading text fix after the run (see Problems).

**Checks run and results:**
- **Build and features:** 69/69 checks passed.
- **Splits:** 8/8 final checks of `splits/fallalld_v1.json` passed:
  - no subject in two splits, each tested once;
  - subjects, per-subject window counts and overlap-group counts equal the build and metadata;
  - inner validation = training subjects with falls;
  - no overlap group spans subjects;
  - the source SHA-256 matches.
- **Determinism:** 32/32 files identical to the trial.
- **Windows:** 2,515 records → 47,785 windows per version.
  - fall_positive 498, fall_clip_context 8,964, label_uncertain_fall 475, adl 36,518, hard_negative_probe 1,330;
  - positive:negative ≈ 1:73 overall; 1:35 (S15) to 1:99 (S13) per subject with falls.
- **Overlap groups:** 1,343 (59–151 per subject).
- **e4_clipped:**
  - 74.1% of fall_positive windows and 9.4% of ADL windows contain saturation;
  - 78.4% of fall and 29.4% of ADL records touch the rail;
  - the median fall-window peak is 41.9 (unclipped) vs 25.1 m/s².
- **Edge check vs native 238 Hz:** ≤ 0.15% median.
- **features_v2 NaN** (by rule): post_peak_stillness 12.6–14.5%, pre_peak_min_mag 5.2–9.0%.
- **pytest:** 71 passed, 1 skipped.

**Decisions made (and why):** none new.

**Problems / surprises:**
- In the generated tables file, the §7 heading still says "Smoke fall clips"; the content is the full run. The script text is now fixed; the generated file is not edited.

**Open questions for the user:** next milestone (e.g. first motion models with the planned shortcut baselines).

**Next step (waiting for user approval):** none started.

## 2026-10-12 06:35 — M01-demo — Demo sprint (tag demo_v0, PRELIMINARY): design fixed before any model runs
**What I did:** Started the user's demo sprint:
- Part A: M01-lite motion models on FallAllD;
- Part B: a context model on PPG-DaLiA;
- Part C: the device-discrimination check.

All outputs are tagged `demo_v0`; all results are PRELIMINARY. Runs on CPU (`CUDA_VISIBLE_DEVICES=""`); GPUs are not used.

**Files created/changed:** `PROJECT_LOG.md` (this entry).

**Checks run and results:** none yet.

**Decisions made (and why)** (mine, fixed now, before any result; overrulable):
- **Part A grid:** {unclipped, e4_clipped} × {features_v1, features_v2} × {logistic regression, random forest}. All reported.
- **Training data:** windows with `eval_role == train_candidate` only:
  - positives = `fall_positive` (the 9 s window of fall clips);
  - negatives = `adl` windows.
  - Never used for training: `fall_clip_context`, `label_uncertain_fall`, probes.
- **Models, with fixed hyperparameters (no tuning):**
  - LR: median imputer → StandardScaler → `LogisticRegression(class_weight="balanced", max_iter=5000)`;
  - RF: median imputer → `RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample", random_state=0)`.
  - Every imputer, scaler and model is fit on training folds only. Seed 0.
- **Threshold:**
  - for each outer fold, from inner LOSO over that fold's training subjects with falls (`inner_validation_subjects` in `splits/fallalld_v1.json`);
  - the pooled inner out-of-fold scores on inner fall windows give the threshold = the **highest score threshold with recall ≥ 0.90** on fall windows;
  - fixed before any outer-test prediction is looked at.
  - **Deploy threshold** = the median of the 13 outer folds' inner-validation thresholds.
- **Metrics:**
  - **Window level** (test subject's `train_candidate` windows; pooled out-of-fold): PR-AUC (primary), ROC-AUC; precision/recall/F1 at each fold's threshold, pooled.
  - **Per subject:** fall recall on fall subjects; ADL-window false-positive rate on all subjects; mean ± std.
  - **Clip level (c):** a fall clip is detected if any of its 19 windows ≥ threshold (falls incl. context windows; `label_uncertain_fall` clips reported separately); an ADL clip (non-probe) is a false alarm if any window ≥ threshold.
  - **Probes:** trigger rate per clip and per window.
  - **Dedup check:** the clip-level metrics recomputed on one clip per `overlap_group_id` (`dedup_representative`).
  - **Position-matched subset (a):** windows starting at 9 s from all ADL and fall clips (PR-AUC of the models and of position-only).
- **Shortcut baselines** (same folds, same LR pipeline):
  - position-only (`window_start` one-hot; full set, position-matched subset, clip level);
  - peak-only (`acc_mag_max`);
  - saturation-only (e4_clipped: `acc_saturated_frac` for v1, plus `sat_longest_run_s` and `sat_n_runs` for v2; not applicable to unclipped).
- **STOP rule** (user; operationalised by me): STOP and report if any model's pooled PR-AUC > 0.98, or if any shortcut baseline's PR-AUC is within 0.05 of the best model of the same configuration ("close").
  - The position-only baseline on the full window set is excluded from "close", because it beats chance by construction (CLAUDE.md §2.3 note). Its position-matched and clip-level values are reported.
  - If triggered: Part A results are written and flagged, no deploy model is presented as usable, and I STOP before Part B.
- **Part B:**
  - `splits/ppg_dalia_v1.json` (LOSO over 15 subjects, automatic check);
  - context features = D03 `context_5s` §14 motion features;
  - trained on `train_candidate` windows (4 classes from `label_maps.yaml`), same LR/RF pipelines, fixed hyperparameters, class weights balanced;
  - out-of-fold predictions for EVERY 5 s window, from the fold model that did not see that subject.
- **Part C:**
  - FallAllD e4_clipped ADL windows (features_v1, 2 s, 32 Hz, computed with `wearsafe.features.motion_features`) vs PPG-DaLiA `motion_2s` windows (the same function, 2 s, 32 Hz, E4 1/64 g data);
  - the classifiers are the LR pipeline (simple) and RF, with subject-grouped 5-fold CV (GroupKFold);
  - AUC reported, plus single-feature AUCs. Report only.

**Problems / surprises:** none yet.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: run Part A → (B, C) → report → commit → STOP.

## 2026-10-12 06:39 — M01-demo — Motion run 1 aborted (CPU oversubscription); restarted as _run2
**What I did:**
- Stopped my own 4 motion-grid processes after about 2 minutes. Each used ~115 threads (BLAS threads on top of RF workers): load average 133 on 40 cores, which also slowed other users' jobs.
- No other user's process and no tmux session was touched. My first stop command also ended its own shell (the process pattern matched that shell's command line); this was harmless, and the steps were redone.
- No results had been produced (only empty or partial `models/` folders). The partial folder `results/2026-10-12_M01_demo_v0/motion/` is kept (not deleted) and is NOT used.
- Restarted with `OMP_NUM_THREADS = OPENBLAS_NUM_THREADS = MKL_NUM_THREADS = 2` and RF `n_jobs=8` per process, writing to `results/2026-10-12_M01_demo_v0_run2/`. The scripts gained a `--run` suffix argument; the design is unchanged.

**Files created/changed:** `scripts/m01_demo_motion.py`, `scripts/m01_demo_eval.py`, `scripts/m01_demo_context.py` (`--run` argument only), `PROJECT_LOG.md`.

**Checks run and results:** none (restart only).

**Decisions made (and why):** thread limits, to stay within this machine's fair share.

**Problems / surprises:** the CPU oversubscription and the self-ending stop command, both described above.

**Open questions for the user:** none.

**Next step (waiting for user approval):** approved: continue the sprint.

## 2026-10-12 06:49 — M01-demo — Demo sprint results (demo_v0, PRELIMINARY)
**What I did:**
- Ran Parts A, B and C in tmux `sao`, env `wearsafe`, on CPU (`CUDA_VISIBLE_DEVICES=""`, BLAS threads 2, RF n_jobs 8–16). Outputs are in `results/2026-10-12_M01_demo_v0_run2/`.
- Logs: `logs/2026-10-12_M01demo_run2_*.log`.
- Wrote `reports/M01_demo_v0.md` and its generated tables (`reports/M01_demo_v0_{motion,context,device}_tables.md`).

**Files created/changed:** `splits/ppg_dalia_v1.json`, the reports above, the `results/...` folder, `scripts/m01_demo_{motion,eval,context,device_check}.py`, `PROJECT_LOG.md`.

**Checks run and results:**
- **STOP check:** not triggered (`results/.../motion/stop_check.json`).
  - Max pooled model PR-AUC is 0.826.
  - Shortcuts: peak-only 0.273 / 0.131; saturation-only 0.051 / 0.114; position-only on the position-matched subset 0.176 (chance 0.206); position-only at clip level 100% / 100%.
- **Motion, pooled out-of-fold PR-AUC:**

  | Config | LR | RF |
  |---|---|---|
  | unclipped v1 | 0.679 | 0.820 |
  | unclipped v2 | 0.682 | 0.826 |
  | e4_clipped v1 | 0.649 | 0.775 |
  | e4_clipped v2 | 0.655 | 0.767 |

- **Motion, RF at the inner-validation threshold:**
  - recall 0.90–0.91; precision 0.51–0.60;
  - clip fall detection 92.6–94.0%;
  - clip false alarm on ADL clips 11.0–14.2% (dedup 6.7–8.4%);
  - probe clips trigger 28.6%; label-uncertain clips detected 72–84%.
  - Per subject (e4_clipped v2, RF): PR-AUC 0.862 ± 0.095; ADL-clip false alarm 14.6 ± 6.4%.
- **Context (PPG-DaLiA, LOSO):**
  - RF macro-F1 0.717 (per subject 0.702 ± 0.060); LR 0.655;
  - per-class RF F1: stationary 0.592, low_activity 0.823, locomotion 0.716, vigorous_activity 0.739;
  - out-of-fold predictions for all 51,777 windows saved.
- **Device check (report only):** FallAllD e4_clipped ADL vs PPG-DaLiA 2 s windows, subject-grouped 5-fold: AUC 0.721 (LR), 0.843 (RF). The largest single-feature differences are mean |a| and jerk.
- **pytest:** 71 passed, 1 skipped.

**Decisions made (and why):** none beyond the design entry.
- Deploy models (8) were saved with threshold = the median inner-validation threshold.

**Problems / surprises:**
- False alarms are the weak point: 11–14% of 20 s ADL clips trigger at least once at the 90% recall operating point.
- The devices are distinguishable (AUC 0.72–0.84), so FallAllD-trained motion models face a device gap on PPG-DaLiA.
- Some single subjects have PR-AUC ≥ 0.98 (S01). The STOP rule was defined on the pooled PR-AUC.
- Position test (b) (comparative) has not been run yet.

**Open questions for the user:** next prompt ("Prompt 2"), which uses the context out-of-fold predictions.

**Next step (waiting for user approval):** STOP.
