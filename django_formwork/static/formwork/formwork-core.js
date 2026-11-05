/**
 * formwork-core.js: page-global infrastructure for django-formwork.
 *
 * This file holds the non-widget logic that runs once per page,
 * regardless of which widgets are on the page:
 *
 *   1. htmx 4 morph extension (`formwork-morph`) that preserves focused
 *      input values, <details> open state, unconfirmed dropdown picks, and
 *      Alpine-template-generated DOM nodes during full-form morphs.  Alpine
 *      bindings survive the morph through htmx's alpine-compat extension.
 *   2. Native browser validation disabling on forms with formwork error
 *      tooltips (CSP-safe replacement for an inline <script>).
 *   3. Dirty-field highlighting (opt-in via data-formwork-dirty) that
 *      toggles a .formwork-dirty class on the containing fieldset.
 *
 * Load via {% formwork_core_js %} if you're using {{ form.media }} for
 * the per-widget Alpine code; the bundle {% formwork_js %} already
 * imports this file.
 *
 * Prerequisites (loaded by the user, BEFORE this script):
 *   - htmx 4.x
 *   - htmx's alpine-compat extension (`dist/ext/hx-alpine-compat.js` in
 *     the htmx release), after htmx.  Without it a morph strips what
 *     Alpine bindings (x-show, x-text, :class, :aria-selected, ...) wrote
 *     into the DOM.
 */

// --- Disable native validation on forms with formwork error tooltips ---
// Lives here rather than an inline <script> so no script-src exception is needed.
const disableNativeValidation = () => {
  for (const form of document.querySelectorAll("form")) {
    if (form.querySelector(".formwork-errors")) {
      form.noValidate = true;
    }
  }
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", disableNativeValidation);
} else {
  disableNativeValidation();
}
document.addEventListener("htmx:after:swap", disableNativeValidation);

// --- Dirty-field highlighting (opt-in via data-formwork-dirty) ---
// Tracks each field's initial value and toggles a .formwork-dirty class
// on the containing fieldset when the current value differs.

const DIRTY_CLS = "formwork-dirty";

const getFieldValue = (el) => {
  if (el.type === "checkbox" || el.type === "radio") return el.checked ? el.value : "";
  return el.value;
};

// SelectMultiple dispatches change events from its <details> root (htmx mode)
// or from the checkboxes inside it; neither carries a comparable .value.
// Derive one: the sorted set of selected option values, read from the
// Alpine-rendered hidden inputs plus the checked boxes.  The empty hidden
// input only marks the field as submitted.
const getSelectMultipleValue = (details) => {
  const values = new Set();
  for (const el of details.querySelectorAll("input[type=hidden][name]")) {
    if (el.value) values.add(el.value);
  }
  for (const el of details.querySelectorAll("input[type=checkbox]:checked")) values.add(el.value);
  return [...values].sort().join(",");
};

// Baseline for an htmx-mode SelectMultiple comes from data-selected:
// Alpine renders the hidden inputs only after its own init, which may run
// after the snapshot.
const getSelectMultipleBaseline = (details) => {
  const json = details.dataset.selected;
  if (json === undefined) return getSelectMultipleValue(details);
  try {
    return JSON.parse(json).map(([value]) => String(value)).sort().join(",");
  } catch {
    return "";
  }
};

const initDirtyTracking = (form) => {
  const baseline = new Map();

  const snapshot = () => {
    baseline.clear();
    for (const el of form.elements) {
      // Hidden inputs stay tracked: widgets (Select, InputMask)
      // hold their real value in a hidden input and dispatch events on it.
      // SelectMultiple internals are tracked as one unit below.
      if (!el.name || el.closest("details.formwork-select-multiple")) continue;
      // Radio groups: track the checked value under the group name.
      if (el.type === "radio") {
        if (el.checked) baseline.set(el.name, el.value);
        if (!baseline.has(el.name)) baseline.set(el.name, "");
      } else {
        baseline.set(el.id || el.name, getFieldValue(el));
      }
    }
    for (const details of form.querySelectorAll("details.formwork-select-multiple")) {
      baseline.set(details, getSelectMultipleBaseline(details));
    }
  };

  const check = (el) => {
    const selectMultiple = el.closest?.("details.formwork-select-multiple");
    const target = selectMultiple || el;
    const fieldset = target.closest("fieldset.fieldset");
    if (!fieldset) return;
    let key;
    let current;
    if (selectMultiple) {
      key = selectMultiple;
      current = getSelectMultipleValue(selectMultiple);
    } else if (el.type === "radio") {
      key = el.name;
      current = form.querySelector(`input[name="${el.name}"]:checked`)?.value ?? "";
    } else {
      key = el.id || el.name;
      current = getFieldValue(el);
    }
    const initial = baseline.get(key) ?? "";
    fieldset.classList.toggle(DIRTY_CLS, current !== initial);
  };

  snapshot();
  form.addEventListener("input", (e) => check(e.target));
  form.addEventListener("change", (e) => check(e.target));

  // Re-snapshot after a successful morph of the form (new server-rendered
  // values = new baseline), not after a dropdown search swaps rows into it.
  form.addEventListener("htmx:after:swap", (e) => {
    const target = e.detail?.ctx?.target;
    if (target instanceof Element && !target.contains(form)) return;
    requestAnimationFrame(snapshot);
  });

  // Expose snapshot for programmatic reset.
  form._formworkDirtySnapshot = snapshot;
};

