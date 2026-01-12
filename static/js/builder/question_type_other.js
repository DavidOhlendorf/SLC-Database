// static/js/ui/question_type_other.js

// Zeigt im Builder das Freitextfeld für "Sonstiger Fragetyp" nur an, wenn dieser Fragetyp ausgewählt ist.
(function () {
  "use strict";

  function syncOtherField() {
    const qt = document.getElementById("id_question_type");
    const wrap = document.getElementById("qt-other-wrap");
    const other = document.getElementById("id_question_type_other");
    if (!qt || !wrap || !other) return;

    const isOther = qt.value === "other";

    wrap.classList.toggle("d-none", !isOther);
    other.toggleAttribute("required", isOther);

    // optional: wenn nicht OTHER, Feld leeren (UI-seitig)
    if (!isOther) other.value = "";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const qt = document.getElementById("id_question_type");
    if (!qt) return;

    qt.addEventListener("change", syncOtherField);
    syncOtherField(); // initialer Zustand
  });
})();
