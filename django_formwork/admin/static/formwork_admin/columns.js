/**
 * columns.js: fits the changelist's columns to its width and its rows to the window.
 *
 * Columns that don't fit hide from the right behind a "+N" toggle that shows them all.
 * The checkbox, the first column and the link columns always show, and the first two
 * stay in view while the table scrolls sideways. The choice to show all columns is
 * kept per model.
 *
 * On a window of at least 40rem by FIT_MIN of rows, the table ends above the window's
 * bottom edge: its rows scroll inside it under the header, and the page keeps its
 * search, filters and pagination in view.
 *
 * Load it as a classic script in <head>. It fits the table while the page parses, and
 * the changelist holds its first frame until the table is parsed (<link rel="expect">),
 * so the first frame shows the fitted table.
 */
(() => {
  const KEY = "formwork-admin-columns";
  const SHADOW = "light-dark(rgb(0 0 0 / 0.14), rgb(0 0 0 / 0.55))";
  const TABLE = "#changelist-table";
  const ROWS = `${TABLE} > :is(thead, tbody) > tr:not([data-empty])`;
  const HEAD = `${TABLE} > thead > tr:not([data-empty])`;
  // The least height worth scrolling the rows in; below it the page scrolls as a whole.
  const FIT_MIN = 288;

  // Every rule lives in an adopted sheet, which a morph of the page content leaves alone.
  const sheet = new CSSStyleSheet();
  const heights = new CSSStyleSheet();
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet, heights];

  const state = {
    scroller: null,
    widths: [],
    cells: 0,
    expanded: false,
    // An error in a column the cut hides shows every column, until the user folds them again.
    forced: null,
    hidden: [],
    pins: [],
    start: false,
    end: false,
    // The rows are scrolled under the header.
    below: false,
    rules: "",
    height: "",
    key: "",
  };

  const resized = new ResizeObserver(() => fit());

  const storageKey = () => `${KEY}:${state.scroller.dataset.columns}`;

  const parts = () => {
    const scroller = document.getElementById("changelist-scroll");
    const table = scroller?.querySelector(":scope > table");
    const header = table?.tHead?.rows[0];
    // The header is complete after its last cell, the toggle, is parsed.
    if (!scroller?.dataset.columns || !header?.lastElementChild?.hasAttribute("data-col-toggle")) return null;
    return { scroller, table, cells: [...header.cells] };
  };

  // Each column's min-content width: the narrowest it gets before the table scrolls.
  const measure = () => {
    const found = parts();
    if (!found || !found.scroller.clientWidth) return;
    const { scroller, table, cells } = found;
    if (scroller !== state.scroller) {
      if (state.scroller) resized.unobserve(state.scroller);
      state.scroller = scroller;
      resized.observe(scroller);
      try {
        state.expanded = localStorage.getItem(storageKey()) === "all";
      } catch {
        state.expanded = false;
      }
    }
    sheet.replaceSync(`${TABLE} { width: 0 } ${TABLE} > thead > tr > [data-col-toggle] { display: table-cell }`);
    state.widths = cells.map((cell) => cell.getBoundingClientRect().width);
    state.cells = table.querySelectorAll("th, td").length;
    state.rules = "";
    state.forced = null;
    fit();
  };

  const fit = () => {
    const found = parts();
    if (!found || found.scroller !== state.scroller) return;
    const { scroller, table, cells } = found;
    const space = scroller.clientWidth;
    if (!space) return;
    if (cells.length !== state.widths.length) return measure();
    const widths = state.widths;
    const toggle = cells.length - 1;
    const hidden = [];
    if (widths.reduce((sum, width) => sum + width, 0) - widths[toggle] > space) {
      let room = space - widths[toggle];
      cells.forEach((cell, i) => {
        if (cell.hasAttribute("data-pin")) room -= widths[i];
      });
      let full = false;
      cells.forEach((cell, i) => {
        if (!cell.hasAttribute("data-col") || cell.hasAttribute("data-pin")) return;
        full ||= widths[i] > room;
        if (full) hidden.push(i);
        else room -= widths[i];
      });
    }
    // A fresh render with an error checks the cut once and brings the first error into view.
    let error = null;
    if (state.forced === null) {
      error = table.querySelector(":scope > tbody > tr > [data-invalid]");
      state.forced = hidden.some((i) => table.querySelector(`:scope > tbody > tr > :nth-child(${i + 1})[data-invalid]`));
    }
    state.hidden = hidden;
    // The cells up to the first column stay in view while the table scrolls.
    state.pins = [];
    let inset = 0;
    for (const [i, cell] of cells.entries()) {
      state.pins.push({ position: i + 1, inset });
      inset += widths[i];
      if (cell.hasAttribute("data-col")) break;
    }
    paint();
    if (error) reveal(error);
    edges();
    label(cells);
  };

  const open = () => state.expanded || Boolean(state.forced);

  // Scrolls the table sideways until the cell clears the toggle column.
  const reveal = (cell) => {
    const el = state.scroller;
    const box = el.getBoundingClientRect();
    const rect = cell.getBoundingClientRect();
    const room = state.hidden.length ? state.widths.at(-1) : 0;
    const rtl = getComputedStyle(el).direction === "rtl";
    const past = rtl ? box.left + room - rect.left : rect.right - (box.right - room);
    if (past > 0) el.scrollLeft += rtl ? -past : past;
  };

  const paint = () => {
    const dir = getComputedStyle(state.scroller).direction === "rtl" ? -1 : 1;
    const rules = state.pins.map(
      ({ position, inset }) =>
        `${ROWS} > :nth-child(${position}) { position: sticky; inset-inline-start: ${inset}px; z-index: 1; background-color: inherit }`,
    );
    const edge = state.pins.at(-1).position;
    const under = state.below ? `, 0 6px 8px -8px ${SHADOW}` : "";
    if (state.start) rules.push(`${ROWS} > :nth-child(${edge}) { box-shadow: ${8 * dir}px 0 8px -8px ${SHADOW} }`);
    if (state.hidden.length) {
      rules.push(
        `${ROWS} > [data-col-toggle] { display: table-cell; position: sticky; inset-inline-end: 0; z-index: 1; background-color: inherit }`,
        `${TABLE} [data-col-count]::after { content: "${state.hidden.length}" }`,
        `${TABLE} ${open() ? "[data-col-more]" : "[data-col-less]"} { display: none }`,
      );
      if (state.end) rules.push(`${ROWS} > [data-col-toggle] { box-shadow: ${-8 * dir}px 0 8px -8px ${SHADOW} }`);
      if (!open()) rules.push(`${ROWS} > :is(${state.hidden.map((i) => `:nth-child(${i + 1})`).join(", ")}) { display: none }`);
    }
    // A header cell with an edge shadow keeps the one toward the rows as well.
    if (state.start) rules.push(`${HEAD} > :nth-child(${edge}) { box-shadow: ${8 * dir}px 0 8px -8px ${SHADOW}${under} }`);
    if (state.hidden.length && state.end) {
      rules.push(`${HEAD} > [data-col-toggle] { box-shadow: ${-8 * dir}px 0 8px -8px ${SHADOW}${under} }`);
    }
    // The header's pinned cells cover the header cells and the rows that scroll under them.
    const corners = state.pins.map(({ position }) => `:nth-child(${position})`);
    if (state.hidden.length) corners.push("[data-col-toggle]");
    rules.push(`${HEAD} > :is(${corners.join(", ")}) { z-index: 3 }`);
    const text = rules.join("\n");
    if (text !== state.rules) {
      sheet.replaceSync(text);
      state.rules = text;
    }
  };

  // The shadows mark an edge that has columns scrolled under it.
  const edges = () => {
    const el = state.scroller;
    const scrolled = Math.abs(el.scrollLeft);
    const start = scrolled > 0;
    const end = scrolled + el.clientWidth < el.scrollWidth - 1;
    if (start === state.start && end === state.end) return;
    state.start = start;
    state.end = end;
    paint();
  };

  // The rows take the window's height that the page leaves them: the space under the
  // scroller's top, less the card's footer and the page's bottom padding, which holds the
  // floating bars. The header cells stick to the scroller's top in either case, and show
  // a shadow while rows are scrolled under them.
  const height = () => {
    const el = document.getElementById("changelist-scroll");
    const card = el?.closest(".card");
    const main = document.getElementById("content");
    if (!el || !card || !main) return;
    const rules = [`${HEAD} > * { position: sticky; top: 0; z-index: 2; background-color: inherit }`];
    if (!window.frameElement && window.matchMedia("(min-width: 40rem)").matches) {
      const box = el.getBoundingClientRect();
      const after = card.getBoundingClientRect().bottom - box.bottom + parseFloat(getComputedStyle(main).paddingBottom);
      const room = Math.floor(window.innerHeight - (box.top + window.scrollY) - after);
      if (room >= FIT_MIN) rules.push(`#changelist-scroll { max-height: ${room}px }`);
    }
    if (state.below) rules.push(`${HEAD} > * { box-shadow: 0 6px 8px -8px ${SHADOW} }`);
    const text = rules.join("\n");
    if (text !== state.height) {
      heights.replaceSync(text);
      state.height = text;
    }
  };
  const layout = new ResizeObserver(() => height());
  window.addEventListener("resize", height, { passive: true });

  const scrolled = (el) => {
    const below = el.scrollTop > 0;
    if (below === state.below) return;
    state.below = below;
    height();
    if (el === state.scroller) paint();
  };

  // The rows of a new list start at the top; a morph of the same list keeps their place.
  // Whatever moves the table's top, a message or the filters, resizes the page content.
  const watch = () => {
    const el = document.getElementById("changelist-scroll");
    const key = el?.closest("[data-total]")?.id ?? "";
    if (el && key !== state.key) {
      if (state.key) el.scrollTop = 0;
      state.key = key;
    }
    layout.disconnect();
    const main = document.getElementById("content");
    if (main) layout.observe(main);
    height();
  };

  // A morph resets the button's attributes to the server's, so each fit sets them again.
  const label = (cells) => {
    const button = cells.at(-1).querySelector("button");
    if (!button) return;
    const text = open() ? button.dataset.less : button.dataset.more;
    const names = state.hidden.map((i) => cells[i].textContent.trim()).join(", ");
    const attrs = { "aria-expanded": String(open()), "aria-label": text, title: open() || !names ? text : `${text}: ${names}` };
    for (const [name, value] of Object.entries(attrs)) {
      if (button.getAttribute(name) !== value) button.setAttribute(name, value);
    }
  };

  const toggle = () => {
    state.expanded = !open();
    state.forced = false;
    try {
      if (state.expanded) localStorage.setItem(storageKey(), "all");
      else localStorage.removeItem(storageKey());
    } catch {
      // Private windows can refuse storage; the choice then lasts for this page only.
    }
    fit();
  };

  // Fits the table as the parser adds its cells, before the browser paints them.
  const parsing = new MutationObserver(() => {
    const table = document.querySelector(TABLE);
    if (table && table.querySelectorAll("th, td").length !== state.cells) measure();
  });
  parsing.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", () => {
    parsing.disconnect();
    measure();
    watch();
  });

  // A swap that brings in new results fits them afresh; one that fills a dialog leaves the table as it is.
  document.addEventListener("htmx:after:swap", (event) => {
    const target = event.detail?.ctx?.target;
    if (!target?.contains || target.contains(document.getElementById("changelist-scroll"))) {
      measure();
      watch();
    }
  });
  document.fonts?.addEventListener("loadingdone", () => {
    measure();
    height();
  });
  document.addEventListener(
    "scroll",
    (event) => {
      if (event.target.id !== "changelist-scroll") return;
      scrolled(event.target);
      if (event.target === state.scroller) edges();
    },
    { capture: true, passive: true },
  );
  document.addEventListener("click", (event) => {
    if (event.target.closest?.(`${TABLE} [data-col-toggle] button`)) toggle();
  });
})();
