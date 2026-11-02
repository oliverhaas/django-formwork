// Alpine.data component for the formwork Select widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { dropdownBase } from "./_helpers.js";

const CHOICE_ATTRIBUTES = ["data-value", "data-label", "data-icon", "data-label-html", "data-selected-toggle-class"];

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkSelect", () =>
    dropdownBase({
      value: "",
      label: "",
      icon: "",
      labelHtml: "",
      selectedToggleClass: "",

      init() {
        const el = this.$el;
        this.watchOpen();
        this.anchorPanel();
        this.showSearch = el.dataset.showSearch === "true";
        this.placeholder = el.dataset.placeholder || "";
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
        this.readChoice();
        // A morph writes the server's choice here, so a value the server
        // changed reaches the input.
        new MutationObserver(() => this.readChoice()).observe(el, { attributeFilter: CHOICE_ATTRIBUTES });
        el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
      },

      readChoice() {
        const data = this.$root.dataset;
        const value = data.value || "";
        // A server re-render can't always resolve the display metadata for
        // the current value: a searched Select backed by a plain CharField
        // knows only the submitted key, not its label, icon, or toggle class,
        // so it emits empty data-label/-icon/-selected-toggle-class. Treat
        // empties as "no info", not "clear it", so a value the client already
        // labelled keeps its display through the morph. When the value itself
        // changes, adopt the server's metadata (even empty) so a server-driven
        // change or clear still wins.
        if (value !== this.value || data.label) {
          this.label = data.label || "";
          this.icon = data.icon || "";
          this.labelHtml = data.labelHtml || "";
          this.selectedToggleClass = data.selectedToggleClass || "";
        }
        this.value = value;
        this._v++;
      },

      // Asked by the formwork morph before a morph touches this root. A
      // stale echo (the response to an older submit, landing after a newer
      // pick) must not revert the newer pick: its change event already
      // armed a fresh submit. The pick's own echo confirms it.
      acceptMorph(newNode) {
        if (!this._dirty) return true;
        if ((newNode.dataset.value || "") !== this.value) return false;
        this._dirty = false;
        return true;
      },

      get displayText() {
        this._v;
        return this.label || "";
      },

      isSelected(el) {
        return this.value === el.dataset.value;
      },

      onOptionClick(event) {
        const btn = event.target.closest("button[data-value]");
        if (btn) this.pick(btn);
      },

      confirm() {
        const target = this.confirmTarget();
        if (target) this.pick(target);
      },

      pick(el) {
        const cleared = el.dataset.value === "";
        this.choose({
          value: el.dataset.value,
          label: cleared ? "" : el.dataset.label,
          icon: cleared ? "" : el.dataset.icon || "",
          labelHtml: cleared ? "" : el.dataset.labelHtml || "",
          selectedToggleClass: cleared ? "" : el.dataset.selectedToggleClass || "",
        });
        this.$root.open = false;
      },

      clear() {
        this.choose({ value: "", label: "", icon: "", labelHtml: "", selectedToggleClass: "" });
      },

      choose(choice) {
        this._dirty = true;
        Object.assign(this, choice);
        // readChoice() reads these, so a cloned or restored copy keeps this
        // choice, and a morph to a different server choice is seen as a change.
        Object.assign(this.$root.dataset, choice);
        this.search = "";
        this._v++;
        this.clearHighlight();
        this.$nextTick(() => {
          const input = this.$root.querySelector("input[type=hidden]");
          if (input) input.dispatchEvent(new Event("change", { bubbles: true }));
        });
      },
    }),
  );
});
