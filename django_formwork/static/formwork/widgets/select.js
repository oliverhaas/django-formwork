// Alpine.data component for the formwork Select widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import {
  clearHighlight,
  clearInput,
  closePanel,
  keyboardNav,
  matchesQuery,
  openPanel,
  panelPopover,
  searchConfig,
  searchSwapAllowed,
  visibleOptions,
} from "./_helpers.js";

const CHOICE_ATTRIBUTES = ["data-value", "data-label", "data-icon", "data-label-html", "data-selected-toggle-class"];

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSelect", () => ({
    _v: 0,
    _dirty: false,
    search: "",
    showSearch: false,
    placeholder: "",
    value: "",
    label: "",
    icon: "",
    labelHtml: "",
    selectedToggleClass: "",
    hasError: false,
    highlightedEl: null,

    init() {
      const el = this.$el;
      this.showSearch = el.dataset.showSearch === "true";
      this.placeholder = el.dataset.placeholder || "";
      this._panel = panelPopover(el);
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
        // A stale echo (the response to an older submit, landing after a
        // newer pick) must not clobber the newer value: that pick's change
        // event already armed a fresh submit.
        if (nextValue === this.value) this._dirty = false;
        else if (this._dirty) return;
        // A server re-render (e.g. after a morph) can't always resolve the
        // display metadata for the current value: a searched Select backed
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
          this.labelHtml = el.dataset.labelHtml || "";
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
      new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: CHOICE_ATTRIBUTES });
    },

    get hasSearchUrl() {
      return this.$root.dataset.hasSearchUrl === "true";
    },

    onToggle() {
      if (this.$el.open) {
        openPanel(this);
        if (this.showSearch) setTimeout(() => this.$refs.search?.focus(), 0);
      } else {
        closePanel(this);
        clearHighlight(this);
      }
    },

    close() {
      this.$root.open = false;
    },

    get noResults() {
      if (this.hasSearchUrl || !this.search) return false;
      return visibleOptions(this, "[data-value]").length === 0;
    },
    get displayText() {
      this._v;
      return this.label || "";
    },
    matches(el) {
      return matchesQuery(el, this.hasSearchUrl ? "" : this.search);
    },
    isSelected(el) {
      return this.value === el.dataset.value;
    },
    clearHighlight() {
      clearHighlight(this);
    },
    clearSearch() {
      clearInput(this.$refs.search);
    },
    onNav(event, dir) {
      if (!this.$root.open) return;
      event.preventDefault();
      keyboardNav(this, dir, "[data-value]");
    },
    onEnter(event) {
      if (!this.$root.open || event.target.closest("button")) return;
      event.preventDefault();
      this.confirm();
    },
    onOptionClick(event) {
      const btn = event.target.closest("button[data-value]");
      if (btn) this.pick(btn);
    },
    onSearchConfig(event) {
      searchConfig(this, event, this.search);
    },
    onSearchBeforeSwap(event) {
      if (searchSwapAllowed(event)) this.hasError = false;
    },
    onSearchError() {
      this.hasError = true;
    },
    _notify() {
      this.$nextTick(() => {
        const inp = this.$root.querySelector("input[type=hidden]");
        if (inp) inp.dispatchEvent(new Event("change", { bubbles: true }));
      });
    },
    confirm() {
      let target = this.highlightedEl;
      if (!target || target.offsetParent === null) target = visibleOptions(this, "[data-value]")[0];
      if (target) this.pick(target);
    },
    pick(el) {
      const data = el.dataset;
      const cleared = data.value === "";
      this._dirty = true;
      this.value = data.value;
      this.label = cleared ? "" : data.label;
      this.icon = cleared ? "" : data.icon || "";
      this.labelHtml = cleared ? "" : data.labelHtml || "";
      this.selectedToggleClass = cleared ? "" : data.selectedToggleClass || "";
      this.search = "";
      this._v++;
      clearHighlight(this);
      this.$root.open = false;
      this._notify();
    },
    clear() {
      this._dirty = true;
      this.value = "";
      this.label = "";
      this.icon = "";
      this.labelHtml = "";
      this.selectedToggleClass = "";
      this.search = "";
      this._v++;
      clearHighlight(this);
      this._notify();
    },
  }));
});
