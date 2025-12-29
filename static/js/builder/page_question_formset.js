document.addEventListener("DOMContentLoaded", () => {

  // ---------------------------------
  // A) Formset zu ausgewählten Fragen: Add/Remove von Zeilen
  // ---------------------------------
  const container = document.getElementById("qfs-container");
  const addBtn = document.getElementById("qfs-add");
  const tpl = document.getElementById("qfs-empty-form-template");

  if (container && addBtn && tpl) {
    const prefix = container.dataset.formsetPrefix || "qfs";
    const totalFormsInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);

    function updateTotalForms(newCount) {
      if (totalFormsInput) totalFormsInput.value = String(newCount);
    }

    function currentFormCount() {
      return totalFormsInput
        ? parseInt(totalFormsInput.value, 10)
        : container.querySelectorAll(".qfs-form").length;
    }

    function handleRemove(btn) {
      const formEl = btn.closest(".qfs-form");
      if (!formEl) return;

      const deleteInput = formEl.querySelector(`input[name^="${prefix}-"][name$="-DELETE"]`);
      if (deleteInput) {
        deleteInput.checked = true;
        formEl.style.display = "none";
        return;
      }
      formEl.remove();
    }

    container.addEventListener("click", (e) => {
      const btn = e.target.closest(".qfs-remove");
      if (!btn) return;
      handleRemove(btn);
    });

    addBtn.addEventListener("click", () => {
      const index = currentFormCount();
      const fragment = tpl.content.cloneNode(true);

      fragment.querySelectorAll("[name], [id], label[for]").forEach((el) => {
        if (el.name) el.name = el.name.replaceAll("__prefix__", String(index));
        if (el.id) el.id = el.id.replaceAll("__prefix__", String(index));
        if (el.getAttribute && el.getAttribute("for")) {
          el.setAttribute("for", el.getAttribute("for").replaceAll("__prefix__", String(index)));
        }
      });

      container.appendChild(fragment);
      updateTotalForms(index + 1);

      const forms = container.querySelectorAll(".qfs-form");
      const last = forms[forms.length - 1];
      if (last) last.scrollIntoView({ behavior: "smooth", block: "center" });

      // Nach dem Hinzufügen ggf. Optionen synchronisieren
      setTimeout(syncQuestionWaveOptions, 0);
    });
  }


  // ---------------------------------
  // B) Sync: Ausgewählte Gruppen im Hauptformular -> Ausgewählte Gruppen in den Fragen
  // ---------------------------------
  const pageWaveInputs = Array.from(document.querySelectorAll('input[name="waves"]'));

  function syncQuestionWaveOptions() {
    if (!pageWaveInputs.length) return;

    const allowed = new Set(
      pageWaveInputs.filter(i => i.checked).map(i => String(i.value))
    );

    const qWaveInputs = document.querySelectorAll('input[name^="qfs-"][name$="-waves"]');
    qWaveInputs.forEach(inp => {
      const id = String(inp.value);

      if (!allowed.has(id)) {
        inp.checked = false;
        inp.disabled = true;
      } else {
        inp.disabled = false;
      }
    });
  }

  if (pageWaveInputs.length) {
    syncQuestionWaveOptions();
    pageWaveInputs.forEach(inp => inp.addEventListener("change", syncQuestionWaveOptions));
  }


  // ---------------------------------
  // C) Falls es Fehler im Formset gibt, zum Formset scrollen
  // ---------------------------------
  const hasErrors = document.getElementById("qfs-has-errors");
  if (hasErrors) {
    const target = document.getElementById("questions");
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }


/// ---------------------------------
// D) Basis-Form: Toggle Edit/Save/Cancel
// ---------------------------------
const baseForm = document.getElementById("base-form");
const baseFields = document.getElementById("base-fields");

const editBtn = document.getElementById("base-edit-btn");
const saveBtn = document.getElementById("base-save-btn");
const cancelBtn = document.getElementById("base-cancel-btn");

// Content-Form Lock
const contentForm = document.getElementById("content-form");
const contentSaveBtn = contentForm?.querySelector('button[type="submit"]');

function setContentLocked(locked) {
  if (!contentForm) return;

  // optional: alles sperren (außer z.B. Links)
  contentForm.querySelectorAll("input, select, textarea, button").forEach((el) => {
    el.disabled = locked;
  });

  // rein visuell:
  contentForm.classList.toggle("opacity-75", locked);
  contentForm.classList.toggle("pe-none", locked); // verhindert Klicks auch auf Wrapper-Ebene
}

// Snapshot/Restore für Question-Waves
function snapshotQuestionWaves() {
  const qWaveInputs = Array.from(document.querySelectorAll('input[name^="qfs-"][name$="-waves"]'));
  return qWaveInputs.map((el) => ({
    id: el.id,
    checked: el.checked,
    disabled: el.disabled,
  }));
}

function restoreQuestionWaves(snap) {
  const byId = new Map(snap.map((x) => [x.id, x]));
  const qWaveInputs = Array.from(document.querySelectorAll('input[name^="qfs-"][name$="-waves"]'));

  qWaveInputs.forEach((el) => {
    const s = byId.get(el.id);
    if (!s) return;
    el.checked = !!s.checked;
    el.disabled = !!s.disabled;
  });
}

if (baseForm && baseFields && editBtn && saveBtn && cancelBtn) {
  const baseInputs = Array.from(baseFields.querySelectorAll("input, select, textarea"));

  const setEnabled = (enabled) => {
    baseInputs.forEach((el) => { el.disabled = !enabled; });

    editBtn.classList.toggle("d-none", enabled);
    saveBtn.classList.toggle("d-none", !enabled);
    cancelBtn.classList.toggle("d-none", !enabled);

    // Content während Base-Edit sperren
    setContentLocked(enabled);

  };

  const snapshotBase = () => baseInputs.map((el) => {
    if (el.type === "checkbox" || el.type === "radio") {
      return { id: el.id, type: el.type, checked: el.checked };
    }
    return { id: el.id, type: el.type, value: el.value };
  });

  const restoreBase = (snap) => {
    const byId = new Map(snap.map((x) => [x.id, x]));
    baseInputs.forEach((el) => {
      const s = byId.get(el.id);
      if (!s) return;

      if (el.type === "checkbox" || el.type === "radio") {
        el.checked = !!s.checked;
      } else {
        el.value = s.value ?? "";
      }
    });
  };

  let baseSnap = snapshotBase();
  let qWaveSnap = snapshotQuestionWaves();

  // Start: gesperrt
  setEnabled(false);

  editBtn.addEventListener("click", () => {
    baseSnap = snapshotBase();
    qWaveSnap = snapshotQuestionWaves(); // Zustand unten merken
    setEnabled(true);
  });

  cancelBtn.addEventListener("click", () => {
    restoreBase(baseSnap);
    restoreQuestionWaves(qWaveSnap); // Zustand unten zurücksetzen
    setEnabled(false);
  });
}


});
