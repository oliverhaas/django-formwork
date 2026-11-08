// Alpine.data component for the formwork ClearableFileInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { filePickerBase, formatSize } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkClearableFileInput", () =>
    filePickerBase({
      cleared: false,

      init() {
        this.cleared = Boolean(this.$refs.clear?.checked);
      },

      get stored() {
        return "stored" in this.$root.dataset;
      },

      get empty() {
        return !this.files.length && !this.stored;
      },

      // A picked file shows instead of the stored one, which it replaces on save.
      get storedShown() {
        return this.stored && !this.files.length;
      },

      // Django rejects a new upload together with the clear box, so a pick unchecks it.
      get clearChecked() {
        return this.cleared && !this.files.length;
      },

      get removable() {
        return this.files.length > 0 || (this.storedShown && !this.cleared && Boolean(this.$refs.clear));
      },

      get restorable() {
        return this.storedShown && this.cleared;
      },

      get storedClass() {
        return { "line-through text-base-content/50": this.cleared };
      },

      get rowClass() {
        return { "input-error": Boolean(this.error) };
      },

      get size() {
        return formatSize(this.files.reduce((total, file) => total + file.size, 0));
      },

      get names() {
        return this.files.map((file) => file.name).join(", ");
      },

      remove() {
        if (this.files.length) this.discard();
        else this.setCleared(true);
      },

      restore() {
        this.setCleared(false);
      },

      discard() {
        this.files = [];
        this.error = "";
        this.$refs.input.value = "";
        this.fire(this.$refs.input);
      },

      // The change event reaches dirty tracking and section forms once Alpine has set the box.
      setCleared(cleared) {
        this.cleared = cleared;
        this.$nextTick(() => this.fire(this.$refs.clear));
      },

      fire(element) {
        element.dispatchEvent(new Event("change", { bubbles: true }));
      },
    }),
  );
});
