// Helpers shared by the formwork Alpine.data components, and the base of the
// dropdowns (formworkSelect, formworkSelectMultiple, formworkComboBox).

// Reset that also notifies x-model and any htmx trigger bound to `input`.
export const clearInput = (input) => {
  input.value = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
};

// Mirrors the file input's `accept` list: MIME types, `type/*` and extensions.
export const acceptsFile = (file, accept) =>
  !accept ||
  accept.split(",").some((part) => {
    const pattern = part.trim().toLowerCase();
    if (pattern.endsWith("/*")) return file.type.startsWith(pattern.slice(0, -1));
    if (pattern.startsWith(".")) return file.name.toLowerCase().endsWith(pattern);
    return file.type === pattern;
  });

// A FileList, the only type a file input's `files` accepts.
export const fileList = (files) => {
  const transfer = new DataTransfer();
  for (const file of files) transfer.items.add(file);
  return transfer.files;
};

// The page's language, so numbers and plurals match the translated text.
export const pageLang = () => document.documentElement.lang || undefined;

// The text for `count` from the plural forms in `data-count-text`, which the
// widget keys by CLDR plural category.
export const countText = (el, count) => {
  const forms = JSON.parse(el.dataset.countText || "{}");
  const form = forms[new Intl.PluralRules(pageLang()).select(count)] ?? forms.other ?? "";
  return form.replace("%(count)s", count);
};

// --- File pickers ------------------------------------------------------
// The base of formworkFileDropzone and formworkClearableFileInput: the picked
// files, the client-side accept and size checks, and their text and icon.

// A byte count in B, KB or MB, in the page's language.
export const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  const [value, unit] = bytes < 1048576 ? [bytes / 1024, "KB"] : [bytes / 1048576, "MB"];
  return `${value.toLocaleString(pageLang(), { maximumFractionDigits: 1, useGrouping: false })} ${unit}`;
};

// The icon class for a file name, from the extension lists in `data-file-icons`,
// which the widget keys by icon name.
const iconFor = (el, name) => {
  const dot = name.lastIndexOf(".");
  const extension = dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
  const icons = Object.entries(JSON.parse(el.dataset.fileIcons || "{}"));
  const match = icons.find(([, extensions]) => extension && extensions.split(" ").includes(extension));
  return `icon-${match ? match[0] : "file"}`;
};

const filePickerData = () => ({
  files: [],
  error: "",

  // One file shows its name, several their count.
  get summary() {
    if (this.files.length === 1) return this.files[0].name;
    return countText(this.$root, this.files.length);
  },

  get fileIcon() {
    if (this.files.length > 1) return "icon-files";
    return this.files.length ? iconFor(this.$root, this.files[0].name) : "";
  },

  browse() {
    this.$refs.input.click();
  },

  // Keeps the accepted files in the input and reports the rest. Client-side hints only.
  onChange() {
    const input = this.$refs.input;
    const { maxSize, typeError, sizeError } = this.$root.dataset;
    const picked = [...input.files];
    const accepted = picked.filter((file) => acceptsFile(file, input.accept));
    const kept = maxSize ? accepted.filter((file) => file.size <= Number(maxSize)) : accepted;
    this.error = accepted.length < picked.length ? typeError : kept.length < accepted.length ? sizeError : "";
    if (kept.length < picked.length) input.files = fileList(kept);
    this.files = kept;
  },
});

// Same descriptor merge as dropdownBase below.
export const filePickerBase = (component) =>
  Object.defineProperties(
    {},
    {
      ...Object.getOwnPropertyDescriptors(filePickerData()),
      ...Object.getOwnPropertyDescriptors(component),
    },
  );

let highlightIds = 0;

const visibleOptions = (component) =>
  [...component.$refs.options.querySelectorAll("[data-value]")].filter((el) => el.offsetParent !== null);

const labelMatches = (el, query) => (el.dataset.label || "").toLowerCase().includes(query);

// Reads the row's own label, so no option value is interpolated into JS. A
// group heading shows while any row of its group does.
const matchesQuery = (el, query) => {
  if (!query) return true;
  const q = query.toLowerCase();
  if (!("group" in el.dataset)) return labelMatches(el, q);
  for (let row = el.nextElementSibling; row && !("group" in row.dataset); row = row.nextElementSibling) {
    if (labelMatches(row, q)) return true;
  }
  return false;
};

// What syncRows() writes on a row, and what a morph sets back to the server's.
const ROW_ATTRIBUTES = ["aria-selected", "class", "id", "style"];

