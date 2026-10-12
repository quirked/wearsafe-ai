# D02 — PPG-DaLiA normalisation and windowing: full run (15 subjects) + boundary-margin rule

Date: 2026-10-12. Scope (user-approved): add `seconds_to_nearest_boundary` and the 10 s margin training rule
(`config/windowing_v2.yaml`), apply it to the smoke outputs as a new version, and run the full D02. D03 has NOT been started.
Numbers are from the auto-generated tables (section numbers in brackets):
- full run: `reports/D02_ppg_dalia_v1_tables.md`
- smoke re-version: `reports/D02_ppg_dalia_smoke_v2_tables.md`

## Plain-language summary

1. **All 15 subjects processed; every check passed.** That is 1310 of 1310 automatic checks on the full run (182 for the signals, 1128 for the windows) and 179 of 179 on the smoke re-version [§1].
2. **Nothing was lost or changed.**
   - Seconds per activity equal the D00a inventory for all 15 subjects (0 s difference) [§3].
   - Window counts equal the formula for every subject and window size [§4].
3. **New boundary rule applied.**
   - Every window now records how far it is from the nearest change of activity label (`seconds_to_nearest_boundary`).
   - A window is a training candidate only if it is 100% one training activity AND at least 10 s from any label change.
   - Windows that miss only the 10 s margin are kept as `false_alert_eval`.
4. **Effect of the margin:** it moved about 3% of the pure training windows to false-alert evaluation (2060 of 67139 motion windows, 824 of 26744 context windows, 129 of 4284 physiology windows) [§5c]. Nothing was dropped.
5. **Training candidates per activity**, all subjects [§5b], as motion 2 s / context 5 s / physiology 30 s windows:

   | Activity | Motion 2 s | Context 5 s | Physiology 30 s |
   |---|---|---|---|
   | working | 16703 | 6665 | 1088 |
   | driving | 13363 | 5328 | 863 |
   | walking | 9089 | 3620 | 582 |
   | sitting | 8821 | 3513 | 560 |
   | cycling | 6634 | 2638 | 417 |
   | stairs | 6164 | 2448 | 384 |
   | table soccer | 4305 | 1708 | 261 |

   - Lunch and transient (27103 + 35068 motion windows) are false-alert evaluation only.
   - Per-subject tables are in [§5b].
6. **Saturation** (watch accelerometer at its ±2 g limit):
   - 0.12–0.38% of samples per subject;
   - highest in cycling (up to 5.8% in S02) and table soccer (up to 2.5% in S06);
   - essentially zero while sitting [§2, §7].
   - 3.8–9.1% of 2 s motion windows contain at least one saturated sample [§7].
7. **Deterministic.** A separate trial run in a scratch folder produced identical tables in all 65 output files [§9].
8. **The smoke outputs are re-versioned, not overwritten.**
   - `windows_smoke_v2` uses the new rule.
   - `windows_smoke_v1` is kept, built with `windowing_v1.yaml`.

## Worth knowing: label noise can be longer than 10 s (visual observation; nothing changed)

The boundary plots [§8] show windows that are not training candidates as faded.

- In some subjects, the movement of the next activity starts well before the label changes.
- In S01, walking-like motion begins while the label still says "sitting", and earlier than the 10 s margin zone, so some late "sitting" windows that look like walking are still training candidates.
- Other subjects (e.g. S03) look cleaner at the plotted boundary.

The margin was fixed in advance and must not be tuned, so I left it as it is.

- **The cost:** context-model training labels at activity edges carry some noise beyond 10 s.
- **How I suggest we measure it in D03, without touching the rule:** a report-only table of motion features by distance-to-boundary bins, which shows how far into an activity the signal still looks like the neighbouring one. This is your call.

## What was produced

| Output | Content |
|---|---|
| `data/interim/ppg_dalia/normalized_signals_v1/PPGDALIA_S01…S15/` | Layer A (as in the smoke test), 148 MB |
| `data/interim/ppg_dalia/windows_v1/` | Layer B, 3 window tables + counts, `run_info.json`, `checks.json` (built with `config/windowing_v2.yaml`) |
| `data/interim/ppg_dalia/windows_smoke_v2/` | smoke windows re-built with the margin rule (from `normalized_signals_smoke_v1`) |
| `metadata/ppg_dalia_subjects_v1.csv` | questionnaire (analysis only, never a model input) |
| `reports/D02_ppg_dalia_v1_tables.md`, `reports/figures/D02_v1/` (15 plots) | full-run tables and boundary plots |
| `reports/D02_ppg_dalia_smoke_v2_tables.md`, `reports/figures/D02_smoke_v2/` | smoke re-version tables and plots |

**Re-run** (repo root, env `wearsafe`):
```
python scripts/d02_ppg_dalia_windows.py --tag smoke_v2 --in-tag smoke_v1
python scripts/d02_ppg_dalia_normalize.py --subjects 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 --tag v1
python scripts/d02_ppg_dalia_windows.py --tag v1 --in-tag v1
python scripts/d02_smoke_report.py --tag v1 --compare-root <folder of an independent re-run>
```

**Current versions:** Layer A `normalized_signals_v1`; Layer B `windows_v1` (windowing config v2).
