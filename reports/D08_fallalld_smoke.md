# D08 smoke test — FallAllD wrist motion dataset (FALLALLD_S01 + FALLALLD_S04)

Date: 2026-10-12. Scope (user-approved): pre-checks on all wrist records, then a smoke build on S01 (falls) and S04 (no falls), using the checks as redefined after the first stop. The full 13-subject build has NOT been run.

Numbers come from:
- `reports/D08_fallalld_prechecks_tables.md` [P§] (all wrist records);
- `reports/D08_fallalld_smoke_v1_tables.md` [S§] (smoke subjects).

## Plain-language summary

1. **Unit check passed before anything else** [P§1]:
   - when the wrist is still, the signal reads 0.990 g (1,549 everyday-activity recordings, all 13 people within 1 ± 0.05 g);
   - so 4096 counts per g is right.
2. **The smoke build passed every check** (36 of 36) [S§1]:
   - 344 recordings → 6,536 windows, each version;
   - both versions (unclipped and E4-clipped) produced;
   - E4-clipped values stay inside the watch's limits and on its 1/64 g grid;
   - the unclipped data is never touched by the clipping step;
   - exactly one positive window per fall clip, at 9–11 s;
   - the probe activities and the fall-context windows are never used for training.
3. **Repeatable:** a separate run gave identical files (10 of 10) [S§9].
4. **The conversion to 32 Hz does not distort clip edges.** The edge windows differ from the original 238 Hz data by 0.06% (unclipped) and 0.15–0.19% (E4-clipped); the limit is 1% [S§6].
5. **Class balance for S01:** 73 fall windows against 2,983 everyday-activity windows (about 1 : 41). S04 has no falls (1,976 everyday windows) [S§2].
6. **Overlapping clips** (user decision 4: all kept):
   - S01's 236 clips form 151 overlap groups, and S04's 108 clips form 59 [S§2b];
   - the deduplicated view counts one clip per group.
7. **What the E4 limit does to falls** [S§3–4]:

   | | Unclipped | E4-clipped |
   |---|---|---|
   | Median peak in fall windows | 40.9 m/s² (4.2 g) | 24.7 m/s² |
   | Fall windows with saturation | 0% | 72.6% |
   | Everyday-activity windows with saturation | 0% | 7.8% |

   - With the ±2 g ceiling, fall peaks are cut down, but saturation becomes a strong cue: 72.6% of fall windows hit the limit, against 7.8% of everyday-activity windows.
   - Example figure: `reports/figures/D08_smoke_v1/FALLALLD_S01_A125_T01.png`. In a jogging fall, every jogging step also hits 2 g.

## Pre-check findings (all wrist records)

- **Fall peak timing** [P§2]:
  - at 32 Hz, the median peak is at 10.00 s and 92.5% of peaks lie in the positive window [9, 11);
  - at 238 Hz, 93.7% lie in [9, 11).
- **Decision 12 (39 clips with the 32 Hz peak outside [9, 11)):**
  - **14 kept** with normal labels: the 238 Hz peak is at about 10.0 s, and only the 32 Hz conversion moved the maximum;
  - **25 set to `label_uncertain_fall`:** off-centre at both rates. They are excluded from training and from window-level metrics, but count as fall clips in clip-level metrics.
  - The list and its evidence are in `metadata/fallalld_label_uncertain_v1.csv`.
  - The same file lists, **for your information only, 8 further clips** whose 238 Hz peak is just outside [9, 11) while the 32 Hz peak is inside. These were not among the 39 you reviewed, so they keep normal labels; one of them is in the smoke set (S01_A118_T01) [S§7].
- **Trial-number gaps** [P§4]:
  - 72 groups and 112 missing numbers, mostly trial 1;
  - none involved in any overlap;
  - consistent with discarded trials [inferred].
