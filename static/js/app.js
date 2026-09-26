// PhytoDex tablet app: a small router plus one function per screen.
// Flask serves the same page for every address in backend/routes/frontend.py,
// and this file decides which screen to draw for the current address.

import { api, ApiError, analysisErrorMessage } from "./api.js";
import { preparePhoto } from "./photo.js";
import {
  el, icon, photo, placeholder, ratingChip, ratingWord, ratingKey, formatWhen, list, notice,
  button, linkButton, loading, assessmentDetails, evidenceLine,
} from "./ui.js";

const main = document.getElementById("main");
const toastBox = document.getElementById("toast");
let renderCount = 0;
let pendingToast = null;
let highlightCaptureId = null;

// ---------------------------------------------------------------- routing

const ROUTES = [
  [/^\/$/, homeView, null],
  [/^\/scan$/, scanView, "scan"],
  [/^\/scan\/(\d+)$/, resultView, "scan"],
  [/^\/garden$/, gardenView, "garden"],
  [/^\/garden\/(\d+)$/, plantView, "garden"],
  [/^\/garden\/(\d+)\/rescan$/, rescanView, "garden"],
];

export function navigate(path, { replace = false, toast = null } = {}) {
  pendingToast = toast;
  if (replace) history.replaceState({}, "", path);
  else history.pushState({}, "", path);
  render();
}

async function render() {
  const id = ++renderCount;
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const match = ROUTES.map(([pattern, view, nav]) => [path.match(pattern), view, nav]).find(([m]) => m);
  const [params, view, nav] = match || [null, notFoundView, null];

  document.querySelectorAll("[data-nav]").forEach((link) => {
    if (link.dataset.nav === nav) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  const ctx = {
    params: params ? params.slice(1).map(Number) : [],
    isCurrent: () => id === renderCount,
    show(...nodes) {
      if (id !== renderCount) return false;  // the user already moved on
      main.replaceChildren(...nodes.flat().filter((node) => node !== null && node !== undefined && node !== false));
      return true;
    },
    title(text) { if (id === renderCount) document.title = text ? `${text} | PhytoDex` : "PhytoDex"; },
  };

  window.scrollTo(0, 0);
  main.replaceChildren(loading("Loading"));
  try {
    await view(ctx);
  } catch (error) {
    ctx.show(pageError(error));
  }
  if (id === renderCount) {
    main.focus({ preventScroll: true });
    if (pendingToast) { showToast(pendingToast); pendingToast = null; }
  }
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-link]");
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
  const url = new URL(link.href, location.href);
  if (url.origin !== location.origin) return;
  event.preventDefault();
  if (url.pathname !== location.pathname) navigate(url.pathname);
});
window.addEventListener("popstate", render);

function showToast(message) {
  toastBox.textContent = message;
  toastBox.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toastBox.classList.remove("is-visible"), 4200);
}

function pageError(error) {
  const message = error instanceof ApiError ? error.message : "Something unexpected went wrong on this screen.";
  return notice("error", "This screen couldn't load", message,
    button("Try again", { onclick: render }), linkButton("Go home", "/", { variant: "secondary" }));
}

function backLink(href, text) {
  return el("a", { class: "back-link", href, "data-link": true, text: `‹ ${text}` });
}

// ------------------------------------------------------------ deck status

const deckStatus = document.getElementById("deck-status");
async function checkDeck() {
  const label = deckStatus.querySelector(".label");
  try {
    await api.health();
    deckStatus.classList.add("is-online");
    deckStatus.classList.remove("is-offline");
    label.textContent = "Deck connected";
  } catch {
    deckStatus.classList.add("is-offline");
    deckStatus.classList.remove("is-online");
    label.textContent = "Deck offline";
  }
}
window.addEventListener("online", checkDeck);
window.addEventListener("offline", checkDeck);
setInterval(checkDeck, 30000);

// ------------------------------------------------ scan results in the tab
// A result lives in this browser tab until it is saved. Refreshing the page
// shows it again without calling Gemini a second time.

const resultKey = (captureId) => `phytodex:scan:${captureId}`;
function storeResult(result) {
  try { sessionStorage.setItem(resultKey(result.capture_id), JSON.stringify(result)); } catch { /* private mode */ }
}
function readResult(captureId) {
  try { return JSON.parse(sessionStorage.getItem(resultKey(captureId))); } catch { return null; }
}

// ------------------------------------------------------ photo capture UI

