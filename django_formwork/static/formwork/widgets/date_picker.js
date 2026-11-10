// Alpine.data component for the formwork DatePicker widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

import { dropdownBase } from "./_helpers.js";
import { isoDate, pad, parseIso, SELECTED, withCalendar } from "./_calendar.js";

// The names Python's strftime writes for %B, %b, %A and %a, so a picked day
// reads the same as a date the server rendered.
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const SHORT_MONTHS = MONTHS.map((name) => name.slice(0, 3));
const SHORT_WEEKDAYS = WEEKDAYS.map((name) => name.slice(0, 3));

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
  Alpine.data("formworkDatePicker", () =>
    dropdownBase(
      withCalendar({
        open: false,
        // The picked day as YYYY-MM-DD; the input shows it in `format`.
        value: "",
        format: "%Y-%m-%d",
        _quietFocus: false,

        init() {
          const el = this.$el;
          this.format = el.dataset.format || this.format;
          this.initCalendar();
          this.anchorPanel();
          // Open after x-show has run: a hidden panel has no height to measure.
          this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
          const sync = () => {
            this.value = el.dataset.value || "";
          };
          sync();
          // A morph keeps this component, so init() runs once. A data-value the
          // server sends re-syncs the calendar, or it would mark a stale day.
          new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: ["data-value"] });
        },

        get isOpen() {
          return this.open;
        },

        show() {
          if (this.open) return;
          this.resetView(this.value);
          this.open = true;
        },
        close() {
          this.open = false;
          this.hidePanel();
        },
        toggle() {
          if (this.open) this.close();
          else this.show();
        },
        // The box around the input is not a <label>, which would add the toggle's
        // name to the input's, so a click on its padding focuses the input here.
        // The toggle's click goes on to the page, so an open dropdown elsewhere closes.
        focusInput(event) {
          if (event.target.closest(".date-picker-toggle")) return;
          this.$refs.input.focus();
        },
        // Back in the input after a pick, without opening the calendar again.
        refocusInput() {
          this._quietFocus = true;
          this.$refs.input.focus();
          this._quietFocus = false;
        },
        onInputFocus() {
          if (!this._quietFocus) this.show();
        },
        // Arrow Down moves from the input into the open calendar.
        onInputDown(event) {
          event.preventDefault();
          this.show();
          this.focusGrid();
        },
        // A click on a day leaves the focus in the input, so typing goes on.
        keepInputFocus(event) {
          if (event.target.closest("button") && this.$refs.input === document.activeElement) event.preventDefault();
        },
        // Escape closes an open calendar and goes no further, so a <dialog>
        // around the widget stays open.
        onEscape(event) {
          if (!this.open) return;
          event.preventDefault();
          event.stopPropagation();
          const refocus = this.$refs.panel.contains(document.activeElement);
          this.close();
          if (refocus) this.refocusInput();
        },
        // Typed text counts in `format` or as ISO, like the server reads it.
        onInput() {
          const text = this.$refs.input.value;
          this.value = parseDate(text, this.format) || parseDate(text, "%Y-%m-%d");
          const date = parseIso(this.value);
          if (date && this.open && this.view === "days") {
            this.focusIso = this.value;
            this.showMonth(date);
          }
        },

        write(iso) {
          this.value = iso;
          const date = parseIso(iso);
          this.$refs.input.value = date ? formatDate(date, this.format) : "";
          this.$refs.input.dispatchEvent(new Event("change", { bubbles: true }));
          this.close();
          this.refocusInput();
        },
        pickDay(cell) {
          this.write(cell.iso);
        },
        pickToday() {
          this.write(isoDate(new Date()));
        },
        clear() {
          this.write("");
        },
        hover() {},

        isSelected(cell) {
          return cell.iso === this.value;
        },
        cellClass() {
          return "";
        },
        dayClass(cell) {
          return cell.iso === this.value ? SELECTED : this.dayTone(cell);
        },
      }),
    ),
  );
});
