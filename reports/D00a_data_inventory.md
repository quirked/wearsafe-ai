# D00a — Data inventory (PPG-DaLiA, WESAD, BITS-2)

Date: 2026-10-11. Look-only milestone: nothing in `data/raw/` was modified, nothing was unzipped (not needed, see §0).

**How to read this report.** Every number comes from one of the scripts in `scripts/inspect/` (re-run from the repo root; see §7). Statements are tagged:
- **[read]**: read directly from the files or the dataset's own documentation.
- **[inferred]**: my interpretation. It is not stated anywhere in the data or docs, so it needs confirming.

---

## Plain-language summary

1. **All three datasets are complete and intact.** The extracted folders are byte-for-byte identical to the downloaded zip files (CRC32 checked on all 1,138 files). PPG-DaLiA has 15 people, WESAD has 15 and BITS-2 has 41.
2. **PPG-DaLiA** is about 2.5 h of daily life per person (sitting, stairs, table soccer, cycling, driving, lunch, walking, office work). It has a wrist watch (accelerometer 32 Hz, PPG 64 Hz) and a chest strap with ECG. It provides a reference heart rate every 2 s, computed from the ECG. Subject S6 only has the first ~1.5 h, as the docs say.
3. **WESAD** is a lab stress study, about 1.5–2 h per person. It uses the same wrist watch and chest strap as PPG-DaLiA. Labels are baseline / stress / amusement / meditation. Each person has about 19–20 min of baseline, 10–12 min of stress, 6 min of amusement and 12–13 min of meditation.
4. **Units trap:** the wrist accelerometer is stored in **g** in PPG-DaLiA's pickle but in **raw counts (1/64 g)** in WESAD's pickle. That is the same device with a 64× difference in numbers. This must be converted before the two are ever combined.
5. **BITS-2 is not what was described.** There are **no separate heart-rate files**. Each of the 984 CSV files already contains IMU *and* heart-rate rows stacked one after another. So "matching an IMU file to its HR file" doesn't apply: they are in the same file.
6. **BITS-2 has no documentation in the download.** It has no readme and no activity names, only `adl1…adl16` and `fall1…fall8`. We know which recordings are falls and which are daily activities (from the folder names), but **not what each numbered activity is**.
7. **BITS-2 timestamps are badly damaged.** About 99% of them were saved with only 3 significant digits (e.g. `1.82E+11`), apparently by Excel. So we **cannot verify the motion-sensor sampling rate**. The little evidence that survives points to irregular, variable rates (between ~5 and ~50 Hz). Heart rate is about 1 per second.
8. **BITS-2 has some data errors.** Two files are exact duplicates (user28 fall4 = fall8). One magnetometer block appears in two *different* people's files. One file has two recordings glued together. Four files are named `user31_.fallN.csv`. 83 files have fewer than 5 heart-rate readings.
9. **Unused chest channels:** in PPG-DaLiA the chest EDA/EMG/Temp channels are dummy constants, as documented. In WESAD all chest channels are real.
10. **The project context document is missing.** `docs/` is empty, so the "differences from the context document" section could not be done (§5).

---

## 0. Folder map and archives (all datasets)

Source: `scripts/inspect/folder_map.py`, `scripts/inspect/check_archives.py`.

| Dataset | On disk | What's there | Extracted vs zip |
|---|---|---|---|
| PPG-DaLiA | 27.8 GB | `ppg+dalia.zip` (contains `data.zip` + `readme.pdf`), `data.zip`, `readme.pdf`, extracted `PPG_FieldStudy/` (15 subject folders S1–S15, 5 files each, 1.0–1.8 GB each) | 76/76 members identical; `ppg+dalia.zip` members identical to the loose `data.zip` and `readme.pdf` |
| WESAD | 18.5 GB | `WESAD.zip`, extracted `WESAD/` (15 subject folders, 5 files each, ~1.0–1.3 GB each) + `wesad_readme.pdf` | 76/76 identical |
| BITS-2 | 135 MB | `full_dataset.zip`, extracted `Dataset/{adl,fall}/user1..user41/` | 984/984 identical |

**[read]** Duplicates by design: `ppg_dalia/readme.pdf` is identical to `PPG_FieldStudy/PPG_FieldStudy_readme.pdf`. The data exists twice (zip + extracted) in every dataset, which costs about 7.5 GB of disk. Nothing needed unzipping, so `data/interim/_unzipped/` was not created. The E4 zips inside the subject folders were read in memory only.

