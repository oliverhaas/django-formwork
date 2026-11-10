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

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Django's admin quote(): a character that would break a key in a URL path becomes _XX.
const adminQuote = (value) =>
  value.replace(/[":/_#?;@&=+$,[\]<>%\n\\]/g, (char) => `_${char.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0")}`);

// The frame of the related-object dialog that shows this page, if one does.
const popupFrame = () => {
  const frame = window.frameElement;
  return frame?.closest("[data-popup-level]") ? frame : null;
};

// The window that shows the related-object dialogs: a page in a dialog opens the next one on top of its own.
const popupHost = () => {
  let host = window;
  while (host.frameElement?.closest("[data-popup-level]")) host = host.parent;
  return host;
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
        // Below lg the filter sits in the closed drawer, which hides it.
        if (drawer && !filter.checkVisibility({ visibilityProperty: true })) drawer.checked = true;
        // The drawer shows after a transition delay, and a hidden input takes no focus.
        const focus = (frames) => {
          filter.focus();
          if (document.activeElement !== filter && frames) requestAnimationFrame(() => focus(frames - 1));
        };
        requestAnimationFrame(() => focus(30));
      } else if (mod && key === "s") {
        const button = document.querySelector("[data-continue]") ?? document.querySelector("[data-save]");
        if (!button) return;
        event.preventDefault();
        button.form.requestSubmit(button);
      } else if (key === "escape" && !event.defaultPrevented) {
        // In a page in a dialog, Escape closes the dialog, as it does with the focus outside the page.
        const frame = popupFrame();
        if (frame) frame.dispatchEvent(new frame.ownerDocument.defaultView.Event("formwork-admin:dismiss", { bubbles: true }));
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
      // After a failed save, the first field with an error takes the focus, so its message shows.
      form.querySelector('[aria-invalid="true"]:not([type=hidden])')?.focus();

      // A widget sends its own change events, also while it starts. They count only
      // after the user has pressed a key or a pointer in the form.
      let used = false;
      let dirty = false;
      const use = (event) => {
        if (event.isTrusted) used = true;
      };
      const mark = (event) => {
        if (used || event.isTrusted) dirty = true;
      };
      form.addEventListener("pointerdown", use);
      form.addEventListener("keydown", use);
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

  // Password-based authentication "Disabled" turns the password fields off; each button with
  // data-usable-password is on only for its own choice. Both stay in place.
  Alpine.data("formworkUsablePassword", () => ({
    init() {
      this.apply();
      this.$root.addEventListener("change", (event) => {
        if (event.target.name === "usable_password") this.apply();
      });
    },

    apply() {
      const root = this.$root;
      const off = root.querySelector('[name="usable_password"][value="false"]')?.checked ?? false;
      for (const el of root.querySelectorAll('[data-field="password1"] input, [data-field="password2"] input')) {
        el.disabled = off;
      }
      for (const el of root.querySelectorAll("[data-usable-password]")) {
        el.disabled = (el.dataset.usablePassword === "false") !== off;
      }
    },
  }));

  // Shows the add or change page of a related object in a dialog, and hands the saved object to the
  // relation's field. Each dialog is a level; a relation in a dialog opens the next level on top.
  Alpine.data("formworkPopup", () => {
    const levels = [];
    return {
      open({ url, source, opener }) {
        const dialog = this.$refs.level.content.firstElementChild.cloneNode(true);
        const frame = dialog.querySelector("iframe");
        const level = { dialog, frame, source, opener, observer: null };
        levels.push(level);
        const label = opener?.getAttribute("aria-label");
        if (label) {
          dialog.setAttribute("aria-label", label);
          frame.title = label;
        }
        dialog.addEventListener("cancel", (event) => {
          event.preventDefault();
          this.dismiss(level);
        });
        // The browser closes a dialog itself after a second Escape without a click between.
        dialog.addEventListener("close", () => this.close(level));
        dialog.addEventListener("formwork-admin:dismiss", () => this.dismiss(level));
        dialog.querySelector("[data-dismiss]").addEventListener("click", () => this.dismiss(level));
        frame.addEventListener("load", () => this.loaded(level));
        // A frame with its address set before it is attached loads no blank page first.
        frame.src = url;
        this.$root.append(dialog);
        dialog.showModal();
      },

      // A page with unsaved changes asks first; the blank page then closes the dialog.
      dismiss(level) {
        level.frame.src = "about:blank";
      },

      loaded(level) {
        const { dialog, frame } = level;
        const doc = frame.contentDocument;
        if (!doc || doc.URL === "about:blank") return this.close(level);
        const response = doc.getElementById("formwork-admin-popup-response");
        if (response) {
          this.close(level);
          this.answer(level, JSON.parse(response.dataset.popupResponse));
          return;
        }
        const title = doc.querySelector("#content h1")?.textContent.trim() || doc.title;
        dialog.setAttribute("aria-label", title);
        frame.title = title;
        // The frame takes the height of its page, up to the height of the dialog.
        level.observer?.disconnect();
        level.observer = new frame.contentWindow.ResizeObserver(() => {
          frame.style.height = `${Math.ceil(doc.body.getBoundingClientRect().height)}px`;
        });
        level.observer.observe(doc.body);
        // While the next page loads, the spinner shows instead of a blank frame.
        frame.contentWindow.addEventListener("pagehide", () => this.busy(level, true));
        this.busy(level, false);
        // A page that focused a field with an error keeps that focus.
        if (doc.activeElement === doc.body) {
          const fields = doc.querySelectorAll("#content form :is(input:not([type=hidden]), textarea, select, summary)");
          [...fields].find((el) => !el.disabled && el.checkVisibility())?.focus();
        }
      },

      busy(level, on) {
        level.frame.classList.toggle("invisible", on);
        level.dialog.querySelector("[data-spinner]").hidden = !on;
      },

      close(level) {
        const index = levels.indexOf(level);
        if (index === -1) return;
        for (const closed of levels.splice(index).reverse()) {
          closed.observer?.disconnect();
          closed.dialog.close();
          closed.dialog.remove();
        }
        // Safari does not focus a clicked link, so the dialog has no focus to give back.
        level.opener?.focus();
      },

      // Every field of the same model on the page gets the saved object; the field that opened the dialog chooses it.
      answer({ source }, data) {
        const doc = source.ownerDocument;
        for (const field of doc.querySelectorAll(`[data-related="${CSS.escape(source.dataset.related)}"]`)) {
          const detail = { ...data, chosen: field === source };
          field.dispatchEvent(new doc.defaultView.CustomEvent("formwork-admin:related", { detail }));
        }
      },
    };
  });

  // A relation's dropdown with buttons that add a row or change the chosen one in a dialog.
  Alpine.data("formworkRelated", () => ({
    field() {
      return this.$root.querySelector(".formwork-select, .formwork-select-multiple");
    },

    // A click with a modifier key opens the full page, in a new tab or window.
    open(event) {
      const link = event.currentTarget;
      if (!link.href || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const url = new URL(link.href);
      for (const [key, value] of new URLSearchParams(this.$root.dataset.popupQuery)) url.searchParams.set(key, value);
      const host = popupHost();
      const detail = { url: url.href, source: this.$root, opener: link };
      host.dispatchEvent(new host.CustomEvent("formwork-admin:popup", { detail }));
    },

    // The change button follows the chosen row. Without one it stays in place, dimmed.
    syncLink() {
      const link = this.$root.querySelector('[data-related-popup="change"]');
      if (!link) return;
      const value = this.field()?.dataset.value ?? "";
      if (value) {
        link.href = this.$root.dataset.changeUrl.replace("__fk__", encodeURIComponent(adminQuote(value)));
        link.removeAttribute("aria-disabled");
      } else {
        link.removeAttribute("href");
        link.setAttribute("aria-disabled", "true");
      }
    },

    selected(field) {
      return JSON.parse(field.dataset.selected || "[]");
    },

    // The widget reads its selection back from this attribute.
    select(field, entries) {
      field.dataset.selected = JSON.stringify(entries);
    },

    // The answer of the dialog: a row of the related model added, changed or deleted. Each field
    // updates its selection; the field that opened the dialog then has the server re-render the
    // form, so every relation lists the rows as they are now.
    apply({ action, value, obj, new_value: newValue, chosen }) {
      const field = this.field();
      if (!field) return;
      const multiple = field.classList.contains("formwork-select-multiple");
      if (action === "delete") {
        if (multiple) this.select(field, this.selected(field).filter(([key]) => key !== value));
        else if (field.dataset.value === value) {
          Object.assign(field.dataset, { value: "", label: "", icon: "", labelHtml: "", selectedToggleClass: "" });
        }
      } else if (action === "change") {
        if (multiple) {
          const entries = this.selected(field).map(([key, html]) => (key === value ? [newValue, escapeHtml(obj)] : [key, html]));
          this.select(field, entries);
        } else if (field.dataset.value === value) Object.assign(field.dataset, { value: newValue, label: obj, labelHtml: "" });
      } else if (chosen && multiple) {
        this.select(field, [...this.selected(field).filter(([key]) => key !== value), [value, escapeHtml(obj)]]);
      } else if (chosen) {
        Alpine.$data(field).choose({ value, label: obj, icon: "", labelHtml: "", selectedToggleClass: "" });
      }
      this.syncLink();
      if (!chosen) return;
      this.$nextTick(() => {
        // A list of boxes has none for the new row until the refresh lists it, so a hidden input
        // posts the row, also when the form is saved first.
        const name = field.dataset.name;
        const posted = [...this.$root.querySelectorAll("input")].some(
          (input) => input.name === name && input.value === value && (input.type === "hidden" || input.checked),
        );
        if (!action && !posted) this.$root.append(Object.assign(document.createElement("input"), { type: "hidden", name, value }));
        this.$dispatch("formwork-admin:refresh");
      });
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

// A refresh of the change form leaves files out.
document.addEventListener("htmx:config:request", (event) => {
  const { ctx } = event.detail;
  if (ctx.sourceEvent?.type !== "formwork-admin:refresh" || !(ctx.request.body instanceof FormData)) return;
  const body = ctx.request.body;
  for (const [key, value] of [...body]) {
    if (value instanceof File) body.delete(key);
  }
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
