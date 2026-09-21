// Searchable pickers (Tom Select) for every <select data-picker>, plus commodity-aware ranking.
function initPickers(root) {
  root.querySelectorAll("select[data-picker]").forEach((el) => {
    if (el.tomselect) return;
    const ts = new TomSelect(el, {
      create: el.dataset.create === "1",
      maxOptions: null,
      plugins: el.multiple ? ["remove_button"] : ["clear_button"],
      searchField: ["text", "meta"],
      lockOptgroupOrder: true,
      render: {
        option: (d, esc) => `<div><span class="n">${esc(d.text)}</span><div class="m">${esc(d.meta || "")}</div></div>`,
        item: (d, esc) => `<div>${esc(d.text)}</div>`,
      },
    });
    if (el.dataset.rankField) wireRanking(el, ts);
  });
}

// Float industries that ship/receive the chosen commodity to the top; never hide the rest.
function wireRanking(el, ts) {
  const source = document.getElementById("f-" + el.dataset.rankField);
  if (!source) return;
  const list = el.dataset.rankList;                       // "ships" or "receives"
  const apply = () => {
    const commodity = source.value;
    const name = commodity && source.selectedOptions[0] ? source.selectedOptions[0].text : "";
    ts.addOptionGroup("match", { label: `${list === "ships" ? "Ships" : "Receives"} ${name}` });
    ts.addOptionGroup("other", { label: "Other industries" });
    Object.keys(ts.options).forEach((key) => {
      const o = ts.options[key];
      const listed = (o[list] || "").split(",").filter(Boolean);
      const group = !commodity ? undefined : listed.includes(commodity) ? "match" : "other";
      ts.updateOption(key, Object.assign({}, o, { optgroup: group }));
    });
    ts.refreshOptions(false);
  };
  source.addEventListener("change", apply);
  apply();
}

document.addEventListener("DOMContentLoaded", () => initPickers(document));
// After the type swap, not before: htmx "settles" swapped elements that share an id with the old
// ones (e.g. originating_railroad_id) by resetting their class, which would un-hide the native select.
document.body.addEventListener("htmx:afterSettle", (e) => initPickers(e.target));
