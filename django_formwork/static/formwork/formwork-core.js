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
 *      toggles a .formwork-dirty class on the containing fieldset, or on
 *      an element marked data-formwork-field.
 *   4. Busy buttons: a .btn that sends a request carries aria-busy until
 *      the response is in, and formwork.css shows a spinner on it.
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
// on the containing fieldset when the current value differs.  A field
// outside a fieldset, such as a widget in a table cell, sits in an element
// marked data-formwork-field.  The server marks a field data-formwork-changed
// when the posted value already differs from the initial one: after a failed
// save, the page starts from the posted values.  After each check the form
// sends formwork:dirty with the number of changed fields.
//
// A checkbox, radio or switch also carries .formwork-dirty-option while its
// own checked state differs from the start, so a group marks the options
// that changed, not every option.  For a field the server marked changed,
// data-formwork-initial lists the option values checked at first.

const DIRTY_CLS = "formwork-dirty";
const OPTION_CLS = "formwork-dirty-option";
const FIELD = "fieldset.fieldset, [data-formwork-field]";
const isCheckable = (el) => el.type === "checkbox" || el.type === "radio";

const getInitialOptions = (field) => {
  const json = field?.dataset.formworkInitial;
  if (json === undefined) return null;
  try {
    return JSON.parse(json).map(String);
  } catch {
    return null;
  }
};

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

// Baseline for an htmx-mode SelectMultiple comes from data-selected, the
// selection the server rendered, whether or not the widget has started.
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
  const checkedAtStart = new Map();

  // A part of the form that a swap replaced takes a new baseline for its own fields only.
  const snapshot = (root) => {
    const part = root !== form;
    if (!part) {
      baseline.clear();
      checkedAtStart.clear();
    }
    const elements = part
      ? [...root.querySelectorAll("input, select, textarea")].filter((el) => el.form === form)
      : form.elements;
    const radios = new Set();
    for (const el of elements) {
      // Hidden inputs stay tracked: widgets (Select, InputMask)
      // hold their real value in a hidden input and dispatch events on it.
      // SelectMultiple internals are tracked as one unit below.
      if (!el.name || el.closest("details.formwork-select-multiple")) continue;
      if (isCheckable(el)) {
        const initial = getInitialOptions(el.closest(FIELD));
        const checked = initial ? initial.includes(el.value) : el.checked;
        checkedAtStart.set(el, checked);
        // Radio groups: track the checked value under the group name.
        if (el.type === "radio") {
          if (!radios.has(el.name)) baseline.set(el.name, "");
          radios.add(el.name);
          if (checked) baseline.set(el.name, el.value);
        } else {
          baseline.set(el.id || el.name, checked ? el.value : "");
        }
      } else {
        baseline.set(el.id || el.name, getFieldValue(el));
      }
    }
    for (const details of root.querySelectorAll("details.formwork-select-multiple")) {
      baseline.set(details, getSelectMultipleBaseline(details));
    }
  };

  const changed = (el) => {
    if (el.type === "radio") {
      const current = form.querySelector(`input[name="${CSS.escape(el.name)}"]:checked`)?.value ?? "";
      return current !== (baseline.get(el.name) ?? "");
    }
    return getFieldValue(el) !== (baseline.get(el.id || el.name) ?? "");
  };

  // A field with several inputs (a date range) is dirty while any of them
  // differs, whichever one the event came from.
  const dirty = (field) => {
    if (field.hasAttribute("data-formwork-changed") && !("formworkInitial" in field.dataset)) return true;
    const selectMultiple = field.querySelector("details.formwork-select-multiple");
    if (selectMultiple) return getSelectMultipleValue(selectMultiple) !== (baseline.get(selectMultiple) ?? "");
    const controls = [...field.querySelectorAll("input[name], select[name], textarea[name]")];
    return controls.some((control) => control.form === form && changed(control));
  };

  const report = () => {
    const count = form.querySelectorAll(`.${DIRTY_CLS}`).length;
    form.dispatchEvent(new CustomEvent("formwork:dirty", { bubbles: true, detail: { count } }));
  };

  const mark = (field) => {
    field.classList.toggle(DIRTY_CLS, dirty(field));
    for (const el of field.querySelectorAll("input[type=checkbox][name], input[type=radio][name]")) {
      if (!checkedAtStart.has(el)) continue;
      el.classList.toggle(OPTION_CLS, el.checked !== checkedAtStart.get(el));
    }
  };

  const check = (el) => {
    const field = (el.closest?.("details.formwork-select-multiple") || el).closest?.(FIELD);
    if (!field || !form.contains(field)) return;
    mark(field);
    report();
  };

  // Every field again, or those of a part of the form: a new baseline leaves only the ones the
  // server marked.
  const refresh = (part) => {
    const root = part instanceof Element && form.contains(part) ? part : form;
    snapshot(root);
    for (const field of root.querySelectorAll(FIELD)) mark(field);
    report();
  };

  refresh();
  form.addEventListener("input", (e) => check(e.target));
  form.addEventListener("change", (e) => check(e.target));

  // Re-snapshot after a successful morph of the form (new server-rendered
  // values = new baseline), not after a dropdown search swaps rows into it.
  form.addEventListener("htmx:after:swap", (e) => {
    const target = e.detail?.ctx?.target;
    if (target instanceof Element && !target.contains(form)) return;
    requestAnimationFrame(refresh);
  });

  // Expose snapshot for programmatic reset.
  form._formworkDirtySnapshot = refresh;
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
// A morph of an element around a tracked form brings new server values too;
// the form's own listener sees only the swaps of the form and inside it.
document.addEventListener("htmx:after:swap", (e) => {
  const target = e.detail?.ctx?.target;
  for (const form of document.querySelectorAll("form[data-formwork-dirty]")) {
    if (!form._formworkDirtySnapshot) initDirtyTracking(form);
    else if (target instanceof Element && target !== form && target.contains(form)) {
      requestAnimationFrame(form._formworkDirtySnapshot);
    }
  }
});

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

