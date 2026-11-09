# Demo script (3 minutes)

Record the dashboard in dark theme at 1080p. The video must show the whole chain: sensor, platform, risk, alert, caregiver response. The guide at the top of the page tells you which button is next, so you can follow it live.

**Start with short timers so every step fits on camera** (PowerShell):

```powershell
$env:ESCALATION_SECONDS="10"; $env:SIGNAL_LOSS_SECONDS="10"; python demo.py
```

Keep the terminal visible in a corner: it shows the simulator printing `sent`, `OFFLINE (network cut) - buffered N` and `[flushed buffer]`. Press **Reset demo** before you start recording.

| Time | Press / show | Say |
|---|---|---|
| 0:00 to 0:20 | Dashboard, Stable; then the architecture diagram from the README | "Home patients lack ward-level awareness. Ward Zero senses, understands, predicts, alerts and tracks the response. It is software only, on synthetic data." |
| 0:20 to 0:35 | **Check in**; point at the pipeline strip | "A caregiver is on duty. The strip shows each stage of the system live." |
| 0:35 to 1:05 | **Make patient worse** | "SpO2 is falling and heart rate rising. The trend check raises an early warning before values are critical, and the risk becomes High with the exact reasons and points. It is rule-based on purpose, so every alert can explain itself." |
| 1:05 to 1:20 | **Add sample note** | "Caregiver notes in Hindi or English add context to the score." |
| 1:20 to 1:55 | Do not acknowledge yet. Point at the notification log under the alert as push, SMS and voice call appear; then **Acknowledge alert** | "Nobody responds, so the supervisor escalates to family, then the doctor. This runs on the server, not in the browser. The messages are simulated and logged. Acknowledging records who responded and how fast." |
| 1:55 to 2:40 | **Make patient stable**, then **Cut network**. Wait about 12 seconds | "Now the device loses its connection. It keeps every reading on disk. After 10 seconds with no data the system does not pretend everything is fine: it raises a signal-lost alert and escalates it." |
| | **Restore network** | "When the network returns, the buffer flushes with no loss and no duplicates, and the alert closes by itself." |
| 2:40 to 3:00 | Scroll to the footer, then the repository page | "Everything is explainable, uses synthetic data and makes no medical claims. Code, 35 tests, an end-to-end check and documentation are on GitHub." |

**If a step misbehaves while recording**, press **Reset demo** and repeat it. As a fallback, `python scripts/e2e_check.py` boots a fresh server and prints 15 passing checks in about 25 seconds, which also demonstrates the full chain.