function progressList(labels, note) {
  const items = labels.map((text) => el("li", {}, el("span", { class: "mark", "aria-hidden": "true" }), el("span", { text })));
  const element = el("ol", { class: "progress", "aria-live": "polite" }, items, note ? el("li", { class: "progress-note", text: note }) : null);
  return {
    element,
    step(index) {
      items.forEach((item, i) => {
        item.classList.toggle("is-done", i < index);
        item.classList.toggle("is-active", i === index);
      });
    },
  };
}

// Two buttons: "Take photo" opens the camera, "Choose photo" opens the photo
// library. File inputs work over plain http:// on the local network, where
// browsers block live camera streams.
function photoCapture({ actionLabel, steps, note, run }) {
  let prepared = null;
  let busy = false;
  let attempt = {};  // remembers the capture_id so a retry doesn't re-upload

  const accept = "image/jpeg,image/png";
  const takeInput = el("input", { type: "file", accept, capture: "environment", class: "file-input", tabindex: "-1", "aria-hidden": "true" });
  const chooseInput = el("input", { type: "file", accept, class: "file-input", tabindex: "-1", "aria-hidden": "true" });
  const frame = el("div", { class: "viewfinder" },
    el("div", { class: "empty-frame" }, icon("camera"), el("p", { text: "Frame the whole plant and any affected leaves in good, even light." })));
  const status = el("div", { class: "capture-status" });
  const takeButton = button("Take photo", { variant: "secondary", iconName: "camera", onclick: () => takeInput.click() });
  const chooseButton = button("Choose photo", { variant: "secondary", iconName: "image", onclick: () => chooseInput.click() });
  const actionButton = button(actionLabel, { iconName: "leaf", onclick: start });
  actionButton.disabled = true;

  function setBusy(value) {
    busy = value;
    takeButton.disabled = value;
    chooseButton.disabled = value;
    actionButton.disabled = value || !prepared;
  }

  async function onFile(event) {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";  // lets the same photo be picked again
    if (!file || busy) return;
    status.replaceChildren();
    try {
      const next = await preparePhoto(file);
      if (prepared) URL.revokeObjectURL(prepared.previewUrl);
      prepared = next;
      attempt = {};
      frame.replaceChildren(el("img", { src: prepared.previewUrl, alt: "Selected plant photo" }));
      actionButton.disabled = false;
    } catch (error) {
      status.replaceChildren(notice("error", "This photo can't be used", error.message));
    }
  }
  takeInput.addEventListener("change", onFile);
  chooseInput.addEventListener("change", onFile);

  async function start() {
    if (!prepared || busy) return;
    setBusy(true);
    const progress = progressList(steps, note);
    status.replaceChildren(progress.element);
    try {
      await run(prepared, progress, attempt);
    } catch (error) {
      status.replaceChildren(notice("error", error.title || "That didn't work", error.message,
        button(error.retryLabel || "Try again", { onclick: start })));
    } finally {
      setBusy(false);
    }
  }

  return el("div", { class: "capture" }, frame, takeInput, chooseInput,
    el("div", { class: "btn-row" }, takeButton, chooseButton), el("div", { class: "btn-row" }, actionButton), status);
}

function stepError(title, message, retryLabel) {
  const error = new Error(message);
  error.title = title;
  error.retryLabel = retryLabel;
  return error;
}

async function uploadStep(prepared, attempt) {
  if (attempt.captureId) return;  // already on the deck from an earlier try
  try {
    const stored = await api.capture(prepared.blob, prepared.filename);
    attempt.captureId = stored.capture_id;
    attempt.imageUrl = stored.image_url;
  } catch (error) {
    throw stepError("Upload failed", error.message, "Try the upload again");
  }
}

// ------------------------------------------------------------------ home

async function homeView(ctx) {
  ctx.title("");
  const gardenLine = el("span", { text: "Follow saved plants over time" });
  ctx.show(
    el("section", { class: "home-intro" },
      el("h1", { text: "Check on a plant" }),
      el("p", { text: "Scan a plant to see what Gemini notices in the photo, or open My Garden to follow a plant you've saved over time." })),
    el("div", { class: "choices" },
      el("a", { class: "choice choice-scan", href: "/scan", "data-link": true },
        icon("sprout", "choice-art"), el("strong", { text: "Scan a plant" }), el("span", { text: "Take or choose a photo" })),
      el("a", { class: "choice choice-garden", href: "/garden", "data-link": true },
        icon("sprout", "choice-art"), el("strong", { text: "My Garden" }), gardenLine)));
  try {
    const garden = await api.garden();
    gardenLine.textContent = garden.length ? `${garden.length} saved ${garden.length === 1 ? "plant" : "plants"}` : "No plants saved yet";
  } catch {
    // The rest of the home screen still works; the deck status shows the problem.
  }
}

