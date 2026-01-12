// static/js/builder/variable_varname_livecheck.js

(function () {
  const input = document.getElementById("id_varname");
  if (!input) return;

  const statusEl = document.getElementById("varname-status");
  const suggEl = document.getElementById("varname-suggestions");

  const checkUrl = input.dataset.checkUrl;
  const initialValue = (input.dataset.initialValue || "").toLowerCase();

  let timer = null;

  function setStatus(html) {
    if (statusEl) statusEl.innerHTML = html || "";
  }

  function clearSuggestions() {
    if (!suggEl) return;
    suggEl.innerHTML = "";
    suggEl.classList.add("d-none");
  }

  function renderSuggestions(items) {
    if (!suggEl || !items || !items.length) {
      clearSuggestions();
      return;
    }

    const rows = items.map(v => `<div class="qc-sugg-row">${v}</div>`).join("");

    suggEl.innerHTML =
      `<div class="qc-sugg-header">Ähnliche, vorhandene Variablen:</div>` +
      `<div class="qc-sugg-box p-2 small">${rows}</div>`;

    suggEl.classList.remove("d-none");
  }


  async function runCheck() {
    const q = (input.value || "").trim();
    const qLower = q.toLowerCase();

    if (q.length < 2) {
      setStatus("");
      clearSuggestions();
      return;
    }

    // Beim Edit: unveränderter Name → kein "belegt"
    if (qLower === initialValue) {
      setStatus("<span class='text-success small'>Unverändert.</span>");
      clearSuggestions();
      return;
    }

    try {
      const res = await fetch(`${checkUrl}?q=${encodeURIComponent(q)}`);
      const data = await res.json();

      if (!data || !data.is_valid_length) {
        setStatus("");
        clearSuggestions();
        return;
      }

      if (data.exists_exact) {
        setStatus("<span class='text-danger small'>Name ist bereits vergeben.</span>");
      } else {
        setStatus("<span class='text-success small'>Name verfügbar.</span>");
      }

      renderSuggestions(data.suggestions || []);
    } catch (e) {
      setStatus("<span class='text-warning small'>Live-Prüfung nicht verfügbar.</span>");
      clearSuggestions();
    }
  }

  input.addEventListener("input", () => {
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(runCheck, 250);
  });
})();
