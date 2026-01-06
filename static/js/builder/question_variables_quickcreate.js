// static/js/builder/question_variables_quickcreate.js

(function () {

    // Hilfsfunktion, um den CSRF-Token aus den Cookies zu lesen
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
    }

    const modalEl = document.getElementById("quickCreateVariableModal");
    if (!modalEl) return;

    if (typeof bootstrap === "undefined") return

    const modal = new bootstrap.Modal(modalEl);
    const inputName = document.getElementById("qc-varname");
    const inputLabel = document.getElementById("qc-varlab");
    const btnSave = document.getElementById("qc-save");
    const errBox = document.getElementById("qc-error");

    const statusEl = document.getElementById("qc-name-status");
    const suggEl = document.getElementById("qc-suggestions");
    const checkUrl = modalEl.dataset.varnameCheckUrl;

    let activeSelectEl = null;
    let activeCreateUrl = null;

    // debounce timer
    let checkTimer = null;

    function showError(msg) {
        if (!errBox) return;
        errBox.textContent = msg;
        errBox.classList.remove("d-none");
    }

    function clearError() {
        if (!errBox) return;
        errBox.textContent = "";
        errBox.classList.add("d-none");
    }

    function setStatus(html) {
        if (!statusEl) return;
        statusEl.innerHTML = html || "";
    }

    function clearSuggestions() {
        if (!suggEl) return;
        suggEl.innerHTML = "";
        suggEl.classList.add("d-none");
    }

    function renderSuggestions(items) {
        if (!suggEl) return;
        
        if (!items || !items.length ) {
            clearSuggestions();
            return;
        }
    
        const rows = items.map(v =>
            `<div class="qc-sugg-row">${v}</div>`
        ).join("");

        suggEl.innerHTML =
            `<div class="qc-sugg-header">Ähnliche, vorhandene Variablen:</div>` +
            `<div class="qc-sugg-box">${rows}</div>`;

        suggEl.classList.remove("d-none");
    }


    // Live-Check bei Eingabe
    async function runVarnameCheck() {
        if (!checkUrl || !inputName) return;

        const q = (inputName.value || "").trim();

        if (q.length < 2) {
        clearSuggestions();
        return;
        }

        try {
        const res = await fetch(`${checkUrl}?q=${encodeURIComponent(q)}`, { method: "GET" });
        const data = await res.json();

        if (!data || !data.is_valid_length) {
            clearSuggestions();
            return;
        }

        if (data.exists_exact) {
            setStatus(`<div class="form-text text-danger">Name ist bereits vergeben.</div>`);
        } else {
            setStatus(`<div class="form-text text-success">Name verfügbar.</div>`);
        }

        renderSuggestions(data.suggestions || []);
        } catch (e) {
        // Live-check ist Komfort, nicht kritisch
        setStatus(`<div class="form-text text-warning">Live-Prüfung nicht verfügbar.</div>`);
        clearSuggestions();
        }
    }


  // Delegation: funktioniert auch für dynamisch hinzugefügte Zeilen
    document.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".vfs-quickcreate");
        if (!btn) return;

        const row = btn.closest(".vfs-form");
        if (!row) return;

        activeSelectEl = row.querySelector(".variable-widget select") || row.querySelector("select");
        activeCreateUrl = btn.getAttribute("data-quickcreate-url");

        inputName.value = "";
        inputLabel.value = "";
        clearError();

        // Live UI initialisieren
        clearSuggestions();

        modal.show();

        setTimeout(() => inputName.focus(), 150);
    });

    // Live-check beim Tippen im Varname-Feld
    if (inputName) {
        inputName.addEventListener("input", () => {
        clearError();
        if (checkTimer) window.clearTimeout(checkTimer);
        checkTimer = window.setTimeout(runVarnameCheck, 250);
        });
    }

    // Speichern-Button im Modal
    btnSave.addEventListener("click", async () => {
        clearError();

        const varname = (inputName.value || "").trim();
        const varlab = (inputLabel.value || "").trim();

        if (varname.length < 2) {
        showError("Mindestens 2 Zeichen.");
        return;
        }
        if (!varlab) {
        showError("Bitte gib ein Variablenlabel ein.");
        return;
        }
        if (!activeSelectEl || !activeCreateUrl) {
        showError("Interner Fehler: Ziel-Select nicht gefunden.");
        return;
        }

        btnSave.disabled = true;

        try {
            const formData = new FormData();
            formData.append("varname", varname);
            formData.append("varlab", varlab);

            const res = await fetch(activeCreateUrl, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
            });

            const data = await res.json();

            if (!res.ok || !data.ok) {
                showError(data.error || "Fehler beim Anlegen.");
                return;
            }

            // TomSelect-Instance holen 
            const ts = activeSelectEl.tomselect;
            if (!ts) {
                showError("Interner Fehler: TomSelect nicht initialisiert.");
                return;
            }

            ts.addOption({ value: data.id, text: data.text });
            ts.addItem(String(data.id), true);

            modal.hide();
        } catch (e) {
            showError("Netzwerkfehler beim Anlegen.");
        } finally {
            btnSave.disabled = false;
        }
    });

    //  beim Schließen aufräumen (verhindert "alte" Vorschläge beim nächsten Öffnen)
    modalEl.addEventListener("hidden.bs.modal", () => {
        clearError();
        setStatus("");
        clearSuggestions();
    });

})();
