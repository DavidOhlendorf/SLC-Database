// Zweistufiger Modal-Workflow zum unveränderten Wiederverwenden einer Frage.

(function () {
  const modalEl = document.getElementById("questionReuseModal");
  if (!modalEl) return;

  const errorEl = document.getElementById("questionReuseError");
  const stepLabel = document.getElementById("questionReuseStepLabel");

  const targetStep = document.getElementById("questionReuseTargetStep");
  const variablesStep = document.getElementById("questionReuseVariablesStep");

  const targetSurveySelect = document.getElementById(
    "questionReuseTargetSurvey"
  );
  const targetPageSelect = document.getElementById(
    "questionReuseTargetPage"
  );
  const wavesBox = document.getElementById("questionReuseWavesBox");

  const createPageToggle = document.getElementById(
    "questionReuseCreatePage"
  );
  const newPageBox = document.getElementById(
    "questionReuseNewPageBox"
  );
  const newPageName = document.getElementById(
    "questionReuseNewPageName"
  );
  const pageNameFeedback = document.getElementById(
    "questionReusePageNameFeedback"
  );

  const existingWarning = document.getElementById(
    "questionReuseExistingWarning"
  );
  const existingWarningText = document.getElementById(
    "questionReuseExistingWarningText"
  );

  const includeVariables = document.getElementById(
    "questionReuseIncludeVariables"
  );
  const variableCount = document.getElementById(
    "questionReuseVariableCount"
  );

  const variablesBox = document.getElementById(
    "questionReuseVariablesBox"
  );
  const noVariablesEl = document.getElementById(
    "questionReuseNoVariables"
  );

  const selectAllVariablesButton = document.getElementById(
    "questionReuseSelectAllVariables"
  );
  const deselectAllVariablesButton = document.getElementById(
    "questionReuseDeselectAllVariables"
  );

  const backButton = document.getElementById("questionReuseBack");
  const submitButton = document.getElementById("questionReuseSubmit");

  if (
    !targetStep
    || !variablesStep
    || !targetSurveySelect
    || !targetPageSelect
    || !wavesBox
    || !createPageToggle
    || !newPageBox
    || !newPageName
    || !includeVariables
    || !variablesBox
    || !backButton
    || !submitButton
  ) {
    return;
  }

  const optionsUrl = modalEl.dataset.optionsUrl;
  const createUrl = modalEl.dataset.createUrl;
  const sourceWaveId = modalEl.dataset.sourceWaveId || "";

  let currentStep = 1;
  let pagesById = new Map();
  let surveyWaves = [];
  let sourceVariables = [];


  // ------------------------------------------------------------
  // Allgemeine Hilfsfunktionen
  // ------------------------------------------------------------

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


  function clearExistingWarning() {
    existingWarning?.classList.add("d-none");

    if (existingWarningText) {
      existingWarningText.innerHTML = "";
    }
  }


  function hasVariableStep() {
    return includeVariables.checked && sourceVariables.length > 0;
  }


  function primaryButtonLabel() {
    if (currentStep === 2) {
      return "Frage übernehmen";
    }

    return hasVariableStep()
      ? "Weiter zu den Variablen"
      : "Frage übernehmen";
  }


  function setStep(step) {
    if (step === 2 && !hasVariableStep()) {
      step = 1;
    }

    currentStep = step;
    clearError();

    const showVariables = step === 2;

    targetStep.classList.toggle("d-none", showVariables);
    variablesStep.classList.toggle("d-none", !showVariables);

    backButton.classList.toggle("d-none", !showVariables);

    if (stepLabel) {
      const totalSteps = hasVariableStep() ? 2 : 1;
      stepLabel.textContent = `Schritt ${step} von ${totalSteps}`;
    }

    submitButton.textContent = primaryButtonLabel();
  }


  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    backButton.disabled = isLoading;

    targetSurveySelect.disabled =
      isLoading || targetSurveySelect.dataset.available !== "1";

    createPageToggle.disabled =
      isLoading
      || !targetSurveySelect.value
      || surveyWaves.length === 0;

    newPageName.disabled = isLoading;

    targetPageSelect.disabled =
      isLoading
      || createPageToggle.checked
      || targetPageSelect.dataset.available !== "1";

    submitButton.textContent = isLoading
      ? "Frage wird übernommen …"
      : primaryButtonLabel();
  }


  function getCSRFToken() {
    const wrapper = document.getElementById("question-reuse-csrf");
    const input = wrapper?.querySelector(
      'input[name="csrfmiddlewaretoken"]'
    );

    return input ? input.value : "";
  }


  async function fetchJSON(url, options = {}) {
    const {
      headers = {},
      ...requestOptions
    } = options;

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
      throw new Error(
        `Ungültige Serverantwort (HTTP ${response.status}).`
      );
    }

    if (!response.ok || data.ok === false) {
      throw new Error(
        data.error || `HTTP ${response.status}`
      );
    }

    return data;
  }


  function withQueryParam(url, key, value) {
    const separator = url.includes("?") ? "&" : "?";

    return (
      `${url}${separator}`
      + `${encodeURIComponent(key)}=${encodeURIComponent(value)}`
    );
  }


  // ------------------------------------------------------------
  // Zielseite / Waves
  // ------------------------------------------------------------

  function clearPageNameFeedback() {
    if (!pageNameFeedback) return;

    pageNameFeedback.textContent = "";
    pageNameFeedback.classList.add("d-none");
    pageNameFeedback.classList.remove(
      "text-danger",
      "text-success"
    );
  }


  function resetPageSelection() {
    pagesById = new Map();
    surveyWaves = [];

    targetPageSelect.innerHTML = "";

    const option = document.createElement("option");
    option.value = "";
    option.textContent =
      "Bitte zuerst eine Zielbefragung auswählen …";

    targetPageSelect.appendChild(option);

    targetPageSelect.disabled = true;
    targetPageSelect.dataset.available = "0";

    createPageToggle.disabled = true;

    wavesBox.innerHTML =
      '<div class="text-muted small">'
      + "Bitte zuerst eine Zielseite auswählen."
      + "</div>";

    clearExistingWarning();
    clearPageNameFeedback();
  }


  function renderWaves(waves) {
    wavesBox.innerHTML = "";
    clearExistingWarning();

    if (
      !Array.isArray(waves)
      || waves.length === 0
    ) {
      wavesBox.innerHTML =
        '<div class="text-muted small">'
        + "Keine bearbeitbaren Befragtengruppen verfügbar."
        + "</div>";

      return;
    }

    for (const wave of waves) {
      const wrapper = document.createElement("div");
      wrapper.className = "form-check";

      const input = document.createElement("input");
      input.className =
        "form-check-input question-reuse-wave";
      input.type = "checkbox";
      input.name = "wave_ids";
      input.value = String(wave.id);
      input.id = `questionReuseWave_${wave.id}`;

      const label = document.createElement("label");
      label.className = "form-check-label";
      label.htmlFor = input.id;
      label.textContent = wave.label;

      wrapper.appendChild(input);
      wrapper.appendChild(label);

      wavesBox.appendChild(wrapper);
    }
  }


  function getSelectedWaveIds() {
    return Array.from(
      wavesBox.querySelectorAll(
        "input.question-reuse-wave:checked"
      )
    ).map((input) => input.value);
  }


  function checkNewPageName() {
    clearPageNameFeedback();

    if (!createPageToggle.checked) {
      return true;
    }

    const name = newPageName.value.trim();

    if (!name) {
      return false;
    }

    const selectedWaveIds = new Set(
      getSelectedWaveIds()
    );

    if (selectedWaveIds.size === 0) {
      return true;
    }

    const normalizedName = name.toLowerCase();

    const duplicates = surveyWaves.filter(
      (wave) =>
        selectedWaveIds.has(String(wave.id))
        && (wave.page_names || []).some(
          (pageName) =>
            String(pageName || "")
              .trim()
              .toLowerCase() === normalizedName
        )
    );

    if (duplicates.length) {
      if (pageNameFeedback) {
        pageNameFeedback.textContent =
          "Bereits vorhanden in: "
          + duplicates
            .map((wave) => wave.label)
            .join(", ");

        pageNameFeedback.classList.remove("d-none");
        pageNameFeedback.classList.add("text-danger");
      }

      return false;
    }

    if (pageNameFeedback) {
      pageNameFeedback.textContent =
        "Der Seitenname ist in den ausgewählten Gruppen "
        + "noch nicht vorhanden.";

      pageNameFeedback.classList.remove("d-none");
      pageNameFeedback.classList.add("text-success");
    }

    return true;
  }


  function applyPageMode() {
    const createNewPage = createPageToggle.checked;

    newPageBox.classList.toggle(
      "d-none",
      !createNewPage
    );

    targetPageSelect.disabled =
      createNewPage
      || targetPageSelect.dataset.available !== "1";

    clearExistingWarning();

    if (createNewPage) {
      renderWaves(surveyWaves);
      checkNewPageName();
      return;
    }

    clearPageNameFeedback();

    const page = pagesById.get(
      targetPageSelect.value
    );

    if (page) {
      renderWaves(page.waves);
    } else {
      wavesBox.innerHTML =
        '<div class="text-muted small">'
        + "Bitte zuerst eine Zielseite auswählen."
        + "</div>";
    }
  }


  // ------------------------------------------------------------
  // Warnung bei Mehrfachverwendung
  // ------------------------------------------------------------

  function updateExistingWarning() {
    clearExistingWarning();

    const selectedWaveIds = new Set(
      getSelectedWaveIds()
    );

    if (selectedWaveIds.size === 0) return;

    let waves = [];
    let targetPageId = null;

    if (createPageToggle.checked) {
      waves = surveyWaves;
    } else {
      const page = pagesById.get(
        targetPageSelect.value
      );

      if (!page) return;

      waves = page.waves || [];
      targetPageId = String(page.id);
    }

    const warningRows = [];

    for (const wave of waves) {
      if (!selectedWaveIds.has(String(wave.id))) {
        continue;
      }

      const otherPages = (
        wave.existing_question_pages || []
      ).filter(
        (existingPage) =>
          targetPageId === null
          || String(existingPage.id) !== targetPageId
      );

      if (otherPages.length) {
        warningRows.push({
          waveLabel: wave.label,
          pages: otherPages,
        });
      }
    }

    if (
      !warningRows.length
      || !existingWarning
      || !existingWarningText
    ) {
      return;
    }

    existingWarningText.innerHTML = "";

    const intro = document.createElement("div");
    intro.textContent =
      "Die Frage wird in mindestens einer ausgewählten "
      + "Befragtengruppe bereits auf einer anderen Seite verwendet:";

    existingWarningText.appendChild(intro);

    const list = document.createElement("ul");
    list.className = "mb-0 mt-1";

    for (const row of warningRows) {
      const item = document.createElement("li");

      const pageNames = row.pages
        .map((pageItem) => pageItem.name)
        .join(", ");

      item.textContent =
        `${row.waveLabel}: ${pageNames}`;

      list.appendChild(item);
    }

    existingWarningText.appendChild(list);
    existingWarning.classList.remove("d-none");
  }


  // ------------------------------------------------------------
  // Variablen
  // ------------------------------------------------------------

  function renderVariables() {
    variablesBox.innerHTML = "";

    const hasVariables = sourceVariables.length > 0;

    variablesBox.classList.toggle(
      "d-none",
      !hasVariables
    );

    noVariablesEl?.classList.toggle(
      "d-none",
      hasVariables
    );

    if (variableCount) {
      variableCount.textContent =
        `(${sourceVariables.length})`;
    }

    includeVariables.checked = hasVariables;
    includeVariables.disabled = !hasVariables;

    if (selectAllVariablesButton) {
      selectAllVariablesButton.disabled = !hasVariables;
    }

    if (deselectAllVariablesButton) {
      deselectAllVariablesButton.disabled = !hasVariables;
    }


    for (const variable of sourceVariables) {

      const row = document.createElement("div");
      row.className =
        "form-check ps-5 pe-3 py-2 border-bottom";


      const input = document.createElement("input");

      input.className =
        "form-check-input question-reuse-variable";

      input.type = "checkbox";
      input.name = "variable_ids";
      input.value = String(variable.id);
      input.id =
        `questionReuseVariable_${variable.id}`;

      input.checked = true;


      const label = document.createElement("label");

      label.className =
        "form-check-label w-100";

      label.htmlFor = input.id;


      const varname = document.createElement("div");
      const code = document.createElement("code");

      code.textContent = variable.varname;

      varname.appendChild(code);
      label.appendChild(varname);


      if (variable.varlab) {
        const varlab = document.createElement("div");

        varlab.className =
          "small text-muted";

        varlab.textContent = variable.varlab;

        label.appendChild(varlab);
      }


      row.appendChild(input);
      row.appendChild(label);

      variablesBox.appendChild(row);
    }

    setStep(1);
  }


  function getSelectedVariableIds() {
    if (!hasVariableStep()) {
      return [];
    }

    return Array.from(
      variablesBox.querySelectorAll(
        "input.question-reuse-variable:checked"
      )
    ).map((input) => input.value);
  }


  // ------------------------------------------------------------
  // Initiale Daten laden
  // ------------------------------------------------------------

  async function loadInitialOptions() {
    targetSurveySelect.disabled = true;
    targetSurveySelect.dataset.available = "0";

    targetSurveySelect.innerHTML =
      '<option value="">Wird geladen …</option>';

    resetPageSelection();


    /*
     * Wichtig:
     * Die Variablen sollen nur aus der aktuell betrachteten
     * Ausgangs-Wave geladen werden.
     */
    let url = optionsUrl;

    if (sourceWaveId) {
      url = withQueryParam(
        url,
        "source_wave",
        sourceWaveId
      );
    }


    const data = await fetchJSON(url);

    const surveys = data.surveys || [];
    sourceVariables = data.variables || [];

    renderVariables();


    targetSurveySelect.innerHTML = "";

    const emptyOption =
      document.createElement("option");

    emptyOption.value = "";

    emptyOption.textContent = surveys.length
      ? "Bitte auswählen …"
      : "Keine bearbeitbare Befragung vorhanden";

    targetSurveySelect.appendChild(emptyOption);


    for (const survey of surveys) {

      const option =
        document.createElement("option");

      option.value = String(survey.id);
      option.textContent = survey.label;

      targetSurveySelect.appendChild(option);
    }


    targetSurveySelect.dataset.available =
      surveys.length ? "1" : "0";

    targetSurveySelect.disabled =
      surveys.length === 0;

    submitButton.disabled =
      surveys.length === 0;
  }


  // ------------------------------------------------------------
  // Seiten der ausgewählten Befragung laden
  // ------------------------------------------------------------

  async function loadPagesForSurvey(surveyId) {
    resetPageSelection();
    clearError();

    if (!surveyId) return;


    targetPageSelect.disabled = true;

    targetPageSelect.innerHTML =
      '<option value="">Wird geladen …</option>';


    const data = await fetchJSON(
      withQueryParam(
        optionsUrl,
        "survey",
        surveyId
      )
    );


    const pages = data.pages || [];
    surveyWaves = data.waves || [];

    pagesById = new Map(
      pages.map(
        (page) => [String(page.id), page]
      )
    );


    targetPageSelect.innerHTML = "";

    const emptyOption =
      document.createElement("option");

    emptyOption.value = "";

    emptyOption.textContent = pages.length
      ? "Bitte auswählen …"
      : "Keine bearbeitbaren Seiten vorhanden";

    targetPageSelect.appendChild(emptyOption);


    for (const page of pages) {

      const option =
        document.createElement("option");

      option.value = String(page.id);
      option.textContent = page.name;

      targetPageSelect.appendChild(option);
    }


    targetPageSelect.dataset.available =
      pages.length ? "1" : "0";

    createPageToggle.disabled =
      surveyWaves.length === 0;

    applyPageMode();
  }


  // ------------------------------------------------------------
  // Validierung
  // ------------------------------------------------------------

  function validateTargetStep() {

    if (!targetSurveySelect.value) {
      showError(
        "Bitte wähle eine Zielbefragung aus."
      );

      targetSurveySelect.focus();
      return false;
    }


    if (createPageToggle.checked) {
      if (!newPageName.value.trim()) {
        showError(
          "Bitte gib einen Seitennamen für die neue Seite an."
        );

        newPageName.focus();
        return false;
      }
    } else if (!targetPageSelect.value) {
      showError(
        "Bitte wähle eine Zielseite aus."
      );

      targetPageSelect.focus();
      return false;
    }


    if (getSelectedWaveIds().length === 0) {
      showError(
        "Bitte wähle mindestens eine Befragtengruppe aus."
      );

      return false;
    }


    if (
      createPageToggle.checked
      && !checkNewPageName()
    ) {
      showError(
        "Dieser Seitenname existiert bereits in mindestens "
        + "einer ausgewählten Befragtengruppe."
      );

      newPageName.focus();
      return false;
    }


    return true;
  }


  // ------------------------------------------------------------
  // Übernahme absenden
  // ------------------------------------------------------------

  async function submitReuse() {
    clearError();


    if (!validateTargetStep()) {
      setStep(1);
      return;
    }


    const formData = new FormData();

    formData.append(
      "survey_id",
      targetSurveySelect.value
    );

    if (createPageToggle.checked) {
      formData.append(
        "create_page",
        "1"
      );

      formData.append(
        "new_page_name",
        newPageName.value.trim()
      );
    } else {
      formData.append(
        "page_id",
        targetPageSelect.value
      );
    }


    for (const waveId of getSelectedWaveIds()) {
      formData.append(
        "wave_ids",
        waveId
      );
    }


    const selectedVariableIds =
      getSelectedVariableIds();


    for (const variableId of selectedVariableIds) {

      formData.append(
        "variable_ids",
        variableId
      );
    }


    /*
     * source_wave_id brauchen wir serverseitig nur,
     * wenn tatsächlich Variablen übernommen werden.
     */
    if (
      selectedVariableIds.length
      && sourceWaveId
    ) {

      formData.append(
        "source_wave_id",
        sourceWaveId
      );
    }


    setLoading(true);


    try {

      const data = await fetchJSON(
        createUrl,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": getCSRFToken(),
          },
          body: formData,
        }
      );

      window.location.reload();


    } catch (error) {

      showError(
        error.message
        || "Die Frage konnte nicht übernommen werden."
      );

      setLoading(false);
    }
  }


  // ------------------------------------------------------------
  // Events: Zielauswahl
  // ------------------------------------------------------------

  targetSurveySelect.addEventListener(
    "change",
    function () {

      loadPagesForSurvey(
        targetSurveySelect.value
      ).catch((error) => {

        showError(
          `Zielseiten konnten nicht geladen werden: ${error.message}`
        );

        resetPageSelection();
      });
    }
  );


  targetPageSelect.addEventListener(
    "change",
    function () {

      clearError();

      if (!createPageToggle.checked) {
        const page = pagesById.get(
          targetPageSelect.value
        );

        renderWaves(
          page ? page.waves : []
        );
      }
    }
  );


  wavesBox.addEventListener(
    "change",
    function (event) {

      if (
        event.target.matches(
          "input.question-reuse-wave"
        )
      ) {

        clearError();
        updateExistingWarning();
        checkNewPageName();
      }
    }
  );


  createPageToggle.addEventListener(
    "change",
    function () {
      clearError();
      applyPageMode();
    }
  );


  newPageName.addEventListener(
    "input",
    function () {
      clearError();
      checkNewPageName();
    }
  );


  // ------------------------------------------------------------
  // Events: Variablen
  // ------------------------------------------------------------

  includeVariables.addEventListener(
    "change",
    function () {

      clearError();

      /*
       * Dadurch ändert sich auch der Button:
       *
       * aktiviert   -> Weiter zu den Variablen
       * deaktiviert -> Frage übernehmen
       */
      setStep(1);
    }
  );


  selectAllVariablesButton?.addEventListener(
    "click",
    function () {

      variablesBox
        .querySelectorAll(
          "input.question-reuse-variable"
        )
        .forEach((input) => {
          input.checked = true;
        });
    }
  );


  deselectAllVariablesButton?.addEventListener(
    "click",
    function () {

      variablesBox
        .querySelectorAll(
          "input.question-reuse-variable"
        )
        .forEach((input) => {
          input.checked = false;
        });
    }
  );


  // ------------------------------------------------------------
  // Navigation zwischen Schritt 1 und 2
  // ------------------------------------------------------------

  backButton.addEventListener(
    "click",
    function () {
      setStep(1);
    }
  );


  submitButton.addEventListener(
    "click",
    function () {

      clearError();


      /*
       * Schritt 1:
       *
       * Variablen gewünscht -> Schritt 2
       * Keine Variablen      -> direkt speichern
       */
      if (
        currentStep === 1
        && hasVariableStep()
      ) {

        if (!validateTargetStep()) {
          return;
        }

        setStep(2);

        return;
      }


      /*
       * Schritt 2 oder direkter Weg ohne Variablen.
       */
      submitReuse();
    }
  );


  // ------------------------------------------------------------
  // Modal öffnen
  // ------------------------------------------------------------

  modalEl.addEventListener(
    "show.bs.modal",
    function () {

      clearError();
      clearExistingWarning();

      pagesById = new Map();
      surveyWaves = [];
      sourceVariables = [];

      createPageToggle.checked = false;
      createPageToggle.disabled = true;

      newPageName.value = "";
      newPageName.disabled = false;
      newPageBox.classList.add("d-none");
      clearPageNameFeedback();

      setStep(1);


      /*
       * Während des initialen Ladens verhindern wir
       * versehentliche Eingaben.
       */
      submitButton.disabled = true;
      backButton.disabled = true;


      loadInitialOptions()
        .then(() => {

          backButton.disabled = false;

          submitButton.textContent =
            primaryButtonLabel();
        })
        .catch((error) => {

          showError(
            `Befragungen konnten nicht geladen werden: ${error.message}`
          );

          targetSurveySelect.disabled = true;
          targetSurveySelect.dataset.available = "0";

          resetPageSelection();

          submitButton.disabled = true;
          backButton.disabled = false;
        });
    }
  );

})();