// ------------------------------------------------------------ scan a plant

async function scanView(ctx) {
  ctx.title("Scan a plant");
  const capture = photoCapture({
    actionLabel: "Analyze photo",
    steps: ["Upload the photo to the deck", "Gemini examines the plant"],
    note: "Keep this screen open while Gemini looks at the photo.",
    async run(prepared, progress, attempt) {
      progress.step(0);
      await uploadStep(prepared, attempt);
      progress.step(1);
      let assessment;
      try {
        assessment = await api.analyze(attempt.captureId);
      } catch (error) {
        throw stepError("No analysis yet", analysisErrorMessage(error), "Try the analysis again");
      }
      progress.step(2);
      storeResult({ ...assessment, image_url: attempt.imageUrl, analyzed_at: new Date().toISOString(), saved_garden_id: null });
      navigate(`/scan/${attempt.captureId}`);
    },
  });
  ctx.show(
    el("div", { class: "page-head" },
      el("h1", { text: "Scan a plant" }),
      el("p", { text: "Take a new photo or choose one you already have. Gemini describes what it can see; it can't test soil or roots." })),
    capture);
}

// -------------------------------------------------------------- scan result

async function resultView(ctx) {
  const [captureId] = ctx.params;
  ctx.title("Scan result");
  const result = readResult(captureId);
  if (!result) {
    ctx.show(el("div", { class: "page-head" }, el("h1", { text: "This result isn't on this screen anymore" }),
      el("p", { text: "Scan results are kept in this browser tab until you save them. Saved scans are always in My Garden." })),
      el("div", { class: "btn-row" }, linkButton("Scan a plant", "/scan", { iconName: "camera" }), linkButton("Open My Garden", "/garden", { variant: "secondary" })));
    return;
  }

  const identified = Boolean(result.plant_name);
  const unknownRating = ratingKey(result.health_rating) === "unknown";
  const label = el("article", { class: "label-card", "aria-labelledby": "plant-title" },
    el("span", { class: "label-source", text: `Live Gemini assessment, ${formatWhen(result.analyzed_at.replace("T", " ").slice(0, 19))}` }),
    el("h1", { id: "plant-title", class: `plant-title${identified ? "" : " is-unknown"}`, text: result.plant_name || "Unidentified plant" }),
    result.scientific_name ? el("p", { class: "sci-name", text: result.scientific_name }) : null,
    el("p", { class: "library-line", text: identified
      ? "Gemini's name is a tentative identification from one photo."
      : "Gemini couldn't identify the species from this photo." }),
    el("div", { class: "reading" }, ratingWord(result.health_rating), evidenceLine(result.certainty)),
    assessmentDetails(result));

  ctx.show(
    backLink("/scan", "Scan another plant"),
    unknownRating && !identified
      ? notice("warn", "Gemini couldn't assess a plant in this photo", "A clearer photo of the whole plant in good light will give a better result.",
        linkButton("Retake photo", "/scan", { variant: "secondary", iconName: "camera" }))
      : null,
    el("div", { class: "specimen" },
      el("figure", { class: "mount", style: "margin:0" }, photo(result.image_url, "The photo Gemini assessed", { eager: true }),
        el("figcaption", { text: "The photo Gemini assessed" })),
      el("div", {}, label, savePanel(result))));
}

// Exact name match only, shown as a suggestion the user has to accept.
function suggestSpecies(plants, result) {
  const names = [result.scientific_name, result.plant_name].filter(Boolean).map((name) => name.trim().toLowerCase());
  return plants.find((plant) => names.includes((plant.scientific_name || "").toLowerCase())
    || names.includes((plant.common_name || "").toLowerCase())) || null;
}

