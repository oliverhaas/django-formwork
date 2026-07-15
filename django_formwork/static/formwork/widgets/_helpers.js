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

// Panels whose widget currently holds them open; lets the morph-recovery
// observer below re-show a panel without a handle on the Alpine component.
const openPanels = new WeakSet();
const repositioners = new WeakMap();

// Anchor names must be unique per instance, so they are inline styles
// rather than a stylesheet rule.
export const panelPopover = (root) => {
  const panel = root.querySelector(":scope > .dropdown-content");
  if (!panel || !supportsPopover) return null;
  const apply = () => {
    panel.setAttribute("popover", "manual");
    if (supportsAnchor) {
      if (!root.style.anchorName) root.style.anchorName = `--formwork-anchor-${++anchorSeq}`;
      panel.style.positionAnchor = root.style.anchorName;
    }
  };
  apply();
  // Morph swaps (htmx 4) sync attributes back to the server HTML, which
  // carries none of this plumbing: the popover attribute and inline anchor
  // styles get stripped, force-hiding an open panel out of the top layer.
  // Re-assert them; the observer runs before the next paint, so an open
  // panel never renders unanchored.
  const observer = new MutationObserver(() => {
    const intact =
      panel.getAttribute("popover") === "manual" &&
      (!supportsAnchor || (root.style.anchorName && panel.style.positionAnchor));
    if (intact) return;
    apply();
    if (openPanels.has(panel) && !panel.matches(":popover-open")) {
      try {
        panel.showPopover();
      } catch {
        return;
      }
      repositioners.get(panel)?.();
    }
  });
  observer.observe(root, { attributes: true, attributeFilter: ["style"] });
  observer.observe(panel, { attributes: true, attributeFilter: ["style", "popover"] });
  // Deliberate teardowns (the screenshot harness flattens panels into normal
  // flow) must disconnect this first or the re-assert fights them.
  panel._formworkPopoverObserver = observer;
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
  const above = box.top - GAP;
  // Open toward whichever side has the most room (like a native <select>),
  // not just when the panel would overflow below.
  const flip = above > below;
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
  openPanels.add(panel);
  if (!supportsAnchor) {
    const reposition = () => positionPanel(component.$root, panel);
    reposition();
    component._reposition = reposition;
    repositioners.set(panel, reposition);
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
  openPanels.delete(panel);
  repositioners.delete(panel);
  if (component._reposition) {
    window.removeEventListener("scroll", component._reposition, true);
    window.removeEventListener("resize", component._reposition);
    component._reposition = null;
  }
  component._resizeObserver?.disconnect();
  component._resizeObserver = null;
  if (panel.matches(":popover-open")) panel.hidePopover();
};

// Close any open <details> dropdown when a real click lands outside it, so a
// click anywhere else on the page (including another dropdown's trigger)
// dismisses it. Native <details> has no such behaviour, and the panels use
// popover="manual" so the browser's light dismiss stays off. One shared
// listener rather than a per-widget @click.outside: this module loads once
// (ES-module dedup), and setting `open = false` fires each widget's @toggle,
// which tears the panel down. A genuine click only, never a morph, so it
// cannot close a panel behind the widget's back the way light dismiss would.
if (typeof document !== "undefined") {
  document.addEventListener("click", (e) => {
    for (const details of document.querySelectorAll("details.dropdown[open]")) {
      if (!details.contains(e.target)) details.open = false;
    }
  });
}

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
