// Alpine.data component for the formwork ValidatedTextarea widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkValidatedTextarea", () => ({
    hasErrors: false,

    init() {
      this.hasErrors = this.$el.dataset.hasErrors === "true";
    },
  }));
});