function savePanel(result) {
  if (result.saved_garden_id && result.scan_attached) {
    return el("section", { class: "save-panel" }, el("h2", { text: "Saved to My Garden" }),
      el("p", { class: "lead", text: "This scan is the first entry in the plant's history." }),
      linkButton("Open this plant", `/garden/${result.saved_garden_id}`, { iconName: "pot" }));
  }

  const nickname = el("input", { id: "nickname", name: "nickname", maxlength: "60", autocomplete: "off", placeholder: "Desk Pothos", required: true });
  const nicknameError = el("p", { class: "field-error", id: "nickname-error", role: "alert" });
  const species = el("select", { id: "species", name: "species", disabled: true, required: true },
    el("option", { value: "", text: "Loading PlantDex species" }));
  const speciesError = el("p", { class: "field-error", id: "species-error", role: "alert" });
  const suggestion = el("div", { "aria-live": "polite" });
  const status = el("div", { "aria-live": "polite" });
  const saveButton = button("Save to My Garden", { iconName: "pot", type: "submit" });
  let speciesReady = false;

  if (result.saved_garden_id) {
    // The plant was created but its first scan wasn't linked (connection lost).
    status.replaceChildren(notice("warn", "Plant created, scan not linked yet", "Tap Save to My Garden again to add this scan to the plant."));
  }

  api.plants().then((plants) => {
    species.replaceChildren(
      el("option", { value: "", text: "Choose a PlantDex species" }),
      ...plants.map((plant) => el("option", { value: String(plant.id), text: plant.scientific_name ? `${plant.common_name} (${plant.scientific_name})` : plant.common_name })));
    species.disabled = false;
    speciesReady = true;
    const match = suggestSpecies(plants, result);
    if (match) {
      suggestion.replaceChildren(el("p", { class: "hint" }, `PlantDex has a species with the same name as Gemini's guess: ${match.common_name}. `,
        button(`Use ${match.common_name}`, { variant: "secondary", onclick: () => { species.value = String(match.id); speciesError.textContent = ""; } })));
    } else {
      suggestion.replaceChildren(el("p", { class: "hint", text: result.plant_name
        ? `"${result.plant_name}" isn't in PlantDex. My Garden plants are linked to a PlantDex species, so choose one only if it's truly this plant.`
        : "Choose the species if you know it. My Garden plants are linked to a PlantDex species." }));
    }
  }).catch((error) => {
    species.replaceChildren(el("option", { value: "", text: "PlantDex list unavailable" }));
    speciesError.textContent = `The species list couldn't load, so this plant can't be saved yet. ${error.message}`;
  });

  async function save(event) {
    event.preventDefault();
    nicknameError.textContent = "";
    speciesError.textContent = "";
    const name = nickname.value.trim();
    if (!result.saved_garden_id && !name) {
      nicknameError.textContent = "Give this plant a nickname, like Desk Pothos.";
      nickname.focus();
      return;
    }
    if (!result.saved_garden_id && (!speciesReady || !species.value)) {
      speciesError.textContent = "Choose the PlantDex species for this plant.";
      species.focus();
      return;
    }
    saveButton.disabled = true;
    status.replaceChildren(loading("Saving to My Garden"));
    try {
      let gardenId = result.saved_garden_id;
      if (!gardenId) {
        const created = await api.createGardenPlant(Number(species.value), name);
        gardenId = created.id;
        result.saved_garden_id = gardenId;
        storeResult(result);
      }
      const { plant } = await api.addScan(gardenId, result.capture_id);
      result.scan_attached = true;
      storeResult(result);
      navigate(`/garden/${gardenId}`, { toast: `Saved ${plant.nickname || "this plant"} to My Garden` });
    } catch (error) {
      saveButton.disabled = false;
      const other = error instanceof ApiError && error.status === 409 && error.data && error.data.garden_id;
      status.replaceChildren(other
        ? notice("info", "Already saved", "This scan is already in My Garden.", linkButton("Open that plant", `/garden/${error.data.garden_id}`, { variant: "secondary" }))
        : notice("error", "Not saved", result.saved_garden_id
          ? `The plant was created, but its first scan wasn't linked: ${analysisErrorMessage(error)}`
          : error.message));
    }
  }

  return el("form", { class: "save-panel", onsubmit: save, novalidate: true },
    el("h2", { text: "Save this plant to My Garden" }),
    el("p", { class: "lead", text: "Saving starts a history for this one plant. Rescan it later to compare scans over time." }),
    result.saved_garden_id ? null : el("div", { class: "field" }, el("label", { for: "nickname", text: "Nickname" }), nickname, nicknameError),
    result.saved_garden_id ? null : el("div", { class: "field" }, el("label", { for: "species", text: "PlantDex species" }), species, suggestion, speciesError),
    el("div", { class: "btn-row" }, saveButton), status);
}

