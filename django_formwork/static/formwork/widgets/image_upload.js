// Alpine.data component for the formwork ImageDropZone widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkImageUpload", () => ({
    preview: null,
    dragging: false,
    error: "",
    maxSize: 0,

    init() {
      this.maxSize = Number(this.$el.dataset.maxSize || "0");
    },

    isAccepted(file) {
      const accept = this.$refs.input.accept;
      if (!accept) return true;
      return accept.split(",").some((p) => {
        p = p.trim();
        if (p.endsWith("/*")) return file.type.startsWith(p.replace("/*", "/"));
        if (p.startsWith(".")) return file.name.toLowerCase().endsWith(p.toLowerCase());
        return file.type === p;
      });
    },
    loadPreview(file) {
      if (!file || !file.type.startsWith("image/")) return;
      const reader = new FileReader();
      reader.onload = (e) => (this.preview = e.target.result);
      reader.readAsDataURL(file);
    },
    handleDrop(e) {
      this.dragging = false;
      this.error = "";
      const file = e.dataTransfer.files[0];
      if (!file) return;
      if (!this.isAccepted(file)) {
        this.error = "File type not accepted";
        return;
      }
      if (this.maxSize && file.size > this.maxSize) {
        this.error = "File too large";
        return;
      }
      this.$refs.input.files = e.dataTransfer.files;
      this.loadPreview(file);
    },
    handleChange(e) {
      this.error = "";
      const file = e.target.files[0];
      if (!file) {
        this.preview = null;
        return;
      }
      if (!this.isAccepted(file)) {
        this.error = "File type not accepted";
        e.target.value = "";
        this.preview = null;
        return;
      }
      if (this.maxSize && file.size > this.maxSize) {
        this.error = "File too large";
        e.target.value = "";
        this.preview = null;
        return;
      }
      this.loadPreview(file);
    },
    clear() {
      this.preview = null;
      this.error = "";
      this.$refs.input.value = "";
    },
  }));
});
