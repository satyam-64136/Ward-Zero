# Code tour

A guided read of the code, in the order data moves through it. Total product code is about 570 lines, so all of it can be read in one sitting. Function names below are real; search for them.

## The one-minute picture

```
simulator.py  --POST /api/readings-->  app.py  --last 24 readings + notes-->  risk.py
   (device)                              |  <-- level, score, reasons, early warning --
                                         |--> alerts table --> supervisor thread (every 1 s)
                                         |                       |--> escalation step + notifications table
                                         |                       |--> signal-lost alert / auto-resolve
dashboard (templates/index.html) <-- GET /api/state (every 1 s)
caregiver --> POST /api/alerts/{id}/ack --> closes the alert, stores who and when
```

## One reading, start to finish

| Step | Where | What happens |
|---|---|---|
| 1. Sense | `simulator.py: tick()` | Moves each vital 8% of the way toward the scenario's target plus Gaussian noise, so values drift instead of jumping. Gives the reading a UUID (`cid`) and a timestamp. |
| 2. Buffer | `simulator.py: main()`, `save()`, `load()` | Every reading is appended to `queue.json` first (atomic: write temp file, then `os.replace`). It is removed only after the server answers 200. |
| 3. Send | `simulator.py: flush()` | Sends the queue in chunks of 200, oldest first. On any failure it stops and keeps everything for the next second. |
| 4. Validate | `app.py: clean()` | Range checks, finite numbers, timestamp not more than 5 minutes in the future. Bad readings are counted in `rejected`; the rest of the batch is still saved. |
| 5. Store | `app.py: readings()` | `INSERT OR IGNORE` on the unique `cid`, so a retry after an outage can never create a duplicate. |
| 6. Understand | `risk.py: assess()` | `_vitals()` scores the latest reading per vital (0 to 3 points), `_trend()` compares the first and last 6 of the last 24 readings, `_note_hits()` adds a point per symptom group in recent caregiver notes. Every point comes with a reason string. |
| 7. Predict | `risk.py: _trend()` | Falling SpO2, rising heart rate, falling blood pressure, rising temperature. Two or more trend points set `early_warning` and lift a Low result to Medium. |
| 8. Alert | `app.py: maybe_alert()` | Medium or High creates one alert. A higher alert supersedes an open lower one and keeps the original alarm time. Same-or-lower within 5 minutes is ignored. |
| 9. Respond | `app.py: escalate()`, `cycle()`, `_supervise()` | Once a second the supervisor thread moves each open alert along caregiver, family, doctor by the server clock and writes one `notifications` row per rung (simulated delivery). |
| 10. Silence | `app.py: watch_signal()` | No readings for `SIGNAL_LOSS_SECONDS` raises a signal-lost alert; fresh data resolves it. |
| 11. Acknowledge | `app.py: ack()` | Closes the alert and stores who and when; the supervisor stops notifying because only `status='open'` alerts escalate. |
| 12. Show | `templates/index.html: render()` | Reads `/api/state` and fills the pipeline strip, vitals, reasons, alerts and notification log. All dynamic text goes through `esc()`. |

## Questions you may be asked

**Why rules instead of machine learning?** Every alert must say why. With rules, each point is visible (`SpO2 88.9% (+3)`), a clinician can review the table, and nothing claims a diagnosis. There is no validated clinical dataset to train on, and inventing one would be a fake result. `docs/RISK_MODEL.md` has the tables.

**What is NEWS2, and is this NEWS2?** NEWS2 is a published early-warning score used in UK hospitals. The bands here are inspired by its structure but are not NEWS2 and are not clinically validated. The README, the dashboard and the docs all say so.

**How does it survive the network going down?** The device writes to disk before sending and deletes only after a 200. The server ignores duplicate `cid`s. So a crash at any point either keeps the reading on the device or has it stored exactly once. Tested live by comparing buffered reading ids with database rows: 8 of 8 arrived after an 8-second network cut, and 8 of 8 after an 8-second `kill -9` of the server, with no duplicates.

**What happens if the device just stops?** After 45 seconds (configurable) a signal-lost alert is raised and escalates like any other. It resolves itself when data returns. See `docs/adr/0002-signal-loss-is-an-alert.md`.

**Does escalation need the dashboard open?** No. The supervisor thread runs every second. `scripts/e2e_check.py` proves it by reading only `/api/notifications`.

**Are notifications really sent?** No. Delivery is simulated: a row in the `notifications` table is the message. The README, API docs and the dashboard say "simulated". A real SMS or WhatsApp channel is on the roadmap and would send from `escalate()`.

**Why SQLite and Flask?** Zero setup, one command to run, persistent, safe for one patient and a demo. WAL mode lets the dashboard read while the device writes. The limits (one host, one patient) are documented.

**Why does `GET /api/state` write to the database?** It runs one `cycle()` so the snapshot is never a second behind the supervisor. It is idempotent, so running it twice is harmless. This is listed as technical debt (#3 in `docs/ASSESSMENT.md`).

**What are the known limits?** Illustrative thresholds, one patient, no login, notifications simulated, the "24 to 48 hours" prediction is represented by a window of readings rather than real days of history. All stated in the README and technical document.

## Where to look when something breaks

| Symptom | Look at |
|---|---|
| Dashboard says "Server unreachable" | Is `python demo.py` still running? Try `GET /api/health` |
| No data on the dashboard | The simulator runs inside `demo.py`; its terminal output says `sent`, `network cut` or `server unreachable` |
| Alert never escalates | Is the supervisor running? It is off when `WARDZERO_WORKER=0` |
| Signal-lost alert appears during a demo | `SIGNAL_LOSS_SECONDS` is shorter than your pause |
| Old database errors after an upgrade | `init()` migrates automatically; delete `wardzero.db` to start clean |

## Checks you can run yourself

```bash
python -m unittest -v                 # 35 tests
python scripts/e2e_check.py           # boots the real server, 15 end-to-end checks, about 25 s
ruff check . && bandit -q -r app.py risk.py simulator.py demo.py
```
