// Alpine.data component for the formwork MultiSelect widget.
// Two internal modes (toggled by data-has-search-url):
//
//   - htmx-driven: tracks selections in a Map populated from
//     data-initial-selected, because server-rendered HTML doesn't include
//     every option and so checkbox state in the DOM is unreliable.
//   - client-only: scans `input:checked` directly from the DOM.

import { clearHighlight, keyboardNav, visibleOptions } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
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
        const sync = () => {
          this.selected = new Map(JSON.parse(el.dataset.initialSelected || "[]"));
        };
        sync();
        // htmx 4 morphs swapped-in content in place rather than replacing the
        // node, so this x-data component (and thus init()) only ever runs
        // once. Re-sync whenever the server updates the attribute (e.g. after
        // this widget's own htmx-triggered save) so the display doesn't lag
        // one swap behind the confirmed server state.
        new MutationObserver(sync).observe(el, {
          attributes: true,
          attributeFilter: ["data-initial-selected"],
        });
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
});
