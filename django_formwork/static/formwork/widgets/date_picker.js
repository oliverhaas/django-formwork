// Alpine.data component for the formwork DatePicker widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDatePicker", () => ({
    open: false,
    value: "",
    month: null,
    year: null,
    days: [],

    init() {
      this.value = this.$el.dataset.value || "";
      const d = this.value ? new Date(this.value + "T00:00:00") : new Date();
      this.month = d.getMonth();
      this.year = d.getFullYear();
      this.buildDays();
    },

    buildDays() {
      const first = new Date(this.year, this.month, 1);
      const last = new Date(this.year, this.month + 1, 0);
      const startDay = first.getDay();
      this.days = [];
      for (let i = 0; i < startDay; i++) this.days.push(null);
      for (let d = 1; d <= last.getDate(); d++) this.days.push(d);
    },
    prev() {
      if (this.month === 0) {
        this.month = 11;
        this.year--;
      } else {
        this.month--;
      }
      this.buildDays();
    },
    next() {
      if (this.month === 11) {
        this.month = 0;
        this.year++;
      } else {
        this.month++;
      }
      this.buildDays();
    },
    pick(day) {
      const m = String(this.month + 1).padStart(2, "0");
      const d = String(day).padStart(2, "0");
      this.value = this.year + "-" + m + "-" + d;
      this.open = false;
      this.$refs.input.value = this.value;
      this.$refs.input.dispatchEvent(new Event("change", { bubbles: true }));
    },
    isSelected(day) {
      if (!this.value || !day) return false;
      const m = String(this.month + 1).padStart(2, "0");
      const d = String(day).padStart(2, "0");
      return this.value === this.year + "-" + m + "-" + d;
    },
    isToday(day) {
      if (!day) return false;
      const t = new Date();
      return day === t.getDate() && this.month === t.getMonth() && this.year === t.getFullYear();
    },
    monthName() {
      return new Date(this.year, this.month).toLocaleString("default", { month: "long" });
    },
  }));
});
