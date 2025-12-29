// required_badge.js
// Zeigt für Pflichtfelder einen Status-Badge an (leer = rot, gefüllt = grün).
// Aktiviert über: [data-required-field="field_name"] und darin [data-required-badge]

(function () {
  "use strict";

  function isFilled(el) {
    if (!el || el.disabled) return false;

    if (el.type === "checkbox" || el.type === "radio") {
      return el.checked;
    }
    if (el.tagName === "SELECT") {
      return el.value !== "";
    }
    return !!el.value && el.value.trim() !== "";
  }

  function updateRequiredBadge(badge, filled) {
    badge.innerHTML = filled
      ? '<i class="fa-solid fa-circle-check text-success"></i>'
      : '<i class="fa-solid fa-circle-exclamation text-danger"></i>';

    badge.title = filled ? "Pflichtfeld ausgefüllt" : "Pflichtfeld fehlt";
  }

  function findField(container, fieldName) {
    return (
      container.querySelector(`#id_${CSS.escape(fieldName)}`) ||
      container.querySelector(`[name="${CSS.escape(fieldName)}"]`)
    );
  }

  function refreshContainer(container) {
    const fieldName = container.dataset.requiredField;
    if (!fieldName) return;

    const field = findField(container, fieldName);
    const badge = container.querySelector("[data-required-badge]");
    if (!field || !badge) return;

    updateRequiredBadge(badge, isFilled(field));
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-required-field]").forEach(refreshContainer);
  });

  document.addEventListener("input", (e) => {
    const field = e.target;

    const container = field.closest("[data-required-field]");
    if (!container) return;

    const fieldName = container.dataset.requiredField;
    if (!fieldName) return;

    // nur reagieren, wenn es wirklich das referenzierte Feld ist
    const matches =
      field.id === `id_${fieldName}` || field.name === fieldName;
    if (!matches) return;

    refreshContainer(container);
  });
})();
