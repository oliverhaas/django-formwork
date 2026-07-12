// Alpine.data component for the formwork FileDropZone widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDropZone", () => ({
    files: [],
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
    validate(files) {
      this.error = "";
      const all = [...files];
      let valid = all.filter((f) => this.isAccepted(f));
      const typeRejected = all.length - valid.length;
      if (this.maxSize) {
        const oversized = valid.filter((f) => f.size > this.maxSize);
        valid = valid.filter((f) => f.size <= this.maxSize);
        if (oversized.length) this.error = oversized.length + " file(s) too large";
      }
      if (typeRejected) {
        this.error = (this.error ? this.error + ", " : "") + typeRejected + " file(s) wrong type";
      }
      return valid;
    },
    handleDrop(e) {
      this.dragging = false;
      const valid = this.validate(e.dataTransfer.files);
      if (!valid.length) return;
      const dt = new DataTransfer();
      valid.forEach((f) => dt.items.add(f));
      this.$refs.input.files = dt.files;
      this.files = valid;
    },
    handleChange(e) {
      const valid = this.validate(e.target.files);
      if (valid.length < e.target.files.length) {
        const dt = new DataTransfer();
        valid.forEach((f) => dt.items.add(f));
        e.target.files = dt.files;
      }
      this.files = valid;
    },
    clear() {
      this.files = [];
      this.error = "";
      this.$refs.input.value = "";
    },
    formatSize(bytes) {
      if (bytes < 1024) return bytes + " B";
      if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
      return (bytes / 1048576).toFixed(1) + " MB";
    },
  }));
});
