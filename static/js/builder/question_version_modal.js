// Modal-Workflow zum Anlegen einer neuen Version einer bestehenden Frage.

(function () {
  const modalEl = document.getElementById("questionVersionModal");
  if (!modalEl) return;

  const errorEl = document.getElementById("questionVersionError");
  const groupNameInput = document.getElementById("questionVersionGroupName");
  const targetSurveySelect = document.getElementById("questionVersionTargetSurvey");
  const targetPageSelect = document.getElementById("questionVersionTargetPage");
  const wavesBox = document.getElementById("questionVersionWavesBox");
  const submitButton = document.getElementById("questionVersionSubmit");

  if (!targetSurveySelect || !targetPageSelect || !wavesBox || !submitButton) return;

  const optionsUrl = modalEl.dataset.optionsUrl;
  const createUrl = modalEl.dataset.createUrl;
  const hasVersionGroup = modalEl.dataset.hasVersionGroup === "1";
  const defaultSurveyId = modalEl.dataset.defaultSurveyId || "";
  const defaultWaveId = modalEl.dataset.defaultWaveId || "";
  const defaultPageId = modalEl.dataset.defaultPageId || "";

  let pagesById = new Map();

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    if (!errorEl) return;
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    submitButton.textContent = isLoading
      ? "Version wird angelegt …"
      : "Version anlegen und bearbeiten";
  }

  function getCSRFToken() {
    const wrapper = document.getElementById("question-version-csrf");
    const input = wrapper?.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  async function fetchJSON(url, options = {}) {
    const { headers = {}, ...requestOptions } = options;
    const response = await fetch(url, {
      credentials: "same-origin",
      ...requestOptions,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ...headers,
      },
    });

    let data;
    try {
      data = await response.json();
    } catch (_error) {
      throw new Error(`Ungültige Serverantwort (HTTP ${response.status}).`);
    }

    if (!response.ok || data.ok === false) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  }

  function resetPageSelection() {
    pagesById = new Map();
    targetPageSelect.innerHTML = "";

    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Bitte zuerst eine Befragung auswählen …";
    targetPageSelect.appendChild(option);
    targetPageSelect.disabled = true;

    wavesBox.innerHTML = '<div class="text-muted small">Bitte zuerst eine Zielseite auswählen.</div>';
  }

  function renderPageWaves(page, preferredWaveId = "") {
    wavesBox.innerHTML = "";

    if (!page || !Array.isArray(page.waves) || page.waves.length === 0) {
      wavesBox.innerHTML = '<div class="text-muted small">Für diese Seite stehen in dieser Befragung keine nicht abgeschlossenen Befragtengruppen zur Verfügung.</div>';
      return;
    }

    for (const wave of page.waves) {
      const wrapper = document.createElement("div");
      wrapper.className = "form-check";

      const input = document.createElement("input");
      input.className = "form-check-input question-version-wave";
      input.type = "checkbox";
      input.name = "wave_ids";
      input.value = String(wave.id);
      input.id = `questionVersionWave_${wave.id}`;
      input.checked = String(wave.id) === targetWaveSelect.value;

      const label = document.createElement("label");
      label.className = "form-check-label";
      label.htmlFor = input.id;
      label.textContent = wave.label;

      wrapper.appendChild(input);
      wrapper.appendChild(label);
      wavesBox.appendChild(wrapper);
    }
  }

  async function loadTargetSurveys() {
    targetSurveySelect.disabled = true;
    targetSurveySelect.innerHTML = "";

    const loadingOption = document.createElement("option");
    loadingOption.value = "";
    loadingOption.textContent = "Wird geladen …";
    targetSurveySelect.appendChild(loadingOption);

    resetPageSelection();

    const data = await fetchJSON(optionsUrl);
    const surveys = data.surveys || [];

    targetSurveySelect.innerHTML = "";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = surveys.length
      ? "Bitte auswählen …"
      : "Keine bearbeitbare Befragung vorhanden";
    targetSurveySelect.appendChild(emptyOption);

    for (const survey of surveys) {
      const option = document.createElement("option");
      option.value = String(survey.id);
      option.textContent = survey.label;
      targetSurveySelect.appendChild(option);
    }

    targetSurveySelect.disabled = surveys.length === 0;
    if (
      defaultSurveyId
      && surveys.some((survey) => String(survey.id) === String(defaultSurveyId))
    ) {
      targetSurveySelect.value = String(defaultSurveyId);
      await loadPagesForSurvey(defaultSurveyId, defaultPageId, defaultWaveId);
     }
  }

  async function loadPagesForSurvey(
    surveyId,
   preferredPageId = "",
    preferredWaveId = ""
  ) {
    resetPageSelection();
    clearError();

    if (!surveyId) return;

    targetPageSelect.disabled = true;
    targetPageSelect.innerHTML = "";
    const loadingOption = document.createElement("option");
    loadingOption.value = "";
    loadingOption.textContent = "Wird geladen …";
    targetPageSelect.appendChild(loadingOption);

    const separator = optionsUrl.includes("?") ? "&" : "?";
    const data = await fetchJSON(
      `${optionsUrl}${separator}survey=${encodeURIComponent(surveyId)}`
    );
    const pages = data.pages || [];
    pagesById = new Map(pages.map((page) => [String(page.id), page]));

    targetPageSelect.innerHTML = "";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = pages.length
      ? "Bitte auswählen …"
      : "Keine bearbeitbaren Seiten vorhanden";
    targetPageSelect.appendChild(emptyOption);

    for (const page of pages) {
      const option = document.createElement("option");
      option.value = String(page.id);
      option.textContent = page.name;
      targetPageSelect.appendChild(option);
    }

    targetPageSelect.disabled = pages.length === 0;

    if (preferredPageId && pagesById.has(String(preferredPageId))) {
      targetPageSelect.value = String(preferredPageId);
      renderPageWaves(pagesById.get(String(preferredPageId)));
    }
  }

  function getSelectedWaveIds() {
    return Array.from(
      wavesBox.querySelectorAll("input.question-version-wave:checked")
    ).map((input) => input.value);
  }

  async function submitVersion() {
    clearError();


    const surveyId = targetSurveySelect.value;
    const pageId = targetPageSelect.value;
    const selectedWaveIds = getSelectedWaveIds();
    const groupName = groupNameInput ? groupNameInput.value.trim() : "";

    if (!hasVersionGroup && !groupName) {
      showError("Bitte gib einen Namen für die neue Versionsgruppe an.");
      groupNameInput?.focus();
      return;
    }
    if (!surveyId) {
      showError("Bitte wähle eine Zielbefragung aus.");
      targetSurveySelect.focus();
      return;
    }
    if (!pageId) {
      showError("Bitte wähle eine Zielseite aus.");
      targetPageSelect.focus();
      return;
    }
    if (selectedWaveIds.length === 0) {
      showError("Bitte wähle mindestens eine Befragtengruppe aus.");
      return;
    }

    const formData = new FormData();
    formData.append("survey_id", surveyId);
    formData.append("page_id", pageId);
    formData.append("group_name", groupName);
    for (const waveId of selectedWaveIds) {
      formData.append("wave_ids", waveId);
    }

    setLoading(true);
    try {
      const data = await fetchJSON(createUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCSRFToken(),
        },
        body: formData,
      });
      window.location.assign(data.redirect_url);
    } catch (error) {
      showError(error.message || "Die neue Version konnte nicht angelegt werden.");
      setLoading(false);
    }
  }

  targetSurveySelect.addEventListener("change", function () {
    loadPagesForSurvey(targetSurveySelect.value).catch((error) => {
      showError(`Zielseiten konnten nicht geladen werden: ${error.message}`);
      resetPageSelection();
    });
  });

  targetPageSelect.addEventListener("change", function () {
    clearError();
    renderPageWaves(pagesById.get(targetPageSelect.value));
  });

  submitButton.addEventListener("click", submitVersion);

  modalEl.addEventListener("show.bs.modal", function () {
    clearError();
    setLoading(false);
    if (groupNameInput) groupNameInput.value = "";

    loadTargetSurveys().catch((error) => {
      showError(`Befragungen konnten nicht geladen werden: ${error.message}`);
      targetSurveySelect.disabled = true;
      resetPageSelection();
    });
  });
})();
