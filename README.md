
## How to run the demo
1. `cd wearsafe-ai` and use the `wearsafe` conda env (`streamlit==1.45.1` is installed there; see `app/requirements-app.txt`).
2. If `results/2026-10-12_demo_app_v0/timelines.joblib` is missing, run `OMP_NUM_THREADS=8 python scripts/demo_precompute.py`.
3. Start: `python -m streamlit run app/wearsafe_demo.py --server.port 8501 --server.address 127.0.0.1 --server.headless true`
4. From your laptop: `ssh -N -L 8501:127.0.0.1:8501 raghav@raptor`, then open http://localhost:8501
5. Backup screenshots: `reports/figures/demo_v0/`. Early prototype; numbers are preliminary.

**Light theme note (2026-10-12):** the app uses a light pink theme saved in `.streamlit/config.toml`. Start Streamlit from the project root so this file applies. For safety, the live demo is also started with the same theme as flags:
`python -m streamlit run app/wearsafe_demo_v4.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false --theme.base=light --theme.primaryColor=#D86A8A --theme.backgroundColor=#FFF7F9 --theme.secondaryBackgroundColor=#FFFFFF --theme.textColor=#3D2C3A`
