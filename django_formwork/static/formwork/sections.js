/**
 * sections.js: section forms for django-formwork (opt-in).
 *
 * A section form (`<form data-section-form>`) posts itself on every change
 * and is morphed back from the response.  Several section forms that save
 * one row share a `data-section-forms` wrapper and one request queue:
 *
 *   <div data-section-forms>
 *     <form id="general_form" data-section-form novalidate hx-post="…"
 *           hx-trigger="change delay:300ms" hx-select="#general_form"
 *           hx-swap="outerMorph" hx-sync="closest [data-section-forms]:queue all">
 *
 * Use `queue all`: a dropped or replaced save leaves its change unsent, and
 * a request waiting for that save then waits for ever.
 *
 * `data-section-indicator="<selector>"` on a field wrapper shows that
 * indicator while a save the field started runs.  `data-send-changed` on a
 * form posts only the fields that differ from the last valid render; a
 * field whose name starts with the attribute's value is always sent.
 *
 * Load via {% formwork_sections_js %}, after htmx.  The formwork bundle
 * leaves this file out.
 */

const FORM = "form[data-section-form]";
const counted = new WeakSet();

// A form counts its changes, so a response sent before the latest change
// leaves the form alone: the queued request after it carries that change.
const count = (event) => {
  if (counted.has(event)) return;
  const form = event.target.closest?.(FORM);
  if (!form) return;
  counted.add(event);
  form.sectionChanges = (form.sectionChanges ?? 0) + 1;
};

export const hasUnsentChanges = (el) => (el.sectionChanges ?? 0) !== (el.sectionSent ?? 0);

const sectionForms = (root) => [...(root.matches?.(FORM) ? [root] : []), ...root.querySelectorAll(FORM)];

const saving = (root) => sectionForms(root).some((form) => form.sectionSending || hasUnsentChanges(form));

// Requests that wait for section saves; each entry re-checks its target.
const waiting = new Set();

const saved = (root) =>
  new Promise((resolve) => {
    const check = () => {
      if (saving(root)) return;
      waiting.delete(check);
      resolve();
    };
    waiting.add(check);
  });

document.addEventListener("change", count);

document.addEventListener("htmx:before:request", (event) => {
  const { ctx } = event.detail;
  const elt = ctx.sourceElement;
  if (elt.matches?.(FORM)) {
    // A trigger without a delay sends before the change reaches the document.
    if (ctx.sourceEvent?.type === "change") count(ctx.sourceEvent);
    elt.sectionSent = elt.sectionChanges ?? 0;
    elt.sectionSending = true;
    return;
  }
  // A request that replaces section forms waits until the server has
  // answered their saves, so a removed form cannot drop a queued save.
  const target = ctx.target;
  if (!(target instanceof Element) || !saving(target)) return;
  const fetch = ctx.fetch;
  ctx.fetch = (...args) => saved(target).then(() => fetch(...args));
});

document.addEventListener("htmx:finally:request", (event) => {
  const form = event.detail.ctx.sourceElement;
  if (!form.matches?.(FORM)) return;
  form.sectionSending = false;
  for (const check of [...waiting]) check();
});

if (typeof htmx !== "undefined") {
  htmx.registerExtension("formwork-sections", {
    // Keeps a section form whose latest change is still to be sent.
    htmx_before_morph_node: (_elt, { oldNode }) => !hasUnsentChanges(oldNode),
  });
}

window.addEventListener("beforeunload", (event) => {
  if (saving(document)) event.preventDefault();
});

// A save started inside [data-section-indicator] shows that indicator until
// its request ends.
document.addEventListener("htmx:before:request", (event) => {
  const { ctx } = event.detail;
  const form = ctx.sourceElement;
  if (!form.matches?.(FORM)) return;
  const field = ctx.sourceEvent?.target?.closest?.("[data-section-indicator]");
  const indicator = field && document.querySelector(field.dataset.sectionIndicator);
  if (!indicator) return;
  indicator.classList.add("htmx-request");
  form.addEventListener("htmx:finally:request", () => indicator.classList.remove("htmx-request"), {
    once: true,
  });
});

// Enter commits a text field the way leaving it does; a section form has no submit.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.defaultPrevented || event.isComposing) return;
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.closest(FORM) || input.closest("dialog")) return;
  event.preventDefault();
  input.blur();
});

document.addEventListener("submit", (event) => {
  if (event.target.matches(FORM)) event.preventDefault();
});

// --- data-send-changed ---

const CHANGED = "form[data-send-changed]";
// Django masks the CSRF token anew on every render, and the section name
// never changes, yet the server needs both on every post.
const ALWAYS_SENT = new Set(["csrfmiddlewaretoken", "_formwork_section"]);
const rendered = new WeakMap();

const values = (form) => {
  const data = new FormData(form);
  return new Map([...new Set(data.keys())].map((key) => [key, data.getAll(key).join("\n")]));
};

// The baseline is the form as the server last rendered it, and only a valid
// render: an invalid one must send its fields again.
const remember = (form) => {
  if (!form.querySelector('[aria-invalid="true"]')) rendered.set(form, values(form));
};

const rememberAll = () => document.querySelectorAll(CHANGED).forEach(remember);

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", rememberAll);
} else {
  rememberAll();
}
// Alpine writes bound values (`:value`) after DOMContentLoaded.
document.addEventListener("alpine:initialized", rememberAll);

document.addEventListener("htmx:after:settle", (event) => {
  const root = event.target;
  if (!(root instanceof Element)) return;
  // The settled root is a form, sits inside one, or brought new ones in.
  for (const form of [root.closest(CHANGED), ...root.querySelectorAll(CHANGED)]) {
    if (form && !hasUnsentChanges(form)) remember(form);
  }
});

document.addEventListener("htmx:config:request", (event) => {
  const { ctx } = event.detail;
  const form = ctx.sourceElement;
  if (!form.matches?.(CHANGED) || !rendered.has(form)) return;
  const before = rendered.get(form);
  const alwaysPrefix = form.dataset.sendChanged;
  for (const [key, value] of values(form)) {
    if (ALWAYS_SENT.has(key) || (alwaysPrefix && key.startsWith(alwaysPrefix))) continue;
    if (before.get(key) === value) ctx.request.body.delete(key);
  }
});
