/**
 * admin.js: the Alpine components of django_formwork.admin.
 *
 * Load it as a module before Alpine (which loads with `defer`), so the
 * `alpine:init` listener exists when Alpine starts.
 */

const THEME_KEY = "formwork-admin-theme";
const TOAST_DELAY = 6000;
const SEARCH_DELAY = 300;

const isTyping = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// The same steps as Django's URLify: strip accents, drop punctuation, join words with hyphens.
const slugify = (text, maxLength) =>
  text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^-\w\s]/g, "")
    .trim()
    .replace(/[-\s]+/g, "-")
    .slice(0, maxLength)
    .replace(/-+$/, "");

// A form control by name; a widget with several inputs of one name returns its visible one.
const control = (form, name) => {
  const item = form.elements.namedItem(name);
  if (item instanceof RadioNodeList) return [...item].find((el) => el.type !== "hidden") ?? item[0];
  return item;
};

document.addEventListener("alpine:init", () => {
  const Alpine = window.Alpine;

  Alpine.data("formworkAdmin", () => ({
    theme: "",

    init() {
      try {
        this.theme = localStorage.getItem(THEME_KEY) || "";
      } catch {
        this.theme = "";
      }
    },

    setTheme(theme) {
      this.theme = theme;
      if (theme) document.documentElement.dataset.theme = theme;
      else delete document.documentElement.dataset.theme;
      try {
        if (theme) localStorage.setItem(THEME_KEY, theme);
        else localStorage.removeItem(THEME_KEY);
      } catch {
        // Private windows can refuse storage; the theme then lasts for this page only.
      }
    },

    shortcut(event) {
      const key = event.key.toLowerCase();
      const mod = event.ctrlKey || event.metaKey;
      if (mod && key === "k") {
        const filter = document.getElementById("formwork-admin-nav-filter");
        if (!filter) return;
        event.preventDefault();
        const drawer = document.getElementById("formwork-admin-nav");
        if (drawer && !filter.offsetParent) drawer.checked = true;
        requestAnimationFrame(() => filter.focus());
      } else if (mod && key === "s") {
        const button = document.querySelector("[data-continue]") ?? document.querySelector("[data-save]");
        if (!button) return;
        event.preventDefault();
        button.form.requestSubmit(button);
      } else if (key === "/" && !mod && !isTyping(event.target)) {
        const search = document.querySelector("[data-search] input:not([type=hidden])");
        if (!search) return;
        event.preventDefault();
        search.focus();
        search.select();
      }
    },
  }));

  Alpine.data("formworkNav", () => ({
    query: "",

    matches(el) {
      const query = this.query.trim().toLowerCase();
      return !query || el.dataset.name.includes(query);
    },

    appMatches(el) {
      return !this.query.trim() || [...el.querySelectorAll("[data-name]")].some((item) => this.matches(item));
    },

    anyMatch() {
      return [...this.$root.querySelectorAll("[data-name]")].some((item) => this.matches(item));
    },

    open() {
      const item = [...this.$root.querySelectorAll("[data-name]")].find((el) => this.matches(el));
      item?.querySelector("a")?.click();
    },
  }));

  Alpine.data("formworkToast", () => ({
    open: true,
    timer: null,

    init() {
      this.resume();
    },

    pause() {
      clearTimeout(this.timer);
    },

    resume() {
      if (!this.$root.dataset.sticky) this.timer = setTimeout(() => this.close(), TOAST_DELAY);
    },

    close() {
      this.open = false;
    },
  }));

  // Submits the changelist filters as the user types or picks, once per distinct query.
  Alpine.data("formworkFilters", () => ({
    timer: null,
    last: "",
    // The filter row starts open while a filter is active.
    open: false,

    init() {
      this.open = this.$root.dataset.open === "1";
      this.last = this.query();
      // "Clear all filters" morphs the fields empty without an input event, so the next change always counts.
      this.cleared = (event) => {
        if (event.target.closest("[data-clear-filters]")) this.last = null;
      };
      document.addEventListener("click", this.cleared);
    },

    destroy() {
      document.removeEventListener("click", this.cleared);
    },

    toggle() {
      this.open = !this.open;
    },

    query() {
      const params = new URLSearchParams();
      for (const [key, value] of new FormData(this.$root)) {
        if (key !== "o" && value !== "") params.append(key, value);
      }
      return params.toString();
    },

    typed() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.submit(), SEARCH_DELAY);
    },

    changed() {
      clearTimeout(this.timer);
      this.submit();
    },

    submit() {
      const query = this.query();
      if (query === this.last) return;
      this.last = query;
      this.$root.requestSubmit();
    },
  }));

  Alpine.data("formworkChangelist", () => ({
    selected: [],
    across: false,
    last: null,
    pks: [],
    total: 0,

    // Each render of the results starts a new selection, including one that a swap brings in.
    reset(list) {
      this.selected = [];
      this.across = false;
      this.last = null;
      this.total = Number(list.dataset.total);
      this.$nextTick(() => {
        this.pks = [...list.querySelectorAll("input[data-index]")].map((box) => box.value);
      });
    },

    get count() {
      return this.across ? this.total : this.selected.length;
    },

    get allChecked() {
      return this.pks.length > 0 && this.selected.length === this.pks.length;
    },

    get someChecked() {
      return this.selected.length > 0 && !this.allChecked;
    },

    toggleAll(checked) {
      this.selected = checked ? [...this.pks] : [];
      this.across = false;
    },

    // Shift-click checks or unchecks every row between the last click and this one.
    range(event) {
      const index = Number(event.target.dataset.index);
      const checked = event.target.checked;
      if (event.shiftKey && this.last !== null && this.last !== index) {
        const [start, end] = this.last < index ? [this.last, index] : [index, this.last];
        const span = new Set(this.pks.slice(start, end + 1));
        this.$nextTick(() => {
          const rest = this.selected.filter((pk) => !span.has(pk));
          this.selected = checked ? [...rest, ...span] : rest;
        });
      }
      this.last = index;
      this.across = false;
    },

    clear() {
      this.selected = [];
      this.across = false;
      this.last = null;
    },
  }));

  Alpine.data("formworkChangeForm", () => ({
    init() {
      const form = this.$root;
      const adding = Boolean(form.dataset.add);
      for (const { field, dependencies } of JSON.parse(form.dataset.prepopulated || "[]")) {
        this.prepopulate(form, field, dependencies, adding);
      }

      let dirty = false;
      const mark = (event) => {
        if (event.isTrusted) dirty = true;
      };
      form.addEventListener("input", mark);
      form.addEventListener("change", mark);
      form.addEventListener("submit", () => {
        dirty = false;
      });
      window.addEventListener("beforeunload", (event) => {
        if (dirty) event.preventDefault();
      });
    },

    // Fills a slug from its source fields until the user edits it; a saved slug stays as it is.
    prepopulate(form, field, dependencies, adding) {
      const target = control(form, field);
      const sources = dependencies.map((name) => control(form, name)).filter(Boolean);
      if (!target || !sources.length) return;
      let edited = !adding && target.value !== "";
      const maxLength = Number(target.getAttribute("maxlength")) || 50;
      target.addEventListener("input", () => {
        edited = target.value !== "";
      });
      const fill = () => {
        if (edited) return;
        const text = sources
          .map((el) => (el.tagName === "SELECT" ? el.selectedOptions[0]?.text ?? "" : el.value))
          .filter(Boolean)
          .join(" ");
        target.value = slugify(text, maxLength);
      };
      for (const source of sources) {
        source.addEventListener("input", fill);
        source.addEventListener("change", fill);
      }
    },
  }));

  // Adds and removes inline rows and keeps the formset's indexes and TOTAL_FORMS contiguous.
  Alpine.data("formworkInline", () => ({
    prefix: "",
    total: 0,
    min: 0,
    max: 1000,

    init() {
      this.prefix = this.$root.dataset.prefix;
      this.min = Number(this.$root.dataset.min) || 0;
      this.max = Number(this.$root.dataset.max) || 1000;
      this.total = Number(this.totalInput().value);
    },

    get canAdd() {
      return this.total < this.max;
    },

    get canRemove() {
      return this.total > this.min;
    },

    totalInput() {
      return this.$root.querySelector(`input[name="${CSS.escape(this.prefix)}-TOTAL_FORMS"]`);
    },

    setTotal(total) {
      this.total = total;
      this.totalInput().value = String(total);
    },

    add() {
      if (!this.canAdd) return;
      const html = this.$refs.empty.innerHTML.replaceAll("__prefix__", String(this.total));
      this.$refs.rows.insertAdjacentHTML("beforeend", html);
      const row = this.$refs.rows.lastElementChild;
      this.setTotal(this.total + 1);
      row.dispatchEvent(new CustomEvent("formset:added", { bubbles: true, detail: { formsetName: this.prefix } }));
      this.$nextTick(() => row.querySelector("input:not([type=hidden]), select, textarea")?.focus());
    },

    // $refs and $root resolve from the clicked button, so the row leaves the document last.
    remove(button) {
      const row = button.closest("[data-inline-row]");
      const root = this.$root;
      this.renumber(row);
      row.remove();
      root.dispatchEvent(new CustomEvent("formset:removed", { bubbles: true, detail: { formsetName: this.prefix } }));
    },

    renumber(removed) {
      const rows = [...this.$refs.rows.querySelectorAll(":scope > [data-inline-row]")].filter((row) => row !== removed);
      const prefix = escapeRegExp(this.prefix);
      rows.forEach((row, index) => {
        const current = row.id.match(new RegExp(`^${prefix}-(\\d+)$`))?.[1];
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

// Leaves empty filters out of the changelist URL.
document.addEventListener("htmx:config:request", (event) => {
  const { ctx } = event.detail;
  if (ctx.sourceElement?.id !== "changelist-filters" || !(ctx.request.body instanceof FormData)) return;
  const body = new FormData();
  for (const [key, value] of ctx.request.body) {
    if (value !== "") body.append(key, value);
  }
  ctx.request.body = body;
});
