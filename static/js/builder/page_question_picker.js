// JavaScript: Frage-Picker (Suche) -> übernimmt Auswahl ins Select im Formset

(function () {
  const modalEl = document.getElementById("qpModal");
  if (!modalEl) return;

  const qpError = document.getElementById("qpError");
  const qpResults = document.getElementById("qpResults");
  const qpQuery = document.getElementById("qpQuery");
  const qpApply = document.getElementById("qpApply");
  const qpMeta = document.getElementById("qpMeta");

  const qpTargetSelectId = document.getElementById("qpTargetSelectId");
  const qpSearchUrl = document.getElementById("qpSearchUrl");

  const bsModal = new bootstrap.Modal(modalEl);

  let selectedQuestionId = null;
  let selectedLabel = null;
  let lastFetchToken = 0;

  function showError(msg) {
    qpError.textContent = msg;
    qpError.classList.remove("d-none");
  }
  function clearError() {
    qpError.classList.add("d-none");
    qpError.textContent = "";
  }

  function resetState() {
    clearError();
    qpQuery.value = "";
    qpMeta.textContent = "";
    qpResults.innerHTML = `<div class="text-muted small">Bitte tippen, um Ergebnisse zu sehen.</div>`;
    qpApply.disabled = true;
    selectedQuestionId = null;
    selectedLabel = null;
  }

  function renderResults(results) {
    if (!results || results.length === 0) {
      qpResults.innerHTML = `<div class="text-muted small">Keine Treffer.</div>`;
      return;
    }

    qpResults.innerHTML = results.map((r) => {
      const id = String(r.id);
      const label = (r.label || "").trim();
      const safeLabel = label.replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      const detailTemplate = modalEl.getAttribute("data-detail-template") || "";

      function detailUrlFor(id) {
        // ersetzt die letzte "/0/" durch "/<id>/"
        return detailTemplate.replace(/\/0\/?$/, `/${id}/`);
      }

      const detailUrl = detailTemplate ? detailUrlFor(id) : null;

      return `
        <label class="list-group-item d-flex gap-2 align-items-start">
          <input class="form-check-input mt-1 qp-radio" type="radio" name="qpPick" value="${id}">
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between align-items-start">
              <div class="fw-semibold">#${id}</div>
              ${detailUrl ? `
                <a class="btn btn-sm"
                  href="${detailUrl}"
                  target="_blank"
                  rel="noopener"
                  title="Detailansicht in neuem Tab öffnen">
                  <i class="fa-regular fa-eye"></i>
                </a>
              ` : ""}
            </div>
            <div class="text-muted small">${safeLabel}</div>
          </div>
        </label>
      `;
    }).join("");

    // Radio-Handler
    qpResults.querySelectorAll(".qp-radio").forEach((el) => {
      el.addEventListener("change", () => {
        selectedQuestionId = el.value;
        const row = el.closest(".list-group-item");
        selectedLabel = row ? row.querySelector(".text-muted")?.textContent : ("Frage #" + selectedQuestionId);
        qpApply.disabled = !selectedQuestionId;
      });
    });
  }

  async function runSearch() {
    const q = (qpQuery.value || "").trim();
    selectedQuestionId = null;
    selectedLabel = null;
    qpApply.disabled = true;

    if (q.length < 2) {
      qpMeta.textContent = "";
      qpResults.innerHTML = `<div class="text-muted small">Mindestens 2 Zeichen eingeben.</div>`;
      return;
    }

    const token = ++lastFetchToken;

    const url = new URL(qpSearchUrl.value, window.location.origin);
    url.searchParams.set("q", q);


    qpMeta.textContent = "Suche…";
    try {
      const resp = await fetch(url.toString(), { method: "GET" });
      const data = await resp.json().catch(() => ({}));

      // falls währenddessen neu gesucht wurde
      if (token !== lastFetchToken) return;

        if (!resp.ok || !data.ok) {
        qpMeta.textContent = "";
        if (data && data.error) return showError(data.error);

        const txt = await resp.text().catch(() => "");
        return showError(`Fehler bei der Suche (HTTP ${resp.status}). ${txt.slice(0, 120)}`);
        }


      const results = data.results || [];
      qpMeta.textContent = `${results.length} Treffer`;
      renderResults(results);

    } catch (e) {
      if (token !== lastFetchToken) return;
      qpMeta.textContent = "";
      showError("Netzwerkfehler bei der Suche.");
    }
  }

  // Öffnen des Pickers: merken, welches Select betroffen ist + Parameter übernehmen
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".qc-search");
    if (!btn) return;

    resetState();

    const row = btn.closest(".qfs-form");
    const select = row ? row.querySelector("select") : null;
    if (!select || !select.id) {
      showError("Konnte das Zielfeld (Frage-Auswahl) nicht finden.");
      return;
    }

    qpTargetSelectId.value = select.id;

    const searchUrl = btn.getAttribute("data-search-url") || "";
    if (!searchUrl) {
      showError("Search-URL fehlt am Button (data-search-url).");
      return;
    }
    qpSearchUrl.value = searchUrl;

    bsModal.show();
    setTimeout(() => qpQuery.focus(), 150);
  });

  // Debounce beim Tippen
  let debounceTimer = null;
  qpQuery.addEventListener("input", () => {
    clearError();
    if (debounceTimer) window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(runSearch, 250);
  });

  // Übernehmen: Option ins Select einfügen/selektieren 
  qpApply.addEventListener("click", () => {
    if (!selectedQuestionId) return;

    const targetId = qpTargetSelectId.value;
    const targetSelect = document.getElementById(targetId);
    if (!targetSelect) {
      showError("Zielfeld nach Auswahl nicht gefunden.");
      return;
    }

    const qid = String(selectedQuestionId);
    const label = (selectedLabel || ("Frage #" + qid)).trim();

    let opt = targetSelect.querySelector(`option[value="${CSS.escape(qid)}"]`);
    if (!opt) {
      opt = document.createElement("option");
      opt.value = qid;
      opt.textContent = label;
      targetSelect.appendChild(opt);
    }

    targetSelect.value = qid;
    targetSelect.dispatchEvent(new Event("change", { bubbles: true }));

    bsModal.hide();
  });

})();
