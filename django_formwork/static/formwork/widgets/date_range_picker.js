// DateRangePicker and DateTimeRangePicker: a start and an end, typed into two
// inputs or picked in a two-month calendar. A day picked in the calendar sets
// the end whose input has the focus, a start moves on to the end, and an end
// picked before the start begins the range again there.

import { countText, dropdownBase } from "./_helpers.js";
import { addMonths, parseIso, readDate, SELECTED, withCalendar } from "./_calendar.js";

const DAY = 86400000;
const PARTS = ["start", "end"];

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDateRangePicker", () =>
    dropdownBase(
      withCalendar({
        open: false,
        withTime: false,
        // What the hidden inputs hold: YYYY-MM-DD, YYYY-MM-DDTHH:MM with time,
        // or typed text that names no date, which the field then reports.
        start: "",
        end: "",
        // The days the inputs name, as YYYY-MM-DD. Text that names no day
        // leaves them as they were, so the calendar keeps still while typing.
        draft: { start: "", end: "" },
        time: { start: "00:00", end: "23:59" },
        // Which end the next day picked sets.
        picking: "start",
        hoverIso: "",
        _quietFocus: false,

        init() {
          const el = this.$el;
          this.withTime = el.dataset.withTime === "true";
          this.initCalendar();
          this.anchorPanel();
          // Open after x-show has run: a hidden panel has no height to measure.
          this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
          this.start = el.dataset.start || "";
          this.end = el.dataset.end || "";
          this.readInputs();
          // A morph keeps this component, so init() runs once. The range the
          // server sends re-syncs it; text the user is typing stays.
          new MutationObserver(() => {
            this.start = el.dataset.start || "";
            this.end = el.dataset.end || "";
            for (const part of PARTS) {
              if (this.input(part) !== document.activeElement) this.input(part).value = this.textOf(this[part]);
            }
            this.readInputs();
          }).observe(el, { attributes: true, attributeFilter: ["data-start", "data-end"] });
          el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
        },

        get isOpen() {
          return this.open;
        },

        input(part) {
          return part === "start" ? this.$refs.startInput : this.$refs.endInput;
        },

        // --- Text ---

        // The text an input shows for a value of its hidden input.
        textOf(value) {
          const date = parseIso(value);
          if (!date) return value;
          if (this.withTime) {
            const [hours, minutes] = value.slice(11, 16).split(":").map(Number);
            date.setHours(hours || 0, minutes || 0);
          }
          return this.formatted(date, "value");
        },
        // Writes a part's day and time into its input.
        writeText(part) {
          const iso = this.draft[part];
          this.input(part).value = iso ? this.textOf(this.withTime ? `${iso}T${this.time[part]}` : iso) : "";
        },
        // The day and time an input's text names, or null. A date without a
        // time counts too, at the time the part has.
        read(part) {
          const formats = [this.formats.value, this.formats.label].filter(Boolean);
          return readDate(this.input(part).value, formats, this.inputFormats, this.names);
        },
        readInputs() {
          for (const part of PARTS) {
            const typed = this.read(part);
            if (!this.input(part).value.trim()) this.draft[part] = "";
            else if (typed) {
              this.draft[part] = typed.iso;
              if (typed.time) this.time[part] = typed.time;
            }
          }
        },
        // What a part posts: ISO for text that names a day, the text itself
        // for text that does not, so the field reports it.
        postValue(part) {
          const text = this.input(part).value.trim();
          const typed = this.read(part);
          if (!typed) return text;
          return this.withTime ? `${typed.iso}T${typed.time || this.time[part]}` : typed.iso;
        },

        // Writes the range to the hidden inputs and fires one `change` for the field.
        commit() {
          const start = this.postValue("start");
          const end = this.postValue("end");
          if (start === this.start && end === this.end) return;
          this.start = start;
          this.end = end;
          this.$refs.start.value = start;
          this.$refs.end.value = end;
          // The attributes follow, so a server value that equals the old one
          // still reads as a change.
          this.$root.dataset.start = start;
          this.$root.dataset.end = end;
          this.notePick();
          this.$refs.end.dispatchEvent(new Event("change", { bubbles: true }));
        },

        // --- The inputs ---

        onPartFocus(part) {
          this.picking = part;
          if (!this._quietFocus) this.show();
        },
        // A click opens the calendar that Escape closed.
        onPartClick(part) {
          this.picking = part;
          this.show();
        },
        quietFocus(part) {
          this._quietFocus = true;
          this.input(part).focus();
          this._quietFocus = false;
        },
        // A click on the box beside the inputs goes to the nearer one. The
        // icon also closes an open calendar.
        onFieldClick(event) {
          if (event.target.closest("input") || this.input("start").disabled) return;
          if (this.open && event.target.closest(".icon")) {
            this.close();
            return;
          }
          const distance = (part) => {
            const box = this.input(part).getBoundingClientRect();
            return Math.abs(event.clientX - (box.left + box.right) / 2);
          };
          const part = distance("end") < distance("start") ? "end" : "start";
          this.input(part).focus();
          this.onPartClick(part);
        },
        onType(part) {
          this.picking = part;
          const typed = this.read(part);
          if (!this.input(part).value.trim()) this.draft[part] = "";
          if (!typed) return;
          this.draft[part] = typed.iso;
          if (typed.time) this.time[part] = typed.time;
          this.reveal(part);
        },
        // Text that names a day reads as the widget writes it once the input is left.
        onTypeDone(part) {
          if (this.read(part)) this.writeText(part);
        },
        // Enter commits the range and closes the calendar. With the calendar
        // closed it also submits the form, as in any text input.
        onEnter(event, part) {
          this.onTypeDone(part);
          this.commit();
          if (!this.open) return;
          event.preventDefault();
          this.close();
        },
        // Tab from the end goes on to the next field, past the open calendar.
        onEndTab(event) {
          if (!event.shiftKey) this.close();
        },
        // Arrow Down moves from an input into the calendar.
        onInputDown(event) {
          event.preventDefault();
          this.show();
          this.focusGrid();
        },
        // A click in the calendar or on the box leaves the focus in the
        // input, so typing goes on. The time inputs take it.
        keepInputFocus(event) {
          if (event.target.closest("input")) return;
          if (PARTS.some((part) => this.input(part) === document.activeElement)) event.preventDefault();
        },
        // Leaving the widget commits what the inputs name. Moving to another
        // control also closes the calendar; a click on the page closes it
        // through @click.outside.
        onFocusOut(event) {
          const to = event.relatedTarget;
          if (to && this.$root.contains(to)) return;
          this.commit();
          if (to) this.close();
        },

        // --- The calendar ---

        show() {
          if (this.open) return;
          this.readInputs();
          this.resetView(this.draft.start || this.draft.end);
          if (this.draft[this.picking]) this.reveal(this.picking);
          this.open = true;
        },
        close() {
          this.open = false;
          this.hoverIso = "";
          this.hidePanel();
        },
        onEscape(event) {
          if (!this.open) return;
          event.preventDefault();
          event.stopPropagation();
          const refocus = this.$refs.panel.contains(document.activeElement);
          this.close();
          if (refocus) this.quietFocus(this.picking);
        },
        // Brings a part's day into view: a start in the first month, an end in the last.
        reveal(part) {
          const iso = this.draft[part];
          this.focusIso = iso;
          if (this.view === "days" && iso >= this.firstIso && iso <= this.lastIso) return;
          this.view = "days";
          const date = parseIso(iso);
          this.showMonth(part === "end" ? addMonths(date, 1 - this.monthCount) : date);
        },

        pickDay(cell) {
          this.focusIso = cell.iso;
          const typing = PARTS.some((part) => this.input(part) === document.activeElement);
          if (this.picking === "start" || cell.iso < this.draft.start) {
            // A new start keeps the end it does not pass.
            if (this.picking === "end" || cell.iso > this.draft.end) this.draft.end = "";
            this.draft.start = cell.iso;
            this.writeText("start");
            this.writeText("end");
            this.picking = "end";
            if (typing) this.quietFocus("end");
            return;
          }
          this.draft.end = cell.iso;
          this.writeText("end");
          this.picking = "start";
          this.commit();
          // A range with times stays open for them.
          if (!this.withTime) this.done();
        },
        hover(cell) {
          this.hoverIso = cell?.iso || "";
        },
        onTimeChange() {
          for (const part of PARTS) if (this.draft[part]) this.writeText(part);
        },
        // Done closes the panel of a range with times.
        done() {
          this.commit();
          this.quietFocus("end");
          this.close();
        },
        clear() {
          this.draft = { start: "", end: "" };
          this.writeText("start");
          this.writeText("end");
          this.commit();
          this.quietFocus("start");
          this.close();
        },

        isActivePart(part) {
          return this.open && this.picking === part;
        },

        // --- The presets ---

        isPreset(button) {
          return this.draft.start === button.dataset.start && this.draft.end === button.dataset.end;
        },
        presetClass(button) {
          return this.isPreset(button) ? SELECTED : "btn-ghost";
        },
        // A preset picks its whole days, from 00:00 to 23:59 in a range with times.
        applyPreset(button) {
          this.draft = { start: button.dataset.start, end: button.dataset.end };
          this.time = { start: "00:00", end: "23:59" };
          this.writeText("start");
          this.writeText("end");
          this.picking = "start";
          this.done();
        },

        // --- The footer ---

        get needsStart() {
          return !this.draft.start;
        },
        get needsEnd() {
          return Boolean(this.draft.start) && !this.draft.end;
        },
        get dayCount() {
          const { start, end } = this.draft;
          if (!start || !end || end < start) return "";
          const days = Math.round((parseIso(end) - parseIso(start)) / DAY) + 1;
          return countText(this.$root, days);
        },

        // --- The days ---

        // The days the band covers, ends included: the range, or the days up
        // to the hovered one while the end is to pick.
        get band() {
          const { start: first, end: last } = this.draft;
          if (first && this.picking === "end" && this.open && this.hoverIso > first) {
            return { first, last: this.hoverIso, preview: true };
          }
          if (first && last) return last > first ? { first, last, preview: false } : null;
          return null;
        },
        isSelected(cell) {
          const { start: first, end: last } = this.draft;
          return cell.iso === first || (Boolean(last) && cell.iso >= first && cell.iso <= last);
        },
        cellClass(cell) {
          const band = this.band;
          if (!band || cell.hidden || cell.iso <= band.first || cell.iso > band.last) return "";
          const classes = band.preview ? "range-middle range-preview" : "range-middle";
          if (cell.iso < band.last) return classes;
          return band.preview ? `${classes} range-last` : "";
        },
        // The ends are squared where they meet the band. While the band
        // follows the pointer, the old end shows as a plain day.
        dayClass(cell) {
          const band = this.band;
          const isStart = cell.iso === this.draft.start;
          const isEnd = cell.iso === this.draft.end && !band?.preview;
          if (!isStart && !isEnd) return this.dayTone(cell);
          if (!band) return SELECTED;
          return isStart ? `${SELECTED} rounded-e-none` : `${SELECTED} rounded-s-none`;
        },
      }),
    ),
  );
});
