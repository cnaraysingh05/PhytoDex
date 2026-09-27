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
  [/^\/plantdex$/, plantDexView, "plantdex"],
  [/^\/plantdex\/(\d+)$/, plantDexPlantView, "plantdex"],
  [/^\/ask$/, askPhytoView, "ask"],
  [/^\/system$/, systemView, "system"],
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
  const names = [result.scientific_name, result.plant_name].filter(Boolean)
    .flatMap((name) => name.split(/[()]/)).map((name) => name.trim().toLowerCase()).filter(Boolean);
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
  const species = el("select", { id: "species", name: "species", disabled: true },
    el("option", { value: "", text: "Unknown / not linked to PlantDex" }));
  const speciesError = el("p", { class: "field-error", id: "species-error", role: "alert" });
  const suggestion = el("div", { "aria-live": "polite" });
  const status = el("div", { "aria-live": "polite" });
  const saveButton = button("Save to My Garden", { iconName: "pot", type: "submit" });

  if (result.saved_garden_id) {
    // The plant was created but its first scan wasn't linked (connection lost).
    status.replaceChildren(notice("warn", "Plant created, scan not linked yet", "Tap Save to My Garden again to add this scan to the plant."));
  }

  api.plants().then((plants) => {
    species.replaceChildren(
      el("option", { value: "", text: "Unknown / not linked to PlantDex" }),
      ...plants.map((plant) => el("option", { value: String(plant.id), text: plant.scientific_name ? `${plant.common_name} (${plant.scientific_name})` : plant.common_name })));
    species.disabled = false;
    const match = suggestSpecies(plants, result);
    if (match) {
      suggestion.replaceChildren(el("p", { class: "hint" }, `PlantDex has a species with the same name as Gemini's guess: ${match.common_name}. `,
        button(`Use ${match.common_name}`, { variant: "secondary", onclick: () => { species.value = String(match.id); speciesError.textContent = ""; } })));
    } else {
      suggestion.replaceChildren(el("p", { class: "hint", text: result.plant_name
        ? `Gemini suggested "${result.plant_name}". You can save it without confirming a species.`
        : "Link a species only if you know it. Otherwise, save it as unidentified." }));
    }
  }).catch((error) => {
    species.replaceChildren(el("option", { value: "", text: "PlantDex list unavailable" }));
    speciesError.textContent = `The species list couldn't load. You can still save this plant without a species. ${error.message}`;
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
    saveButton.disabled = true;
    status.replaceChildren(loading("Saving to My Garden"));
    try {
      let gardenId = result.saved_garden_id;
      if (!gardenId) {
        const created = await api.createGardenPlant(species.value ? Number(species.value) : null, name);
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
    result.saved_garden_id ? null : el("div", { class: "field" }, el("label", { for: "species", text: "PlantDex species (optional)" }), species, suggestion, speciesError),
    el("div", { class: "btn-row" }, saveButton), status);
}

// --------------------------------------------------------------- PlantDex

function plantDexCard(plant) {
  const details = [plant.category, plant.difficulty].filter(Boolean);

  return el("li", {},
    el("a", {
      class: "plant-card plantdex-card",
      href: `/plantdex/${plant.id}`,
      "data-link": true,
    },
      el("div", { class: "thumb" },
        photo(plant.image_url, plant.common_name || "Plant")),
      el("div", { class: "body" },
        el("span", {
          class: "nick",
          text: plant.common_name || "Unnamed plant",
        }),
        plant.scientific_name
          ? el("span", {
              class: "species sci-name",
              text: plant.scientific_name,
            })
          : null,
        details.length
          ? el("div", { class: "meta" },
              details.map((value) => el("span", { text: value })))
          : null
      )
    )
  );
}

async function plantDexView(ctx) {
  ctx.title("PlantDex");

  const search = el("input", {
    id: "plantdex-search",
    type: "search",
    name: "q",
    placeholder: "Search Pothos, Monstera, basil...",
    autocomplete: "off",
    enterkeyhint: "search",
  });

  const count = el("p", {
    class: "library-line plantdex-count",
    "aria-live": "polite",
  });

  const results = el("div", {
    class: "plantdex-results",
    "aria-live": "polite",
  });

  let requestNumber = 0;

  async function loadPlants(query = "") {
    const currentRequest = ++requestNumber;
    results.replaceChildren(loading(query ? "Searching PlantDex" : "Loading PlantDex"));

    try {
      const plants = await api.plants(query);

      if (!ctx.isCurrent() || currentRequest !== requestNumber) return;

      const description = query
        ? `${plants.length} ${plants.length === 1 ? "match" : "matches"} for "${query}"`
        : `${plants.length} ${plants.length === 1 ? "plant" : "plants"} in the library`;

      count.textContent = description;

      if (!plants.length) {
        results.replaceChildren(
          el("section", { class: "empty-state" },
            icon("sprout"),
            el("h2", { text: "No plants found" }),
            el("p", {
              text: `PlantDex does not have a plant matching "${query}". Try another common or scientific name.`,
            })
          )
        );
        return;
      }

      results.replaceChildren(
        el("ul", { class: "garden-grid plantdex-grid" },
          plants.map(plantDexCard))
      );
    } catch (error) {
      if (!ctx.isCurrent() || currentRequest !== requestNumber) return;

      count.textContent = "";
      results.replaceChildren(
        notice(
          "error",
          "PlantDex couldn't load",
          error.message,
          button("Try again", {
            onclick: () => loadPlants(search.value.trim()),
          })
        )
      );
    }
  }

  const clearButton = button("Clear", {
    variant: "secondary",
    onclick: () => {
      search.value = "";
      search.focus();
      loadPlants();
    },
  });

  const form = el("form", {
    class: "plantdex-search",
    role: "search",
    onsubmit: (event) => {
      event.preventDefault();
      loadPlants(search.value.trim());
    },
  },
    el("div", { class: "field" },
      el("label", {
        for: "plantdex-search",
        text: "Search the plant library",
      }),
      search
    ),
    el("div", { class: "btn-row" },
      button("Search", { type: "submit", iconName: "leaf" }),
      clearButton
    )
  );

  ctx.show(
    el("div", { class: "page-head" },
      el("h1", { text: "PlantDex" }),
      el("p", {
        text: "Browse the care library by common or scientific name, then open a plant for its saved care profile.",
      })
    ),
    form,
    count,
    results
  );

  await loadPlants();
}

async function plantDexPlantView(ctx) {
  const [plantId] = ctx.params;

  let plant;

  try {
    plant = await api.plant(plantId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      ctx.title("Plant not found");
      ctx.show(
        backLink("/plantdex", "PlantDex"),
        el("div", { class: "page-head" },
          el("h1", { text: "Plant not found" }),
          el("p", {
            text: "This PlantDex entry does not exist or may have been removed.",
          })
        ),
        linkButton("Back to PlantDex", "/plantdex")
      );
      return;
    }

    throw error;
  }

  ctx.title(plant.common_name || "PlantDex plant");

  const careFields = [
    ["Water", plant.water],
    ["Light", plant.light],
    ["Soil", plant.soil],
    ["Temperature", plant.temperature],
    ["Difficulty", plant.difficulty],
    ["Category", plant.category],
  ].filter(([, value]) => value);

  const careGrid = el("dl", { class: "care-grid" },
    careFields.flatMap(([label, value]) => [
      el("div", { class: "care-item" },
        el("dt", { text: label }),
        el("dd", { text: value })
      ),
    ])
  );

  ctx.show(
    backLink("/plantdex", "PlantDex"),
    el("div", { class: "plantdex-profile" },
      el("figure", { class: "mount plantdex-photo", style: "margin:0" },
        photo(
          plant.image_url,
          plant.common_name || "PlantDex plant",
          { eager: true }
        )
      ),
      el("article", { class: "label-card plantdex-details" },
        el("span", {
          class: "label-source",
          text: "PlantDex care profile",
        }),
        el("h1", {
          class: "plant-title",
          text: plant.common_name || "Unnamed plant",
        }),
        plant.scientific_name
          ? el("p", {
              class: "sci-name",
              text: plant.scientific_name,
            })
          : null,
        plant.summary
          ? el("p", {
              class: "plantdex-summary",
              text: plant.summary,
            })
          : null,
        careGrid
      )
    )
  );
}

// -------------------------------------------------------------- Ask Phyto

function guidanceSection(title, items, emptyText) {
  return el("section", { class: "guidance-section" },
    el("h2", { text: title }),
    list(items, emptyText));
}

function guidanceResult(result) {
  const isLive = result.source === "gemini";
  const urgency = ["low", "medium", "high"].includes(result.urgency)
    ? result.urgency
    : "unknown";

  return el("article", { class: "assistant-result" },
    isLive
      ? el("div", { class: "assistant-source assistant-source-live" },
          el("strong", { text: "Live Gemini guidance" }),
          result.model
            ? el("span", { text: `Model: ${result.model}` })
            : null)
      : el("div", { class: "assistant-source assistant-source-fallback" },
          el("strong", { text: "Offline fallback guidance" }),
          el("span", {
            text: "Gemini did not provide this answer. PhytoDex is showing its built-in general checklist.",
          })),

    el("div", { class: "guidance-urgency" },
      el("span", { text: "Urgency" }),
      el("strong", {
        class: `urgency urgency-${urgency}`,
        text: urgency === "unknown"
          ? "Not assessed"
          : urgency.charAt(0).toUpperCase() + urgency.slice(1),
      })),

    guidanceSection(
      "Likely causes",
      result.likely_causes,
      "No likely causes were returned."
    ),

    guidanceSection(
      "What to check",
      result.what_to_check,
      "No checks were returned."
    ),

    guidanceSection(
      "Recommended actions",
      result.recommended_actions,
      "No actions were returned."
    ),

    el("section", { class: "guidance-section guidance-uncertainty" },
      el("h2", { text: "Limits and uncertainty" }),
      el("p", {
        text: result.uncertainty_note ||
          "PhytoDex did not receive an uncertainty note.",
      }))
  );
}

async function askPhytoView(ctx) {
  ctx.title("Ask Phyto");

  const species = el("input", {
    id: "ask-species",
    name: "species",
    type: "text",
    maxlength: "120",
    list: "ask-species-list",
    autocomplete: "off",
    placeholder: "Pothos (optional)",
  });

  const speciesList = el("datalist", {
    id: "ask-species-list",
  });

  const message = el("textarea", {
    id: "ask-message",
    name: "message",
    maxlength: "3000",
    rows: "6",
    placeholder: "Example: The lower leaves are yellow and the soil stays wet. What should I check?",
    required: true,
  });

  const errorBox = el("p", {
    class: "field-error",
    role: "alert",
  });

  const resultBox = el("div", {
    class: "assistant-output",
    "aria-live": "polite",
  });

  const submitButton = button("Ask Phyto", {
    type: "submit",
    iconName: "leaf",
  });

  // PlantDex provides suggestions, but users can still type any species.
  api.plants()
    .then((plants) => {
      speciesList.replaceChildren(
        ...plants.map((plant) =>
          el("option", {
            value: plant.common_name,
            label: plant.scientific_name || plant.common_name,
          }))
      );
    })
    .catch(() => {
      // Ask Phyto still works without PlantDex suggestions.
    });

  async function submit(event) {
    event.preventDefault();

    const question = message.value.trim();
    const plantSpecies = species.value.trim();

    errorBox.textContent = "";

    if (!question) {
      errorBox.textContent = "Enter a plant-care question for Phyto.";
      message.focus();
      return;
    }

    submitButton.disabled = true;
    resultBox.replaceChildren(loading("Phyto is checking your question"));

    try {
      const result = await api.askPhyto(plantSpecies, question);

      if (!ctx.isCurrent()) return;

      resultBox.replaceChildren(guidanceResult(result));
    } catch (error) {
      if (!ctx.isCurrent()) return;

      resultBox.replaceChildren(
        notice(
          "error",
          "Phyto couldn't answer",
          error.message,
          button("Try again", {
            variant: "secondary",
            onclick: () =>
              form.dispatchEvent(
                new Event("submit", { cancelable: true })
              ),
          })
        )
      );
    } finally {
      submitButton.disabled = false;
    }
  }

  const form = el("form", {
    class: "assistant-form",
    onsubmit: submit,
    novalidate: true,
  },
    el("div", { class: "field" },
      el("label", {
        for: "ask-species",
        text: "Species (optional)",
      }),
      species,
      speciesList,
      el("p", {
        class: "hint",
        text: "Choose a PlantDex suggestion or type another species. Leave it blank if you're not sure.",
      })
    ),

    el("div", { class: "field" },
      el("label", {
        for: "ask-message",
        text: "What do you want to know?",
      }),
      message,
      el("p", {
        class: "hint",
        text: "Include useful details like watering, drainage, light, and how long the symptoms have been present.",
      }),
      errorBox
    ),

    el("div", { class: "btn-row" }, submitButton)
  );

  ctx.show(
    el("div", { class: "page-head" },
      el("h1", { text: "Ask Phyto" }),
      el("p", {
        text: "Describe what is happening with a plant. Phyto gives tentative care guidance and clearly tells you whether the response came from live Gemini or the deck's offline fallback.",
      })
    ),
    form,
    resultBox
  );
}

// ---------------------------------------------------------------- System

function humanStatus(value) {
  const labels = {
    ok: "OK",
    offline: "Offline",
    configured_not_checked: "Configured, not checked",
    not_configured: "Not configured",
    not_initialized: "Not initialized",
    schema_incomplete: "Schema incomplete",
    unavailable: "Unavailable",
    local_interface_up: "Local network connected",
    no_local_ipv4: "No local IPv4",
    not_checked: "Not checked",
  };

  return labels[value] || String(value || "Unavailable").replaceAll("_", " ");
}

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) return "Unavailable";

  let remaining = Math.max(0, Math.floor(seconds));
  const days = Math.floor(remaining / 86400);
  remaining %= 86400;
  const hours = Math.floor(remaining / 3600);
  remaining %= 3600;
  const minutes = Math.floor(remaining / 60);

  const parts = [];
  if (days) parts.push(`${days}d`);
  if (hours || days) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);

  return parts.join(" ");
}

