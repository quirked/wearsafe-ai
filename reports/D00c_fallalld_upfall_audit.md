# D00c — FallAllD and UP-Fall inventory and audit (look-only)

Date: 2026-10-12. Purpose: decide, with evidence, whether **FallAllD** can be the main motion-training dataset and **UP-Fall** the external validation set. This is the "proposed, pending audits" design change in PROJECT_LOG.

Every number is from `reports/D00c_fallalld_upfall_audit_tables.md` (section IDs in brackets), produced by:
- `scripts/inspect/d00c_audit.py` (Parts A–B);
- `scripts/inspect/d00c_followup.py` (Part C, appended to the same file).

Earlier-dataset numbers come from the D00a, D00b and D02 reports. Tags: **[stated in paper]**, **[verified in files]**, **[inferred]**, **[unknown]**.

Nothing was preprocessed, windowed or modelled.

**Banned file:** `FallAllD_40SamplesPerSec_ActivityIdsFiltered.pkl` (241,792,100 B) was **listed only**. It was not extracted and not loaded [A1].

---

## Plain-language summary

1. **FallAllD is solid and matches its paper.**
   - The file holds 6,605 recordings across three body positions. Each has 4 sensors, which gives exactly the paper's "26,420 files" [A2].
   - Every recording is exactly 20 s, so the rates match the paper: 238 Hz accelerometer and gyroscope, 80 Hz magnetometer, 10 Hz barometer [A3].
   - Fall and ADL counts per device equal the paper's Fig. 8 exactly: wrist 523 falls + 1,992 ADLs [A4].
   - No accelerometer recording is duplicated [A9].
2. **The wrist part of FallAllD is smaller than it sounds.**
   - It has 2,515 recordings from **13 subjects**, and only **9 of them did falls**. The paper says 10 [A4, A6].
   - Subjects 7 and 8 have no wrist data. Subjects 4, 10, 11 and 12 have wrist ADLs only [A6].
3. **FallAllD activity numbers: use `activity_info.pkl`, not the paper's Fig. 4.**
   - The paper's Fig. 4 numbers ADLs differently from the data.
   - The data uses the `activity_info.pkl` numbering: the 12 hand-only activities are IDs 1–12, and they appear only on the wrist [A5]. That order is the same as the paper's Fig. 8 axis.
   - 65 of 79 names match Fig. 8 exactly; the other 14 are wording differences only [A5, §2.4].
4. **FallAllD units: the paper gives no conversion factor.**
   - Values are raw integer counts. The gravity check gives about 4,064 counts per g on the wrist, which fits 4,096 counts per g (±8 g on 16 bits) [inferred, A8].
   - The full ±8 g range is almost never reached: 0 samples sit at the limit [A8].
5. **Every FallAllD wrist fall goes above 2 g, and half the ADLs do too.**
   - **100%** of wrist falls (median peak 7.7 g) and **50.5%** of wrist ADLs exceed 2 g [A8].
   - The E4 watch in PPG-DaLiA and WESAD stops at ±2 g, so it would clip almost every fall.
6. **In FallAllD falls, the impact sits at the centre of the 20 s clip.** 96.6% of wrist-fall peaks fall between 8 and 12 s, and the median is 10.00 s [A10]. This makes event-centred windows easy, but it is also a shortcut a model could learn. Window design must hide the clip position.
7. **UP-Fall has the raw signals, not only pre-computed features.**
   - One full CSV holds all 17 subjects, 11 activities and 3 trials. It has 559 of 561 trials; the 2 missing ones are also listed in the paper [B2].
   - The three feature files in the zip are only a sample (one trial) [B1].
8. **UP-Fall's wrist signal is much coarser than its sensors.**
   - The sensors run at 100 Hz [stated in paper], but the released data was **resampled to the camera's timestamps** [stated in paper].
   - Rows arrive irregularly, at about 18–20 per second [B5, C4].
   - A third of accelerometer rows just repeat the previous value. So the wrist accelerometer gives only about **12 new values per second** [C3, C4].
   - Falls were done onto a mattress [stated in paper].
