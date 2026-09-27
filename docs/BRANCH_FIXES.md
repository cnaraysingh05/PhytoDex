# PhytoDex branch integration walkthrough

This update addresses your assigned issues 1, 6, 5, 3 and 7, in that order: unpack source, unify the database/assistant, add System telemetry, connect the Gemini photo path, and run shared tests/CI. Earlier changes supply what later changes need. Your teammates retain issue 2 (final diagnosis module and photo route) and issue 4 (frontend). Everything stays on feature/model-sourcing until branch testing and team review are complete.

The installer has five stages so each change can be explained and committed separately. It checks the existing file contents against the published branch baseline and backs up replaced code in ignored `.phytodex-update/backups`. It refuses unknown edits, preserves private configuration and database files, and never commits, pushes or merges. Do not rerun the old kit installer over this integration update.

## 0 Open your existing Mac checkout

Use your Mac Terminal, not the SSH window connected to the Pi. Do not clone again.

```bash
cd ~/Documents/PhytoDex-work/PhytoDex
source .venv-ai/bin/activate
git branch --show-current
git status --short
```

Expected branch: `feature/model-sourcing`. If the branch differs, switch only after preserving any current changes. Expected status: no output (clean). If you see unexpected modified files, stop and review them; do not reset or delete them.

```bash
git fetch origin
git pull --ff-only
FIX_KIT="/Users/chrisnaraysingh/Documents/Codex/2026-09-26/okay-we-are-now-working-on/outputs/phytodex-branch-fixes"
```

Keep this terminal open: FIX_KIT is a shortcut to the generated code bundle, not an API key. If you open another terminal, repeat the folder, environment and FIX_KIT setup. A newer teammate edit may cause the installer to stop with a conflict; send the filenames for reconciliation, rather than forcing it.

## 1 Fix issue 1 by unpacking real source files

```bash
python "$FIX_KIT/apply_update.py" --repo "$PWD" --stage 1
git status --short
```

This installs the extracted backend files from the exact published scaffold archive, including `app.py`, database helpers/schema/seed, plant/garden/capture routes, and original backend tests. It adds ignore rules for local backups, databases, captures and generated files. It does not add another ZIP to the repository. The subsequent stages update this scaffold, so do not start its original server yet.

Why this matters: a ZIP is stored data. Python imports and GitHub Actions test discovery need source at real paths such as `backend/routes/plants.py`. A merge of ZIPs alone would not make the application runnable. The files were copied from the inspected Ty-Montgomery archive; no separate merge of Ty's ZIP-only branch is needed to obtain this code. Coordinate later changes using ordinary file diffs.

Save this stage:

```bash
git add .
git --no-pager diff --cached --name-only
git commit -m "build: unpack backend scaffold into source files"
```

Inspect the staged names before committing. `.env.ai.example` is a template; `.env.ai` must never be staged. The no-pager option prevents the scrolling viewer that previously left you at `(END)`. If you ever see `(END)`, press q to exit.

Restate it: “I made the backend source available where Python and tests can load it. I have not yet verified the assembled app.”

## 2 Fix issue 6 by using one database and one assistant

```bash
python "$FIX_KIT/apply_update.py" --repo "$PWD" --stage 2
python -m pip install -r requirements.txt
python scripts/init_database.py
```

Expected: `Plant library ready: 15 entries...` on a fresh database. An existing database can have more entries. Run initialization a second time and verify that the count does not grow:

```bash
python scripts/init_database.py
```

What changed:

- The runtime dependency list includes your AI dependencies and compatible Flask, Pillow and psutil versions. Installing the app no longer downgrades Flask to the scaffold's older incompatible pin.
- `backend/models/db.py` is the shared connection helper; `database/schema.sql` is the schema actually loaded.
- Plants, Garden, captures, assistant logs and the optional telemetry table live in the same SQLite database.
- Your validated typed assistant is the active implementation; no duplicate root-level `assistant (1).py` is installed.
- The assistant route logs its responses to the shared database. A logging failure is reported to the backend without preventing a care response.
- Seeding adds missing scientific names instead of deleting the plants table. Existing plant IDs and saved Garden references survive.
- `app.py` is the shared server; `run_ai.py` becomes a compatibility entry point for the same app.

Why stable IDs matter: a saved Garden row points to a plant's numeric ID. Deleting/recreating plants can break that relationship. “Initialize” should safely create missing structures, not clear the user's collection.

The seed data's image URLs are placeholders for the frontend team's assets. These changes do not supply missing plant photos or verify the horticultural content of every existing seed entry.

```bash
git add .
git --no-pager diff --cached --name-only
git commit -m "fix: unify database setup and assistant logging"
```

Restate it: “All features now agree on one database and assistant implementation. Initialization preserves saved data.”

## 3 Fix issue 5 by exposing live System information