const initAllDirtyForms = () => {
  for (const form of document.querySelectorAll("form[data-formwork-dirty]")) {
    if (!form._formworkDirtySnapshot) initDirtyTracking(form);
  }
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAllDirtyForms);
} else {
  initAllDirtyForms();
}
document.addEventListener("htmx:after:swap", initAllDirtyForms);

// --- Inline disclosure sizing (help text + inline errors) ---
// The help/error collapsible is a native <details class="formwork-disclosure">.
// CSS cannot tell whether the summary text overflows one line, so this small
// vanilla pass marks each disclosure `data-expandable` when there is something
// to reveal: a help row (shown under an inline error once open) or summary
// text that overflows while closed.  Only then does the [more]/[less] affordance
// appear and the summary act as a toggle; otherwise the summary stays a plain,
// non-focusable one-line label.
//
// Overflow depends on text metrics, which move under the widget's feet:
// web fonts load after first paint (a row that fit the fallback font can
// overflow the real one), a container narrows without a window resize (a
// sidebar or modal opens), and a morph or Alpine rewrites the row's text.
// So this reruns on initial load, once document.fonts settles, after every
// htmx settle, and whenever a disclosure changes size or text.  <details
// open> state is preserved across morphs (open is in htmx.config.morphIgnore)
// and no Alpine :class binding fights it, so an expanded row stays open; this
// pass only re-derives expandability.

const measureDisclosures = (target) => {
  const root = target instanceof Element ? target : document;
  const list = [];
  if (target instanceof Element && target.matches("details.formwork-disclosure")) {
    list.push(target);
  }
  list.push(...root.querySelectorAll("details.formwork-disclosure"));

  for (const d of list) {
    const summary = d.querySelector(":scope > summary");
    if (!summary) continue;

    const hasBody = !!d.querySelector(":scope > summary > .formwork-disclosure-body");
    let expandable;
    if (hasBody || d.open) {
      // A help row always hides revealable content; an already-open row was
      // expandable when it was opened, and its wrapped text can't be
      // measured for overflow.
      expandable = true;
    } else {
      const text = summary.querySelector(".formwork-disclosure-text") || summary;
      // Measure against the affordance-free width.  The [more] label is itself
      // a flex item that narrows the text (~44px), so leaving a stale
      // data-expandable set would bias this measurement and make the result
      // depend on the previous state.  Strip it first for a stable baseline.
      d.removeAttribute("data-expandable");
      expandable = text.scrollWidth > text.clientWidth;
    }

    if (expandable) {
      d.setAttribute("data-expandable", "");
      summary.removeAttribute("tabindex");
    } else {
      d.removeAttribute("data-expandable");
      // Keep a non-expandable summary out of the tab order: toggling it
      // would reveal nothing.
      summary.setAttribute("tabindex", "-1");
    }
  }
};

// The first callback for a newly observed row runs after layout and before
// the first paint, so a new row is painted with its measured state.
const disclosureSizes = new ResizeObserver((entries) => {
  for (const { target } of entries) {
    if (target.isConnected) {
      measureDisclosures(target);
    } else {
      disclosureSizes.unobserve(target);
      delete target._formworkObserved;
    }
  }
});
const disclosureTexts = new MutationObserver((records) => {
  const changed = new Set();
  for (const record of records) {
    const node = record.target instanceof Element ? record.target : record.target.parentElement;
    const d = node && node.closest("details.formwork-disclosure");
    if (d) changed.add(d);
  }
  for (const d of changed) measureDisclosures(d);
});

const observeDisclosures = (target) => {
  const root = target instanceof Element ? target : document;
  const list = [...root.querySelectorAll("details.formwork-disclosure")];
  if (target instanceof Element && target.matches("details.formwork-disclosure")) list.push(target);
  for (const d of list) {
    if (d._formworkObserved) continue;
    d._formworkObserved = true;
    disclosureSizes.observe(d);
    disclosureTexts.observe(d, { characterData: true, childList: true, subtree: true });
  }
};