9. **UP-Fall labels need care.**
   - Each sample has a state tag (standing / falling / lying).
   - Tag 20 appears only in "falling forward using knees", for 4 subjects, and the paper doesn't explain it [B3, C5].
   - The accelerometer range isn't stated. The largest value seen is 9.26 g [B6].
10. **Recommendation (decision is yours):**
    - **FallAllD wrist** is suitable as the **main motion-training source**, with conditions on subjects, units, clip position and device harmonisation (§5).
    - **UP-Fall** is usable only as a **low-rate external stress test**. It is not an E4-equivalent validation set (§5).

---

## 1. Documentation summary

### 1.1 FallAllD (Saleh et al., IEEE Sensors J. 21(2), 2021)

- **Devices:** three identical RF-TRACK data-loggers, worn at the same time on the **neck, wrist and waist**. The dataset is meant for single-device detectors [stated in paper].
- **Sensors** (LSM9DS1 + MS5607 barometer):

  | Sensor | Rate | Range |
  |---|---|---|
  | Accelerometer | 238 Hz | ±8 g |
  | Gyroscope | 238 Hz | ±2000 dps |
  | Magnetometer | 80 Hz | ±4 Gauss |
  | Barometer (pressure + temperature) | 10 Hz | |

  [stated in paper]
- **Units:** the paper gives **no count-to-unit conversion factor** [unknown]. The files hold int16 counts [verified in files].
- **Subjects:** 15 (8 male, 7 female), aged 21–53, 48–85 kg, 158–187 cm [stated in paper].
  - Wrist: 13 subjects did ADLs and 10 did falls [stated in paper].
  - Waist/neck: 14 did ADLs and 12 did falls [stated in paper].
  - Subjects chose their own devices and activities [stated in paper].
- **Activities** [stated in paper]:
  - 44 ADL types, 12 of them hand activities (wrist only);
  - 35 fall types, covering forward/backward/lateral falls, slip/trip/syncope/rotation, and falls with and without recovery;
  - **no mattress**; body protection gear instead.
- **Clips:** each file is 20 s. Falls and transient ADLs are "centered around the transition moment", and cyclic ADLs fill the whole file [stated in paper].
- **Trials:** a trial number exists, but the paper doesn't fix how many trials each activity has [stated in paper]. In the data, there are 1–13 recordings per (subject, activity) on the wrist [verified in files, C2].
- **Wrist side and hand dominance:** not stated in the paper text [unknown].
- **No readme** is inside the zip [verified in files, A1].

### 1.2 UP-Fall (Martínez-Villaseñor et al., Sensors 19:1988, 2019)

- **Sensors:** 5 Mbientlab MetaSensor IMUs on the left wrist, neck, right trouser pocket, waist/belt and left ankle; plus EEG, 6 infrared sensors and 2 cameras [stated in paper]. Only the wearable IMUs are used here.
- **IMU channels:**
  - accelerometer in **g**, gyroscope in **deg/s**, each at **100 Hz**;
  - luminosity at 50 Hz;
  - accelerometer range **not stated** [unknown].

  [stated in paper]
- **Released data:** the consolidated dataset was **resampled to the timestamps of the slowest camera** (≈18 fps); "only raw values at these time-stamps were included". The final dataset has 296,364 samples at ≈18.4 Hz [stated in paper].
- **Subjects:** 17, aged 18–24, healthy. 16 are right-handed; subject 3 is left-handed [stated in paper, Table 4]. So the left wrist is the non-dominant wrist for 16 of 17 subjects, which is the same as the E4 placement in PPG-DaLiA (non-dominant) [stated in paper / D00a].
- **Activities:** 11 (Table 5) [stated in paper]:
  - 5 falls: forward using hands, forward using knees, backwards, sideward, sitting into an empty chair; each 10 s;
  - 6 ADLs: walking 60 s, standing 60 s, sitting 60 s, picking up an object 10 s, jumping 30 s, laying 60 s.
- **Trials and protocol:** 3 trials each, with a mattress in the falling area [stated in paper].
- **Labels:**
  - ADL labels come from timestamps; fall trials were tagged manually from video [stated in paper].
  - Falls have 3 states (standing → falling → laying) [stated in paper].