// --- Busy buttons ---
// A .btn that sends a request carries aria-busy="true" until the response is
// in, and formwork.css turns its icon into a spinner.  Without a visible icon
// the button also gets data-busy-overlay, and the spinner covers its label.
// The button is the source of an htmx request or one of its hx-indicator
// elements, or the submitter of a form, htmx or native.  A menu item in a
// .dropdown passes the state to the dropdown's trigger.
//
// A native submit stays busy until the next page replaces this one, or until
// the browser stops the navigation.  A form that answers with a download
// leaves the page in place, so its button opts out with .btn-loading-none.

const BUSY_OPT_OUT = "btn-loading-none";
const busyCounts = new WeakMap();
const nativeBusy = new Set();

const busyButton = (el) => {
  if (!(el instanceof Element)) return null;
  const button = el.matches(".btn")
    ? el
    : el.matches("button") && el.closest(".dropdown")?.querySelector(":scope > .btn");
  if (!button || button.classList.contains(BUSY_OPT_OUT) || el.classList.contains(BUSY_OPT_OUT)) return null;
  return button;
};

const hasVisibleIcon = (button) =>
  button.matches(".btn-icon, .btn-icon-end") ||
  [...button.children].some((child) => child.classList.contains("icon") && child.getClientRects().length > 0);

// Counted, as the requests of one button can overlap: a request that
// hx-sync replaces ends after the one that replaced it has started.
const setBusy = (button, busy) => {
  const count = (busyCounts.get(button) ?? 0) + (busy ? 1 : -1);
  if (count > 0) {
    busyCounts.set(button, count);
    if (count === 1) {
      button.toggleAttribute("data-busy-overlay", !hasVisibleIcon(button));
      button.setAttribute("aria-busy", "true");
    }
    return;
  }
  busyCounts.delete(button);
  button.removeAttribute("aria-busy");
  button.removeAttribute("data-busy-overlay");
};

document.addEventListener("htmx:before:request", (e) => {
  const ctx = e.detail.ctx;
  const sources = [...(ctx.indicators ?? []), ctx.sourceEvent?.submitter];
  ctx.formworkBusy = [...new Set(sources.map(busyButton).filter(Boolean))];
  for (const button of ctx.formworkBusy) setBusy(button, true);
});

// htmx keeps its indicators while a response header sends the page elsewhere.
document.addEventListener("htmx:finally:request", (e) => {
  const ctx = e.detail.ctx;
  if (ctx.keepIndicators) return;
  for (const button of ctx.formworkBusy ?? []) setBusy(button, false);
});

// htmx cancels the submits it sends on the form itself, before this listener.
document.addEventListener("submit", (e) => {
  if (e.defaultPrevented) return;
  const form = e.target;
  const submitter = e.submitter;
  if ((submitter?.formMethod || form.method) === "dialog") return;
  const target = submitter?.formTarget || form.target;
  if (target && target !== "_self") return;
  const button = busyButton(submitter);
  if (!button || nativeBusy.has(button)) return;
  nativeBusy.add(button);
  setBusy(button, true);
});

