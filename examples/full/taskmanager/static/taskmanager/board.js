// Drag a card onto another column to move it. The drop fills the hidden
// #board-move form, and htmx posts it and morphs the board from the response.

const COLUMN = "[data-column]";
let dragged = null;

const leaveAll = () => {
  for (const column of document.querySelectorAll(`${COLUMN}[data-over]`)) column.removeAttribute("data-over");
};

const target = (event) => (dragged ? event.target.closest?.(COLUMN) : null);

document.addEventListener("dragstart", (event) => {
  dragged = event.target.closest?.("[data-card]") ?? null;
  if (!dragged) return;
  dragged.dataset.dragging = "";
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", dragged.dataset.card);
});

document.addEventListener("dragend", () => {
  dragged?.removeAttribute("data-dragging");
  dragged = null;
  leaveAll();
});

document.addEventListener("dragover", (event) => {
  const column = target(event);
  if (!column) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  if (column.hasAttribute("data-over")) return;
  leaveAll();
  column.dataset.over = "";
});

document.addEventListener("dragleave", (event) => {
  const column = target(event);
  if (column && !column.contains(event.relatedTarget)) column.removeAttribute("data-over");
});

document.addEventListener("drop", (event) => {
  const column = target(event);
  if (!column) return;
  event.preventDefault();
  leaveAll();
  if (dragged.closest(COLUMN) === column) return;
  const form = document.getElementById("board-move");
  form.elements.task.value = dragged.dataset.card;
  form.elements.status.value = column.dataset.column;
  // Show the card in its new column right away; the response puts it in order.
  column.querySelector("[data-cards]").prepend(dragged);
  form.requestSubmit();
});
