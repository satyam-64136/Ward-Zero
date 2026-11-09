# Architecture

![Architecture](images/architecture.svg)

## Components

| Component | File | Responsibility |
|---|---|---|
| Sensor simulator | `simulator.py` | Generates vitals for a stable or deteriorating patient, sends them, buffers on failure |
| Offline buffer | `queue.json` | Atomic, capped (5,000) on-disk queue, flushed in chunks of 200 |
| REST API | `app.py` | Validates and stores readings, serves one state snapshot, handles notes, check-ins, acknowledgements and demo controls |
| Risk engine | `risk.py` | Pure functions: vital bands, trend, note keywords, level, reasons |
| Alert manager | `app.py` | Creates and supersedes risk alerts, acknowledges them, raises signal-lost alerts |
| Supervisor thread | `app.py` | Every second: advances escalation by the server clock, writes one simulated notification per rung, closes signal-lost alerts when data returns |
| Database | SQLite (WAL) | `readings`, `notes`, `alerts`, `checkins`, `notifications` |
| Dashboard | `templates/index.html` | Single page; polls `/api/state` every second |

## Reading to response

![Pipeline](images/data-flow.svg)

```mermaid
sequenceDiagram
    participant S as Simulator
    participant A as API
    participant R as Risk engine
    participant D as Dashboard
    participant V as Supervisor thread
    participant C as Caregiver
    S->>A: POST /api/readings (batch, client ids)
    A->>A: validate, insert (ignore duplicate ids)
    A->>R: last 24 readings + recent notes
    R-->>A: level, score, reasons, early warning
    A->>A: raise or supersede alert if Medium/High
    loop every second, no browser needed
        V->>A: cycle(): escalate open alerts, log notifications, watch for silence
    end
    D->>A: GET /api/state (every second)
    A-->>D: readings, risk, alerts, notifications
    C->>D: Acknowledge
    D->>A: POST /api/alerts/{id}/ack
    A->>A: close alert, record response time
```

## Data model

| Table | Columns | Notes |
|---|---|---|
| `readings` | `id`, `cid` (unique), `ts`, `hr`, `spo2`, `sbp`, `dbp`, `temp` | `cid` makes retries idempotent |
| `notes` | `id`, `ts`, `text` | Only notes newer than `NOTE_WINDOW_SECONDS` affect risk |
| `alerts` | `id`, `ts`, `level`, `reason`, `status`, `ack_by`, `ack_ts`, `esc`, `kind` | `kind`: `risk` or `signal`. `status`: `open`, `acknowledged`, `superseded`, `resolved` (closed by the system) |
| `notifications` | `id`, `alert_id`, `step`, `ts`, `recipient`, `channel`, `message` | `UNIQUE(alert_id, step)`: one row per alert and rung, so repeats are harmless. Delivery is simulated |
| `checkins` | `id`, `ts`, `name` | Latest row drives the "on duty" indicator |

## Alert lifecycle

![Escalation](images/escalation.svg)

- A new alert is raised when risk is Medium or High and no alert of the same or higher level was raised in the last 5 minutes.
- A higher alert supersedes open lower ones and keeps the original alarm time, so escalation timing and response time count from the first alarm.
- Escalation level is computed from the server clock by the supervisor thread (and on each state request) and can only move forward. Each rung writes one simulated notification.
- If no reading arrives for `SIGNAL_LOSS_SECONDS`, a separate `signal` alert is raised. It escalates like any other, is never superseded by a risk alert, and resolves itself when data returns.

See [ADR-0001](adr/0001-supervisor-thread-for-escalation.md) and [ADR-0002](adr/0002-signal-loss-is-an-alert.md).

## Resilience

![Resilience](images/resilience.svg)

## Design decisions

| Decision | Reason | Trade-off |
|---|---|---|
| Rules and trends instead of a trained model | Every alert can state why; no unvalidated "AI" medical claim | Less sensitive than a validated model |
| SQLite with WAL | Zero setup, survives restarts, handles concurrent dashboard and device requests | One host, one patient |
| Polling instead of WebSockets | Simple, robust through proxies, trivial to debug | One request per second per viewer |
| Supervisor thread inside the API process | Escalation and notification work when nobody is watching the screen; no extra service to run | Stops if the API process stops; Docker restarts it |
| Silence is an alert | A quiet device must never look like a healthy patient | Threshold trades warning speed against false alarms on a flaky link |
| One gunicorn worker in Docker | Demo control state lives in process memory | Not horizontally scalable as is |
| Dashboard served as a static file | No templating surface for injection; no build step | Single large file |
