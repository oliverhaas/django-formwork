// Alpine.data component for the formwork SearchSelect widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { clearHighlight, keyboardNav, visibleOptions } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSearchSelect", () => ({
    _v: 0,
    search: "",
    showSearch: false,
    value: "",
    label: "",
    icon: "",
    selectedToggleClass: "",
    hasError: false,
    highlightedEl: null,

    init() {
      const el = this.$el;
      this.showSearch = el.dataset.showSearch === "true";
      // The template server-renders the initial display classes on the
      // summary so they are styled at first paint, before Alpine loads.
      // Strip them here, in the same synchronous pass in which the :class
      // binding re-applies them: Alpine only ever removes classes it added
      // itself, so a static copy would go stale on the next pick.
      const summary = el.querySelector("summary");
      if (summary) {
        summary.classList.remove("formwork-placeholder");
        for (const cls of (el.dataset.selectedToggleClass || "").split(/\s+/)) {
          if (cls) summary.classList.remove(cls);
        }
      }
      const sync = () => {
        const nextValue = el.dataset.value || "";
        const nextLabel = el.dataset.label || "";
        // A server re-render (e.g. after a morph) can't always resolve the
        // display metadata for the current value: an async SearchSelect backed
        // by a plain CharField knows only the submitted key, not its label,
        // icon, or toggle class, so it emits empty data-label/-icon/
        // -selected-toggle-class. Treat empties as "no info", not "clear it",
        // so a value the client already labelled (e.g. "us" to "United
        // States") keeps its display through the morph. When the value itself
        // changes, adopt the server's metadata (even empty) so a server-driven
        // change or clear still wins.
        if (nextValue !== this.value || nextLabel) {
          this.label = nextLabel;
          this.icon = el.dataset.icon || "";
          this.selectedToggleClass = el.dataset.selectedToggleClass || "";
        }
        this.value = nextValue;
        this._v++;
      };
      sync();
      // htmx 4 morphs swapped-in content in place rather than replacing the
      // node, so this x-data component (and thus init()) only ever runs
      // once. Re-sync whenever the server updates these attributes (e.g.
      // after this widget's own htmx-triggered save) so the display doesn't
      // lag one swap behind the confirmed server state.
      new MutationObserver(sync).observe(el, {
        attributes: true,
        attributeFilter: ["data-value", "data-label", "data-icon", "data-selected-toggle-class"],
      });
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
      if (target)
        this.pick(
          target.dataset.value,
          target.dataset.label,
          target.dataset.icon || "",
          target.dataset.selectedToggleClass || "",
        );
    },
    pick(val, lbl, ic, selectedToggleClass) {
      this.value = val;
      this.label = lbl;
      this.icon = ic || "";
      this.selectedToggleClass = selectedToggleClass || "";
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
      this.selectedToggleClass = "";
      this.search = "";
      this._v++;
      clearHighlight(this);
      this._notify();
    },
  }));
});
