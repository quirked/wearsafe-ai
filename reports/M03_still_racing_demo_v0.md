# M03-lite — "Still but heart racing" check-in (demo_v0, PRELIMINARY)

A second trigger, separate from the movement detector: if the wrist is **still** and the heart reading is **reliable**, but the heart behaves like stress, the watch gives a quiet check-in. The definitions were fixed in `config/m03_still_racing.yaml` before any result. All numbers come from `reports/M03_tables.md` and `results/2026-10-12_M03_still_racing_demo_v0/`, produced by `scripts/m03_still_racing.py`. Nothing in the demo app was changed.

## Plain-language summary

| | Simple model (logistic regression) | Tree model (random forest) |
|---|---|---|
| Stress moments caught (WESAD, unseen people; 30 s moments where the wrist was still) | **87%** | 75% |
| Calm/fun moments wrongly flagged (amusement / meditation) | **0% / 4%** | 0% / 0% |
| Unnecessary check-ins per hour in everyday life (PPG-DaLiA) | **0.06** (2 in 36 h) | 0.11 (4 in 36 h) |

- **When the wrist is still, heart rate tells stress apart well:** PR-AUC 0.88 and ROC-AUC 0.96 (logistic regression).
- **In everyday life it almost never fires:** 2 check-ins in 36 hours across 15 people.
- **The big catch: the wrist is rarely still enough.**
  - Only **7%** of stress moments, 18% of calm baseline and 11% of everyday-life moments passed the "still and reliable" check.
  - So the full check-in rule (2 flagged moments in a row) fired during stress for only **27% of people** (4 of 15).
  - Most of the time the heart reading is not trustworthy, as in A01, so this trigger is quiet but often blind.
- **Device check:** a simple classifier can partly tell WESAD calm moments from PPG-DaLiA sitting moments, even though both use the E4 watch (AUC 0.72 with logistic regression, 0.82 with the tree model). The lab session and everyday life differ, so the everyday number needs care.

## Details
- **WESAD build:**
  - wrist ACC (raw counts ÷ 64 → g → m/s²) and wrist pulse at 64 Hz;
  - labels aligned by their common start; duration checked equal for all 15 people;
  - 30 s windows with 15 s steps; training = purity-1.0 calm (baseline) vs stress, still-and-reliable windows only.
- **Features:** the same D03 heart features (HR mean/std/min/max, change, slope, relative to baseline, beat intervals, quality score) plus wrist movement intensity. No skin-sweat signal.
- **Validation:** leave-one-person-out over 15 people. The threshold came from inner validation on training people only (recall ≥ 80% on stress windows).
  - Logistic regression: precision 0.89 at recall 0.87.
  - Random forest: precision 0.75 at recall 0.75.
  - Per-person results are in the tables.
- **Everyday life:**
  - the model was trained on all 15 WESAD people, with threshold = the median of the inner thresholds (LR 0.917, RF 0.473);
  - it was applied to PPG-DaLiA 30 s windows of all 15 people, none seen by it;
  - the few check-ins came during lunch and transitions between activities, with none while sitting, working or driving (LR) [tables].

## Limitations
- The lab stress is a speech and maths test (TSST). It is **not real danger**, and there is no real attack data.
- Driving, excitement and illness can also raise heart rate.
- The trigger **only works when the wrist is still**; during movement it stays silent by design.
- Few training windows pass the gate (stress 7%), so the model learned from small numbers.
- There is a device and setting difference between WESAD and PPG-DaLiA (AUC 0.72–0.82).
- PRELIMINARY: fixed settings, no tuning, not added to the demo.