**File types per subject:**
- PPG-DaLiA: `SX.pkl`, `SX_activity.csv`, `SX_quest.csv`, `SX_E4.zip`, `SX_RespiBAN.h5`.
- WESAD: `SX.pkl`, `SX_quest.csv`, `SX_readme.txt`, `SX_E4_Data.zip`, `SX_respiban.txt`.
- BITS-2: `userN_adlK.csv` (K=1..16) and `userN_fallK.csv` (K=1..8).

### Documentation found and read
| File | Key content for us |
|---|---|
| PPG-DaLiA `readme.pdf` (6 pp.) | Protocol (8 activities + transient 0), sampling rates, pkl layout, HR ground truth = mean ECG-HR over 8 s windows shifted 2 s; chest EDA/EMG/Temp are dummy; E4 HR/IBI/tags are derived and "should be ignored"; S6 valid only for first ~1.5 h; sync by double-tap with drift correction (≤1.2 s deleted for S9/S10). Table 1: subject demographics; Table 2: nominal minutes per activity (sitting 10, stairs 5, soccer 5, cycling 8, driving 15, lunch 30, walking 10, working 20). |
| WESAD `wesad_readme.pdf` (4 pp.) | S1 and S12 discarded (sensor malfunction); label codes 0–7; pkl layout; RespiBAN raw-to-SI formulas; E4 rates; quest.csv format (times in [minutes.seconds]); questionnaires (PANAS, STAI, SAM, SSSQ). |
| WESAD `SX_readme.txt` ×15 | Demographics, coffee/sport/smoking/illness, and notes (see §2.1). |
| E4 `info.txt` (in each E4 zip) | ACC range ±2 g, unit 1/64 g; first CSV row = start unix time (UTC), second row = sample rate. |
| BITS-2 | **None.** Only CSVs. |

---

## 1. PPG-DaLiA

Source: `scripts/inspect/inspect_ppg_dalia.py`. **[read]** All 15 pickles needed `pickle.load(f, encoding="latin1")` because they are Python-2 era.

### 1.1 Subjects
S1–S15, 15 subjects, none missing or extra. The pkl `questionnaire` matches `SX_quest.csv` (age, gender, height, weight, skin type, sport level 1–6). Subject notes in the docs:
- S6 has only the first ~1.5 h (hardware issue).
- S1 and S2 went down the stairs only once.

### 1.2 Pickle key tree (identical for all subjects; S1 shapes shown)
```
rpeaks                (11431,)      int32     indices into the 700 Hz ECG
signal/chest/ACC      (6448400, 3)  float64   700 Hz
signal/chest/ECG      (6448400, 1)  float64
signal/chest/EMG      (6448400, 1)  float64   dummy (constant -1.5)
signal/chest/EDA      (6448400, 1)  float64   dummy (constant 0)
signal/chest/Temp     (6448400, 1)  float32   dummy (constant -273.15)
signal/chest/Resp     (6448400, 1)  float64
signal/wrist/ACC      (294784, 3)   float64   32 Hz
signal/wrist/BVP      (589568, 1)   float64   64 Hz
signal/wrist/EDA      (36848, 1)    float64   4 Hz
signal/wrist/TEMP     (36848, 1)    float64   4 Hz
label                 (4603,)       float64   HR ground truth, one value per 8 s window / 2 s shift
activity              (36848, 1)    float64   4 Hz, codes 0..8
questionnaire         dict {WEIGHT, Gender, AGE, HEIGHT, SKIN, SPORT}
subject               'S1'
```
Other files:
- `SX_activity.csv`: lines `# NAME, start_second`.
- `SX_RespiBAN.h5`: raw 700 Hz uint16 channels, `channel_1`=ECG and others `CUSTOM`, plus zoom-level summaries.
- `SX_E4.zip`: ACC/BVP/EDA/TEMP/HR/IBI CSVs plus tags.csv and info.txt.

