# D00b — BITS-2 forensics and exclusion list

Date: 2026-10-12. Look-only on `data/raw/` (one new raw folder was added on request, see §2).

**Sources and tags.**
- Every number in this report comes from `reports/D00b_bits2_forensics_tables.md`, which `scripts/d00b_bits2_forensics.py` regenerates deterministically.
- Paper = Nandi et al., *Data in Brief* 52 (2024) 109812, `docs/papers/BITS2_DataInBrief_2024.pdf`.
- Tags: **[paper]** stated in the paper · **[files]** verified in the files · **[inferred]** my interpretation · **[unknown]** stated nowhere.
- Decision numbers refer to "User decisions D00b" in `PROJECT_LOG.md`.

---

## Plain-language summary

1. **The paper's activity list matches the files.** It names all 16 daily activities and 8 fall types, and file `adlK`/`fallK` = row K of its Table 1 **[inferred, website map]**. For 15 of the 24 activities, the recording length matches what the paper says. 9 do not; they are flagged, not removed.
2. **The "5 repetitions" are not in the published files.** Each file holds about **one** recording. For the 2-minute activities, heart rate covers about 2 minutes, not 10. So the public data has about 984 recordings, not 4,920.
3. **The motion sampling rate cannot be trusted.** The paper says 20 Hz. The files contradict each other: in the files we can measure best, some run at about 50 rows per second, others at 5–15, and a few at about 100. Under the rules fixed in advance, the verdict is **"inconsistent"**, so **no jerk or frequency features for BITS-2 v1** (decision 6).
4. **Heart rate really is 1 per second.** The same method that fails for motion recovers exactly 1.00 Hz for heart rate in 142 files. The method is sound; the motion data is irregular.
5. **The "without heart rate" website files are the same files.** All 984 are byte-identical to the merged files and still contain heart rate. No cleaner copy exists online.
6. **The paper mislabels its own accelerometers.** It calls `acg` the gravity-free one. The data shows `acg` *includes* gravity (9.87 m/s² when lying still) and `acc` is gravity-free (0.14). We follow the data, so `acg` is our canonical accelerometer (decision 8).
7. **The BITS-2 watch measures up to ±8 g; the E4 watch saturates at ±2 g.** 288 of 328 falls exceed 2 g, so an E4-type watch would clip most falls.
8. **Exclusions:** 5 files are removed entirely:
   - a duplicate pair (user28 fall4/fall8);
   - a pair sharing an identical heart-rate series (user29 adl13/adl14, *newly found*);
   - one file containing two recordings (user7 fall3).

   One magnetometer block shared across two people is dropped from both files.
9. **Usable for analysis:**
   - **979 files** are usable for motion.
   - Only **437** have good enough heart rate for heart-rate analysis (decision 4). The other 542 are "motion only".
   - Heart rate is worst in the short sit/stand activities (adl10, adl11: about 42% invalid rows).

---

## 1. Paper facts

| Topic | What the paper says | Status vs files |
|---|---|---|
| Subjects | 41 volunteers; Table 2 gives gender, height, weight, age (20–47), base HR, health condition **[paper]** | 41 user folders **[files]**; Table 2 extracted to `metadata/bits2_subjects.csv` (decision 10) |
| Activities | 16 ADLs + 8 falls, "every activity was repeated for 5 trials", 4,920 instances **[paper]** | One file per subject × activity; ≈1 trial per file (§4) **[files]** |
| Device | Custom wrist-worn device on the **left wrist**; Qualcomm Snapdragon 820c; MPU6500 (acc, linear acc, gyro); GY-273 magnetometer (HMC5883L); MAX30102 HR/SpO2 sensor; I2C **[paper]** | — |
| Rates | Motion **20 Hz**, HR **1 Hz** **[paper]** | HR 1 Hz ✔ **[files]**; motion inconsistent (§3) |
| Ranges / units | **Not stated [unknown]** | Accelerometer full scale 78.45 m/s² = 8.0 g; gyro max 35.3 rad/s (≈ ±2000 °/s) **[inferred from files]** |
| Timestamp unit | **Not stated [unknown]** | ns **[inferred]**: HR steps of 1e9 = 1 s |
| CSV columns | IMU: t, x, y, z, "number of axis", sensor tag. HR: t, bpm, "a single value", `hrt` **[paper]** | Matches; the "single value" is −1/0/3 in the files, meaning undocumented **[unknown]** |
| Stream names | `acc` = 3-axis accelerometer; `acg` = "3 axis **linear** accelerometer" **[paper text]** | **Contradicted**: `acg` includes gravity, `acc` does not (§7). The paper's own Fig. 3 shows `acg` ≈ −9.2 on one axis |
| Two files per activity | "one had data from heart-rate sensor and the another which did not" **[paper]** | The website's "without HR" files are byte-identical to the merged ones (984/984) **[files]** |
| Protocol | Base HR recorded before each activity, subject at base HR at start; falls in a "well-padded anechoic chamber" **[paper]** | HR often starts before the IMU data: 93 files have ≥10 HR rows before the first IMU timestamp **[files]** |
| "No contact" HR | **Not mentioned [unknown]** | Status −1 in 5,246 rows (§5) |
| Timestamp rounding | Fig. 3 shows `2920000000000.00` **[paper]** | The rounding was already present in the authors' own spreadsheet **[inferred]** |

