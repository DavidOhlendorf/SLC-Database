// accordion_auto_open.js
// Öffnet Accordion-Items, wenn das referenzierte Feld gefüllt ist.
// Aktiviert über: .accordion-item[data-acc-open-when-filled="field_name"]

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

  function openAccordionItem(item) {
    const collapse = item.querySelector(".accordion-collapse");
    const button = item.querySelector(".accordion-button");
    if (!collapse || !button) return;

    if (!collapse.classList.contains("show")) {
      collapse.classList.add("show");
      button.classList.remove("collapsed");
      button.setAttribute("aria-expanded", "true");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document
      .querySelectorAll(".accordion-item[data-acc-open-when-filled]")
      .forEach((item) => {
        const fieldName = item.dataset.accOpenWhenFilled;
        if (!fieldName) return;

        const field =
          item.querySelector(`#id_${CSS.escape(fieldName)}`) ||
          item.querySelector(`[name="${CSS.escape(fieldName)}"]`);

        if (!field) return;

        if (isFilled(field)) {
          openAccordionItem(item);
        }
      });
  });
})();
