// Shared helpers for the formwork dropdown Alpine.data components
// (formworkSearchSelect, formworkMultiSelect, formworkComboBox).

export const visibleOptions = (component, selector) =>
  [...component.$refs.options.querySelectorAll(selector)]
    .filter((b) => b.offsetParent !== null);

// --- Top-layer dropdown panels -----------------------------------------
// popover="manual" (not "auto"): the details toggle / Alpine `open` state
// stays the source of truth, so light dismiss must not close the popover
// behind its back.  Placement is CSS anchor positioning where supported,
// positionPanel() otherwise; with no Popover API the panel stays
// absolutely positioned.

const supportsPopover =
  typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
const supportsAnchor =
  typeof CSS !== "undefined" && CSS.supports("anchor-name: --a");

let anchorSeq = 0;

// Anchor names must be unique per instance, so they are inline styles
// rather than a stylesheet rule.
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
    // The panel can resize while open (htmx swaps in search results).
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
