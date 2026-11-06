// Alpine.data component for the formwork SelectMultiple widget.
// `selected` maps each chosen value to the markup the toggle shows for it and
// is the source of truth for the toggle: a searched list holds only one page
// of rows, so the checked rows in the DOM cannot name the whole selection.

import { countText, dropdownBase } from "./_helpers.js";

// The toggle renders with x-html for the option icons; plain text goes in escaped.
const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Mirrors _pick_html() on the server: the icon, then the rich label or the
// label text. Icons and rich labels are trusted markup, as in the rows.
const pickHtml = ({ label = "", icon, labelHtml }) => {
  const text = labelHtml || escapeHtml(label);
  return icon ? `${icon} ${text}` : text;
};

const parseSelected = (json) => Object.fromEntries(JSON.parse(json || "[]"));

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSelectMultiple", () =>
    dropdownBase({
      selected: {},
      summaryThreshold: 0,

      init() {
        const el = this.$el;
        this.watchOpen();
        this.anchorPanel();
        this.showSearch = el.dataset.showSearch === "true";
        this.placeholder = el.dataset.placeholder || "";
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

      get hasSelection() {
        return Object.keys(this.selected).length > 0;
      },

      get triggerClass() {
        return this.hasSelection ? "" : "formwork-placeholder";
      },

      // Reads the selection map, not the checked rows: a swap replaces them.
      get displayHtml() {
        const picks = Object.values(this.selected);
        if (!picks.length) return escapeHtml(this.placeholder);
        if (picks.length > this.summaryThreshold) return escapeHtml(countText(this.$root, picks.length));
        return picks.join(", ");
      },

      // Delegated on the stable <ul> so it also catches htmx-swapped rows.
      toggle(event) {
        const cb = event.target;
        if (cb.type !== "checkbox") return;
        if (cb.checked) this.selected[cb.dataset.value] = pickHtml(cb.dataset);
        else delete this.selected[cb.dataset.value];
        this.notePick();
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
