# 🏥 Ward Zero — a hospital ward inside a bedroom
Operation Ward Zero submission. **Sense → Understand → Predict → Alert → Respond**, fully simulated (no hardware).
> ⚠ Experimental prototype, synthetic data only. Not a medical device; no diagnosis or treatment claims.

## Run (2 terminals)
```bash
pip install -r requirements.txt
python app.py            # terminal 1 → http://127.0.0.1:5000
python simulator.py      # terminal 2 (virtual sensors)
```
Optional env vars: `ESCALATION_SECONDS=30` (escalation step), `NOTE_WINDOW_SECONDS=1800` (how long a note influences risk), `HOST=127.0.0.1` (localhost-only by default), `PORT=5000`.
Tests: `python -m unittest -v`

## Demo flow
1. Dashboard shows live vitals, risk **Low**. Caregiver taps **Check in**.
2. **Trigger deterioration** → SpO₂ falls, HR rises → trend model flags early warning → **Medium/High** with reasons → alert.
3. Add note `saans phool rahi hai, chakkar` → keywords raise the score (Hindi + English).
4. Ignore the alert → it escalates Caregiver → Family → Doctor. Tap **Acknowledge** to close it.
5. **Cut network** → simulator buffers to `queue.json`; **Restore** → buffer syncs, nothing lost, no duplicates.

## Architecture
```
simulator.py ──POST /api/readings──► Flask API (app.py) ──► SQLite
 (disk buffer + retry)                  │                      │
                                        ▼                      ▼
                                  risk.py (rules+trend+notes)  alerts / escalation ladder
                                        ▼
                              templates/index.html (live dashboard)
```
| File | Role |
|---|---|
| `simulator.py` | Virtual HR/SpO₂/BP/Temp sensor; offline buffer; idempotent IDs |
| `app.py` | REST API, storage, alert + escalation + acknowledgement |
| `risk.py` | NEWS2-style scoring, 24-window trend (early warning), EN/HI note keywords |
| `templates/index.html` | Dashboard, demo controls, caregiver check-in |

## Risk method (explainable)
Score = vital bands (HR, SpO₂, SBP, Temp) + trend points (SpO₂ ↓≥3, HR ↑≥15, SBP ↓≥15, Temp ↑≥0.8) + note keywords (max 3).
`≥6 High · ≥3 (or any single extreme vital) Medium · else Low`. A rising trend alone raises Low → Medium as an early warning. Every result lists its reasons.

## Reliability
Disk-backed atomic device queue · chunked flush · retry · idempotent `cid` dedupe · input validation (bad readings rejected, batch survives) · SQLite WAL + lock timeout · device-offline indicator · SQLite persistence survives restart · escalation continues without user action.

## Limitations / future work
Thresholds are illustrative (not clinically validated); trend uses reading windows, not real 24–48h history; SMS/WhatsApp/call alerts (e.g. Twilio) would plug into the escalation step; auth, encryption and consent flows needed for real use; an ML model could replace the rules once validated data exists.
