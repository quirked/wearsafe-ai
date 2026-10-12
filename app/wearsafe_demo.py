"""WearSafe AI demo app (early prototype; numbers are preliminary).

Replays real recordings. The per-second results come from the project's streaming engine
(src/wearsafe/inference.py) and alert rules (src/wearsafe/fusion_v1.py), saved by scripts/demo_precompute.py.
This file only plays them back and shows them; it contains no detection logic.

Run (repo root):  streamlit run app/wearsafe_demo.py --server.port 8501
"""
import re
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
TIMELINES = REPO / "results/2026-10-12_demo_app_v0/timelines.joblib"
RESULTS_TABLE = REPO / "reports/F02_demo_v1_test_tables.md"
COUNTDOWN_S = 15

SETTINGS = {  # on-screen name -> (saved key, one-line description)
    "Most sensitive": ("most_sensitive", "Checks in at every sudden movement."),
    "Balanced": ("balanced", "Catches most falls, asks less often."),
    "Fewer interruptions": ("fewer_interruptions", "Waits a few seconds to see if anything changed."),
    "Quietest": ("quietest", "Only asks if you stay still afterwards. Misses more falls."),
}
REPORT_ROW = {"Most sensitive": "V0-base", "Balanced": "V1-tiered", "Fewer interruptions": "V1-change", "Quietest": "V0-stillness"}
DOING = {"stationary": "Sitting still", "low_activity": "Light activity", "locomotion": "Walking",
         "vigorous_activity": "Active exercise", "unknown": "Not sure yet"}
HEART = {"normal": "Normal", "elevated": "Raised", "uncertain": "Not reliable right now (too much movement)",
         "unknown": "Not available"}
STATUS = {"NONE": ("All good", "#1f9d55"), "CHECK": ("Checking on you", "#d97706"), "HIGH": ("Possible danger", "#dc2626")}
SEGMENTS = {"Sitting": "sitting", "Driving": "driving", "Walking": "walking", "Cycling": "cycling",
            "Table soccer": "table_soccer"}
CLIPS = {"A real fall": "fall", "Jogging (no fall)": "jogging"}
REAL_ACTIVITY = {"sitting": "Sitting", "driving": "Driving", "walking": "Walking", "cycling": "Cycling",
                 "table_soccer": "Table soccer", "transient": "Moving between activities", "lunch": "Lunch",
                 "working": "Desk work", "stairs": "Stairs"}
CONTACTS = ["Asha (sister)", "Ravi (friend)", "Campus security (example)"]

st.set_page_config(page_title="WearSafe AI demo", page_icon="⌚", layout="wide")


@st.cache_resource
def load_timelines():
    return joblib.load(TIMELINES)


@st.cache_data
def load_results():
    """Reads the test-people results table from the report file (does not retype numbers)."""
    text = RESULTS_TABLE.read_text()
    lines = [l for l in text.splitlines() if l.startswith("|")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = {}
    for l in lines[2:]:
        cells = [c.strip() for c in l.strip("|").split("|")]
        if len(cells) == len(header) and cells[0] in REPORT_ROW.values():
            rows[cells[0]] = dict(zip(header, cells))
    out = []
    for name, key in REPORT_ROW.items():
        r = rows[key]
        out.append({"Alert setting": name, "Falls caught": f"{float(r['fall_detect_pct']):.1f}%",
                    "Unnecessary check-ins per hour": f"{float(r['prompts_per_hour']):.1f}"})
    return pd.DataFrame(out)


def qp(name, default):
    v = st.query_params.get(name)
    return v if v is not None else default


def init_state():
    s = st.session_state
    if "init" in s:
        return
    s.init = True
    s.page = "About this demo" if qp("page", "") == "about" else "Live demo"
    s.demo = "Fall event" if qp("demo", "everyday") == "fall" else "Everyday life"
    s.segment = next((k for k, v in SEGMENTS.items() if v == qp("segment", "")), "Sitting")
    s.clip = next((k for k, v in CLIPS.items() if v == qp("clip", "")), "A real fall")
    s.setting = next((k for k, v in SETTINGS.items() if v[0] == qp("setting", "")), "Balanced")
    s.speed = {"1": "1×", "10": "10×", "60": "60×"}.get(qp("speed", ""), "10×")
    s.playing = qp("autoplay", "0") == "1"
    s.pos = 0
    s.alert = None
    s.help = None
    s.log = []
    s.key = None
    s.no_reply = qp("noreply", "0") == "1"


def current_recording(tl):
    s = st.session_state
    if s.demo == "Everyday life":
        seg = tl["everyday"][SEGMENTS[s.segment]]
        return seg, seg["decisions"], True
    clip = tl["fall"][CLIPS[s.clip]]
    return clip, clip["decisions"], False


def reset_playback():
    s = st.session_state
    s.pos, s.alert, s.help = 0, None, None


def add_log(text, t_rec):
    st.session_state.log.insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Recording time": f"{t_rec:.0f} s",
                                    "What happened": text})


