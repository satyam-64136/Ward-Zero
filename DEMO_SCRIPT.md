# 3-minute demo script (screen-record dashboard + terminals)
**0:00–0:20** Problem: "Home patients have no ward-level monitoring." Show architecture block from README.
**0:20–0:50** Start both terminals. Dashboard live, risk Low, vitals streaming. Caregiver checks in.
**0:50–1:30** Click *Trigger deterioration*. Point at SpO₂ falling, HR rising → risk Medium → High, read the reason list. Alert appears.
**1:30–1:50** Add note "saans phool rahi hai, chakkar" → new reasons from Hindi keywords.
**1:50–2:20** Wait for escalation ladder to advance, then click *Acknowledge* (show response time).
**2:20–2:50** Resilience: *Cut network* → terminal shows "OFFLINE – buffered"; *Restore* → "flushed buffer", chart fills in, no duplicates.
**2:50–3:00** Close: safety disclaimer, repo link, future work.
