// Alpine.data component for the formwork SearchInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { clearInput } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSearchInput", () => ({
    // Disables the clear button while there is nothing to clear.
    empty: true,

    init() {
      this.empty = !this.$refs.input.value;
    },

    // Runs on each input, and after an htmx swap, which can change the value.
    sync() {
      this.empty = !this.$refs.input.value;
      if (this.$root.dataset.filterItems) this.filter();
    },

    clear() {
      clearInput(this.$refs.input);
    },

    // Hides the rows of `data-filter-items` whose label misses the query.
    filter() {
      const query = this.$refs.input.value.trim().toLowerCase();
      for (const item of document.querySelectorAll(this.$root.dataset.filterItems)) {
        item.hidden = !(item.dataset.label ?? item.textContent).toLowerCase().includes(query);
      }
    },
  }));
});