def sidebar():
    s = st.session_state
    st.sidebar.title("⌚ WearSafe AI")
    s.page = st.sidebar.radio("Page", ["Live demo", "About this demo"], index=["Live demo", "About this demo"].index(s.page))
    st.sidebar.divider()
    demo = st.sidebar.radio("Choose a demo", ["Everyday life", "Fall event"], index=["Everyday life", "Fall event"].index(s.demo))
    if s.demo == "Everyday life":
        seg = st.sidebar.selectbox("Jump to", list(SEGMENTS), index=list(SEGMENTS).index(s.segment))
        changed = seg != s.segment
        s.segment = seg
    else:
        clip = st.sidebar.selectbox("Recording", list(CLIPS), index=list(CLIPS).index(s.clip))
        changed = clip != s.clip
        s.clip = clip
    if demo != s.demo or changed:
        s.demo = demo
        reset_playback()
        st.rerun()
    st.sidebar.divider()
    setting = st.sidebar.radio("Alert setting", list(SETTINGS), index=list(SETTINGS).index(s.setting),
                               captions=[v[1] for v in SETTINGS.values()])
    if setting != s.setting:
        s.setting = setting
        reset_playback()
        st.rerun()
    s.speed = st.sidebar.select_slider("Playback speed", ["1×", "10×", "60×"], value=s.speed)
    c1, c2, c3 = st.sidebar.columns(3)
    if c1.button("▶ Play", use_container_width=True):
        s.playing = True
    if c2.button("⏸ Pause", use_container_width=True):
        s.playing = False
    if c3.button("↺ Restart", use_container_width=True):
        reset_playback()
        s.playing = True
    st.sidebar.caption("Early prototype. Numbers are preliminary.")


def prompt_times(dec, key):
    """Recording second at which each check-in is shown (some settings wait 5 s before asking)."""
    m = dec[f"prompt_{key}"].astype(bool)
    return [(float(t + lat), r) for t, lat, r in zip(dec.t_abs[m], dec[f"lat_{key}"][m], dec[f"risk_{key}"][m])]


def advance(dec, key):
    s = st.session_state
    if not s.playing or s.alert or s.help or s.pos >= len(dec) - 1:
        if s.pos >= len(dec) - 1:
            s.playing = False
        return
    step = {"1×": 1, "10×": 10, "60×": 60}[s.speed]
    t_now = dec.t_abs.iloc[s.pos]
    new_pos = min(len(dec) - 1, s.pos + step)
    t_new = dec.t_abs.iloc[new_pos]
    for t_show, risk in prompt_times(dec, key):
        if t_now < t_show <= t_new:
            new_pos = int(np.searchsorted(dec.t_abs.to_numpy(), t_show, side="left"))
            new_pos = min(new_pos, len(dec) - 1)
            s.alert = {"start": time.time(), "risk": risk, "t": t_show}
            add_log("Sudden movement noticed — asked “Are you safe?”", t_show)
            break
    s.pos = new_pos


def status_card(text, color, sub=""):
    st.markdown(
        f"<div style='background:{color};color:white;border-radius:18px;padding:22px 28px;margin-bottom:12px'>"
        f"<div style='font-size:42px;font-weight:700'>{text}</div><div style='font-size:18px'>{sub}</div></div>",
        unsafe_allow_html=True)


def alert_box():
    s = st.session_state
    left = COUNTDOWN_S - (time.time() - s.alert["start"])
    if left <= 0:
        add_log("No answer — help is being contacted (SIMULATION)", s.alert["t"])
        s.help = {"t": s.alert["t"], "when": datetime.now().strftime("%H:%M:%S"), "risk": s.alert["risk"]}
        s.alert = None
        s.playing = False
        st.rerun()
    title, color = STATUS[s.alert["risk"]]
    st.markdown(
        f"<div style='border:6px solid {color};border-radius:24px;padding:30px;text-align:center;background:#fff7ed'>"
        f"<div style='font-size:22px;color:{color};font-weight:700'>{title}</div>"
        f"<div style='font-size:56px;font-weight:800;margin:6px 0'>Are you safe?</div>"
        f"<div style='font-size:24px'>If you don't answer in <b>{int(np.ceil(left))} s</b>, "
        f"your contacts will be alerted.</div></div>", unsafe_allow_html=True)
    if st.button("✅  I'm safe", type="primary", use_container_width=True):
        add_log("You said you were safe", s.alert["t"])
        s.alert = None
        st.rerun()


