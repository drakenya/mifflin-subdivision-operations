// Auto-generated ids. A new record's id is shown locked and follows the fields it is derived from
// (asking the server, so the rules and uniqueness checks live in one place). "Edit" unlocks it for typing;
// "Auto" locks it again and regenerates. `id_manual` (0/1) is posted so a re-rendered form keeps the mode.
(function () {
  let latest = 0;   // ignore responses that arrive out of order

  function parts(wrap) {
    return {
      input: wrap.querySelector("#f-id"),
      manual: wrap.querySelector("#f-id_manual"),
      button: wrap.querySelector(".id-toggle"),
      hint: wrap.parentElement.querySelector("[data-id-hint]"),
    };
  }

  async function refresh(wrap) {
    const { input, manual } = parts(wrap);
    if (!wrap.dataset.suggestUrl || !manual || manual.value === "1") return;
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(wrap.closest("form"))) {
      if (typeof value === "string" && key !== "id") params.append(key, value);
    }
    const mine = ++latest;
    try {
      const response = await fetch(wrap.dataset.suggestUrl + "?" + params);
      if (!response.ok || mine !== latest) return;
      const { id } = await response.json();
      if (manual.value !== "1") input.value = id;   // the user may have clicked Edit while we waited
    } catch (_) { /* keep whatever is there */ }
  }

  function setManual(wrap, on) {
    const { input, manual, button, hint } = parts(wrap);
    manual.value = on ? "1" : "0";
    input.readOnly = !on;
    input.classList.toggle("locked", !on);
    button.textContent = on ? "↺ Auto" : "✎ Edit";
    if (hint) hint.textContent = on ? hint.dataset.hintManual : hint.dataset.hintLocked;
    if (on) { input.focus(); input.select(); } else { refresh(wrap); }
  }

  function debounce(fn, ms) {
    let timer;
    return () => { clearTimeout(timer); timer = setTimeout(fn, ms); };
  }

  function initIds(root) {
    root.querySelectorAll("[data-id-field]").forEach((wrap) => {
      const { input, button } = parts(wrap);
      if (button && !button.dataset.bound) {
        button.dataset.bound = "1";
        button.addEventListener("click", () => setManual(wrap, input.readOnly));
      }
      if (input.readOnly && wrap.dataset.suggestUrl && input.value === "") refresh(wrap);
      const form = wrap.closest("form");
      if (form && !form.dataset.idWired) {          // one listener per form: the field block gets swapped by htmx
        form.dataset.idWired = "1";
        const later = debounce(() => {
          const current = form.querySelector("[data-id-field]");
          if (current) refresh(current);
        }, 300);
        const onEdit = (event) => { if (event.target.id !== "f-id") later(); };
        form.addEventListener("input", onEdit);
        form.addEventListener("change", onEdit);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => initIds(document));
  document.addEventListener("htmx:afterSettle", (event) => initIds(event.target));
})();