// Defer to the next frame so layout is settled before measuring.
const scheduleMeasureDisclosures = (target) =>
  requestAnimationFrame(() => measureDisclosures(target));

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    observeDisclosures(document);
    scheduleMeasureDisclosures(document);
  });
} else {
  observeDisclosures(document);
  scheduleMeasureDisclosures(document);
}
// Web fonts change glyph widths without resizing any box, so no observer fires.
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(() => measureDisclosures(document));
}
// htmx fires after:settle on the swap target.  The rows already observed
// re-measure themselves, so only the swapped subtree needs a pass.
document.addEventListener("htmx:after:settle", (e) => {
  const target = e.target instanceof Element && e.target.isConnected ? e.target : document;
  observeDisclosures(target);
  scheduleMeasureDisclosures(target);
});

// --- htmx 4 morph configuration ---

if (typeof htmx !== "undefined") {
  // Globally ignored attributes during morph:
  //   x-data: re-applying it makes Alpine re-init the component and lose
  //           reactive state.
  //   open:   on <details> and <dialog>, the open attribute is the user's
  //           UI state, not server state.  A morph never closes an open
  //           dropdown, and server HTML cannot open or close one either.
  htmx.config.morphIgnore = [
    ...(htmx.config.morphIgnore || []),
    "x-data",
    "open",
  ];

  // Skip morphing children of any element that contains an Alpine
  // <template x-for> or <template x-if> direct child.  Those elements own
  // sibling DOM nodes that Alpine creates from the template at runtime;
  // those nodes do not exist in server-rendered HTML and would be removed
  // by the morph diff.  Skipping the parent's children preserves them and
  // lets Alpine continue managing them reactively.
  const morphSkipChildrenSelector =
    ":has(> template[x-for]), :has(> template[x-if])";
  htmx.config.morphSkipChildren = htmx.config.morphSkipChildren
    ? `${htmx.config.morphSkipChildren}, ${morphSkipChildrenSelector}`
    : morphSkipChildrenSelector;

  // Per-pair morph hook.  htmx 4 dispatches `htmx:before:morph:node` via
  // the extension API for every (oldNode, newNode) pair.  Returning false
  // skips morphing that node entirely; mutating `newNode` here lets us
  // pre-seed values that the subsequent attribute/child copy will then
  // pick up.
  htmx.registerExtension("formwork-morph", {
    htmx_before_morph_node: (_elt, detail) => {
      const oldNode = detail.oldNode;
      const newNode = detail.newNode;

      if (!(oldNode instanceof Element) || !(newNode instanceof Element)) {
        return true;
      }

      // A dropdown holding a pick the server has not confirmed yet skips a
      // stale echo whole: its hidden inputs would otherwise post the older
      // choice.
      if (oldNode._formworkAcceptMorph && !oldNode._formworkAcceptMorph(newNode)) {
        return false;
      }

      // Sync input `.value` property to match the new server-rendered
      // value, EXCEPT when this is the focused element (preserve user's
      // in-progress typing).  htmx's core morph only writes .value when
      // the `value` *attribute* differs, but `<input>` elements where
      // the user has typed have a .value PROPERTY that diverges from the
      // empty .value attribute.  Without this sync, server-driven
      // resets (e.g. clearing a form on delete) leave stale typed
      // values in the inputs.
      if (oldNode instanceof HTMLInputElement && oldNode.type !== "file") {
        if (oldNode === document.activeElement) {
          // Preserve user's in-progress typing AND cursor position.
          newNode.setAttribute("value", oldNode.value);
          newNode.value = oldNode.value;
        } else {
          const newAttrValue = newNode.getAttribute("value") ?? "";
          if (oldNode.value !== newAttrValue) {
            oldNode.value = newAttrValue;
          }
        }
      } else if (oldNode instanceof HTMLTextAreaElement) {
        if (oldNode === document.activeElement) {
          // For <textarea>, defaultValue is the inner text content;
          // making newNode's textContent match oldNode.value avoids the
          // defaultValue-comparison branch in htmx's morph that would
          // otherwise overwrite oldNode.value.
          newNode.textContent = oldNode.value;
        } else if (oldNode.value !== newNode.textContent) {
          oldNode.value = newNode.textContent;
        }
      }

      // Preserve `checked` on user-toggled checkboxes inside SelectMultiple.
      // The Alpine `selected` Map is the source of truth; the server
      // doesn't know which boxes the user has just ticked, so don't let
      // the morph reset them.
      if (
        oldNode instanceof HTMLInputElement &&
        oldNode.type === "checkbox" &&
        oldNode.closest("details.formwork-select-multiple")
      ) {
        if (oldNode.checked) {
          newNode.setAttribute("checked", "");
        } else {
          newNode.removeAttribute("checked");
        }
        newNode.checked = oldNode.checked;
      }

      return true;
    },
  });
}