- **Missing data (Table 7):** S8 A11 trials 2–3 (all devices); S5 and S9 pocket IMU; S2 A5 EEG; S6 A10 T2 camera. The wrist IMU is not listed [stated in paper].

---

## 2. FallAllD (original `FallAllD.pkl` only)

### 2.1 Structure [verified in files, A2–A3]
- **Format:** a pandas DataFrame, 6,605 rows × 8 columns:
  - `SubjectID`, `Device` (Neck/Waist/Wrist), `ActivityID` and `TrialNo` (uint8 / str);
  - `Acc` and `Gyr`: int16 arrays of shape (4760, 3);
  - `Mag`: int16 (1600, 3);
  - `Bar`: float64 (200, 2), pressure + temperature.
- **Keys:** no duplicate (subject, device, activity, trial) keys.
- **No timestamps and no event-time field.**
- **Loading:** both pickles were loaded with a restricted unpickler that allows only pandas/numpy classes (`scripts/inspect/common.py`).

### 2.2 Paper numbers vs files

| Check | Paper | Files |
|---|---|---|
| Subjects | 15 | 15 [A2] |
| "Files" | 26,420 | 6,605 records × 4 sensors = 26,420 [A2]. The paper's "files" are per sensor [inferred] |
| Records per device | — | wrist 2,515, neck 2,292, waist 1,798 [A2] |
| Falls / ADLs per device (Fig. 8) | wrist 523/1,992, neck 733/1,559, waist 466/1,332 | identical [A4] |
| ACC/gyro rate | 238 Hz | 4,760 samples / 20 s = 238.0 for all 6,605 records [A3] |
| Mag / Bar rate | 80 / 10 Hz | 1,600/20 = 80; 200/20 = 10 for all records [A3] |
| Wrist subjects with ADLs / falls | 13 / 10 | 13 / **9** [A4] |
| Waist subjects with ADLs / falls | 14 / 12 | **13 / 11** [A4] |
| Neck subjects with ADLs / falls | 14 / 12 | 14 / 12 [A4] |

The rates are verified only as sample count ÷ the stated 20 s, because there are no timestamps. They are identical across all records.

### 2.3 Wrist device [A6, A7]
- **Records:** 2,515 from 13 subjects (no S7 or S8):
  - 1,992 ADLs (IDs 1–44);
  - 523 falls (IDs 101–135).
- **Subjects with falls:** only 9: S1, S2, S3, S5, S6, S9, S13, S14, S15. S13 has just 22 fall records.
- **ADL-only subjects:** S4, S10, S11, S12.
- **Records per subject:** 108–242.
- **Sensors:** all four on every wrist record [A2].

### 2.4 Activity labels: which numbering, and does `activity_info.pkl` match the paper? [A5]
- **Two numberings in the paper:**
  - Fig. 4 gives explicit IDs 1–44, e.g. 1 = walking slowly, 9 = clapping hands.
  - Fig. 8 lists all activities in a different order, without numbers.
- **The data follows `activity_info.pkl`:**
  - The IDs that occur **only** on the wrist are exactly **1–12**.
  - In `activity_info.pkl`, those are the 12 hand activities (start clap hands … beating a table).
  - Under Fig. 4 numbering, the hand activities would be 9, 10, 11, 22–26 and 31–34.
  - So **Fig. 4's numbers do not apply to the data** [verified in files].
- **`activity_info.pkl` order:** it matches the order of the Fig. 8 axis for all 44 ADLs and 35 falls.
- **Name differences:** 65/79 names agree exactly after normalisation. The 14 that differ, by `activity_info.pkl` ID, are:
  - **4** "Clap hands 1" vs "Clap hands 1 time";
  - **37–40** "lift" vs "lifts";
  - **114** "Fall, syncope, table" vs "Fall, syncope, attempt protection";
  - **115–120** "try sit" vs "attempt sit/lye down";
  - **124** "rev." vs "rec": a typo, the meaning is "with recovery" [inferred];
  - **135** "slide over a wall" vs "ending sitting". The paper text describes this fall as "sliding his back over a wall" [stated in paper].

  These are wording differences, with no swapped meanings [inferred]. One cosmetic issue: 110 is missing a comma.