const setAttribute = (el, name, value) => {
  if (el.getAttribute(name) !== value) el.setAttribute(name, value);
};

// As x-show does it.
const setShown = (el, shown) => {
  if (shown === (el.style.display !== "none")) return;
  if (!shown) {
    el.style.display = "none";
    return;
  }
  el.style.removeProperty("display");
  if (!el.style.length) el.removeAttribute("style");
};

// --- Top-layer dropdown panels -----------------------------------------
// popover="manual" (not "auto"): the details open attribute (the combobox's
// `open`) stays the source of truth, so light dismiss must not close the
// popover behind its back. CSS anchor positioning places the panel where
// supported, setDropDirection() otherwise; with no Popover API the panel
// stays absolutely positioned.

const supportsPopover = typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
const supportsAnchor = typeof CSS !== "undefined" && CSS.supports("anchor-name: --a");

// The first mirrors the panel's max-h-72 in the templates.
const PANEL_MAX_HEIGHT = 288;
// Matches the anchor-positioned margin (0.25rem).
const PANEL_OFFSET = 4;
const VIEWPORT_MARGIN = 8;
// Below this a list is too cramped to pick from, so flipping up is worth it.
const PANEL_USABLE_HEIGHT = 192;

const borderHeight = (el) => {
  const style = getComputedStyle(el);
  return parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
};

let anchorSeq = 0;

const FOCUSABLE = "input, button, select, textarea, a[href], summary, [tabindex]";

// Whether focus that leaves root moved to another control. A move to an
// element around root is none: a press on a part of root that takes no focus,
// such as a scrollbar, focuses the nearest focusable ancestor.
export const outside = (root, to) => Boolean(to) && !root.contains(to) && !to.contains(root);

// Close any open formwork <details> dropdown when a real click lands outside
// it, so a click anywhere else on the page (including another dropdown's
// trigger) dismisses it. Native <details> has no such behaviour, and light
// dismiss is off. Other <details> on the page keep their own behaviour. One
// shared listener rather than a per-widget @click.outside: this module loads
// once (ES-module dedup), and setting `open = false` lets each widget's open
// observer hide its panel. A genuine click only, never a morph, so it cannot
// close a panel behind the widget's back.
if (typeof document !== "undefined") {
  document.addEventListener("click", (e) => {
    for (const details of document.querySelectorAll('details[open][x-data^="formwork"]')) {
      if (!details.contains(e.target)) details.open = false;
    }
  });
}

// --- Widgets that start on first use -----------------------------------
// A page with many widgets, such as a formset or an editable list, spent most
// of its load starting them, while the server's markup already shows each one
// as it is. Alpine skips a root with data-formwork-lazy and its content, as
// x-ignore does, until the first event that reaches it: a press, focus, a key,
// its opening, or a formwork:start from a script that is about to call into it.
// The started mark is a property, so a morph keeps it on a started root, and a
// root that a swap brings in waits again.
const START_EVENTS = ["pointerdown", "focus", "keydown", "click", "toggle", "input", "change", "formwork:start"];

if (typeof document !== "undefined") {
  document.addEventListener("alpine:init", () => {
    Alpine.interceptInit((el) => {
      if (el.hasAttribute("data-formwork-lazy") && !el._formworkStarted) el._x_ignore = true;
    });
    // htmx's alpine-compat extension evaluates the server's copy of each node
    // that a morph keeps, in the scope of the kept node. A node in a widget
    // that has not started has no scope, so its copy is left alone too.
    Alpine.interceptClone((from, to) => {
      if (Alpine.findClosest(from, (el) => el._x_ignore)) to._x_ignore = true;
    });
  });
  // On the way down to the widget, so the listeners it adds run for this event.
  const start = (event) => {
    const root = event.target.closest?.("[data-formwork-lazy]");
    if (!root || root._formworkStarted) return;
    root._formworkStarted = true;
    // Before Alpine walks the page, the mark alone lets the root through.
    if (!root._x_ignore) return;
    delete root._x_ignore;
    Alpine.initTree(root);
  };
  for (const type of START_EVENTS) document.addEventListener(type, start, true);
}

// --- Widgets that the server sent as a stub ----------------------------
// An editable list renders its selects and date pickers as stubs: the closed
// widget, and the value in an input that posts as the full widget's would. A
// hover that rests on a stub, a focus or a press loads the full widget from
// the stub's URL and puts it in the stub's place, started, so that the focus,
// the typed text and the press move over to it.
const STUB_HOVER_DELAY = 80;

