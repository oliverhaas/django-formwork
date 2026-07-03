// Alpine.data component for the formwork SearchSelect widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { dropdownBase } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSearchSelect", () => ({
    ...dropdownBase("[data-value]"),
    search: "",
    showSearch: false,
    value: "",
    label: "",
    icon: "",
    labelClass: "",

    init() {
      const el = this.$el;
      this.showSearch = el.dataset.showSearch === "true";
      this.value = el.dataset.value || "";
      this.label = el.dataset.label || "";
      this.icon = el.dataset.icon || "";
      this.labelClass = el.dataset.labelClass || "";
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
        this._clearHighlight();
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
    confirm() {
      const target = this._confirmTarget();
      if (target) {
        this.pick(target.dataset.value, target.dataset.label, target.dataset.icon || "", target.dataset.labelClass || "");
      }
    },
    pick(val, lbl, ic, lc) {
      this.value = val;
      this.label = lbl;
      this.icon = ic || "";
      this.labelClass = lc || "";
      this.search = "";
      this._v++;
      this._clearHighlight();
      this.$root.open = false;
      this._notify();
    },
    clear() {
      this.value = "";
      this.label = "";
      this.icon = "";
      this.labelClass = "";
      this.search = "";
      this._v++;
      this._clearHighlight();
      this._notify();
    },
  }));
});
