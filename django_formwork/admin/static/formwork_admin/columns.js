/**
 * columns.js: fits the changelist's columns to its width.
 *
 * Columns that don't fit hide from the right behind a "+N" toggle that shows them all.
 * The checkbox, the first column and the link columns always show, and the first two
 * stay in view while the table scrolls sideways. The choice to show all columns is
 * kept per model.
 *
 * The rows scroll with the page, and the header sticks under the page's top bar, whose
 * height base.html sets in --formwork-admin-top, and under the list's toolbar,
 * which sticks there first. The table's box clips its sides, so the
 * header can stick; a table with every column shown scrolls sideways in its box instead,
 * and its header then stays at the table's top.
 *
 * Load it as a classic script in <head>. It fits the table while the page parses, and
 * the changelist holds its first frame until the table is parsed (<link rel="expect">),
 * so the first frame shows the fitted table.
 */
(() => {
  const KEY = "formwork-admin-columns";
  const SHADOW = "light-dark(rgb(0 0 0 / 0.14), rgb(0 0 0 / 0.55))";
  const UNDER = "light-dark(rgb(0 0 0 / 0.06), rgb(0 0 0 / 0.3))";
  const TABLE = "#changelist-table";
  // A row's details span every column, so no column rule applies to them.
  const ROWS = `${TABLE} > :is(thead, tbody) > tr:not([data-empty], [data-row-details])`;
  const HEAD = `${TABLE} > thead > tr:not([data-empty])`;
  // A rule ends in tag names, so a change to the rules restyles the cells, not the page.
  const CELL = ":is(th, td)";
  // The room a new list's top keeps under the top bar.
  const GAP = 12;

  // Every rule lives in an adopted sheet, which a morph of the page content leaves alone.
  const sheet = new CSSStyleSheet();
  const heads = new CSSStyleSheet();
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet, heads];

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
    head: "",
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
    stick();
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
    // A pinned cell sits as high as the header's other cells, so their shadow ends at the pinned
    // column instead of darkening it under the pinned header cell's own shadow.
    const rules = state.pins.map(
      ({ position, inset }) =>
        `${ROWS} > ${CELL}:nth-child(${position}) { position: sticky; inset-inline-start: ${inset}px; z-index: 2; background-color: inherit }`,
    );
    const edge = state.pins.at(-1).position;
    if (state.start) rules.push(`${ROWS} > ${CELL}:nth-child(${edge}) { box-shadow: ${8 * dir}px 0 8px -8px ${SHADOW} }`);
    if (state.hidden.length) {
      rules.push(
        `${ROWS} > [data-col-toggle] { display: table-cell; position: sticky; inset-inline-end: 0; z-index: 2; background-color: inherit }`,
        `${TABLE} [data-col-count]::after { content: "${state.hidden.length}" }`,
        `${TABLE} ${open() ? "[data-col-more]" : "[data-col-less]"} { display: none }`,
      );
      if (state.end) rules.push(`${ROWS} > [data-col-toggle] { box-shadow: ${-8 * dir}px 0 8px -8px ${SHADOW} }`);
      if (!open()) rules.push(`${ROWS} > ${CELL}:is(${state.hidden.map((i) => `:nth-child(${i + 1})`).join(", ")}) { display: none }`);
    }
    // The header's pinned cells cover the header cells and the rows that scroll under them.
    const corners = state.pins.map(({ position }) => `:nth-child(${position})`);
    if (state.hidden.length) corners.push("[data-col-toggle]");
    rules.push(`${HEAD} > ${CELL}:is(${corners.join(", ")}) { z-index: 3 }`);
    // A table wider than its box scrolls sideways in it; any other box clips, so its header can stick to the page.
    // It clips both ways, as only then does it clip to its rounded corners. The menus and error tips in the
    // cells open in the top layer, so the clip doesn't cut them.
    if (!(state.hidden.length && open())) rules.push("#changelist-scroll { overflow: clip }");
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

  // The header cells stick under the top bar, and show a shadow while rows are under them.
  const stick = () => {
    const table = document.querySelector(TABLE);
    if (!table) return;
    const head = table.tHead?.getBoundingClientRect().top ?? 0;
    state.below = head - table.getBoundingClientRect().top > 0.5;
    // The list's toolbar sticks first, and the header under it. A table that scrolls sideways in its
    // box keeps its header at the top of that box. The toolbar's height takes in the room it keeps
    // under the top bar, and it is stuck while its bar has left the card's top edge.
    const toolbar = document.getElementById("changelist-toolbar");
    const bar = toolbar?.offsetHeight ?? 0;
    if (toolbar?.firstElementChild) {
      const edge = toolbar.parentElement.getBoundingClientRect().top;
      toolbar.toggleAttribute("data-stuck", toolbar.firstElementChild.getBoundingClientRect().top - edge > 0.5);
    }
    const top = state.hidden.length && open() ? "0px" : `calc(var(--formwork-admin-top, 0px) + ${bar}px)`;
    const rules = [`${HEAD} > ${CELL} { position: sticky; top: ${top}; z-index: 2; background-color: inherit }`];
    // Each cell draws its part of the shadow, edge to edge, so the shadow has no gaps.
    if (state.below) {
      rules.push(`${HEAD} > ${CELL}::after { content: ""; position: absolute; inset-inline: 0; top: 100%; height: 8px; background: linear-gradient(${UNDER}, #0000); pointer-events: none }`);
    }
    const text = rules.join("\n");
    if (text !== state.head) {
      heads.replaceSync(text);
      state.head = text;
    }
  };
  window.addEventListener("resize", stick, { passive: true });
  // The toolbar wraps on a narrow page, and its texts change with the selection.
  const bars = new ResizeObserver(stick);

  // A new list whose top is scrolled out of view starts at its top, under the top bar, so a page
  // link under the rows shows the next page's first rows. A morph of the same list keeps its place.
  const watch = () => {
    const el = document.getElementById("changelist-scroll");
    const key = el?.closest("[data-state]")?.dataset.state ?? "";
    if (el && key !== state.key) {
      const card = el.closest(".card") ?? el;
      const bar = parseFloat(getComputedStyle(el).getPropertyValue("--formwork-admin-top")) || 0;
      const above = card.getBoundingClientRect().top - bar - GAP;
      if (state.key && above < 0) window.scrollBy(0, above);
      state.key = key;
    }
    bars.disconnect();
    const bar = document.getElementById("changelist-toolbar");
    if (bar) bars.observe(bar);
    stick();
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

  // Fits the table that the parser has added before each frame, so no frame shows it
  // unfitted. Each fit lays out the whole table, so it runs once per frame, not once per
  // parsed chunk. The first frame waits for the footer, which ends the card, so the fit
  // runs as soon as the footer is parsed and sees every row before that frame starts.
  let frame = 0;
  let ended = false;
  // A script that changes the fitted table before the page has loaded, such as one that fills a
  // cell, gets it measured again then; a table that nothing changed keeps its fit.
  let changed = true;
  // The attributes that can change a cell's width; htmx marks links and forms with others.
  const SHAPE = ["class", "style", "hidden", "x-cloak"];
  const changes = new MutationObserver(() => {
    changed = true;
    changes.disconnect();
  });
  const parsed = () => {
    cancelAnimationFrame(frame);
    frame = 0;
    const table = document.querySelector(TABLE);
    if (table && table.querySelectorAll("th, td").length !== state.cells) {
      measure();
      if (ended) {
        changed = false;
        changes.observe(table, { subtree: true, childList: true, characterData: true, attributeFilter: SHAPE });
      }
    }
    if (ended) stick();
  };
  const parsing = new MutationObserver(() => {
    if (!ended && document.getElementById("changelist-footer")) {
      ended = true;
      parsed();
    } else {
      frame ||= requestAnimationFrame(parsed);
    }
  });
  parsing.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", () => {
    parsing.disconnect();
    if (changes.takeRecords().length) changed = true;
    changes.disconnect();
    cancelAnimationFrame(frame);
    frame = 0;
    const table = document.querySelector(TABLE);
    if (changed || table?.querySelectorAll("th, td").length !== state.cells) measure();
    else fit();
    watch();
  });

  // A swap that brings in new results fits them afresh; one that fills a dialog leaves the table as it is.
  // It fits as the swap puts the results in, so a page's crossfade (a view transition) shows the fitted table.
  document.addEventListener("htmx:before:settle", (event) => {
    if (event.target.contains?.(document.getElementById("changelist-scroll"))) {
      measure();
      watch();
    }
  });
  document.fonts?.addEventListener("loadingdone", () => {
    measure();
    stick();
  });
  document.addEventListener(
    "scroll",
    (event) => {
      if (event.target === document) stick();
      else if (event.target === state.scroller) edges();
    },
    { capture: true, passive: true },
  );
  document.addEventListener("click", (event) => {
    if (event.target.closest?.(`${TABLE} [data-col-toggle] button`)) toggle();
  });
})();