### 1.3 Signals
| Signal | Location / device | Doc rate | Verified | Units | Range (all subjects) | NaN |
|---|---|---|---|---|---|---|
| ACC | wrist, Empatica E4 (non-dominant) | 32 Hz | yes: len/32 equals all other signals' duration exactly | **g in pkl** (raw CSV is 1/64 g; pkl×64 is integer-valued for 100% of samples in all 15 subjects) | −2.0 … +1.984 (saturates at the ±2 g sensor limit) | 0 |
| BVP (PPG) | wrist, E4 | 64 Hz | yes | arbitrary (not stated) | about −2594 … +1933 | 0 |
| EDA | wrist, E4 | 4 Hz | yes | µS | — | 0 |
| TEMP | wrist, E4 | 4 Hz | yes | °C | — | 0 |
| ECG, Resp, ACC | chest, RespiBAN | 700 Hz | yes | already converted (ECG about ±1.5 mV; ACC ≈ g) **[inferred from ranges]** | — | 0 |
| EDA, EMG, Temp | chest | 700 Hz | — | **dummy constants** (docs say discard) | 0 / −1.5 / −273.15 | 0 |
| HR (E4 `HR.csv`) | wrist, derived by Empatica | 1 Hz (from CSV header) | — | bpm | — | — |

"Verified" means: n_samples / documented rate gives the **same duration (0.000 s spread)** for every signal and the activity vector, in every subject. Raw E4 CSV headers also state 32/64/4/4 Hz.

### 1.4 Labels
**Activity** (`activity`, 4 Hz) **[read: docs + verified]**. The codes are 0=transient, 1=sitting, 2=stairs, 3=table soccer, 4=cycling, 5=driving, 6=lunch, 7=walking, 8=working. The CSV names map onto them: NO_ACTIVITY→0, BASELINE→1, STAIRS→2, SOCCER→3, CYCLING→4, DRIVING→5, LUNCH→6, WALKING→7, WORKING→8.

**Not in the docs:** `SX_activity.csv` also contains a `CLEAN_BASELINE` segment (~2 min, at the very end). In the pkl it is labelled **0 (transient)**, not 1.

Seconds per activity code (pkl):

| sid | 0 transient | 1 sit | 2 stairs | 3 soccer | 4 cycle | 5 drive | 6 lunch | 7 walk | 8 work | total |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 2281 | 700 | 287 | 345 | 412 | 889 | 2355 | 754 | 1189 | 9212 |
| S2 | 2527 | 600 | 267 | 304 | 387 | 920 | 1220 | 689 | 1291 | 8205 |
| S3 | 2016 | 600 | 435 | 293 | 379 | 910 | 2160 | 738 | 1210 | 8741 |
| S4 | 2518 | 570 | 523 | 328 | 475 | 1007 | 1895 | 594 | 1240 | 9150 |
| S5 | 2574 | 600 | 465 | 290 | 432 | 830 | 2255 | 589 | 1270 | 9305 |
| S6 | 2297 | 633 | 430 | 309 | 533 | 1048 | **0** | **0** | **0** | 5250 |
| S7 | 2198 | 618 | 406 | 274 | 503 | 1035 | 2425 | 709 | 1175 | 9343 |
| S8 | 2082 | 600 | 412 | 323 | 420 | 770 | 1800 | 481 | 1192 | 8080 |
| S9 | 2007 | 600 | 483 | 285 | 554 | 955 | 1842 | 589 | 1245 | 8560 |
| S10 | 3542 | 598 | 467 | 305 | 488 | 937 | 2084 | 1082 | 1145 | 10648 |
| S11 | 2035 | 600 | 457 | 324 | 490 | 860 | 2408 | 654 | 1220 | 9048 |
| S12 | 1994 | 602 | 484 | 280 | 480 | 890 | 1460 | 529 | 1195 | 7914 |
| S13 | 2387 | 605 | 497 | 290 | 498 | 897 | 2028 | 709 | 1225 | 9136 |
| S14 | 2562 | 608 | 456 | 325 | 502 | 954 | 1731 | 615 | 1205 | 8958 |
| S15 | 2063 | 611 | 419 | 354 | 405 | 785 | 1440 | 659 | 1203 | 7939 |

Transient (code 0) is 22–33% of each recording, and 44% in the truncated S6.

**HR ground truth** (`label`) **[read + verified]**:
- One value per 8 s window with a 2 s shift.
- The count equals floor((duration − 8)/2) + 1 exactly for all 15 subjects (e.g. S1: 4603).
- Range 41.7–187.0 bpm, no NaN.
- S5 and S6 have high mean HR (125.8 and 119.5 bpm), versus 71–103 for the rest.

**R-peaks:** indices into the 700 Hz ECG. They are strictly increasing except for **repeated indices**: 3 in S6 and 1 in S14.

