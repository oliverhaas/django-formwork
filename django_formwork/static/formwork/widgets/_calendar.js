// The calendar that DatePicker, DateRangePicker and DateTimeRangePicker share:
// dates written in Django's format codes, the month grid, the month and year
// views, and the keyboard moves of the grid.

export const pad = (number, width = 2) => String(number).padStart(width, "0");

// new Date(year, ...) reads years 0-99 as 1900-1999.
export const makeDate = (year, month, day) => {
  const date = new Date(2000, 0, 1);
  date.setFullYear(year, month, day);
  return date;
};

export const isoDate = (date) => `${pad(date.getFullYear(), 4)}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

// The day that `text` spells as YYYY-MM-DD (the rest is ignored), or null for no real day.
export const parseIso = (text) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text || "");
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number);
  const date = makeDate(year, month - 1, day);
  return date.getMonth() === month - 1 && date.getDate() === day ? date : null;
};

export const addDays = (date, days) => makeDate(date.getFullYear(), date.getMonth(), date.getDate() + days);

// The same day `months` later, or the month's last day where it is shorter.
export const addMonths = (date, months) => {
  const lastDay = makeDate(date.getFullYear(), date.getMonth() + months + 1, 0).getDate();
  return makeDate(date.getFullYear(), date.getMonth() + months, Math.min(date.getDate(), lastDay));
};

// A picked day, month or year. The class also marks it for focus.
export const SELECTED = "btn-primary calendar-selected";

const parseJson = (text) => {
  try {
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
};

// --- Django's date format codes ----------------------------------------
// A port of django.utils.dateformat for the codes a date or a naive datetime
// writes. The time zone codes write nothing, as Django's do for a naive value.
// `names` holds the translated names from the widget (see _calendar.py).

const FORMAT_CODE = /(?<!\\)([aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ])/;

const isLeap = (year) => (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
const dayOfYear = (date) => Math.round((addDays(date, 0) - makeDate(date.getFullYear(), 0, 1)) / 86400000) + 1;
// Monday first, as Django's weekday names.
const weekdayIndex = (date) => (date.getDay() + 6) % 7;

const isoWeek = (date) => {
  const thursday = addDays(date, 3 - weekdayIndex(date));
  return { year: thursday.getFullYear(), week: Math.floor((dayOfYear(thursday) - 1) / 7) + 1 };
};

const englishSuffix = (day) => {
  if (day >= 11 && day <= 13) return "th";
  return { 1: "st", 2: "nd", 3: "rd" }[day % 10] || "th";
};

const CODES = {
  a: (d, names) => names.a?.[d.getHours() > 11 ? 1 : 0] ?? "",
  A: (d, names) => names.A?.[d.getHours() > 11 ? 1 : 0] ?? "",
  b: (d, names) => names.b?.[d.getMonth()] ?? "",
  c: (d) => `${isoDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`,
  d: (d) => pad(d.getDate()),
  D: (d, names) => names.D?.[weekdayIndex(d)] ?? "",
  e: () => "",
  E: (d, names) => names.E?.[d.getMonth()] ?? "",
  f: (d) => (d.getMinutes() ? `${CODES.g(d)}:${pad(d.getMinutes())}` : CODES.g(d)),
  F: (d, names) => names.F?.[d.getMonth()] ?? "",
  g: (d) => String(d.getHours() % 12 || 12),
  G: (d) => String(d.getHours()),
  h: (d) => pad(d.getHours() % 12 || 12),
  H: (d) => pad(d.getHours()),
  i: (d) => pad(d.getMinutes()),
  I: () => "",
  j: (d) => String(d.getDate()),
  l: (d, names) => names.l?.[weekdayIndex(d)] ?? "",
  L: (d) => (isLeap(d.getFullYear()) ? "True" : "False"),
  m: (d) => pad(d.getMonth() + 1),
  M: (d, names) => names.M?.[d.getMonth()] ?? "",
  n: (d) => String(d.getMonth() + 1),
  N: (d, names) => names.N?.[d.getMonth()] ?? "",
  o: (d) => String(isoWeek(d).year),
  O: () => "",
  P: (d, names) => {
    if (!d.getMinutes() && !d.getHours()) return names.P?.[0] ?? "";
    if (!d.getMinutes() && d.getHours() === 12) return names.P?.[1] ?? "";
    return `${CODES.f(d)} ${CODES.a(d, names)}`;
  },
  r: () => "",
  s: (d) => pad(d.getSeconds()),
  S: (d) => englishSuffix(d.getDate()),
  t: (d) => String(makeDate(d.getFullYear(), d.getMonth() + 1, 0).getDate()),
  T: () => "",
  u: () => "000000",
  U: () => "",
  w: (d) => String(d.getDay()),
  W: (d) => String(isoWeek(d).week),
  y: (d) => pad(d.getFullYear() % 100),
  Y: (d) => String(d.getFullYear()),
  z: (d) => String(dayOfYear(d)),
  Z: () => "",
};

// `date` written in a Django format string, as django.utils.dateformat.format writes it.
export const formatDjango = (date, format, names) =>
  format
    .split(FORMAT_CODE)
    .map((piece, index) => (index % 2 ? CODES[piece](date, names) : piece.replace(/\\(.)/g, "$1")))
    .join("");

// --- Reading typed dates -------------------------------------------------
// The range pickers read what the user types: the date in the Django format
// they write it in, or in one of the language's input formats (strftime, as
// Django's DATE_INPUT_FORMATS). Case does not matter, spaces, dots and commas
// may be left out, and any month name stands for any month code.

const escapeRegex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const fold = (text) => text.toLowerCase().replace(/\./g, "");
const separators = (text) => text.split(/[\s.,]+/).map(escapeRegex).join("[\\s.,]*");

// Matches any name of the lists and reads its index into `field`, the longest name first.
const nameReader = (lists, field) => {
  const entries = lists
    .flatMap((list) => (list || []).map((name, index) => [fold(name), index, name]))
    .filter(([folded]) => folded)
    .sort((a, b) => b[0].length - a[0].length);
  if (!entries.length) return { pattern: "(?!)" };
  return {
    // A name's own dots may be left out: "Sept", "Sept." and "pm" for "p.m.".
    pattern: entries.map(([, , name]) => name.toLowerCase().split(".").map(escapeRegex).join("\\.?")).join("|"),
    read: (parts, text) => {
      if (field) parts[field] = entries.find(([folded]) => folded === fold(text))[1];
    },
  };
};

const numberReader = (pattern, field, map = (number) => number) => ({
  pattern,
  read: (parts, text) => {
    parts[field] = map(Number(text));
  },
});

// Django's f ("3", "3:30") and P ("3:30 p.m.", "midnight", "noon").
const clockReader = (half, midnightNoon) => {
  const clock = "\\d{1,2}(?::\\d{2})?";
  const read = (parts, text) => {
    const [, time, rest] = /^([\d:]+)\s*(.*)$/.exec(text) || [];
    if (!time) {
      midnightNoon.read(parts, text);
      parts.hour = parts.noon * 12;
      return;
    }
    const [hour, minute] = time.split(":").map(Number);
    Object.assign(parts, { hour12: hour, minute: minute || 0 });
    if (rest) half.read(parts, rest);
  };
  return {
    f: { pattern: clock, read },
    P: { pattern: `${midnightNoon.pattern}|${clock}\\s*(?:${half.pattern})`, read },
  };
};

const readers = (names) => {
  const month = nameReader([names.F, names.E, names.N, names.b, names.M], "month");
  const weekday = nameReader([names.l, names.D]);
  const half = nameReader([names.a, names.A], "half");
  const fullYear = numberReader("\\d{4}", "year");
  // Python's %y reads 00-68 as 2000-2068 and 69-99 as 1969-1999.
  const shortYear = numberReader("\\d{2}", "year", (year) => year + (year < 69 ? 2000 : 1900));
  const monthNumber = numberReader("\\d{1,2}", "month", (number) => number - 1);
  const day = numberReader("\\d{1,2}", "day");
  const hour = numberReader("\\d{1,2}", "hour");
  const hour12 = numberReader("\\d{1,2}", "hour12");
  const minute = numberReader("\\d{2}", "minute");
  const { f, P } = clockReader(half, nameReader([names.P], "noon"));
  const ignored = (pattern) => ({ pattern });
  return {
    django: {
      d: day, j: day, m: monthNumber, n: monthNumber, y: shortYear, Y: fullYear,
      b: month, M: month, N: month, E: month, F: month, D: weekday, l: weekday,
      S: ignored("st|nd|rd|th|"), H: hour, G: hour, h: hour12, g: hour12, i: minute,
      s: ignored("\\d{2}"), u: ignored("\\d+"), a: half, A: half, f, P,
    },
    strftime: {
      Y: fullYear, y: shortYear, m: monthNumber, d: day, B: month, b: month, A: weekday, a: weekday,
      H: hour, I: hour12, M: minute, S: ignored("\\d{2}"), f: ignored("\\d{1,6}"), p: half,
    },
  };
};

// The day and time that `parts` hold, or null for no real day. A 12-hour
// clock without a.m. or p.m. reads as a 24-hour one.
const finish = (parts) => {
  const { year, month, day, hour12, half, minute = 0 } = parts;
  if (year === undefined || month === undefined || day === undefined) return null;
  const date = makeDate(year, month, day);
  if (date.getMonth() !== month || date.getDate() !== day) return null;
  const hour = hour12 === undefined ? parts.hour : half === undefined ? hour12 : (hour12 % 12) + half * 12;
  if (hour === undefined) return { iso: isoDate(date), time: "" };
  if (hour > 23 || minute > 59) return null;
  return { iso: isoDate(date), time: `${pad(hour)}:${pad(minute)}` };
};

const readPieces = (text, pieces) => {
  const reads = [];
  const source = pieces
    .map((piece) => {
      if (typeof piece === "string") return separators(piece);
      reads.push(piece.read);
      return `(${piece.pattern})`;
    })
    .join("");
  const match = new RegExp(`^\\s*${source}[\\s.,]*$`, "i").exec(text);
  if (!match) return null;
  const parts = {};
  reads.forEach((read, index) => read?.(parts, match[index + 1]));
  return finish(parts);
};

// Codes a typed date cannot carry (a time zone, a week number) match any word.
const djangoPieces = (format, codes) =>
  format.split(FORMAT_CODE).map((piece, index) => (index % 2 ? codes[piece] || { pattern: "\\S*?" } : piece.replace(/\\(.)/g, "$1")));

const strftimePieces = (format, codes) =>
  format.split(/%(.)/).map((piece, index) => (index % 2 ? codes[piece] || (piece === "%" ? "%" : { pattern: "\\S*?" }) : piece));

// The day `text` names as { iso: "YYYY-MM-DD", time: "HH:MM" or "" }, or null.
// `formats` are Django formats, `inputFormats` strftime formats.
export const readDate = (text, formats, inputFormats, names) => {
  if (!text.trim()) return null;
  const codes = readers(names);
  const tries = [
    ...formats.map((format) => djangoPieces(format, codes.django)),
    ...inputFormats.map((format) => strftimePieces(format, codes.strftime)),
  ];
  for (const pieces of tries) {
    const read = readPieces(text, pieces);
    if (read) return read;
  }
  return null;
};

// --- The calendar component -------------------------------------------
// Mixed into a widget component through withCalendar(). The widget supplies
// pickDay(cell), dayClass(cell), cellClass(cell), isSelected(cell) and hover(cell).

const calendarData = () => ({
  // "days", "months" or "years".
  view: "days",
  // The first month shown.
  year: 2000,
  month: 0,
  // The day that holds the grid's tab stop, as YYYY-MM-DD.
  focusIso: "",
  // 0 is Sunday, as Django's FIRST_DAY_OF_WEEK.
  firstDay: 0,
  monthCount: 1,
  names: {},
  formats: {},
  // The strftime formats a typed date may also take (see readDate).
  inputFormats: [],
  // Which month of the panel the month view was opened from.
  viewOffset: 0,

  // The calendar is as tall as it is: no cap, and it flips up whenever the
  // room below is short and above holds more.
  panelMaxHeight: Number.POSITIVE_INFINITY,
  panelUsableHeight: Number.POSITIVE_INFINITY,
  panelMatchesTrigger: false,

  initCalendar() {
    const data = this.$root.dataset;
    this.firstDay = Number(data.firstDay) || 0;
    this.monthCount = Number(data.months) || 1;
    this.names = parseJson(data.names);
    this.formats = parseJson(data.formats);
    this.inputFormats = data.inputFormats ? parseJson(data.inputFormats) : [];
  },

  formatted(date, key) {
    return date ? formatDjango(date, this.formats[key] || "Y-m-d", this.names) : "";
  },

  dateLabel(iso) {
    return this.formatted(parseIso(iso), "label");
  },

  // Opens the panel on the month of `iso`, or of today.
  resetView(iso) {
    const date = parseIso(iso) || new Date();
    this.view = "days";
    this.focusIso = isoDate(date);
    this.showMonth(date);
  },

  showMonth(date) {
    this.year = date.getFullYear();
    this.month = date.getMonth();
  },

  monthTitle(offset) {
    return this.formatted(makeDate(this.year, this.month + offset, 1), "title");
  },

  // Six weeks, so the panel keeps its height from month to month. A panel of
  // several months leaves out the days of the months beside each one.
  weeks(offset) {
    const first = makeDate(this.year, this.month + offset, 1);
    const start = addDays(first, -((first.getDay() - this.firstDay + 7) % 7));
    const today = isoDate(new Date());
    return Array.from({ length: 6 }, (_, week) =>
      Array.from({ length: 7 }, (_, column) => {
        const date = addDays(start, week * 7 + column);
        const iso = isoDate(date);
        const outside = date.getMonth() !== first.getMonth();
        return { iso, day: date.getDate(), outside, hidden: outside && this.monthCount > 1, today: iso === today };
      }),
    );
  },

  get firstIso() {
    return isoDate(makeDate(this.year, this.month, 1));
  },

  get lastIso() {
    return isoDate(makeDate(this.year, this.month + this.monthCount, 0));
  },

  // The day that Tab reaches in the grid: the focused day while it is shown,
  // else the first day of the first month.
  get tabIso() {
    return this.focusIso >= this.firstIso && this.focusIso <= this.lastIso ? this.focusIso : this.firstIso;
  },

  dayTabindex(cell) {
    return cell.iso === this.tabIso ? 0 : -1;
  },

  todayMark(cell) {
    return cell.today ? "date" : null;
  },

  focusGrid() {
    this.$nextTick(() => this.$refs.panel?.querySelector(`[data-date="${this.tabIso}"]`)?.focus());
  },

  moveFocus(date) {
    this.focusIso = isoDate(date);
    if (this.focusIso < this.firstIso) this.showMonth(date);
    if (this.focusIso > this.lastIso) this.showMonth(makeDate(date.getFullYear(), date.getMonth() - this.monthCount + 1, 1));
    this.focusGrid();
  },

  // The arrow keys move a day or a week, Home and End to the ends of the
  // week, Page Up and Page Down a month, or a year with Shift.
  onGridKey(event) {
    const date = parseIso(event.target.dataset?.date);
    if (!date || event.altKey || event.ctrlKey || event.metaKey) return;
    const back = getComputedStyle(event.target).direction === "rtl" ? 1 : -1;
    const column = (date.getDay() - this.firstDay + 7) % 7;
    const moves = {
      ArrowLeft: () => addDays(date, back),
      ArrowRight: () => addDays(date, -back),
      ArrowUp: () => addDays(date, -7),
      ArrowDown: () => addDays(date, 7),
      Home: () => addDays(date, -column),
      End: () => addDays(date, 6 - column),
      PageUp: () => addMonths(date, event.shiftKey ? -12 : -1),
      PageDown: () => addMonths(date, event.shiftKey ? 12 : 1),
    };
    if (!moves[event.key]) return;
    event.preventDefault();
    this.moveFocus(moves[event.key]());
  },

  // The arrows of the panel: a month in the day view, a year in the month
  // view, twelve years in the year view.
  page(direction) {
    if (this.view === "years") this.year += 12 * direction;
    else if (this.view === "months") this.year += direction;
    else this.showMonth(makeDate(this.year, this.month + direction, 1));
  },

  // The month view opens on the year of the month whose title was clicked.
  showMonths(offset) {
    this.viewOffset = offset;
    this.showMonth(makeDate(this.year, this.month + offset, 1));
    this.view = "months";
    this.focusView();
  },

  // The three views share one grid cell, so the hidden ones keep their size.
  viewClass(view) {
    return this.view === view ? "" : "invisible";
  },

  showYears() {
    this.view = "years";
    this.focusView();
  },

  pickMonth(month) {
    this.showMonth(makeDate(this.year, month - this.viewOffset, 1));
    this.view = "days";
    const focused = parseIso(this.focusIso) || new Date();
    const day = makeDate(this.year, month + 1, 0).getDate();
    this.focusIso = isoDate(makeDate(this.year, month, Math.min(focused.getDate(), day)));
    this.focusGrid();
  },

  pickYear(year) {
    this.year = year;
    this.view = "months";
    this.focusView();
  },

  focusView() {
    this.$nextTick(() => this.$refs.panel?.querySelector(`.calendar-${this.view} .calendar-selected`)?.focus());
  },

  get monthNames() {
    return this.names.M || [];
  },

  get years() {
    const first = this.year - (((this.year % 12) + 12) % 12);
    return Array.from({ length: 12 }, (_, index) => first + index);
  },

  get yearsTitle() {
    return `${this.years[0]}–${this.years[11]}`;
  },

  monthClass(month) {
    return month === this.month ? SELECTED : "btn-ghost";
  },

  yearClass(year) {
    return year === this.year ? SELECTED : "btn-ghost";
  },

  // A day that is not picked: today in primary text, days of the next or
  // previous month faded.
  dayTone(cell) {
    const tone = cell.today ? "btn-ghost text-primary font-semibold" : "btn-ghost";
    return cell.outside ? `${tone} calendar-outside` : tone;
  },
});

// Merges descriptors rather than values, so no getter runs before Alpine binds the component.
export const withCalendar = (component) =>
  Object.defineProperties(
    {},
    {
      ...Object.getOwnPropertyDescriptors(calendarData()),
      ...Object.getOwnPropertyDescriptors(component),
    },
  );
