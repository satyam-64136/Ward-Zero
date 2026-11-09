# API reference

Base URL: `http://127.0.0.1:5000`. All bodies are JSON. API responses carry `Cache-Control: no-store`.

## POST /api/readings

Accepts one reading or an array (at most 1,000). Duplicate `cid` values are ignored, so retries are safe.

```json
{ "cid": "7f0c...", "ts": 1794182607.08, "hr": 118, "spo2": 89.4, "sbp": 96, "dbp": 62, "temp": 38.6 }
```

| Field | Rule |
|---|---|
| `cid` | Unique string per reading (up to 64 characters) |
| `ts` | Seconds since epoch; rejected if more than 5 minutes in the future |
| `hr` | 20 to 250 |
| `spo2` | 50 to 100 |
| `sbp` / `dbp` | 40 to 300 / 20 to 200 |
| `temp` | 30 to 45 (Celsius) |

Response `200`:
```json
{ "accepted": 5, "rejected": 1, "risk": { "level": "High", "score": 12, "reasons": ["SpO2 87.7% (+3)"], "early_warning": true, "pts": { "HR": 2, "SpO2": 3, "SBP": 1, "Temp": 1 } } }
```
Invalid readings are counted in `rejected`; the rest of the batch is still saved. More than 1,000 items returns `413`.

## GET /api/state

One snapshot for the dashboard: `readings` (latest 40, oldest first), `risk`, `alerts` (latest 6), `notes` (latest 4), `checkin`, `sim`, `ladder`, `esc_seconds`, `age` (seconds since the last reading) and `now`.

## POST /api/notes
`{ "text": "saans phool rahi hai" }` stores a caregiver note (up to 500 characters). Notes influence risk for `NOTE_WINDOW_SECONDS`.

## POST /api/checkin
`{ "name": "Priya" }` marks a caregiver as on duty.

## POST /api/alerts/{id}/ack
`{ "by": "Priya" }` closes an open alert and records who and when. Returns `404` for an unknown id.

## GET, POST /api/sim
Demo controls. `{ "scenario": "stable" | "deteriorating", "offline": true | false }`. Any other value returns `400`. The simulator polls this endpoint; `offline` makes it buffer instead of send.

## GET /api/health
`{ "status": "ok", "readings": 123 }`. Used by Docker health checks.

## Errors
`400` malformed or invalid input, `404` unknown alert, `413` batch too large. Malformed JSON bodies never cause a `500`.