### 1.5 Timing
- **[read]** In the pkl, all wrist and chest signals and the activity vector start together and have identical durations. The docs say they were synchronised by double-tap, with drift correction.
- No timestamps are stored in the pkl, so time = index / rate.
- The raw files are longer than the pkl (the pkl was trimmed during sync). The RespiBAN h5 is +25 to +68 s longer and the raw E4 is +51 to +171 s longer. S6 is far longer still, because of the truncation.
- Durations per subject (pkl): 5250 s (S6), and 7914–10648 s for the others.
- **[read]** The raw E4 `HR.csv` starts 10 s after the E4 start, at 1 Hz.
- `tags.csv` has one button press per subject (two for S8).

### 1.6 Oddities
- S6: `S6_activity.csv` lists segments up to 9845 s (lunch, walking, working). The pkl ends at 5250 s, during the transient after driving. This matches the docs. **Do not use the CSV for S6 beyond 5250 s.**
- `CLEAN_BASELINE` segment exists in the CSV but is coded 0 in the pkl (undocumented).
- Wrist ACC saturates at ±2 g in every subject. That matters for vigorous motion and impacts.
- Gender key is `Gender` in the pkl but `GENDER` in the CSV, and the pkl value has a leading space (`' m'`).

---

## 2. WESAD

Source: `scripts/inspect/inspect_wesad.py`. **[read]** All 15 pickles needed `encoding="latin1"`.

### 2.1 Subjects
S2–S11 and S13–S17, 15 subjects. S1 and S12 are absent, as documented (sensor malfunction). Notes from `SX_readme.txt`:

| Subject | Note |
|---|---|
| S2, S17 | RespiBAN temperature sensor not fully attached |
| S3 | sunny workplace during baseline; reported valence 7 after stress |
| S5 | may have fallen asleep in meditation 1 |
| S6 | "not really stressed" in TSST interview; smoker |
| S8 | stressful day before; felt cold during stress; left-handed (all others right-handed) |
| S9 | felt ill |
| S15 | didn't believe the TSST cover story |
| S16 | felt cold during stress |

Additional data finding: **S3 chest Temp contains −273.15** (a sensor error value) even though its readme has no note about it.

### 2.2 Pickle key tree (S2 shapes)
```
signal/chest/{ACC (4255300,3), ECG, EMG, EDA, Temp(float32), Resp}   700 Hz, float64
signal/wrist/ACC  (194528, 3)  float64   32 Hz, **raw integer counts, 1/64 g**
signal/wrist/BVP  (389056, 1)  64 Hz
signal/wrist/EDA  (24316, 1)   4 Hz
signal/wrist/TEMP (24316, 1)   4 Hz
label             (4255300,)   int32     700 Hz
subject           'S2'
```
WESAD has no `activity`, `rpeaks` or `questionnaire` keys. `SX_quest.csv` holds the protocol schedule and self-reports. `SX_respiban.txt` is the raw 700 Hz text file with a JSON header.

### 2.3 Signals
| Signal | Location | Doc rate | Verified | Units | Range | NaN |
|---|---|---|---|---|---|---|
| ACC | wrist E4 | 32 Hz | yes (all durations equal) | **1/64 g counts** (integer-valued in all 15) | −128 … 127 (saturates) | 0 |
| BVP | wrist E4 | 64 Hz | yes | arbitrary | about −1774 … 1789 | 0 |
| EDA | wrist | 4 Hz | yes | µS | 0.045–15.9 | 0 |
| TEMP | wrist | 4 Hz | yes | °C | 28.97–35.97 (pkl) | 0 |
| ACC, ECG, EDA, EMG, Temp, Resp | chest RespiBAN | 700 Hz | yes | already in SI units in the pkl **[inferred from ranges, e.g. ECG ±1.5]** | — | 0 |

WESAD provides **no heart-rate ground truth**. HR would have to be derived from chest ECG or wrist BVP. The E4 `HR.csv` (1 Hz) exists but the docs say to ignore it.

### 2.4 Labels (700 Hz) **[read]**
The codes are:
- 0 = not defined / transient
- 1 = baseline
- 2 = stress (TSST)
- 3 = amusement
- 4 = meditation (appears twice per subject: Medi 1 and Medi 2)
- 5/6/7 = "ignore"

**[inferred]** By matching the protocol order in quest.csv, 5/6/7 = the `bRead` / `sRead` / `fRead` reading periods. S2 has no bRead and no code 5.

Seconds per code:

