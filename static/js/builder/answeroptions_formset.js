
// static/js/builder/answeroptions_formset.js
// JavaScript für dynamisches Hinzufügen/Löschen von Antwortoptionen im Formset
document.addEventListener("DOMContentLoaded", () => {
const prefix = "ao";

const addBtn = document.getElementById("ao-add-row");
const tbody = document.getElementById("ao-tbody");
const tpl = document.getElementById("ao-empty-form-template");

const totalFormsInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);

function setDelete(row) {
    const delInput = row.querySelector(`input[name^="${prefix}-"][name$="-DELETE"]`);
    if (delInput) delInput.checked = true;
    row.classList.add("d-none");
}

// Delete (Event Delegation)
tbody.addEventListener("click", (e) => {
    const btn = e.target.closest(".ao-delete-row");
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

    totalFormsInput.value = String(idx + 1);
});
});
