"""Run: python -m unittest -v   (no extra dependencies)"""
import os
import tempfile
import time
import unittest

os.environ["WARDZERO_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app as W
from risk import assess


def reading(cid, ts=None, **kw):
    d = dict(cid=cid, ts=ts or time.time(), hr=76, spo2=97, sbp=120, dbp=78, temp=36.8); d.update(kw); return d

class Ward(unittest.TestCase):
    def setUp(self):
        with W.db() as c:
            for t in ("readings", "notes", "alerts", "checkins"): c.execute(f"DELETE FROM {t}")
        W.SIM.update(scenario="stable", offline=False)
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

if __name__ == "__main__": unittest.main()
