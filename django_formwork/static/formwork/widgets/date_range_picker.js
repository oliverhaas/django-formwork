// DateRangePicker and DateTimeRangePicker: a start and an end picked in a
// two-month calendar. The first pick sets the start, the second the end; a
// second pick before the start begins the range again there.

import { countText, dropdownBase } from "./_helpers.js";
import { parseIso, SELECTED, withCalendar } from "./_calendar.js";

const DAY = 86400000;

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkDateRangePicker", () =>
    dropdownBase(
      withCalendar({
        open: false,
        withTime: false,
        // What the hidden inputs hold: YYYY-MM-DD, or YYYY-MM-DDTHH:MM with time.
        start: "",
        end: "",
        // The range on screen, as YYYY-MM-DD. It differs from the inputs only
        // while the end is still to pick.
        draftStart: "",
        draftEnd: "",
        startTime: "00:00",
        endTime: "23:59",
        // Which end the next day picked sets.
        picking: "start",
        hoverIso: "",

        init() {
          const el = this.$el;
          this.withTime = el.dataset.withTime === "true";
          this.initCalendar();
          this.anchorPanel();
          // Open after x-show has run: a hidden panel has no height to measure.
          this.$watch("open", (open) => (open ? this.$nextTick(() => this.showPanel()) : this.hidePanel()));
          const sync = () => {
            this.start = el.dataset.start || "";
            this.end = el.dataset.end || "";
            if (!this.open) this.loadDraft();
          };
          sync();
          // A morph keeps this component, so init() runs once. The range the
          // server sends re-syncs it.
          new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: ["data-start", "data-end"] });
          el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
        },

        get isOpen() {
          return this.open;
        },

        loadDraft() {
          this.draftStart = this.start.slice(0, 10);
          this.draftEnd = this.end.slice(0, 10);
          this.startTime = this.start.slice(11, 16) || "00:00";
          this.endTime = this.end.slice(11, 16) || "23:59";
          this.picking = "start";
          this.hoverIso = "";
        },

        // A click on the end of the trigger picks the end first, so a range
        // can change its end alone.
        toggle(event) {
          if (this.open) {
            this.close();
            return;
          }
          this.show();
          if (this.$refs.endPart.contains(event?.target) && this.draftStart) this.picking = "end";
        },
        show() {
          if (this.open) return;
          this.loadDraft();
          this.resetView(this.draftStart || this.draftEnd);
          this.open = true;
        },
        // Closing drops a range whose end is still to pick.
        close() {
          this.open = false;
          this.hidePanel();
          this.loadDraft();
        },
        openGrid() {
          this.show();
          this.focusGrid();
        },
        onEscape(event) {
          if (!this.open) return;
          event.preventDefault();
          event.stopPropagation();
          const refocus = this.$refs.panel.contains(document.activeElement);
          this.close();
          if (refocus) this.$refs.trigger.focus();
        },
        // Done closes the panel of a range with times.
        done() {
          if (!this.draftEnd) return;
          this.close();
          this.$refs.trigger.focus();
        },

        pickDay(cell) {
          this.focusIso = cell.iso;
          if (this.picking === "start" || cell.iso < this.draftStart) {
            this.draftStart = cell.iso;
            this.draftEnd = "";
            this.picking = "end";
            return;
          }
          this.draftEnd = cell.iso;
          this.picking = "start";
          this.commit();
          // A range with times stays open for them.
          if (!this.withTime) this.done();
        },
        hover(cell) {
          this.hoverIso = cell?.iso || "";
        },
        onTimeChange() {
          if (this.draftEnd) this.commit();
        },
        clear() {
          this.draftStart = "";
          this.draftEnd = "";
          this.commit();
          this.close();
          this.$refs.trigger.focus();
        },

        // Writes the range to the inputs and fires one `change` for the field.
        commit() {
          const complete = this.draftStart && this.draftEnd;
          const value = (iso, time, fallback) => (this.withTime ? `${iso}T${time || fallback}` : iso);
          this.start = complete ? value(this.draftStart, this.startTime, "00:00") : "";
          this.end = complete ? value(this.draftEnd, this.endTime, "23:59") : "";
          this.$refs.start.value = this.start;
          this.$refs.end.value = this.end;
          // The attributes follow, so a server value that equals the old one
          // still reads as a change.
          this.$root.dataset.start = this.start;
          this.$root.dataset.end = this.end;
          this.notePick();
          this.$refs.end.dispatchEvent(new Event("change", { bubbles: true }));
        },

        // --- The trigger ---

        get startText() {
          return this.partText("start");
        },
        get endText() {
          return this.partText("end");
        },
        partText(part) {
          const iso = part === "start" ? this.draftStart : this.draftEnd;
          if (!iso) return part === "start" ? this.$root.dataset.startPlaceholder : this.$root.dataset.endPlaceholder;
          const date = parseIso(iso);
          if (this.withTime) {
            const [hours, minutes] = (part === "start" ? this.startTime : this.endTime).split(":").map(Number);
            date.setHours(hours || 0, minutes || 0);
          }
          return this.formatted(date, "value");
        },
        isActivePart(part) {
          return this.open && this.picking === part;
        },

        // --- The footer ---

        get needsStart() {
          return !this.draftStart;
        },
        get needsEnd() {
          return Boolean(this.draftStart) && !this.draftEnd;
        },
        get dayCount() {
          if (!this.draftEnd) return "";
          const days = Math.round((parseIso(this.draftEnd) - parseIso(this.draftStart)) / DAY) + 1;
          return countText(this.$root, days);
        },

        // --- The calendar ---

        // The days the band covers, ends included: the picked range, or the
        // days up to the hovered one while the end is still to pick.
        get band() {
          const { draftStart: first, draftEnd: last } = this;
          if (first && last) return last > first ? { first, last, preview: false } : null;
          if (first && this.picking === "end" && this.hoverIso > first) return { first, last: this.hoverIso, preview: true };
          return null;
        },
        isSelected(cell) {
          const { draftStart: first, draftEnd: last } = this;
          return cell.iso === first || (Boolean(last) && cell.iso >= first && cell.iso <= last);
        },
        cellClass(cell) {
          const band = this.band;
          if (!band || cell.hidden || cell.iso <= band.first || cell.iso > band.last) return "";
          const classes = band.preview ? "range-middle range-preview" : "range-middle";
          if (cell.iso < band.last) return classes;
          return band.preview ? `${classes} range-last` : "";
        },
        // The ends are squared where they meet the band.
        dayClass(cell) {
          const band = this.band;
          const isStart = cell.iso === this.draftStart;
          const isEnd = cell.iso === this.draftEnd;
          if (!isStart && !isEnd) return this.dayTone(cell);
          if (!band) return SELECTED;
          return isStart ? `${SELECTED} rounded-e-none` : `${SELECTED} rounded-s-none`;
        },
      }),
    ),
  );
});
