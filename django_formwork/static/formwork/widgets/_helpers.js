// Shared helpers for the formwork dropdown Alpine.data components
// (formworkSearchSelect, formworkMultiSelect, formworkComboBox).

export const visibleOptions = (component, selector) =>
  [...component.$refs.options.querySelectorAll(selector)]
    .filter((b) => b.offsetParent !== null);

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

// Base state and behavior shared by every dropdown component.  Each one
// spreads this into its Alpine.data object, then adds its own state, getters,
// and a `confirm()` that acts on `_confirmTarget()`.  `optionSelector` is the
// attribute selector for the navigable option rows ("[data-value]", etc.).
export const dropdownBase = (optionSelector) => ({
  _v: 0,
  hasError: false,
  highlightedEl: null,

  _visibleOptions() {
    return visibleOptions(this, optionSelector);
  },
  _clearHighlight() {
    clearHighlight(this);
  },
  nav(dir) {
    keyboardNav(this, dir, optionSelector);
  },
  // The highlighted option, falling back to the first visible one.  Each
  // component's confirm() picks from whatever this returns on Enter.
  _confirmTarget() {
    let target = this.highlightedEl;
    if (!target || target.offsetParent === null) target = this._visibleOptions()[0];
    return target;
  },
});
