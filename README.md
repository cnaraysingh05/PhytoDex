# PhytoDex

Raspberry Pi botanical cyberdeck with a plant library, saved garden, plant-care assistant, and live host status.

This branch integrates the API and Gemini work. The frontend and final photo-diagnosis modules are still teammate-owned work in progress. Read [the branch walkthrough](docs/BRANCH_FIXES.md) and [API contract](docs/CONTRACT.md).

## Run locally

```bash
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/init_database.py
python -m pytest -q
python app.py
```

The API listens at http://127.0.0.1:5001. Try `/api/health`, `/api/plants`, and `/api/system`. A missing homepage is expected until the frontend is integrated.

Run `python scripts/configure_ai.py` once to create private `.env.ai`, then `python scripts/check_ai.py` for a live check. Default mode without configuration is offline. Restart the server after configuration changes. Gemini runs remotely; the Pi hosts the API and SQLite database. Photo analysis requires internet and account access. The older local-model training files remain experimental and are not connected to this app.

## Tests and integration

`python -m pytest -q` uses fake provider responses and temporary databases. GitHub Actions runs it on branch pushes, PRs to main, and pushes to main. PR/main runs also require the teammate diagnosis and final photo route. Until those arrive, branch tests report their modules as skipped; this is not full product readiness. No API keys are needed in GitHub Actions.

Before merging, agree on the photo contract in docs/CONTRACT.md, bring in the teammate modules, run `python scripts/check_readiness.py --require-team`, and rerun all tests. Frontend browser testing, live Gemini testing, Pi telemetry, and a cold-boot device demo remain separate checks.