- **Overlapping clips** [P§5–7]:
  - 1,570 pairs of recordings share ≥ 1 s of identical raw samples, involving 1,621 of 2,515 records and forming 1,343 overlap groups (largest: 23 clips);
  - these are clips cut from one continuous recording (e.g. before/during/after clapping; sitting down/standing up);
  - all within one person — **0 across people**, so the leave-one-subject-out split is leakage-safe;
  - no fall–ADL overlap;
  - groups and pairs are in `metadata/fallalld_overlap_groups_v1.csv` and `metadata/fallalld_overlap_pairs_v1.csv`.

## Limitations

1. **Clip-centre intensity pattern (dataset property)** [S§7b, P diagnostic].
   - FallAllD clips are not evenly placed in time. Even "cyclic" everyday-activity clips (walking, clapping, …) are about 3–4% more intense at 7–10 s and about 2% less intense near the clip edges (windows starting at 1–2 s and 15–18 s).
   - The same pattern is in the raw 238 Hz data (the edge diagnostic), so it comes from how the dataset was cut, not from our processing.
   - Window position therefore carries a little information in the data itself. That is why test (b) is comparative: the converted vs raw-238 Hz position classifiers must differ by ≤ 0.02 AUC.
2. **Part of a short impact can be lost at watch-like sampling rates.**
   - In 14 falls the 238 Hz impact peak sits at 10.0 s, but after anti-aliasing to 32 Hz the impact spike is smaller than other movement in the clip (e.g. jogging steps), so the clip's maximum moves elsewhere [P§2].
   - A 32 Hz watch may see a weaker impact than the sensor really experienced.
3. **The E4 ±2 g ceiling removes most of the peak information.** Saturation length and count, and post-peak stillness, carry what remains (features_v2). Whether that is enough is a modelling question; no model has been trained.
4. **features_v2 has missing values by rule** [S§5]:
   - `post_peak_stillness` is missing when the window's peak is in its last 0.25 s (12–15% of windows);
   - `pre_peak_min_mag` is missing when the peak is the window's first sample (5–9%).
   - Models will need an imputation fitted on training folds only.
5. **Only 2 subjects in the smoke test,** so the class balance and saturation numbers are not yet representative.

## What was produced

| Output | Content |
|---|---|
| `data/interim/fallalld/normalized_signals_smoke_v1/{unclipped,e4_clipped}/` | Layer A, 32 Hz, m/s², per-axis saturation flags |
| `data/interim/fallalld/windows_smoke_v1/` | window table (roles, overlap groups) + `run_info.json`, `checks.json` |
| `data/processed/motion/fallalld_{unclipped,e4_clipped}_features-{v1,v2}_smoke_v1.parquet` | 4 feature tables |
| `data/processed/fallalld_features_smoke_v1_run/` | checks, edge check, clip-centre profile |
| `metadata/fallalld_records_smoke_v1.csv` | per-record manifest (raw SHA-256, peak time, saturation, overlap group) |
| `metadata/fallalld_label_uncertain_v1.csv`, `metadata/fallalld_overlap_groups_v1.csv`, `metadata/fallalld_overlap_pairs_v1.csv` | decisions 3 and 4 (all subjects) |
| `splits/fallalld_v1.json` | 13 LOSO folds; 9 subjects with falls, 4 without; inner validation subjects per fold; dedup and label-uncertain rules |

**Re-run** (repo root, env `wearsafe`):
```
python scripts/d08_fallalld_prechecks.py      # + d08_neardup_followup.py, d08_overlap_search.py, d08_overlap_search_cross.py
python scripts/d08_fallalld_metadata.py
python scripts/d08_fallalld_build.py --subjects 1 4 --tag smoke_v1
python scripts/d08_fallalld_features.py --tag smoke_v1
python scripts/d08_fallalld_splits.py
python scripts/d08_report.py --tag smoke_v1
```

## Next step (needs your approval)

The full D08 build on all 13 wrist subjects, tag `v1`, with the same code and checks. Open for you: whether the 8 info-only clips need any handling.
