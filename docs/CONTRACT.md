# AI integration contract

`POST /api/assistant` accepts JSON with required `message` (nonempty string, max 3000 characters) and optional `species` (string, max 120, or null). No camera required.

```json
{"species":"Pothos","message":"Yellow leaves and soil is staying wet."}
```

Response fields: `likely_causes`, `what_to_check`, `recommended_actions` are nonempty arrays of strings; `urgency` is `low|medium|high`; `uncertainty_note` is text; `source` is `gemini|fallback`; added diagnostic fields are `model` (string/null), `fallback_reason` (string/null). Frontend should render text as text, not HTML.

Missing/invalid input: 400. Wrong content type: 415. Oversized body: 413. Provider failure: 200 with `source=fallback` and a generic checklist. The frontend must show the fallback state and uncertainty; fallback urgency is not an assessment.

The assistant import hook in the inspected scaffold works without changing app.py. Dependencies in requirements-ai.txt must be installed in the backend environment. Use scripts/integrate_ai_dependencies.py to update the scaffold’s Flask 3.0.3 pin to Flask >=3.1.3, required for per-request size limits, and include these dependencies; review this with the backend owner. Environment files are read from repository root. `.env.ai` takes precedence over `.env`, and process variables take precedence over both. Restart after changing configuration. Real provider responses are not persisted or cached by this kit.

## Optional photo route

`POST /api/identify` accepts either multipart form field `image` (JPEG/PNG, request <=8 MiB, image <=20 million pixels) or JSON `{"capture_id": integer}` in the integrated backend. Register the route using the provided script. The standalone server supports file upload; capture IDs need the team DB.

Response has `status` (`candidate|uncertain`), `label` (string/null), top-three `candidates` (`label`, `score`), `threshold`, `source=local_mobilenetv2`, `latency_ms`, and `uncertainty_note`. Scores are model outputs, not calibrated confidence in botanical identity. `candidate` still requires manual confirmation. Do not silently map these category strings to a database plant ID.

Missing capture: 404. Bad request/image: 400. Missing/incompatible model/runtime: 503. Existing capture rows are read only; this kit does not create a results table or update `captures.status`.

Typed assistant model: remotely hosted Gemini. Photo model: locally executed MobileNetV2 once trained and deployed. Auth/rate controls for public hosting are outside this private-network demo integration.
