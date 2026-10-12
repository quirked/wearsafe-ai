
## How to run the demo
**Current live demo: v4 with the light theme** (`app/wearsafe_demo_v4.py`). Run from the project root, in the `wearsafe` conda env:
```
python -m streamlit run app/wearsafe_demo_v4.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false --theme.base=light --theme.primaryColor=#D86A8A --theme.backgroundColor=#FFF7F9 --theme.secondaryBackgroundColor=#FFFFFF --theme.textColor=#3D2C3A
```
1. `cd wearsafe-ai` and use the `wearsafe` conda env (`streamlit==1.45.1` is installed there; see `app/requirements-app.txt`).
2. The app replays saved results (it contains no detection logic). It needs:
   - `results/2026-10-12_demo_app_v0/timelines.joblib` (in the repo; otherwise `OMP_NUM_THREADS=8 python scripts/demo_precompute.py`)
   - `results/2026-10-12_M02_demo_replay/replay.joblib` (`python scripts/m02_demo_replay.py`)
   - `results/2026-10-12_M03_v2_demo_replay/heart.joblib` (`python scripts/m03_v2_demo_replay.py`)
   - `results/2026-10-12_M02_extra_sensors/summary.csv` (`python scripts/m02_extra_sensors.py --phase eval`)
   - `reports/F02_demo_v1_test_tables.md` and `reports/M03_v2_sqi_demo_v0.md` (in the repo)

   The regeneration scripts need the local datasets under `data/` (not in the repo).
3. From your laptop: `ssh -N -L 8501:127.0.0.1:8501 raghav@raptor`, then open http://localhost:8501
4. Screenshots: `reports/figures/demo_v4/` (`light_theme.png` = the live look). Early prototype; numbers are preliminary.

**Light theme note (2026-10-12):** the light pink theme is also saved in `.streamlit/config.toml`. Start Streamlit from the project root so this file applies; the flags above set the same theme for safety.

### Previous versions (kept for reference)
- `app/wearsafe_demo_v5.py`: draft with visual fixes. **Not live**: it failed the visual check (controls row misaligned); see PROJECT_LOG 2026-10-12 11:28.
- `app/wearsafe_demo_v3.py`: adds the "heart racing while still" check; the design before the v4 redesign. Screenshots in `reports/figures/demo_v3/`.
- `app/wearsafe_demo_v2.py`: adds the air-pressure replay. Screenshots in `reports/figures/demo_v2/`.
- `app/wearsafe_demo.py` (v0/v1): the first prototype. Start: `python -m streamlit run app/wearsafe_demo.py --server.port 8501 --server.address 127.0.0.1 --server.headless true`. Screenshots in `reports/figures/demo_v0/`.
