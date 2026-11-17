/**
 * filters.js: fits the changelist's filters to the search row.
 *
 * The filters follow the search box in list_filter order. Those the row has no room for
 * wait in the More menu, which puts one in the row and opens it. A filter with a value
 * always shows: it takes the room of the last filter without one, so the row keeps its
 * height and the other filters keep their place. A list too narrow for two filters next
 * to the search gives them a row of their own.
 *
 * Load it as a classic script in <head>, like columns.js: it fits the row before each
 * frame while the page parses, so no frame shows every filter.
 */
(() => {
  const BAR = "changelist-filter-bar";
  const FILTER = `#${BAR} [data-filter]`;
  const CONTROLS = "input[name], select[name], textarea[name]";

  // The filter that the More menu puts in the row. Like the filter that holds the focus, it
  // shows while it is empty, so a filter does not leave the row under the user's hands.
  let picked = "";
  let width = -1;
  let pressed = false;
  let fitOnRelease = false;

  const px = (value) => Number.parseFloat(value) || 0;

  const isSet = (filter) =>
    [...filter.querySelectorAll(CONTROLS)].some((control) =>
      control.type === "checkbox" || control.type === "radio" ? control.checked : control.value !== "",
    );

  const parts = () => {
    const bar = document.getElementById(BAR);
    const list = bar?.querySelector("[data-filter-list]");
    const more = bar?.querySelector("[data-filter-more]");
    return list && more ? { bar, list, more, filters: [...list.children] } : null;
  };

  const fit = () => {
    const found = parts();
    if (!found) return;
    const { bar, list, more, filters } = found;
    const count = more.querySelector("[data-more-count]");
    const button = more.querySelector("[role=button]");
    // Everything in the flow at its widest, to be measured.
    for (const el of [...filters, more, count]) el.hidden = false;
    delete bar.dataset.stacked;
    delete more.dataset.bare;

    const gap = px(getComputedStyle(bar).columnGap);
    const sizes = filters.map((filter) => px(getComputedStyle(filter).flexBasis) + gap);
    const focused = document.activeElement;
    const must = filters.map(
      (filter) => filter.dataset.filter === picked || filter.contains(focused) || isSet(filter),
    );
    // The filters with a value, then the others in order for as long as they fit.
    const pick = (room, forced = must) => {
      const shown = [...forced];
      let used = sizes.reduce((sum, size, index) => sum + (forced[index] ? size : 0), 0);
      for (const [index, size] of sizes.entries()) {
        if (shown[index]) continue;
        if (used + size > room) break;
        shown[index] = true;
        used += size;
      }
      return shown;
    };

    const search = bar.querySelector(":scope > [data-search]");
    const clear = bar.querySelector(":scope > a");
    const menu = more.offsetWidth + gap;
    const always = more.hasAttribute("data-always");
    let room = bar.clientWidth + gap;
    if (search) room -= px(getComputedStyle(search).flexBasis) + gap;
    if (clear) room -= clear.offsetWidth + gap;
    // The filters get their own row when fewer than two fit next to the search, or when
    // those with a value do not. Without a search they are the row.
    const beside = pick(room - menu, []).filter(Boolean).length;
    const set = sizes.reduce((sum, size, index) => sum + (must[index] ? size : 0), 0);
    const stacked = Boolean(search) && (beside < Math.min(2, filters.length) || set > room - menu);
    let shown;
    if (stacked) {
      bar.dataset.stacked = "";
      shown = pick(list.clientWidth + gap);
    } else {
      shown = always ? null : pick(room);
      if (!shown || shown.includes(false)) shown = pick(room - menu);
    }
    if (!shown.includes(true)) shown[0] = true;

    const waiting = shown.filter((value) => !value).length;
    for (const [index, filter] of filters.entries()) filter.hidden = !shown[index];
    for (const item of more.querySelectorAll("[data-more-item]")) {
      const index = filters.findIndex((filter) => filter.dataset.filter === item.dataset.moreItem);
      item.hidden = shown[index] !== false;
    }
    count.textContent = waiting;
    count.hidden = waiting === 0;
    // With every filter in the row, the menu holds only its switch and the button is its icon.
    more.toggleAttribute("data-bare", waiting === 0);
    const label = waiting === 0 ? button.dataset.labelBare : button.dataset.label;
    button.setAttribute("aria-label", label);
    button.title = waiting === 0 ? label : "";
    more.hidden = waiting === 0 && !always;
    width = bar.clientWidth;
  };

  const resized = new ResizeObserver(() => {
    const bar = document.getElementById(BAR);
    if (bar && bar.clientWidth !== width) fit();
  });

  const watch = () => {
    resized.disconnect();
    const bar = document.getElementById(BAR);
    if (bar) resized.observe(bar);
  };

  // The More menu's search box narrows its list.
  const find = (more) => {
    const words = more.querySelector("[data-more-search]")?.value.trim().toLowerCase() ?? "";
    let waiting = 0;
    let matches = 0;
    for (const item of more.querySelectorAll("[data-more-item]")) {
      const miss = !item.textContent.toLowerCase().includes(words);
      item.toggleAttribute("data-miss", miss);
      if (!item.hidden) waiting += 1;
      if (!item.hidden && !miss) matches += 1;
    }
    more.querySelector("[data-more-none]").hidden = matches > 0 || waiting === 0;
  };

  const items = (more) => [...more.querySelectorAll("[data-more-item]:not([hidden], [data-miss]) > button")];

  // Puts a filter of the More menu in the row and opens it.
  const add = (name) => {
    const filter = parts()?.filters.find((el) => el.dataset.filter === name);
    if (!filter) return;
    picked = name;
    fit();
    picked = "";
    const trigger = filter.querySelector("summary, input:not([type=hidden]), select, textarea, button");
    if (!trigger) return;
    trigger.focus();
    // A dropdown opens after the click that picked it: that click lands outside the
    // dropdown, which closes it.
    if (trigger.matches("summary")) setTimeout(() => trigger.click());
  };

  document.addEventListener("click", (event) => {
    const item = event.target.closest?.(`#${BAR} [data-more-item] > button`);
    if (item) add(item.parentElement.dataset.moreItem);
  });

  document.addEventListener("input", (event) => {
    if (event.target.matches?.(`#${BAR} [data-more-search]`)) find(event.target.closest("[data-filter-more]"));
  });

  document.addEventListener("keydown", (event) => {
    const more = event.target.closest?.(`#${BAR} [data-filter-more]`);
    if (!more) return;
    const search = more.querySelector("[data-more-search]");
    const rows = items(more);
    const at = rows.indexOf(event.target);
    if (event.key === "ArrowDown" || (event.key === "ArrowUp" && at >= 0)) {
      const to = at + (event.key === "ArrowDown" ? 1 : -1);
      // From the first row, up goes back to the search box.
      const next = to < 0 ? search : rows[Math.min(rows.length - 1, to)];
      if (!next) return;
      event.preventDefault();
      next.focus();
    } else if (event.key === "Enter" && event.target === search) {
      // Not a submit of the filter form: the first match goes to the row.
      event.preventDefault();
      rows[0]?.click();
    } else if (event.key === "Escape") {
      document.activeElement?.blur();
    }
  });

  document.addEventListener("focusout", (event) => {
    const more = event.target.closest?.(`#${BAR} [data-filter-more]`);
    const search = more?.querySelector("[data-more-search]");
    if (search?.value && !more.contains(event.relatedTarget)) {
      search.value = "";
      find(more);
    }
    const filter = event.target.closest?.(FILTER);
    if (!filter || filter.contains(event.relatedTarget) || isSet(filter)) return;
    // An empty filter that the row has no room for goes back to the menu, once the focus is
    // where it goes. A press that took the focus finishes first, so the row does not move
    // under the pointer.
    if (pressed) fitOnRelease = true;
    else setTimeout(fit);
  });

  document.addEventListener(
    "pointerdown",
    () => {
      pressed = true;
    },
    true,
  );
  for (const type of ["pointerup", "pointercancel"]) {
    document.addEventListener(
      type,
      () => {
        pressed = false;
        // A press on the More button opened its menu: typing now finds a filter. The click
        // cannot tell, as DaisyUI takes an open menu's button out of the pointer's reach.
        const button = document.activeElement?.closest?.(`#${BAR} [data-filter-more] > [role=button]`);
        button?.parentElement.querySelector("[data-more-search]")?.focus();
        if (!fitOnRelease) return;
        fitOnRelease = false;
        // After the click that this release ends.
        setTimeout(fit);
      },
      true,
    );
  }

  // While the page parses, a fit before each frame.
  let frame = 0;
  const parsing = new MutationObserver(() => {
    frame ||= requestAnimationFrame(() => {
      frame = 0;
      fit();
    });
  });
  parsing.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", () => {
    parsing.disconnect();
    cancelAnimationFrame(frame);
    fit();
    watch();
  });

  // A swap brings the server's markup, which shows every filter: fit it as the swap puts it in.
  // A dropdown hands the server's value to its input a moment later, so the row is fitted
  // again before the frame.
  document.addEventListener("htmx:before:settle", (event) => {
    if (event.target.contains?.(document.getElementById(BAR))) {
      fit();
      watch();
      requestAnimationFrame(fit);
    }
  });
  document.fonts?.addEventListener("loadingdone", fit);
})();
