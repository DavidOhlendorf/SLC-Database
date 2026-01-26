// static/js/builder/question_detail_variable_quickcreate.js
// JS für die Schnellerstellung von Variablen aus der Question-Detail-Page heraus

(function () {

  function getCSRFToken() {
    return document.getElementById("qcq-csrf")?.value || "";
  }


  const modalEl = document.getElementById("qcVarForQuestionModal");
  if (!modalEl || typeof bootstrap === "undefined") return;

  const modal = new bootstrap.Modal(modalEl);

  const inputName = document.getElementById("qcq-varname");
  const errBox = document.getElementById("qcq-error");
  const statusEl = document.getElementById("qcq-name-status");
  const suggEl = document.getElementById("qcq-suggestions");

  const btnLater = document.getElementById("qcq-later");
  const btnComplete = document.getElementById("qcq-complete");

  const checkUrl = modalEl.dataset.varnameCheckUrl;
  const createUrl = modalEl.dataset.createUrl;
  const questionId = modalEl.dataset.questionId;

  let checkTimer = null;

  function showError(msg) {
    errBox.textContent = msg;
    errBox.classList.remove("d-none");
  }
  function clearError() {
    errBox.textContent = "";
    errBox.classList.add("d-none");
  }
  function setStatus(html) { statusEl.innerHTML = html || ""; }
  
  function clearSuggestions() { suggEl.innerHTML = ""; suggEl.classList.add("d-none"); }

  function renderSuggestions(items) {
    if (!items || !items.length) return clearSuggestions();

    const rows = items.map(v => `<div class="qc-sugg-row">${v}</div>`).join("");

    suggEl.innerHTML =
      `<div class="qc-sugg-header">Ähnliche, vorhandene Variablen:</div>` +
      `<div class="qc-sugg-box p-2 small">${rows}</div>`;

    suggEl.classList.remove("d-none");
  }


  async function runVarnameCheck() {
    if (!checkUrl) return;
    const q = (inputName.value || "").trim();
    if (q.length < 2) { setStatus(""); clearSuggestions(); return; }

    try {
      const res = await fetch(`${checkUrl}?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!data || !data.is_valid_length) { setStatus(""); clearSuggestions(); return; }

      if (data.exists_exact) setStatus(`<div class="form-text text-danger">Name ist bereits vergeben.</div>`);
      else setStatus(`<div class="form-text text-success">Name verfügbar.</div>`);

      renderSuggestions(data.suggestions || []);
    } catch {
      setStatus(`<div class="form-text text-warning">Live-Prüfung nicht verfügbar.</div>`);
      clearSuggestions();
    }
  }

  function selectedWaveIds() {
    return Array.from(modalEl.querySelectorAll('#qcq-waves input[name="wave_ids"]:checked'))
      .map(cb => cb.value);
  }

  async function submit(mode) {
    clearError();
    const varname = (inputName.value || "").trim();
    const waves = selectedWaveIds();

    if (varname.length < 2) return showError("Mindestens 2 Zeichen.");
    if (!waves.length) return showError("Bitte wähle mindestens eine Befragungsgruppe aus.");

    btnLater.disabled = true;
    btnComplete.disabled = true;

    try {
      const fd = new FormData();
      fd.append("varname", varname);
      fd.append("question_id", questionId);
      fd.append("mode", mode);
      waves.forEach(w => fd.append("wave_ids", w));

      const res = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        body: fd,
        headers: { "X-CSRFToken": getCSRFToken() },
      });

      const data = await res.json();
      if (!res.ok || !data.ok) {
        showError(data.error || "Fehler beim Anlegen.");
        return;
      }

      window.location.href = data.redirect_url;
    } catch {
      showError("Netzwerkfehler beim Anlegen.");
    } finally {
      btnLater.disabled = false;
      btnComplete.disabled = false;
    }
  }

  inputName?.addEventListener("input", () => {
    clearError();
    if (checkTimer) clearTimeout(checkTimer);
    checkTimer = setTimeout(runVarnameCheck, 250);
  });

  btnLater?.addEventListener("click", () => submit("later"));
  btnComplete?.addEventListener("click", () => submit("complete"));

  modalEl.addEventListener("hidden.bs.modal", () => {
    clearError();
    setStatus("");
    clearSuggestions();
    inputName.value = "";
  });
})();
