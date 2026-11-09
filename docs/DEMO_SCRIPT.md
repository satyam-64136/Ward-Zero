# Demo script (3 minutes)

Record the dashboard in dark theme at 1080p. Start with `python demo.py --no-browser`, open the page, and keep a terminal visible in a corner for the offline step.

| Time | Show | Say |
|---|---|---|
| 0:00 to 0:20 | Dashboard, Stable, architecture diagram from the README | "Home patients lack ward-level awareness. Ward Zero senses, understands, predicts, alerts and tracks the response, with no hardware." |
| 0:20 to 0:40 | Enter a name, press Check in; point at the pipeline strip | "A caregiver is on duty. The strip shows each stage of the system live." |
| 0:40 to 1:20 | Choose Deteriorating | "SpO2 is falling and heart rate rising. The trend check raises an early warning before values are critical, and the risk becomes High with the exact reasons." |
| 1:20 to 1:40 | Add the note `saans phool rahi hai, chakkar` | "Caregiver notes in Hindi or English add context to the score." |
| 1:40 to 2:10 | Wait for the ladder to advance, then press Acknowledge | "Unacknowledged alerts escalate to family, then the doctor. Acknowledging records the response time." |
| 2:10 to 2:40 | Cut the network, wait 5 seconds, restore it | "The device keeps every reading on disk and syncs them when the network returns, with no loss and no duplicates." |
| 2:40 to 3:00 | Scroll to the footer, then the repository page | "Everything is explainable, uses synthetic data and makes no medical claims. Code, tests and documentation are on GitHub." |

Tip: set `ESCALATION_SECONDS=15` before starting to keep the escalation step short on camera.
