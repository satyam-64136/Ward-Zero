<p align="center"><img src="assets/logo.svg" width="64" alt="Ward Zero logo"></p>
<h1 align="center">Ward Zero</h1>
<p align="center"><b>A hospital ward inside a bedroom.</b><br>Simulated vitals, explainable risk scoring, alert escalation and caregiver response, in one working prototype.</p>

<p align="center">
  <a href="https://github.com/satyam-64136/Ward-Zero/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/satyam-64136/Ward-Zero/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-17677d">
  <img alt="Flask" src="https://img.shields.io/badge/backend-Flask%20%2B%20SQLite-17677d">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-17677d">
</p>

> **Experimental prototype.** Synthetic data only. Not a medical device. It makes no diagnosis or treatment claims, and its thresholds are illustrative, not clinically validated.

Built for **Operation Ward Zero** (Nursio Innovation, hosted on Wooble and Unstop). No hardware needed: a simulator stands in for the sensors.

```
Sense  ->  Understand  ->  Predict  ->  Alert  ->  Respond
```

## Run it (about a minute)

You need **Python 3.11 or newer**. Open a terminal in the project folder.

**Windows (PowerShell)**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python demo.py
```

**macOS / Linux**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python demo.py
```

> **Always start with `python demo.py`.** It launches the server *and* the sensor simulator together and opens the dashboard at <http://127.0.0.1:5000>. You do not need to run `app.py` or `simulator.py` yourself. Press **Ctrl+C** in the terminal to stop.

Prefer Docker? `docker compose up --build`, then open <http://127.0.0.1:5000>.

| Problem | Fix |
|---|---|
| `python` or `py` not found | Install Python 3.11+ from python.org and tick "Add to PATH" |
| `No module named flask` | Run `pip install -r requirements.txt` inside the activated virtual environment |
| "The server did not start" | Port 5000 is busy. Close the other program, or run `$env:PORT="5050"; python demo.py` (PowerShell) / `PORT=5050 python demo.py` (macOS, Linux) |
| Page says "Waiting for the first reading" | Wait two seconds; the simulator sends one reading per second |
| Want a clean slate | Press **Reset demo** on the page |

## Try it in 5 steps

The top of the dashboard is a guide. The **highlighted** button is always the next thing to press.

| Step | Press | What you should see |
|---|---|---|
| 1 | **Check in** | The top bar shows the caregiver as on duty |
| 2 | **Make patient worse** | Oxygen falls and heart rate rises. An early warning appears, risk climbs to High, and the headline changes to "Needs attention now" |
| 3 | **Add sample note** | A Hindi symptom note (`saans phool rahi hai, chakkar`) adds points; the reasons list shows them |
| 4 | Wait, then **Acknowledge alert** | If you wait, the alert escalates to family, then the doctor, and each step is logged under the alert. Acknowledging closes it and records the response time |
| 5 | **Cut network**, wait, then **Restore network** | The device keeps every reading and sends them back with no loss and no duplicates. If the silence is long, a **Signal lost** alert appears and closes itself when data returns |

For the signal-lost step to show quickly, start with a shorter limit (default is 45 seconds):
`$env:SIGNAL_LOSS_SECONDS="10"; python demo.py` (PowerShell) or `SIGNAL_LOSS_SECONDS=10 python demo.py`.

## How to check the work

| What | Command | Expect |
|---|---|---|
| Unit and API tests | `pip install -r requirements-dev.txt` then `python -m unittest -v` | 35 tests pass |
| Whole pipeline against the real server | `python scripts/e2e_check.py` | `15/15 checks passed` in about 25 seconds |
| Lint and security scan | `ruff check .` and `bandit -q -r app.py risk.py simulator.py demo.py scripts/e2e_check.py` | No findings |