const clearNativeBusy = () => {
  for (const button of nativeBusy) setBusy(button, false);
  nativeBusy.clear();
};
// Back and Forward can bring the page back from the cache as it was left.
window.addEventListener("pageshow", (e) => {
  if (e.persisted) clearNativeBusy();
});
// The Navigation API reports the Stop button.  It says nothing of a download.
window.navigation?.addEventListener("navigateerror", clearNativeBusy);

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

  // The hook below sees a node only when htmx morphs it.  htmx leaves out
  // the children of a node equal to its new version, and a control's
  // checked, selected or value property is not part of that comparison, so
  // the controls in an unchanged subtree keep what the user did there.
  // These are the nodes of the running morph that the hook saw; after the
  // morph, each control it did not see is set to its attributes, which are
  // the server's.
  let morphed = [];

  const morphedControls = (target) => {
    const seen = new Set(morphed.map((detail) => detail.oldNode));
    // Every extension hook gets the same detail; htmx marks it cancelled
    // when one of them kept the node.
    const kept = morphed.filter((detail) => detail.cancelled).map((detail) => detail.oldNode);
    const skipped = [htmx.config.morphSkip, htmx.config.morphSkipChildren].filter(Boolean).join(", ");
    return [...target.querySelectorAll("input, textarea, option")].filter(
      (control) =>
        !seen.has(control) &&
        !kept.some((node) => node.contains(control)) &&
        !(skipped && control.parentElement?.closest(skipped)),
    );
  };

  const syncToAttributes = (control) => {
    if (control === document.activeElement || control._x_model) return;
    if (control instanceof HTMLOptionElement) {
      if (control.closest("select") !== document.activeElement) {
        control.selected = control.hasAttribute("selected");
      }
    } else if (control instanceof HTMLTextAreaElement) {
      control.value = control.defaultValue;
    } else if (control.type === "checkbox" || control.type === "radio") {
      control.checked = control.hasAttribute("checked");
    } else if (control.type !== "file") {
      control.value = control.getAttribute("value") ?? "";
    }
  };

  // Per-pair morph hook.  htmx 4 dispatches `htmx:before:morph:node` via
  // the extension API for every (oldNode, newNode) pair.  Returning false
  // skips morphing that node entirely; mutating `newNode` here lets us
  // pre-seed values that the subsequent attribute/child copy will then
  // pick up.
  htmx.registerExtension("formwork-morph", {
    // A dropdown gives its highlighted row an id, which the server's copy of
    // the row lacks. htmx pairs a node that has an id only with a node of the
    // same id, so it would replace the row; this pairs it with the server's
    // row of the same label.
    init: (api) => {
      const isSoftMatch = api.isSoftMatch;
      api.isSoftMatch = (oldNode, newNode) =>
        oldNode._formworkOwnId && oldNode.id === oldNode._formworkOwnId && !newNode.id
          ? oldNode.tagName === newNode.tagName && oldNode.dataset.label === newNode.dataset?.label
          : isSoftMatch(oldNode, newNode);
    },
    htmx_before_settle: (target) => {
      if (!morphed.length) return;
      if (target.isConnected) morphedControls(target).forEach(syncToAttributes);
      morphed = [];
    },
    htmx_before_morph_node: (_elt, detail) => {
      const oldNode = detail.oldNode;
      const newNode = detail.newNode;

      if (!(oldNode instanceof Element) || !(newNode instanceof Element)) {
        return true;
      }
      morphed.push(detail);

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
      } else if (oldNode instanceof HTMLInputElement && (oldNode.type === "checkbox" || oldNode.type === "radio")) {
        // The same sync for the checked state. Once a click or a script has
        // changed it, the `checked` attribute that htmx copies no longer
        // moves it, and a list that gains a choice pairs each old input with
        // a different choice.
        if (oldNode === document.activeElement) {
          newNode.toggleAttribute("checked", oldNode.checked);
        } else {
          oldNode.checked = newNode.hasAttribute("checked");
        }
      } else if (oldNode instanceof HTMLOptionElement) {
        if (oldNode.closest("select") === document.activeElement) {
          newNode.toggleAttribute("selected", oldNode.selected);
        } else {
          oldNode.selected = newNode.hasAttribute("selected");
        }
      }

      return true;
    },
  });
}
