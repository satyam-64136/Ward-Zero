"""Generates the architecture diagrams in docs/images/*.svg (run: python scripts/make_diagrams.py)."""
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
INK, MU, LINE, BG = "#0e141b", "#566170", "#c9d2dc", "#ffffff"
C = {"dev": ("#eaf4f7", "#17677d"), "plat": ("#f3f5f7", "#7b8794"), "risk": ("#fff6e6", "#9a5a08"),
     "bad": ("#fdeeec", "#c0352b"), "ok": ("#e8f5ee", "#1b8450"), "ui": ("#eef0fb", "#4b5bb0")}
F = 'font-family="Helvetica, Arial, sans-serif"'

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def text(x, y, s, size=14, w=400, fill=INK, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{anchor}" {F}>{esc(s)}</text>'
def box(x, y, w, h, title, lines=(), kind="plat", tag=None):
    f, s = C[kind]
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{f}" stroke="{s}" stroke-width="1.5"/>'
    o += text(x + 16, y + 28, title, 16, 700)
    if tag: o += text(x + w - 16, y + 28, tag, 12, 500, MU, "end")
    for i, line in enumerate(lines): o += text(x + 16, y + 54 + i * 20, line, 13, 400, MU)
    return o
def arrow(x1, y1, x2, y2, label=None, color=MU, dash=False, lx=None, ly=None):
    o = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.75" marker-end="url(#a)"' + (' stroke-dasharray="6 5"' if dash else "") + "/>"
    if isinstance(lx, tuple):
        lx, ly = lx
    if label:
        mx, my = lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2
        tw = len(label) * 6.6 + 14
        o += f'<rect x="{mx - tw / 2}" y="{my - 11}" width="{tw}" height="20" rx="6" fill="{BG}"/>' + text(mx, my + 4, label, 12, 500, INK, "middle")
    return o
def lane(x, w, h, title):
    return f'<rect x="{x}" y="64" width="{w}" height="{h}" rx="16" fill="#fafbfc" stroke="{LINE}" stroke-dasharray="3 5"/>' + text(x + 18, 90, title, 13, 600, MU)
def svg(name, h, body, title):
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {h}" width="1200" height="{h}" role="img" aria-label="{esc(title)}">'
         f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{MU}"/></marker></defs>'
         f'<rect width="1200" height="{h}" rx="18" fill="{BG}" stroke="{LINE}"/>' + text(32, 42, title, 20, 700) + body + "</svg>")
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(s)

# 1. System architecture
b = lane(24, 340, 560, "Device layer (simulated)") + lane(384, 436, 560, "Platform layer (Flask + SQLite)") + lane(840, 336, 560, "Presentation layer (browser)")
b += box(48, 112, 292, 112, "Sensor simulator", ["Virtual HR, SpO2, BP, temperature", "Scenarios: stable, deteriorating", "One reading per second"], "dev", "simulator.py")
b += box(48, 300, 292, 112, "Offline buffer", ["Atomic writes, capped at 5,000", "Flushed in chunks of 200", "Survives restarts and power loss"], "dev", "queue.json")
b += box(408, 112, 388, 132, "REST API", ["POST /api/readings  validate, dedupe by cid", "GET /api/state  one snapshot for the UI", "POST /api/notes  /checkin  /alerts/id/ack", "GET /api/health  liveness"], "plat", "app.py")
b += box(408, 290, 180, 118, "Risk engine", ["Vital bands + trend", "+ caregiver notes", "Explainable reasons"], "risk", "risk.py")
b += box(616, 290, 180, 118, "Alert manager", ["Create, supersede", "Escalate on timer", "Acknowledge"], "bad", "app.py")
b += box(408, 454, 388, 100, "SQLite (WAL mode)", ["readings, notes, alerts, checkins", "Idempotent inserts, lock timeout"], "plat", "wardzero.db")
b += box(864, 112, 288, 132, "Dashboard", ["Polls /api/state every second", "Sends acknowledge, notes, controls", "Vitals, ECG trace, risk reasons"], "ui", "templates/index.html")
b += box(864, 300, 288, 112, "Caregiver", ["Acknowledges alerts", "Checks in, adds notes (EN / HI)", "Controls the demo scenario"], "ok")
b += arrow(340, 168, 408, 168, None, INK) + arrow(194, 300, 194, 226, "offline: store, then flush", MU, True, 194, 262)
b += arrow(602, 244, 498, 290, "score", INK, lx=(548, 262)) + arrow(702, 244, 706, 290, "alerts", INK, lx=(708, 262))
b += arrow(602, 408, 602, 454, "read / write", INK) + arrow(864, 160, 796, 160, None, INK)
b += arrow(1008, 300, 1008, 244, "uses", INK) + arrow(796, 214, 864, 214, None, INK)
svg("architecture.svg", 640, b, "Ward Zero system architecture")

# 2. Data flow (pipeline)
steps = [("Sense", "dev", ["Simulator emits one", "reading per second:", "hr, spo2, sbp, dbp, temp"], "reading"),
         ("Understand", "plat", ["Validate and store the", "reading, then score the", "four vitals against bands"], "score + reasons"),
         ("Predict", "risk", ["Compare the first and last", "6 readings of a 24-reading", "window for a worsening trend"], "early-warning flag"),
         ("Alert", "bad", ["Medium or High raises one", "alert. A higher level", "supersedes an open one"], "alert record"),
         ("Respond", "ok", ["Caregiver, then family, then", "doctor on a timer. An", "acknowledgement closes it"], "ack + response time")]
b = ""
for i, (t, k, ls, art) in enumerate(steps):
    x = 28 + i * 232
    b += box(x, 84, 204, 150, t, ls, k)
    b += f'<rect x="{x}" y="250" width="204" height="44" rx="10" fill="#fff" stroke="{LINE}"/>' + text(x + 102, 277, art, 13, 600, INK, "middle")
    b += arrow(x + 102, 234, x + 102, 250, None, MU)
    if i < 4: b += arrow(x + 204, 159, x + 232, 159, None, INK)
b += arrow(1066, 316, 366, 316, "acknowledgement stops escalation; closes the alert", MU, True, 716, 316)
b += text(32, 350, "Every stage is visible live in the dashboard's pipeline strip.", 13, 400, MU)
svg("data-flow.svg", 372, b, "Sense, Understand, Predict, Alert, Respond")

# 3. Risk engine
b = box(28, 72, 372, 300, "1. Vital bands (0 to 3 points each)", ["SpO2 (%): 91 or less = 3; 92-93 = 2; 94-95 = 1", "Heart rate: 40 or less, 131 or more = 3;", "111-130 = 2; 41-50, 91-110 = 1", "Systolic BP: 90 or less, 220 or more = 3;", "91-100 = 2; 101-110 = 1", "Temperature: 35 or less = 3; 39.1 or more = 2;", "35.1-36, 38.1-39 = 1", "", "NEWS2-inspired. Illustrative, not validated."], "dev")
b += box(428, 72, 372, 140, "2. Trend (window of 24 readings)", ["SpO2 fell by 3 or more:  +2", "Heart rate rose by 15 or more:  +1", "Systolic BP fell by 15 or more:  +1", "Temperature rose by 0.8 or more:  +1"], "risk")
b += box(428, 232, 372, 140, "3. Caregiver notes (last 30 min)", ["English and Hindi keyword groups:", "breathless / saans, chest pain, dizzy /", "chakkar, fever / bukhar, vomiting / ulti,", "weakness. +1 per group, at most +3"], "plat")
b += box(836, 72, 336, 168, "Total score and level", ["High    score 6 or more", "Medium  score 3 to 5, or any single", "              vital scoring 3", "Low     otherwise", "Early warning (trend 2+) lifts Low to Medium"], "bad")
b += box(836, 262, 336, 110, "Output", ["Level + score", "Reasons list, e.g. 'SpO2 88.9% (+3)'", "Early-warning flag"], "ok")
b += text(414, 148, "+", 22, 700, INK, "middle") + text(614, 228, "+", 22, 700, INK, "middle")
b += arrow(800, 142, 836, 142, "sum", INK, lx=(818, 124)) + arrow(800, 302, 836, 215, None, INK) + arrow(1004, 240, 1004, 262, None, INK)
b += text(32, 410, "Rules were chosen over a black-box model so every alert can state exactly why it was raised.", 13, 400, MU)
svg("risk-engine.svg", 432, b, "Risk engine: bands, trend, notes")

# 4. Escalation
b = text(32, 84, "Elapsed time since the first alarm (step length = ESCALATION_SECONDS, default 30 s)", 13, 400, MU)
b += f'<line x1="60" y1="132" x2="1140" y2="132" stroke="{LINE}" stroke-width="2"/>'
for i, (t, who, k) in enumerate([("0 s", "Caregiver", "ok"), ("30 s", "Family", "risk"), ("60 s", "Doctor", "bad")]):
    x = 60 + i * 380
    b += f'<circle cx="{x}" cy="132" r="9" fill="{C[k][1]}"/>' + text(x, 112, t, 14, 700, INK, "middle")
    b += box(x - 90 if i < 2 else x - 150, 160, 240 if i < 2 else 240, 96, who + " notified", ["Alert shown with a live", "countdown to the next step"] if i < 2 else ["Final rung: stays open", "until someone acknowledges"], k)
b += box(60, 290, 520, 96, "Acknowledge", ["A caregiver taps Acknowledge on the dashboard.", "The alert closes and the response time is recorded."], "ok")
b += box(620, 290, 520, 96, "Supersede rule", ["A higher-level alert replaces an open lower one.", "It keeps the original alarm time and ladder position."], "plat")
svg("escalation.svg", 410, b, "Alert escalation ladder")

# 5. Resilience
cols = [("Simulator", 150), ("Disk buffer (queue.json)", 600), ("API + database", 1040)]
b = ""
for n, x in cols:
    b += f'<rect x="{x - 130}" y="64" width="260" height="40" rx="10" fill="{C["plat"][0]}" stroke="{C["plat"][1]}"/>' + text(x, 89, n, 14, 700, INK, "middle")
    b += f'<line x1="{x}" y1="104" x2="{x}" y2="470" stroke="{LINE}" stroke-dasharray="4 5"/>'
rows = [(136, "1", "Online: send each reading", 150, 1040, INK, "POST /api/readings"),
        (196, "2", "Network cut: append to buffer", 150, 600, "#c0352b", "atomic write"),
        (256, "3", "Dashboard shows 'No signal, buffering'", None, None, None, None),
        (316, "4", "Restored: flush oldest first, 200 at a time", 600, 1040, "#1b8450", "chunked POST"),
        (376, "5", "Validate, dedupe by cid, re-score by timestamp", None, None, None, None),
        (436, "6", "Buffer clears only after a 200 response", 1040, 600, "#1b8450", "ok")]
for y, n, label, x1, x2, col, al in rows:
    b += f'<circle cx="60" cy="{y}" r="13" fill="{INK}"/>' + text(60, y + 5, n, 13, 700, "#fff", "middle")
    if x1: b += arrow(x1, y, x2, y, al, col, lx=(x1 + x2) / 2, ly=y - 16)
    b += text(90 if not x1 else (x1 + x2) / 2, y + 22 if x1 else y + 5, label, 13, 500, MU if x1 else INK, "middle" if x1 else "start")
svg("resilience.svg", 500, b, "Offline buffering and recovery")
print("diagrams written to", os.path.abspath(OUT))