- **Placeholders:** IDs 45–100 are "Unknown activity" placeholders, and none occur in the data [A5].
- **Falls:** IDs 101–135 [verified in files].
- **Near-falls:** the paper has no near-fall category. The closest ADLs are **23 "Stumbling"** (stumbling while walking without falling) and **15 "Fail to stand up"** (collapsing back into a chair). The paper notes that the latter "could arguably be considered a fall" [stated in paper]. Both are ADLs in the data. **Their role is a decision for you** (§6).

### 2.5 Units and range [A8]
- **Storage:** int16 counts [verified in files].
  - Wrist per-axis min −31,737 and max 32,680.
  - 0 samples at the int16 rails.
  - 29 of 11,971,400 samples have an axis ≥ 32,000 counts (≥ 7.8 g if 4,096 counts/g).
- **Conversion factor:** not stated in the paper [unknown].
  - **Gravity check** [verified in files]: in the quietest 1 s of each wrist record, the median |acc| is 4,064 counts (IQR 4,039–4,100). Waist gives 4,081 and neck 4,027.
  - **Full scale:** 32,768 counts / 8 g = **4,096 counts/g** [inferred].
  - The measured gravity sits within 1% of that.
  - With 4,096, still-wrist gravity reads 0.992 g. That is plausible for an uncalibrated MEMS sensor [inferred].
- **In g** (using 4,096 counts/g [inferred]):

  | Wrist group | Samples \|a\| > 2 g | Samples with any axis beyond ±2 g | Records with peak > 2 g | Median peak |
  |---|---|---|---|---|
  | Falls | 2.30% | 1.42% | **100%** | 7.74 g |
  | ADLs | 1.87% | 1.39% | **50.5%** | 2.01 g |

  The maximum |a| is 119.3 m/s² (12.2 g as a vector magnitude); the maximum single axis is 7.98 g.

### 2.6 Duplicates [A9, C1]
- **Exact hashes:** ACC, gyro and barometer are unique for all 6,605 records.
- **Magnetometer:** one pair is identical, both waist records of S12 (fall 113 trial 1 and fall 120 trial 1). That does not affect the wrist.
- **First-second check:** no records share an identical first 1 s of ACC.
- **Not tested:** near-duplicates beyond these exact checks [unknown].

### 2.7 Where is the impact? [A10]
- **Wrist falls:** the time of peak |acc| has median **10.00 s**, p25–p75 9.99–10.01 s and p5–p95 9.44–10.75 s. 96.6% lie in 8–12 s.
- **Wrist ADLs:** the median peak time is also 10.0 s, but the spread is wide (p5 1.25 s, p95 18.43 s).
- **No event-time field exists.** In practice, the clip centre (≈10 s) is a reliable impact marker for falls [verified in files].
- **Consequence:** in falls, the peak is at a fixed position, so any window or feature that can "see" the position within the clip is a shortcut. Event-based windows need random offsets, or another position-hiding scheme. That is decided later, not here.

---

## 3. UP-Fall (wearable data only)

### 3.1 What the zip contains [B1, B2]
- **`up-fail-complete-dataset.csv`** (82 MB): raw consolidated sensor data with 294,678 rows (the paper says 296,364) and 47 columns:
  - timestamp;
  - 5 IMUs × (ACC xyz in g, gyro xyz in deg/s, luminosity);
  - EEG and 6 infrared;
  - Subject, Activity, Trial and **Tag**.

  **These are raw signal values, not pre-computed features** [verified in files]. They are already resampled, though (§3.3).
- **Three `Subject1Activity1Trial1Features…csv` files** (761 columns): feature windows for **one trial only**, so a sample of the feature dataset, not the dataset itself.
- **No camera images or readme** are included [verified in files].

