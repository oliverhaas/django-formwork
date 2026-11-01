// Alpine.data component for the formwork SelectMultiple widget.
// `selected` maps each chosen value to its label and is the source of truth
// for the toggle text: a searched list holds only one page of rows, so the
// checked rows in the DOM cannot name the whole selection.

import { dropdownBase } from "./_helpers.js";

const sameKeys = (a, b) => {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((k) => k in b);
};

const parseSelected = (json) => Object.fromEntries(JSON.parse(json || "[]"));

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSelectMultiple", () =>
    dropdownBase({
      selected: {},
      selectedSuffix: "",
      summaryThreshold: 0,

      init() {
        const el = this.$el;
        this.watchOpen();
        this.anchorPanel();
        this.showSearch = el.dataset.showSearch === "true";
        this.placeholder = el.dataset.placeholder || "";
        this.selectedSuffix = el.dataset.selectedSuffix || "";
        this.summaryThreshold = Number(el.dataset.summaryThreshold);
        // The template server-renders the placeholder class on the summary so
        // it is styled at first paint, before Alpine loads. Strip it here, in
        // the same synchronous pass in which the :class binding re-applies it:
        // Alpine only ever removes classes it added itself, so a static copy
        // would go stale on the first pick.
        el.querySelector("summary")?.classList.remove("formwork-placeholder");
        this.readSelected();
        // A morph writes the server's selection here.
        new MutationObserver(() => this.readSelected()).observe(el, { attributeFilter: ["data-selected"] });
        el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
      },

      readSelected() {
        this.selected = parseSelected(this.$root.dataset.selected);
        this.syncChecked();
        this.writeValues();
      },

      // Asked by the formwork morph before a morph touches this root. A stale
      // echo (the response to an older submit, landing after further toggles)
      // must not revert the newer selection: the last toggle's change event
      // already armed a submit that carries all of it. The echo of that
      // submit confirms it.
      acceptMorph(newNode) {
        if (!this._dirty) return true;
        if (!sameKeys(parseSelected(newNode.dataset.selected), this.selected)) return false;
        this._dirty = false;
        return true;
      },

      // Reads the selection map, not the checked rows: a swap replaces them.
      get displayText() {
        const labels = Object.values(this.selected);
        if (labels.length > this.summaryThreshold) return `${labels.length} ${this.selectedSuffix}`;
        return labels.join(", ");
      },

      // Delegated on the stable <ul> so it also catches htmx-swapped rows.
      toggle(event) {
        const cb = event.target;
        if (cb.type !== "checkbox") return;
        if (cb.checked) this.selected[cb.dataset.value] = cb.dataset.label;
        else delete this.selected[cb.dataset.value];
        this._dirty = true;
        // Written back so that a morph to a different server selection is seen as a change.
        this.$root.dataset.selected = JSON.stringify(Object.entries(this.selected));
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

      // Rows a search or "Load more" swaps in render unchecked.
      syncChecked() {
        for (const cb of this.$refs.options.querySelectorAll("input[type=checkbox]")) {
          cb.checked = cb.dataset.value in this.selected;
        }
      },

      confirm() {
        this.confirmTarget()?.click();
      },
    }),
  );
});
