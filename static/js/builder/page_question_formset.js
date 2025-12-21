document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("qfs-container");
  const addBtn = document.getElementById("qfs-add");
  const tpl = document.getElementById("qfs-empty-form-template");

  if (!container || !addBtn || !tpl) return;

  const prefix = container.dataset.formsetPrefix || "qfs";
  const totalFormsInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);

  function updateTotalForms(newCount) {
    if (totalFormsInput) totalFormsInput.value = String(newCount);
  }

  function currentFormCount() {
    return totalFormsInput ? parseInt(totalFormsInput.value, 10) : container.querySelectorAll(".qfs-form").length;
  }

  function handleRemove(btn) {
    const formEl = btn.closest(".qfs-form");
    if (!formEl) return;

    // Für bestehende Forms: DELETE anhaken, dann nur ausblenden
    const deleteInput = formEl.querySelector(`input[name^="${prefix}-"][name$="-DELETE"]`);
    if (deleteInput) {
      deleteInput.checked = true;
      formEl.style.display = "none";
      return;
    }

    // Fallback: wenn kein DELETE Feld vorhanden wäre (sollte nicht passieren)
    formEl.remove();
  }

  // Remove-Handler für existierende Zeilen
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".qfs-remove");
    if (!btn) return;
    handleRemove(btn);
  });

  // Add new form
  addBtn.addEventListener("click", () => {
    const index = currentFormCount();

    // Template klonen
    const fragment = tpl.content.cloneNode(true);

    // __prefix__ ersetzen in allen name/id/for Attributen
    fragment.querySelectorAll("[name], [id], label[for]").forEach((el) => {
      if (el.name) el.name = el.name.replaceAll("__prefix__", String(index));
      if (el.id) el.id = el.id.replaceAll("__prefix__", String(index));
      if (el.getAttribute && el.getAttribute("for")) {
        el.setAttribute("for", el.getAttribute("for").replaceAll("__prefix__", String(index)));
      }
    });

    container.appendChild(fragment);
    updateTotalForms(index + 1);

    // Optional: Scroll zum neuen Element
    const forms = container.querySelectorAll(".qfs-form");
    const last = forms[forms.length - 1];
    if (last) last.scrollIntoView({ behavior: "smooth", block: "center" });
  });


    // Synchronisation der Befragtengruppen-Checkboxen
    // Oben: Checkboxen aus WavePageForm (name="waves")
    const pageWaveInputs = Array.from(document.querySelectorAll('input[name="waves"]'));
    if (!pageWaveInputs.length) return;

    // Unten: Checkboxen aus Question-Formset (name="qfs-0-waves", "qfs-1-waves", ...)
    function syncQuestionWaveOptions() {
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

    // Initial einmal ausführen  bei bereits geladenen Pages)
    syncQuestionWaveOptions();

    // Bei Änderung im Hauptformular neu synchronisieren
    pageWaveInputs.forEach(inp => inp.addEventListener("change", syncQuestionWaveOptions));

    // Wenn per JS neue Frage-Zeilen hinzugefügt werden, neu synchronisieren

    if (addBtn) addBtn.addEventListener("click", () => setTimeout(syncQuestionWaveOptions, 0));




    // Falls es Fehler im Formset gibt, zum Formset scrollen
    const hasErrors = document.getElementById("qfs-has-errors");
    if (hasErrors) {
        const target = document.getElementById("questions");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }


});
