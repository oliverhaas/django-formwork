/**
 * formwork-core.js — page-global infrastructure for django-formwork.
 *
 * This file holds the non-widget logic that runs once per page,
 * regardless of which widgets are on the page:
 *
 *   1. htmx 4 morph extension (`formwork-morph`) that preserves Alpine
 *      reactive state, focused input values, <details> open state, and
 *      Alpine-template-generated DOM nodes during full-form morphs.
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

// MultiSelect dispatches change events from its <details> root (htmx mode)
// or from name-less checkboxes inside it; neither carries a comparable
// .value.  Derive one: the sorted set of selected option values, read from
// the Alpine-rendered hidden inputs plus the checked boxes.
const getMultiSelectValue = (details) => {
  const values = new Set();
  for (const el of details.querySelectorAll("input[type=hidden][name]")) values.add(el.value);
  for (const el of details.querySelectorAll("input[type=checkbox]:checked")) values.add(el.value);
  return [...values].sort().join(",");
};

// Baseline for an htmx-mode MultiSelect comes from data-initial-selected:
// Alpine renders the hidden inputs only after its own init, which may run
// after the snapshot.
const getMultiSelectBaseline = (details) => {
  const json = details.dataset.initialSelected;
  if (json === undefined) return getMultiSelectValue(details);
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
      // Hidden inputs stay tracked: widgets (SearchSelect, OTPInput,
      // InputMask) hold their real value in a hidden input and dispatch
      // events on it.  MultiSelect internals are tracked as one unit below.
      if (!el.name || el.closest("details.multiselect")) continue;
      // Radio groups: track the checked value under the group name.
      if (el.type === "radio") {
        if (el.checked) baseline.set(el.name, el.value);
        if (!baseline.has(el.name)) baseline.set(el.name, "");
      } else {
        baseline.set(el.id || el.name, getFieldValue(el));
      }
    }
    for (const details of form.querySelectorAll("details.multiselect")) {
      baseline.set(details, getMultiSelectBaseline(details));
    }
  };

  const check = (el) => {
    const multiselect = el.closest?.("details.multiselect");
    const target = multiselect || el;
    const fieldset = target.closest("fieldset.fieldset");
    if (!fieldset) return;
    let key;
    let current;
    if (multiselect) {
      key = multiselect;
      current = getMultiSelectValue(multiselect);
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

  // Re-snapshot after successful morph (new server-rendered values = new baseline).
  form.addEventListener("htmx:after:swap", () => requestAnimationFrame(snapshot));

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
// overflow the real one) and the viewport resizes.  So this reruns on
// initial load, once document.fonts settles, on window resize, and after
// every htmx settle.  <details open> state is preserved across morphs (open
// is in htmx.config.morphIgnore) and no Alpine :class binding fights it, so
// an expanded row stays open; this pass only re-derives expandability.

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
      // expandable when it was opened (and its text is wrapped now, so it
      // can no longer be measured for overflow).
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

// Defer to the next frame so layout is settled before measuring.
const scheduleMeasureDisclosures = (target) =>
  requestAnimationFrame(() => measureDisclosures(target));

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => scheduleMeasureDisclosures(document));
} else {
  scheduleMeasureDisclosures(document);
}
// Web fonts change glyph widths after first paint; re-derive once they load.
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(() => measureDisclosures(document));
}
// Viewport width drives one-line overflow; re-derive on resize, coalesced to
// one measurement per frame.
let resizeScheduled = false;
window.addEventListener("resize", () => {
  if (resizeScheduled) return;
  resizeScheduled = true;
  requestAnimationFrame(() => {
    resizeScheduled = false;
    measureDisclosures(document);
  });
});
document.addEventListener("htmx:after:settle", (e) => {
  scheduleMeasureDisclosures(e.detail && e.detail.target ? e.detail.target : document);
});

// --- Alpine initialization for htmx-swapped content ---
// htmx inserts and morphs server HTML outside Alpine's knowledge.  Two
// failure modes have to be handled together:
//
//   1. Lazy-loaded content (hx-trigger="load", innerHTML swaps): Alpine's
//      MutationObserver normally initializes inserted nodes, but it can miss
//      the first swap if htmx inserts content before Alpine.start() runs
//      (Alpine is commonly deferred).  Those roots need an explicit init.
//
//   2. Morphed content (hx-swap="outerMorph"): the morph preserves existing
//      Alpine components (x-data is in morphIgnore, so the node is kept and
//      its reactive state survives).  Calling Alpine.initTree() on such a
//      subtree RE-initializes already-live components, corrupting Alpine's
//      internal x-for/x-if markers ("Cannot read properties of undefined
//      (reading '_x_marker')") and leaving the tree half-bound.
//
// The fix is a single idempotent pass: after every settle, initialize only
// the Alpine roots that are NOT already initialized.  Fresh lazy-loaded roots
// get set up exactly once; morph-preserved roots (which already carry
// Alpine's _x_dataStack) are skipped, and the new nodes a morph adds inside
// them are handled by Alpine's own observer.  This removes the need for user
// pages to wire their own (double-initializing) Alpine.initTree call.
const initAlpineRoots = (target) => {
  if (typeof window === "undefined" || !window.Alpine) return;
  if (!(target instanceof Element)) return;
  const roots = target.hasAttribute("x-data") ? [target] : [];
  roots.push(...target.querySelectorAll("[x-data]"));
  for (const el of roots) {
    // _x_dataStack is set by Alpine once a node's x-data is initialized;
    // its absence means this root is genuinely new and needs setup.
    if (!el._x_dataStack) {
      window.Alpine.initTree(el);
    }
  }
};
document.addEventListener("htmx:after:settle", (e) => {
  if (e.detail && e.detail.target) initAlpineRoots(e.detail.target);
});

// --- htmx 4 morph configuration ---

if (typeof htmx !== "undefined") {
  // Globally ignored attributes during morph:
  //   x-data — re-applying it makes Alpine re-init the component and lose
  //            reactive state.
  //   open   — on <details>, the open attribute reflects user UI state, not
  //            server state, so server HTML must never close an opened
  //            dropdown.
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

      // Sync input `.value` property to match the new server-rendered
      // value, EXCEPT when this is the focused element (preserve user's
      // in-progress typing).  htmx's core morph only writes .value when
      // the `value` *attribute* differs — but `<input>` elements where
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

      // Preserve `checked` on user-toggled checkboxes inside MultiSelect.
      // The Alpine `selected` Map is the source of truth; the server
      // doesn't know which boxes the user has just ticked, so don't let
      // the morph reset them.
      if (
        oldNode instanceof HTMLInputElement &&
        oldNode.type === "checkbox" &&
        oldNode.closest("details.multiselect")
      ) {
        if (oldNode.checked) {
          newNode.setAttribute("checked", "");
        } else {
          newNode.removeAttribute("checked");
        }
        newNode.checked = oldNode.checked;
      }

      // Preserve Alpine-managed text content (x-text directive).  Alpine
      // sets .textContent reactively but won't re-evaluate after morph
      // since no reactive data changed.  Without this, morph would
      // overwrite with the server-rendered fallback text.
      if (oldNode.hasAttribute("x-text")) {
        newNode.textContent = oldNode.textContent;
      }

      // Preserve Alpine-applied classes (:class bindings).  Server HTML
      // carries only the static class attribute, so a morph would strip
      // classes Alpine added (formwork-placeholder, a selected option's
      // toggle class, dropdown-open).  When the swap changes no reactive
      // state (e.g. re-saving an unchanged value), nothing ever re-applies
      // them.  Union old into new: the server can still add classes, and
      // classes Alpine no longer wants are removed by its own undo pass
      // the next time the binding evaluates.
      if (oldNode.hasAttribute(":class") || oldNode.hasAttribute("x-bind:class")) {
        for (const cls of oldNode.classList) {
          newNode.classList.add(cls);
        }
      }

      // Preserve Alpine-managed HTML content (x-html directive).
      if (oldNode.hasAttribute("x-html")) {
        newNode.innerHTML = oldNode.innerHTML;
      }

      // Preserve Alpine x-show display state.  Alpine toggles display via
      // inline style; without this, morph clears the inline style and
      // Alpine doesn't re-evaluate.
      if (oldNode.hasAttribute("x-show")) {
        if (oldNode.style.display) {
          newNode.style.display = oldNode.style.display;
        } else {
          newNode.style.removeProperty("display");
        }
      }

      return true;
    },
  });
}
