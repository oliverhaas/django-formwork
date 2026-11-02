// Alpine.data component for the formwork ValidatedTextarea widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkValidatedTextarea", () => ({
    hasErrors: false,

    init() {
      this.hasErrors = this.$el.dataset.hasErrors === "true";
    },

    get ariaInvalid() {
      return this.hasErrors ? "true" : "false";
    },

    // The highlights sit under the text, so they scroll with it.
    syncScroll() {
      this.$refs.backdrop.scrollTop = this.$refs.textarea.scrollTop;
    },

    // htmx 4 posts the whole enclosing form; the endpoint reads only these three values.
    onValidateConfig(event) {
      const body = event.detail.ctx.request.body;
      for (const key of [...body.keys()]) body.delete(key);
      body.set("text", this.$refs.textarea.value);
      body.set("field_name", this.$refs.textarea.name);
      body.set("errors_id", this.$refs.errors.id);
    },

    // after:swap fires on the textarea once the out-of-band error swap is done.
    onValidated() {
      this.hasErrors = !!this.$refs.errors.querySelector("p");
    },
  }));
});
