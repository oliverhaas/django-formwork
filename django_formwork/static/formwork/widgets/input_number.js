// Alpine.data component for the formwork InputNumber widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkInputNumber", () => ({
    val: "",
    min: null,
    max: null,
    step: 1,

    init() {
      const el = this.$el;
      this.val = el.dataset.value || "";
      this.min = el.dataset.min === "" ? null : Number(el.dataset.min);
      this.max = el.dataset.max === "" ? null : Number(el.dataset.max);
      this.step = Number(el.dataset.step || "1");
    },

    _num() {
      const n = Number(this.val);
      return Number.isFinite(n) ? n : 0;
    },
    _round(v) {
      const d = (String(this.step).split(".")[1] || "").length;
      const f = 10 ** d;
      return Math.round(v * f) / f;
    },
    dec() {
      const v = this._round(this._num() - this.step);
      this.val = this.min !== null && v < this.min ? this.min : v;
      this.sync();
    },
    inc() {
      const v = this._round(this._num() + this.step);
      this.val = this.max !== null && v > this.max ? this.max : v;
      this.sync();
    },
    sync() {
      this.$refs.input.value = this.val;
      this.$refs.input.dispatchEvent(new Event("input", { bubbles: true }));
    },
  }));
});