// ---------------------------------------------------------------- garden

function speciesText(plant) {
  return plant.common_name || "Unknown species";
}

async function gardenView(ctx) {
  ctx.title("My Garden");
  // Team garden entries, plus scan counts and latest scans from this feature.
  const [plants, summaries] = await Promise.all([api.garden(), api.scanSummaries()]);
  for (const plant of plants) {
    const summary = summaries[String(plant.id)];
    plant.scan_count = summary ? summary.scan_count : 0;
    plant.latest_scan = summary ? summary.latest_scan : null;
  }
  const head = el("div", { class: "list-head" },
    el("div", { class: "page-head" }, el("h1", { text: "My Garden" }),
      el("p", { text: "Each entry is one plant you own. Two plants of the same species each get their own history." })),
    plants.length ? linkButton("Scan a new plant", "/scan", { iconName: "camera" }) : null);

  if (!plants.length) {
    ctx.show(head, el("section", { class: "empty-state" }, icon("sprout"),
      el("h2", { text: "No plants saved yet" }),
      el("p", { text: "Scan a plant, give it a nickname, and save it here. Each rescan adds a dated entry to its history." }),
      linkButton("Scan your first plant", "/scan", { iconName: "camera" })));
    return;
  }

  ctx.show(head, el("ul", { class: "garden-grid" }, plants.map((plant) => {
    const latest = plant.latest_scan;
    return el("li", {}, el("a", { class: "plant-card", href: `/garden/${plant.id}`, "data-link": true },
      el("div", { class: "thumb" }, latest ? photo(latest.image_url, "") : placeholder()),
      el("div", { class: "body" },
        el("span", { class: "nick", text: plant.nickname || "Unnamed plant" }),
        el("span", { class: "species", text: speciesText(plant) }),
        el("div", { class: "meta" },
          latest ? ratingChip(latest.health_rating) : el("span", { text: "No scans yet" }),
          plant.scan_count ? el("span", { text: `${plant.scan_count} ${plant.scan_count === 1 ? "scan" : "scans"}, latest ${formatWhen(latest.scanned_at, { withTime: false }).replace(/^(Today|Yesterday)$/, (day) => day.toLowerCase())}` }) : null,
          null))));
  })));
}

async function loadGardenPlant(ctx, gardenId) {
  try {
    return await api.gardenPlant(gardenId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      ctx.show(el("div", { class: "page-head" }, el("h1", { text: "This plant isn't in My Garden" }),
        el("p", { text: "It may have been removed." })), linkButton("Open My Garden", "/garden"));
      return null;
    }
    throw error;
  }
}

