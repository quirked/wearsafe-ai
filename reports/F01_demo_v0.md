# F01 demo_v0 — rule-based fusion v0 and false prompts per user-hour (PRELIMINARY)

**PRELIMINARY — demo sprint (tag `demo_v0`), 2026-10-12.**
- The fusion rules were fixed in `config/fusion_v0.yaml` before any fusion result existed.
- The physiology rule is a **placeholder**, not a trained arousal model.
- Numbers come from `reports/F01_demo_v0_tables.md` [T§], produced by `scripts/f01_demo.py` into `results/2026-10-12_F01_demo_v0/`. The per-subject ranges come from `results/.../per_subject.csv`.

## Plain-language summary

1. **Normal daily life (PPG-DaLiA, all 15 people, 36.0 hours; the motion model never saw this dataset)** [T§1–2]:

   | Variant | False "Are you safe?" prompts per hour | Mean ± std across people | Range across people |
   |---|---|---|---|
   | **V0-base** | **23.8** | 24.1 ± 8.8 | 11.1 (S03) to 36.4 (S12) |
   | **V0-stillness** | **2.4** | 2.4 ± 1.4 | 0.4 (S03) to 5.9 (S04) |

   - **V0-base** would interrupt the user about every 2.5 minutes.
   - **V0-stillness** (prompt only if the person then stays still for 5 s) cuts that tenfold, to about one prompt every 25 minutes.
2. **Falls (FallAllD, held-out people)** [T§5]:

   | Variant | Fall clips detected | 20 s everyday clips with a prompt | Same, one clip per overlap group |
   |---|---|---|---|
   | **V0-base** | **93.6%** | 14.1% | 8.4% |
   | **V0-stillness** | **50.6%** | 7.0% | 2.1% |

   **The stillness rule loses almost half of the falls.** Many FallAllD falls are followed by movement within 5 s: recovery falls, getting up, or the 20 s clip ending.
   - Neither variant is "the" answer. Both were pre-registered and both are reported; the app offers both as a toggle.
3. **Which daily activities cause false prompts** [T§3], in prompts per hour of that activity:

   | Activity | V0-base | V0-stillness |
   |---|---|---|
   | table soccer | **80.9** | **22.6** |
   | cycling | **69.3** | 0 |
   | transient (between activities, often walking) | 33.2 | 1.7 |
   | driving | 32.6 | 5.8 |
   | walking | 28.0 | 0 |
   | stairs | 22.2 | 0 |
   | lunch | 5.7 | 2.1 |
   | working | 2.8 | 0.4 |
   | sitting | 0.4 | 0 |

   - Table soccer, the expected hard negative, still triggers 22.6 per hour with stillness.
   - Under stillness, driving (5.8 per hour) and lunch (2.1) remain.
4. **Physiology adds almost nothing in v0.**
   - At 97% of V0-base prompts (828 of 856) physiology is "uncertain", because SQI is low or motion is high.
   - So **no prompt reached HIGH** in either variant. This is the intended, honest behaviour: during strong movement, wrist PPG cannot be trusted (D03), and "uncertain" never suppresses the motion alarm.
5. **Context is shown but changes nothing in v0.** At V0-base prompts it matches the situation in many cases: cycling → "vigorous" in 132 of 134, driving → "low_activity" in 97 of 124 [T§4]. That is a possible future suppression cue, but it was not used.
6. **Device caveat.**
   - The motion model was trained on FallAllD and applied to the Empatica E4 data of PPG-DaLiA.
   - The two devices are distinguishable (M01 device check: AUC 0.72 with logistic regression, 0.84 with random forest). Part of the false-prompt rate may come from this device gap.
   - PPG-DaLiA itself is clipped at ±2 g, so **false-alert rates may be optimistic for wider-range watches**.
7. **Streaming engine:**
   - `src/wearsafe/inference.py` takes ACC at 32 Hz and optional BVP at 64 Hz, and produces every second: motion probability, context, physiology status, risk level and alert state, for both variants.
   - A test (`tests/test_inference.py`) streams 900 s of PPGDALIA_S03, one second at a time. It reproduces the offline motion probabilities (to 1e-12), alarms, physiology status and prompts (both variants) **exactly**, and matches the deploy context model on the offline features.

## Fusion v0 (as fixed in `config/fusion_v0.yaml`)
- **Motion model:** FallAllD **e4_clipped + features_v2 random forest** (M01 PR-AUC 0.767, against 0.655 for logistic regression), trained on all 13 FallAllD people.
  - Deploy threshold **0.1622** = median of the inner-validation thresholds.
  - The same feature code runs on the E4 data. features_v2 per-axis saturation = E4 counts at −128/+127.
- **Decisions:** one per second (2 s window ending now). A prompt is created by an alarm if no prompt occurred in the previous 30 s.
- **Physiology (placeholder):** from the latest completed 30 s window.
  - "uncertain" if SQI < 0.9, or if acc_mag_std > the gate. The gate = 95th percentile of sitting windows from the other 14 people: 0.51–0.58 m/s²; app value 0.567.
  - Otherwise "elevated" if HR relative to baseline ≥ +15 bpm, "unknown" if missing, "normal" otherwise.
- **Risk levels:** NONE / CHECK / HIGH (alarm + elevated). Physiology and context never suppress an alarm.
- **V0-stillness:** prompt only if acc_mag_std over the 5 s after the alarm window is ≤ the same gate; no prompt if fewer than 5 s remain.

## Still to do (before any final, non-demo claim)
1. **Position test (b)** (comparative position classifier: converted vs raw-238 Hz features, ΔAUC ≤ 0.02). It is still owed for the FallAllD motion models.
2. **False alerts:** the high false-prompt rate of V0-base (24/h) and the lost falls of V0-stillness (51%) both need work. Possible next steps, all to be pre-registered:
   - context-aware suppression (vigorous / driving);
   - stillness windows matched to the fall protocol;
   - more training negatives from real-life data.
3. **Device gap:** check the motion model's score distribution on PPG-DaLiA everyday windows vs FallAllD everyday windows.
4. **A trained arousal model** to replace the placeholder physiology rule (WESAD, milestone D04/M02). The motion-aware gate and the longer HR baseline (findings 3–4) are in place or pending.
5. **Calibration, hyperparameter search** (inner folds only), and the deduplicated / clip-level reporting for every future model.

## Limitations
- Falls are lab-simulated proxies (FallAllD); no real danger events exist in these data. Never "attack" detection.
- False prompts are measured on 36 h of protocol-driven daily life from 15 young adults wearing one device type.
- Stillness and the gate use a single threshold, the sitting p95. It was chosen before results and never tuned.
- PRELIMINARY: fixed hyperparameters, no calibration.

## Files
| Output | Content |
|---|---|
| `config/fusion_v0.yaml` | the fixed fusion rules |
| `results/2026-10-12_F01_demo_v0/ppg_dalia_decisions.parquet` | per-second decisions for all 15 PPG-DaLiA subjects (motion probability, alarm, physiology status, context, prompts and risk for both variants) |
| `results/2026-10-12_F01_demo_v0/{summary,per_subject,per_activity,fallalld_clip_level}.csv`, `thresholds.json` | tables and thresholds |
| `results/2026-10-12_F01_demo_v0/models/context_rf_deploy.joblib` | deploy context model for the app (all PPG-DaLiA) |
| `src/wearsafe/fusion.py`, `src/wearsafe/inference.py` | fusion rules and streaming engine |
| `tests/test_inference.py` | engine reproduces offline predictions (S03, 900 s) |
