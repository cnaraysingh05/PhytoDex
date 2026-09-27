// Small helpers for building the screens.
// el() always inserts text with textContent, never innerHTML, so nothing
// Gemini or a user types can be run as code in the page.

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Icon paths are fixed strings written here, never data from the server.
const ICONS = {
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  image: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m4 17 5-4.5 4 3.5 3-2.5 4 3.5"/>',
  leaf: '<path d="M12 21V10"/><path d="M12 13c-5 0-8-3-8-9 5.5 0 8 3 8 9Z"/><path d="M12 16c4 0 7-2.5 7-7.5-4.5 0-7 2.5-7 7.5Z"/>',
  pot: '<path d="M6 13h12l-1.5 7h-9z"/><path d="M12 13V8"/><path d="M12 9c-3 0-5-2-5-5 3 0 5 2 5 5Z"/><path d="M12 10c2.5 0 4.5-1.5 4.5-4-2.5 0-4.5 1.5-4.5 4Z"/>',
  refresh: '<path d="M19 12a7 7 0 1 1-2.1-5"/><path d="M19 4v4h-4"/>',
  sprout: '<path d="M32 58V30"/><path d="M32 38c-12 0-20-8-20-22 14 0 20 8 20 22Z"/><path d="M32 46c10 0 18-6 18-18-12 0-18 6-18 18Z"/><path d="M18 58h28"/>',
};

export function icon(name, className = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", name === "sprout" ? "0 0 64 64" : "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  if (className) svg.setAttribute("class", className);
  svg.innerHTML = ICONS[name] || "";
  return svg;
}

export function placeholder() {
  return el("div", { class: "placeholder" }, icon("leaf"));
}

// Shows a saved photo; if the file is missing, shows a leaf placeholder instead
// of a broken image.
export function photo(src, alt, { eager = false } = {}) {
  if (!src) return placeholder();
  const image = el("img", { src, alt, loading: eager ? "eager" : "lazy", decoding: "async" });
  image.addEventListener("error", () => image.replaceWith(placeholder()), { once: true });
  return image;
}

export const RATING_LABELS = {
  healthy: "Healthy",
  attention: "Needs attention",
  concerning: "Concerning",
  unknown: "Not assessed",
};

export function ratingKey(rating) {
  return rating in RATING_LABELS ? rating : "unknown";
}

export function ratingChip(rating) {
  const key = ratingKey(rating);
  return el("span", { class: `chip chip-${key}`, text: RATING_LABELS[key] });
}

export function ratingWord(rating) {
  const key = ratingKey(rating);
  return el("span", { class: `reading-word rating-${key}`, text: RATING_LABELS[key] });
}

// Backend timestamps are UTC text like "2026-09-26 14:03:11".
export function parseTimestamp(value) {
  if (!value) return null;
  const date = new Date(`${String(value).replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function formatWhen(value, { withTime = true } = {}) {
  const date = parseTimestamp(value);
  if (!date) return "Unknown date";
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  let day;
  if (sameDay(date, now)) day = "Today";
  else if (sameDay(date, yesterday)) day = "Yesterday";
  else day = date.toLocaleDateString([], { month: "short", day: "numeric", year: date.getFullYear() === now.getFullYear() ? undefined : "numeric" });
  return withTime ? `${day}, ${time}` : day;
}

export function list(items, emptyText) {
  if (!Array.isArray(items) || items.length === 0) return el("p", { class: "none", text: emptyText });
  return el("ul", {}, items.map((item) => el("li", { text: item })));
}

export function notice(kind, title, message, ...actions) {
  return el("div", { class: `notice notice-${kind}`, role: kind === "error" ? "alert" : "status" },
    title ? el("strong", { text: title }) : null,
    message ? el("p", { text: message }) : null,
    actions.length ? el("div", { class: "btn-row" }, actions) : null);
}

export function button(label, { variant = "primary", iconName, onclick, type = "button" } = {}) {
  return el("button", { class: `btn btn-${variant}`, type, onclick }, iconName ? icon(iconName) : null, label);
}

export function linkButton(label, href, { variant = "primary", iconName } = {}) {
  return el("a", { class: `btn btn-${variant}`, href, "data-link": true }, iconName ? icon(iconName) : null, label);
}

export function loading(text) {
  return el("p", { class: "loading", role: "status", text });
}

// The reading block shared by the scan result and each history entry.
// certainty is qualitative evidence strength from Gemini, never a percentage.
export function assessmentDetails(assessment) {
  const unknown = ratingKey(assessment.health_rating) === "unknown";
  return [
    el("section", { class: "finding" }, el("h3", { text: "What's visible" }),
      list(assessment.visible_signs, "No visible signs were listed.")),
    el("section", { class: "finding" }, el("h3", { text: "Possible causes" }),
      list(assessment.possible_causes, unknown ? "Not assessed for this photo." : "No likely causes were listed.")),
    el("section", { class: "finding" }, el("h3", { text: "Next steps" }),
      list(assessment.next_steps, "No next steps were listed.")),
    el("section", { class: "finding finding-limits" }, el("h3", { text: "Limits of this reading" }),
      el("p", { text: assessment.limitations || "A photo alone may not reveal the underlying cause." })),
  ];
}

export function evidenceLine(certainty) {
  const value = ["low", "medium", "high"].includes(certainty) ? certainty : "low";
  return el("span", { class: "reading-evidence" },
    "Evidence: ", el("b", { text: value[0].toUpperCase() + value.slice(1) }),
    el("span", { class: "visually-hidden", text: " (how well the photo supports this reading, not a percentage)" }));
}
