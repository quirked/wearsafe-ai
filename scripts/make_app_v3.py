from pathlib import Path
src = Path("app/wearsafe_demo_v2.py").read_text()
s = src
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
rep('"""WearSafe AI demo app v2', '"""WearSafe AI demo app v3 (adds the "heart racing while still" check to the everyday demo; replay from\nscripts/m03_v2_demo_replay.py). Based on v2')
rep('PRESSURE_REPLAY = REPO / "results/2026-10-12_M02_demo_replay/replay.joblib"\n',
    'PRESSURE_REPLAY = REPO / "results/2026-10-12_M02_demo_replay/replay.joblib"\nHEART_REPLAY = REPO / "results/2026-10-12_M03_v2_demo_replay/heart.joblib"\nHEART_REPORT = REPO / "reports/M03_v2_sqi_demo_v0.md"\n')
rep('''@st.cache_resource
def load_pressure():''', '''@st.cache_resource
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
def load_pressure():''')
rep('''def advance(dec, key):''', '''def advance(dec, key, extra=()):''')
rep('''    for t_show, risk in prompt_times(dec, key):
        if t_now < t_show <= t_new:''', '''    events = [(t, r, None) for t, r in prompt_times(dec, key)] + list(extra)
    for t_show, risk, reason in sorted(events, key=lambda e: e[0]):
        if t_now < t_show <= t_new:''')
rep('''            s.alert = {"start": time.time(), "risk": risk, "t": t_show}
            add_log("Sudden movement noticed — asked “Are you safe?”", t_show)''', '''            s.alert = {"start": time.time(), "risk": risk, "t": t_show, "reason": reason}
            add_log((reason + " — asked “Are you safe?”") if reason else "Sudden movement noticed — asked “Are you safe?”", t_show)''')
rep('''        f"<div style='font-size:56px;font-weight:800;margin:6px 0'>Are you safe?</div>"''', '''        f"<div style='font-size:56px;font-weight:800;margin:6px 0'>Are you safe?</div>"
        + (f"<div style='font-size:22px;margin-bottom:6px'>{s.alert['reason']}</div>" if s.alert.get("reason") else "")
        + ""''')
rep('''    advance(dec, key)''', '''    advance(dec, key, heart_events() if s.demo == "Everyday life" else ())''')
rep('''        st.caption("Air pressure: not available on this watch — using movement only.")''', '''        st.caption("Air pressure: not available on this watch — using movement only.")
        hw = load_heart()["windows"]
        past = hw[hw.window_end <= t]
        stt = past.status.iloc[-1] if len(past) else "moving"
        txt = {"moving": "Can't check now (moving)", "calm": "Calm",
               "racing": "Heart racing while still — checking on you"}[stt]
        st.markdown(f"**Heart check (when still):** {txt}")''')
rep('''                   f"This recording: **{rec['label'].split(': ', 1)[-1]}**. This test watch can't measure very hard jolts fully.")''',
    '''                   f"This recording: **{rec['label'].split(': ', 1)[-1]}**. This test watch can't measure very hard jolts fully.")
        st.caption("Heart check: not available in this recording.")''')
rep('''    st.markdown("### Extra sensor test (early result)")''', '''    st.markdown("### Second safety check: heart racing while still (early result)")
    st.table(load_heart_table())
    st.markdown("- Works only when the wrist is still, because the heart reading is unreliable during movement.\\n"
                "- Lab stress (a speech and maths test) is not real danger; more testing needed.")
    st.markdown("### Extra sensor test (early result)")''')
Path("app/wearsafe_demo_v3.py").write_text(s)
print("v3 written")
