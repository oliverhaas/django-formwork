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

// Close any open <details> dropdown when a real click lands outside it, so a
// click anywhere else on the page (including another dropdown's trigger)
// dismisses it. Native <details> has no such behaviour, and light dismiss is
// off. One shared listener rather than a per-widget @click.outside: this
// module loads once (ES-module dedup), and setting `open = false` lets each
// widget's open observer hide its panel. A genuine click only, never a
// morph, so it cannot close a panel behind the widget's back.
if (typeof document !== "undefined") {
  document.addEventListener("click", (e) => {
    for (const details of document.querySelectorAll("details.dropdown[open]")) {
      if (!details.contains(e.target)) details.open = false;
    }
  });
}

const baseData = () => ({
  _v: 0,
  _dirty: false,
  search: "",
  showSearch: false,
  placeholder: "",
  highlightedEl: null,
  dropUp: false,
  hasError: false,
  _unfollow: null,

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
    if (!supportsAnchor) panel.style.minWidth = `${rect.width}px`;
    const reserved = PANEL_OFFSET + VIEWPORT_MARGIN;
    const below = window.innerHeight - rect.bottom - reserved;
    const above = rect.top - reserved;
    // A searched list arrives after the open.
    // scrollHeight is the padding box; max-height caps the border box.
    const measured = panel.scrollHeight + borderHeight(panel);
    const wanted = this.hasSearchUrl ? PANEL_MAX_HEIGHT : Math.min(measured, PANEL_MAX_HEIGHT);
    this.dropUp = below < Math.min(wanted, PANEL_USABLE_HEIGHT) && above > below;
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
    new MutationObserver(() => {
      if (!el.open) {
        this.hidePanel();
        return;
      }
      if (el.dataset.disabled === "true" || el.closest("fieldset:disabled")) {
        el.open = false;
        return;
      }
      this.showPanel();
    }).observe(el, { attributeFilter: ["open"] });
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

  // The server filters a searched list itself, on more fields than the label.
  matches(el) {
    return matchesQuery(el, this.hasSearchUrl ? "" : this.query);
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
    if (this.highlightedEl) {
      this.highlightedEl.classList.remove("highlighted");
      this.highlightedEl = null;
    }
  },

  nav(dir) {
    const visible = visibleOptions(this);
    if (!visible.length) return;
    let idx = visible.findIndex((el) => el.closest("li") === this.highlightedEl);
    if (idx === -1) idx = dir > 0 ? 0 : visible.length - 1;
    else idx = (idx + dir + visible.length) % visible.length;
    this.clearHighlight();
    this.highlightedEl = visible[idx].closest("li");
    this.highlightedEl.classList.add("highlighted");
    this.highlightedEl.scrollIntoView({ block: "nearest" });
  },

  // The highlighted row's option, else the first visible one.
  confirmTarget() {
    const target = this.highlightedEl?.querySelector("[data-value]");
    return target && target.offsetParent !== null ? target : visibleOptions(this)[0];
  },

  // htmx 4 builds the GET query from the request body. The search box has no
  // name, so the form never posts it.
  onSearchConfig(event) {
    event.detail.ctx.request.body.set("q", this.query);
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
