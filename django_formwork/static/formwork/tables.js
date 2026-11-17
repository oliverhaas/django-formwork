/**
 * tables.js: editable formset tables (formset.as_rows) and the errors of a table cell.
 *
 *   1. formworkFormset: adds and removes rows and keeps the formset's indexes and
 *      TOTAL_FORMS contiguous. A row is an element with data-formset-row="<form prefix>"
 *      in x-ref="rows"; Add another copies the row in <template x-ref="empty">. Each
 *      added row sends formset:added and each removal formset:removed, both bubbling,
 *      with detail.formsetName.
 *   2. A field in a table cell keeps its errors in DaisyUI's tooltip, so its row keeps
 *      its height. The tooltip shows while the pointer rests on the cell or the focus
 *      is in it.
 *
 * Load it with {% formwork_js %}, or with {{ formset.media }} after {% formwork_core_js %}.
 */

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkFormset", () => ({
    prefix: "",
    total: 0,
    min: 0,
    max: 1000,

    // A morph keeps this state, so the numbers come again from the markup after each swap.
    init() {
      this.read();
      this.onSwap = () => this.$root.isConnected && this.read();
      document.addEventListener("htmx:after:swap", this.onSwap);
    },

    destroy() {
      document.removeEventListener("htmx:after:swap", this.onSwap);
    },

    read() {
      this.prefix = this.$root.dataset.prefix;
      this.min = Number(this.$root.dataset.min) || 0;
      this.max = Number(this.$root.dataset.max) || 1000;
      this.total = Number(this.totalInput()?.value ?? this.rows().length);
    },

    get canAdd() {
      return this.total < this.max;
    },

    get canRemove() {
      return this.total > this.min;
    },

    rows() {
      return [...this.$refs.rows.querySelectorAll(":scope > [data-formset-row]")];
    },

    totalInput() {
      return this.$root.querySelector(`input[name="${CSS.escape(this.prefix)}-TOTAL_FORMS"]`);
    },

    setTotal(total) {
      this.total = total;
      const input = this.totalInput();
      if (input) input.value = String(total);
    },

    add() {
      if (!this.canAdd) return;
      const html = this.$refs.empty.innerHTML.replaceAll("__prefix__", String(this.total));
      this.$refs.rows.insertAdjacentHTML("beforeend", html);
      const row = this.$refs.rows.lastElementChild;
      this.setTotal(this.total + 1);
      row.dispatchEvent(new CustomEvent("formset:added", { bubbles: true, detail: { formsetName: this.prefix } }));
      this.$nextTick(() => row.querySelector("input:not([type=hidden]), select, textarea, summary")?.focus());
    },

    // $refs and $root resolve from the clicked button, so the row leaves the document last.
    remove(button) {
      const row = button.closest("[data-formset-row]");
      const root = this.$root;
      this.renumber(row);
      row.remove();
      root.dispatchEvent(new CustomEvent("formset:removed", { bubbles: true, detail: { formsetName: this.prefix } }));
    },

    // The rows after a removed one move up an index: every attribute that names the old prefix names the new one.
    renumber(removed) {
      const rows = this.rows().filter((row) => row !== removed);
      const prefix = escapeRegExp(this.prefix);
      rows.forEach((row, index) => {
        const current = row.dataset.formsetRow.match(new RegExp(`^${prefix}-(\\d+)$`))?.[1];
        if (current === undefined || Number(current) === index) return;
        const pattern = new RegExp(`${prefix}-${current}(?!\\d)`, "g");
        for (const el of [row, ...row.querySelectorAll("*")]) {
          for (const attr of [...el.attributes]) {
            const value = attr.value.replace(pattern, `${this.prefix}-${index}`);
            if (value !== attr.value) el.setAttribute(attr.name, value);
          }
        }
      });
      this.setTotal(rows.length);
    },
  }));
});

// --- The errors of a table cell ---
// Escape hides the tooltip. It waits while the cell's own dropdown is open, as that opens where
// it would. Its box sits in the top layer over the cell's widget, so the table's scroll box does
// not clip the message; every frame while it shows, the box follows the widget and hides with it
// under the table's edges.
const TIP_MARGIN = 8;
// DaisyUI's tooltip fades out in 0.2s, after a delay of 75ms.
const TIP_FADE = 300;
const tip = { hovered: null, focused: null, dismissed: null, cell: null, shown: false, clips: [], frame: 0, timer: 0 };

const tipBox = (cell) => cell?.querySelector(":scope > [data-cell-error]") ?? null;

const invalidCell = (el) => (el instanceof Element ? el.closest("td[data-invalid]") : null);

// The widget, without the cell's padding.
const tipAnchor = (cell) =>
  [...cell.children].find((el) => !el.matches("[data-cell-error], [hidden], input[type=hidden]") && el.getClientRects().length) ??
  cell;

