# ADR-0002: Treat loss of signal as its own alert

**Status:** Accepted
**Date:** 2026-11-09
**Deciders:** Satyam (author)

## Context

A monitor that goes quiet looks the same as a patient who is fine. Before this change, a stopped or disconnected device produced no alert, and the dashboard kept showing the last risk. The hackathon criteria weight reliability and resilience (outages, delayed data, failures), and clinical safety means silence must never be read as "all clear".

## Decision

If no reading has arrived for `SIGNAL_LOSS_SECONDS` (default 45) after at least one reading has been seen, raise an alert of `kind='signal'`, level Medium, reason "No readings for over N s: the patient is not being monitored". It uses the same escalation ladder and can be acknowledged. It closes itself (`status='resolved'`, `ack_by='System'`) as soon as data flows again, including after the offline buffer is flushed. One alert per silence, not one per second.

## Options considered

### Option A: Only show "No recent data" on screen (status quo)
Cheap, but invisible to anyone not looking and never escalates.

### Option B: Separate alert kind on the existing alert table (chosen)
Reuses acknowledgement, escalation and the response panel. Needs a `kind` column and care that risk alerts never supersede signal alerts (and the reverse).

### Option C: A separate "device health" subsystem
Cleaner separation, but a second lifecycle, table and UI for one rule.

## Trade-off analysis

Option B keeps one mental model for caregivers (an alert is an alert) and one place to test lifecycle rules. The cost is a `kind` filter in the three risk-alert queries; tests cover that a signal alert and a risk alert can be open at the same time.

Threshold trade-off: a short limit gives faster warning and more false alarms on a flaky link; 45 s is long enough that the demo's 5-second network cut stays quiet and short enough to show on camera (set `SIGNAL_LOSS_SECONDS=15` for recording). Silence is measured against device timestamps, so a device clock that runs ahead delays detection; documented as an assumption.

## Consequences

- Easier: honest status; the "cut network" demo step now shows the safety behaviour as well as the buffering.
- Harder: alerts have two kinds, so any new alert code must filter on `kind`.
- Revisit: per-patient thresholds, and measuring silence by server receipt time instead of device time.

## Action items

1. [x] Add `kind` column, migration, and the `watch_signal()` rule.
2. [x] Tests: raised once, auto-resolved, second silence, coexists with a risk alert, can be acknowledged.
3. [ ] Make the threshold configurable per patient when multi-patient support lands.