### Paper Table 1, with the duration cross-check (decision 5)

"HR rows" ≈ seconds of heart rate (1 Hz). The index agrees if HR rows ÷ stated duration is between 0.6 and 1.6 (for 1 or 5 trials).

| File | Activity [paper] | Stated per trial | Median HR rows | Ratio (1 trial) | Agrees |
|---|---|---|---|---|---|
| adl1 | Walking slowly | 120 s | 122 | 1.02 | ✔ |
| adl2 | Walking quickly | 120 s | 132 | 1.10 | ✔ |
| adl3 | Jogging | 120 s | 127 | 1.06 | ✔ |
| adl4 | Jumping | 30 s | 32 | 1.07 | ✔ |
| adl5 | Climbing up slowly | 120 s | 127 | 1.06 | ✔ |
| adl6 | Climbing down slowly | 120 s | 122 | 1.02 | ✔ |
| adl7 | Climbing up normally | 120 s | 30 | 0.25 | ✘ flagged |
| adl8 | Climbing down normally | 120 s | 40 | 0.33 | ✘ flagged |
| adl9 | Slowly sitting on chair | 30 s | 18 | 0.60 | ✔ (edge) |
| adl10 | Rapidly sitting on chair | 30 s | 10 | 0.33 | ✘ flagged |
| adl11 | Nearly sitting on chair and getting up | 30 s | 11 | 0.37 | ✘ flagged |
| adl12 | Swinging hands | 120 s | 122 | 1.02 | ✔ |
| adl13 | Lying on bed | 120 s | 122 | 1.02 | ✔ |
| adl14 | Lying on back and getting up slowly | 30 s | 17 | 0.57 | ✘ flagged |
| adl15 | Lying on back and getting up normally | 30 s | 10 | 0.33 | ✘ flagged |
| adl16 | Transition from sideways to one's back while lying | 30 s | 11 | 0.37 | ✘ flagged |
| fall1 | Forward fall landing on knee | 40 s | 14 | 0.35 | ✘ flagged |
| fall2 | Right fall | 40 s | 32 | 0.80 | ✔ |
| fall3 | Left fall | 40 s | 32 | 0.80 | ✔ |
| fall4 | Forward fall | 40 s | 29 | 0.72 | ✔ |
| fall5 | Seated on bed and falling on ground | 40 s | 21 | 0.53 | ✘ flagged |
| fall6 | Forward fall, body weight on hand | 40 s | 26 | 0.65 | ✔ |
| fall7 | Backward fall from seated position | 40 s | 25 | 0.62 | ✔ |
| fall8 | Grabbing while falling | 40 s | 25 | 0.62 | ✔ |

**15/24 agree, so the index mapping is accepted (decision 5).** The 9 disagreeing indices (369 files) carry `index_duration_flag=True` and rule R6 (keep, flagged).

Caveat: HR rows understate duration whenever the HR sensor drops out. The short activities, which have the most invalid HR (§5), are exactly the ones that disagree. adl7/adl8 are different: they are 2-minute activities with only ~30–40 s of HR, whereas their "slowly" counterparts adl5/adl6 have ~2 min. That is unexplained.

---

## 2. Copies of the data

- **Zenodo copy** (`data/raw/bits2/`): 984 CSVs, the primary copy.
- **Website full copy** (`data/raw/bits2_website/`): 984/984 byte-identical to Zenodo. Made read-only (decision 12).
- **Website "without heart rate"** (`data/raw/bits2_website_nohr/`, new, decision 11):
  - Fetched from `https://shamanx86.github.io/fall_detection_data/Dataset_no_heart/{adl,fall}/userN/userN_{adl,fall}K.csv` with `scripts/download_bits2_nohr.py`.
  - All 984 were downloaded and are **byte-identical to the merged files**, including their `hrt` rows. So they offer no independent timestamps or values.
  - The 4 alternative names the website's JavaScript would build for user31 (`user31_fallN.csv`) return HTTP 404; the files only exist as `user31_.fallN.csv`.
  - The download log is `metadata/bits2_nohr_download.csv`. The folder is read-only and is in checksum manifest v2.