| sid | 0 | 1 baseline | 2 stress | 3 amusement | 4 meditation | 5 | 6 | 7 | total |
|---|---|---|---|---|---|---|---|---|---|
| S2 | 3061 | 1144 | 615 | 362 | 768 | 0 | 65 | 64 | 6079 |
| S3 | 3351 | 1140 | 640 | 375 | 780 | 73 | 67 | 67 | 6493 |
| S4 | 3306 | 1158 | 635 | 372 | 805 | 51 | 44 | 52 | 6423 |
| S5 | 3061 | 1198 | 645 | 374 | 794 | 72 | 44 | 70 | 6258 |
| S6 | 3905 | 1180 | 650 | 372 | 787 | 58 | 50 | 69 | 7071 |
| S7 | 2103 | 1186 | 640 | 372 | 790 | 50 | 44 | 53 | 5238 |
| S8 | 2309 | 1169 | 670 | 370 | 796 | 49 | 51 | 52 | 5466 |
| S9 | 2051 | 1180 | 645 | 372 | 793 | 60 | 62 | 60 | 5223 |
| S10 | 2270 | 1180 | 725 | 372 | 796 | 51 | 45 | 57 | 5496 |
| S11 | 2062 | 1180 | 680 | 368 | 791 | 50 | 52 | 50 | 5233 |
| S13 | 2399 | 1180 | 664 | 382 | 795 | 49 | 48 | 20 | 5537 |
| S14 | 2355 | 1180 | 675 | 372 | 794 | 63 | 55 | 54 | 5548 |
| S15 | 2082 | 1175 | 686 | 372 | 794 | 50 | 47 | 46 | 5252 |
| S16 | 2453 | 1180 | 673 | 368 | 792 | 55 | 57 | 53 | 5631 |
| S17 | 2739 | 1181 | 723 | 372 | 731 | 58 | 59 | 57 | 5920 |

Protocol order varies between subjects:
- Base, TSST, Medi 1, Fun, Medi 2 in S2, S3, S6, S9, S11, S14, S16.
- Base, Fun, Medi 1, TSST, Medi 2 in the other 8.
- S14's quest.csv lists "Medi 2" before "Fun".

### 2.5 Timing
- In the pkl, all signals and labels have identical durations (5223–7071 s) and a common start.
- There are no timestamps, so time = index / rate.
- **[read]** quest.csv times are in [minutes.seconds] from the RespiBAN start.
- **Verified:** each pkl label segment starts at a **constant per-subject offset** from its quest.csv time (−32.8 s to −154.8 s, the same offset for every condition of a subject). Every segment is **exactly 20 s shorter** than its quest interval.
- **[inferred]** The pkl was trimmed at the start relative to the raw RespiBAN file, which is 132–372 s longer. The labels drop 10 s at each edge, or 20 s at one end; I can't tell which.
- **Consequence:** use the pkl labels, not quest.csv times, against pkl signals.

### 2.6 Oddities
- Raw E4 `TEMP.csv` max is 382.18–382.21 °C in every subject. This is a start-up artefact, and it is absent in the pkl.
- Raw E4 recordings are 1006–1795 s longer than the pkl.
- S3 chest Temp contains −273.15.
- Codes 5/6/7 are present but documented only as "ignore".

---

## 3. BITS-2

Source: `scripts/inspect/inspect_bits2.py`. **No documentation is included in the download**, so everything below about meaning is **[inferred]** unless it is a count.

### 3.1 Subjects and files **[read]**
- Users 1–41: 41 users, none missing, all present in both `adl/` and `fall/`.
- `adl/userN/`: 16 files, `userN_adl1..16.csv` (656 files total).
- `fall/userN/`: 8 files, `userN_fall1..8.csv` (328 files total).
- **Naming anomaly:** `fall/user31/user31_.fall1/3/4/6.csv` has a dot before "fall". Its siblings fall2/5/7/8 are named normally. They appear to be ordinary fall files.

### 3.2 File structure **[read]**

Each CSV has the header `t,x,y,z,a,` and is a **stack of 5 sensor blocks**. Each block's rows are tagged by a sensor name:

| Tag | Row format | Rows total | Meaning **[inferred]** |
|---|---|---|---|
| `acc` | t,x,y,z,accuracy,acc | 637,950 | linear acceleration, gravity removed (median \|v\| 0.65; m/s²) |
| `acg` | t,x,y,z,accuracy,acg | 627,774 | acceleration incl. gravity (median \|v\| 9.85 ≈ 1 g in m/s²) |
| `gyro` | t,x,y,z,accuracy,gyro | 638,732 | gyroscope (rad/s) |
| `mgm` | t,x,y,z,accuracy,mgm | 616,824 | magnetometer (median \|v\| 35, µT) |
| `hrt` | t,bpm,status,hrt,, | 51,903 | heart rate (bpm) with Android sensor status |

