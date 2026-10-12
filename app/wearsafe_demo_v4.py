"""WearSafe demo app v4 — soft visual redesign (layout, styling and text only). Data loading and replay
playback code copied unchanged from app/wearsafe_demo_v3.py. Based on v3 (adds the "heart racing while still" check to the everyday demo; replay from
scripts/m03_v2_demo_replay.py). Based on v2 (early prototype; numbers are preliminary). Copy of app/wearsafe_demo.py plus the
air-pressure option in the fall demo (replay outputs from scripts/m02_demo_replay.py) and an About-page section.

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
PRESSURE_REPLAY = REPO / "results/2026-10-12_M02_demo_replay/replay.joblib"
HEART_REPLAY = REPO / "results/2026-10-12_M03_v2_demo_replay/heart.joblib"
HEART_REPORT = REPO / "reports/M03_v2_sqi_demo_v0.md"
EXTRA_RESULTS = REPO / "results/2026-10-12_M02_extra_sensors/summary.csv"
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

st.set_page_config(page_title="WearSafe", page_icon="🌸", layout="centered")


@st.cache_resource
def load_timelines():
    return joblib.load(TIMELINES)


@st.cache_resource
def load_heart():
    return joblib.load(HEART_REPLAY)


@st.cache_data
def load_heart_table():
    """Reads the side-by-side table from the report file (does not retype numbers)."""
    lines = [l for l in HEART_REPORT.read_text().splitlines() if l.startswith("|")]
    start = next(i for i, l in enumerate(lines) if "Before (old setting)" in l)
    head = [c.strip() for c in lines[start].strip("|").split("|")]
    rows = []
    for l in lines[start + 2:]:
        cells = [c.strip() for c in l.strip("|").split("|")]
        if len(cells) != len(head):
            break
        rows.append(dict(zip(head, cells)))
    return pd.DataFrame(rows)


def heart_events():
    w = load_heart()["windows"]
    return [(float(t), "CHECK", "Your heart is racing while you're still") for t in w.window_end[w.fire]]


@st.cache_resource
def load_pressure():
    return joblib.load(PRESSURE_REPLAY)


@st.cache_data
def load_extra_results():
    """Reads the extra-sensor results file (does not retype numbers)."""
    s = pd.read_csv(EXTRA_RESULTS)
    s = s[s.accelerometer == "e4_clipped"].set_index("sensor_set")
    out = []
    for name, key in (("Movement only", "ACC-only (M01)"), ("Movement + air pressure", "ACC+baro")):
        r = s.loc[key]
        out.append({"Sensors": name, "Falls caught": f"{r.clip_fall_detect_pct:.1f}%",
                    "Normal activity recordings with an unnecessary check-in": f"{r.clip_false_alarm_pct:.1f}%"})
    return pd.DataFrame(out)


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
    s.pressure = qp("pressure", "1") == "1"


def current_recording(tl):
    s = st.session_state
    if s.demo == "Everyday life":
        seg = tl["everyday"][SEGMENTS[s.segment]]
        return seg, seg["decisions"], True
    clip = tl["fall"][CLIPS[s.clip]]
    dec = clip["decisions"]
    if s.pressure:
        rp = load_pressure()[CLIPS[s.clip]]["decisions"].set_index("t_abs")
        dec = dec.copy()
        m = dec.t_abs.isin(rp.index)
        dec["p_motion"] = dec.t_abs.map(rp.score)
        dec["prompt_pressure"] = dec.t_abs.map(rp.prompt).fillna(False).astype(bool)
        dec["lat_pressure"] = 0.0
        dec["risk_pressure"] = np.where(dec.prompt_pressure, "CHECK", "NONE")
        dec["height_change"] = dec.t_abs.map(rp.height_change).fillna(False).astype(bool)
    return clip, dec, False


def reset_playback():
    s = st.session_state
    s.pos, s.alert, s.help = 0, None, None


def add_log(text, t_rec):
    st.session_state.log.insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Recording time": f"{t_rec:.0f} s",
                                    "What happened": text})


def prompt_times(dec, key):
    """Recording second at which each check-in is shown (some settings wait 5 s before asking)."""
    m = dec[f"prompt_{key}"].astype(bool)
    return [(float(t + lat), r) for t, lat, r in zip(dec.t_abs[m], dec[f"lat_{key}"][m], dec[f"risk_{key}"][m])]


def advance(dec, key, extra=()):
    s = st.session_state
    if not s.playing or s.alert or s.help or s.pos >= len(dec) - 1:
        if s.pos >= len(dec) - 1:
            s.playing = False
        return
    step = {"1×": 1, "10×": 10, "60×": 60}[s.speed]
    t_now = dec.t_abs.iloc[s.pos]
    new_pos = min(len(dec) - 1, s.pos + step)
    t_new = dec.t_abs.iloc[new_pos]
    events = [(t, r, None) for t, r in prompt_times(dec, key)] + list(extra)
    for t_show, risk, reason in sorted(events, key=lambda e: e[0]):
        if t_now < t_show <= t_new:
            new_pos = int(np.searchsorted(dec.t_abs.to_numpy(), t_show, side="left"))
            new_pos = min(new_pos, len(dec) - 1)
            s.alert = {"start": time.time(), "risk": risk, "t": t_show, "reason": reason}
            add_log((reason + " — asked “Are you safe?”") if reason else "Sudden movement noticed — asked “Are you safe?”", t_show)
            break
    s.pos = new_pos



CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
html, body, [class*="css"], .stApp, .stMarkdown, button, input, label { font-family: 'Nunito', sans-serif !important; }
.stApp { background: #FFF7F9; color: #3D2C3A; }
.block-container { max-width: 1050px; padding-top: 1.5rem; }
h1, h2, h3, p, li, label, .stMarkdown { color: #3D2C3A; }
.ws-card { background: #fff; border-radius: 16px; box-shadow: 0 4px 18px rgba(216,106,138,0.12); padding: 18px 22px; margin-bottom: 14px; }
.ws-small { font-size: 15px; opacity: 0.8; }
.ws-big { font-size: 22px; font-weight: 700; }
.ws-circle { width: 230px; height: 230px; border-radius: 50%; margin: 6px auto 10px auto; display: flex; flex-direction: column;
             align-items: center; justify-content: center; color: white; box-shadow: 0 8px 28px rgba(61,44,58,0.18); }
.ws-circle .icon { font-size: 64px; line-height: 1; }
.ws-circle .phrase { font-size: 26px; font-weight: 800; margin-top: 8px; text-align: center; }
.ws-reason { text-align: center; font-size: 19px; margin-bottom: 12px; }
.stButton > button { border-radius: 14px; border: none; background: #D86A8A; color: white; font-weight: 700; padding: 0.6rem 1rem; }
.stButton > button:hover { background: #c45878; color: white; }
</style>
"""
PALETTE = {"safe": ("#7FB5A0", "🌿", "You're safe"), "check": ("#F2B880", "🤍", "Checking on you"),
           "help": ("#C8475F", "💗", "Getting help")}
