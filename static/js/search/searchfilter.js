// --- SLC/static/js/searchfilter.js ---
// JavaScript für die Wellen-Facette im Suchfilter von search.html

(function () {
  function run() {
    const form     = document.getElementById('filter-form');
    const panel    = document.getElementById('wave-panel');
    const openBtn  = document.getElementById('btn-open-wave-panel');
    const closeBtn = document.getElementById('btn-close-wave-panel');

    const facetList = document.getElementById('facet-list');
    const allList   = document.getElementById('all-list');

    if (!form || !panel) return; // Seite ohne Filter – sauber aussteigen

    // Sichtbare Panel-Checkboxen mit versteckten Inputs synchronisieren
    function wirePanelChecks() {
      document.querySelectorAll('#wave-list .wave-check').forEach(chk => {
        chk.onchange = () => {
          const hidden = document.getElementById('wave-' + chk.value);
          if (hidden) hidden.checked = chk.checked;
        };
      });
    }
    wirePanelChecks();

    // Panel öffnen / schließen
    if (openBtn)  openBtn.addEventListener('click', () => { panel.style.display = 'block'; });
    if (closeBtn) closeBtn.addEventListener('click', () => { panel.style.display = 'none';  });

    // Zurücksetzen
    const resetBtn = document.getElementById('btn-clear-waves');
    if (resetBtn) resetBtn.addEventListener('click', () => {
      document.querySelectorAll('#wave-list .wave-check').forEach(c => c.checked = false);
      document.querySelectorAll('input[type="checkbox"][name="waves"]').forEach(h => h.checked = false);
      form.submit();
    });

    // Chips (×) entfernen
    document.querySelectorAll('.remove-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.waveId;
        const hidden = document.getElementById('wave-' + id);
        if (hidden) hidden.checked = false;
        document.querySelectorAll('#wave-list .wave-check[value="' + id + '"]').forEach(c => c.checked = false);
        form.submit();
      });
    });

    // Umschalten Treffer <-> Alle
    const btnToggle = document.getElementById('btn-show-all-waves');
    if (btnToggle && allList) {
      btnToggle.addEventListener('click', () => {
        const showingAll = allList.style.display !== 'none';
        if (showingAll) {
          allList.style.display = 'none';
          if (facetList) facetList.style.display = '';
          btnToggle.textContent = 'Alle anzeigen';
        } else {
          if (facetList) facetList.style.display = 'none';
          allList.style.display = '';
          btnToggle.textContent = 'Nur Treffer anzeigen';
        }
        wirePanelChecks();
      });
    }
  }

  // Robuster Start: sofort ausführen, oder auf DOMContentLoaded warten
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