Format details:
- HR blocks sometimes carry their own header `t,bpm,a` (375 files), which confirms the bpm/accuracy columns.
- IMU rows show accuracy = 3 in all but 4 rows. HR status values: 3 (46,613 rows), −1 (5,246), 0 (42).
- **[inferred]** These are Android `SensorManager` accuracy codes: 3 = high, 0 = unreliable, −1 = no contact. Rows with status −1 still carry bpm values (median 95), so **they look like real numbers but may not be valid readings**.
- **[inferred]** The value ranges (≈ ±78 m/s² ≈ ±8 g clip, gyro up to ±35 rad/s) and the Android-style tags suggest a **smartwatch**, presumably on the wrist. **The body location and device are not stated anywhere.**

Block layouts:

| Layout | Files |
|---|---|
| acc acg gyro hrt mgm | 602 |
| same, with header lines repeated between blocks | 368 |
| other orders (e.g. mgm first) | 13 |
| blocks repeated twice (`fall/user7/user7_fall3.csv`) | 1 |

Format variants:
- 711 files start with a UTF-8 BOM.
- One file has header `a,x,y,z,a,` (`adl/user23/user23_adl13.csv`).
- One file uses old-Mac CR line endings mixed with CRLF (`adl/user21/user21_adl7.csv`).
- Malformed rows: 5 files. Empty `,,,,,` rows appear in user21_adl4, user28_adl5 and user6_adl8. There is one HR row with no value (user2_adl15) and one IMU row with no sensor tag (user38_fall1).
- No NaN values.

### 3.3 "IMU file ↔ HR file" pairing
**[read]** The download contains **no separate HR files**. All 984 files contain both the IMU blocks and the HR block. Pairing is therefore **by construction, within the same file**:
- Complete IMU+HR "pairs": **984/984**.
- Unmatched files: **0**.
- In every file the HR time range overlaps the acc time range (checked at the coarse timestamp precision).

I did **not** invent any cross-file matching. **Uncertain cases** to list separately:
- `fall/user28/user28_fall4.csv` and `user28_fall8.csv` are **byte-identical**. One is probably a copy error, so user28 likely has only 7 distinct falls.
- The `mgm` block of `adl/user40/user40_adl4.csv` is **identical** to that of `adl/user5/user5_adl2.csv`. This is a cross-subject copy, so at least that block belongs to the wrong person in one of the files.
- `fall/user7/user7_fall3.csv` contains two full sets of blocks (3,372 rows per IMU stream). It may be two trials, or a duplicated recording.
- The 4 `user31_.fallN` files.

### 3.4 Sampling rates (this is the weakest part of BITS-2)
**[read]** Timestamps look like Android nanosecond counters (values 1e11–6e14). **~99% were written with 3 significant digits or fewer** (`1.82E+11`), as if the CSVs were re-saved by Excel:

| Stream | 3 significant digits or fewer | 5+ digits |
|---|---|---|
| acc | 637,948 | 2 |
| acg | 627,089 | 685 |
| gyro | 637,671 | 1,061 |
| mgm | 614,934 | 1,883 (+7 rows with 4 digits) |
| hrt | 51,855 | 48 |

At those magnitudes, one rounding step is 1 s to 1000 s. That makes most timestamps useless for rate checks. Timestamps are also **non-monotonic** inside a stream in 32–117 files per stream.

What *can* be verified:
- **HR:** 46 resolvable intervals, all = **1.000 s → HR ≈ 1 Hz**. The rows / span estimate gives median 1.02 Hz on the 49 files where it is meaningful.
- **IMU:** only 3 files have resolvable timestamps. `acg` in `fall/user16/user16_fall3.csv` has dt = 20 ms (**~50 Hz**). `mgm` in 2 files has dt = 100 ms (**~10 Hz**).
- **IMU rows / timestamp span** (only on the 61–74 files where rounding is <10% of the span): median **~5–6 Hz**, p10 0.02–0.3 Hz, p90 ~21–22 Hz.
- **IMU rows per HR row:** median ~20, p10 ~3, p90 ~61.

**Conclusion: the IMU sampling rate is NOT verified and appears irregular and variable across files** (consistent with event-driven Android sensors). Any fixed-rate assumption (e.g. "BITS-2 is 50 Hz") is unsupported by these files.

