# Technical Documentation — Ward Zero
**1. Problem.** Home patients lack continuous monitoring; caregivers react late. We prototype a small "always-aware ward": sense vitals, assess risk, alert, and track the response.
**2. Solution.** A Python sensor simulator streams vitals to a Flask API (SQLite). A transparent risk engine scores each update; Medium/High creates an alert with reasons. A dashboard lets the caregiver acknowledge; unacknowledged alerts escalate Caregiver → Family → Doctor.
**3. Stack.** Python, Flask, SQLite, vanilla JS/Canvas. No external services, runs offline.
**4. Features.** Live vitals + sparklines · explainable Low/Medium/High · early-warning trend · EN/HI caregiver-note analysis · alert acknowledge + escalation · caregiver check-in · offline buffering + sync · device-offline indicator · safety disclaimer.
**5. Risk approach.** NEWS2-inspired vital banding + trend deltas over a sliding window (proxy for 24–48h deterioration) + keyword matching on notes. Rules were chosen over a black-box model for explainability and clinical safety; each alert lists the exact triggers.
**6. Resilience.** Device persists unsent readings to disk and retries; API dedupes by client UUID (idempotent); control channel separated from data channel; escalation is time-driven server-side.
**7. Safety/privacy.** Synthetic data only; no diagnosis claims; disclaimer on UI; alerts say "possible", not "is".
**8. Assumptions & limits.** Illustrative thresholds, simulated sensors, single patient, no auth. 
**9. Future.** Validated ML model, multi-patient, SMS/call integration, auth + encryption, PWA with local-first caregiver app.
