// Alpine.data component for the formwork SearchInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { clearInput } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSearchInput", () => ({
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
