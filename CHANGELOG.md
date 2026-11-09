# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] - 2026-11-09
### Added
- Guided dashboard: a five-step panel whose highlighted button shows the next action, replacing the Simulate panel; `Reset demo` button and `POST /api/reset`.
- `demo.py` runs from any folder and explains port conflicts.
- Supervisor thread: escalation and notifications advance every second with no browser open.
- Simulated notification log (`notifications` table, `GET /api/notifications`), shown under each alert on the dashboard.
- Signal-lost alert when no readings arrive for `SIGNAL_LOSS_SECONDS` (default 45); it closes itself when data returns.
- `test_risk.py` (12 risk engine tests), 13 new API and supervisor tests, `scripts/e2e_check.py` (15 checks against the real server) and a CI step for it.
- `docs/CODE_TOUR.md`, `docs/adr/` decision records, a debug report in `docs/ASSESSMENT.md`.
### Removed
- Unused project files: issue and pull request templates, contributing guide, logo design brief, roadmap draft, stale screenshots and duplicate PNG diagrams.
### Changed
- Alerts have a `kind` (`risk` or `signal`) and a new `resolved` status; existing databases are migrated on start.
- Alert-writing paths take the SQLite write lock up front.
- Simulator log distinguishes "network cut" from "server unreachable".
### Fixed
- A silent device no longer leaves the last risk on screen with no alert.
- Escalation no longer depends on someone polling `/api/state`.
- Test leak: one test left the escalation timer at 1 second for later tests.
- The first box of the escalation diagram was drawn off the left edge.

## [0.3.0] - 2026-11-09
### Added
- Redesigned dashboard: live pipeline, ECG trace, risk reasoning, response panel, light and dark themes, self-hosted fonts.
- `demo.py` one-command launcher, Dockerfile and compose file, GitHub Actions CI, issue and pull request templates.
- Documentation set under `docs/` with generated architecture diagrams.
- Security response headers and `Cache-Control: no-store` on API responses.
### Changed
- A higher alert now supersedes an open lower one and keeps the original alarm time.
- Escalation level can only move forward.
- Risk engine split into small functions (complexity 24 to 7); behaviour verified identical on 5,000 random inputs.
### Fixed
- Readings with timestamps far in the future are rejected.
- Note reasons no longer list more points than were scored.

## [0.2.0] - 2026-11-09
### Fixed
- Bad readings no longer break a whole upload batch or the device buffer.
- Score bands no longer leave gaps (an SpO2 of 91.5 scored 0).
- Invalid simulator scenarios are rejected instead of crashing the simulator.
- Caregiver notes expire after 30 minutes instead of inflating risk forever.
### Added
- Regression tests, atomic and capped offline buffer, SQLite WAL mode, `/api/health`.

## [0.1.0] - 2026-11-09
- First working prototype: simulator, Flask API, risk engine, dashboard.
