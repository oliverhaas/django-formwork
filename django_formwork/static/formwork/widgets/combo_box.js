// Alpine.data component for the formwork ComboBox and ComboBoxMultiple widgets.
// In multiple mode the input holds comma-separated values; the *segment*
// after the last comma is what's being typed.  iconMap is hydrated from
// data-icons and grows as the user picks icon-bearing suggestions.

import {
  clearHighlight,
  closePanel,
  keyboardNav,
  matchesQuery,
  openPanel,
  panelPopover,
  searchConfig,
  searchSwapAllowed,
  visibleOptions,
} from "./_helpers.js";

const splitValues = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);

// The values before the segment being typed; all of them after a trailing comma.
const confirmedValues = (v) => {
  const all = splitValues(v);
  const sep = /,\s*$/.test(v) || !all.length;
  return sep ? all : all.slice(0, -1);
};

// A multiple input shows a trailing ", " while focused; the form posts the
// list without it.
const stripTrailingSeparators = (form) => {
  form.addEventListener("formdata", (e) => {
    for (const input of form.querySelectorAll(".formwork-combobox[data-multiple=true] .combobox-input")) {
      if (input.value) e.formData.set(input.name, input.value.replace(/,\s*$/, ""));
    }
  });
};

const strippedForms = new WeakSet();

document.addEventListener("alpine:init", () => {
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
      this._panel = panelPopover(el);
      this.$watch("open", (open) => (open ? openPanel(this) : closePanel(this)));
      try {
        this.iconMap = JSON.parse(el.dataset.icons || "{}");
      } catch {
        this.iconMap = {};
      }
      const form = el.closest("form");
      if (this.multiple && form && !strippedForms.has(form)) {
        strippedForms.add(form);
        stripTrailingSeparators(form);
      }
    },

    get hasSearchUrl() {
      return this.$root.dataset.hasSearchUrl === "true";
    },
    get noResults() {
      if (this.hasSearchUrl || !this.currentSegment) return false;
      return visibleOptions(this, "[data-value]").length === 0;
    },
    get currentSegment() {
      this._v;
      const v = this.$refs.input?.value || "";
      if (!this.multiple) return v.trim();
      const parts = v.split(",");
      return parts[parts.length - 1].trim();
    },
    get displayParts() {
      this._v;
      const v = this.$refs.input?.value || "";
      if (!v.trim()) return [];
      if (this.multiple) return splitValues(v).map((t) => ({ text: t, icon: this.iconMap[t] || "" }));
      const ic = this.iconMap[v.trim()] || "";
      return ic ? [{ text: v.trim(), icon: ic }] : [];
    },

    focusInput() {
      this.$refs.input.focus();
    },
    onFocus() {
      this.open = true;
      this.focused = true;
      const inp = this.$refs.input;
      if (this.multiple && inp.value && !/,\s*$/.test(inp.value)) {
        inp.value += ", ";
        this._v++;
      }
    },
    onInput() {
      this.open = true;
      this._v++;
      clearHighlight(this);
    },
    onBlur(event) {
      if (this.$root.contains(event.relatedTarget)) return;
      this.focused = false;
      if (this.multiple) {
        const inp = this.$refs.input;
        inp.value = inp.value.replace(/,\s*$/, "");
        this._v++;
      }
    },
    close() {
      this.open = false;
      clearHighlight(this);
    },

    matches(el) {
      return matchesQuery(el, this.hasSearchUrl ? "" : this.currentSegment);
    },
    isSelected(el) {
      if (!this.multiple) return false;
      this._v;
      const label = (el.dataset.label || "").toLowerCase();
      return confirmedValues(this.$refs.input?.value || "").some((v) => v.toLowerCase() === label);
    },
    onNav(event, dir) {
      if (!this.open) return;
      event.preventDefault();
      keyboardNav(this, dir, "[data-value]");
    },
    onEnter(event) {
      if (!this.open) return;
      event.preventDefault();
      this.confirm();
    },
    onOptionClick(event) {
      const btn = event.target.closest("button[data-value]");
      if (btn) this.pick(btn);
    },
    onSearchConfig(event) {
      searchConfig(this, event, this.currentSegment);
    },
    onSearchBeforeSwap(event) {
      if (searchSwapAllowed(event)) this.hasError = false;
    },
    onSearchError() {
      this.hasError = true;
    },
    confirm() {
      let target = this.highlightedEl;
      if (!target || target.offsetParent === null) target = visibleOptions(this, "[data-value]")[0];
      if (target) this.pick(target);
    },
    pick(el) {
      const text = el.dataset.label;
      if (el.dataset.icon) this.iconMap[text] = el.dataset.icon;
      const inp = this.$refs.input;
      if (this.multiple) {
        const confirmed = confirmedValues(inp.value || "");
        const idx = confirmed.findIndex((c) => c.toLowerCase() === text.toLowerCase());
        if (idx >= 0) confirmed.splice(idx, 1);
        else confirmed.push(text);
        inp.value = confirmed.length ? `${confirmed.join(", ")}, ` : "";
        this._v++;
        clearHighlight(this);
        inp.focus();
        inp.dispatchEvent(new Event("input", { bubbles: true }));
      } else {
        inp.value = text;
        this._v++;
        clearHighlight(this);
        this.open = false;
        // change, not input: the @input handler reopens the dropdown.
        inp.dispatchEvent(new Event("change", { bubbles: true }));
      }
    },
  }));
});
