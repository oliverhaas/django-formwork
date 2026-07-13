// Alpine.data component for the formwork ComboBox widget.
// In multiple mode the input holds comma-separated values; the *segment*
// after the last comma is what's being typed.  iconMap is hydrated from
// data-icons and grows as the user picks icon-bearing suggestions.

import { clearHighlight, keyboardNav, visibleOptions } from "./_helpers.js";

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
        // change, not input: the template's @input handler reopens the dropdown.
        inp.dispatchEvent(new Event("change", { bubbles: true }));
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