### 3.2 Subjects, activities and trials [B2–B4]
- **Coverage:** 17 subjects, 11 activities, trials 1–3. **559 of 561** trials are present; the missing ones are S8 A11 T2–T3, which the paper also lists.
- **Durations:** trials run 9.4–10.0 s (stated 10), 29.5–30.0 s (stated 30) and 59.5–60.0 s (stated 60), matching Table 5.
- **Labels:** the `Activity` column is the trial's activity. The per-sample `Tag` holds the state:
  - fall trials contain Tag 7 (standing), the fall code (1–5) and Tag 11 (laying);
  - picking-up trials contain Tags 6/7/9/11.
  - **Tag 20** appears in 12 trials, all "falling forward using knees" (S5, S7, S10, S12; 107–173 rows each) [C5]. Its meaning is **not documented** [unknown].

### 3.3 Wrist sensor [B6]
- **Columns:** `WristAccelerometer` x/y/z (g), `WristAngularVelocity` x/y/z (deg/s) and `WristLuminosity` (lx). There are no NaNs in the wrist columns.
- **Units:** the gravity check gives a median |acc| of 1.035 g (IQR 0.974–1.061) while standing, sitting or laying, so the unit really is g [inferred].
- **Range:** per-axis −9.26 to +7.12 g. There is no clustering at the extremes (1–2 samples at each min/max), so no visible saturation. The sensor range isn't stated [unknown]; the values exceed 8 g, so it is at least ±9.26 g [verified in files].
- **Wrist side:** left [stated in paper].

### 3.4 Sampling rate [B5, C3, C4]
- **Timestamp steps:** median 0.050 s. The per-trial median rate is 15.3–21.2 Hz (median 20.25 Hz).
  - Steps are irregular: p5 0.043 s, p95 0.087 s, max 1.73 s.
  - 10,154 steps are longer than twice the trial median.
  - There are no negative or zero steps.
- **Actual rows per second** (rows ÷ trial duration): median 17.97 Hz (14.0–20.0).
- **Repeated values:** about **33% of accelerometer rows exactly repeat the previous row on every IMU**, while the gyroscope repeats in only 0.1–0.6% of rows.
  - Repeats are runs of 1–4 rows.
  - The rate is the same in every activity (32.9–33.8%).
- **Effective rate:** the wrist ACC delivers a median **11.9 new values per second** (10.1–12.5 per trial) [verified in files].
  - Why this happens is not documented [unknown]. It is plausibly a slower ACC stream being held at the camera timestamps [inferred].
- **Verdict:** the wrist ACC rate is consistent across trials (IQR/median 5% for the per-trial median-step rate), but it is low and irregular.

### 3.5 Above 2 g, saturation, duplicates, missing data [B6, B7, C6]

| Wrist group | Samples \|a\| > 2 g | Samples with any axis beyond ±2 g | Trials with peak > 2 g | Median trial peak |
|---|---|---|---|---|
| Falls (Activity 1–5) | 2.22% | 1.55% | **95.7%** | 3.66 g |
| ADLs (Activity 6–11) | 3.05% | 2.71% | **31.9%** | 1.59 g |

- **Peak size:** the median fall peak is 3.66 g, well below FallAllD's 7.74 g. Possible reasons, none proven [inferred]: the mattress, the ~12 Hz effective sampling missing peaks, and a different device.
- **Peak timing:** the median fall peak is at 1.89 s into the 10 s trial (p5 1.23 s, p95 7.66 s) [C6].
- **Duplicates:** no duplicated rows or timestamps, and no two trials share an identical wrist series.
- **Missing values:** only the right-pocket IMU (36,109 rows; S5 and S9 per Table 7) and EEG (455).

---

## 4. Cross-dataset comparison (wrist ACC)

