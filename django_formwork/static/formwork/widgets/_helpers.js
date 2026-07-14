// Shared helpers for the formwork dropdown Alpine.data components
// (formworkSearchSelect, formworkMultiSelect, formworkComboBox).

export const visibleOptions = (component, selector) =>
  [...component.$refs.options.querySelectorAll(selector)]
    .filter((b) => b.offsetParent !== null);

// --- Top-layer dropdown panels -----------------------------------------
// The .dropdown-content panel is promoted to popover="manual" so it
// renders in the browser top layer and escapes overflow/clip ancestors
// (scrollable tables, cards).  Support tiers:
//   1. Popover + CSS anchor positioning: formwork.css pins the panel to
//      the widget root and flips it when out of room (position-try).
//   2. Popover only (Firefox): positionPanel() mirrors that CSS with
//      inline fixed coordinates, flipping above when out of room below.
//   3. No Popover API: the attribute is never added and the panel keeps
//      its absolutely-positioned behavior.
// The open/close state machines (details toggle, Alpine `open`) stay the
// source of truth; popover="manual" opts out of light dismiss so the
// existing outside-click handling keeps working.

const supportsPopover =
  typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
const supportsAnchor =
  typeof CSS !== "undefined" && CSS.supports("anchor-name: --a");

let anchorSeq = 0;

// Called from init(): returns the panel with the popover attribute set,
// or null when the Popover API is unavailable.  Anchor names must be
// unique per instance, so they are assigned here rather than in CSS.
export const panelPopover = (root) => {
  const panel = root.querySelector(":scope > .dropdown-content");
  if (!panel || !supportsPopover) return null;
  panel.setAttribute("popover", "manual");
  if (supportsAnchor && !root.style.anchorName) {
    const name = `--formwork-anchor-${++anchorSeq}`;
    root.style.anchorName = name;
    panel.style.positionAnchor = name;
  }
  return panel;
};

const positionPanel = (root, panel) => {
  const GAP = 4; // matches the anchor-positioned margin (0.25rem)
  const EDGE = 8;
  const box = root.getBoundingClientRect();
  panel.style.margin = "0";
  panel.style.minWidth = `${box.width}px`;
  const pw = panel.offsetWidth;
  const ph = panel.offsetHeight;
  const below = window.innerHeight - box.bottom - GAP;
  const flip = ph > below && box.top - GAP > below;
  panel.style.top = flip
    ? `${Math.max(EDGE, box.top - GAP - ph)}px`
    : `${box.bottom + GAP}px`;
  panel.style.left = `${Math.max(EDGE, Math.min(box.left, window.innerWidth - pw - EDGE))}px`;
};

export const openPanel = (component) => {
  const panel = component._panel;
  if (!panel || !panel.isConnected) return;
  try {
    panel.showPopover();
  } catch {
    return;
  }
  if (!supportsAnchor) {
    const reposition = () => positionPanel(component.$root, panel);
    reposition();
    component._reposition = reposition;
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    // Re-place when the panel's size settles or changes (Alpine x-show
    // flushing after showPopover, htmx swapping in search results).
    component._resizeObserver = new ResizeObserver(reposition);
    component._resizeObserver.observe(panel);
  }
};

export const closePanel = (component) => {
  const panel = component._panel;
  if (!panel) return;
  if (component._reposition) {
    window.removeEventListener("scroll", component._reposition, true);
    window.removeEventListener("resize", component._reposition);
    component._reposition = null;
  }
  component._resizeObserver?.disconnect();
  component._resizeObserver = null;
  if (panel.matches(":popover-open")) panel.hidePopover();
};

export const clearHighlight = (component) => {
  if (component.highlightedEl) {
    component.highlightedEl.classList.remove("highlighted");
    component.highlightedEl = null;
  }
};

export const keyboardNav = (component, dir, selector) => {
  const visible = visibleOptions(component, selector);
  if (!visible.length) return;
  let idx = visible.indexOf(component.highlightedEl);
  if (idx === -1) idx = dir > 0 ? 0 : visible.length - 1;
  else idx = (idx + dir + visible.length) % visible.length;
  clearHighlight(component);
  component.highlightedEl = visible[idx];
  component.highlightedEl.classList.add("highlighted");
  component.highlightedEl.scrollIntoView({ block: "nearest" });
};
