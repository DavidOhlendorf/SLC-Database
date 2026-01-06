document.addEventListener("DOMContentLoaded", function () {

  function initVariableTomSelect(selectEl) {
    if (!selectEl) return;
    if (selectEl.tomselect) return;

    const wrapper = selectEl.closest(".variable-widget");
    if (!wrapper) return;

    const searchUrl = wrapper.dataset.searchUrl;
    if (!searchUrl) return;

    new TomSelect(selectEl, {
      maxItems: 1,
      create: false,
      persist: false,

      // wichtig für "Input"-Gefühl
      placeholder: "Variable suchen…",
      openOnFocus: true,
      closeAfterSelect: true,

      valueField: "value",
      labelField: "text",
      searchField: ["text"],

      shouldLoad: function (query) {
        return (query || "").trim().length >= 2;
      },

      load: function (query, callback) {
        query = (query || "").trim();
        if (query.length < 2) return callback();

        fetch(`${searchUrl}?q=${encodeURIComponent(query)}`)
          .then(r => r.json())
          .then(items => callback(items))
          .catch(() => callback());
      },
    });

  }

  function initAll() {
    document.querySelectorAll(".variable-widget select").forEach(initVariableTomSelect);
  }

  // initial
  initAll();

  // wenn neue Formset-Zeile hinzugefügt wird: nach dem Append initialisieren
  const addBtn = document.getElementById("vfs-add");
  if (addBtn) {
    addBtn.addEventListener("click", () => {
      // Formset-JS hängt die Zeile synchron an, daher reicht setTimeout(0)
      setTimeout(initAll, 0);
    });
  }
});