| | PPG-DaLiA | WESAD | BITS-2 | FallAllD (wrist) | UP-Fall (wrist) |
|---|---|---|---|---|---|
| Subjects | 15 | 15 | 41 | 13 (9 with falls) | 17 |
| Device | Empatica E4, non-dominant | Empatica E4 | phone/watch (MPU6500 [inferred, D00b]) | RF-TRACK logger, side [unknown] | MetaSensor, left wrist |
| ACC rate stated | 32 Hz | 32 Hz | 20 Hz | 238 Hz | 100 Hz sensor; ≈18.4 Hz released |
| ACC rate verified | 32 Hz exact (D00a) | 32 Hz exact (D00a) | **inconsistent**, ~5–100 Hz (D00b) | 238 Hz by length (no timestamps) | 15–21 Hz rows; **~12 Hz new ACC values** |
| Range / saturation | ±2 g; 0.12–0.38% of samples at rail (D02) | ±2 g, saturates (D00a) | ±8 g; 0.009% at full scale (D00b) | ±8 g; 0 at rail | not stated; max 9.26 g, no clustering |
| Stored units | g (pkl) | 1/64 g counts | m/s² (`acg` incl. gravity) | int16 counts, factor **not in paper** | g |
| Gyro | no | no | yes | yes (238 Hz) | yes (deg/s) |
| PPG / HR | BVP 64 Hz + ECG HR | BVP 64 Hz | HR ~1 Hz | no | no |
| Labels | 8 daily activities + transient | 4 affect states | 16 ADL + 8 fall types | 44 ADL + 35 fall types | 6 ADL + 5 fall types + per-sample state |
| Falls | no | no | yes (lab) | yes (lab, no mattress) | yes (lab, mattress) |
| Usable records | 15 recordings (~2.5 h each) | 15 | 979 motion_ok, 437 hr_ok | 2,515 × 20 s (523 falls) | 559 trials (255 fall trials) |
| Wrist falls with peak > 2 g | — | — | 288/328 files (D00b) | 100% | 95.7% |

---

## 5. Recommendation on the proposed design change (evidence-based; the decision is yours)

### 5.1 FallAllD as the main motion-training source: **supported, with conditions**

**For:**
- The data matches the paper exactly (counts, rates, record lengths).
- The rate is high and fixed (238 Hz) and the range is wide (±8 g, no saturation).
- No duplicate ACC data.
- 35 fall types without a mattress.
- Wrist-specific confusers that matter for false alarms: clapping, beating a table, waving.
- Clean subject IDs, which suit leave-one-subject-out.

**Risks and conditions:**
1. **Few fall subjects.**
   - Only 9 subjects did wrist falls, and S13 has just 22 fall records.
   - With leave-one-subject-out, 4 of 13 folds have no falls at all, so fall sensitivity must be reported per subject over the 9.
2. **Units.** The counts-to-g factor (4,096) is inferred, not stated in the paper. It needs your approval before use (§6).
3. **Clip position.** The fall impact always sits at 10.0 s in a 20 s clip. Windowing must hide the position, or a model can learn "peak in the middle".
4. **Not continuous life.** These are 20 s clips, so FallAllD cannot measure false alerts per hour. That stays with PPG-DaLiA (subject-held-out only, per the evaluation rule).
5. **Lab-simulated falls by adults aged 21–53** in protective gear. These are proxies for falls, not real falls, and never attacks.
6. **Unknown wrist side and hand dominance**; the E4 is worn on the non-dominant wrist.

### 5.2 UP-Fall as external validation: **only as a low-rate stress test, not an E4-equivalent check**

**For:**
- 17 new subjects (no overlap with FallAllD).
- Raw wrist signals are present.
- Left wrist, mostly right-handed subjects, which is close to the E4's non-dominant placement.
- Gyroscope included.
- Missing data is small and documented.

**Against:**
- The wrist accelerometer gives only **~12 new values per second**, at irregular steps.
- The data was resampled to camera timestamps.
- Falls landed on a mattress (median peak 3.66 g, against 7.74 g in FallAllD).
- Only 5 fall types.
- An undocumented Tag 20.
- An unknown sensor range.

A detector built at 32 Hz would be tested on much coarser data. Lower scores would partly reflect the data, not the model. Results must be reported separately and labelled as degraded-rate external validation.

### 5.3 PPG-DaLiA "normal life" as negatives across the device gap

- **The gap:** the E4 is ±2 g per axis, at 32 Hz. FallAllD is ±8 g, at 238 Hz.
- **The confound:** training on FallAllD falls (positives) against PPG-DaLiA windows (negatives) would let a model separate *devices*, not *events*. It could pick up clipping, rate, noise floor or orientation conventions.
- **Suggested safeguard (not done):**
  - train fall vs ADL **within FallAllD**;
  - use PPG-DaLiA for false-alert evaluation only, after identical harmonisation, on held-out subjects;
  - before any cross-device mixing, run a **device-discrimination check**: can a simple classifier tell harmonised FallAllD ADL windows from PPG-DaLiA windows? If yes, the gap is still there.

