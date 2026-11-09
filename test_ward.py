"""Run: python -m unittest -v   (no extra dependencies)"""
import os
import sqlite3
import tempfile
import time
import unittest

os.environ["WARDZERO_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["WARDZERO_WORKER"] = "0"  # tests call W.cycle() themselves; no background thread
import app as W
from risk import assess


def reading(cid, ts=None, **kw):
    d = dict(cid=cid, ts=ts or time.time(), hr=76, spo2=97, sbp=120, dbp=78, temp=36.8); d.update(kw); return d

class Ward(unittest.TestCase):
    def setUp(self):
        with W.db() as c:
            for t in ("readings", "notes", "alerts", "checkins", "notifications"): c.execute(f"DELETE FROM {t}")
        W.SIM.update(scenario="stable", offline=False)
        W.ESC, W.SIGNAL_LOSS = 30, 45  # tests may change these; never leak into the next test
        self.c = W.app.test_client()

    def test_band_has_no_gaps(self):
        r = lambda s: [dict(hr=76, spo2=s, sbp=120, temp=36.8)]
        self.assertGreaterEqual(assess(r(91.5), [])["score"], 2)
        self.assertEqual(assess(r(93.5), [])["score"], 1)

    def test_bad_reading_rejected_batch_survives(self):
        j = self.c.post("/api/readings", json=[reading("a", hr="abc"), reading("b"), reading("c", spo2=140)]).get_json()
        self.assertEqual((j["accepted"], j["rejected"]), (1, 2))

    def test_duplicate_cid_ignored(self):
        self.c.post("/api/readings", json=reading("x")); j = self.c.post("/api/readings", json=reading("x")).get_json()
        self.assertEqual(j["accepted"], 0)

    def test_invalid_sim_scenario_rejected(self):
        self.assertEqual(self.c.post("/api/sim", json={"scenario": "foo"}).status_code, 400)
        self.assertEqual(W.SIM["scenario"], "stable")
        self.assertEqual(self.c.post("/api/sim", json={"offline": "yes"}).status_code, 400)

    def test_old_notes_expire(self):
        with W.db() as c: c.execute("INSERT INTO notes(ts,text) VALUES(?,?)", (time.time() - 7200, "saans chakkar bukhar"))
        j = self.c.post("/api/readings", json=reading("n1")).get_json()
        self.assertEqual(j["risk"]["level"], "Low")

    def test_future_timestamp_rejected_and_headers_set(self):
        r = self.c.post("/api/readings", json=reading("f", ts=time.time() + 86400))
        self.assertEqual(r.get_json()["accepted"], 0)
        self.assertEqual(r.headers["Cache-Control"], "no-store"); self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_ack_unknown_alert_404(self):
        self.assertEqual(self.c.post("/api/alerts/999/ack", json={}).status_code, 404)

    def test_non_object_body_is_400_not_500(self):
        self.assertLess(self.c.post("/api/notes", json=[1]).status_code, 500)
        self.assertLess(self.c.post("/api/checkin", data="x", content_type="application/json").status_code, 500)

    def test_high_risk_alerts_once_then_ack_and_escalates(self):
        for i in range(3):
            self.c.post("/api/readings", json=reading(f"h{i}", hr=135, spo2=88, sbp=85, temp=39.5))
        a = self.c.get("/api/state").get_json()["alerts"]
        self.assertEqual((len(a), a[0]["level"]), (1, "High"))
        W.ESC = 1
        with W.db() as c: c.execute("UPDATE alerts SET ts=ts-10")
        self.assertEqual(self.c.get("/api/state").get_json()["alerts"][0]["esc"], 2)
        self.assertEqual(self.c.post(f"/api/alerts/{a[0]['id']}/ack", json={"by": "Priya"}).status_code, 200)
        self.assertEqual(self.c.get("/api/state").get_json()["alerts"][0]["status"], "acknowledged")

    def test_higher_alert_supersedes_and_keeps_alarm_time(self):
        t0 = time.time() - 40
        with W.db() as c: c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,?,1)", (t0, "Medium", "x", "open"))
        for i in range(3): self.c.post("/api/readings", json=reading(f"s{i}", hr=135, spo2=88, sbp=85, temp=39.5))
        al = self.c.get("/api/state").get_json()["alerts"]
        self.assertEqual([a["status"] for a in al], ["open", "superseded"])
        self.assertAlmostEqual(al[0]["ts"], t0, delta=1); self.assertGreaterEqual(al[0]["esc"], 1)

    # ---- supervisor: escalation, notifications, signal loss -------------------------------------------------
    def _alerts(self, kind=None):
        with W.db() as c:
            q, a = ("SELECT * FROM alerts WHERE kind=? ORDER BY id", (kind,)) if kind else ("SELECT * FROM alerts ORDER BY id", ())
            return [dict(r) for r in c.execute(q, a)]

    def _notes_logged(self):
        with W.db() as c: return [dict(r) for r in c.execute("SELECT * FROM notifications ORDER BY alert_id, step")]

    def test_escalation_and_notifications_advance_without_any_dashboard_poll(self):
        W.ESC = 30
        with W.db() as c: c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,?,0)", (time.time() - 70, "High", "SpO2 88% (+3)", "open"))
        W.cycle()  # what the background thread does; /api/state is never called
        self.assertEqual(self._alerts()[0]["esc"], 2)
        n = self._notes_logged()
        self.assertEqual([x["channel"] for x in n], ["Push notification", "SMS", "Voice call"])
        self.assertEqual([x["recipient"] for x in n], W.LADDER)
        self.assertIn("possible deterioration", n[0]["message"])
        self.assertNotIn("diagnos", n[0]["message"].lower())

    def test_notifications_are_idempotent(self):
        with W.db() as c: c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,?,0)", (time.time() - 70, "High", "x", "open"))
        for _ in range(5): W.cycle()
        self.assertEqual(len(self._notes_logged()), 3)

    def test_acknowledged_alert_stops_notifying(self):
        W.ESC = 30
        with W.db() as c: c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,?,0)", (time.time() - 5, "High", "x", "open"))
        W.cycle(); self.assertEqual(len(self._notes_logged()), 1)
        aid = self._alerts()[0]["id"]
        self.c.post(f"/api/alerts/{aid}/ack", json={"by": "Priya"})
        W.cycle(time.time() + 120)  # two rungs later, but nobody is waiting any more
        self.assertEqual(len(self._notes_logged()), 1)

    def test_no_signal_alert_before_first_reading(self):
        W.cycle(time.time() + 9999)
        self.assertEqual(self._alerts("signal"), [])

    def test_signal_loss_alert_raised_once_then_auto_resolved(self):
        self.c.post("/api/readings", json=reading("old", ts=time.time() - 100))
        W.cycle(); W.cycle(); W.cycle()
        sig = self._alerts("signal")
        self.assertEqual((len(sig), sig[0]["status"], sig[0]["level"]), (1, "open", "Medium"))
        self.assertIn("not being monitored", sig[0]["reason"])
        self.c.post("/api/readings", json=reading("fresh"))  # data flows again (e.g. buffer flushed)
        W.cycle()
        sig = self._alerts("signal")
        self.assertEqual((len(sig), sig[0]["status"], sig[0]["ack_by"]), (1, "resolved", "System"))

    def test_second_silence_raises_a_second_alert(self):
        self.c.post("/api/readings", json=reading("a", ts=time.time() - 100)); W.cycle()
        self.c.post("/api/readings", json=reading("b")); W.cycle()
        W.cycle(time.time() + 100)
        self.assertEqual([a["status"] for a in self._alerts("signal")], ["resolved", "open"])

    def test_signal_alert_coexists_with_risk_alert(self):
        old = time.time() - 100
        for i in range(3): self.c.post("/api/readings", json=reading(f"h{i}", ts=old + i, hr=135, spo2=88, sbp=85, temp=39.5))
        W.cycle()
        self.assertEqual(len(self._alerts("risk")), 1)
        self.assertEqual(len(self._alerts("signal")), 1)
        self.assertEqual({a["status"] for a in self._alerts()}, {"open"})  # neither supersedes the other

    def test_signal_alert_can_be_acknowledged(self):
        self.c.post("/api/readings", json=reading("o", ts=time.time() - 100)); W.cycle()
        aid = self._alerts("signal")[0]["id"]
        self.assertEqual(self.c.post(f"/api/alerts/{aid}/ack", json={"by": "Priya"}).status_code, 200)
        self.assertEqual(self._alerts("signal")[0]["status"], "acknowledged")

    def test_state_and_notifications_endpoints_expose_the_log(self):
        with W.db() as c: c.execute("INSERT INTO alerts(ts,level,reason,status,esc) VALUES(?,?,?,?,0)", (time.time(), "Medium", "x", "open"))
        j = self.c.get("/api/state").get_json()
        self.assertEqual(j["signal_loss_seconds"], 45)
        self.assertEqual(len(j["notifications"]), 1)
        self.assertEqual(len(self.c.get("/api/notifications").get_json()["notifications"]), 1)

    def test_old_database_is_migrated(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        with sqlite3.connect(path) as c:  # the v0.3.0 schema: no `kind` column, no notifications table
            c.execute("CREATE TABLE alerts(id INTEGER PRIMARY KEY, ts REAL, level TEXT, reason TEXT, status TEXT, ack_by TEXT, ack_ts REAL, esc INTEGER DEFAULT 0)")
            c.execute("INSERT INTO alerts(ts,level,reason,status) VALUES(1,'High','old','acknowledged')")
        keep, W.DB = W.DB, path
        try:
            W.init()
            with W.db() as c:
                self.assertEqual(c.execute("SELECT kind FROM alerts").fetchone()[0], "risk")
                c.execute("SELECT 1 FROM notifications")
        finally:
            W.DB = keep

    def test_concurrent_requests_still_create_one_alert(self):
        import threading
        def go(i):
            cl = W.app.test_client()
            for j in range(3): cl.post("/api/readings", json=reading(f"t{i}-{j}", hr=135, spo2=88, sbp=85, temp=39.5))
        ths = [threading.Thread(target=go, args=(i,)) for i in range(12)]
        [t.start() for t in ths]; [t.join() for t in ths]
        self.assertEqual([a["status"] for a in self._alerts("risk")], ["open"])

    def test_reset_clears_everything_and_signals_the_simulator(self):
        self.c.post("/api/readings", json=reading("r1", hr=135, spo2=88, sbp=85, temp=39.5))
        self.c.post("/api/notes", json={"text": "saans"}); self.c.post("/api/checkin", json={"name": "Priya"})
        W.SIM.update(scenario="deteriorating", offline=True)
        before = W.SIM["epoch"]
        j = self.c.post("/api/reset").get_json()
        self.assertEqual((j["scenario"], j["offline"], j["epoch"]), ("stable", False, before + 1))
        s = self.c.get("/api/state").get_json()
        self.assertEqual((s["readings"], s["alerts"], s["notes"], s["checkin"]), ([], [], [], None))

    def test_sim_endpoint_cannot_set_epoch(self):
        before = W.SIM["epoch"]
        self.c.post("/api/sim", json={"scenario": "stable", "epoch": 999})
        self.assertEqual(W.SIM["epoch"], before)

if __name__ == "__main__": unittest.main()
