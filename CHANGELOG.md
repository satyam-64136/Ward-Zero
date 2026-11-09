# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
