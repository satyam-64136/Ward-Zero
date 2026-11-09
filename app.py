import math
import os
import sqlite3
import time

from flask import Flask, jsonify, request, send_from_directory

from risk import assess

DB = os.environ.get("WARDZERO_DB", "wardzero.db")
ESC = int(os.environ.get("ESCALATION_SECONDS", "30"))  # seconds per escalation step (short for demo)
NOTE_WINDOW = int(os.environ.get("NOTE_WINDOW_SECONDS", "1800"))  # notes older than this stop influencing risk
SCENARIOS = ("stable", "deteriorating")
MAX_BATCH = 1000
LADDER = ["Caregiver (Priya)", "Family (Rahul)", "Doctor (Dr. Mehta)"]
ORDER = {"Low": 0, "Medium": 1, "High": 2}
SIM = {"scenario": "stable", "offline": False}
app = Flask(__name__)

LIMITS = dict(hr=(20, 250), spo2=(50, 100), sbp=(40, 300), dbp=(20, 200), temp=(30, 45))

def clean(x):
    """Validate one reading; returns a tuple or None. Bad data must never poison the buffer or crash scoring."""
    try:
        v = {k: float(x[k]) for k in LIMITS}
        ts, cid = float(x["ts"]), str(x["cid"])[:64]
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v[k]) and lo <= v[k] <= hi for k, (lo, hi) in LIMITS.items()):
        return None
    if not math.isfinite(ts) or ts > time.time() + 300:  # a far-future clock would pin "latest reading" forever
        return None
    return (cid, ts, v["hr"], v["spo2"], v["sbp"], v["dbp"], v["temp"])

def body():
    """JSON object body, or {} for anything else (never a 500 from a malformed client)."""
    d = request.get_json(force=True, silent=True)
    return d if isinstance(d, dict) else {}

def db():
    c = sqlite3.connect(DB, timeout=10)  # wait instead of "database is locked" under concurrent requests
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, cid TEXT UNIQUE, ts REAL, hr REAL, spo2 REAL, sbp REAL, dbp REAL, temp REAL);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, ts REAL, text TEXT);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, ts REAL, level TEXT, reason TEXT, status TEXT, ack_by TEXT, ack_ts REAL, esc INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, ts REAL, name TEXT);
        """)

def risk_now(c):
    rs = [dict(r) for r in c.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 24")][::-1]
    ns = [r["text"] for r in c.execute("SELECT text FROM notes WHERE ts > ? ORDER BY ts DESC LIMIT 10", (time.time() - NOTE_WINDOW,))]
    return assess(rs, ns)

def maybe_alert(c, risk):
    if risk["level"] == "Low":
        return
    last = c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 1").fetchone()
    now = time.time()
    if last and now - last["ts"] < 300 and ORDER[last["level"]] >= ORDER[risk["level"]]:
        return
    # A new alert supersedes still-open older ones and keeps the ORIGINAL alarm time,
    # so escalation timing and "time to acknowledge" are measured from the first alarm.
    first = c.execute("SELECT MIN(ts), MAX(esc) FROM alerts WHERE status='open'").fetchone()
    c.execute("UPDATE alerts SET status='superseded' WHERE status='open'")
    c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,'open',?)",
              (first[0] or now, risk["level"], "; ".join(risk["reasons"][:4]), first[1] or 0))

@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"  # patient data must not be cached
    return resp

@app.get("/")
def index():
    return send_from_directory("templates", "index.html")  # served as-is (no Jinja parsing of JS)

@app.post("/api/readings")
def readings():
    data = request.get_json(force=True)
    items = data if isinstance(data, list) else [data]
    if len(items) > MAX_BATCH:
        return jsonify(error=f"max {MAX_BATCH} readings per request"), 413
    n = bad = 0
    with db() as c:
        for x in items:  # idempotent: duplicate cid (retries after outage) are ignored
            row = clean(x) if isinstance(x, dict) else None
            if row is None:
                bad += 1  # rejected, but the batch still succeeds so the device buffer can clear
                continue
            n += c.execute("INSERT OR IGNORE INTO readings(cid,ts,hr,spo2,sbp,dbp,temp) VALUES(?,?,?,?,?,?,?)", row).rowcount
        risk = risk_now(c)
        maybe_alert(c, risk)
    return jsonify(accepted=n, rejected=bad, risk=risk)

@app.post("/api/notes")
def notes():
    t = str(body().get("text") or "").strip()[:500]
    with db() as c:
        if t:
            c.execute("INSERT INTO notes(ts,text) VALUES(?,?)", (time.time(), t))
        maybe_alert(c, risk_now(c))
    return jsonify(ok=True)

@app.post("/api/alerts/<int:aid>/ack")
def ack(aid):
    by = str(body().get("by") or "Caregiver")[:40]
    with db() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            return jsonify(error="alert not found"), 404
        c.execute("UPDATE alerts SET status='acknowledged', ack_by=?, ack_ts=? WHERE id=? AND status='open'",
                  (by, time.time(), aid))
    return jsonify(ok=True)

@app.post("/api/checkin")
def checkin():
    name = str(body().get("name") or "Caregiver")[:40]
    with db() as c:
        c.execute("INSERT INTO checkins(ts,name) VALUES(?,?)", (time.time(), name))
    return jsonify(ok=True)

@app.route("/api/sim", methods=["GET", "POST"])
def sim():
    if request.method == "POST":
        d = body()
        if d.get("scenario", "stable") not in SCENARIOS or not isinstance(d.get("offline", False), bool):
            return jsonify(error="invalid scenario/offline value"), 400
        SIM.update({k: d[k] for k in SIM if k in d})
    return jsonify(SIM)

@app.get("/api/health")
def health():
    with db() as c:
        n = c.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    return jsonify(status="ok", readings=n)

@app.get("/api/state")
def state():
    now = time.time()
    with db() as c:
        for a in c.execute("SELECT * FROM alerts WHERE status='open'").fetchall():
            step = min(int((now - a["ts"]) // ESC), len(LADDER) - 1)
            step = max(step, a["esc"])  # never step back down
            if step != a["esc"]:
                c.execute("UPDATE alerts SET esc=? WHERE id=?", (step, a["id"]))
        rs = [dict(r) for r in c.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 40")][::-1]
        return jsonify(
            now=now, readings=rs, risk=risk_now(c), sim=SIM, ladder=LADDER, esc_seconds=ESC,
            age=(now - rs[-1]["ts"]) if rs else None,
            alerts=[dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 6")],
            notes=[dict(r) for r in c.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 4")],
            checkin=(dict(r) if (r := c.execute("SELECT * FROM checkins ORDER BY id DESC LIMIT 1").fetchone()) else None))

init()
if __name__ == "__main__":
    # localhost-only by default (patient data!). Set HOST=0.0.0.0 deliberately to expose on a LAN.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
