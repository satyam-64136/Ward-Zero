"""End-to-end check of the whole pipeline against the REAL server process (no mocks).

    python scripts/e2e_check.py

It boots app.py on a free port with a throw-away database, feeds it a patient who deteriorates (using the
simulator's own generator), and verifies Sense -> Understand -> Predict -> Alert -> Respond, then the
resilience paths: duplicate batches, bad data, and a silent device. Escalation is observed through
/api/notifications only, never /api/state, to prove it advances with nobody watching the dashboard.
Exit code 0 = every check passed. Takes about 25 seconds.
"""
import os
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
import uuid

import requests

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import simulator  # noqa: E402  (the same generator the demo uses)

ESC, SIGNAL = 2, 4
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""), flush=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def series(scenario, n, end):
    """n readings from the simulator's generator, one per second, ending at `end` (epoch seconds)."""
    out = []
    for i in range(n):
        r = simulator.tick(scenario)
        r["ts"], r["cid"] = end - (n - 1 - i), str(uuid.uuid4())
        out.append(r)
    return out


def main():
    port = free_port()
    api = f"http://127.0.0.1:{port}"
    env = {**os.environ, "PORT": str(port), "HOST": "127.0.0.1", "ESCALATION_SECONDS": str(ESC),
           "SIGNAL_LOSS_SECONDS": str(SIGNAL), "WARDZERO_DB": os.path.join(tempfile.mkdtemp(), "e2e.db")}
    server = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # nosec B603
    try:
        for _ in range(60):
            try:
                if requests.get(f"{api}/api/health", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.25)
        else:
            print("FAIL  server did not start")
            return 1
        post = lambda path, body: requests.post(api + path, json=body, timeout=5).json()  # noqa: E731
        state = lambda: requests.get(api + "/api/state", timeout=5).json()  # noqa: E731

        def beat():
            """The device is alive: one fresh reading. Keeps the signal watch quiet while we observe escalation."""
            post("/api/readings", [{**simulator.tick("deteriorating"), "cid": str(uuid.uuid4())}])

        print("SENSE")
        t0 = time.time()  # the first 60 seconds of data arrive as one delayed batch, all in the past
        stable = series("stable", 30, t0 - 31)
        j = post("/api/readings", stable)
        check("30 stable readings accepted", j["accepted"] == 30 and j["rejected"] == 0)
        check("stable patient scores Low, no risk alert", j["risk"]["level"] == "Low" and not [a for a in state()["alerts"] if a["kind"] == "risk"])

        print("UNDERSTAND / PREDICT")
        worse = series("deteriorating", 10, t0 - 21)
        j = post("/api/readings", worse)
        check("trend check raises an early warning", j["risk"]["early_warning"], f"level {j['risk']['level']}")
        check("every risk carries readable reasons", len(j["risk"]["reasons"]) >= 2, "; ".join(j["risk"]["reasons"][:2]))
        j = post("/api/readings", series("deteriorating", 20, t0 - 1))
        check("sustained deterioration reaches High", j["risk"]["level"] == "High", f"score {j['risk']['score']}")

        print("ALERT")
        beat()
        risk = [a for a in state()["alerts"] if a["kind"] == "risk"]
        check("exactly one open risk alert (lower ones superseded)", [a["status"] for a in risk].count("open") == 1)
        aid = next(a["id"] for a in risk if a["status"] == "open")

        print("RESPOND (observed without polling /api/state)")
        deadline = time.time() + ESC * 3 + 4
        notes = []
        while time.time() < deadline and len([n for n in notes if n["alert_id"] == aid]) < 3:
            time.sleep(0.5)
            beat()
            notes = requests.get(api + "/api/notifications", timeout=5).json()["notifications"]
        mine = sorted((n for n in notes if n["alert_id"] == aid), key=lambda n: n["step"])
        check("caregiver, family, doctor notified in order", [n["channel"] for n in mine] == ["Push notification", "SMS", "Voice call"])
        check("messages are hedged, never a diagnosis", all("possible deterioration" in n["message"] and "diagnos" not in n["message"].lower() for n in mine))
        post(f"/api/alerts/{aid}/ack", {"by": "Priya"})
        a = next(x for x in state()["alerts"] if x["id"] == aid)
        check("acknowledgement closes the alert and records who", a["status"] == "acknowledged" and a["ack_by"] == "Priya")
        before = len(requests.get(api + "/api/notifications", timeout=5).json()["notifications"])
        for _ in range(ESC + 1):
            time.sleep(1)
            beat()
        after = len(requests.get(api + "/api/notifications", timeout=5).json()["notifications"])
        check("no further notifications after acknowledgement", before == after)

        print("RESILIENCE")
        j = post("/api/readings", stable + worse)
        check("replayed batch creates no duplicates", j["accepted"] == 0)
        check("no signal alert while the device is alive", not [x for x in state()["alerts"] if x["kind"] == "signal" and x["status"] == "open"])
        bad = {**simulator.tick("stable"), "spo2": 140}
        j = post("/api/readings", [bad, {**simulator.tick("stable"), "cid": str(uuid.uuid4())}])
        check("bad reading rejected, rest of the batch kept", (j["accepted"], j["rejected"]) == (1, 1))
        time.sleep(SIGNAL + ESC)
        sig = [x for x in state()["alerts"] if x["kind"] == "signal"]
        check("silent device raises a signal-lost alert", bool(sig) and sig[0]["status"] == "open")
        post("/api/readings", [{**simulator.tick("stable"), "cid": str(uuid.uuid4())}])
        sig = [x for x in state()["alerts"] if x["kind"] == "signal"]
        check("alert closes itself when data returns", sig[0]["status"] == "resolved" and sig[0]["ack_by"] == "System")
    finally:
        server.terminate()
        server.wait(timeout=5)

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
