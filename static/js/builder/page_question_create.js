// JavaScript für das Anlegen von Fragen via Modal in der Seiten-Bearbeitung

(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }

  const modalEl = document.getElementById("qcModal");
  if (!modalEl) return;

  const qcMode = document.getElementById("qcMode")?.value || "ajax";
  if (qcMode !== "ajax") return;

  const qcPostUrl = document.getElementById("qcPostUrl").value;
  const qcTargetSelectId = document.getElementById("qcTargetSelectId");
  const qcError = document.getElementById("qcError");
  const qcQuestiontext = document.getElementById("qcQuestiontext");
  const qcSubmit = document.getElementById("qcSubmit");

  const bsModal = new bootstrap.Modal(modalEl);

  function showError(msg) {
    qcError.textContent = msg;
    qcError.classList.remove("d-none");
  }
  function clearError() {
    qcError.classList.add("d-none");
    qcError.textContent = "";
  }

  // Öffnen: merken, welches Select in der Zeile betroffen ist
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".qc-open");
    if (!btn) return;

    clearError();
    qcQuestiontext.value = "";

    // Waves vorauswählen:
    modalEl.querySelectorAll("input.qc-wave").forEach(cb => cb.checked = false);

    const row = btn.closest(".qfs-form");
    const select = row ? row.querySelector("select") : null;
    if (!select || !select.id) {
      showError("Konnte das Zielfeld (Frage-Auswahl) nicht finden.");
      return;
    }
    qcTargetSelectId.value = select.id;

    bsModal.show();
  });

  qcSubmit.addEventListener("click", async () => {
    clearError();

    const text = (qcQuestiontext.value || "").trim();
    const waveIds = Array.from(modalEl.querySelectorAll("input.qc-wave:checked")).map(x => x.value);

    if (!text) return showError("Bitte gib einen Fragetext ein.");
    if (waveIds.length === 0) return showError("Bitte wähle mindestens eine Befragtengruppe aus.");

    const fd = new FormData();
    fd.append("questiontext", text);
    waveIds.forEach(w => fd.append("wave_ids", w));

    try {
      const resp = await fetch(qcPostUrl, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
        body: fd,
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        return showError(data.error || "Fehler beim Anlegen der Frage.");
      }

      const targetId = qcTargetSelectId.value;
      const targetSelect = document.getElementById(targetId);
      if (!targetSelect) {
        return showError("Zielfeld nach dem Anlegen nicht gefunden.");
      }

      // Option ins Select einfügen (falls noch nicht vorhanden)
      const qid = String(data.question.id);
      const label = data.question.label || ("Frage #" + qid);

      let opt = targetSelect.querySelector(`option[value="${CSS.escape(qid)}"]`);
      if (!opt) {
        opt = document.createElement("option");
        opt.value = qid;
        opt.textContent = label;
        targetSelect.appendChild(opt);
      }

      targetSelect.value = qid;
      const row = targetSelect.closest(".qfs-form");
        if (row) {
            const waveSet = new Set(waveIds.map(String));
            row.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = waveSet.has(String(cb.value));
            });
        }
      targetSelect.dispatchEvent(new Event("change", { bubbles: true }));

      bsModal.hide();

    } catch (e) {
      showError("Netzwerkfehler beim Anlegen der Frage.");
    }
  });
})();
