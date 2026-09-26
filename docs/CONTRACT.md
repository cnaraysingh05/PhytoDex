# Shared API contract

The API runs on the Pi; Gemini inference runs on Google's servers. Offline typed guidance is a labeled generic checklist. Photo analysis has no fabricated offline answer. The local MobileNet training code is retained only as an unused experiment and is not part of runtime dependencies.

## Routes

| Route | Input | Output |
|---|---|---|
| GET /api/health | none | {"status":"ok"}; process availability only |
| GET /api/plants?q=poth | optional search/category | list of plant summaries |
| GET /api/plants/1 | plant ID | full care profile, or 404 |
| GET/POST/DELETE /api/garden | existing scaffold contract | persisted garden records |
| POST /api/capture | multipart image | capture_id, image_url, status=stored |
| POST /api/assistant | JSON species (optional), message | likely_causes, what_to_check, recommended_actions, urgency, uncertainty_note, source, model, fallback_reason |
| GET /api/system | none | real hostname, hardware_model, is_raspberry_pi, uptime_seconds, cpu_temperature_c, backend/database/network/gemini status |
| POST /api/analysis | multipart image OR JSON capture_id | final teammate diagnosis response; temporary bridge returns 503 diagnosis_not_ready until diagnosis exists |
| POST /api/identify | legacy alias in temporary bridge | same Gemini photo flow; no TFLite inference |

Assistant input limits: message nonempty and <=3000 characters; species string <=120 or null. Body <=16 KiB. 400 invalid JSON/input, 415 wrong content type, 413 oversized body. Cloud failure returns HTTP 200 with source=fallback, and the UI must visibly label it. Fallback urgency is not assessed; show its uncertainty note.

Photo requests: at most 10 MiB total HTTP body, JPEG/PNG, decoded pixels <=20 million. Capture stores images; analysis validates/normalizes and calls Gemini. Invalid images are 400, missing stored capture is 404, absent diagnosis/configuration is 503, provider/output failure is 502. The temporary bridge leaves capture.status=stored and does not persist photo diagnoses. Do not silently map tentative plant_name into a database plant ID.

## Teammate handoff for issue 2

Your teammate owns `analysis/diagnosis.py` and `backend/routes/analysis.py`. This update deliberately does not create or overwrite either one. The final route should export `analysis_bp`, call `analysis.classifier.classify_leaf(image_bytes)`, then `analysis.diagnosis.build_diagnosis(raw)`, and accept the photo input contract above. Preserve the /api/identify alias if the UI already uses it. Reuse or import the tested `backend.routes.photo_bridge.read_photo` helper if useful.

The temporary bridge is in `backend/routes/photo_bridge.py`. app.py automatically prefers your teammate's final `backend.routes.analysis` module once it exists; it does not register both blueprints. Existing-module import errors are not silently hidden. Tests for the temporary bridge explicitly select it, while the deferred teammate contract test checks the final route separately once present.

Expected final photo fields: plant_name (string/null), visible_signs and possible_causes (string arrays), health_rating (healthy/attention/concerning/unknown), certainty (low/medium/high), limitations (text), source=gemini. No numeric confidence claim. The provided diagnosis tests define string cleanup and unknown-rating behavior and start running automatically when the module appears.

## Database and system status

One DB helper and schema live under backend/models/db.py and database/schema.sql. Initialization adds missing tables; seeding inserts only missing scientific names and preserves IDs. Assistant logging uses this same database. Logging failures do not suppress the care response, but are reported as sanitized backend warnings. There is no public logs endpoint. The optional telemetry table is present for schema compatibility but is not required for live telemetry or written by this change.

System uptime and temperature may be null if the host denies access or lacks the sensor. On a Mac, is_raspberry_pi should be false. network.status reports local interfaces, not internet availability. gemini.status=configured_not_checked means credentials exist, not that an API request succeeded. Reading System makes no paid request and never returns the key.

## CI readiness

Branch pushes run offline tests. Two test modules are visibly skipped until teammate code arrives. PRs targeting main and pushes to main additionally require BOTH teammate photo modules, then fail if absent. Green branch tests mean the available components passed, not that the frontend, physical Pi, model accuracy, internet access or full demo is ready. No Gemini secret belongs in Actions for these tests.
