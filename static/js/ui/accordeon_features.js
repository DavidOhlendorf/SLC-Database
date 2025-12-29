// Erweiterte Akkordeon-Funktionen für Pflichtfelder und automatische Öffnung

// Helper: Prüfen, ob ein Feld ausgefüllt ist
function isFilled(el) {
  if (!el) return false;

  if (el.type === "checkbox" || el.type === "radio") {
    return el.checked;
  }
  if (el.tagName === "SELECT") {
    return !!el.value && el.value !== "";
  }
  return !!el.value && el.value.trim() !== "";
}

// Helper: Badge für Pflichtfelder updaten
function updateRequiredBadge(badge, filled) {
  badge.innerHTML = filled
    ? '<i class="fa-solid fa-circle-check" style="color: #198754"></i>'
    : '<i class="fa-solid fa-circle-exclamation" style="color: #cc0617ff;"></i>';

  badge.title = filled
    ? "Pflichtfeld ausgefüllt"
    : "Pflichtfeld fehlt";
}

// Automatisches Öffnen von Akkordeons bei gefüllten Feldern
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".accordion-item[data-acc-open-when-filled]")
    .forEach((item) => {
      const fieldName = item.dataset.accOpenWhenFilled;
      const field =
        item.querySelector(`#id_${CSS.escape(fieldName)}`) ||
        item.querySelector(`[name="${CSS.escape(fieldName)}"]`);

      if (!field) return;

      const filled = isFilled(field);
      if (filled) {
        const collapse = item.querySelector(".accordion-collapse");
        const button = item.querySelector(".accordion-button");
        if (collapse && button && !collapse.classList.contains("show")) {
          collapse.classList.add("show");
          button.classList.remove("collapsed");
          button.setAttribute("aria-expanded", "true");
        }
      }
    });
});

// Badges für Pflichtfelder initialisieren
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".accordion-item[data-acc-required-field]")
    .forEach((item) => {
      const fieldName = item.dataset.accRequiredField;
      const field =
        item.querySelector(`#id_${CSS.escape(fieldName)}`) ||
        item.querySelector(`[name="${CSS.escape(fieldName)}"]`);

      if (!field) return;

      const badge = item.querySelector("[data-required-badge]");
      if (!badge) return; 

      updateRequiredBadge(badge, isFilled(field));
    });
});


// Badges für Pflichtfelder bei Eingaben aktualisieren
document.addEventListener("input", (e) => {
  const field = e.target;

  const item = field.closest(".accordion-item[data-acc-required-field]");
  if (!item) return;

  const fieldName = item.dataset.accRequiredField;
  if (field.name !== fieldName && field.id !== `id_${fieldName}`) return;

  const badge = item.querySelector("[data-required-badge]");
  if (!badge) return;

  updateRequiredBadge(badge, isFilled(field));
});
