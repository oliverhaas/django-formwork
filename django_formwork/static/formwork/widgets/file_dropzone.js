// Alpine.data component for the formwork FileDropzoneInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { filePickerBase, fileList, formatSize } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkFileDropzone", () =>
    filePickerBase({
      dragging: false,

      get dragClass() {
        return { dragging: this.dragging };
      },

      get details() {
        if (this.files.length === 1) return formatSize(this.files[0].size);
        return this.files.map((file) => file.name).join(", ");
      },

      onDragOver() {
        this.dragging = true;
      },

      onDragLeave() {
        this.dragging = false;
      },

      // A drop fills the real file input, so the form posts the files and a section form saves at once.
      drop(event) {
        this.dragging = false;
        const input = this.$refs.input;
        const files = [...(event.dataTransfer?.files ?? [])];
        if (!files.length) return;
        input.files = fileList(input.multiple ? files : files.slice(0, 1));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      },

      clear() {
        this.files = [];
        this.error = "";
        this.$refs.input.value = "";
        this.$refs.input.dispatchEvent(new Event("change", { bubbles: true }));
      },
    }),
  );
});
