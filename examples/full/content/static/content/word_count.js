// Counts the words of a post's body while it is typed, with the minutes it
// takes to read. The admin moves between pages with htmx and does not run a
// page's scripts again, so this listens on the document and looks for the
// field after each swap.
(() => {
  const FIELD = "#post_form textarea[name=body]";
  const WORDS_PER_MINUTE = 230;

  const counter = (textarea) => {
    let el = textarea.nextElementSibling;
    if (!el?.classList.contains("word-count")) {
      el = document.createElement("p");
      el.className = "word-count";
      el.setAttribute("aria-live", "polite");
      textarea.after(el);
    }
    return el;
  };

  const update = (textarea) => {
    const words = textarea.value.split(/\s+/).filter(Boolean).length;
    const minutes = Math.max(1, Math.round(words / WORDS_PER_MINUTE));
    counter(textarea).textContent =
      words === 0 ? "0 words" : `${words} ${words === 1 ? "word" : "words"}, about ${minutes} min to read`;
  };

  const scan = () => document.querySelectorAll(FIELD).forEach(update);

  document.addEventListener("input", (event) => {
    if (event.target.matches?.(FIELD)) update(event.target);
  });
  document.addEventListener("DOMContentLoaded", scan);
  document.addEventListener("htmx:after:swap", scan);
})();