async function plantView(ctx) {
  const [gardenId] = ctx.params;
  const plant = await loadGardenPlant(ctx, gardenId);
  if (!plant) return;
  ctx.title(plant.nickname);

  const speciesLine = el("p", {}, speciesText(plant),
    plant.scientific_name ? el("span", { class: "sci-name", text: ` ${plant.scientific_name}` }) : null);

  const head = el("div", { class: "plant-head" },
    el("div", { class: "page-head" }, el("h1", { text: plant.nickname || "Unnamed plant" }), speciesLine),
    linkButton("Rescan this plant", `/garden/${plant.id}/rescan`, { iconName: "refresh" }));

  let compare;
  if (plant.comparison) {
    const { previous, current, note } = plant.comparison;
    const column = (heading, scan) => el("div", { class: "compare-col" },
      el("h3", { text: heading }), el("span", { class: "when", text: formatWhen(scan.scanned_at) }),
      ratingWord(scan.health_rating), evidenceLine(scan.certainty),
      list(scan.visible_signs, "No visible signs listed."));
    compare = el("section", { class: "compare", "aria-labelledby": "compare-title" },
      el("h2", { id: "compare-title", text: "Previous and latest scan" }),
      el("div", { class: "compare-grid" }, column("Previous", previous), column("Latest", current)),
      el("p", { class: "compare-note", text: note }));
  } else if (plant.scan_count === 1) {
    compare = notice("info", null, "Rescan this plant later to see the previous and latest scans side by side.");
  } else if (plant.scan_count === 0) {
    compare = notice("info", null, "This plant has no scans yet. Rescan it to start its history.");
  }

  const newest = plant.scans.length ? plant.scans[0].capture_id : null;
  const oldest = plant.scans.length ? plant.scans[plant.scans.length - 1].capture_id : null;
  const history = plant.scans.length ? el("section", { "aria-labelledby": "history-title" },
    el("h2", { id: "history-title", text: "Scan history, newest first" }),
    el("ol", { class: "history" }, plant.scans.map((scan) => {
      const seenAs = scan.plant_name && scan.plant_name.toLowerCase() !== (plant.common_name || "").toLowerCase()
        ? el("p", { class: "seen-as", text: `Gemini saw: ${scan.plant_name}` }) : null;
      return el("li", { class: `scan-entry${scan.capture_id === highlightCaptureId ? " is-new" : ""}` },
        el("figure", { class: "mount", style: "margin:0" }, photo(scan.image_url, `Scan from ${formatWhen(scan.scanned_at)}`)),
        el("div", {},
          el("div", { class: "top" },
            el("span", { class: "when", text: formatWhen(scan.scanned_at) }),
            ratingChip(scan.health_rating),
            scan.capture_id === newest && plant.scans.length > 1 ? el("span", { class: "tag", text: "Latest" }) : null,
            scan.capture_id === oldest ? el("span", { class: "tag", text: "First scan" }) : null),
          seenAs,
          evidenceLine(scan.certainty),
          el("section", { class: "finding" }, el("h3", { text: "What's visible" }), list(scan.visible_signs, "No visible signs were listed.")),
          el("details", {}, el("summary", { text: "Causes, next steps and limits" }), assessmentDetails(scan).slice(1))));
    }))) : null;
  highlightCaptureId = null;

  ctx.show(backLink("/garden", "My Garden"), head, compare, history, removeSection(plant));
}

function removeSection(plant) {
  let armed = false;
  const status = el("div", { "aria-live": "polite" });
  const removeButton = button("Remove from My Garden", { variant: "danger", onclick: async () => {
    if (!armed) {
      armed = true;
      removeButton.classList.add("is-confirming");
      removeButton.textContent = "Tap again to remove";
      setTimeout(() => {
        armed = false;
        removeButton.classList.remove("is-confirming");
        removeButton.textContent = "Remove from My Garden";
      }, 5000);
      return;
    }
    removeButton.disabled = true;
    try {
      await api.removePlant(plant.id);
      navigate("/garden", { replace: true, toast: `Removed ${plant.nickname} from My Garden` });
    } catch (error) {
      removeButton.disabled = false;
      status.replaceChildren(notice("error", "Not removed", error.message));
    }
  } });
  return el("section", { class: "danger-zone" },
    el("p", { text: "Removing takes this plant out of My Garden. Its photos stay on the deck." }), removeButton, status);
}

async function rescanView(ctx) {
  const [gardenId] = ctx.params;
  const plant = await loadGardenPlant(ctx, gardenId);
  if (!plant) return;
  const name = plant.nickname || "this plant";
  ctx.title(`Rescan ${name}`);

  const capture = photoCapture({
    actionLabel: "Analyze and add to history",
    steps: ["Upload the photo to the deck", `Gemini examines ${name} and adds the scan to its history`],
    note: "Earlier scans stay exactly as they are.",
    async run(prepared, progress, attempt) {
      progress.step(0);
      await uploadStep(prepared, attempt);
      progress.step(1);
      let response;
      try {
        response = await api.addScan(plant.id, attempt.captureId);
      } catch (error) {
        throw stepError("Scan not added", analysisErrorMessage(error), "Try again");
      }
      progress.step(2);
      highlightCaptureId = response.scan.capture_id;
      navigate(`/garden/${plant.id}`, { replace: true, toast: `New scan added to ${name}` });
    },
  });

  const last = plant.scans[0];
  ctx.show(backLink(`/garden/${plant.id}`, name),
    el("div", { class: "page-head" }, el("h1", { text: `Rescan ${name}` }),
      el("p", { text: "This scan is added to this plant's history. Matching the angle and light of the last photo makes the comparison easier." })),
    last ? el("p", { class: "library-line", text: `Last scan: ${formatWhen(last.scanned_at)}` }) : null,
    capture);
}

// ---------------------------------------------------------------- 404

async function notFoundView(ctx) {
  ctx.title("Page not found");
  ctx.show(el("div", { class: "page-head" }, el("h1", { text: "Page not found" })), linkButton("Go home", "/"));
}

checkDeck();
render();
