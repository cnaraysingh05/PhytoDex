// Talks to the Flask backend on the Pi, using the routes in docs/CONTRACT.md.
// The Gemini key never reaches this file: the browser only calls PhytoDex's
// own /api/ routes.

export class ApiError extends Error {
  constructor(message, { status = 0, data = null, kind = "http" } = {}) {
    super(message);
    this.status = status;   // HTTP status, or 0 when the request never arrived
    this.data = data;       // parsed JSON body, if any
    this.kind = kind;       // "http", "network", "timeout" or "bad-response"
  }
}

const NETWORK_MESSAGE =
  "Can't reach the PhytoDex deck. Check that this device is on the same Wi-Fi as the Raspberry Pi and that the app is running, then try again.";

async function request(path, { method = "GET", json, form, timeoutMs = 20000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: json !== undefined ? JSON.stringify(json) : form,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new ApiError("The deck took too long to answer. Check the Wi-Fi connection and try again.", { kind: "timeout" });
    }
    throw new ApiError(NETWORK_MESSAGE, { kind: "network" });
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;  // e.g. an HTML error page
  }
  if (!response.ok) {
    const detail = data && typeof data.error === "string" ? data.error : null;
    let message = detail || `The deck returned an error (${response.status}).`;
    if (response.status === 413) message = "That photo is too large to upload. Try a smaller photo.";
    throw new ApiError(message, { status: response.status, data });
  }
  if (data === null) {
    throw new ApiError("The deck sent a response this screen couldn't read.", { status: response.status, kind: "bad-response" });
  }
  return data;
}

// Photo-analysis failures, using the status codes in docs/CONTRACT.md.
// None of these ever shows a made-up assessment.
export function analysisErrorMessage(error) {
  if (!(error instanceof ApiError) || error.kind !== "http") return error.message;
  switch (error.status) {
    case 400:
      return `This photo couldn't be analyzed: ${error.message}. Take or choose a clear JPEG or PNG photo.`;
    case 404:
      return "This photo is no longer on the deck. Take or choose the photo again.";
    case 503:
      return "Photo analysis isn't set up on this deck. Run python scripts/configure_ai.py on the Pi (it sets AI_MODE=gemini, the Gemini key and model in the private .env.ai file), then restart the app.";
    case 502:
      return "Gemini is unavailable right now, so this photo was not analyzed. Your photo is still on the deck; try the analysis again in a moment.";
    default:
      return error.message;
  }
}

export const api = {
  health: () => request("/api/health", { timeoutMs: 6000 }),

  // POST /api/capture  multipart field "image"  ->  {capture_id, image_url, status}
  capture(blob, filename) {
    const form = new FormData();
    form.append("image", blob, filename);
    return request("/api/capture", { method: "POST", form, timeoutMs: 60000 });
  },

  // POST /api/analysis {capture_id} -> diagnosis fields + capture_id
  analyze: (captureId) =>
    request("/api/analysis", { method: "POST", json: { capture_id: captureId }, timeoutMs: 90000 }),

  // GET /api/garden -> team garden entries (id, plant_id, nickname, common_name, ...)
  garden: () => request("/api/garden"),
  // GET /api/garden/scan-summaries -> {"<garden_id>": {scan_count, latest_scan}}
  scanSummaries: () => request("/api/garden/scan-summaries"),
  gardenPlant: (gardenId) => request(`/api/garden/${gardenId}`),

  // POST /api/garden {plant_id, nickname} -> new garden entry.
  // plant_id is the chosen species or null; the app never confirms a guess.
  createGardenPlant: (plantId, nickname) =>
    request("/api/garden", { method: "POST", json: { plant_id: plantId, nickname } }),

  // POST /api/garden/<id>/scans {capture_id} -> {plant, scan}
  addScan: (gardenId, captureId) =>
    request(`/api/garden/${gardenId}/scans`, { method: "POST", json: { capture_id: captureId }, timeoutMs: 90000 }),

  removePlant: (gardenId) => request(`/api/garden/${gardenId}`, { method: "DELETE" }),

  // PlantDex species library.
  // With no query this returns the whole library; with a query the backend
  // searches common and scientific names.
  plants(query = "") {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request(`/api/plants${suffix}`);
  },

  // GET /api/plants/<id> -> full care profile for one PlantDex species.
  plant: (plantId) => request(`/api/plants/${plantId}`),

  // POST /api/assistant -> structured plant-care guidance.
  // species is optional; message is required.
  askPhyto: (species, message) =>
    request("/api/assistant", {
      method: "POST",
      json: { species: species || null, message },
      timeoutMs: 30000,
    }),

  // GET /api/system -> live status from the machine running PhytoDex.
  system: () => request("/api/system", { timeoutMs: 6000 }),
};
