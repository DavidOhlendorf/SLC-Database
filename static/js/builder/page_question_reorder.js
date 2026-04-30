document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("qfs-container");
  if (!container || typeof Sortable === "undefined") return;

  function updateSortOrderFields() {
    const forms = container.querySelectorAll(".qfs-form");

    let position = 1;

    forms.forEach((formEl) => {
      const deleteInput = formEl.querySelector('input[name$="-DELETE"]');
      const isDeleted = deleteInput && deleteInput.checked;
      const sortInput = formEl.querySelector('input[name$="-sort_order"]');

      if (!sortInput) return;

      if (isDeleted || formEl.classList.contains("d-none")) {
        sortInput.value = "";
        return;
      }

      sortInput.value = position;
      position += 1;
    });
  }

  Sortable.create(container, {
    animation: 150,
    handle: ".js-qfs-drag-handle",
    draggable: ".qfs-form",
    ghostClass: "opacity-50",
    onEnd: updateSortOrderFields,
  });

  updateSortOrderFields();

  container.addEventListener("qfs:changed", updateSortOrderFields);
});