// Alpine.data component for the formwork ComboBox and ComboBoxMultiple widgets.
// In multiple mode the input holds comma-separated values; the *segment*
// after the last comma is what's being typed.  iconMap is hydrated from
// data-icons and grows as the user picks icon-bearing suggestions.

import { dropdownBase } from "./_helpers.js";

const splitValues = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);

// The values before the segment being typed; all of them after a trailing comma.
const confirmedValues = (v) => {
  const all = splitValues(v);
  const sep = /,\s*$/.test(v) || !all.length;
  return sep ? all : all.slice(0, -1);
};

// A multiple input shows a trailing ", " while focused; the form posts the
// list without it.
const stripTrailingSeparators = (form) => {
  form.addEventListener("formdata", (e) => {
    for (const input of form.querySelectorAll(".formwork-combobox[data-multiple=true] .combobox-input")) {
      if (input.value) e.formData.set(input.name, input.value.replace(/,\s*$/, ""));
    }
  });
};

const strippedForms = new WeakSet();

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkComboBox", () =>
    dropdownBase({
      // No <details> here: the list is a popover anchored on the wrapper.
      open: false,
      focused: false,
      multiple: false,
      iconMap: {},

      init() {
        const el = this.$el;
        this.multiple = el.dataset.multiple === "true";
        this.anchorPanel();
        // Open after x-show has run: a hidden panel has no height to measure
        // the drop against.
        this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
        try {
          this.iconMap = JSON.parse(el.dataset.icons || "{}");
        } catch {
          this.iconMap = {};
        }
        const form = el.closest("form");
        if (this.multiple && form && !strippedForms.has(form)) {
          strippedForms.add(form);
          stripTrailingSeparators(form);
        }
      },

      get isOpen() {
        return this.open;
      },

      get query() {
        return this.currentSegment;
      },

      get currentSegment() {
        this._v;
        const v = this.$refs.input?.value || "";
        if (!this.multiple) return v.trim();
        const parts = v.split(",");
        return parts[parts.length - 1].trim();
      },
      get displayParts() {
        this._v;
        const v = this.$refs.input?.value || "";
        if (!v.trim()) return [];
        if (this.multiple) return splitValues(v).map((t) => ({ text: t, icon: this.iconMap[t] || "" }));
        const ic = this.iconMap[v.trim()] || "";
        return ic ? [{ text: v.trim(), icon: ic }] : [];
      },
      // The icon overlay covers the input text while the input has no focus.
      get showDisplay() {
        return !this.focused && this.displayParts.length > 0;
      },
      get inputClass() {
        return this.showDisplay ? "text-transparent" : "";
      },
      get dropdownClass() {
        return this.open ? "dropdown-open" : "";
      },

      focusInput() {
        this.$refs.input.focus();
      },
      onFocus() {
        this.open = true;
        this.focused = true;
        const inp = this.$refs.input;
        if (this.multiple && inp.value && !/,\s*$/.test(inp.value)) {
          inp.value += ", ";
          this._v++;
        }
      },
      onInput() {
        this.open = true;
        this._v++;
        this.clearHighlight();
      },
      onBlur(event) {
        if (this.$root.contains(event.relatedTarget)) return;
        this.focused = false;
        // Tabbing to another control closes the list; a click is @click.outside's.
        if (event.relatedTarget) this.close();
        if (this.multiple) {
          const inp = this.$refs.input;
          inp.value = inp.value.replace(/,\s*$/, "");
          this._v++;
        }
      },
      close() {
        this.open = false;
        this.hidePanel();
        this.clearHighlight();
      },

      isSelected(el) {
        if (!this.multiple) return false;
        this._v;
        const label = (el.dataset.label || "").toLowerCase();
        return confirmedValues(this.$refs.input?.value || "").some((v) => v.toLowerCase() === label);
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
        const text = el.dataset.label;
        if (el.dataset.icon) this.iconMap[text] = el.dataset.icon;
        const inp = this.$refs.input;
        if (this.multiple) {
          const confirmed = confirmedValues(inp.value || "");
          const idx = confirmed.findIndex((c) => c.toLowerCase() === text.toLowerCase());
          if (idx >= 0) confirmed.splice(idx, 1);
          else confirmed.push(text);
          inp.value = confirmed.length ? `${confirmed.join(", ")}, ` : "";
          this._v++;
          this.clearHighlight();
          inp.focus();
          inp.dispatchEvent(new Event("input", { bubbles: true }));
        } else {
          inp.value = text;
          this._v++;
          this.close();
          // change, not input: the @input handler reopens the dropdown and the
          // search fires on input.
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      },
    }),
  );
});
