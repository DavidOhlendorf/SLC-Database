document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("modulesForm");
  if (!form) return; // Modal nicht auf der Seite

  const list = document.getElementById("moduleList");
  const orderInput = document.getElementById("moduleOrder");
  const addBtn = document.getElementById("btnAddModule");
  const tpl = document.getElementById("newModuleRowTpl");

  if (!list || !orderInput || !addBtn || !tpl) return;

  let newCounter = 0;

  function isDeleted(row) {
    // existing rows: hidden checkbox (name=delete_ids) wird gesetzt
    const cb = row.querySelector("input[name='delete_ids']");
    return cb ? cb.checked : false;
  }

  function writeOrder() {
    const keys = Array.from(list.querySelectorAll(".module-row"))
      .filter(r => !isDeleted(r))
      .map(r => r.dataset.key);
    orderInput.value = keys.join(",");
  }

  function moveRow(row, dir) {
    const visible = Array.from(list.querySelectorAll(".module-row")).filter(r => !isDeleted(r));
    const i = visible.indexOf(row);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= visible.length) return;

    if (dir < 0) list.insertBefore(row, visible[j]);
    else list.insertBefore(visible[j], row);

    writeOrder();
  }

  function markDeleted(row) {
    const key = row.dataset.key || "";
    if (key.startsWith("new-")) {
      // neue Zeile: sofort entfernen
      row.remove();
      writeOrder();
      return;
    }

    // bestehend: checkbox setzen und row visuell ausblenden
    const cb = row.querySelector("input[name='delete_ids']");
    if (cb) cb.checked = true;

    row.classList.add("opacity-50");
    row.style.display = "none"; // optional: komplett weg
    writeOrder();
  }

  list.addEventListener("click", (e) => {
    const row = e.target.closest(".module-row");
    if (!row) return;

    if (e.target.closest(".js-up")) moveRow(row, -1);
    if (e.target.closest(".js-down")) moveRow(row, +1);

    if (e.target.closest(".js-trash")) {
      markDeleted(row);
    }
  });

  addBtn.addEventListener("click", () => {
    const key = `new-${newCounter++}`;
    const html = tpl.innerHTML.replaceAll("__KEY__", key);

    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    list.appendChild(wrap.firstElementChild);

    writeOrder();
  });

  writeOrder();
});
