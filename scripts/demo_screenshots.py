"""Capture the 6 backup screenshots of the running demo app (headless system Chrome via Playwright).
Usage (repo root, app running on 127.0.0.1:8501):  python scripts/demo_screenshots.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/figures/demo_v0"
BASE = "http://127.0.0.1:8501/?"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shots = [p for p in OUT.glob("*.png")]
    if shots:
        raise FileExistsError(f"{OUT} already has screenshots; refusing to overwrite")
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)

        def page(q):
            p = b.new_page(viewport={"width": 1440, "height": 1000})
            p.goto(BASE + q, wait_until="networkidle")
            return p

        p = page("demo=everyday&segment=sitting&setting=balanced&speed=10&autoplay=1")
        p.wait_for_selector("text=All good", timeout=60000)
        p.wait_for_timeout(9000)
        p.screenshot(path=str(OUT / "1_everyday_all_good.png"), full_page=True)
        p.close()

        p = page("demo=everyday&segment=cycling&setting=balanced&speed=60&autoplay=1")
        p.wait_for_selector("text=Are you safe?", timeout=120000)
        p.wait_for_timeout(1500)
        p.screenshot(path=str(OUT / "2_everyday_unnecessary_checkin.png"), full_page=True)
        p.close()

        p = page("demo=fall&clip=fall&setting=balanced&speed=1&autoplay=1")
        p.wait_for_selector("text=Are you safe?", timeout=120000)
        p.wait_for_timeout(1500)
        p.screenshot(path=str(OUT / "3_fall_are_you_safe.png"), full_page=True)
        p.wait_for_selector("text=Help is being contacted", timeout=60000)
        p.wait_for_timeout(1500)
        p.screenshot(path=str(OUT / "4_help_contacted_simulation.png"), full_page=True)
        p.close()

        p = page("demo=fall&clip=fall&setting=balanced&speed=1&autoplay=1")
        p.wait_for_selector("text=Are you safe?", timeout=120000)
        p.get_by_role("button", name="I'm safe").click()
        p.wait_for_selector("text=You said you were safe", timeout=30000)
        p.wait_for_timeout(2500)
        p.screenshot(path=str(OUT / "5_im_safe_log.png"), full_page=True)
        p.close()

        p = page("page=about")
        p.wait_for_selector("text=Results so far", timeout=60000)
        p.wait_for_timeout(1500)
        p.screenshot(path=str(OUT / "6_about.png"), full_page=True)
        p.close()
        b.close()
    print("saved", sorted(x.name for x in OUT.glob("*.png")))


if __name__ == "__main__":
    sys.exit(main())
