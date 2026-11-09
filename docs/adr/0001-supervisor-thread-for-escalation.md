# ADR-0001: Escalate with a supervisor thread, not on dashboard requests

**Status:** Accepted
**Date:** 2026-11-09
**Deciders:** Satyam (author)

## Context

Escalation (caregiver, then family, then doctor) used to be computed inside `GET /api/state`. That meant the ladder only moved while somebody had the dashboard open, and "notifying" someone was only a changed highlight on screen. A home-care alert that nobody is watching is exactly the case the system exists for. Constraints: no new services to run (one command must start the demo), SQLite storage, a 3-minute demo, one author.

## Decision

Run a daemon thread inside the API process that calls `cycle()` once per second. `cycle()` does two things in one write transaction: close or raise signal-lost alerts, and advance every open alert along the ladder, writing one row per rung to a `notifications` table (`UNIQUE(alert_id, step)`). Delivery is simulated: the row is the notification, nothing leaves the machine. `GET /api/state` also calls `cycle()` so a snapshot is never behind.

## Options considered

### Option A: Escalate inside `GET /api/state` (status quo)
| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Correctness | Fails when nobody is watching |
| Testability | Needs a request to trigger time |

### Option B: Supervisor thread in the API process (chosen)
| Dimension | Assessment |
|---|---|
| Complexity | Low: about 40 lines, no new dependency |
| Correctness | Runs without any client; idempotent writes make duplicate runs harmless |
| Testability | `cycle(now)` is a plain function that tests call directly |

### Option C: Celery or APScheduler with a broker
| Dimension | Assessment |
|---|---|
| Complexity | High: broker, worker process, more setup steps |
| Correctness | Strong |
| Fit | Over-built for one patient and a one-command demo |

### Option D: Separate worker process
| Dimension | Assessment |
|---|---|
| Complexity | Medium: another process to start, supervise and document |
| Correctness | Strong; survives an API crash |
| Fit | Reasonable later; adds demo friction now |

## Trade-off analysis

Option B buys correctness without infrastructure. Its weakness is that the thread dies with the API process, so a crashed API stops escalating. The simulator and dashboard already report an unreachable server, and a process manager (Docker `restart: unless-stopped`) restarts it. If the API runs with several processes, `UNIQUE(alert_id, step)` plus `INSERT OR IGNORE` and `BEGIN IMMEDIATE` keep notifications from duplicating.

## Consequences

- Easier: escalation and notification logging work with no browser open; time-dependent behaviour is unit-testable.
- Harder: one more moving part inside the API process; tests must disable it (`WARDZERO_WORKER=0`) and call `cycle()` themselves.
- Revisit: when a real delivery channel (SMS, WhatsApp) is added, send from the same `escalate()` step after the row is written, and record delivery status. Move to Option D if the API must restart independently.

## Action items

1. [x] Add `notifications` table and migration for older databases.
2. [x] Tests: unattended escalation, idempotency, stop after acknowledgement.
3. [ ] Real delivery channel and delivery receipts (see roadmap).
