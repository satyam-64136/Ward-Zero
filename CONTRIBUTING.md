# Contributing

Thanks for helping improve Ward Zero.

## Set up
```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python demo.py
```

## Before you open a pull request
1. Work on your own branch, not `main`.
2. Write a failing test first for any bug fix (`test_ward.py`, standard `unittest`).
3. Run `ruff check .`, `python -m unittest -v` and `bandit -q -r app.py risk.py simulator.py demo.py`.
4. Never add real patient data, secrets or personal information.
5. Keep wording in the UI and docs cautious: "possible", never a diagnosis.
6. Update `docs/` and `CHANGELOG.md` when behaviour or settings change.

## Commit messages
Short imperative subject, for example `Reject readings with future timestamps`. Explain why in the body when it is not obvious.

## Reporting issues
Use the issue templates. Describe the steps you took in plain language, what you expected and what happened, so anyone can reproduce it.
