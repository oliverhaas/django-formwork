// Alpine.data component for the formwork InputMask widget.
// Loaded as an ES module via Media.js or imported by formwork.js.

// The characters each mask slot accepts. Every other mask character is a literal.
const SLOTS = { "#": /\d/, A: /[a-zA-Z]/, "*": /./ };

document.addEventListener("alpine:init", () => {
  Alpine.data("formworkInputMask", () => ({
    mask: "",
    dot: "·",
    raw: "",

    init() {
      this.mask = this.$el.dataset.mask || "";
      this.raw = this.parse(this.$refs.display.getAttribute("data-initial") || "");
      this.render();
      this.$el._formworkAcceptMorph = (newNode) => this.acceptMorph(newNode);
    },

    // The display and the overlay exist only on the client, so the server's
    // copy of them is empty. Fill it in before the morph copies it over.
    acceptMorph(newNode) {
      const display = newNode.querySelector(".input-mask-display");
      // A focused display keeps the user's typing, as every focused input does.
      if (display && this.$refs.display !== document.activeElement) {
        this.raw = this.parse(display.getAttribute("data-initial") || "");
        display.setAttribute("value", this.buildFull());
      }
      const hidden = newNode.querySelector("input[type=hidden]");
      if (hidden) hidden.setAttribute("value", this.buildClean());
      const overlay = newNode.querySelector(".input-mask-overlay");
      if (overlay) overlay.innerHTML = this.buildOverlay();
      return true;
    },

    // The slot characters of a value written against the mask. A literal is
    // skipped where the mask has it, so a `+1` mask does not read its own 1.
    parse(value) {
      const input = value.replaceAll(this.dot, "");
      let result = "";
      let ri = 0;
      for (let i = 0; i < this.mask.length && ri < input.length; ) {
        const slot = SLOTS[this.mask[i]];
        if (slot) {
          if (slot.test(input[ri])) {
            result += input[ri];
            i++;
          }
          ri++;
        } else {
          if (input[ri] === this.mask[i]) ri++;
          i++;
        }
      }
      return result;
    },
    // Keep the characters that fit the slots in order, dropping the rest.
    fit(chars) {
      let result = "";
      let si = 0;
      const slots = [...this.mask].filter((m) => SLOTS[m]);
      for (const c of chars) {
        if (si >= slots.length) break;
        if (SLOTS[slots[si]].test(c)) {
          result += c;
          si++;
        }
      }
      return result;
    },
    // How many raw characters sit before display position `pos`.
    rawIndexAt(pos) {
      let count = 0;
      for (let i = 0; i < Math.min(pos, this.mask.length); i++) {
        if (SLOTS[this.mask[i]]) count++;
      }
      return Math.min(count, this.raw.length);
    },
    // The display position of slot `k`, or the end of the mask.
    slotPos(k) {
      let count = 0;
      for (let i = 0; i < this.mask.length; i++) {
        if (SLOTS[this.mask[i]]) {
          if (count === k) return i;
          count++;
        }
      }
      return this.mask.length;
    },

    buildFull() {
      let result = "";
      let ri = 0;
      for (const m of this.mask) {
        if (SLOTS[m]) {
          result += ri < this.raw.length ? this.raw[ri++] : this.dot;
        } else {
          result += m;
        }
      }
      return result;
    },
    buildClean() {
      let result = "";
      let ri = 0;
      for (const m of this.mask) {
        if (ri >= this.raw.length) break;
        result += SLOTS[m] ? this.raw[ri++] : m;
      }
      return result;
    },
    buildOverlay() {
      let html = "";
      let ri = 0;
      for (const m of this.mask) {
        if (SLOTS[m]) {
          html += ri < this.raw.length ? this.raw[ri++] : `<span class=input-mask-dot>${this.dot}</span>`;
        } else {
          html += ri < this.raw.length ? m : `<span class=input-mask-dot>${m}</span>`;
        }
      }
      return html;
    },
    cursorPos() {
      return this.slotPos(this.raw.length);
    },
    render() {
      this.$refs.display.value = this.buildFull();
      this.$refs.hidden.value = this.buildClean();
      this.$refs.overlay.innerHTML = this.buildOverlay();
    },
    commit(el, cursor) {
      this.render();
      el.setSelectionRange(cursor, cursor);
      this.$refs.hidden.dispatchEvent(new Event("input", { bubbles: true }));
    },

    // Typing and deleting edit the raw characters, so the caret steps over
    // literals: Backspace after ") " removes the digit before the ")".
    handleBeforeInput(e) {
      // An IME composition can't be cancelled; handleInput reads its result.
      if (e.isComposing || e.inputType === "insertCompositionText") return;
      const el = e.target;
      const start = this.rawIndexAt(el.selectionStart);
      const end = this.rawIndexAt(el.selectionEnd);
      const before = this.raw.slice(0, start);
      const after = this.raw.slice(end);
      if (e.inputType === "deleteContentBackward" || e.inputType === "deleteContentForward") {
        e.preventDefault();
        if (start !== end) {
          this.raw = before + after;
          this.commit(el, this.slotPos(start));
        } else if (e.inputType === "deleteContentBackward" && start > 0) {
          this.raw = before.slice(0, -1) + after;
          this.commit(el, this.slotPos(start - 1));
        } else if (e.inputType === "deleteContentForward") {
          this.raw = before + after.slice(1);
          this.commit(el, this.slotPos(start));
        }
        return;
      }
      const text = e.data ?? e.dataTransfer?.getData("text/plain");
      if (e.inputType.startsWith("insert") && text != null) {
        e.preventDefault();
        const inserted = this.fit(before + text).slice(before.length);
        this.raw = this.fit(before + inserted + after);
        this.commit(el, this.slotPos(start + inserted.length));
      }
    },
    // Edits that skip beforeinput (autofill, for one) re-read the whole display.
    handleInput(e) {
      this.raw = this.parse(e.target.value);
      this.commit(e.target, this.cursorPos());
    },
    handleClick(e) {
      const cp = this.cursorPos();
      if (e.target.selectionStart > cp) {
        e.target.setSelectionRange(cp, cp);
      }
    },
  }));
});