function systemValue(label, value) {
  return el("div", { class: "system-item" },
    el("dt", { text: label }),
    el("dd", { text: value }));
}

function systemStatusClass(value) {
  if (["ok", "local_interface_up", "configured_not_checked"].includes(value)) {
    return "system-good";
  }

  if (["offline", "not_checked", "not_initialized"].includes(value)) {
    return "system-neutral";
  }

  if (["unavailable", "schema_incomplete", "no_local_ipv4", "not_configured"].includes(value)) {
    return "system-warn";
  }

  return "system-neutral";
}

async function systemView(ctx) {
  ctx.title("System");

  const content = el("div", {
    class: "system-content",
    "aria-live": "polite",
  });

  const refreshButton = button("Refresh status", {
    variant: "secondary",
    iconName: "refresh",
    onclick: loadStatus,
  });

  async function loadStatus() {
    refreshButton.disabled = true;
    content.replaceChildren(loading("Reading deck status"));

    try {
      const status = await api.system();

      if (!ctx.isCurrent()) return;

      const interfaces = Array.isArray(status.network?.interfaces)
        ? status.network.interfaces
        : [];

      const networkList = interfaces.length
        ? el("ul", { class: "system-interface-list" },
            interfaces.flatMap((iface) => {
              const addresses = Array.isArray(iface.ipv4) ? iface.ipv4 : [];

              if (!addresses.length) {
                return [el("li", { text: iface.name || "Unknown interface" })];
              }

              return addresses.map((address) =>
                el("li", {
                  text: `${iface.name || "Interface"} — ${address}`,
                }));
            }))
        : el("p", {
            class: "none",
            text: "No active non-loopback IPv4 interfaces reported.",
          });

      const temperature = Number.isFinite(status.cpu_temperature_c)
        ? `${status.cpu_temperature_c.toFixed(1)} °C`
        : "Unavailable";

      const hardware = status.hardware_model || "Unavailable";

      const piValue = status.is_raspberry_pi ? "Yes" : "No";

      const backendStatus = status.backend?.status || "unavailable";
      const databaseStatus = status.database?.status || "unavailable";
      const networkStatus = status.network?.status || "unavailable";
      const internetStatus = status.network?.internet_status || "not_checked";
      const geminiStatus = status.gemini?.status || "unavailable";

      content.replaceChildren(
        el("section", {
          class: "system-panel",
          "aria-labelledby": "system-device-title",
        },
          el("div", { class: "system-panel-head" },
            el("h2", {
              id: "system-device-title",
              text: "Deck hardware",
            }),
            el("span", {
              class: `system-pill ${status.is_raspberry_pi ? "system-good" : "system-neutral"}`,
              text: status.is_raspberry_pi ? "Raspberry Pi" : "Non-Pi host",
            })
          ),

          el("dl", { class: "system-grid" },
            systemValue("Hostname", status.hostname || "Unavailable"),
            systemValue("Hardware model", hardware),
            systemValue("Raspberry Pi", piValue),
            systemValue("Uptime", formatUptime(status.uptime_seconds)),
            systemValue("CPU temperature", temperature)
          )
        ),

        el("section", {
          class: "system-panel",
          "aria-labelledby": "system-services-title",
        },
          el("h2", {
            id: "system-services-title",
            text: "Services",
          }),

          el("div", { class: "system-status-list" },
            el("div", { class: "system-status-row" },
              el("span", { text: "Backend" }),
              el("strong", {
                class: `system-pill ${systemStatusClass(backendStatus)}`,
                text: humanStatus(backendStatus),
              })
            ),

            el("div", { class: "system-status-row" },
              el("span", { text: "Database" }),
              el("strong", {
                class: `system-pill ${systemStatusClass(databaseStatus)}`,
                text: humanStatus(databaseStatus),
              })
            ),

            el("div", { class: "system-status-row" },
              el("span", { text: "Local network" }),
              el("strong", {
                class: `system-pill ${systemStatusClass(networkStatus)}`,
                text: humanStatus(networkStatus),
              })
            ),

            el("div", { class: "system-status-row" },
              el("span", { text: "Internet check" }),
              el("strong", {
                class: `system-pill ${systemStatusClass(internetStatus)}`,
                text: humanStatus(internetStatus),
              })
            ),

            el("div", { class: "system-status-row" },
              el("span", { text: "Gemini" }),
              el("strong", {
                class: `system-pill ${systemStatusClass(geminiStatus)}`,
                text: humanStatus(geminiStatus),
              })
            )
          )
        ),

        el("section", {
          class: "system-panel",
          "aria-labelledby": "system-network-title",
        },
          el("h2", {
            id: "system-network-title",
            text: "Network",
          }),

          networkList,

          el("p", {
            class: "system-note",
            text: "These are local IPv4 addresses reported by the machine running PhytoDex.",
          })
        ),

        el("section", {
          class: "system-panel",
          "aria-labelledby": "system-ai-title",
        },
          el("h2", {
            id: "system-ai-title",
            text: "Gemini configuration",
          }),

          el("dl", { class: "system-grid" },
            systemValue("Mode", status.gemini?.mode || "Unavailable"),
            systemValue("Model", status.gemini?.model || "Unavailable"),
            systemValue("Status", humanStatus(geminiStatus))
          ),

          el("p", {
            class: "system-note",
            text: "Opening this screen does not make a Gemini request or expose the API key.",
          })
        )
      );
    } catch (error) {
      if (!ctx.isCurrent()) return;

      content.replaceChildren(
        notice(
          "error",
          "System status couldn't load",
          error.message,
          button("Try again", {
            variant: "secondary",
            onclick: loadStatus,
          })
        )
      );
    } finally {
      refreshButton.disabled = false;
    }
  }

  ctx.show(
    el("div", { class: "list-head" },
      el("div", { class: "page-head" },
        el("h1", { text: "System" }),
        el("p", {
          text: "Live status from the machine running PhytoDex. Hardware-only values show as unavailable when the host cannot report them.",
        })
      ),
      refreshButton
    ),
    content
  );

  await loadStatus();
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
