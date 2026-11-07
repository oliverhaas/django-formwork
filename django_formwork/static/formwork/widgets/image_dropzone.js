// Alpine.data component for the formwork ImageDropzoneInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { acceptsFile, fileList } from "./_helpers.js";

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkImageDropzone", () => ({
    dragging: false,
    cleared: false,
    preview: null,
    error: "",

    get dragClass() {
      return { dragging: this.dragging };
    },

    // The stored image shows until the user clears it or picks a new one.
    get stored() {
      return "stored" in this.$root.dataset && !this.cleared && !this.preview;
    },

    get empty() {
      return !this.preview && !this.stored;
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

    // A drop fills the real file input, so the form posts the file and a section form saves at once.
    drop(event) {
      this.dragging = false;
      const file = event.dataTransfer?.files[0];
      if (!this.$refs.input || !file) return;
      this.$refs.input.files = fileList([file]);
      this.fire(this.$refs.input);
    },

    onChange() {
      const input = this.$refs.input;
      const file = input.files[0];
      this.preview = null;
      if (!file || !this.check(file)) {
        input.value = "";
        return;
      }
      // A new upload replaces the stored file; with the clear flag Django would reject it.
      this.$refs.clear.value = "";
      const reader = new FileReader();
      reader.onload = () => {
        this.preview = reader.result;
      };
      reader.readAsDataURL(file);
    },

    // Client-side hints only; the field validates the upload.
    check(file) {
      const { maxSize, typeError, sizeError } = this.$root.dataset;
      this.error = "";
      if (!acceptsFile(file, this.$refs.input.accept)) this.error = typeError;
      else if (maxSize && file.size > Number(maxSize)) this.error = sizeError;
      return !this.error;
    },

    discard() {
      this.$refs.input.value = "";
      this.$refs.clear.value = this.cleared ? "true" : "";
      this.preview = null;
      this.fire(this.$refs.input);
    },

    // Asks the server to delete the stored image.
    clear() {
      this.$refs.clear.value = "true";
      this.cleared = true;
      this.fire(this.$refs.clear);
    },

    fire(element) {
      element.dispatchEvent(new Event("change", { bubbles: true }));
    },
  }));
});
