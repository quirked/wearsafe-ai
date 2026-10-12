# D02 smoke test — PPG-DaLiA normalisation and windowing (S03 + S06)

Date: 2026-10-12. Scope: smoke test only (user-approved). The full 15-subject run and D03 have NOT been started.
Every number here is in the auto-generated `reports/D02_ppg_dalia_smoke_v1_tables.md` (section numbers in brackets),
produced by `scripts/d02_smoke_report.py` from the outputs.

## Plain-language summary

1. **The two test subjects went through cleanly.**
   - S03 is a normal full-length recording (8741 s).
   - S06 is the shortened one (5250 s, no lunch, walking or working).
   - All 149 automatic checks passed [§1].
2. **Nothing was lost or invented.**
   - Every sample in the raw file appears once in the output.
   - The seconds per activity match the D00a inventory exactly (0 s difference) [§2, §3].
3. **Units:**
   - The watch accelerometer is now in m/s² (g × 9.80665), and its original unit is recorded [§1].
   - PPG stays at its native 64 Hz.
4. **Saturation flag added.**
   - Every accelerometer sample is now flagged when any axis sits at the ±2 g limit of the watch. That happens in 0.29% of S03's samples and 0.38% of S06's [§2].
   - It is concentrated in cycling for S03 (4.6%) and table soccer for S06 (2.5%) [§7].
   - 5% (S03) and 9% (S06) of 2-second motion windows contain at least one saturated sample [§7].
5. **Window counts are exactly as expected** for all three window sizes (2 s, 5 s, 30 s, each with 50% overlap) [§4].
6. **Windows at activity changes are flagged, not dropped.**
   - Only 0.35–0.95% of 2 s and 5 s windows span a change of activity, and 5–6% of 30 s windows do [§4].
   - Because of the 50% overlap, each activity change produces about one boundary window per task with a training label. So S03 has 14 `false_alert_eval_only` windows in every task (7 activities × 2 edges) [§5].
7. **Roles:**
   - Windows that are 100% one training activity are `train_candidate`.
   - Lunch and transient are `false_alert_eval`.
   - Boundary windows are `false_alert_eval_only`.
   - Every window is kept [§5].
   - Arousal is empty (null) for every PPG-DaLiA window, and all windows are `normal_adl` for the motion task (checked) [§1].
8. **Windows line up with the labels.** The two boundary plots show it [§8]. Both show the change from transient to stairs, with ±2 minutes around it.
9. **Deterministic.**
   - A separate trial run (written to a scratch folder) and the real run produced identical tables in every file [§9].
   - The trial run passed unchanged. No code was changed between the two runs.

## One thing worth knowing (an observation, no action taken)

The activity labels follow the study protocol, not the movement. In the boundary plots [§8]:
- **S03:** much of the "transient" period before the stairs looks like walking.
- **S06:** walking-like motion visibly starts before the "stairs" label begins.

(These are visual observations from the plots, not measured numbers.)

So "transient" windows can contain real locomotion, and the edges of activities are only approximate. This doesn't break anything:
- transient is already excluded from training and used for false-alert evaluation;
- training windows must be 100% one label.

It does mean the start of each activity carries some label noise. I'll keep watching for this in D03, using motion, not labels.

## What was produced

| Output | Content |
|---|---|
| `data/interim/ppg_dalia/normalized_signals_smoke_v1/PPGDALIA_S0{3,6}/` | Layer A: `wrist_acc` (m/s², `acc_saturated`), `wrist_bvp` (64 Hz), `activity` (4 Hz, label, context class, eval role), `hr_ref` (ECG HR on 8 s/2 s windows) + `run_info.json`, `checks.json` |
| `data/interim/ppg_dalia/windows_smoke_v1/` | Layer B: `motion_2s`, `context_5s`, `physiology_30s` (index references into Layer A + labels, purity, boundary flag, role, availability, saturation) + counts, `run_info.json`, `checks.json` |
| `metadata/ppg_dalia_subjects_smoke_v1.csv` | questionnaire data (analysis only, never a model input) |
| `reports/D02_ppg_dalia_smoke_v1_tables.md`, `reports/figures/D02_smoke_v1/` | tables and boundary plots |

**Re-run** (repo root, env `wearsafe`):
```
python scripts/d02_ppg_dalia_normalize.py --subjects 3 6 --tag smoke_v1
python scripts/d02_ppg_dalia_windows.py --tag smoke_v1
python scripts/d02_smoke_report.py --tag smoke_v1 --compare-root <folder of an independent re-run>
```
Rules used are in `config/windowing_v1.yaml` and `config/label_maps.yaml`. The scripts refuse to overwrite.

## Next step (needs your approval)

The full D02 run on all 15 subjects uses the same code and configs, with `--tag v1`, and writes to `*_v1/`.
