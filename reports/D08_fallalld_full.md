# D08 — FallAllD wrist motion dataset: full build (13 subjects, v1)

Date: 2026-10-12. Scope (user-approved): full build on all 13 wrist subjects, with the same code and checks as the smoke test. It covers both signal versions (unclipped, e4_clipped) and both feature sets (v1, v2). Numbers come from `reports/D08_fallalld_v1_tables.md` (section numbers in brackets) and the run logs. No model has been trained.

## Plain-language summary

1. **Every check passed:**
   - 69 of 69 build and feature checks [§1];
   - 8 of 8 final split checks (`logs/2026-10-12_D08_full.log`).
2. **Size:** all 2,515 wrist recordings → **47,785 two-second windows** per version, and 4 feature tables (2 versions × features v1/v2).
3. **Repeatable:** an independent run gave identical files (32 of 32) [§9].
4. **Windows by role** (all subjects) [§2, §4]:

   | Role | Windows | Use |
   |---|---|---|
   | Fall (impact window 9–11 s) | **498** | positives |
   | Everyday activity | **36,518** | negatives |
   | Fall context (rest of each fall clip) | 8,964 | analysis only |
   | Label-uncertain falls (25 clips) | 475 | clip-level scoring only |
   | Hard-negative probes (IDs 15, 23) | 1,330 | evaluation only |

   - Overall that is about 1 fall window for every 73 everyday windows.
   - Per subject with falls the ratio ranges from 1 : 35 (S15) to 1 : 99 (S13).
   - S04, S10, S11 and S12 have no falls [§2].
5. **Overlap groups** (identical shared samples between clips, all within one person) [§2b]:
   - 2,515 clips form 1,343 groups;
   - per subject, 59–151 groups.
   - The deduplicated view (one clip per group) is in [§2b].
6. **The E4 ±2 g limit** (e4_clipped) [§3–4]:
   - 78.4% of fall recordings and 29.4% of everyday recordings touch the limit somewhere;
   - **74.1% of fall windows** contain saturation, against **9.4% of everyday windows** (per subject 56–86% vs 5.4–15.5%);
   - the median fall-window peak drops from 41.9 m/s² (unclipped) to 25.1 m/s².
7. **Edge check (conversion vs native 238 Hz):** 0.07% (unclipped) and 0.14–0.15% (e4_clipped) at the clip edges, well under the 1% limit [§6].

## Limitations
1. **Clip-centre intensity pattern (dataset property).**
   - FallAllD everyday-activity clips are more intense around the clip centre and less intense near the edges, also in the raw 238 Hz data.
   - Window position carries a little information in the data itself. Test (b) is therefore comparative (converted vs raw-238 Hz position classifier, ΔAUC ≤ 0.02), and it runs at the first modelling milestone.
   - The table is in [§7b].
2. **Short impacts can be weakened at 32 Hz.** In 14 falls the 238 Hz impact peak is at 10.0 s, but after anti-aliasing the clip maximum moves elsewhere (D08 pre-checks). A watch-rate signal may under-represent brief impacts.
3. **The E4 ±2 g ceiling** removes most peak-size information. Saturation features (v2) carry part of it. Every later model reports **both** feature sets and **both** versions.
4. **Few fall subjects** (9). S13 has only 22 positive windows. Fall-detection metrics per subject will be noisy.
5. **features_v2 missing values by rule:**
   - `post_peak_stillness` is missing in 12.6–14.5% of windows;
   - `pre_peak_min_mag` in 5.2–9.0% [§5].
   - Imputation must be fitted on training folds only.
6. **Overlapping clips double-count windows within a subject.** The main results and the deduplicated check are always both reported (user decision 4).
7. **Report wording:** in the generated tables, §7's heading says "Smoke fall clips". In the full run it lists all clips with status entries in `metadata/fallalld_label_uncertain_v1.csv`. The table content is correct; the script heading is left over from the smoke test.

## What was produced

| Output | Content |
|---|---|
| `data/interim/fallalld/normalized_signals_v1/{unclipped,e4_clipped}/` | Layer A, 13 subjects, 32 Hz, m/s², per-axis saturation |
| `data/interim/fallalld/windows_v1/` | 47,785 windows with roles, overlap groups, `run_info.json`, `checks.json` |
| `data/processed/motion/fallalld_{unclipped,e4_clipped}_features-{v1,v2}_v1.parquet` | 4 feature tables |
| `data/processed/fallalld_features_v1_run/` | checks, edge check, clip-centre profile |
| `metadata/fallalld_records_v1.csv` | 2,515-record manifest |
| `splits/fallalld_v1.json` | 13 LOSO folds (built in the smoke step; verified against the full build) |

**Re-run** (repo root, env `wearsafe`):
```
python scripts/d08_fallalld_build.py --subjects 1 2 3 4 5 6 9 10 11 12 13 14 15 --tag v1
python scripts/d08_fallalld_features.py --tag v1
python scripts/d08_check_splits.py --tag v1
python scripts/d08_report.py --tag v1
```

**Current versions:** FallAllD Layer A/B `*_v1`; features `fallalld_*_features-{v1,v2}_v1`; split `splits/fallalld_v1.json`.