## 6. Proposed harmonised motion format (proposal only; nothing decided or applied)

Based on the verified numbers:
- **Signal:** 3-axis ACC in m/s² plus its magnitude. Gyro is an optional input; only FallAllD, UP-Fall and BITS-2 have it.
- **Rate:** **32 Hz**, the E4's native rate and the main target device. FallAllD is anti-alias filtered and downsampled from 238 Hz, and PPG-DaLiA and WESAD stay native.
  - UP-Fall cannot genuinely reach 32 Hz, because it has ~12 new values per second.
  - Proposal: evaluate UP-Fall in a **second, low-rate variant**. Resample everything to a common low rate (e.g. 12 Hz) and report it separately. Never upsample UP-Fall and present it as 32 Hz.
- **Range:** in the harmonised variant, clip each axis to the E4 rails [−2.0 g, +1.984 g] (= −128 and +127 counts of 1/64 g). Apply it identically to every dataset and always report it next to the unharmonised version, as already decided.
- **Orientation:** axis conventions differ between devices [unknown for FallAllD/UP-Fall vs E4]. Prefer magnitude-based features, or test axis-invariance explicitly.
- **BITS-2:** stays out of motion training (decision Q2).

## 7. Decisions for you
1. **Accept the design change?** FallAllD wrist as the main motion-training source and UP-Fall as a separate low-rate external stress test (§5)?
2. **FallAllD unit factor:** accept 4,096 counts/g [inferred: ±8 g on int16, and measured gravity 0.992 g], or keep raw counts until a source states the factor?
3. **FallAllD activity IDs:** confirm that `activity_info.pkl` (= the Fig. 8 order) is the label source, and that Fig. 4's numbers are ignored.
4. **Near-fall ADLs:** keep 15 "Fail to stand up" and 23 "Stumbling" as normal ADLs (hard negatives), or exclude them from training as ambiguous (and use them only in evaluation)?
5. **Neck and waist devices:** use only the wrist (matching the product)? Or are neck/waist recordings allowed for anything, such as analysis only?
6. **Clip-position shortcut:** how should event windows be placed (e.g. random offsets around the clip centre)? This is decided in the FallAllD windowing milestone. Should I record the risk as a rule now?
7. **UP-Fall Tag 20:** treat those samples as "falling", exclude them, or keep the trial-level label only? And should evaluation use the trial label (`Activity`) or the per-sample `Tag`?
8. **Harmonised rate:** 32 Hz main with a separate ~12 Hz variant that includes UP-Fall (§6), or something else?
9. **Device-discrimination check** (§5.3): add it as a required step before any cross-dataset mixing?

## 8. Files and re-run

| Output | Content |
|---|---|
| `data/interim/_unzipped/fallalld/` | `FallAllD.pkl`, `activity_info.pkl` (read-only; SHA-256 equals the zip stream; CRC OK) |
| `data/interim/_unzipped/upfall/` | the 4 CSVs (read-only; SHA-256/CRC OK) |
| `metadata/fallalld_file_manifest.csv`, `metadata/upfall_file_manifest.csv` | every zip member: size, CRC32, status (banned / extracted), SHA-256 zip vs extracted |
| `reports/D00c_fallalld_upfall_audit_tables.md` | all tables (Parts A–C) |

```
python scripts/inspect/d00c_extract.py         # refuses if the _unzipped folders exist
python scripts/inspect/d00c_audit.py           # Parts A–B
python scripts/inspect/d00c_followup.py        # appends Part C
```
Logs are in `logs/2026-10-12_D00c_*.log`.

**Disclosed issues:**
- **Empty table:** table C2 is empty because of a slicing bug in `d00c_followup.py` (`.head(0)`). The distribution line under it is correct. Nothing else depends on it.
- **Appended file:** the tables file was appended once by the follow-up script. Parts A–B were not changed.