def help_screen():
    s = st.session_state
    st.markdown("<div style='background:#dc2626;color:white;border-radius:18px;padding:22px 28px'>"
                "<div style='font-size:20px;font-weight:700'>SIMULATION — no real messages are sent</div>"
                "<div style='font-size:44px;font-weight:800'>Help is being contacted</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Emergency contacts notified (SIMULATION)")
        for c in CONTACTS:
            st.markdown(f"- 📱 {c} — message sent (simulated)")
        st.markdown("📍 **Location shared (simulated)**")
        st.markdown(f"🕒 **Time of alert:** {s.help['when']}")
    with c2:
        st.subheader("Event log")
        st.dataframe(pd.DataFrame(s.log), hide_index=True, use_container_width=True)
    if st.button("Back to the demo", use_container_width=True):
        s.help = None
        st.rerun()


def live_page(tl):
    s = st.session_state
    rec, dec, has_heart = current_recording(tl)
    key = SETTINGS[s.setting][0]
    advance(dec, key)
    if s.help:
        help_screen()
        return
    row = dec.iloc[s.pos]
    t = float(row.t_abs)
    if s.alert:
        alert_box()
    else:
        sub = f"Alert setting: {s.setting}"
        status_card(*STATUS["NONE"], sub=sub)
    if s.demo == "Everyday life":
        seg0 = rec["seg"][0]
        real = rec["activity"][min(len(rec["activity"]) - 1, max(0, int(t - seg0)))]
        st.caption(f"Everyday-life recordings (15 people) — one real person the system had never seen. "
                   f"What they were really doing: **{REAL_ACTIVITY.get(real, real)}**")
    else:
        st.caption(f"Fall recordings (13 people) — one real person the system had never seen. "
                   f"This recording: **{rec['label'].split(': ', 1)[-1]}**. This test watch can't measure very hard jolts fully.")
    score = 0 if np.isnan(row.p_motion) else int(round(100 * row.p_motion))
    heart = HEART.get(str(row.phys_status), "Not available") if has_heart else "Not available in this recording"
    c = st.columns(4)
    c[0].metric("Sudden movement score", f"{score} / 100", help="How sudden and unusual the wrist movement is right now.")
    c[1].metric("What the person is doing", DOING.get(str(row.context), "Not sure yet"))
    c[2].metric("Heart reading", heart, help="The wrist heart reading is often not reliable during strong movement.")
    c[3].metric("Alert setting in use", s.setting)
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Wrist movement**")
        mag = rec["mag"] / 9.80665
        start = rec["seg"][0] if s.demo == "Everyday life" else 0
        i1 = int((t - start) * 32)
        i0 = max(0, i1 - 60 * 32)
        x = np.arange(i0, i1)[::4] / 32 + start
        st.line_chart(pd.DataFrame({"seconds": x, "Wrist movement": mag[i0:i1][::4]}).set_index("seconds"), height=220)
    with g2:
        st.markdown("**Heart rate**")
        if has_heart:
            hr = rec["hr"]
            hr = hr[(hr.end_abs <= t) & (hr.end_abs > t - 600)]
            if len(hr):
                st.line_chart(pd.DataFrame({"seconds": hr.end_abs, "Heart rate (beats per minute)": hr.hr_mean}).set_index("seconds"),
                              height=220)
            else:
                st.info("Waiting for enough heart data…")
        else:
            st.info("Not available in this recording (no heart sensor).")
    st.progress(min(1.0, s.pos / max(1, len(dec) - 1)), text=f"Playback: {t:.0f} s")
    if s.log:
        st.markdown("**Event log**")
        st.dataframe(pd.DataFrame(s.log), hide_index=True, use_container_width=True)
    if (s.playing and not s.alert) or s.alert:
        time.sleep(1)
        st.rerun()


def about_page():
    st.title("About this demo")
    st.markdown("### What it does\nWatches for sudden, unusual wrist movement and checks if you are okay. "
                "If you don't answer, it can alert your contacts.")
    st.markdown("### What it does not claim\nIt cannot prove an attack happened. It looks for patterns that might mean "
                "danger. Falls are used as practice examples because real attack recordings don't exist.")
    st.markdown("### Results so far (preliminary, people the system had never seen)")
    st.table(load_results())
    st.markdown("The settings were fixed before testing. Under our pre-set rule, only 'Quietest' met the goal of "
                "3 or fewer check-ins per hour.")
    st.markdown("### What we learned\n"
                "- Wrist heart readings are unreliable during strong movement, so the system currently decides mainly from movement.\n"
                "- Most unnecessary check-ins come from naturally bumpy activities like table soccer and cycling.\n"
                "- This test watch can't measure very hard jolts fully.")
    st.markdown("### Next steps\n"
                "- Use what the person was doing to avoid check-ins during sport.\n"
                "- Add a stress and heart model.\n"
                "- Test on modern smartwatches with real users.")
    st.caption("Early prototype. Numbers are preliminary.")


def main():
    init_state()
    tl = load_timelines()
    sidebar()
    if st.session_state.page == "About this demo":
        about_page()
    else:
        live_page(tl)


main()
