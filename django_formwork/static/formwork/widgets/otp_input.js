// Alpine.data component for the formwork OTPInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkOtpInput", () => ({
    digits: [],

    init() {
      this.digits = JSON.parse(this.$el.dataset.digits || "[]");
    },

    get combined() {
      return this.digits.join("");
    },
    handleInput(i, e) {
      const v = e.target.value.slice(-1);
      this.digits[i] = v;
      if (v && i < this.digits.length - 1) this.$refs["d" + (i + 1)].focus();
      this.$refs.hidden.value = this.combined;
      this.$refs.hidden.dispatchEvent(new Event("input", { bubbles: true }));
    },
    handleKey(i, e) {
      if (e.key === "Backspace" && !this.digits[i] && i > 0) {
        this.$refs["d" + (i - 1)].focus();
      }
    },
    handlePaste(e) {
      e.preventDefault();
      // Keep only digits, matching the inputmode="numeric" boxes.
      const text = (e.clipboardData || window.clipboardData)
        .getData("text")
        .replace(/\D/g, "")
        .slice(0, this.digits.length);
      if (!text) return;
      for (let i = 0; i < text.length; i++) {
        this.digits[i] = text[i];
      }
      const next = Math.min(text.length, this.digits.length - 1);
      this.$refs["d" + next].focus();
      this.$refs.hidden.value = this.combined;
      this.$refs.hidden.dispatchEvent(new Event("input", { bubbles: true }));
    },
  }));
});
