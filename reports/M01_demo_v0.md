# M01 demo_v0 — first motion and context models (PRELIMINARY)

**PRELIMINARY — demo sprint results (tag `demo_v0`), 2026-10-12.**
- Fixed hyperparameters, no tuning; thresholds chosen on training subjects only.
- Not a final evaluation: no hyperparameter search, no calibration, no fusion.

All numbers come from the auto-generated tables, produced by `scripts/m01_demo_eval.py`, `scripts/m01_demo_context.py` and `scripts/m01_demo_device_check.py` from `results/2026-10-12_M01_demo_v0_run2/`:
- `reports/M01_demo_v0_motion_tables.md` [M§]
- `reports/M01_demo_v0_context_tables.md` [C]
- `reports/M01_demo_v0_device_tables.md` [D]

## Plain-language summary

1. **Fall vs everyday-activity detection works reasonably well on FallAllD, even with the E4 watch's ±2 g limit** [M§1].
   - The best model is the random forest. On held-out people its PR-AUC (the main score; 1.0 is perfect, 0.014 is chance here, because only 1.4% of windows are falls) is:
     - **0.83** on the full-range signal;
     - **0.77** on the E4-imitating signal.
   - The saturation features (v2) change little: 0.826 vs 0.820 unclipped, 0.767 vs 0.775 E4-clipped.
2. **Operating point:** the alarm threshold is set so that about 90% of fall windows trigger, using training people only. At that threshold, for the random forest [M§1–2]:

   | | Unclipped | E4-clipped |
   |---|---|---|
   | Fall clips detected | 92.6% | 93.6–94.0% |
   | Everyday clips with a false alarm | **11.0–11.5%** | **14.1%** |
   | Everyday clips with a false alarm, one clip per overlap group | 6.7–6.9% | 8.1–8.4% |
   | Fall windows correctly flagged (precision) | 58–60% | 51–52% |

   **False alarms are the weak point.** 1 in 7 to 1 in 9 everyday 20 s clips triggers at least once.
3. **The hard everyday movements trigger most** [M§2]:
   - the "stumbling" and "failing to stand up" probe clips trigger in 28.6% of cases (random forest);
   - the 25 uncertain-label fall clips are detected 72–84% of the time.
4. **The shortcut checks pass** [M§1–2]:
   - **peak size alone:** PR-AUC 0.27 (unclipped) and 0.13 (E4-clipped);
   - **saturation alone:** 0.05–0.11; at the 90% recall threshold it fires on almost every clip;
   - **position-only, on the position-matched subset:** 0.18, against a chance level of 0.21;
   - **position-only, at clip level:** it fires on 100% of clips, i.e. chance;
   - **STOP rule** (pooled PR-AUC > 0.98, or a shortcut within 0.05 of the models): not triggered.
5. **Results differ between people** [M§3–4]:
   - random forest, E4-clipped v2: per-person PR-AUC **0.86 ± 0.10** (worst S15 0.63, best S01 0.99);
   - everyday-clip false-alarm rate **14.6 ± 6.4%** (worst S15 29%).
6. **Activity context on PPG-DaLiA (4 classes)** [C]:
   - the random forest reaches **macro-F1 0.72** (0.70 ± 0.06 per person); logistic regression 0.66;
   - "Stationary" is the hardest class (F1 0.59): sitting is often confused with "low activity" (working, driving);
   - "low activity" is the easiest (F1 0.82).
   - Out-of-fold context predictions now exist for **every** PPG-DaLiA 5 s window (51,777), each from a model that never saw that person.
7. **Device check (report only): the two devices can be told apart** [D].
   - Using the same motion features, a classifier separates FallAllD (E4-imitated) everyday windows from PPG-DaLiA windows with AUC **0.72** (logistic regression) and **0.84** (random forest), where 0.5 would mean indistinguishable.
   - The biggest differences [D]:
     - FallAllD reads slightly lower average gravity (|a| median 9.82 vs 9.96 m/s²);
     - PPG-DaLiA everyday life has about twice the jerk.
   - So **a FallAllD-trained motion model applied to PPG-DaLiA is used on a different kind of data**. False-alert numbers measured on PPG-DaLiA must be read with that in mind.
   - Nothing was changed because of this check.

## Part A — FallAllD motion models (details)
- **Data:**
  - `data/processed/motion/fallalld_{unclipped,e4_clipped}_features-{v1,v2}_v1.parquet`, with splits from `splits/fallalld_v1.json` (13 people; LOSO);
  - training used `train_candidate` windows only: 498 fall windows (9–11 s) and 36,518 everyday windows;
  - never used for training: fall-context windows, the 25 uncertain-label fall clips, and the probes.
