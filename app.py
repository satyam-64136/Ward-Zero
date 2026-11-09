import logging
import math
import os
import sqlite3
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from risk import assess

DB = os.environ.get("WARDZERO_DB", "wardzero.db")
ESC = int(os.environ.get("ESCALATION_SECONDS", "30"))  # seconds per escalation step (short for demo)
NOTE_WINDOW = int(os.environ.get("NOTE_WINDOW_SECONDS", "1800"))  # notes older than this stop influencing risk
SIGNAL_LOSS = int(os.environ.get("SIGNAL_LOSS_SECONDS", "45"))  # silence longer than this = patient not being monitored
SCENARIOS = ("stable", "deteriorating")
MAX_BATCH = 1000
LADDER = ["Caregiver (Priya)", "Family (Rahul)", "Doctor (Dr. Mehta)"]
CHANNELS = ["Push notification", "SMS", "Voice call"]  # one per rung; delivery is SIMULATED (logged, nothing is sent)
ORDER = {"Low": 0, "Medium": 1, "High": 2}
SIM = {"scenario": "stable", "offline": False, "epoch": 0}  # epoch counts demo resets so the simulator can start fresh
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
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, ts REAL, level TEXT, reason TEXT, status TEXT, ack_by TEXT, ack_ts REAL, esc INTEGER DEFAULT 0, kind TEXT DEFAULT 'risk');
        CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, ts REAL, name TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, alert_id INTEGER, step INTEGER, ts REAL, recipient TEXT, channel TEXT, message TEXT, UNIQUE(alert_id, step));
        """)
        if "kind" not in {r[1] for r in c.execute("PRAGMA table_info(alerts)")}:  # database created by v0.3.0 or older
            c.execute("ALTER TABLE alerts ADD COLUMN kind TEXT DEFAULT 'risk'")

def risk_now(c):
    rs = [dict(r) for r in c.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 24")][::-1]
    ns = [r["text"] for r in c.execute("SELECT text FROM notes WHERE ts > ? ORDER BY ts DESC LIMIT 10", (time.time() - NOTE_WINDOW,))]
    return assess(rs, ns)

def maybe_alert(c, risk):
    if risk["level"] == "Low":
        return
    last = c.execute("SELECT * FROM alerts WHERE kind='risk' ORDER BY id DESC LIMIT 1").fetchone()
    now = time.time()
    if last and now - last["ts"] < 300 and ORDER[last["level"]] >= ORDER[risk["level"]]:
        return
    # A new alert supersedes still-open older ones and keeps the ORIGINAL alarm time,
    # so escalation timing and "time to acknowledge" are measured from the first alarm.
    first = c.execute("SELECT MIN(ts), MAX(esc) FROM alerts WHERE status='open' AND kind='risk'").fetchone()
    c.execute("UPDATE alerts SET status='superseded' WHERE status='open' AND kind='risk'")
    c.execute("INSERT INTO alerts(ts,level,reason,status,esc,kind) VALUES(?,?,?,'open',?,'risk')",
              (first[0] or now, risk["level"], "; ".join(risk["reasons"][:4]), first[1] or 0))

def watch_signal(c, now):
    """Silent failure is the worst failure: no readings for SIGNAL_LOSS seconds raises its own alert,
    and the alert closes by itself once data flows again (e.g. after the offline buffer is flushed)."""
    latest = c.execute("SELECT MAX(ts) FROM readings").fetchone()[0]
    if latest is None:  # nothing has ever arrived, so there is nothing to lose yet
        return
    if now - latest <= SIGNAL_LOSS:
        c.execute("UPDATE alerts SET status='resolved', ack_by='System', ack_ts=? WHERE kind='signal' AND status='open'", (now,))
        return
    prev = c.execute("SELECT MAX(ts) FROM alerts WHERE kind='signal'").fetchone()[0]
    if prev is None or prev < latest:  # one alert per silence, not one per second
        c.execute("INSERT INTO alerts(ts,level,reason,status,esc,kind) VALUES(?,?,?,'open',0,'signal')",
                  (now, "Medium", f"No readings for over {SIGNAL_LOSS}s: the patient is not being monitored"))

def notice(a, step):
    """Hedged, human-readable text for one escalation message (simulated delivery)."""
    if a["kind"] == "signal":
        return f"Ward Zero: no data from Bed 1's device for over {SIGNAL_LOSS}s, so the patient is not being monitored. Please check the patient and the device."
    return f"Ward Zero: possible deterioration for Bed 1, {a['level']} risk. {a['reason']}. Please check the patient and acknowledge."

def escalate(c, now):
    """Move every open alert along the ladder by the server clock and log one notification per rung.
    Idempotent (UNIQUE alert_id+step), so it is safe from the background thread, /api/state and several processes."""
    for a in c.execute("SELECT * FROM alerts WHERE status='open'").fetchall():
        step = max(min(int((now - a["ts"]) // ESC), len(LADDER) - 1), a["esc"])  # never step back down
        if step != a["esc"]:
            c.execute("UPDATE alerts SET esc=? WHERE id=?", (step, a["id"]))
        for s in range(step + 1):
            c.execute("INSERT OR IGNORE INTO notifications(alert_id,step,ts,recipient,channel,message) VALUES(?,?,?,?,?,?)",
                      (a["id"], s, now, LADDER[s], CHANNELS[s], notice(a, s)))

def cycle(now=None):
    """One supervision pass. Takes the write lock up front so the check-then-insert steps cannot interleave."""
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        now = now or time.time()
        watch_signal(c, now)
        escalate(c, now)

def _supervise():
    while True:
        try:
            cycle()
        except Exception:  # the supervisor must outlive any single failure
            logging.getLogger("wardzero").exception("supervisor pass failed")
        time.sleep(1)

def start_supervisor():
    threading.Thread(target=_supervise, daemon=True, name="ward-supervisor").start()

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
        c.execute("BEGIN IMMEDIATE")  # lock first: the alert check below is check-then-insert
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
        c.execute("BEGIN IMMEDIATE")
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
        SIM.update({k: d[k] for k in ("scenario", "offline") if k in d})
    return jsonify(SIM)

@app.post("/api/reset")
def reset():
    """Demo only: wipe all synthetic data and return to a calm, online patient."""
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        for t in ("readings", "notes", "alerts", "checkins", "notifications"):  # fixed names, no user input
            c.execute(f"DELETE FROM {t}")  # nosec B608
    SIM.update(scenario="stable", offline=False, epoch=SIM["epoch"] + 1)
    return jsonify(SIM)

@app.get("/api/health")
def health():
    with db() as c:
        n = c.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    return jsonify(status="ok", readings=n)

@app.get("/api/notifications")
def notifications():
    with db() as c:
        return jsonify(notifications=[dict(r) for r in c.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 50")])

@app.get("/api/state")
def state():
    now = time.time()
    cycle(now)  # the supervisor thread is authoritative; this keeps the snapshot current even without it
    with db() as c:
        rs = [dict(r) for r in c.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 40")][::-1]
        return jsonify(
            now=now, readings=rs, risk=risk_now(c), sim=SIM, ladder=LADDER, esc_seconds=ESC, signal_loss_seconds=SIGNAL_LOSS,
            age=(now - rs[-1]["ts"]) if rs else None,
            alerts=[dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 6")],
            notifications=[dict(r) for r in c.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 18")],
            notes=[dict(r) for r in c.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 4")],
            checkin=(dict(r) if (r := c.execute("SELECT * FROM checkins ORDER BY id DESC LIMIT 1").fetchone()) else None))

init()
if os.environ.get("WARDZERO_WORKER", "1") != "0":  # tests switch it off and call cycle() directly
    start_supervisor()
if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # no log line for every dashboard refresh
    # localhost-only by default (patient data!). Set HOST=0.0.0.0 deliberately to expose on a LAN.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
