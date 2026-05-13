/**
 * formwork.js — htmx 4 morph configuration for django-formwork.
 *
 * Configures htmx 4's built-in morph (innerMorph/outerMorph swap styles) to
 * preserve Alpine.js reactive state, focused-input values, <details> open
 * state, and Alpine-template-generated DOM nodes during full-form morphs.
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
 *   - htmx 4.x
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

  // --- Dropdown Alpine.data components ---
  // Shared keyboard nav + highlight helpers, closure-private, used by
  // formworkSearchSelect, formworkMultiSelect, and formworkComboBox.

  const visibleOptions = (component, selector) =>
    [...component.$refs.options.querySelectorAll(selector)]
      .filter((b) => b.offsetParent !== null);

  const clearHighlight = (component) => {
    if (component.highlightedEl) {
      component.highlightedEl.classList.remove("highlighted");
      component.highlightedEl = null;
    }
  };

  const keyboardNav = (component, dir, selector) => {
    const visible = visibleOptions(component, selector);
    if (!visible.length) return;
    let idx = visible.indexOf(component.highlightedEl);
    if (idx === -1) idx = dir > 0 ? 0 : visible.length - 1;
    else idx = (idx + dir + visible.length) % visible.length;
    clearHighlight(component);
    component.highlightedEl = visible[idx];
    component.highlightedEl.classList.add("highlighted");
    component.highlightedEl.scrollIntoView({ block: "nearest" });
  };

  document.addEventListener("alpine:init", () => {
    // SearchSelect: single-value dropdown with text filter.  Server-rendered
    // state arrives on data-* attrs: value, label, icon, show-search, and a
    // has-search-url flag that controls the htmx prefetch behaviour.
    Alpine.data("formworkSearchSelect", () => ({
      _v: 0,
      search: "",
      showSearch: false,
      value: "",
      label: "",
      icon: "",
      hasError: false,
      highlightedEl: null,

      init() {
        const el = this.$el;
        this.showSearch = el.dataset.showSearch === "true";
        this.value = el.dataset.value || "";
        this.label = el.dataset.label || "";
        this.icon = el.dataset.icon || "";
      },

      onToggle() {
        const el = this.$el;
        if (el.open) {
          const s = this.$refs.search;
          if (el.dataset.hasSearchUrl === "true" && !el.dataset.loaded) {
            el.dataset.loaded = "1";
            requestAnimationFrame(() => s?.dispatchEvent(new Event("focus")));
          }
          if (this.showSearch) setTimeout(() => s?.focus(), 0);
        } else {
          clearHighlight(this);
        }
      },

      get noResults() {
        if (!this.search) return false;
        const q = this.search.toLowerCase();
        return ![...this.$refs.options.querySelectorAll(".select-none")].some(
          (s) => s.textContent.trim().toLowerCase().includes(q),
        );
      },
      get displayText() {
        this._v;
        return this.label || "";
      },
      _notify() {
        this.$nextTick(() => {
          const inp = this.$root.querySelector("input[type=hidden]");
          if (inp) inp.dispatchEvent(new Event("change", { bubbles: true }));
        });
      },
      _visibleOptions() {
        return visibleOptions(this, "[data-value]");
      },
      _clearHighlight() {
        clearHighlight(this);
      },
      nav(dir) {
        keyboardNav(this, dir, "[data-value]");
      },
      confirm() {
        let target = this.highlightedEl;
        if (!target || target.offsetParent === null) target = this._visibleOptions()[0];
        if (target) this.pick(target.dataset.value, target.dataset.label, target.dataset.icon || "");
      },
      pick(val, lbl, ic) {
        this.value = val;
        this.label = lbl;
        this.icon = ic || "";
        this.search = "";
        this._v++;
        clearHighlight(this);
        this.$root.open = false;
        this._notify();
      },
      clear() {
        this.value = "";
        this.label = "";
        this.icon = "";
        this.search = "";
        this._v++;
        clearHighlight(this);
        this._notify();
      },
    }));

    // MultiSelect: multi-value dropdown with checkboxes.  Two internal
    // branches: htmx-driven mode (`hasSearchUrl=true`) tracks selections in
    // a Map populated from data-initial-selected; client-only mode reads
    // checked checkboxes from the DOM.  The Map branch is needed because
    // server-rendered HTML doesn't include all options, so client-side
    // checkbox state is the only source of truth for selection.
    Alpine.data("formworkMultiSelect", () => ({
      _v: 0,
      search: "",
      hasError: false,
      highlightedEl: null,
      hasSearchUrl: false,
      selected: null,

      init() {
        const el = this.$el;
        this.hasSearchUrl = el.dataset.hasSearchUrl === "true";
        if (this.hasSearchUrl) {
          this.selected = new Map(JSON.parse(el.dataset.initialSelected || "[]"));
        }
      },

      onToggle() {
        const el = this.$el;
        if (el.open) {
          const s = this.$refs.search;
          if (s) setTimeout(() => s.focus(), 0);
        } else {
          clearHighlight(this);
        }
      },

      toggle(value, label, icon) {
        if (this.selected.has(value)) this.selected.delete(value);
        else this.selected.set(value, [label, icon || ""]);
        this._v++;
        this.$nextTick(() => this.$root.dispatchEvent(new Event("change", { bubbles: true })));
      },

      get noResults() {
        if (!this.search) return false;
        if (this.hasSearchUrl) return !this.$refs.options.querySelector(".select-none");
        const q = this.search.toLowerCase();
        return ![...this.$refs.options.querySelectorAll(".select-none")].some(
          (s) => s.textContent.trim().toLowerCase().includes(q),
        );
      },
      get displayText() {
        this._v;
        if (this.hasSearchUrl) {
          if (!this.selected.size) return "";
          if (this.selected.size > 3) return this.selected.size + " selected";
          return [...this.selected.values()]
            .map(([lbl, ic]) => (ic ? ic + " " + lbl : lbl))
            .join(", ");
        }
        const checked = [...this.$refs.options.querySelectorAll("input:checked")];
        if (!checked.length) return "";
        if (checked.length > 3) return checked.length + " selected";
        return checked.map((input) => {
          const label = input.parentElement;
          const ic = label.querySelector(".shrink-0:not(.formwork-check)");
          const text = label.querySelector(".select-none").textContent.trim();
          return ic ? ic.textContent.trim() + " " + text : text;
        }).join(", ");
      },
      _visibleOptions() {
        return visibleOptions(this, "[data-value]");
      },
      _clearHighlight() {
        clearHighlight(this);
      },
      nav(dir) {
        keyboardNav(this, dir, "[data-value]");
      },
      confirm() {
        let target = this.highlightedEl;
        if (!target || target.offsetParent === null) target = this._visibleOptions()[0];
        if (target) target.click();
      },
    }));

    // ComboBox: free-text input with autocomplete suggestions.  In multiple
    // mode the input holds comma-separated values; the *segment* after the
    // last comma is what's being typed.  iconMap is hydrated from
    // data-icons and grows as the user picks icon-bearing suggestions.
    Alpine.data("formworkComboBox", () => ({
      open: false,
      focused: false,
      _v: 0,
      hasError: false,
      highlightedEl: null,
      multiple: false,
      iconMap: {},

      init() {
        const el = this.$el;
        this.multiple = el.dataset.multiple === "true";
        try {
          this.iconMap = JSON.parse(el.dataset.icons || "{}");
        } catch {
          this.iconMap = {};
        }
      },

      get noResults() {
        this._v;
        const q = this.currentSegment;
        if (!q) return false;
        return ![...this.$refs.options.querySelectorAll(".select-none")].some(
          (s) => s.textContent.trim().toLowerCase().includes(q),
        );
      },
      get currentSegment() {
        this._v;
        const v = this.$refs.input?.value || "";
        if (!this.multiple) return v.toLowerCase();
        const parts = v.split(",");
        return parts[parts.length - 1].trim().toLowerCase();
      },
      get displayParts() {
        this._v;
        const v = this.$refs.input?.value || "";
        if (!v.trim()) return [];
        if (this.multiple) {
          return v.split(",").map((s) => s.trim()).filter(Boolean).map(
            (t) => ({ text: t, icon: this.iconMap[t] || "" }),
          );
        }
        const ic = this.iconMap[v.trim()] || "";
        return ic ? [{ text: v.trim(), icon: ic }] : [];
      },
      matches(label) {
        const q = this.currentSegment;
        return !q || label.toLowerCase().includes(q);
      },
      isSelected(text) {
        if (!this.multiple) return false;
        this._v;
        const v = this.$refs.input?.value || "";
        const all = v.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
        const sep = v.endsWith(",") || v.endsWith(", ") || !all.length;
        return (sep ? all : all.slice(0, -1)).includes(text.toLowerCase());
      },
      pick(text, icon) {
        if (icon) this.iconMap[text] = icon;
        const inp = this.$refs.input;
        if (this.multiple) {
          const v = inp.value || "";
          const all = v.split(",").map((s) => s.trim()).filter(Boolean);
          const sep = v.endsWith(",") || v.endsWith(", ") || !all.length;
          const confirmed = sep ? [...all] : all.slice(0, -1);
          const idx = confirmed.findIndex((c) => c.toLowerCase() === text.toLowerCase());
          if (idx >= 0) confirmed.splice(idx, 1);
          else confirmed.push(text);
          inp.value = confirmed.length ? confirmed.join(", ") + ", " : "";
          this._v++;
          clearHighlight(this);
          inp.focus();
          inp.dispatchEvent(new Event("input", { bubbles: true }));
        } else {
          inp.value = text;
          this._v++;
          clearHighlight(this);
          this.open = false;
        }
      },
      _visibleOptions() {
        return visibleOptions(this, "[data-suggestion]");
      },
      _clearHighlight() {
        clearHighlight(this);
      },
      nav(dir) {
        keyboardNav(this, dir, "[data-suggestion]");
      },
      confirm() {
        let target = this.highlightedEl;
        if (!target || target.offsetParent === null) target = this._visibleOptions()[0];
        if (target) this.pick(target.dataset.suggestion, target.dataset.icon || "");
      },
    }));
  });

  // --- htmx 4 morph configuration ---

  if (typeof htmx === "undefined") {
    return;
  }

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
})();
