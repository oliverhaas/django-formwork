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