- **Models (fixed):** logistic regression (median imputer + scaler + balanced class weights) and a random forest (300 trees, min leaf 2, balanced class weights). Seed 0. All fitting is done on training folds only.
- **Threshold:**
  - per outer fold, from inner leave-one-out over that fold's training people with falls: the highest score keeping ≥ 90% recall on inner fall windows;
  - realised pooled recall on the test people is 0.90–0.91 [M§1];
  - deploy threshold = the median of the fold thresholds.
- **Saved models:**
  - 13 fold models + 1 deploy model (all 13 subjects) per configuration × model, in `results/2026-10-12_M01_demo_v0_run2/motion/<config>/models/` (8 deploy models);
  - out-of-fold scores for every window: `oof_<model>.parquet`.

| Config | Model | PR-AUC | ROC-AUC | Precision | Recall | Clip detection | Clip false alarm |
|---|---|---|---|---|---|---|---|
| unclipped v1 | LR | 0.679 | 0.983 | 0.340 | 0.900 | 93.2% | 22.9% |
| unclipped v1 | RF | 0.820 | 0.992 | 0.579 | 0.908 | 92.6% | 11.5% |
| unclipped v2 | LR | 0.682 | 0.983 | 0.342 | 0.902 | 93.4% | 23.2% |
| unclipped v2 | RF | 0.826 | 0.994 | 0.596 | 0.906 | 92.6% | 11.0% |
| e4_clipped v1 | LR | 0.649 | 0.992 | 0.401 | 0.902 | 93.6% | 20.4% |
| e4_clipped v1 | RF | 0.775 | 0.991 | 0.513 | 0.904 | 94.0% | 14.2% |
| e4_clipped v2 | LR | 0.655 | 0.993 | 0.429 | 0.902 | 93.2% | 19.1% |
| e4_clipped v2 | RF | 0.767 | 0.992 | 0.515 | 0.910 | 93.6% | 14.1% |

Shortcut baselines, the dedup check and per-subject tables are in [M§1–4].
- The position-only full-set PR-AUC (0.18) is above the full-set base rate (0.014) by construction, because positives sit only at the 9 s position. Its position-matched (0.18 vs chance 0.21) and clip-level (100% everywhere) values are at chance.
- Some single subjects reach PR-AUC ≥ 0.98 (e.g. S01 0.98–0.99). The STOP rule applies to the pooled PR-AUC, as fixed before the run; the pooled maximum is 0.826.

## Part B — PPG-DaLiA context model (details)
- **Split:** `splits/ppg_dalia_v1.json`: LOSO over 15 subjects; automatic check passed.
- **Training data:** 25,920 `train_candidate` 5 s windows with 4 classes; D03 v1 context features (§14).
- **Results (pooled out-of-fold F1):**

  | Model | Stationary | Low activity | Locomotion | Vigorous | Macro-F1 | Per subject |
  |---|---|---|---|---|---|---|
  | RF | 0.59 | 0.82 | 0.72 | 0.74 | **0.717** | 0.702 ± 0.060 |
  | LR | | | | | 0.655 | 0.650 ± 0.045 |

  Confusion matrices and per-subject tables are in [C].
- **Main confusions:**
  - stationary ↔ low_activity (sitting vs working/driving);
  - locomotion ↔ vigorous (walking vs stairs).
- **Out-of-fold predictions for all 51,777 windows** (probabilities for the 4 classes, predicted class, fold): `results/2026-10-12_M01_demo_v0_run2/context/oof_context_{lr,rf}.parquet`, ready for the next prompt.
- **What the false-alert windows look like:**
  - lunch is mostly predicted as `low_activity`;
  - transient windows spread over all classes (they contain real walking, D02/D03) [C].

## Part C — Device-discrimination check (details, report only)
- **Data:** 36,518 FallAllD e4_clipped ADL windows and 129,474 PPG-DaLiA 2 s windows. Both come from the same feature function, 2 s windows, 32 Hz, on the E4 1/64 g grid.
- **Method:** subject-grouped 5-fold CV.
- **Result:** AUC 0.721 (LR), 0.843 (RF).
- **The most different single features** [D]: `acc_mag_mean` (AUC 0.36), `acc_mag_rms`, and jerk (median 14.5 vs 29.0 m/s³).

## Limitations (PRELIMINARY)
- These are lab-simulated falls by 9 people, and falls are only a proxy for danger, never "attack".
- The false-alarm rate is per 20 s FallAllD clip, not per hour of real life. False alerts per user-hour on PPG-DaLiA are a separate evaluation (subject-held-out only; device gap per Part C).
- Fixed hyperparameters and no calibration. The deploy thresholds come from inner validation, not from any test person.
- **Clip-centre structure:** FallAllD clips are themselves more intense at the centre (D08). Test (b), the comparative position classifier, has not been run yet; it is still owed before any final claim.
- An earlier, aborted run (CPU oversubscription, no results) is kept in `results/2026-10-12_M01_demo_v0/` and is not used.
