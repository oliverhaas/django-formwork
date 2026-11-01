// Alpine.data component for the formwork SelectMultiple widget.
// `selected` maps each chosen value to its label and is the source of truth
// for the toggle text: a searched list holds only one page of rows, so the
// checked rows in the DOM cannot name the whole selection.

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

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSelectMultiple", () => ({
    _dirty: false,
    search: "",
    showSearch: false,
    placeholder: "",
    selectedSuffix: "",
    summaryThreshold: 0,
    selected: {},
    hasError: false,
    highlightedEl: null,

    init() {
      const el = this.$el;
      this.showSearch = el.dataset.showSearch === "true";
      this.placeholder = el.dataset.placeholder || "";
      this.selectedSuffix = el.dataset.selectedSuffix || "";
      this.summaryThreshold = Number(el.dataset.summaryThreshold);
      this._panel = panelPopover(el);
      // The template server-renders the placeholder class on the summary so
      // it is styled at first paint, before Alpine loads. Strip it here, in
      // the same synchronous pass in which the :class binding re-applies it:
      // Alpine only ever removes classes it added itself, so a static copy
      // would go stale on the first pick.
      el.querySelector("summary")?.classList.remove("formwork-placeholder");
      let first = true;
      const sync = () => {
        const server = Object.fromEntries(JSON.parse(el.dataset.selected || "[]"));
        if (!first) {
          const keys = Object.keys(server);
          const local = Object.keys(this.selected);
          const confirmed = keys.length === local.length && keys.every((k) => k in this.selected);
          if (confirmed) this._dirty = false;
          // A stale echo (the response to an older submit, landing after
          // further toggles) must not clobber the newer local state: the
          // last toggle's change event already armed a fresh submit that
          // carries the full current selection.
          else if (this._dirty) return;
        }
        first = false;
        this.selected = server;
        this.syncChecked();
        this.writeValues();
      };
      sync();
      // htmx 4 morphs swapped-in content in place rather than replacing the
      // node, so this x-data component (and thus init()) only ever runs
      // once. Re-sync whenever the server updates the attribute (e.g. after
      // this widget's own htmx-triggered save) so the display doesn't lag
      // one swap behind the confirmed server state.
      new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: ["data-selected"] });
      // Rows a search or "Load more" swaps in render unchecked. The Load more
      // swap replaces its own trigger, so its after:swap event never bubbles here.
      new MutationObserver(() => this.syncChecked()).observe(this.$refs.options, { childList: true });
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

    // Delegated on the stable <ul> so it also catches htmx-swapped rows.
    toggle(event) {
      const cb = event.target;
      if (cb.type !== "checkbox") return;
      if (cb.checked) this.selected[cb.dataset.value] = cb.dataset.label;
      else delete this.selected[cb.dataset.value];
      this._dirty = true;
      this.writeValues();
    },

    // A searched list holds one page of rows, so hidden inputs post the selection.
    writeValues() {
      const values = this.$refs.values;
      if (!values) return;
      values.replaceChildren(
        ...Object.keys(this.selected).map((value) =>
          Object.assign(document.createElement("input"), { type: "hidden", name: values.dataset.name, value }),
        ),
      );
    },

    syncChecked() {
      for (const cb of this.$root.querySelectorAll("ul[role=listbox] input[type=checkbox]")) {
        cb.checked = cb.dataset.value in this.selected;
      }
    },

    get noResults() {
      if (this.hasSearchUrl || !this.search) return false;
      return visibleOptions(this, "[data-value]").length === 0;
    },
    get displayText() {
      const labels = Object.values(this.selected);
      if (labels.length > this.summaryThreshold) return `${labels.length} ${this.selectedSuffix}`;
      return labels.join(", ");
    },
    matches(el) {
      return matchesQuery(el, this.hasSearchUrl ? "" : this.search);
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
    onSearchConfig(event) {
      searchConfig(this, event, this.search);
    },
    onSearchBeforeSwap(event) {
      if (searchSwapAllowed(event)) this.hasError = false;
    },
    onSearchError() {
      this.hasError = true;
    },
    confirm() {
      let target = this.highlightedEl;
      if (!target || target.offsetParent === null) target = visibleOptions(this, "label[data-value]")[0];
      if (target) target.click();
    },
  }));
});