```bash
python "$FIX_KIT/apply_update.py" --repo "$PWD" --stage 3
python -c "import json; from backend.services.system_status import system_status; print(json.dumps(system_status(), indent=2))"
```

This creates the `/api/system` route and its service. The command above checks the service directly on your Mac.

Understand the fields:

- `hostname`: the computer actually running the code. It should be your Mac's name now and the Pi's hostname later.
- `is_raspberry_pi`: hardware detection, not a hard-coded claim.
- `uptime_seconds`: host time since boot, or null if the environment denies access.
- `cpu_temperature_c`: actual CPU/SOC thermal reading on supported Linux hardware; null on a Mac without the Pi sensor interface.
- `database.status`: whether the shared DB and expected tables exist.
- `network`: local interfaces and addresses. This does not prove internet access.
- `gemini.status`: offline, not_configured or configured_not_checked. Merely having a key is not a successful API test.

Why this matters: it proves the device's computing role with measured values. Missing sensors should not crash the page or display fabricated zeroes. Reading System neither exposes the key nor makes a paid API call.

```bash
git add .
git --no-pager diff --cached --name-only
git commit -m "feat: add live host system status"
```

Restate it: “The backend reports measurements from whichever machine runs it; the UI will display those values.”

## 4 Fix issue 3 by choosing Gemini for photo analysis

```bash
python "$FIX_KIT/apply_update.py" --repo "$PWD" --stage 4
python scripts/check_readiness.py
```

Right now you should see the diagnosis module and final route marked PENDING. This is intentional: your teammate owns those files. Do not create placeholder diagnoses just to remove the message.

The chosen flow is:

```text
Photo upload or saved capture ID
    → validate, orient and resize the photo
    → Gemini API call from the backend
    → teammate's build_diagnosis(raw) function
    → structured response for the frontend
```

Your active application no longer loads MobileNet/TFLite. The old training files remain available as unused experiments and TensorFlow is not installed as a runtime dependency. You do not need to train a model to use Gemini.

The source comes from Ty's preprocessing update, with EXIF orientation, decoded-pixel limits, bounded provider requests and structured JSON requests added. Image normalization here means converting to RGB, resizing and JPEG encoding; it is not training or calibrating a classifier. Model certainty is qualitative evidence, not a validated numeric probability.

To respect your teammate's ownership, this update provides `backend/routes/photo_bridge.py`, not their `backend/routes/analysis.py`. The temporary bridge exposes `/api/analysis` and the old `/api/identify` alias. It returns 503 `diagnosis_not_ready` until the diagnosis module exists. When the final teammate route arrives, app.py automatically prefers it and does not register both routes. Their route should export `analysis_bp` and follow docs/CONTRACT.md.

If you have not configured Gemini, run:

```bash
python scripts/configure_ai.py
```

Paste the key only into its private prompt. Accept the supplied model if available in your account; otherwise select an available compatible model. If `.env.ai` already exists, the script refuses to overwrite it: retain it, or edit it privately if changes are needed. Do not display it in a screenshot. The service requires `AI_MODE=gemini` for live photo calls; absent configuration defaults to offline.

Check your private file is ignored, then check the typed assistant:

```bash
git check-ignore .env.ai
python scripts/check_ai.py
```

Expected live result: `source: gemini`, `fallback_reason: null`. A fallback response is not a successful live check.

Optional live photo-provider check, before your teammate finishes diagnosis:

```bash
python scripts/check_photo.py --image data/samples/sample_leaf.jpg --live
```

This explicitly sends the included photo to Google and consumes API quota. It prints `stage: raw_observations`; it does not pretend that the final diagnosis pipeline is complete. You can replace the sample path with your own JPEG/PNG. No Gemini key or live request is used in CI.

```bash
git add .
git --no-pager diff --cached --name-only
git commit -m "feat: connect Gemini photo provider and pending diagnosis bridge"
```

Restate it: “We source Gemini's pretrained vision capability. Our code prepares the image and integrates the API; the teammate's diagnosis layer validates the response.”

## 5 Fix issue 7 by adding shared tests and GitHub Actions