| Evaluation criterion | How it is addressed | Where to look |
|---|---|---|
| End-to-end integration (25%) | One live flow from simulator to acknowledgement, shown stage by stage on the dashboard and checked by `scripts/e2e_check.py` | [Architecture](docs/ARCHITECTURE.md) |
| Technical skills (20%) | Small validated REST API, pure risk engine, 35 tests, CI with lint and security scan, decision records | [Code tour](docs/CODE_TOUR.md), [ADRs](docs/adr), [Assessment](docs/ASSESSMENT.md) |
| Reliability and resilience (20%) | Disk-backed offline buffer, idempotent writes, input validation, signal-lost alert, escalation that runs with no browser open | [Reliability](#reliability) |
| Practical implementation (20%) | Guided dashboard, caregiver check-in, escalation ladder with a notification log, English and Hindi notes, one-command start | [Try it](#try-it-in-5-steps) |
| Explainability and clinical safety (15%) | Every score lists its reasons, early warnings say "possible", disclaimers on every screen | [Risk model](docs/RISK_MODEL.md) |

## What it does

At home, a patient usually has a family member and a thermometer. Ward Zero shows what continuous, ward-level awareness could look like.

1. **Sense**: a simulated device streams heart rate, SpO2, blood pressure and temperature every second.
2. **Understand**: each reading is validated, stored and scored against NEWS2-inspired bands.
3. **Predict**: a trend check over a 24-reading window raises an early warning before values become critical.
4. **Alert**: Medium and High risk raise one alert that states exactly why.
5. **Respond**: a supervisor thread escalates the alert caregiver, then family, then doctor, logging a simulated push, SMS and voice call at each step, until someone acknowledges it. It runs with no browser open.

If the device goes silent, that is an alert too: no readings for 45 seconds raises **Signal lost**, and it closes itself when data returns.

![Pipeline](docs/images/data-flow.svg)

## Architecture

![Architecture](docs/images/architecture.svg)

Components, data model and design decisions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Endpoints: [docs/API.md](docs/API.md).

## Risk model

![Risk engine](docs/images/risk-engine.svg)

A transparent rules model was chosen over a black box so that every alert can say why it was raised. Full tables and a worked example: [docs/RISK_MODEL.md](docs/RISK_MODEL.md).

## Reliability

![Resilience](docs/images/resilience.svg)

- The device writes every reading to an atomic on-disk buffer and clears it only after the server confirms receipt.
- The API validates each reading, rejects bad ones without failing the batch, and ignores duplicates by client id.
- The dashboard shows device state honestly: online, no recent data, or network cut. A device that stays silent raises its own alert instead of leaving the last risk on screen.
- Escalation is driven by the server clock in a supervisor thread, so it continues without anyone watching the screen.

![Escalation](docs/images/escalation.svg)

## Safety and privacy

- Synthetic data only. Do not connect real patient data to this prototype.
- Wording is deliberately hedged: "possible deterioration", never a diagnosis.
- Notifications are **simulated**: each one is logged and shown on the dashboard; nothing is sent anywhere.
- The server listens on localhost by default and sends `Cache-Control: no-store` on every API response.
- There is no authentication yet. See [SECURITY.md](SECURITY.md) before exposing it to a network.

## Configuration

All optional. Set them as environment variables before `python demo.py`.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Server port |
| `HOST` | `127.0.0.1` | Bind address (localhost only by default) |
| `WARDZERO_DB` | `wardzero.db` | SQLite file |
| `ESCALATION_SECONDS` | `30` | Seconds per escalation step |
| `SIGNAL_LOSS_SECONDS` | `45` | Silence longer than this raises a signal-lost alert |
| `NOTE_WINDOW_SECONDS` | `1800` | How long a caregiver note influences risk |
| `WARDZERO_WORKER` | `1` | Set to `0` to disable the supervisor thread (tests do this) |

## Project structure

```
demo.py                START HERE: launches server + simulator, opens the dashboard
app.py                 Flask API, storage, alerts, supervisor thread
risk.py                Explainable risk engine
simulator.py           Virtual sensors with offline buffering
templates/index.html   Dashboard (served as-is)
static/fonts/          Self-hosted Instrument Sans and Serif (OFL)
test_ward.py           API, alert, escalation and signal-loss tests
test_risk.py           Risk engine unit tests
scripts/               End-to-end check, diagram generator
docs/                  Technical document, architecture, API, risk model, code tour, ADRs
assets/logo.svg        Logo
Dockerfile, docker-compose.yml, .github/workflows/ci.yml
```

## Documentation

| Document | Contents |
|---|---|
| [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md) | Problem, solution, stack, features, assumptions, limitations |
| [Architecture](docs/ARCHITECTURE.md) | Components, data model, sequence, design decisions |
| [API reference](docs/API.md) | Every endpoint with examples |
| [Risk model](docs/RISK_MODEL.md) | Scoring tables, worked example, safety notes |
| [Code tour](docs/CODE_TOUR.md) | One reading followed through the code, with likely questions and answers |
| [Decision records](docs/adr) | Why a supervisor thread, why signal loss is an alert |
| [Engineering assessment](docs/ASSESSMENT.md) | Inventory, complexity, debt, security findings, debug report |
| [Demo script](docs/DEMO_SCRIPT.md) | Timed 3-minute recording plan |
| [Changelog](CHANGELOG.md) | What changed in each version |

## Limitations

Thresholds are illustrative. The trend window counts readings rather than hours, so "24 to 48 hours ahead" is demonstrated, not clinically validated. There is one patient and no login. Notifications are simulated. Future work is listed in the [technical documentation](docs/TECHNICAL_DOCUMENTATION.md#8-assumptions-limitations-and-future-improvements).

## Credits

Flask (BSD-3-Clause), requests (Apache-2.0) and SQLite (public domain) are the only runtime dependencies. Instrument Sans and Instrument Serif are used under the SIL Open Font License. The scoring bands are inspired by the structure of the NEWS2 early-warning score published by the Royal College of Physicians; they are not NEWS2 and are not clinically validated. No pretrained models and no external APIs are used. Development tools: ruff, bandit, radon.

## License

MIT. Fonts are licensed under the SIL Open Font License (see `static/fonts`). Author: Satyam Kumar.