### 3.5 Activities, falls vs ADLs, trials
- **Falls vs ADLs [read]**: from the folder and file names, `fall1..8` are falls and `adl1..16` are activities of daily living.
- **Activity names: unknown.** There is no documentation in the download. I did not guess them.
- **Trials [read]**: one file per (user, activity index). There is no trial field, so it is **1 trial per subject per activity**, except the possible double recording in user7_fall3 and the duplicate user28 fall4/fall8.
- Whether, e.g., adl1..16 are 16 different activities or 8 activities × 2 repeats cannot be determined from the files.

Per-index sizes. HR rows are ≈ seconds of HR coverage, assuming 1 Hz **[inferred]**:

| Index | HR rows median [min–max] | acc rows median | | Index | HR rows median [min–max] | acc rows median |
|---|---|---|---|---|---|---|
| adl1 | 122 [2–269] | 446 | | adl13 | 122 [2–263] | 429 |
| adl2 | 132 [3–267] | 464 | | adl14 | 17 [2–138] | 429 |
| adl3 | 127 [3–256] | 869 | | adl15 | 10 [3–133] | 348 |
| adl4 | 32 [3–271] | 703 | | adl16 | 11 [3–138] | 470 |
| adl5 | 127 [3–240] | 724 | | fall1 | 14 [2–96] | 361 |
| adl6 | 122 [4–235] | 594 | | fall2 | 32 [4–59] | 684 |
| adl7 | 30 [2–185] | 349 | | fall3 | 32 [4–95] | 695 |
| adl8 | 40 [2–96] | 341 | | fall4 | 29 [3–92] | 379 |
| adl9 | 18 [2–145] | 289 | | fall5 | 21 [3–95] | 679 |
| adl10 | 10 [2–22] | 354 | | fall6 | 26 [4–88] | 479 |
| adl11 | 11 [2–20] | 344 | | fall7 | 25 [4–92] | 429 |
| adl12 | 122 [5–170] | 473 | | fall8 | 25 [2–86] | 594 |

### 3.6 Heart-rate quality
- bpm range 0–192 (mean 98.1). There are 138 rows with bpm = 0, spread across 16 files.
- Files with fewer than 5 HR rows: 63 ADL and 20 fall files.
- Files with fewer than 10 HR rows: 131 ADL and 50 fall files.
- Files with fewer than 50 acc rows: 13.

---

## 4. Cross-dataset comparison

| | PPG-DaLiA | WESAD | BITS-2 |
|---|---|---|---|
| Subjects | 15 (S1–S15) | 15 (S2–S17, no S1/S12) | 41 (user1–41) |
| Wrist device | Empatica E4, non-dominant wrist | same | not documented (Android watch **[inferred]**) |
| Wrist ACC rate | 32 Hz (verified) | 32 Hz (verified) | **unverified**, irregular (~5–50 Hz evidence) |
| Wrist ACC units (as stored) | **g** in pkl (raw CSV 1/64 g) | **1/64 g counts** in pkl | m/s² **[inferred]**; `acg` incl. gravity, `acc` gravity-removed |
| ACC range | ±2 g (saturates) | ±2 g (saturates) | about ±78 m/s² (~±8 g) |
| Gyroscope | none | none | yes (`gyro`, rad/s **[inferred]**) |
| Magnetometer | none | none | yes (`mgm`) |
| PPG/BVP | 64 Hz | 64 Hz | **none** (only HR values) |
| HR | ECG-derived ground truth, 8 s windows / 2 s shift; + E4 HR.csv 1 Hz (derived, "ignore") | none as ground truth (E4 HR.csv 1 Hz, "ignore"); derive from ECG/BVP | watch HR ~1 Hz with status codes; often sparse |
| Other wrist | EDA 4 Hz, TEMP 4 Hz | EDA 4 Hz, TEMP 4 Hz | — |
| Chest | ECG/Resp/ACC 700 Hz | ECG/Resp/ACC/EDA/EMG/Temp 700 Hz | — |
| Labels | activity 0–8 @4 Hz | condition 0–7 @700 Hz | file-level: adl1–16 / fall1–8 (names unknown) |
| Per-subject length | 1.5–3 h continuous | 1.5–2 h continuous | many short clips (seconds to ~4.5 min) |
| Timestamps | none in pkl (index/rate); raw E4 has unix start | same | per-row but rounded to 3 sig. figs |