- **Checksum manifest v2** (`metadata/raw_checksums_v2.csv`, 3,110 files): all 2,126 v1 files are unchanged. The 984 new entries are all under `bits2_website_nohr/`. v1 is kept, and the guard test now uses v2.

---

## 3. Sampling rate (verdict criteria fixed before running)

Most timestamps carry only 3 significant digits:
- The rounding step of the `acg` timestamps is 1 s in 11 files, 10 s in 162, 100 s in 344 and 1000 s in 465.
- 981 of 984 files have a median of 3 significant digits.

**Estimator A** counts rows inside one full rounding step. **Estimator B** = `acg` rows ÷ HR rows.

| | Value |
|---|---|
| A (acg): files with an estimate | 87 |
| A (acg): median | **25.8 Hz** |
| A (acg): p25–p75 | 3.1–50.0 Hz |
| A (acg): p5–p95 | 0.15–99.7 Hz |
| A (acg): spread (IQR / median) | **1.82** (needs < 0.15) |
| B (acg/HR): median, p25–p75 | 20.2 Hz, 7.0–51.2 Hz (984 files) |
| A vs B: median relative difference | **0.85** (needs < 0.15); only 12.6% of files within 15% |
| A on heart rate (check of the method) | **1.00 Hz**, IQR/median 0.000, 142 files |

Per-file estimator A, by timestamp resolution. The 1-s rows are the most trustworthy.

| Rounding step | Files | <1 Hz | 1–5 | 5–15 | 15–25 | 25–45 | 45–55 | 55–90 | 90–110 |
|---|---|---|---|---|---|---|---|---|---|
| 1 s | 11 | 0 | 0 | 4 | 0 | 0 | **7** | 0 | 0 |
| 10 s | 57 | 5 | 5 | 5 | 5 | 14 | 10 | 5 | 8 |
| 100 s | 19 | 5 | 11 | 2 | 0 | 1 | 0 | 0 | 0 |

**Per activity:** no activity is consistent. Spread ranges from 0.24 (adl4, n=3) to 31 (adl12); 10 activities have fewer than 3 estimates.

**Per subject:** only 10 of 41 subjects have ≥3 estimates, and 1 of those 10 is consistent.

**What the data shows [files]:**
- In well-resolved files, IMU rows cluster at about **50 Hz** (7 of 11 files at 1-s resolution), with others at 5–15 Hz and some around 100 Hz.
- The IMU data often covers only part of the HR period. In `user29_adl6` (manifest), 109 of 133 HR rows come *before* the first `acg` timestamp and 24 during it, while estimator A gives 49.9 Hz. So the 819 `acg` rows cover roughly the last half-minute of a ~2-minute HR record.
- The likely cause is bursty or buffered logging rather than a steady 20 Hz **[inferred]**.
- Timestamps go backwards in 32–117 files per stream (D00a).

### Verdict
- (a) Consistency: **not consistent** (spread 1.82; A–B difference 0.85).
- (b) Match to paper: median 25.8 Hz is not within 20 Hz ± 10%.
- **Final verdict: "inconsistent".** Under decision 6: **no jerk or frequency features for BITS-2 v1, and no row-index proxy rate.**

