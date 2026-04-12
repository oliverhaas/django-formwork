/**
 * formwork.js — idiomorph morph configuration for django-formwork.
 *
 * Wraps Idiomorph.morph() to preserve Alpine.js reactive state and
 * <details> open/closed state during full-form morphing.
 *
 * Also disables native browser validation on forms that have formwork
 * error tooltips (CSP-safe replacement for an inline <script>).
 *
 * Include this script on pages that use htmx morph swaps with formwork
 * forms:
 *
 *   {% load formwork %}
 *   {% formwork_js %}
 *
 * Prerequisites (loaded by the user, BEFORE this script):
 *   - htmx 2.x with the idiomorph extension, OR htmx 4.x (built-in)
 *   - Alpine.js 3.x (if using Alpine-powered widgets)
 */
(() => {
  // --- Disable native validation on forms with formwork error tooltips ---
  // Previously an inline <script> in the form template; moved here for CSP.
  const disableNativeValidation = () => {
    for (const form of document.querySelectorAll("form")) {
      if (form.querySelector(".formwork-errors")) {
        form.noValidate = true;
      }
    }
  };

  // Run on initial load.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", disableNativeValidation);
  } else {
    disableNativeValidation();
  }

  // Re-run after htmx swaps (errors may appear after morph).
  document.addEventListener("htmx:afterSwap", disableNativeValidation);

  // --- Dirty-field highlighting (opt-in via data-formwork-dirty) ---
  // Tracks each field's initial value and toggles a .formwork-dirty class
  // on the containing fieldset when the current value differs.

  const DIRTY_CLS = "formwork-dirty";

  const getFieldValue = (el) => {
    if (el.type === "checkbox" || el.type === "radio") return el.checked ? el.value : "";
    return el.value;
  };

  const initDirtyTracking = (form) => {
    const baseline = new Map();

    const snapshot = () => {
      baseline.clear();
      for (const el of form.elements) {
        if (!el.name || el.type === "hidden") continue;
        // Radio groups: track the checked value under the group name.
        if (el.type === "radio") {
          if (el.checked) baseline.set(el.name, el.value);
          if (!baseline.has(el.name)) baseline.set(el.name, "");
        } else {
          baseline.set(el.id || el.name, getFieldValue(el));
        }
      }
    };

    const check = (el) => {
      const fieldset = el.closest("fieldset.fieldset");
      if (!fieldset) return;
      const key = el.type === "radio" ? el.name : (el.id || el.name);
      const initial = baseline.get(key) ?? "";
      const current = el.type === "radio"
        ? (form.querySelector(`input[name="${el.name}"]:checked`)?.value ?? "")
        : getFieldValue(el);
      fieldset.classList.toggle(DIRTY_CLS, current !== initial);
    };

    snapshot();
    form.addEventListener("input", (e) => check(e.target));
    form.addEventListener("change", (e) => check(e.target));

    // Re-snapshot after successful morph (new server-rendered values = new baseline).
    form.addEventListener("htmx:afterSwap", () => requestAnimationFrame(snapshot));

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
  document.addEventListener("htmx:afterSwap", initAllDirtyForms);

  // --- Idiomorph morph wrapper ---

  if (typeof Idiomorph === "undefined") {
    return;
  }

  const origMorph = Idiomorph.morph;

  Idiomorph.morph = (target, newContent, config) => {
    config = config || {};

    // Preserve the focused input's current value during morph —
    // only set if the caller hasn't explicitly configured it.
    if (!("ignoreActiveValue" in config)) {
      config.ignoreActiveValue = true;
    }

    // Install callbacks to protect Alpine state and <details> state.
    config.callbacks = config.callbacks || {};
    const origAttr = config.callbacks.beforeAttributeUpdated;
    const origNode = config.callbacks.beforeNodeMorphed;
    const origRemove = config.callbacks.beforeNodeRemoved;

    config.callbacks.beforeAttributeUpdated = (
      attrName,
      element,
      updateType,
    ) => {
      // Block x-data attribute changes — prevents Alpine.js from
      // re-parsing and resetting reactive state on morph.
      if (attrName === "x-data") {
        return false;
      }

      // Block open attribute changes on <details> — preserves
      // dropdown open/closed state across morphs.
      if (attrName === "open" && element.tagName === "DETAILS") {
        return false;
      }

      // Block checked attribute changes on checkboxes inside MultiSelect —
      // user selections are tracked by Alpine state and checkbox DOM
      // properties; idiomorph would reset them to the server-rendered state.
      if (
        attrName === "checked" &&
        element.tagName === "INPUT" &&
        element.type === "checkbox" &&
        element.closest("details.multiselect")
      ) {
        return false;
      }

      // Delegate to any previously installed callback.
      if (typeof origAttr === "function") {
        return origAttr(attrName, element, updateType);
      }
    };

    config.callbacks.beforeNodeMorphed = (oldNode, newNode) => {
      if (oldNode.nodeType === 1 && newNode.nodeType === 1) {
        // Preserve Alpine-managed text content (x-text directive).
        // Alpine sets .textContent reactively but won't re-evaluate
        // after morph since no reactive data changed.
        if (oldNode.hasAttribute("x-text")) {
          newNode.textContent = oldNode.textContent;
        }
        // Preserve Alpine-managed HTML content (x-html directive).
        if (oldNode.hasAttribute("x-html")) {
          newNode.innerHTML = oldNode.innerHTML;
        }
        // Preserve Alpine x-show display state — Alpine toggles
        // display via style, but won't re-evaluate after morph.
        if (oldNode.hasAttribute("x-show")) {
          newNode.style.display = oldNode.style.display;
        }
      }
      if (typeof origNode === "function") {
        return origNode(oldNode, newNode);
      }
    };

    config.callbacks.beforeNodeRemoved = (node) => {
      // Preserve DOM nodes generated by Alpine's <template x-for>
      // or <template x-if>.  These sibling nodes exist in the live
      // DOM (created by Alpine) but not in server-rendered HTML, so
      // idiomorph would remove them.
      //
      // Walk backward through all siblings looking for a generating
      // template.  Check the template's content to verify the node's
      // tag matches what the template produces.
      if (node.nodeType === 1) {
        let prev = node.previousElementSibling;
        while (prev) {
          if (
            prev.tagName === "TEMPLATE" &&
            (prev.hasAttribute("x-for") || prev.hasAttribute("x-if"))
          ) {
            const tmplChild = prev.content?.firstElementChild;
            if (!tmplChild || tmplChild.tagName === node.tagName) {
              return false;
            }
          }
          prev = prev.previousElementSibling;
        }
      }
      if (typeof origRemove === "function") {
        return origRemove(node);
      }
    };

    return origMorph.call(this, target, newContent, config);
  };
})();
