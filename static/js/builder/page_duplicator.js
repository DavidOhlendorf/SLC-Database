// static/js/builder/page_duplicator.js
// JavaScript für die Seiten-Duplikation


(function () {
    const errorEl = document.getElementById("copyPageError");
    const surveySel = document.getElementById("copyTargetSurvey");
    const wavesBox = document.getElementById("copyTargetWavesBox");
    const nameInput = document.getElementById("copyNewName");
    const nameHint = document.getElementById("copyNameHint");

    const includeQ = document.getElementById("copyIncludeQuestions");
    const includeV = document.getElementById("copyIncludeVariables");

    const hiddenPageId = document.getElementById("copySourcePageId");

    const submitBtn = document.getElementById("copySubmitBtn");

    const endpoints = document.getElementById("page-copy-endpoints");

    const modalEl = document.getElementById("copyPageModal");

    // Wenn das Modal nicht auf der Seite ist, nichts tun
    if (!surveySel || !wavesBox || !nameInput || !submitBtn || !endpoints) return;


    function hideModal() {
        if (!modalEl || typeof bootstrap === "undefined") return;
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modal.hide();
        }

        function syncVarCheckboxState() {
        if (!includeQ || !includeV) return;

        if (!includeQ.checked) {
            includeV.checked = false;
            includeV.disabled = true;
        } else {
            includeV.disabled = false;
        }
    }

    if (includeQ) {
        includeQ.addEventListener("change", function () {
            syncVarCheckboxState();
        });
    }



    // --- Endpoints (vom Template per data-attributes)
    const API_SURVEYS_URL = endpoints.dataset.apiSurveysUrl;
    const API_WAVES_TEMPLATE = endpoints.dataset.apiWavesUrlTemplate; 
    const API_CHECK_NAME_URL = endpoints.dataset.apiCheckNameUrl;
    const COPY_URL_TEMPLATE = endpoints.dataset.copyUrlTemplate; 

    let nameOk = true;
    let nameDebounce = null;

    function showError(msg) {
        if (!errorEl) return;
        errorEl.textContent = msg;
        errorEl.classList.remove("d-none");
    }
    
    function clearError() {
        if (!errorEl) return;
        errorEl.classList.add("d-none");
        errorEl.textContent = "";
    }

    async function fetchJSON(url) {
        const r = await fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}});
        if (!r.ok) throw new Error("HTTP " + r.status);
        return await r.json();
    }

    function getCSRFToken() {
        const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : "";
    }

    function debounce(fn, ms) {
        if (nameDebounce) clearTimeout(nameDebounce);
        nameDebounce = setTimeout(fn, ms);
    }

    function getSelectedWaveIds() {
        const cbs = wavesBox.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(cbs).map((cb) => cb.value);
    }

    function setNameHint(ok, text) {
        if (!nameHint) return;
        nameHint.classList.remove("d-none");
        nameHint.className = ok ? "form-text" : "form-text text-danger";
        nameHint.textContent = text;
    }

    function hideNameHint() {
        if (!nameHint) return;
        nameHint.classList.add("d-none");
        nameHint.textContent = "";
    }

    // Erfolgsmeldung anzeigen
    function showSuccessToast() {
        const toastEl = document.getElementById("copyPageSuccessToast");
        if (!toastEl || typeof bootstrap === "undefined") return;

        const toast = bootstrap.Toast.getOrCreateInstance(toastEl, {
            delay: 3000,
        });
        toast.show();
    }

    // Hilfsfunktion: URL mit ID füllen
    function urlWithId(template, id) {
        // ersetzt "/0/" oder "/0" (z.B. am Ende) zuverlässig
        return template.replace("/0/", `/${id}/`).replace("/0", `/${id}`);
        }




    async function loadSurveys() {
        surveySel.innerHTML = `<option value="">– bitte wählen –</option>`;
        clearError();
        const data = await fetchJSON(API_SURVEYS_URL);

        const surveys = data.surveys || [];
        for (const s of surveys) {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = `${s.name}`;
        surveySel.appendChild(opt);
        }

        if (!surveys.length) {
        showError("Keine Surveys gefunden.");
        }
    }

    async function loadWavesForSurvey(surveyId) {
        wavesBox.innerHTML = "";

        if (!surveyId) {
            wavesBox.innerHTML = `<div class="text-muted small">Bitte zuerst eine Befragung auswählen.</div>`;
            return;
        }

        const wavesUrl = urlWithId(API_WAVES_TEMPLATE, surveyId);
        const data = await fetchJSON(wavesUrl);

        const waves = data.waves || [];
        if (!waves.length) {
            wavesBox.innerHTML = `<div class="text-muted small">Keine Gruppen vorhanden.</div>`;
            return;
        }

        for (const w of waves) {
        const id = `copyWave_${w.id}`;

        const row = document.createElement("div");
        row.className = "form-check";

        row.innerHTML = `
            <input class="form-check-input" type="checkbox" value="${w.id}" id="${id}" ${w.is_locked ? "disabled" : ""}>
            <label class="form-check-label" for="${id}">
            ${w.label} ${w.is_locked ? '<span class="text-muted small">(gesperrt)</span>' : ""}
            </label>
        `;

        wavesBox.appendChild(row);
        }
    }

    async function checkName() {
        const surveyId = surveySel.value;
        const pagename = nameInput.value.trim();

        hideNameHint();
        nameOk = false;

        if (!surveyId || !pagename) return;

        const url = new URL(API_CHECK_NAME_URL, window.location.origin);
        url.searchParams.set("survey_id", surveyId);
        url.searchParams.set("pagename", pagename);

        const data = await fetchJSON(url.toString());
        nameOk = !!data.ok;

        if (nameOk) {
        setNameHint(true, "Name ist verfügbar.");
        } else {
        setNameHint(false, "Name ist im Ziel-Survey bereits vergeben.");
        }
    }
    

