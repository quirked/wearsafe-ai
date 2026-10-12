# M03 v2 — new heart-reading quality cut-off for the "still but heart racing" check (demo_v0, PRELIMINARY)

The cut-off was chosen by a pre-set rule on 5 everyday-life "dev" people (`config/sqi_v2.yaml`): the lowest cut-off whose wrist heart rate stays within 5 bpm on average and within 10 bpm for ≥ 85% of moments. **Result: 0.50** (old: 0.90).
- Everything else is exactly as in M03; the old-setting numbers reproduce M03.
- All numbers come from `reports/M03_v2_tables.md` and `results/2026-10-12_SQI_v2_demo_v0/` + `results/2026-10-12_M03_v2_sqi_demo_v0/`.
- Everyday numbers are for the 10 "test" people, who were not used for the choice.

## Plain-language summary (simple model)

| | Before (old setting) | After (new setting) |
|---|---|---|
| Stress moments when the heart could be checked | 7% | 62% |
| People whose stress test triggered a check-in (of 15) | 4 | 15 |
| Stress moments caught (when checkable) | 87% | 79% |
| Calm/fun moments wrongly flagged (amusement / meditation) | 0% / 4% | 18% / 12% |
| Unnecessary check-ins per hour in everyday life | 0.09 | 2.4 |

- **The new cut-off lets the heart check work far more often.** During everyday stillness, the wrist heart rate is still accurate: on test people, the average error is 4.4 bpm and 88% of moments are within 10 bpm (old cut-off: 1.2 bpm, 99.5%).
- **The cost:**
  - more false check-ins in everyday life, about 2.4 per hour instead of 0.09;
  - more fun and calm moments flagged;
  - a lower overall score (PR-AUC 0.72 vs 0.88).
- **Device check:** WESAD calm vs PPG-DaLiA sitting can still partly be told apart (AUC 0.79; old 0.72).
- **The tree model shows the same pattern** [tables]: 15 of 15 people, 2.1 check-ins per hour.

## Limitations
- Lab stress (a speech and maths test) is not real danger, and there is no attack data.
- Driving, excitement and illness also raise heart rate.
- The check works only when the wrist is still.
- The cut-off was chosen on 5 people; table soccer heart readings stay poor (55% within 10 bpm).
- PRELIMINARY.
