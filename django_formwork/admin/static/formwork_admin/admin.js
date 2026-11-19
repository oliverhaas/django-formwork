/**
 * admin.js: the Alpine components of django_formwork.admin.
 *
 * Load it as a module before Alpine (which loads with `defer`), so the
 * `alpine:init` listener exists when Alpine starts.
 */

const THEME_KEY = "formwork-admin-theme";
const TOAST_DELAY = 6000;
const SEARCH_DELAY = 300;
// How long the pointer rests on a page link before the page loads, and how long a page link waits
// for its page before it shows the page's skeleton.
const INTENT_DELAY = 100;
const SKELETON_DELAY = 100;

const isTyping = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

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

// Fills a slug from its source fields until the user edits it; a saved slug stays as it is.
const prepopulate = (form, field, dependencies, adding) => {
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
};

// The first control in an element that takes the focus.
const focusable = (el) =>
  [...el.querySelectorAll("input:not([type=hidden]), select, textarea, summary, button, [tabindex]")].find(
    (item) => !item.disabled && item.tabIndex >= 0 && item.checkVisibility({ visibilityProperty: true }),
  );

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

// True after a page link gave up its morph and loads the page as a whole. The user has answered
// the page's own question by then, so the browser's leave prompt stays quiet.
let leaving = false;