TABS = ["Live demo", "How it works", "Results & honesty"]


def card(title, value, note=""):
    st.markdown(f"<div class='ws-card'><div class='ws-small'>{title}</div><div class='ws-big'>{value}</div>"
                f"<div class='ws-small'>{note}</div></div>", unsafe_allow_html=True)


def status_circle(kind, reason):
    color, icon, phrase = PALETTE[kind]
    st.markdown(f"<div class='ws-circle' style='background:{color}'><div class='icon'>{icon}</div>"
                f"<div class='phrase'>{phrase}</div></div><div class='ws-reason'>{reason}</div>", unsafe_allow_html=True)


def scenario_picker():
    s = st.session_state
    c1, c2 = st.columns(2)
    for col, name, title, line in ((c1, "Everyday life", "🌸 A normal day", "One real person going about their day."),
                                   (c2, "Fall event", "🍃 A sudden fall", "A real recorded fall, and a jog with no fall.")):
        with col:
            st.markdown(f"<div class='ws-card'><div class='ws-big'>{title}</div><div class='ws-small'>{line}</div></div>",
                        unsafe_allow_html=True)
            if st.button("Selected ✓" if s.demo == name else "Choose", key=f"pick_{name}", use_container_width=True):
                if s.demo != name:
                    s.demo = name
                    reset_playback()
                    st.rerun()
    if s.demo == "Everyday life":
        seg = st.selectbox("Part of the day", list(SEGMENTS), index=list(SEGMENTS).index(s.segment))
        if seg != s.segment:
            s.segment = seg
            reset_playback()
            st.rerun()
    else:
        clip = st.selectbox("Recording", list(CLIPS), index=list(CLIPS).index(s.clip))
        if clip != s.clip:
            s.clip = clip
            reset_playback()
            st.rerun()
    b1, b2, b3, b4 = st.columns([1, 1, 1, 2])
    if b1.button("▶ Play", use_container_width=True):
        s.playing = True
    if b2.button("⏸ Pause", use_container_width=True):
        s.playing = False
    if b3.button("↺ Restart", use_container_width=True):
        reset_playback()
        s.playing = True
    s.speed = b4.select_slider("Speed", ["1×", "10×", "60×"], value=s.speed)


