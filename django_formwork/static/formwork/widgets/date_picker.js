// Alpine.data component for the formwork DatePicker widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

// The names Python's strftime writes for %B, %b, %A and %a, so a picked day
// reads the same as a date the server rendered.
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const SHORT_MONTHS = MONTHS.map((name) => name.slice(0, 3));
const SHORT_WEEKDAYS = WEEKDAYS.map((name) => name.slice(0, 3));

const pad = (number, width = 2) => String(number).padStart(width, "0");
const nameIndex = (names, text) => names.findIndex((name) => name.toLowerCase() === text.toLowerCase());

// The strftime codes the calendar writes and reads. Any other code stays as text.
const CODES = {
  Y: {
    pattern: "\\d{4}",
    write: (d) => pad(d.getFullYear(), 4),
    read: (p, v) => { p.year = Number(v); },
  },
  y: {
    pattern: "\\d{2}",
    write: (d) => pad(d.getFullYear() % 100),
    // Python reads 00-68 as 2000-2068 and 69-99 as 1969-1999.
    read: (p, v) => { p.year = Number(v) + (Number(v) < 69 ? 2000 : 1900); },
  },
  m: {
    pattern: "\\d{1,2}",
    write: (d) => pad(d.getMonth() + 1),
    read: (p, v) => { p.month = Number(v) - 1; },
  },
  d: {
    pattern: "\\d{1,2}",
    write: (d) => pad(d.getDate()),
    read: (p, v) => { p.day = Number(v); },
  },
  B: {
    pattern: MONTHS.join("|"),
    write: (d) => MONTHS[d.getMonth()],
    read: (p, v) => { p.month = nameIndex(MONTHS, v); },
  },
  b: {
    pattern: SHORT_MONTHS.join("|"),
    write: (d) => SHORT_MONTHS[d.getMonth()],
    read: (p, v) => { p.month = nameIndex(SHORT_MONTHS, v); },
  },
  A: { pattern: WEEKDAYS.join("|"), write: (d) => WEEKDAYS[d.getDay()] },
  a: { pattern: SHORT_WEEKDAYS.join("|"), write: (d) => SHORT_WEEKDAYS[d.getDay()] },
  "%": { pattern: "%", write: () => "%" },
};

const isoDate = (date) => formatDate(date, "%Y-%m-%d");

function formatDate(date, format) {
  return format.replace(/%(.)/g, (text, code) => (CODES[code] ? CODES[code].write(date) : text));
}

// The ISO date that `text` spells in `format`, or "" if it spells no real day.
function parseDate(text, format) {
  const readers = [];
  const source = format.replace(/%(.)|[^%]+/g, (part, code) => {
    if (!CODES[code]) return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    readers.push(CODES[code].read);
    return `(${CODES[code].pattern})`;
  });
  const match = new RegExp(`^\\s*${source}\\s*$`, "i").exec(text);
  if (!match) return "";
  const parts = { year: 1900, month: 0, day: 1 };
  readers.forEach((read, i) => read?.(parts, match[i + 1]));
  const date = new Date(parts.year, parts.month, parts.day);
  const real = date.getFullYear() === parts.year && date.getMonth() === parts.month && date.getDate() === parts.day;
  return real ? isoDate(date) : "";
}

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDatePicker", () => ({
    open: false,
    // The picked day as YYYY-MM-DD; the input shows it in `format`.
    value: "",
    format: "%Y-%m-%d",
    month: null,
    year: null,
    days: [],

    init() {
      const el = this.$el;
      this.format = el.dataset.format || this.format;
      const sync = () => {
        this.value = el.dataset.value || "";
        const d = this.value ? new Date(this.value + "T00:00:00") : new Date();
        this.month = d.getMonth();
        this.year = d.getFullYear();
        this.buildDays();
      };
      sync();
      // A morph keeps this component, so init() runs once. A data-value the
      // server sends re-syncs the calendar, or it would highlight a stale day.
      new MutationObserver(sync).observe(el, {
        attributes: true,
        attributeFilter: ["data-value"],
      });
    },

    show() {
      this.open = true;
    },
    close() {
      this.open = false;
    },
    toggle() {
      this.open = !this.open;
    },
    // The box around the input is not a <label>, which would add the toggle's
    // name to the input's, so a click on its padding focuses the input here.
    focusInput() {
      this.$refs.input.focus();
    },
    // Escape closes an open calendar and goes no further, so a <dialog>
    // around the widget stays open.
    onEscape(event) {
      if (!this.open) return;
      event.preventDefault();
      event.stopPropagation();
      this.close();
    },
    // Focus moving to another control closes the calendar.
    onFocusOut(event) {
      if (event.relatedTarget && !this.$root.contains(event.relatedTarget)) this.close();
    },
    // Typed text counts in `format` or as ISO, like the server reads it.
    onInput() {
      const text = this.$refs.input.value;
      this.value = parseDate(text, this.format) || parseDate(text, "%Y-%m-%d");
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
      const date = new Date(this.year, this.month, day);
      this.value = isoDate(date);
      this.open = false;
      this.$refs.input.value = formatDate(date, this.format);
      this.$refs.input.dispatchEvent(new Event("change", { bubbles: true }));
    },
    isSelected(day) {
      if (!this.value || !day) return false;
      return this.value === isoDate(new Date(this.year, this.month, day));
    },
    isToday(day) {
      if (!day) return false;
      const t = new Date();
      return day === t.getDate() && this.month === t.getMonth() && this.year === t.getFullYear();
    },
    dayClass(day) {
      return { "btn-primary": this.isSelected(day), "font-bold": this.isToday(day) };
    },
    // Month and year in the page's language, so they match the translated labels.
    get title() {
      const lang = document.documentElement.lang || undefined;
      return new Date(this.year, this.month).toLocaleString(lang, { month: "long", year: "numeric" });
    },
  }));
});
