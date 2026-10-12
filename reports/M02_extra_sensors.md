# M02 — Do the gyroscope and barometer help catch falls? (EXPERIMENT, PRELIMINARY)

FallAllD wrist only. The setup was fixed in `config/m02_extra_sensors.yaml` before any result: the same windows, labels, splits, random-forest settings and threshold rule as M01. All numbers come from `reports/M02_tables.md` and `results/2026-10-12_M02_extra_sensors/`, produced by `scripts/m02_extra_sensors.py` and `scripts/m02_baselines.py`.

**Important limit:**
- The E4 watch used for the everyday-life recordings has **no gyroscope and no barometer**.
- So M02 measures only the fall side and FallAllD's own short everyday clips. It **cannot** measure false alarms per hour in everyday life.

## Plain-language summary (people the models never saw; accelerometer imitating the E4 watch)

| Sensors | Falls caught | Everyday clips with a false alarm (one per overlap group) | PR-AUC |
|---|---|---|---|
| Accelerometer only (M01) | 93.6% | 14.1% (8.4%) | 0.767 |
| + gyroscope | 93.4% | 13.2% (7.5%) | 0.816 |
| **+ barometer** | 93.0% | **4.7% (3.1%)** | **0.932** |
| + gyroscope + barometer | 92.6% | **4.7% (2.9%)** | **0.936** |

- **The barometer helps a lot.** It sees the small pressure change when the wrist drops in height.
  - With it, false alarms on everyday clips fall by about two-thirds (14.1% → 4.7%) while catching just as many falls.
  - The hard everyday movements trigger much less: "fail to stand up" 40% → 3%, "stumbling" 17% → 9%.
  - Results are steadier across people: per-person PR-AUC 0.96 ± 0.04 vs 0.86 ± 0.10.
- **The gyroscope helps only a little:** PR-AUC 0.77 → 0.82; false alarms 14.1% → 13.2%.
- **These are not shortcuts:**
  - gyroscope peak alone scores PR-AUC 0.13, and barometer change alone 0.08;
  - at the 90% recall threshold they fire on 49% and 92% of everyday clips;
  - the STOP check (any model > 0.98, or a shortcut close to a model) passed.
- **Jogging:** falls while jogging were caught 85–100% of the time in every configuration. Ordinary jogging clips rarely triggered: 0–19% depending on the clip type and sensors [M02 tables §2–3].

## Not finished (hard stop)
- The **unclipped-accelerometer** versions with gyroscope / barometer / both were **not run** in the time box; only the unclipped accelerometer-only row from M01 is available.
- Those 3 of the 8 configurations are missing, and are listed in `reports/M02_tables.md`. The E4-clipped results above are complete.

## Limitations
- FallAllD falls are lab-simulated proxies (9 people with falls), and its everyday clips are short 20 s cuts, not real daily life.
- **The barometer benefit could not be checked in everyday life.** Stairs, lifts, sitting down and weather change pressure too; in FallAllD only some of these appear.
- **Gyroscope units are [inferred]** (±2000 dps full scale). This does not affect the forest's results, because a constant scale factor doesn't change tree splits.
- The barometer feature is causal: it uses only the 4 s before the end of each window. Position test (b) from the D08 rules is still owed.
- Same fixed settings as M01; no tuning; PRELIMINARY.