// The files a page's head loads, each by its URL, or by its text for inline code.
const headFiles = (head) =>
  new Set([...head.querySelectorAll("script, link[rel~=stylesheet], style")].map((el) => el.src || el.href || el.textContent));

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
        // The server remembers the way a form was saved, but not from the shortcut. The form data is
        // read during requestSubmit, so the input goes again right after.
        const shortcut = Object.assign(document.createElement("input"), { type: "hidden", name: "_shortcut", value: "1" });
        button.form.append(shortcut);
        button.form.requestSubmit(button);
        shortcut.remove();
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

    // A page link keeps the sidebar; the next page starts with every model listed and its own in view.
    init() {
      this.page = () => {
        this.query = "";
        this.$nextTick(() => this.$root.querySelector("[aria-current=page]")?.scrollIntoView({ block: "nearest" }));
      };
      document.addEventListener("formwork-admin:page", this.page);
    },

    destroy() {
      document.removeEventListener("formwork-admin:page", this.page);
    },

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

    init() {
      this.last = this.query();
      // "Clear all filters" and "Clear search" morph the fields empty without an input event, so the next
      // change always counts.
      this.cleared = (event) => {
        if (event.target.closest("[data-clear-filters], [data-clear-search]")) this.last = null;
      };
      document.addEventListener("click", this.cleared);
    },

    destroy() {
      document.removeEventListener("click", this.cleared);
    },

    query() {
      const params = new URLSearchParams();
      for (const [key, value] of new FormData(this.$root)) {
        if (key !== "o" && key !== "per_page" && value !== "") params.append(key, value);
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
    // The editable cells whose value differs from the saved one; formwork counts them.
    changes: 0,

    init() {
      // After a failed save, the first cell with an error takes the focus, so its message shows.
      const focusError = () => {
        const invalid = this.$root.querySelector("#changelist-form td[data-invalid]");
        if (invalid) focusable(invalid)?.focus();
      };
      focusError();
      this.$root.addEventListener("htmx:after:swap", (event) => {
        if (event.target.id === "changelist-form") focusError();
      });
      // formwork may have counted before Alpine started.
      this.changes = this.$root.querySelectorAll("#changelist-form .formwork-dirty").length;
      this.$root.addEventListener("formwork:dirty", (event) => {
        this.changes = event.detail.count;
      });

      // Other results replace the changed cells, and so does another page: both ask first.
      // The save and the Discard button replace them on purpose.
      this.leave = (event) => {
        if (this.changes && !leaving) event.preventDefault();
      };
      this.guard = (event) => {
        const { ctx } = event.detail;
        const form = this.$root.querySelector("#changelist-form");
        if (!this.changes || !form || !(ctx.target instanceof Element) || !ctx.target.contains(form)) return;
        if (ctx.sourceElement?.id === "changelist-form" || ctx.sourceElement?.closest?.("[data-discard]")) return;
        if (!window.confirm(this.$root.dataset.discardQuestion)) event.preventDefault();
      };
      window.addEventListener("beforeunload", this.leave);
      document.addEventListener("htmx:before:request", this.guard);
    },

    destroy() {
      window.removeEventListener("beforeunload", this.leave);
      document.removeEventListener("htmx:before:request", this.guard);
    },

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
    // True while the form has changes. The page then asks before it leaves, the actions menu waits,
    // and the save bar stays in view.
    dirty: false,
    // The number of fields that differ from the saved object, on a change form.
    changes: 0,

    init() {
      const form = this.$root;
      const adding = Boolean(form.dataset.add);
      for (const { field, dependencies } of JSON.parse(form.dataset.prepopulated || "[]")) {
        prepopulate(form, field, dependencies, adding);
      }
      // After a failed save, the first field with an error takes the focus, so its message shows.
      form.querySelector('[aria-invalid="true"]:not([type=hidden])')?.focus();

      if (form.hasAttribute("data-formwork-dirty")) {
        // formwork compares each field with the saved object, so a change put back no longer counts.
        const count = () => {
          this.changes = form.querySelectorAll(".formwork-dirty").length;
          this.dirty = this.changes > 0;
        };
        count();
        form.addEventListener("formwork:dirty", count);
        // A removed new inline row takes its changes along without a change event.
        form.addEventListener("formset:removed", count);
      } else {
        // A new object has nothing saved to compare with. A widget sends its own change events,
        // also while it starts, so they count only after the user has pressed a key or a pointer.
        let used = false;
        const use = (event) => {
          if (event.isTrusted) used = true;
        };
        const mark = (event) => {
          if (used || event.isTrusted) this.dirty = true;
        };
        form.addEventListener("pointerdown", use);
        form.addEventListener("keydown", use);
        form.addEventListener("input", mark);
        form.addEventListener("change", mark);
      }
      form.addEventListener("submit", () => {
        this.dirty = false;
      });
      this.leave = (event) => {
        if (this.dirty && !leaving) event.preventDefault();
      };
      // A page link replaces the form without leaving the page, so it asks here. The form's own
      // requests keep it, except another page of an inline's rows, which replaces the rows on screen.
      this.guard = (event) => {
        const { ctx } = event.detail;
        if (!this.dirty || !(ctx.target instanceof Element)) return;
        if (ctx.sourceElement?.closest?.("[data-inline-pages]")) {
          if (!ctx.target.querySelector(".formwork-dirty")) return;
        } else if (!ctx.target.contains(form) || form.contains(ctx.sourceElement)) return;
        if (!window.confirm(form.dataset.leaveQuestion)) event.preventDefault();
      };
      window.addEventListener("beforeunload", this.leave);
      document.addEventListener("htmx:before:request", this.guard);
    },

    destroy() {
      window.removeEventListener("beforeunload", this.leave);
      document.removeEventListener("htmx:before:request", this.guard);
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
        // A row of the related list answers as a saved object does; a click with a modifier key
        // opens the row's page in a new tab or window.
        doc.addEventListener("click", (event) => {
          const link = event.target.closest("a[data-popup-pick]");
          if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          this.close(level);
          this.answer(level, JSON.parse(link.dataset.popupPick));
        });
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
    open(event, link = event.currentTarget) {
      if (!link.href || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const url = new URL(link.href);
      for (const [key, value] of new URLSearchParams(this.$root.dataset.popupQuery)) url.searchParams.set(key, value);
      const host = popupHost();
      const detail = { url: url.href, source: this.$root, opener: link };
      host.dispatchEvent(new host.CustomEvent("formwork-admin:popup", { detail }));
    },

    // The inputs and native selects that post the field.
    controls() {
      return [...this.$root.querySelectorAll("input, select")].filter((el) => el.name === this.$root.dataset.name);
    },

    // The chosen row: the dropdown's value, or the value that the field posts last, as the
    // server reads it.
    value() {
      const field = this.field();
      if (field) return field.dataset.value ?? "";
      return this.controls().filter((el) => el.type !== "radio" || el.checked).at(-1)?.value ?? "";
    },

    // The Edit link follows the chosen row. Without one it stays in place, dimmed. It sits in the
    // field's label row, or next to the widget in a table cell.
    syncLink() {
      const link = this.$root.closest("td, fieldset")?.querySelector('.formwork-label-links [data-related-popup="change"]');
      if (!link) return;
      const value = this.value();
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
      // A dropdown that nobody has opened yet starts now, so it follows the writes below.
      field?.dispatchEvent(new Event("formwork:start"));
      const multiple = field?.classList.contains("formwork-select-multiple");
      if (!field) this.applyToControls({ action, value, newValue, chosen });
      else if (action === "delete") {
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
        // A list has no option for the new row until the refresh lists it, so a hidden input
        // posts the row, also when the form is saved first.
        const posted = this.controls().some((el) => el.value === value && (el.type === "hidden" || el.checked));
        if (!action && !posted) {
          const input = Object.assign(document.createElement("input"), { type: "hidden", name: this.$root.dataset.name, value });
          this.$root.append(input);
          this.syncLink();
        }
        this.$dispatch("formwork-admin:refresh");
      });
    },

    // Radio buttons, checkboxes or a native select. The refresh lists the rows with their new
    // names, so only the choice changes here.
    applyToControls({ action, value, newValue, chosen }) {
      for (const el of this.$root.querySelectorAll("input, option")) {
        if ((el.closest("select") ?? el).name !== this.$root.dataset.name) continue;
        if (el.value === value && action === "delete") el[el.tagName === "OPTION" ? "selected" : "checked"] = false;
        else if (el.value === value && action === "change") el.value = newValue;
        else if (chosen && !action && el.type === "radio") el.checked = false;
      }
    },
  }));

  // The prepopulated fields of an inline's rows fill from the row's own fields; formwork's formset
  // table adds and renumbers the rows, and a renumbering keeps the listeners.
  Alpine.data("formworkInline", () => ({
    init() {
      const fields = JSON.parse(this.$root.dataset.prepopulated);
      const fill = (row) => {
        const form = row.closest("form");
        const prefix = row.dataset.formsetRow;
        for (const { field, dependencies } of fields) {
          const names = dependencies.map((name) => `${prefix}-${name}`);
          prepopulate(form, `${prefix}-${field}`, names, row.hasAttribute("data-formset-new"));
        }
      };
      for (const row of this.$root.querySelectorAll("[data-formset-row]")) fill(row);
      this.$root.addEventListener("formset:added", (event) => fill(event.target));
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

// A lazy slot (macros.html slot) is busy while it loads.
for (const [name, busy] of [["htmx:before:request", true], ["htmx:finally:request", false]]) {
  document.addEventListener(name, (event) => {
    if (!event.target.matches?.("[data-slot]")) return;
    if (busy) event.target.setAttribute("aria-busy", "true");
    else event.target.removeAttribute("aria-busy");
  });
}

// A list save that worked comes back through a redirect. The slots that show content load it again for the
// saved values and keep it meanwhile; one that still waits for its first load needs nothing.
document.addEventListener("htmx:after:swap", (event) => {
  const { ctx } = event.detail;
  if (ctx.sourceElement?.id !== "changelist-form" || !ctx.response?.raw?.redirected) return;
  for (const slot of document.querySelectorAll("#content [data-slot][hx-get]")) {
    if (!slot.hidden && !slot.querySelector(":scope > [data-slot-skeleton]")) {
      slot.dispatchEvent(new CustomEvent("formwork-admin:reload"));
    }
  }
});

// The button over a list hides its top slot and shows it again; its form tells the server, which keeps
// the choice. A slot that was closed when the page came loads when it first shows.
document.addEventListener("click", (event) => {
  const button = event.target.closest?.("[data-slot-toggle] button");
  const slot = button && document.getElementById(button.getAttribute("aria-controls"));
  if (!slot) return;
  const open = button.getAttribute("aria-expanded") !== "true";
  button.setAttribute("aria-expanded", String(open));
  button.title = open ? button.dataset.hide : button.dataset.show;
  button.setAttribute("aria-label", button.title);
  button.form.elements.closed.value = open ? "" : "1";
  slot.hidden = !open;
  if (open && slot.hasAttribute("data-slot-closed")) {
    slot.removeAttribute("data-slot-closed");
    slot.dispatchEvent(new CustomEvent("formwork-admin:open"));
  }
});

// A page link (data-page-link) morphs the page into the next one, so the sidebar keeps its place.
document.addEventListener("htmx:config:request", (event) => {
  const { ctx } = event.detail;
  const link = ctx.sourceElement?.closest?.("[data-page-link]");
  if (!link) return;
  ctx.formworkLink = link;
  // The page crossfades into the next one, unless the user asked for less motion.
  ctx.transition = Boolean(document.startViewTransition) && matchMedia("(prefers-reduced-motion: no-preference)").matches;
});

// A page link loads its page early (hx-preload) when the pointer rests on it, so a pointer that
// crosses the sidebar loads nothing.
let intent;
// The Edit and Add links of a relation sit outside its component, in the label row.
document.addEventListener("click", (event) => {
  const link = event.target.closest?.(".formwork-label-links [data-related-popup]");
  const related = link?.closest("td, fieldset")?.querySelector("[data-related]");
  if (related) Alpine.$data(related).open(event, link);
});

document.addEventListener("mouseover", (event) => {
  const link = event.target.closest?.("[data-page-link]");
  if (!link || link.contains(event.relatedTarget)) return;
  clearTimeout(intent);
  intent = setTimeout(() => link.dispatchEvent(new CustomEvent("formwork-admin:intent")), INTENT_DELAY);
});
document.addEventListener("mouseout", (event) => {
  const link = event.target.closest?.("[data-page-link]");
  if (link && !link.contains(event.relatedTarget)) clearTimeout(intent);
});

// The sidebar link of a path's model: the longest link path that starts it, as the server marks it.
const modelLink = (path) => {
  let found = null;
  for (const link of document.querySelectorAll("[data-nav-app] [data-page-link=list]")) {
    const start = new URL(link.href).pathname;
    if (path.startsWith(start) && start.length > (found ? new URL(found.href).pathname.length : 0)) found = link;
  }
  return found;
};

// Puts the skeleton of the link's page (skeletons.html) in the content, with the link's title and
// the model's icon, until the page arrives.
const showSkeleton = (link) => {
  const content = document.getElementById("content");
  const template =
    document.getElementById(`formwork-admin-skeleton-${link.dataset.pageLink}`) ?? document.getElementById("formwork-admin-skeleton-page");
  if (!content || !template) return;
  const skeleton = template.content.cloneNode(true);
  const heading = skeleton.querySelector("[data-skeleton-title]");
  const title = link.dataset.pageTitle ?? link.textContent.trim();
  if (heading && title) heading.textContent = title;
  const tile = skeleton.querySelector("[data-skeleton-icon]");
  const icon = modelLink(new URL(link.href).pathname)?.querySelector(".icon");
  if (tile && icon) {
    tile.append(icon.cloneNode(true));
    tile.hidden = false;
    skeleton.querySelector("[data-skeleton-tile]")?.remove();
  }
  content.replaceChildren(skeleton);
  content.setAttribute("aria-busy", "true");
  window.scrollTo({ top: 0, behavior: "instant" });
};

// A page that takes a moment shows its skeleton; a faster or preloaded one replaces the content
// directly. The sidebar marks the next page's model at once.
document.addEventListener("htmx:before:request", (event) => {
  const { ctx } = event.detail;
  const link = ctx.formworkLink;
  if (!link) return;
  // The page is on its way, so a pointer that still rests on the link loads nothing more.
  clearTimeout(intent);
  // A form with changes can still keep the page (its guard runs after this listener).
  queueMicrotask(() => {
    if (event.defaultPrevented) return;
    // The drawer of a narrow window closes on the way, so the skeleton shows; after the swap, the
    // focus leaves the drawer.
    const drawer = document.getElementById("formwork-admin-nav");
    if (drawer?.checked) {
      drawer.checked = false;
      ctx.formworkDrawn = true;
    }
    const current = modelLink(new URL(link.href).pathname);
    for (const item of document.querySelectorAll("[data-nav-app] [aria-current=page]")) {
      if (item !== current) item.removeAttribute("aria-current");
    }
    current?.setAttribute("aria-current", "page");
    const showing = document.getElementById("content")?.getAttribute("aria-busy") === "true";
    ctx.formworkSkeleton = setTimeout(() => showSkeleton(link), showing ? 0 : SKELETON_DELAY);
  });
});
for (const name of ["htmx:after:request", "htmx:finally:request"]) {
  document.addEventListener(name, (event) => clearTimeout(event.detail.ctx.formworkSkeleton));
}

// An error page, or a page that needs files this page has not loaded, loads as a whole.
document.addEventListener("htmx:after:request", (event) => {
  const { ctx } = event.detail;
  if (!ctx.formworkLink) return;
  const head = ctx.text.match(/<head[\s>][\s\S]*?<\/head>/i)?.[0] ?? "";
  const files = headFiles(new DOMParser().parseFromString(head, "text/html").head);
  const loaded = headFiles(document.head);
  // formwork.js imports every widget's module, so a widget's own script tag adds nothing the page lacks.
  for (const entry of performance.getEntriesByType("resource")) {
    if (entry.initiatorType === "script" || entry.initiatorType === "link") loaded.add(entry.name);
  }
  if (ctx.response.status < 400 && [...files].every((file) => loaded.has(file))) return;
  event.preventDefault();
  leaving = true;
  location.assign(ctx.response.raw.url);
});

// A page link that gets no answer leaves it to the browser to show why.
document.addEventListener("htmx:error", (event) => {
  const { ctx } = event.detail;
  if (!ctx.formworkLink) return;
  leaving = true;
  location.assign(ctx.formworkLink.href);
});

// A morph keeps the Alpine state of each element it matches. The sidebar and the top bar morph;
// the next page's content and messages replace the old ones, as a page load would.
document.addEventListener("htmx:before:swap", (event) => {
  const { ctx, tasks } = event.detail;
  const main = ctx.formworkLink && tasks.find((task) => task.type === "main");
  if (!main) return;
  for (const id of ["content", "formwork-admin-toasts"]) {
    const incoming = main.fragment.querySelector(`#${id}`);
    const current = document.getElementById(id);
    if (!incoming || !current) continue;
    const fragment = document.createDocumentFragment();
    fragment.append(...incoming.childNodes);
    tasks.push({ type: "partial", fragment, target: current, swapSpec: "innerHTML", sourceElement: ctx.sourceElement });
  }
});

// Another page of an inline's rows (macros.html inline_pager) morphs the group's content. The
// pager keeps its place on the screen, also next to the shorter last page. The fields take their
// own baseline for the count of changes, and the focus stays in the pager: on the link with the
// same id, or else on the current page.
document.addEventListener("htmx:before:request", (event) => {
  const { ctx } = event.detail;
  if (ctx.sourceElement?.closest?.("[data-inline-pages]")) ctx.formworkInlinePage = true;
});

const inlinePagerTop = (group) => group.querySelector("[data-inline-pages]")?.getBoundingClientRect().top;

document.addEventListener("htmx:before:swap", (event) => {
  const { ctx } = event.detail;
  if (ctx.formworkInlinePage && ctx.target instanceof Element) ctx.target._formworkPagerTop = inlinePagerTop(ctx.target);
});

// Settling starts right after the morph, before the browser draws the new rows.
document.addEventListener("htmx:before:settle", (event) => {
  const group = event.target;
  const before = group._formworkPagerTop;
  if (before === undefined) return;
  delete group._formworkPagerTop;
  const after = inlinePagerTop(group);
  if (after !== undefined && after !== before) window.scrollBy({ top: after - before, behavior: "instant" });
});

document.addEventListener("htmx:after:swap", (event) => {
  const { ctx } = event.detail;
  const group = ctx.target;
  if (!ctx.formworkInlinePage || !(group instanceof Element) || !group.isConnected) return;
  const form = group.closest("form");
  requestAnimationFrame(() => form?._formworkDirtySnapshot?.(group));
  if (!group.contains(document.activeElement)) {
    group.querySelector("[data-inline-pages] [aria-current=page]")?.focus({ preventScroll: true });
  }
});

document.addEventListener("htmx:after:swap", (event) => {
  const { ctx } = event.detail;
  const link = ctx.formworkLink;
  if (!link) return;
  document.dispatchEvent(new CustomEvent("formwork-admin:page"));
  // The focus stays on the link that led here while it shows; otherwise the new content takes it.
  if (ctx.formworkDrawn || document.activeElement !== link || !link.isConnected) {
    document.getElementById("content")?.focus({ preventScroll: true });
  }
  // A screen reader hears the new page's title, as after a page load.
  const announcer = document.getElementById("formwork-admin-announcer");
  if (announcer && ctx.title) announcer.textContent = ctx.title;
});
