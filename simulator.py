"""IoT simulator: sends vitals every second. Buffers to disk when the link is down
(or when 'Cut network' is pressed on the dashboard) and flushes on reconnect."""
import json
import os
import random
import time
import uuid

import requests

API = os.environ.get("API", "http://127.0.0.1:5000")
QUEUE = "queue.json"
MAX_Q, CHUNK = 5000, 200  # bound disk/memory during long outages; flush in chunks the API accepts
TARGET = {"stable": dict(hr=76, spo2=97, sbp=120, dbp=78, temp=36.8),
          "deteriorating": dict(hr=118, spo2=88, sbp=96, dbp=62, temp=38.7)}
NOISE = dict(hr=1.2, spo2=0.3, sbp=1.5, dbp=1.0, temp=0.04)
CAP = dict(hr=(30, 220), spo2=(70, 100), sbp=(60, 250), dbp=(30, 150), temp=(33, 42))
v = dict(TARGET["stable"])

def load():
    try:
        q = json.load(open(QUEUE))
        return q if isinstance(q, list) else []
    except Exception:
        return []

def save(q):  # atomic: a power cut mid-write can't corrupt the buffer
    tmp = QUEUE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(q[-MAX_Q:], f)
    os.replace(tmp, QUEUE)

def tick(scenario):
    for k, t in TARGET.get(scenario, TARGET["stable"]).items():
        lo, hi = CAP[k]
        v[k] = min(hi, max(lo, v[k] + (t - v[k]) * 0.08 + random.gauss(0, NOISE[k])))
    return {"cid": str(uuid.uuid4()), "ts": time.time(), **{k: round(x, 1) for k, x in v.items()}}

def flush(q):
    """Send queue in chunks; returns (remaining, last_risk). Stops at first failure, keeping the rest."""
    risk = None
    while q:
        r = requests.post(f"{API}/api/readings", json=q[:CHUNK], timeout=3)
        r.raise_for_status()
        risk, q = r.json()["risk"]["level"], q[CHUNK:]
    return q, risk

def main():
    print(f"Simulator -> {API}  (Ctrl+C to stop)")
    while True:
        offline, scenario, why = False, "stable", "network cut"
        try:  # control channel (separate from data channel)
            s = requests.get(f"{API}/api/sim", timeout=2).json()
            offline, scenario = bool(s["offline"]), s["scenario"]
        except Exception:
            offline, why = True, "server unreachable"
        q = load()
        q.append(tick(scenario))
        n = len(q)
        if offline:
            print(f"OFFLINE ({why}) - buffered {n}")
        else:
            try:
                q, risk = flush(q)
                print(f"sent {n} reading(s)" + (" [flushed buffer]" if n > 1 else ""), "| risk:", risk)
            except Exception as e:
                print(f"link down ({type(e).__name__}) - buffered {len(q)}")
        save(q)
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped (unsent readings are kept in queue.json)")