```bash
python "$FIX_KIT/apply_update.py" --repo "$PWD" --stage 5
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

At the packaged baseline: **43 passed, 2 skipped**, plus unittest subtests. The two skips represent deferred test modules for your teammate's diagnosis and final photo route. They automatically activate when those modules arrive. Additional teammate changes may change the count.

The tests verify existing backend routes, assistant behavior/logging, stable seed IDs/Garden preservation, missing sensors, photo preparation, Gemini failure handling, temporary bridge wiring, and capture lookup. They use temporary databases and fake Gemini responses. Unexpected real HTTP requests are blocked. These tests do not measure real model accuracy, verify your account access, or exercise the final frontend.

The workflow is an actual `.github/workflows/tests.yml` file. It installs the runtime/test dependencies and tests Python 3.11, 3.12 and 3.13 on Linux. It runs on branch pushes, PRs targeting main, and pushes to main. PR/main checks also run:

```bash
python scripts/check_readiness.py --require-team
```

That command currently exits with an error because your teammate modules are still absent. This is an intentional readiness gate, not a reason to manufacture placeholder code. Normal branch tests can pass while clearly reporting the deferred integration. A PR can remain draft until the team finishes its work. Frontend completion still requires your team to review and test it; no placeholder UI gate claims otherwise.

```bash
git add .
git --no-pager diff --cached --name-only
git commit -m "ci: test branch integration and gate main on teammate photo modules"
```

Restate it: “CI repeats our isolated tests on a clean machine. It checks reproducibility and integration, not whether Gemini's advice is scientifically correct or the hardware demo works.”

## 6 Try the assembled API on your Mac

In the same activated terminal:

```bash
python scripts/init_database.py
python app.py
```

Leave it running. In a second Mac terminal:

```bash
curl -s http://127.0.0.1:5001/api/health
curl -s http://127.0.0.1:5001/api/plants
curl -s http://127.0.0.1:5001/api/system
curl -s http://127.0.0.1:5001/api/assistant -H 'Content-Type: application/json' -d '{"species":"Pothos","message":"Yellow leaves and soil staying wet."}'
```

The health response should be ok, plants should be a list, System should show your Mac, and the assistant should clearly indicate gemini or fallback. The frontend homepage is still teammate work: a 404 at `/` does not mean these API routes failed.

To exercise the pending photo endpoint from the repo folder:

```bash
cd ~/Documents/PhytoDex-work/PhytoDex
curl -s -i http://127.0.0.1:5001/api/analysis -F 'image=@data/samples/sample_leaf.jpg'
```

Until the diagnosis module arrives, expect 503 with `diagnosis_not_ready`. This is different from the raw-provider CLI check above. Stop the server with Control+C in its own terminal before restarting it after code/config changes.

## 7 Push your branch and inspect Actions

Because this update adds a workflow file, your GitHub fine-grained push token needs both **Contents: Read and write** and **Workflows: Write** for PhytoDex. This is the GitHub token, not the Gemini API key. In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens, edit the token you actually use and save the added permission. If you no longer have the secret token value, generate a replacement and copy it once.

```bash
git status --short
git -c credential.helper= push -u origin feature/model-sourcing
```

Use username `cnaraysingh05`; paste your GitHub token at the password prompt. The token stays invisible. Never paste either kind of key into chat or commit it. If Git rejects workflow modification, check Workflows permission; creating a token does not automatically grant that permission.

Open https://github.com/cnaraysingh05/PhytoDex/actions. Find **PhytoDex tests** for **feature/model-sourcing**, open the run, and inspect each Python-version job. Success should show green checks and the expected skip explanations. A failure means open the failing step and read the first relevant error; share that error without credentials.

Do not merge yet. The workflow will run again on the combined main branch after the team finishes, reviews, tests and merges. Adding the file on your branch enables push checks now; it does not require editing main first. If Actions is disabled in repository settings, enable the repository's Actions support and rerun the failed run from GitHub.

## 8 What to hand your teammates

Point both teammates to `docs/CONTRACT.md` on your branch. Teammate 2 keeps ownership of `analysis/diagnosis.py` and `backend/routes/analysis.py`, and should use the existing classifier rather than create another provider client. Teammate 4 builds the UI against the documented endpoints, displays uncertainty and offline/pending states, and supplies plant image assets.

Once their modules are included in the integration branch, rerun:

```bash
python scripts/check_readiness.py --require-team
python -m pytest -q
```

The readiness command should succeed, the diagnosis and final-route tests should stop skipping, and all tests should pass before merge. The application should choose the final teammate route automatically. Agree on any route/response changes before frontend integration. If your teammates changed the exported blueprint name or request fields, resolve that contract difference explicitly rather than disabling tests.

After review and merge, wait for the main Actions run, then use the Pi's known-good checkout procedure to pull main, install requirements, initialize the database, and restart its service. Verify `/api/system` shows the Pi, test a live Gemini question/photo, exercise Garden persistence, and perform the physical cold-boot demo. This package does not install an auto-start service or test your physical Pi.

## Verification and scope

Locally checked: Python 3.13, shared offline test suite, main-readiness failure when teammate modules are absent, and staged installer behavior on a temporary copy of the published branch. The package contains no actual API key. Live Gemini calls, hosted GitHub Actions jobs, final teammate modules, frontend behavior and Pi sensors are not claimed as verified by those local tests.

Inspected sources: feature/model-sourcing at 867acaa97a162548b03a347f4f40500b691dc0ec; Ty-Montgomery at 73d85917a3c332db5f255db9db7f5d4e02508cac; Data-Storage at 9202f9e73a108af212e4071e7cffb0f2fa509333. Existing archive hashes were compared to their published Git blobs before reuse.

Primary references: [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output), [GitHub Python testing](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [GitHub token permissions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
