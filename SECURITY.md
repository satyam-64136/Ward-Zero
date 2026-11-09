# Security

Ward Zero is a hackathon prototype that runs on synthetic data. It is **not** safe to expose to untrusted networks or to use with real patient information.

## Current posture

- Binds to `127.0.0.1` by default. Set `HOST=0.0.0.0` only on a network you trust.
- No authentication or authorization yet. Any client that can reach the API can post readings, acknowledge alerts and change the demo scenario.
- Plain HTTP. Put it behind a TLS reverse proxy for anything beyond localhost.
- Input validation: readings are range-checked, batches are capped at 1,000, notes at 500 characters, names at 40.
- All user-supplied text is HTML-escaped before it is rendered.
- API responses are sent with `Cache-Control: no-store`; pages are sent with `X-Content-Type-Options`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.
- No secrets are stored in the repository. See `.env.example` for configuration.

The full list of findings, with CWE references, is in [docs/ASSESSMENT.md](docs/ASSESSMENT.md).

## Reporting a vulnerability

Open a private security advisory on GitHub (Security tab, "Report a vulnerability"), or email satyam64136@gmail.com. Please do not include real patient data in any report.
