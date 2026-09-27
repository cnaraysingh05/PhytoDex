# Leaf photo diagnosis and My Garden scan history

This branch adds the leaf health diagnosis (`analysis/diagnosis.py`), the final
photo route (`backend/routes/analysis.py`), My Garden scan history, and the
tablet screens for scanning and My Garden. It is built to sit on top of
`feature/model-sourcing` and follows `docs/CONTRACT.md` there.

## How this branch fits the integration branch

This branch is meant to be created from `feature/model-sourcing` and merged
back into it with a normal pull request. Relative to that branch it adds new
files and makes two small edits to shared files:

- `app.py`: adds `backend.routes.garden_scans` and `backend.routes.frontend` to the
  existing optional-module loop, the same way `system` and the photo route are loaded.
- `database/schema.sql`: adds the `photo_assessments` table and its index at the end.

After merging, run `python scripts/init_database.py` once to add the new table
(existing data is kept), then `python -m pytest -q` and
`python scripts/check_readiness.py --require-team`.

## What this branch relies on from the team code

- `analysis/classifier.py` (`classify_leaf`, `AnalysisError`, `ConfigurationError`)
  and `analysis/preprocess.py` (`prepare_image`)
- `backend/routes/photo_bridge.py` (`read_photo`, reused for image and `capture_id` input)
- `backend/models/db.py` (`get_db`, `init_db`), `backend/routes/capture.py`,
  `backend/routes/garden.py`, `backend/routes/plants.py`, `backend/routes/health.py`
- `conftest.py` (temporary database, capture folder, offline mode for tests)
- Gemini settings in the private `.env.ai`: `AI_MODE=gemini`, `GEMINI_API_KEY`,
  `GEMINI_MODEL` (`python scripts/configure_ai.py` creates it; see `.env.ai.example`)

## Photo analysis (matches docs/CONTRACT.md)

`POST /api/analysis` and the alias `POST /api/identify` accept either a multipart
`image` or JSON `{"capture_id": int}` from `POST /api/capture`.

Response: `plant_name` (string or null), `scientific_name` (string or null),
`health_rating` (healthy / attention / concerning / unknown), `visible_signs`,
`possible_causes`, `next_steps` (string arrays), `certainty` (low / medium / high,
never a number), `limitations`, `source` = `gemini`, and `capture_id` when one
was sent. The current classifier schema does not request `scientific_name` or
`next_steps`, so they are null and a generic "General check:" step unless it does.

Errors: 400 bad input or unreadable photo, 404 missing capture, 503 Gemini not
configured, 502 provider or output failure (message is generic). There is no
offline or placeholder assessment. The route never returns a PlantDex plant ID.

## My Garden scan history (proposed contract addition; needs team review)

A stored capture's assessment is kept in `photo_assessments` so it can become
a scan. `plants`, `garden` and `captures` are unchanged; `capture.status` stays
`stored`.

| Route | Input | Output |
|---|---|---|
| GET /api/garden/scan-summaries | none | `{"<garden_id>": {scan_count, latest_scan}}` for plants with scans; `latest_scan` = {capture_id, image_url, scanned_at, health_rating} |
| GET /api/garden/<id> | garden ID | the GET /api/garden fields for that plant, plus `scan_count`, `latest_scan`, `scans` (newest first: capture_id, image_url, scanned_at and the diagnosis fields) and `comparison` {previous, current, note} or null; 404 if missing |
| POST /api/garden/<id>/scans | JSON capture_id | 201 {plant, scan}; 200 if already attached to this plant; 409 if attached to another plant; photo errors as for /api/analysis, nothing attached on failure |

Saving a first scan: the user picks the PlantDex species, then the frontend
calls the existing `POST /api/garden {plant_id, nickname}` and
`POST /api/garden/<id>/scans {capture_id}`. Gemini's `plant_name` is only shown
as a same-name suggestion the user must tap; nothing converts it to a plant ID.
Scans attached to a plant are never overwritten. Deleting a plant with the
existing `DELETE /api/garden/<id>` keeps its photos and assessments, unlinked.

## Screens

`/` (Scan a plant or My Garden), `/scan`, `/scan/<capture_id>` (assessment and
save), `/garden`, `/garden/<id>` (comparison and history), `/garden/<id>/rescan`.
Files: `templates/index.html`, `static/css/phytodex.css`, `static/js/api.js`
(every API call), `static/js/photo.js` (resizes photos on the tablet),
`static/js/ui.js`, `static/js/app.js` (screens).

## Opening it on a tablet

1. Start the app on the Pi so other devices can connect: `HOST=0.0.0.0 python app.py`
2. Find the Pi's address with `hostname -I`.
3. On the tablet (same Wi-Fi), open `http://<that address>:5001`.

"Take photo" and "Choose photo" use the browser's file picker, which works over
plain `http://` on a local network. Photos are shrunk to at most 2048 pixels and
re-saved as JPEG before upload.

## Tests

`tests/test_my_garden.py` (analysis route and scan history, fake Gemini) and
`tests/test_frontend.py` (screens, assets, API routes used by the frontend).
The team's `tests/test_diagnosis.py` and `tests/test_team_photo_contract.py`
also run against this code once it is applied.
