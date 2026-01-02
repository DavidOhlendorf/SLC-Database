document.addEventListener("DOMContentLoaded", () => {

  // ---------------------------------
  // A) Formset: Add/Remove von Zeilen
  // ---------------------------------
  const container = document.getElementById("vfs-container");
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

      // Wenn can_delete=True: DELETE markieren und ausblenden
      const deleteInput = formEl.querySelector(`input[name^="${prefix}-"][name$="-DELETE"]`);
      if (deleteInput) {
        deleteInput.checked = true;
        formEl.style.display = "none";
        return;
      }

      // Fallback: hart entfernen
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
      if (last) last.scrollIntoView({ behavior: "smooth", block: "center" });
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
