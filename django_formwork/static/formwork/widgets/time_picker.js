// TimePicker: a time of day, typed into the input or picked from the lists
// of hours and minutes under it. The hidden input posts it as HH:MM.

import { dropdownBase, outside } from "./_helpers.js";
import { formatDjango, pad, parseJson, readTime, SELECTED } from "./_calendar.js";

// A stored time with seconds posts back unchanged while its minute stays.
const sameMinute = (value, stored) => value === stored || (/^\d{2}:\d{2}:\d{2}/.test(stored) && value === stored.slice(0, 5));

const NEXT_KEYS = { ArrowDown: 1, ArrowUp: -1 };

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkTimePicker", () =>
    dropdownBase({
      open: false,
      // What the hidden input holds: HH:MM, or typed text that names no
      // time, which the field then reports.
      value: "",
      // The time the input names, as HH:MM, or "". Text that names no time
      // leaves it, so the lists keep still while typing.
      draft: "",
      // The lists are built when the panel first opens.
      built: false,
      names: {},
      formats: {},
      inputFormats: [],
      // How the hour list writes an hour: H, G, h or g, as Django's codes.
      hourCode: "H",
      // The names code of a.m. and p.m. for a 12-hour clock, else "".
      half: "",
      step: 5,
      _quietFocus: false,

      // The panel is as tall as its lists and keeps its own width.
      panelMaxHeight: Number.POSITIVE_INFINITY,
      panelUsableHeight: Number.POSITIVE_INFINITY,
      panelMatchesTrigger: false,
      panelKeepsWidth: false,

      init() {
        const el = this.$el;
        const data = el.dataset;
        this.names = parseJson(data.names);
        this.formats = parseJson(data.formats);
        this.inputFormats = data.inputFormats ? parseJson(data.inputFormats) : [];
        this.hourCode = data.hour || "H";
        this.half = data.half || "";
        this.step = Math.max(1, Number(data.step) || 5);
        this.anchorPanel();
        // Open after x-show has run: a hidden panel has no height to measure.
        this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
        this.value = data.value || "";
        this.readInput();
        // A morph keeps this component, so init() runs once. The value the
        // server sends re-syncs it; text the user is typing stays.
        new MutationObserver(() => {
          this.value = el.dataset.value || "";
          if (this.$refs.input !== document.activeElement) this.$refs.input.value = this.textOf(this.value);
          this.readInput();
        }).observe(el, { attributes: true, attributeFilter: ["data-value"] });
        el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
      },

      get isOpen() {
        return this.open;
      },

      // --- Text ---

      // The text the input shows for a value of the hidden input.
      textOf(value) {
        const match = /^(\d{2}):(\d{2})(?::(\d{2}))?/.exec(value);
        if (!match) return value;
        const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]), Number(match[3] || 0));
        return formatDjango(date, this.formats.value || "H:i", this.names);
      },
      writeText() {
        this.$refs.input.value = this.draft ? this.textOf(this.draft) : "";
      },
      // The time the input's text names as HH:MM, or null.
      read() {
        return readTime(this.$refs.input.value, [this.formats.value].filter(Boolean), this.inputFormats, this.names);
      },
      readInput() {
        const typed = this.read();
        if (!this.$refs.input.value.trim()) this.draft = "";
        else if (typed) this.draft = typed;
      },
      // HH:MM for text that names a time, the text itself for text that does
      // not, so the field reports it.
      postValue() {
        return this.read() || this.$refs.input.value.trim();
      },

      // Writes the hidden input and fires its `change`.
      commit() {
        const value = this.postValue();
        if (sameMinute(value, this.value)) return;
        this.value = value;
        this.$refs.value.value = value;
        // The attribute follows, so a server value that equals the old one
        // still reads as a change.
        this.$root.dataset.value = value;
        this.notePick();
        this.$refs.value.dispatchEvent(new Event("change", { bubbles: true }));
      },

      // --- The lists ---

      get hour() {
        return this.draft ? Number(this.draft.slice(0, 2)) : null;
      },
      get minute() {
        return this.draft ? Number(this.draft.slice(3, 5)) : null;
      },
      // The options of a list, each with the value it picks and its label. A
      // 12-hour clock lists 12 first, which picks hour 0 of its half. A
      // minute off the step joins the list while it is picked.
      options(column) {
        if (column === "hour") {
          const twelve = Boolean(this.half);
          const hours = twelve ? [12, ...Array.from({ length: 11 }, (_, index) => index + 1)] : Array.from({ length: 24 }, (_, index) => index);
          const label = (hour) => ("Hh".includes(this.hourCode) ? pad(hour) : String(hour));
          return hours.map((hour) => ({ value: twelve ? hour % 12 : hour, label: label(hour) }));
        }
        if (column === "half") return (this.names[this.half] || []).map((label, index) => ({ value: index, label }));
        const minutes = Array.from({ length: Math.ceil(60 / this.step) }, (_, index) => index * this.step);
        if (this.minute !== null && !minutes.includes(this.minute)) minutes.push(this.minute);
        return minutes.sort((a, b) => a - b).map((minute) => ({ value: minute, label: pad(minute) }));
      },
      picked(column) {
        if (this.hour === null) return null;
        if (column === "hour") return this.half ? this.hour % 12 : this.hour;
        if (column === "half") return Math.floor(this.hour / 12);
        return this.minute;
      },
      isPicked(column, option) {
        return this.picked(column) === option.value;
      },
      optionClass(column, option) {
        return this.isPicked(column, option) ? SELECTED : "btn-ghost";
      },
      // Each list is one tab stop: its picked option, else its first.
      optionTabindex(column, option) {
        const picked = this.picked(column);
        return option.value === (picked ?? this.options(column)[0].value) ? 0 : -1;
      },
      // A pick keeps the other parts of the time; without one, they start at 00:00.
      pick(column, option) {
        let hour = this.hour ?? 0;
        let minute = this.minute ?? 0;
        if (column === "hour") hour = this.half ? option.value + (hour >= 12 ? 12 : 0) : option.value;
        else if (column === "half") hour = (hour % 12) + option.value * 12;
        else minute = option.value;
        this.draft = `${pad(hour)}:${pad(minute)}`;
        this.writeText();
      },
      // Each list scrolls its picked option to the middle.
      scrollToPicked() {
        for (const list of this.$refs.panel.querySelectorAll("[data-column]")) {
          const option = list.querySelector('[aria-selected="true"]');
          list.scrollTop = option ? option.offsetTop - list.offsetTop - (list.clientHeight - option.offsetHeight) / 2 : 0;
        }
      },
      // Up and Down move in a list, Home and End to its ends, Left and Right
      // to the next list.
      onColumnKey(event) {
        const option = event.target.closest('[role="option"]');
        if (!option || event.altKey || event.ctrlKey || event.metaKey) return;
        const options = [...option.parentElement.querySelectorAll('[role="option"]')];
        const index = options.indexOf(option);
        const lists = [...this.$refs.panel.querySelectorAll("[data-column]")];
        const back = getComputedStyle(option).direction === "rtl" ? 1 : -1;
        const sideways = { ArrowLeft: back, ArrowRight: -back }[event.key];
        let target = null;
        if (event.key in NEXT_KEYS) target = options[index + NEXT_KEYS[event.key]];
        else if (event.key === "Home") target = options[0];
        else if (event.key === "End") target = options.at(-1);
        else if (sideways) target = lists[lists.indexOf(option.parentElement) + sideways]?.querySelector('[tabindex="0"]');
        else return;
        event.preventDefault();
        target?.focus();
      },

      // --- The input ---

      show() {
        if (this.open) return;
        this.readInput();
        this.built = true;
        this.open = true;
        this.$nextTick(() => this.scrollToPicked());
      },
      close() {
        this.open = false;
        this.hidePanel();
      },
      toggle() {
        if (this.open) this.close();
        else this.show();
      },
      // The box around the input is not a <label>, which would add the
      // toggle's name to the input's, so a click on its padding focuses the
      // input here.
      focusInput(event) {
        if (event.target.closest(".date-picker-toggle")) return;
        this.$refs.input.focus();
      },
      // Back in the input after a pick, without opening the lists again.
      quietFocus() {
        this._quietFocus = true;
        this.$refs.input.focus();
        this._quietFocus = false;
      },
      onInputFocus() {
        if (!this._quietFocus) this.show();
      },
      // Arrow Down moves from the input into the hour list.
      onInputDown(event) {
        event.preventDefault();
        this.show();
        this.$nextTick(() => this.$refs.panel.querySelector('[data-column] [tabindex="0"]')?.focus());
      },
      onType() {
        this.readInput();
        if (this.open) this.$nextTick(() => this.scrollToPicked());
      },
      // Text that names a time reads as the widget writes it when the input is left.
      onTypeDone() {
        if (this.read()) this.writeText();
      },
      // Enter commits and closes the lists. With the lists closed it also
      // submits the form, as in any text input.
      onEnter(event) {
        this.onTypeDone();
        this.commit();
        if (!this.open) return;
        event.preventDefault();
        this.close();
      },
      // A click in the panel leaves the focus in the input, so typing goes on.
      keepInputFocus(event) {
        if (event.target.closest("input")) return;
        if (this.$refs.input === document.activeElement) event.preventDefault();
      },
      // Leaving the widget commits what the input names. Moving to another
      // control also closes the panel; a click on the page closes it through
      // @click.outside.
      onFocusOut(event) {
        const to = event.relatedTarget;
        if (to && this.$root.contains(to)) return;
        this.commit();
        if (outside(this.$root, to)) this.close();
      },
      // Escape closes an open panel and goes no further, so a <dialog> around
      // the widget stays open.
      onEscape(event) {
        if (!this.open) return;
        event.preventDefault();
        event.stopPropagation();
        const refocus = this.$refs.panel.contains(document.activeElement);
        this.close();
        if (refocus) this.quietFocus();
      },

      // --- The footer ---

      pickNow() {
        const now = new Date();
        this.draft = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
        this.writeText();
        this.done();
      },
      clear() {
        this.draft = "";
        this.writeText();
        this.done();
      },
      done() {
        this.commit();
        this.quietFocus();
        this.close();
      },
    }),
  );
});