if (typeof document !== "undefined") {
  const loading = new WeakMap();
  const stubOf = (event) => event.target.closest?.("[data-formwork-stub]");
  // The part of the full widget that stands where `el` stood in the stub.
  const twin = (widget, el) => {
    if (el.id) return document.getElementById(el.id);
    return widget.querySelector(el.classList.length ? `${el.localName}.${el.classList[0]}` : el.localName);
  };
  const swapIn = (stub, html) => {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const widget = template.content.firstElementChild;
    if (!widget || !stub.isConnected) return;
    const active = stub.contains(document.activeElement) ? document.activeElement : null;
    const typed = stub.querySelector('input:not([type="hidden"])');
    // Started at once: the focus and the press below need its listeners, and
    // Alpine's own observer would only see it after them.
    widget._formworkStarted = true;
    Alpine.mutateDom(() => stub.replaceWith(widget));
    Alpine.initTree(widget);
    window.htmx?.process?.(widget);
    const input = typed && twin(widget, typed);
    if (input && typed.value !== typed.defaultValue) {
      input.value = typed.value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (active) twin(widget, active)?.focus();
    if (stub._formworkPress) twin(widget, stub._formworkPress)?.click();
  };
  const load = (stub) => {
    if (!loading.has(stub)) {
      // The stub's inputs, which hold the value that the full widget shows.
      const query = new URLSearchParams();
      for (const input of stub.querySelectorAll("[name]")) query.append(input.name, input.value);
      const url = `${stub.dataset.formworkStub}&${query}`;
      const done = fetch(url, { credentials: "same-origin" })
        .then((response) => (response.ok ? response.text() : Promise.reject(new Error(response.statusText))))
        .then((html) => swapIn(stub, html))
        // The next hover, focus or press tries again.
        .catch(() => loading.delete(stub));
      loading.set(stub, done);
    }
    return loading.get(stub);
  };

  // A pointer that only passes over a list loads nothing.
  let hover = null;
  document.addEventListener(
    "pointerover",
    (event) => {
      const stub = stubOf(event);
      if (!stub || stub === hover?.stub || loading.has(stub)) return;
      clearTimeout(hover?.timer);
      hover = { stub, timer: setTimeout(() => load(stub), STUB_HOVER_DELAY) };
    },
    true,
  );
  document.addEventListener(
    "pointerout",
    (event) => {
      if (!hover || hover.stub.contains(event.relatedTarget)) return;
      clearTimeout(hover.timer);
      hover = null;
    },
    true,
  );
  for (const type of ["focusin", "pointerdown"]) {
    document.addEventListener(
      type,
      (event) => {
        const stub = stubOf(event);
        if (stub) load(stub);
      },
      true,
    );
  }
  document.addEventListener(
    "click",
    (event) => {
      const stub = stubOf(event);
      if (!stub) return;
      // The stub's <details> must not open empty. The full widget gets the press.
      event.preventDefault();
      stub._formworkPress = event.target.closest("summary, input, button");
      load(stub);
    },
    true,
  );
  // A swap that brings a stub where the page shows the full widget, or the
  // full widget where the page shows a stub (a save renders a field with an
  // error in full), puts the new one in plainly first. A morph would keep the
  // full widget's Alpine bindings on the stub, or leave the full widget unbound.
  // The focus stays: a save sent with Enter from a loaded date picker leaves
  // it on the stub, which loads the full widget again.
  document.addEventListener("htmx:before:swap", (e) => {
    for (const task of e.detail.tasks ?? []) {
      for (const root of task.fragment?.querySelectorAll("[data-formwork-stub], [data-formwork-lazy]") ?? []) {
        const old = root.id && document.getElementById(root.id);
        if (!old || old.hasAttribute("data-formwork-stub") === root.hasAttribute("data-formwork-stub")) continue;
        const active = old.contains(document.activeElement) ? document.activeElement : null;
        const fresh = root.cloneNode(true);
        old.replaceWith(fresh);
        if (active) (twin(fresh, active) ?? fresh.querySelector('summary, input:not([type="hidden"])'))?.focus();
      }
    }
  });
}

// Numbers each htmx request when it has collected its values. A swap stamps
// the formwork roots it brings in with the number of the request they answer,
// so a widget can tell the answer to a request sent before its latest pick
// from the answer to one that carried the pick.
let requestSeq = 0;

if (typeof document !== "undefined") {
  document.addEventListener("htmx:config:request", (e) => {
    e.detail.ctx.formworkRequest = ++requestSeq;
  });
  document.addEventListener("htmx:before:swap", (e) => {
    for (const task of e.detail.tasks ?? []) {
      for (const root of task.fragment?.querySelectorAll('[x-data^="formwork"]') ?? []) {
        root._formworkRequest = e.detail.ctx?.formworkRequest;
      }
      // A widget that replaces a started one starts with it, so a morph that
      // clones Alpine state onto the new markup finds it bound. Without an id
      // the old widget is unknown, and the new one starts as before.
      for (const root of task.fragment?.querySelectorAll("[data-formwork-lazy]") ?? []) {
        if (!root.id || document.getElementById(root.id)?._formworkStarted) root._formworkStarted = true;
      }
    }
  });
}

const baseData = () => ({
  _v: 0,
  _pickedAfter: 0,
  search: "",
  showSearch: false,
  placeholder: "",
  // The option value of the row the arrow keys highlight, and that row's id.
  highlighted: null,
  highlightId: "",
  dropUp: false,
  hasError: false,
  _unfollow: null,

  // The panel's height cap, the height below which it flips up, and whether
  // it is at least as wide as its trigger. The calendar panels change them.
  panelMaxHeight: PANEL_MAX_HEIGHT,
  panelUsableHeight: PANEL_USABLE_HEIGHT,
  panelMatchesTrigger: true,

  // The <details> element owns the open state; the combobox is a plain <div>
  // and overrides this.
  get isOpen() {
    return this.$root.open === true;
  },

  // Set by the widget template when the list is filled by the search endpoint.
  get hasSearchUrl() {
    return this.$root.dataset.hasSearchUrl === "true";
  },

  // The text the list is filtered by and the search endpoint receives.
  get query() {
    return this.search;
  },

  close() {
    this.$root.open = false;
    this.hidePanel();
    this.clearHighlight();
  },

  notePick() {
    this._pickedAfter = requestSeq;
  },

  // Asked by the formwork morph before a morph touches this root. The answer
  // to a request older than the latest pick is a stale echo: it would revert
  // the pick, whose change event armed a newer request. The answer to a
  // request that carried the pick is the server's word, even when it holds
  // another value.
  acceptMorph(newNode) {
    return !(newNode._formworkRequest <= this._pickedAfter);
  },

  // Escape closes an open panel and goes no further, so a <dialog> around
  // the widget stays open. Cancelling the key also keeps the search box from
  // clearing itself, so the query is cleared here. Focus inside the closing
  // panel goes back to the trigger instead of to the page.
  onEscape(event) {
    if (!this.isOpen) return;
    event.preventDefault();
    event.stopPropagation();
    const refocus = this.$refs.panel?.contains(document.activeElement);
    if (this.search) this.clearSearch();
    this.close();
    if (refocus) this.$root.querySelector("summary")?.focus();
  },

  // Focus moving to another control closes the panel. Without a related
  // target (a click on the page, a switch to another window) it stays open:
  // the click listener above handles the click.
  onFocusOut(event) {
    if (outside(this.$root, event.relatedTarget)) this.close();
  },

  // A press on a part of the panel that takes no focus keeps focus where it
  // is, so the keys still reach the widget after a drag of the scrollbar.
  keepFocus(event) {
    if (!this.$root.contains(event.target.closest(FOCUSABLE))) event.preventDefault();
  },

  // Anchor names must be unique per instance, so they are inline styles
  // rather than a stylesheet rule.
  anchorPanel() {
    const root = this.$root;
    const panel = this.$refs.panel;
    if (!panel || !supportsPopover) return;
    const apply = () => {
      panel.setAttribute("popover", "manual");
      if (supportsAnchor) {
        if (!root.style.anchorName) root.style.anchorName = `--formwork-anchor-${++anchorSeq}`;
        panel.style.positionAnchor = root.style.anchorName;
      }
    };
    apply();
    // A morph syncs attributes back to the server HTML, which carries none
    // of the inline styles: the anchor name and the placement get stripped.
    // Re-assert them; the observer runs before the next paint, so an open
    // panel never renders unplaced.
    const observer = new MutationObserver(() => {
      const intact =
        panel.getAttribute("popover") === "manual" &&
        (!supportsAnchor || (root.style.anchorName && panel.style.positionAnchor)) &&
        (!this.isOpen || (panel.matches(":popover-open") && panel.style.maxHeight));
      if (intact) return;
      apply();
      this.reposition();
    });
    observer.observe(root, { attributeFilter: ["style"] });
    observer.observe(panel, { attributeFilter: ["style", "popover"] });
    // Deliberate teardowns (the screenshot harness flattens panels into normal
    // flow) must disconnect this first or the re-assert fights them.
    panel._formworkPopoverObserver = observer;
  },

  // The panel is a popover: the top layer escapes any clipping ancestor, such
  // as a modal body. Down is the default. Flip up only when the room below is
  // too cramped and above holds more, then cap the height so the panel stays
  // on screen.
  setDropDirection() {
    const panel = this.$refs.panel;
    if (!panel?.isConnected || !supportsPopover) return;
    if (!panel.matches(":popover-open")) {
      try {
        panel.showPopover();
      } catch {
        return;
      }
    }
    const rect = this.$root.getBoundingClientRect();
    // Width first: it decides how the options wrap, so the measured height.
    if (!supportsAnchor && this.panelMatchesTrigger) panel.style.minWidth = `${rect.width}px`;
    const reserved = PANEL_OFFSET + VIEWPORT_MARGIN;
    const below = window.innerHeight - rect.bottom - reserved;
    const above = rect.top - reserved;
    // A searched list arrives after the open.
    // scrollHeight is the padding box; max-height caps the border box.
    const measured = panel.scrollHeight + borderHeight(panel);
    const wanted = this.hasSearchUrl ? this.panelMaxHeight : Math.min(measured, this.panelMaxHeight);
    this.dropUp = below < Math.min(wanted, this.panelUsableHeight) && above > below;
    const room = this.dropUp ? above : below;
    panel.style.maxHeight = `${Math.max(Math.min(wanted, room), 0)}px`;
    if (supportsAnchor) {
      panel.style.positionArea = `${this.dropUp ? "block-start" : "block-end"} span-inline-end`;
      return;
    }
    const width = panel.offsetWidth;
    panel.style.left = `${Math.max(VIEWPORT_MARGIN, Math.min(rect.left, window.innerWidth - width - VIEWPORT_MARGIN))}px`;
    panel.style.top = this.dropUp ? "auto" : `${rect.bottom + PANEL_OFFSET}px`;
    panel.style.bottom = this.dropUp ? `${window.innerHeight - rect.top + PANEL_OFFSET}px` : "auto";
  },

  reposition() {
    if (this.isOpen) this.setDropDirection();
  },

  showPanel() {
    this.setDropDirection();
    if (supportsAnchor || this._unfollow) return;
    // Without anchor positioning the panel follows its trigger by hand, and
    // re-measures when a swap resizes it.
    const follow = () => this.reposition();
    const resize = new ResizeObserver(follow);
    resize.observe(this.$refs.panel);
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    this._unfollow = () => {
      resize.disconnect();
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
    };
  },

  hidePanel() {
    this._unfollow?.();
    this._unfollow = null;
    const panel = this.$refs.panel;
    if (panel?.matches(":popover-open")) panel.hidePopover();
  },

  // The toggle event runs after the browser can paint the open panel, so the
  // open attribute decides instead: a MutationObserver runs before that paint.
  // A disabled widget stays shut; a disabled <fieldset> reaches form controls
  // but not the <summary> trigger.
  watchOpen() {
    const el = this.$root;
    const sync = () => {
      if (!el.open) {
        this.hidePanel();
        return;
      }
      if (el.dataset.disabled === "true" || el.closest("fieldset:disabled")) {
        el.open = false;
        return;
      }
      this.showPanel();
    };
    new MutationObserver(sync).observe(el, { attributeFilter: ["open"] });
    // A widget that a script opened starts on the toggle event, after the change.
    if (el.open) sync();
  },

  onToggle() {
    if (!this.$el.open) {
      this.clearHighlight();
      return;
    }
    if (this.showSearch) setTimeout(() => this.$refs.search?.focus(), 0);
  },

  onNav(event, dir) {
    if (!this.isOpen) return;
    event.preventDefault();
    this.nav(dir);
  },

  onEnter(event) {
    if (!this.isOpen || event.target.closest("button")) return;
    event.preventDefault();
    this.confirm();
  },

  // Client-side filtering only: a swapped-in list brings its own empty row.
  // Reads the rows, not their layout, so it does not wait on their x-show.
  get noResults() {
    const query = this.query;
    if (this.hasSearchUrl || !query) return false;
    return ![...this.$refs.options.querySelectorAll("li[role=option]")].some((li) => matchesQuery(li, query));
  },

  clearSearch() {
    clearInput(this.$refs.search);
  },

  clearHighlight() {
    this.highlighted = null;
  },

  // Shows the rows that match the search and marks the selected and the
  // highlighted one, from one effect on the list. Bindings on each row cost
  // far more: a list of rows with a few dropdowns each sets up thousands of
  // them on load. Rows that a search, "Load more" or a morph brings in are
  // marked through the list's observer.
  syncRows() {
    // Read up front, so the effect follows them while the list is empty. The
    // server filters a searched list itself, on more fields than the label.
    const query = this.hasSearchUrl ? "" : this.query;
    const highlighted = this.highlighted;
    const highlightId = this.highlightId;
    this._v;
    const list = this.$refs.options;
    if (!list) return;
    const selectable = typeof this.isSelected === "function";
    for (const row of list.children) {
      const option = "label" in row.dataset;
      if (!option && !("group" in row.dataset)) continue;
      setShown(row, matchesQuery(row, query));
      if (!option) continue;
      const lit = highlighted !== null && row.querySelector("[data-value]")?.dataset.value === highlighted;
      if (selectable) setAttribute(row, "aria-selected", String(this.isSelected(row)));
      row.classList.toggle("highlighted", lit);
      if (lit && highlightId) {
        setAttribute(row, "id", highlightId);
        row._formworkOwnId = highlightId;
      } else if (row.id) row.removeAttribute("id");
    }
    if (!list._formworkRows) {
      list._formworkRows = new MutationObserver(() => this.syncRows());
      list._formworkRows.observe(list, { childList: true, subtree: true, attributeFilter: ROW_ATTRIBUTES });
    }
    // These writes need no second pass.
    list._formworkRows.takeRecords();
  },

  // The text box keeps focus while the arrows move the highlight, so it
  // points screen readers at the highlighted row by id.
  get activeOption() {
    return this.highlighted === null ? undefined : this.highlightId;
  },

  nav(dir) {
    const visible = visibleOptions(this);
    if (!visible.length) return;
    let idx = visible.findIndex((el) => el.dataset.value === this.highlighted);
    if (idx === -1) idx = dir > 0 ? 0 : visible.length - 1;
    else idx = (idx + dir + visible.length) % visible.length;
    // A new id for each step, so a screen reader announces the move.
    this.highlightId = `formwork-option-${++highlightIds}`;
    this.highlighted = visible[idx].dataset.value;
    visible[idx].closest("li").scrollIntoView({ block: "nearest" });
  },

  // The highlighted row's option, else the first visible one.
  confirmTarget() {
    const visible = visibleOptions(this);
    return visible.find((el) => el.dataset.value === this.highlighted) ?? visible[0];
  },

  // The rows a typed search brought in are the answer to that search; the
  // form's own render lists other rows, so a morph leaves them. It also
  // leaves an open list, whose first page the render does not hold.
  keepSearchedList() {
    const list = this.$refs.options;
    if (list) list._formworkAcceptMorph = () => !(this.hasSearchUrl && (this.query || this.isOpen));
  },

  // htmx 4 builds the GET query from the request body. The search box has no
  // name, so the form never posts it. The ComboBox input has the field name,
  // which could shadow a search param, so its text goes out as q only.
  onSearchConfig(event) {
    const body = event.detail.ctx.request.body;
    if (this.$root.dataset.name) body.delete(this.$root.dataset.name);
    body.set("q", this.query);
  },

  // Bound on the root, so it also covers "Load more". An error response must
  // not replace the list; a real one clears a previous error.
  onSearchBeforeSwap(event) {
    const status = event.detail.ctx?.response?.status;
    if (status >= 400) {
      event.preventDefault();
      return;
    }
    if (status) this.hasError = false;
  },

  onSearchError() {
    this.hasError = true;
  },
});

// Merges descriptors rather than values: object spread would *call* every getter
// above against a component that Alpine has not bound yet, so `this.$root` is
// still undefined and the read throws before the widget ever initializes.
export const dropdownBase = (component) =>
  Object.defineProperties(
    {},
    {
      ...Object.getOwnPropertyDescriptors(baseData()),
      ...Object.getOwnPropertyDescriptors(component),
    },
  );