// --- Submit
    async function submitCopy() {
        clearError();

        const targetSurveyId = surveySel.value;
        const targetWaveIds = getSelectedWaveIds();
        const newName = nameInput.value.trim();

        if (!targetSurveyId) return showError("Bitte eine Ziel-Befragung auswählen.");
        if (!targetWaveIds.length) return showError("Bitte mindestens eine Gruppe auswählen.");
        if (!newName) return showError("Bitte einen neuen Seitennamen angeben.");
        if (!nameOk) return showError("Der Seitenname ist im Ziel-Survey nicht verfügbar.");

        const form = new FormData();
        form.append("target_survey_id", targetSurveyId);
        for (const wid of targetWaveIds) form.append("target_wave_ids", wid);
        form.append("new_pagename", newName);
        form.append("include_questions", includeQ && includeQ.checked ? "1" : "0");
        form.append("include_variables", includeV && includeV.checked ? "1" : "0");

        const pageId = hiddenPageId ? hiddenPageId.value : "";
        if (!pageId) return showError("Interner Fehler: page_id fehlt.");

        const url = urlWithId(COPY_URL_TEMPLATE, pageId);

        submitBtn.disabled = true;
        try {
        const r = await fetch(url, {
            method: "POST",
            body: form,
            headers: {
            "X-CSRFToken": getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest",
            },
        });

        const data = await r.json().catch(() => ({}));

        if (!r.ok || !data.ok) {
            throw new Error(data.error || "Kopieren fehlgeschlagen.");
        }

        hideModal();
        showSuccessToast();

        // Formular zurücksetzen
        surveySel.value = "";
        wavesBox.innerHTML = `<div class="text-muted small">Bitte zuerst eine Befragung auswählen.</div>`;
        nameInput.value = "";

        hideNameHint();

        } catch (e) {
        showError(e.message || String(e));
        } finally {
        submitBtn.disabled = false;
        }
    }

  // --- Event wiring

  // Modal öffnen: Defaults setzen
    document.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".js-page-copy-open");
        if (!btn) return;

        clearError();

        if (hiddenPageId) hiddenPageId.value = btn.dataset.pageId || "";

        nameInput.value = btn.dataset.defaultName || "";
        nameOk = true;
        hideNameHint();

        syncVarCheckboxState();

        //  Waves-Box zurücksetzen, falls der User vorher schon was ausgewählt hatte
        wavesBox.innerHTML = `<div class="text-muted small">Bitte zuerst eine Befragung auswählen.</div>`;
    });

    surveySel.addEventListener("change", async function () {
        clearError();
        hideNameHint();
        nameOk = true;

        try {
        await loadWavesForSurvey(surveySel.value);
        } catch (e) {
        showError("Gruppen konnten nicht geladen werden: " + (e.message || e));
        }

        debounce(checkName, 250);
    });

    nameInput.addEventListener("input", function () {
        debounce(checkName, 250);
    });

    submitBtn.addEventListener("click", submitCopy);

    // Initial surveys laden
    document.addEventListener("DOMContentLoaded", function () {
        loadSurveys().catch((e) => {
        showError("Surveys konnten nicht geladen werden: " + (e.message || e));
        });

    });

})();










