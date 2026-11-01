// Alpine.data component for the formwork FileDropzoneInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { acceptsFile, fileList } from "./_helpers.js";

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
};

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkFileDropzone", () => ({
    files: [],
    dragging: false,
    error: "",

    get dragClass() {
      return { dragging: this.dragging };
    },

    // One file shows its name, several their count.
    get summary() {
      if (this.files.length === 1) return this.files[0].name;
      return `${this.files.length} ${this.$root.dataset.filesSelected}`;
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

    browse() {
      this.$refs.input.click();
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

    // Keeps the accepted files in the input and reports the rest. Client-side hints only.
    onChange() {
      const input = this.$refs.input;
      const { maxSize, typeError, sizeError } = this.$root.dataset;
      const picked = [...input.files];
      const accepted = picked.filter((file) => acceptsFile(file, input.accept));
      const kept = maxSize ? accepted.filter((file) => file.size <= Number(maxSize)) : accepted;
      this.error = accepted.length < picked.length ? typeError : kept.length < accepted.length ? sizeError : "";
      if (kept.length < picked.length) input.files = fileList(kept);
      this.files = kept;
    },

    clear() {
      this.files = [];
      this.error = "";
      this.$refs.input.value = "";
      this.$refs.input.dispatchEvent(new Event("change", { bubbles: true }));
    },
  }));
});
