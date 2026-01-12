document.addEventListener("DOMContentLoaded", () => {

  // ---------------------------------
  // LOCKED-WAVES: Init + Confirm on submit
  // ---------------------------------
  const container = document.getElementById("vfs-container");
  const form = container ? container.closest("form") : null;

  // locked IDs aus data-Attribut lesen
  const lockedCsv = (container?.dataset.lockedWaveIds || "").trim();
  const lockedIds = new Set(
    lockedCsv ? lockedCsv.split(",").map(s => s.trim()).filter(Boolean) : []
  );

  function initLockedCheckboxes(rootEl) {
    if (!lockedIds.size) return;

    // rootEl = container oder neu hinzugefügte Zeile
    const scope = rootEl || document;

    const cbs = Array.from(scope.querySelectorAll('input[type="checkbox"]'))
      .filter(cb => lockedIds.has(cb.value));

    cbs.forEach(cb => {
      // nicht doppelt initialisieren
      if (cb.dataset.lockedInitDone === "1") return;
      cb.dataset.lockedInitDone = "1";

      // initial state merken
      cb.dataset.initialChecked = cb.checked ? "1" : "0";

      // Label markieren (fallback: nächstes Label suchen)
      const label = document.querySelector(`label[for="${cb.id}"]`);
      if (label) {
        label.classList.add("text-body-tertiary");
        label.title = "Abgeschlossene Befragung";
      }
    });
  }

  // initial: bestehende Checkboxen markieren
  if (container) initLockedCheckboxes(container);

  // confirm beim Speichern nur wenn locked geändert wurde
  let bypassLockedConfirm = false;

  if (form && lockedIds.size) {
    form.addEventListener("submit", (e) => {
      if (bypassLockedConfirm) return;

      const lockedCbs = Array.from(form.querySelectorAll('input[type="checkbox"]'))
        .filter(cb => cb.dataset.lockedInitDone === "1");

      const changedLocked = lockedCbs.some(cb => {
        const initial = cb.dataset.initialChecked === "1";
        return cb.checked !== initial;
      });

      if (!changedLocked) return;

      // Submit stoppen und Modal zeigen
      e.preventDefault();
      e.stopPropagation();

      const modalEl = document.getElementById("confirmLockedWavesModal");
      const yesBtn = document.getElementById("confirmLockedWavesYes");
      if (!modalEl || !yesBtn) return;

      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

      // Click nur einmal binden
      if (!yesBtn.dataset.bound) {
        yesBtn.dataset.bound = "1";
        yesBtn.addEventListener("click", () => {
          modal.hide();
          bypassLockedConfirm = true;
          form.requestSubmit();
        });
      }

      modal.show();
    }, true);
  }

  // ---------------------------------
  // A) Formset: Add/Remove von Zeilen
  // ---------------------------------
  const addBtn = document.getElementById("vfs-add");
  const tpl = document.getElementById("vfs-empty-form-template");

  if (container && addBtn && tpl) {
    const prefix = container.dataset.formsetPrefix || "vfs";
    const totalFormsInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);

    function updateTotalForms(newCount) {
      if (totalFormsInput) totalFormsInput.value = String(newCount);
    }

    function currentFormCount() {
      return totalFormsInput
        ? parseInt(totalFormsInput.value, 10)
        : container.querySelectorAll(".vfs-form").length;
    }

    function handleRemove(btn) {
      const formEl = btn.closest(".vfs-form");
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
      const btn = e.target.closest(".vfs-remove");
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

      const forms = container.querySelectorAll(".vfs-form");
      const last = forms[forms.length - 1];
      if (last) {
        // locked-checkboxes initialisieren
        initLockedCheckboxes(last);
        last.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  // ---------------------------------
  // B) Falls es Fehler gibt, zum Formset scrollen
  // ---------------------------------
  const hasErrors = document.getElementById("vfs-has-errors");
  if (hasErrors && container) {
    container.scrollIntoView({ behavior: "smooth", block: "start" });
  }

});
