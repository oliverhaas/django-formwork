// DateTimePicker: a day and a time, typed into the input or picked in the
// calendar with the time under it. The hidden input posts them as
// YYYY-MM-DDTHH:MM local time.

import { dropdownBase, outside } from "./_helpers.js";
import { isoDate, pad, parseIso, readDate, SELECTED, withCalendar } from "./_calendar.js";

// A stored time with seconds posts back unchanged while its minute stays.
const sameMinute = (value, stored) => value === stored || (/T\d{2}:\d{2}:\d{2}/.test(stored) && value === stored.slice(0, 16));

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDateTimePicker", () =>
    dropdownBase(
      withCalendar({
        open: false,
        // What the hidden input holds: YYYY-MM-DDTHH:MM, or typed text that
        // names no day, which the field then reports.
        value: "",
        // The day the input names, as YYYY-MM-DD, and its time. Text that
        // names no day leaves them, so the calendar keeps still while typing.
        draft: "",
        time: "00:00",
        _quietFocus: false,

        init() {
          const el = this.$el;
          this.initCalendar();
          this.anchorPanel();
          // Open after x-show has run: a hidden panel has no height to measure.
          this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
          this.value = el.dataset.value || "";
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
          const date = parseIso(value);
          if (!date) return value;
          const [hours, minutes, seconds] = value.slice(11, 19).split(":").map(Number);
          date.setHours(hours || 0, minutes || 0, seconds || 0);
          return this.formatted(date, "value");
        },
        writeText() {
          this.$refs.input.value = this.draft ? this.textOf(`${this.draft}T${this.time}`) : "";
        },
        // The day and time the input's text names, or null. A day without a
        // time counts too, at the time the panel shows.
        read() {
          const formats = [this.formats.value, this.formats.label].filter(Boolean);
          return readDate(this.$refs.input.value, formats, this.inputFormats, this.names);
        },
        readInput() {
          const typed = this.read();
          if (!this.$refs.input.value.trim()) this.draft = "";
          else if (typed) {
            this.draft = typed.iso;
            if (typed.time) this.time = typed.time;
          }
        },
        // ISO for text that names a day, the text itself for text that does
        // not, so the field reports it.
        postValue() {
          const typed = this.read();
          if (!typed) return this.$refs.input.value.trim();
          return `${typed.iso}T${typed.time || this.time}`;
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

        // --- The input ---

        show() {
          if (this.open) return;
          this.readInput();
          this.resetView(this.draft);
          this.open = true;
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
        // Back in the input after a pick, without opening the calendar again.
        quietFocus() {
          this._quietFocus = true;
          this.$refs.input.focus();
          this._quietFocus = false;
        },
        onInputFocus() {
          if (!this._quietFocus) this.show();
        },
        // Arrow Down moves from the input into the calendar.
        onInputDown(event) {
          event.preventDefault();
          this.show();
          this.focusGrid();
        },
        onType() {
          this.readInput();
          const date = parseIso(this.draft);
          if (!date || !this.open || this.view !== "days") return;
          this.focusIso = this.draft;
          if (this.draft < this.firstIso || this.draft > this.lastIso) this.showMonth(date);
        },
        // Text that names a day reads as the widget writes it when the input is left.
        onTypeDone() {
          if (this.read()) this.writeText();
        },
        // Enter commits and closes the calendar. With the calendar closed it
        // also submits the form, as in any text input.
        onEnter(event) {
          this.onTypeDone();
          this.commit();
          if (!this.open) return;
          event.preventDefault();
          this.close();
        },
        // A click in the calendar leaves the focus in the input, so typing
        // goes on. The time input takes it.
        keepInputFocus(event) {
          if (event.target.closest("input")) return;
          if (this.$refs.input === document.activeElement) event.preventDefault();
        },
        // Leaving the widget commits what the input names. Moving to another
        // control also closes the calendar; a click on the page closes it
        // through @click.outside.
        onFocusOut(event) {
          const to = event.relatedTarget;
          if (to && this.$root.contains(to)) return;
          this.commit();
          if (outside(this.$root, to)) this.close();
        },
        // Escape closes an open calendar and goes no further, so a <dialog>
        // around the widget stays open.
        onEscape(event) {
          if (!this.open) return;
          event.preventDefault();
          event.stopPropagation();
          const refocus = this.$refs.panel.contains(document.activeElement);
          this.close();
          if (refocus) this.quietFocus();
        },

        // --- The calendar ---

        // A picked day stays open for the time.
        pickDay(cell) {
          this.focusIso = cell.iso;
          this.draft = cell.iso;
          this.writeText();
        },
        onTimeChange() {
          if (this.draft) this.writeText();
        },
        pickNow() {
          const now = new Date();
          this.draft = isoDate(now);
          this.time = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
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
        hover() {},

        get picked() {
          return Boolean(this.draft);
        },
        isSelected(cell) {
          return cell.iso === this.draft;
        },
        cellClass() {
          return "";
        },
        dayClass(cell) {
          return cell.iso === this.draft ? SELECTED : this.dayTone(cell);
        },
      }),
    ),
  );
});
