document.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("add-wave");
  const formsDiv = document.getElementById("wave-forms");
  const template = document.getElementById("empty-wave-form");

  if (!formsDiv) return;

  formsDiv.querySelectorAll(".wave-form").forEach(formEl => {
    const delInput = formEl.querySelector('input[name$="-DELETE"]');
    if (delInput && delInput.checked) {
      formEl.classList.add("d-none");
    }
  });

  const prefix = formsDiv.dataset.formsetPrefix || "waves";
  const totalForms = document.getElementById(`id_${prefix}-TOTAL_FORMS`);

  /* ----------------------------------------------------
   * Hilfsfunktion: zählt aktive (nicht gelöschte) Waves
   * ---------------------------------------------------- */
  function countActiveForms() {
    const forms = formsDiv.querySelectorAll(".wave-form");
    let count = 0;

    forms.forEach(formEl => {
      const delInput = formEl.querySelector('input[name$="-DELETE"]');
      const isDeleted = delInput && delInput.checked;
      const isHidden = formEl.classList.contains("d-none");

      if (!isDeleted && !isHidden) {
        count += 1;
      }
    });

    return count;
  }

   /* ----------------------------------------------------
   * Hilfsfunktion: Alerts anzeigen
   * ---------------------------------------------------- */
  function showWaveAlert(message) {
    const alertBox = document.getElementById("wave-alert");
    if (!alertBox) return;

    const textEl = alertBox.querySelector(".js-wave-alert-text");
    if (textEl) textEl.textContent = message;

    alertBox.classList.remove("d-none");
  }


  /* -----------------------
   * Gruppe hinzufügen
   * ----------------------- */
  if (addBtn && template && totalForms) {
    addBtn.addEventListener("click", () => {
      const formIndex = parseInt(totalForms.value, 10);
      const html = template.innerHTML.replaceAll("__prefix__", formIndex);

      formsDiv.insertAdjacentHTML("beforeend", html);
      totalForms.value = formIndex + 1;
    });
  }

  /* -----------------------
   * Gruppe entfernen
   * ----------------------- */
  formsDiv.addEventListener("click", (e) => {
    const removeBtn = e.target.closest(".js-remove-wave");
    if (!removeBtn) return;

    const waveForm = removeBtn.closest(".wave-form");
    if (!waveForm) return;

    // 1) Darf diese Gruppe gelöscht werden?
    if (waveForm.dataset.canDelete === "0") {
      showWaveAlert(
        waveForm.dataset.deleteReason ||
        "Diese Gruppe kann nicht gelöscht werden."
      );
      return;
    }

    // 2) Mindestens eine Gruppe muss bleiben
    if (countActiveForms() <= 1) {
      showWaveAlert("Mindestens eine Gruppe ist erforderlich.");
      return;
    }

    // 3) DELETE-Feld setzen
    const deleteInput = waveForm.querySelector('input[name$="-DELETE"]');
    if (deleteInput) {
      deleteInput.checked = true;
    }

    // 4) Zeile visuell ausblenden
    waveForm.classList.add("d-none");
  });
});