def alert_area():
    s = st.session_state
    left = COUNTDOWN_S - (time.time() - s.alert["start"])
    if left <= 0:
        add_log("No answer — your trusted contacts are being alerted (SIMULATION)", s.alert["t"])
        s.help = {"t": s.alert["t"], "when": datetime.now().strftime("%H:%M:%S")}
        s.alert, s.playing = None, False
        st.rerun()
    reason = s.alert.get("reason") or "Sudden movement noticed"
    status_circle("check", reason)
    st.markdown("<div class='ws-card' style='text-align:center'><div style='font-size:42px;font-weight:800'>Are you safe?</div>"
                f"<div class='ws-small'>If you don't answer in {int(np.ceil(left))} s, your trusted contacts will be alerted.</div></div>",
                unsafe_allow_html=True)
    st.progress(max(0.0, min(1.0, left / COUNTDOWN_S)))
    a, b = st.columns(2)
    if a.button("💚  I'm safe", use_container_width=True):
        add_log("You said you were safe", s.alert["t"])
        s.alert = None
        st.rerun()
    if b.button("🆘  Get help now", use_container_width=True):
        add_log("You asked for help (SIMULATION)", s.alert["t"])
        s.help = {"t": s.alert["t"], "when": datetime.now().strftime("%H:%M:%S")}
        s.alert, s.playing = None, False
        st.rerun()


def help_area():
    s = st.session_state
    status_circle("help", "SIMULATION — no real messages are sent")
    st.markdown("<div class='ws-card' style='text-align:center'><div style='font-size:34px;font-weight:800'>Getting help (SIMULATION)</div>"
                "<div class='ws-big' style='margin-top:6px'>Help is on the way. You're not alone.</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='ws-card'><div class='ws-big'>Trusted contacts notified (SIMULATION)</div>"
                    + "".join(f"<div>📱 {c} — message sent (simulated)</div>" for c in CONTACTS)
                    + f"<div style='margin-top:8px'>📍 Location shared (simulated)</div><div>🕒 {s.help['when']}</div></div>",
                    unsafe_allow_html=True)
    with c2:
        timeline()
    if st.button("Back to the demo", use_container_width=True):
        s.help = None
        st.rerun()


def timeline():
    s = st.session_state
    items = "".join(f"<div>• {e['Time']} — {e['What happened']}</div>" for e in s.log) or "<div class='ws-small'>Nothing yet.</div>"
    st.markdown(f"<div class='ws-card'><div class='ws-big'>What happened</div>{items}</div>", unsafe_allow_html=True)


def live_tab(tl):
    s = st.session_state
    scenario_picker()
    rec, dec, has_heart = current_recording(tl)
    use_pressure = s.demo == "Fall event" and s.pressure
    key = "pressure" if use_pressure else SETTINGS[s.setting][0]
    advance(dec, key, heart_events() if s.demo == "Everyday life" else ())
    row = dec.iloc[s.pos]
    t = float(row.t_abs)
    main_area = st.container()
    with main_area:
        if s.help:
            help_area()
            return
        if s.alert:
            alert_area()
        else:
            status_circle("safe", "Watching quietly in the background")
    ctx = str(row.context)
    moving = "Sudden movement noticed" if (s.alert and not s.alert.get("reason")) else (
        "Calm" if ctx in ("stationary", "low_activity") else "Moving")
    if s.demo == "Everyday life":
        hw = load_heart()["windows"]
        past = hw[hw.window_end <= t]
        stt = past.status.iloc[-1] if len(past) else "moving"
        heart = {"moving": "Can't check while moving", "calm": "Calm", "racing": "Racing while still"}[stt]
        air = "Not on this watch"
    else:
        heart = "Not in this recording"
        air = ("Height change noticed" if bool(row.height_change) else "No height change") if use_pressure else "Switched off"
    c = st.columns(3)
    with c[0]:
        card("Movement", moving, DOING.get(ctx, "Not sure yet"))
    with c[1]:
        card("Heart (when still)", heart)
    with c[2]:
        card("Air pressure", air)
    with st.expander("See what the watch senses"):
        p1, p2, p3 = st.empty(), st.empty(), st.empty()
        mag = rec["mag"] / 9.80665
        start = rec["seg"][0] if s.demo == "Everyday life" else 0
        i1 = int((t - start) * 32)
        i0 = max(0, i1 - 60 * 32)
        x = np.arange(i0, i1)[::4] / 32 + start
        p1.line_chart(pd.DataFrame({"seconds": x, "Wrist movement": mag[i0:i1][::4]}).set_index("seconds"), height=180)
        if has_heart:
            hr = rec["hr"]
            hr = hr[(hr.end_abs <= t) & (hr.end_abs > t - 600)]
            if len(hr):
                p2.line_chart(pd.DataFrame({"seconds": hr.end_abs, "Heart rate": hr.hr_mean}).set_index("seconds"), height=180)
            else:
                p2.info("Waiting for enough heart data…")
        else:
            p2.info("No heart sensor in this recording.")
        if use_pressure:
            pres = load_pressure()[CLIPS[s.clip]]["pressure_hpa"]
            n = int(min(len(pres), max(1, t * 10)))
            p3.line_chart(pd.DataFrame({"seconds": np.arange(n) / 10, "Air pressure change": pres[:n] - pres[0]}).set_index("seconds"),
                          height=160)
        else:
            p3.empty()
    with st.expander("Settings"):
        locked = use_pressure
        setting = st.radio("Alert sensitivity", list(SETTINGS), index=list(SETTINGS).index(s.setting),
                           captions=[v[1] for v in SETTINGS.values()], disabled=locked)
        if locked:
            st.caption("Alert settings are not yet tuned for the air-pressure sensor.")
        if setting != s.setting:
            s.setting = setting
            reset_playback()
            st.rerun()
        if s.demo == "Fall event":
            pr = st.toggle("Use air-pressure sensor (if the watch has one)", value=s.pressure)
            if pr != s.pressure:
                s.pressure = pr
                reset_playback()
                st.rerun()
    st.progress(min(1.0, s.pos / max(1, len(dec) - 1)), text=f"Playback: {t:.0f} s")
    timeline()
    if s.playing or s.alert:
        time.sleep(1)
        st.rerun()