const scrollBoxes = (cell) => {
  const boxes = [];
  for (let el = cell.parentElement; el && el !== document.body; el = el.parentElement) {
    const { overflowX, overflowY } = getComputedStyle(el);
    if (overflowX !== "visible" || overflowY !== "visible") boxes.push(el);
  }
  return boxes;
};

const placeTip = () => {
  const { cell } = tip;
  const box = tipBox(cell);
  if (!box || !cell.isConnected) return hideTip(true);
  const widget = tipAnchor(cell).getBoundingClientRect();
  const view = document.documentElement;
  const edges = { top: 0, right: view.clientWidth, bottom: view.clientHeight, left: 0 };
  for (const el of tip.clips) {
    const rect = el.getBoundingClientRect();
    edges.top = Math.max(edges.top, rect.top);
    edges.right = Math.min(edges.right, rect.right);
    edges.bottom = Math.min(edges.bottom, rect.bottom);
    edges.left = Math.max(edges.left, rect.left);
  }
  // The rows of a long list scroll under the table's header.
  const head = cell.closest("table")?.tHead;
  if (head) edges.top = Math.max(edges.top, head.getBoundingClientRect().bottom);
  const inView = widget.bottom > edges.top && widget.top < edges.bottom && widget.right > edges.left && widget.left < edges.right;
  const style = `left: ${widget.left}px; top: ${widget.top}px; width: ${widget.width}px; height: ${widget.height}px${inView ? "" : "; visibility: hidden"}`;
  if (box.getAttribute("style") !== style) box.setAttribute("style", style);
  // Under the widget, as in a form; above it when the window ends first.
  const message = box.firstElementChild;
  const room = message.offsetHeight + 2 * TIP_MARGIN;
  const above = widget.bottom + room > view.clientHeight && widget.top >= room;
  box.classList.toggle("tooltip-top", above);
  box.classList.toggle("tooltip-bottom", !above);
  // A message wider than the widget stays inside the window; the tail keeps pointing at the widget.
  const width = message.offsetWidth;
  const start = widget.left + widget.width / 2 - width / 2;
  const shift = Math.round(Math.min(Math.max(start, TIP_MARGIN), view.clientWidth - TIP_MARGIN - width) - start);
  const trans = shift ? `calc(-50% + ${shift}px)` : "";
  if (message.style.getPropertyValue("--tt-trans") !== trans) message.style.setProperty("--tt-trans", trans);
  tip.frame = requestAnimationFrame(placeTip);
};

const showTip = (cell) => {
  clearTimeout(tip.timer);
  if (tip.cell !== cell) {
    hideTip(true);
    const box = tipBox(cell);
    tip.cell = cell;
    tip.clips = scrollBoxes(cell);
    if (!box.matches(":popover-open")) box.showPopover();
    placeTip();
  }
  tip.shown = true;
  // A frame after the box opens, so DaisyUI's fade runs.
  requestAnimationFrame(() => {
    if (tip.cell === cell && tip.shown) tipBox(cell)?.classList.add("tooltip-open");
  });
};

const hideTip = (now) => {
  const box = tipBox(tip.cell);
  tip.shown = false;
  box?.classList.remove("tooltip-open");
  const close = () => {
    cancelAnimationFrame(tip.frame);
    tip.cell = null;
    if (box?.matches(":popover-open")) box.hidePopover();
  };
  clearTimeout(tip.timer);
  if (now || !tip.cell) close();
  else tip.timer = setTimeout(close, TIP_FADE);
};

const updateTip = () => {
  const cell = [tip.hovered, tip.focused].find(
    (el) =>
      el?.isConnected &&
      el !== tip.dismissed &&
      tipBox(el) &&
      !el.querySelector(":popover-open:not([data-cell-error]), details[open]"),
  );
  if (cell) showTip(cell);
  else if (tip.shown) hideTip(false);
};

document.addEventListener("pointerover", (event) => {
  const cell = invalidCell(event.target);
  if (cell === tip.hovered) return;
  tip.hovered = cell;
  tip.dismissed = null;
  updateTip();
});
// Otherwise the next element's pointerover tells where the pointer went.
document.addEventListener("pointerout", (event) => {
  if (event.relatedTarget || !tip.hovered) return;
  tip.hovered = null;
  updateTip();
});
document.addEventListener("focusin", (event) => {
  const cell = invalidCell(event.target);
  if (cell === tip.focused) return;
  tip.focused = cell;
  tip.dismissed = null;
  updateTip();
});
document.addEventListener("focusout", (event) => {
  if (event.relatedTarget || !tip.focused) return;
  tip.focused = null;
  updateTip();
});
// A dropdown opens or closes. The toggle event does not bubble, so it is caught on its way down.
document.addEventListener(
  "toggle",
  (event) => {
    if ((tip.hovered || tip.focused) && !event.target.matches?.("[data-cell-error]")) updateTip();
  },
  true,
);
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !tip.shown || event.defaultPrevented) return;
  event.preventDefault();
  tip.dismissed = tip.cell;
  hideTip(false);
});
