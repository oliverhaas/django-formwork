// Alpine.data component for the formwork PasswordInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkPasswordInput", () => ({
    show: false,

    get inputType() {
      return this.show ? "text" : "password";
    },

    toggle() {
      this.show = !this.show;
    },
  }));
});