def how_tab():
    steps = [("⌚", "Your watch notices sudden movement or a racing heart"),
             ("🤔", "It checks: is this normal for what you're doing?"),
             ("💬", "It asks you: Are you safe?"),
             ("📱", "No answer? It alerts your trusted contacts.")]
    cols = st.columns(4)
    for i, (col, (icon, text)) in enumerate(zip(cols, steps), 1):
        col.markdown(f"<div class='ws-card' style='text-align:center;min-height:190px'><div style='font-size:44px'>{icon}</div>"
                     f"<div class='ws-big'>{i}</div><div>{text}</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='ws-card'><div class='ws-big'>What it can't do</div>"
                "<div>• It cannot prove an attack happened. It looks for patterns that might mean danger.</div>"
                "<div>• Falls are used as practice examples because real attack recordings don't exist.</div>"
                "<div>• The heart check works only when the wrist is still.</div></div>", unsafe_allow_html=True)


def results_tab():
    st.markdown("<div class='ws-card'><div class='ws-big'>Movement check — people the system had never seen</div>"
                "<div class='ws-small'>The settings were fixed before testing. Under our pre-set rule, only 'Quietest' met the "
                "goal of 3 or fewer check-ins per hour.</div></div>", unsafe_allow_html=True)
    st.table(load_results())
    st.markdown("<div class='ws-card'><div class='ws-big'>Air pressure (early result)</div>"
                "<div>• Air pressure helps because a fall usually means dropping to the ground.</div>"
                "<div>• Not every dangerous situation involves falling — someone attacked while standing may show no height change. "
                "So air pressure should add confidence, not be required.</div>"
                "<div>• Not yet tested on everyday life: the everyday-life watch has no air-pressure sensor. Stairs, lifts and "
                "weather also change air pressure.</div>"
                "<div>• This sensor was picked after comparing several options, so the result is promising but needs confirmation.</div>"
                "</div>", unsafe_allow_html=True)
    st.table(load_extra_results())
    st.markdown("<div class='ws-card'><div class='ws-big'>Heart racing while still (early result)</div>"
                "<div>• Works only when the wrist is still, because the heart reading is unreliable during movement.</div>"
                "<div>• Lab stress (a speech and maths test) is not real danger; more testing needed.</div>"
                "<div>• Skin sweat reacts to many everyday movements, so it is not useful for quick checks, but it clearly showed "
                "stress — a possible future background signal.</div></div>", unsafe_allow_html=True)
    st.table(load_heart_table())
    st.caption("Early prototype. Numbers are preliminary.")


def main():
    init_state()
    s = st.session_state
    if "tab" not in s:
        s.tab = {"how": "How it works", "results": "Results & honesty"}.get(qp("tab", ""), "Live demo")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("<div style='font-size:44px;font-weight:800;color:#D86A8A'>WearSafe</div>"
                "<div style='font-size:20px;margin-bottom:10px'>Your watch quietly looks out for you.</div>", unsafe_allow_html=True)
    tab = st.segmented_control("Section", TABS, default=s.tab, key="tab_ctl", label_visibility="collapsed")
    s.tab = tab or s.tab
    tl = load_timelines()
    if s.tab == "Live demo":
        live_tab(tl)
    elif s.tab == "How it works":
        how_tab()
    else:
        results_tab()


main()
