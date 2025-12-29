// static/js/builder/item_formset.js
// JavaScript für dynamisches Hinzufügen/Löschen von Items im Formset

function nextUidNumber(prefix, tbody) {
  const re = new RegExp("^" + prefix + "(\\d+)$", "i");
  const used = new Set();

  tbody.querySelectorAll("tr").forEach((row) => {
    // Zeilen, die (per JS) gelöscht wurden, ignorieren
    if (row.classList.contains("d-none")) return;

    // Zeilen, die per DELETE markiert sind, ignorieren
    const del = row.querySelector(`input[name$="-DELETE"]`);
    if (del && del.checked) return;

    const uidInput = row.querySelector(`input[name$="-uid"]`);
    if (!uidInput) return;

    const v = (uidInput.value || "").trim();
    const m = v.match(re);
    if (m) used.add(parseInt(m[1], 10));
  });

  // kleinste freie Nummer suchen: 1,2,3,...
  let n = 1;
  while (used.has(n)) n++;
  return n;
}

document.addEventListener("DOMContentLoaded", () => {
  const prefix = "it";

  const addBtn = document.getElementById("it-add-row");
  const tbody = document.getElementById("it-tbody");
  const tpl = document.getElementById("it-empty-form-template");
  const totalFormsInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);

  function setDelete(row) {
    const delInput = row.querySelector(`input[name^="${prefix}-"][name$="-DELETE"]`);
    if (delInput) delInput.checked = true;

    // optional: UID leeren, damit es visuell "weg" ist
    const uidInput = row.querySelector(`input[name$="-uid"]`);
    if (uidInput) uidInput.value = "";

    row.classList.add("d-none");
  }

  // Delete (Event Delegation)
  tbody.addEventListener("click", (e) => {
    const btn = e.target.closest(".it-delete-row");
    if (!btn) return;

    const row = btn.closest("tr");
    if (!row) return;

    setDelete(row);
  });

  // Add row
  addBtn.addEventListener("click", () => {
    const idx = parseInt(totalFormsInput.value, 10);

    const html = tpl.innerHTML.replaceAll("__prefix__", String(idx));
    tbody.insertAdjacentHTML("beforeend", html);

    const newRow = tbody.lastElementChild;
    if (newRow) {
      const uidInput = newRow.querySelector(`input[name$="-uid"]`);
      if (uidInput && !(uidInput.value || "").trim()) {
        const n = nextUidNumber(prefix, tbody);
        uidInput.value = `${prefix}${n}`;
        uidInput.dispatchEvent(new Event("input", { bubbles: true } ));
      }
    }

    totalFormsInput.value = String(idx + 1);
  });
});
