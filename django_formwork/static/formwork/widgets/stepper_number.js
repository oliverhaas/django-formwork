// Alpine.data component for the formwork StepperNumberInput widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

// Rounds away float noise (0.1 + 0.2) to the decimals of a numeric step.
const roundToStep = (value, step) => {
  if (step === "" || !Number.isFinite(Number(step))) return value;
  const factor = 10 ** (step.split(".")[1] || "").length;
  return Math.round(value * factor) / factor;
};

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkStepperNumber", () => ({
    // The input holds the value, so a morph that changes it needs no sync.
    step(direction) {
      const input = this.$refs.input;
      const value = (Number(input.value) || 0) + direction * (Number(input.step) || 1);
      this.commit(roundToStep(value, input.step));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    },

    // Typing stays untouched so the field can be cleared; only a settled value is coerced.
    onChange() {
      if (this.$refs.input.value === "") return;
      this.commit(Number(this.$refs.input.value));
    },

    commit(value) {
      const input = this.$refs.input;
      const min = this.$root.dataset.min ?? input.min;
      if (min !== "" && value < Number(min)) value = Number(min);
      if (input.max !== "" && value > Number(input.max)) value = Number(input.max);
      input.value = this.$root.dataset.integer === "true" ? Math.trunc(value) : value;
    },
  }));
});