### What this means for abrupt-event (fall) detection
- **Samples per 2 s motion window:** unknown. The rates suggested by the data give anything from about 10 samples (5 Hz) through 40 (the paper's 20 Hz) to 100 (50 Hz) or 200 (100 Hz). We cannot cut fixed-duration windows on BITS-2 without trusting a rate.
- **Impact peaks:**
  - The half-maximum width of the largest `acg` peak in each fall file is a median of **3 rows** (p10 = 1, p90 = 15).
  - 52 fall files have a single-row peak.
  - At 20 Hz, 3 rows ≈ 150 ms; at 50 Hz ≈ 60 ms. We can't say which **[unknown]**.
- **What still works:** peaks are captured *as samples*. 288/328 fall files exceed 2 g. Rate-free features (peak magnitude, magnitude distribution, counts above thresholds) remain possible.
- **What doesn't:** anything that divides by time (jerk, dominant frequency, spectral energy, durations in seconds) would be unreliable.
- **Cross-dataset:** E4 data (PPG-DaLiA/WESAD) is a known 32 Hz but clipped at ±2 g. BITS-2 has the range but no reliable clock. A motion model trained on one will not transfer simply to the other.

---

## 4. Repetitions

The paper says 5 trials per activity. The files show **≈1 trial per file**:
- **By duration:** per file, 430 look like ≈1 trial, 25 like ≈5 trials, and 529 like neither (mostly shorter than one trial).
- **By segments:** 860 files have no timestamp resets or gaps (>1 s) in any stream. 116 have breaks that differ between streams. 8 have the same 2 segments in every stream, but the piece durations don't fit a trial, and the low-motion check is impossible with an untrustworthy rate.
- **Splits proposed: none.** No file has an unambiguous boundary. 123 files with internal breaks are kept and flagged (R4b).
- Under decision 7: **the published data contains about 984 recordings. The figure 4,920 must not be used.**

---

## 5. Heart-rate validity (decisions 3 and 4)

HR is invalid if status is −1, or bpm = 0, or bpm is outside 30–220. Status 0 is kept but flagged. Nothing is imputed.

| | Rows |
|---|---|
| HR rows total (incl. 1 malformed) | 51,904 |
| Valid | 46,655 |
| Invalid | 5,249 (**10.1%**) |
| … status −1 | 5,246 |
| … bpm = 0 | 138 (overlapping with −1) |
| … outside 30–220 (non-zero) | 1 |
| Status 0 (kept, `hr_unreliable`) | 42 |

**Invalid fraction per activity:**
- Worst: adl11 0.43, adl10 0.42, adl15 0.28, adl16 0.23, fall5 0.18, adl8 0.18, adl9 0.17, fall6 0.17, fall1 0.17.
- Best: adl14 0.05, adl13 0.05, adl1 0.06.
- Files passing `hr_ok`: 437 of 984. adl10 has 2/41, adl11 1/41, adl15 1/41 and adl16 2/41. The full per-activity and per-subject tables are in the tables file §5.

**Worst subjects:** BITS2_S07 (30% invalid, 4/24 files hr_ok), S10 (27%), S41 (26%), S05 (25%), S38 (25%), S40 (25%, 3/24).

**Scope:**
- `motion_ok` = 979 files.
- `hr_ok` = 437 files.
- 542 files are `motion_only` (rule R7).

---

## 6. Duplicates and copy errors (decisions 1 and 2)

| Finding | Rule | Decision |
|---|---|---|
| `fall/user28/user28_fall4.csv` = `user28_fall8.csv` (byte-identical) | R1 | **exclude both** |
| `adl/user29/user29_adl13.csv` and `user29_adl14.csv` share an identical **HR** series (≥20 rows). **New finding.** | R2 | **exclude both** |
| `adl/user5/user5_adl2.csv` and `adl/user40/user40_adl4.csv` share an identical **magnetometer** series. Their acc/acg/gyro/HR are *not* shared. | R3 | **drop `mgm` from both**, keep the files |
| `fall/user7/user7_fall3.csv`: two complete block sets with *different* values; boundary not unambiguous | R4 | **exclude** |
| `fall/user31/user31_.fall{1,3,4,6}.csv`: the folder has no normally named fall1/3/4/6, so there is no conflict | R5 | keep, mapped to fall1/3/4/6, flagged |
| 3 files with malformed rows (blank `,,,,,` rows, 1 IMU row with no tag) | R8 | keep, flagged |

Shared-data search: a values-only hash of every stream with ≥20 rows, plus identical first 50 rows, across all 984 files. No other matches were found.

---

## 7. Accelerometer range and units (decision 8)

| Stream | Paper name | Median magnitude | adl13 (lying) median magnitude | Range | Meaning **[files]** |
|---|---|---|---|---|---|
| `acc` | "accelerometer" | 0.65 | 0.14 | ±78.3 | **gravity removed** (linear acceleration) |
| `acg` | "linear accelerometer" | 9.85 | 9.87 | ±78.45 | **includes gravity**. Canonical BITS-2 ACC (decision 8) |
| `gyro` | gyroscope | 0.43 | — | ±35.3 | rad/s **[inferred]** |
| `mgm` | magnetometer | 35.0 | — | −249…182 | µT **[inferred]** |

- **Units:** m/s² **[inferred]**. The lying-still magnitude is 9.87 ≈ g = 9.81.
- **Full scale:** `acg` full scale is 78.45 m/s² = **8.0 g**, so the MPU6500 was presumably set to ±8 g **[inferred]**. Saturation is rare: 0.009% of `acg` samples sit at full scale.
- **vs the E4 (±2 g = 19.61 m/s²):** median fraction of `acg` samples with any axis beyond 2 g:

  | Activity | Fraction beyond 2 g |
  |---|---|
  | jogging (adl3) | 21% |
  | jumping (adl4) | 23% |
  | swinging hands (adl12) | 11% |
  | falls | 0.2–1.5% of samples |
  | other ADLs | ~0% |

  **288/328 fall files peak above 2 g.** Median peak |acg| ranges from 24 m/s² (fall7) to 99 m/s² (fall8).

---

## 8. Proposed BITS-2 label mapping (decision 9; proposal only, NOT written to config)

`original_label` = the file stem (`adl1` …) plus the paper name. `motion_event_class`: falls → `abrupt_event_proxy`, ADLs → `normal_adl`.

| File | Paper activity | Proposed context_class | Context training | Notes |
|---|---|---|---|---|
| adl1 | Walking slowly | locomotion | include | |
| adl2 | Walking quickly | locomotion | include | |
| adl3 | Jogging | vigorous_activity | include | hard negative (>2 g) |
| adl4 | Jumping | vigorous_activity | include | hard negative (>2 g) |
| adl5–adl8 | Climbing up/down, slowly/normally | vigorous_activity | include | **assumed stairs, not stated in paper**; adl7/adl8 duration-flagged |
| adl9–adl11 | Sitting on chair (slow / rapid / nearly) | — | **exclude** | motion hard negatives; false-alert eval |
| adl12 | Swinging hands | — | **exclude** | motion hard negative (>2 g in 11% of samples) |
| adl13 | Lying on bed | stationary | include | |
| adl14–adl16 | Getting up / turning while lying | — | **exclude** | motion hard negatives; false-alert eval |
| fall1–fall8 | (Table 1) | — | — | `abrupt_event_proxy`; never "attack" |

---

## 9. Outputs

| File | Content |
|---|---|
| `metadata/bits2_file_manifest.csv` | 984 rows, one per file. Identity and paper name, format quirks, rows per stream, timestamp precision, rate estimates A/B, HR validity counts, HR-before/during/after-IMU counts, segments, duplicate/copy checks, flags, `excluded`, `dropped_streams`, `motion_ok`, `hr_ok` |
| `metadata/bits2_exclusions.csv` | one row per affected file/stream: rule_id, reason, evidence, decision, decided_by |
| `metadata/bits2_subjects.csv` | paper Table 2 (analysis only; never model inputs) |
| `metadata/bits2_nohr_download.csv` | URL, HTTP status, size and SHA-1 for every no-HR download |
| `metadata/raw_checksums_v2.csv` | raw checksum manifest v2 (v1 kept) |
| `reports/D00b_bits2_forensics_tables.md` | all auto-generated tables behind this report |

Re-run from the repo root in env `wearsafe`:
```
python scripts/download_bits2_nohr.py          # only if data/raw/bits2_website_nohr is absent
python scripts/make_bits2_subjects.py
python scripts/d00b_bits2_forensics.py          # ~30 s; deterministic (verified by re-run + byte compare)
```

---

## 10. Decisions for you

1. **Rate review.** The verdict is "inconsistent", so time-dependent features are off for BITS-2 v1 (decision 6). Do you also want rate-free motion features (peak magnitude, magnitude percentiles, threshold counts) treated as the *only* BITS-2 motion features in v1?
2. **BITS-2 windowing.** Fixed-duration windows (e.g. 2 s) can't be defined without a rate. Options:
   - (a) event-centred windows of a fixed number of rows around the peak, clearly labelled as row-based, not time-based. This may conflict with the spirit of decision 6, so it needs your call.
   - (b) whole-file features only.
   - (c) leave BITS-2 out of the v1 motion model and use it only for HR event analysis.
3. **adl7/adl8** (2-minute climbs with ~30–40 s of HR): keep flagged (current), or exclude?
4. **Event-centred HR (context doc §19):** IMU and HR overlap only at 1–1000 s timestamp resolution, and HR often starts well before the IMU. Should pre/during/post-event HR analysis be limited to files with ≤10 s timestamp steps, or postponed?
5. **Flagged files (R4b):** 123 files with internal timestamp breaks are kept. Should any of them be excluded?
6. **Confirm the label proposal in §8** before it goes into `config/label_maps.yaml`.
7. **Subject S01** (base HR 114, sinus tachycardia) and others with cardiac conditions: keep in all analyses, given that the health conditions are analysis-only?