---

## 5. Differences from `docs/WearSafe_AI_Full_Context_for_Claude.docx`

**This comparison could not be done.** Neither `docs/WearSafe_AI_Full_Context_for_Claude.docx` (named in the task) nor `docs/WearSafe_AI_Context.md` (named in CLAUDE.md) exists. `docs/` is empty, and a search of `/home` found no copy.

What *can* be compared with assumptions stated in the task prompt and CLAUDE.md:
- *"BITS-2: each activity has two CSV files, one with heart-rate data and one without."* **Not true for these files.** There is one file per activity, and it contains both.
- CLAUDE.md §1 says "wrist accelerometer (+ optional gyroscope) and PPG / heart-rate":
  - Only BITS-2 has a gyroscope.
  - BITS-2 has no PPG waveform.
  - PPG-DaLiA and WESAD have no gyroscope.
- CLAUDE.md lists hard negatives such as "table soccer, stairs, cycling, amusement". These do exist (PPG-DaLiA codes 2/3/4; WESAD code 3).

---

## 6. Open questions for the user

1. **Context document:** please add `docs/WearSafe_AI_Context.md` (or the .docx). Then I can complete §5 and check milestone IDs.
2. **BITS-2 documentation:** do you have the BITS-2 paper/readme? We need the activity names for adl1–16 and fall1–8, the device, the wrist side, the intended sampling rates and the units. Where did "two files per activity (with/without HR)" come from? Possibly a different release of the dataset.
3. **BITS-2 duplicates:** how should we treat user28 fall4 = fall8, the cross-user mgm block (user5_adl2 / user40_adl4), user7_fall3 (two recordings) and the user31 `_.fall` names? My recommendation: flag them in metadata and decide before any modelling.
4. **BITS-2 HR status −1** ("no contact" **[inferred]**) rows: treat them as invalid HR?
5. **PPG-DaLiA `CLEAN_BASELINE`** (coded 0 in the pkl): keep it as transient, as the dataset authors did?
6. **WESAD codes 5/6/7:** confirm they stay excluded, as the docs say.
7. The Python used was conda env `sao` (Python 3.11, numpy 2.4.6, pandas 3.0.5, h5py 3.16.0), because base Python lacks h5py. Should I create a dedicated project env and `requirements.txt` in the next milestone?

## 7. Risks for later milestones

- **Unit mismatch, wrist ACC:** DaLiA pkl in g, WESAD pkl in 1/64 g, BITS-2 in m/s² (inferred). A missed conversion would silently break any shared motion model.
- **Different ACC ranges:** E4 saturates at ±2 g, while BITS-2 reaches ~±8 g. Impact or fall features will clip on E4 data, so features won't transfer one-to-one.
- **BITS-2 sampling rate is unknown and irregular.** Resampling to a fixed grid needs trustworthy timestamps, and these are rounded (often to ≥1 s steps). Within-block row order may be the only usable time ordering. This is a major risk for the motion (fall-proxy) model.
- **BITS-2 has no PPG**, and its HR is sparse (181 files have fewer than 10 HR readings) and sometimes flagged as no contact. BITS-2 can't support PPG-quality logic.
- **BITS-2 duplicate/copy errors** (§3.3) could create cross-subject leakage if they are not handled before splitting.
- **WESAD quest.csv times are offset** from the pkl by 33–155 s per subject. Use the pkl labels only.
- **PPG-DaLiA S6** is truncated at 5250 s, and its activity CSV extends beyond the pkl.
- **WESAD has no HR ground truth.** Any arousal/HR feature must be derived (ECG or BVP), and the method must be fit on training data only.
- **Transient/undefined time is large** (DaLiA 22–44%, WESAD 2,051–3,905 s per subject). How it is handled must be decided before modelling, not after.
- **Sensor glitches:** WESAD S3 chest Temp −273.15; raw E4 TEMP 382 °C; DaLiA duplicate R-peaks (S6 ×3, S14 ×1).
- **Disk:** ~46 GB of raw data, stored twice (zip + extracted).

## 8. Reproducing this report
From the repo root (Python with numpy, h5py):
```
python scripts/inspect/folder_map.py --depth 2
python scripts/inspect/check_archives.py
python scripts/inspect/inspect_ppg_dalia.py      # ~10 min, loads one 1.0–1.7 GB pickle at a time
python scripts/inspect/inspect_wesad.py          # ~10 min
python scripts/inspect/inspect_bits2.py
```
