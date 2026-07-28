// Zweistufiger Modal-Workflow zum Versionieren einer Frage und ihrer Variablen.
 

(function () {
  const modalEl = document.getElementById("questionVersionModal");
  if (!modalEl) return;

  const errorEl = document.getElementById("questionVersionError");
  const stepLabel = document.getElementById("questionVersionStepLabel");
  const targetStep = document.getElementById("questionVersionTargetStep");
  const variablesStep = document.getElementById("questionVersionVariablesStep");
  const groupNameInput = document.getElementById("questionVersionGroupName");
  const versionReasonInput = document.getElementById("questionVersionReason");
  const targetSurveySelect = document.getElementById("questionVersionTargetSurvey");
  const targetPageSelect = document.getElementById("questionVersionTargetPage");
  const wavesBox = document.getElementById("questionVersionWavesBox");
  const variablesBody = document.getElementById("questionVersionVariablesBody");
  const variablesTableWrap = document.getElementById("questionVersionVariablesTableWrap");
  const noVariablesEl = document.getElementById("questionVersionNoVariables");
  const unlinkedVariablesEl = document.getElementById("questionVersionUnlinkedVariables");
  const backButton = document.getElementById("questionVersionBack");
  const submitButton = document.getElementById("questionVersionSubmit");

  if (
   !targetStep
   || !variablesStep
   || !targetSurveySelect
   || !targetPageSelect
   || !wavesBox
   || !variablesBody
   || !backButton
   || !submitButton
  ) return;
  const optionsUrl = modalEl.dataset.optionsUrl;
  const createUrl = modalEl.dataset.createUrl;
  const varnameCheckUrl = modalEl.dataset.varnameCheckUrl;
  const hasVersionGroup = modalEl.dataset.hasVersionGroup === "1";
  const defaultSurveyId = modalEl.dataset.defaultSurveyId || "";
  const defaultWaveId = modalEl.dataset.defaultWaveId || "";
  const defaultPageId = modalEl.dataset.defaultPageId || "";

  let currentStep = 1;
  let pagesById = new Map();
  let sourceVariables = [];
  let unlinkedVariableNames = [];
  const checkTimers = new WeakMap();

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

  function primaryButtonLabel() {
    if (currentStep === 2) {
      return "Version mit Variablen anlegen und bearbeiten";
    }
    return sourceVariables.length
      ? "Weiter zu den Variablen"
      : "Version anlegen und bearbeiten";
  }


  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    backButton.disabled = isLoading;
    submitButton.textContent = isLoading
      ? "Version wird angelegt …"
      : primaryButtonLabel();
  }

  function setStep(step) {
    currentStep = step;
    clearError();

    const showVariables = step === 2;
    targetStep.classList.toggle("d-none", showVariables);
    variablesStep.classList.toggle("d-none", !showVariables);
    backButton.classList.toggle("d-none", !showVariables);
    if (stepLabel) {
      const totalSteps = sourceVariables.length ? 2 : 1;
      stepLabel.textContent = `Schritt ${step} von ${totalSteps}`;
    }
    submitButton.textContent = primaryButtonLabel();
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
      input.checked = Boolean(preferredWaveId)
        && String(wave.id) === String(preferredWaveId);

      const label = document.createElement("label");
      label.className = "form-check-label";
      label.htmlFor = input.id;
      label.textContent = wave.label;

      wrapper.appendChild(input);
      wrapper.appendChild(label);
      wavesBox.appendChild(wrapper);
    }
  }

  function parseVariableName(name) {
    const normalized = (name || "").trim().toLowerCase();
    const match = normalized.match(
      /^(?:[a-z]{2}_)?[a-z]{3}\d{3}(?:_((?:[vgpf]\d{1,2})+))?$/
    );
    if (!match) return null;

    const suffixText = match[1] || "";

    const rank = { v: 0, g: 1, p: 2, f: 3 };
    const seen = new Set();
    const suffixes = {};
    let previousRank = -1;
    let consumed = "";
    const tokenRegex = /([vgpf])(\d{1,2})/g;
    let token;

    while ((token = tokenRegex.exec(suffixText)) !== null) {
      const suffix = token[1];
      const number = Number(token[2]);
      consumed += token[0];
      if (
        seen.has(suffix)
        || rank[suffix] < previousRank
        || number < 1
        || number > 99
      ) {
        return null;
       }
      seen.add(suffix);
      suffixes[suffix] = number;
      previousRank = rank[suffix];
    }

  if (consumed !== suffixText) return null;
    return { normalized, suffixes };
  }

  function validateVariableName(name) {
    return parseVariableName(name) !== null;
  }

  function nonVersionSuffixes(name) {
    const parsed = parseVariableName(name);
    if (!parsed) return null;
    const result = {};
    for (const suffix of ["g", "p", "f"]) {
      if (Object.prototype.hasOwnProperty.call(parsed.suffixes, suffix)) {
        result[suffix] = parsed.suffixes[suffix];
      }
    }
    return result;
  }

  function sameSuffixes(first, second) {
    return ["g", "p", "f"].every(
      (suffix) => (first?.[suffix] ?? null) === (second?.[suffix] ?? null)
    );
   }

  function setVariableStatus(input, message = "", type = "") {
    const status = input.closest("td")?.querySelector(".question-version-variable-status");
    input.classList.remove("is-invalid", "is-valid");
    if (type === "invalid") input.classList.add("is-invalid");
    if (type === "valid") input.classList.add("is-valid");

    if (status) {
      status.textContent = message;
      status.className = "question-version-variable-status small";
      if (type === "invalid") status.classList.add("text-danger");
      if (type === "valid") status.classList.add("text-success");
      if (!type) status.classList.add("text-muted");
    }
  }

  function setSuffixStatus(row, message = "", type = "") {
    const status = row.querySelector(".question-version-suffix-status");
    const checkbox = row.querySelector(
      ".question-version-inherit-suffix-metadata"
    );
    checkbox?.classList.remove("is-invalid");
    if (type === "invalid") checkbox?.classList.add("is-invalid");

    if (!status) return;
    status.textContent = message;
    status.className = "question-version-suffix-status small";
    if (type === "invalid") status.classList.add("text-danger");
    else if (type === "warning") status.classList.add("text-warning-emphasis");
    else status.classList.add("text-muted");
  }

  function validateSuffixMetadataRow(row) {
    const versionCheckbox = row.querySelector(
      ".question-version-variable-check"
    );
    const inheritCheckbox = row.querySelector(
      ".question-version-inherit-suffix-metadata"
    );
    const input = row.querySelector(".question-version-variable-name");

    if (!versionCheckbox?.checked || !inheritCheckbox || !input) {
      setSuffixStatus(row);
      return true;
    }

    const sourceSuffixes = nonVersionSuffixes(row.dataset.sourceVarname || "");
    const targetSuffixes = nonVersionSuffixes(input.value);
    if (sourceSuffixes === null || targetSuffixes === null) {
      setSuffixStatus(row);
      return true;
    }

    const suffixesChanged = !sameSuffixes(sourceSuffixes, targetSuffixes);
    if (inheritCheckbox.checked && suffixesChanged) {
      setSuffixStatus(
        row,
        "g-, p- oder f-Suffixe wurden verändert. Deaktiviere die Übernahme, wenn dies beabsichtigt ist.",
        "invalid"
      );
      return false;
    }

    if (!inheritCheckbox.checked) {
      const targetHasSuffixes = Object.keys(targetSuffixes).length > 0;
      const sourceHasMetadata = row.dataset.hasSuffixMetadata === "1";

      if (targetHasSuffixes) {
        setSuffixStatus(
          row,
          "Die g-/p-/f-Angaben werden nicht übernommen, obwohl der neue Name entsprechende Suffixe enthält. Dadurch kann eine Inkonsistenz entstehen.",
          "warning"
        );
      } else if (suffixesChanged || sourceHasMetadata) {
        setSuffixStatus(
          row,
          "Die bisherigen g-/p-/f-Kennzeichnungen und Begründungen werden nicht übernommen. Bitte prüfe die Variable anschließend.",
          "warning"
        );
      } else {
        setSuffixStatus(row);
      }
    } else {
      setSuffixStatus(row);
    }

    return true;
  }


  function selectedVariableRows() {
    return Array.from(
      variablesBody.querySelectorAll("tr.question-version-variable-row")
    ).filter((row) => row.querySelector(".question-version-variable-check")?.checked);
  }

  function validateLocalVariableRows() {
    let valid = true;
    const usedNames = new Map();

    for (const row of selectedVariableRows()) {
      const input = row.querySelector(".question-version-variable-name");
      const name = (input?.value || "").trim().toLowerCase();
      if (!input) continue;

      if (!validateSuffixMetadataRow(row)) {
        valid = false;
      }


      if (!validateVariableName(name)) {
        setVariableStatus(
          input,
          "Name entspricht nicht dem SLC-Variablenschema.",
          "invalid"
        );
        valid = false;
        continue;
      }

      if (usedNames.has(name)) {
        setVariableStatus(input, "Name wurde im Dialog mehrfach vergeben.", "invalid");
        const firstInput = usedNames.get(name);
        setVariableStatus(firstInput, "Name wurde im Dialog mehrfach vergeben.", "invalid");
        valid = false;
        continue;
      }

      usedNames.set(name, input);
      if (input.dataset.existsExact !== "1") {
        setVariableStatus(input);
      }
    }

    return valid;
  }

  async function checkVariableAvailability(input) {
    if (!input || input.disabled) return true;

    const name = (input.value || "").trim().toLowerCase();
    input.value = name;

    if (!validateVariableName(name)) {
      setVariableStatus(input, "Name entspricht nicht dem SLC-Variablenschema.", "invalid");
      input.dataset.existsExact = "0";
      return false;
    }

    const data = await fetchJSON(
      `${varnameCheckUrl}?q=${encodeURIComponent(name)}`
    );
    input.dataset.checkedName = name;
    input.dataset.existsExact = data.exists_exact ? "1" : "0";

    if (data.exists_exact) {
      setVariableStatus(input, "Name ist bereits vergeben.", "invalid");
      return false;
    }

    setVariableStatus(input, "Name ist verfügbar.", "valid");
    return true;
  }

  function scheduleAvailabilityCheck(input) {
    const oldTimer = checkTimers.get(input);
    if (oldTimer) window.clearTimeout(oldTimer);

    input.dataset.existsExact = "0";
    input.dataset.checkedName = "";
    setVariableStatus(input);
    validateLocalVariableRows();

    const timer = window.setTimeout(() => {
      checkVariableAvailability(input)
        .then(() => validateLocalVariableRows())
        .catch(() => {
          setVariableStatus(input, "Verfügbarkeit konnte nicht geprüft werden.");
        });
    }, 300);
    checkTimers.set(input, timer);
  }

  async function validateVariableRowsForSubmit() {
    if (!validateLocalVariableRows()) return false;

    const inputs = selectedVariableRows()
      .map((row) => row.querySelector(".question-version-variable-name"))
      .filter(Boolean);

    const results = await Promise.all(
      inputs.map(async (input) => {
        const name = (input.value || "").trim().toLowerCase();
        if (input.dataset.checkedName === name && input.dataset.existsExact === "0") {
          return true;
        }
        return checkVariableAvailability(input);
      })
    );

    return results.every(Boolean) && validateLocalVariableRows();
  }

  function renderVariableRows() {
    variablesBody.innerHTML = "";
    const hasVariables = sourceVariables.length > 0;
    variablesTableWrap?.classList.toggle("d-none", !hasVariables);
    noVariablesEl?.classList.toggle("d-none", hasVariables);

    for (const variable of sourceVariables) {
      const row = document.createElement("tr");
      row.className = "question-version-variable-row";
      row.dataset.sourceVariableId = String(variable.id);
      row.dataset.sourceVarname = variable.varname;
      row.dataset.hasSuffixMetadata = variable.has_suffix_metadata ? "1" : "0";

      const checkCell = document.createElement("td");
      checkCell.className = "text-center";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-check-input question-version-variable-check";
      checkbox.checked = Boolean(variable.suggested_name);
      checkbox.disabled = !variable.suggested_name;
      checkbox.setAttribute("aria-label", `${variable.varname} versionieren`);
      checkCell.appendChild(checkbox);

      const sourceCell = document.createElement("td");
      const sourceCode = document.createElement("code");
      sourceCode.textContent = variable.varname;
      sourceCell.appendChild(sourceCode);

      const labelCell = document.createElement("td");
      labelCell.textContent = variable.varlab || "–";

      const metadataCell = document.createElement("td");
      metadataCell.className = "text-center";
      const metadataCheck = document.createElement("input");
      metadataCheck.type = "checkbox";
      metadataCheck.className =
        "form-check-input question-version-inherit-suffix-metadata";
      metadataCheck.checked = true;
      metadataCheck.disabled = !checkbox.checked;
      metadataCheck.setAttribute(
        "aria-label",
        `g-/p-/f-Angaben von ${variable.varname} übernehmen`
      );
      metadataCell.appendChild(metadataCheck);

      const suffixLabel = document.createElement("div");
      suffixLabel.className = "small text-muted mt-1";
      const sourceSuffixes = variable.source_suffixes || {};
      suffixLabel.textContent = ["g", "p", "f"]
        .filter((suffix) => sourceSuffixes[suffix])
        .map((suffix) => `${suffix}${sourceSuffixes[suffix]}`)
        .join(" · ") || "keine Suffixe";
      metadataCell.appendChild(suffixLabel);

      const suffixStatus = document.createElement("div");
      suffixStatus.className = "question-version-suffix-status small text-muted";
      metadataCell.appendChild(suffixStatus);

      const nameCell = document.createElement("td");
      const input = document.createElement("input");
      input.type = "text";
      input.className = "form-control form-control-sm question-version-variable-name";
      input.value = variable.suggested_name || "";
      input.maxLength = 50;
      input.autocomplete = "off";
      input.disabled = !checkbox.checked;
      input.dataset.existsExact = "0";
      input.dataset.checkedName = "";
      nameCell.appendChild(input);

      const status = document.createElement("div");
      status.className = "question-version-variable-status small text-muted";
      if (variable.suggestion_error) {
        status.textContent = variable.suggestion_error;
        status.className = "question-version-variable-status small text-danger";
      }
      nameCell.appendChild(status);

      row.appendChild(checkCell);
      row.appendChild(sourceCell);
      row.appendChild(labelCell);
      row.appendChild(metadataCell);
      row.appendChild(nameCell);
      variablesBody.appendChild(row);
    }

    if (unlinkedVariablesEl) {
      if (unlinkedVariableNames.length) {
        unlinkedVariablesEl.textContent =
          `Hinweis: ${unlinkedVariableNames.join(", ")} stehen in Items oder Antwortoptionen, sind aber nicht mit der Ausgangsfrage verknüpft. Diese Felder werden in der neuen Frage geleert.`;
        unlinkedVariablesEl.classList.remove("d-none");
      } else {
        unlinkedVariablesEl.textContent = "";
        unlinkedVariablesEl.classList.add("d-none");
      }
    }
  }

  async function loadTargetSurveys() {
    targetSurveySelect.disabled = true;
    targetSurveySelect.innerHTML = '<option value="">Wird geladen …</option>';
    resetPageSelection();

    const data = await fetchJSON(optionsUrl);
    const surveys = data.surveys || [];
    sourceVariables = data.variables || [];
    unlinkedVariableNames = data.unlinked_variable_names || [];
    renderVariableRows();
    setStep(1);
    submitButton.textContent = primaryButtonLabel();

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
    targetPageSelect.innerHTML = '<option value="">Wird geladen …</option>';

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
      renderPageWaves(
        pagesById.get(String(preferredPageId)),
        preferredWaveId
      );
    }
  }

  function getSelectedWaveIds() {
    return Array.from(
      wavesBox.querySelectorAll("input.question-version-wave:checked")
    ).map((input) => input.value);
  }

  function validateTargetStep() {
    const groupName = groupNameInput ? groupNameInput.value.trim() : "";

    if (!hasVersionGroup && !groupName) {
      showError("Bitte gib einen Namen für die neue Versionsgruppe an.");
      groupNameInput?.focus();
      return false;
    }
    if (!targetSurveySelect.value) {
      showError("Bitte wähle eine Zielbefragung aus.");
      targetSurveySelect.focus();
      return false;
    }
    if (!targetPageSelect.value) {
      showError("Bitte wähle eine Zielseite aus.");
      targetPageSelect.focus();
      return false;
    }
    if (getSelectedWaveIds().length === 0) {
      showError("Bitte wähle mindestens eine Befragtengruppe aus.");
      return false;
    }
    return true;
  }

  function getVariableVersionsPayload() {
    return selectedVariableRows().map((row) => ({
      source_variable_id: Number(row.dataset.sourceVariableId),
      new_varname: (
        row.querySelector(".question-version-variable-name")?.value || ""
      ).trim().toLowerCase(),
      inherit_suffix_metadata: Boolean(
        row.querySelector(
          ".question-version-inherit-suffix-metadata"
        )?.checked
      ),
    }));
  }

  async function submitVersion() {
    clearError();
    if (!validateTargetStep()) {
      setStep(1);
      return;
    }

    if (sourceVariables.length && currentStep === 2) {
      try {
        const variablesValid = await validateVariableRowsForSubmit();
        if (!variablesValid) {
          showError("Bitte korrigiere die markierten Variablennamen.");
          return;
        }
      } catch (error) {
        showError(`Variablennamen konnten nicht geprüft werden: ${error.message}`);
        return;
      }
    }


    const formData = new FormData();
    formData.append("survey_id", targetSurveySelect.value);
    formData.append("page_id", targetPageSelect.value);
    formData.append("group_name", groupNameInput ? groupNameInput.value.trim() : "");
    formData.append(
      "version_reason",
      versionReasonInput ? versionReasonInput.value.trim() : ""
    );
    formData.append(
      "variable_versions",
      JSON.stringify(sourceVariables.length ? getVariableVersionsPayload() : [])
    );
    for (const waveId of getSelectedWaveIds()) {
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

  variablesBody.addEventListener("change", function (event) {
    const checkbox = event.target.closest(".question-version-variable-check");
    if (!checkbox) return;
    const row = checkbox.closest("tr");
    const input = row?.querySelector(".question-version-variable-name");
    const metadataCheck = row?.querySelector(
      ".question-version-inherit-suffix-metadata"
    );
    if (!input) return;
    input.disabled = !checkbox.checked;
    if (metadataCheck) metadataCheck.disabled = !checkbox.checked;
    if (!checkbox.checked) {
      setVariableStatus(input);
      setSuffixStatus(row);
      validateLocalVariableRows();
    } else {
      input.focus();
      scheduleAvailabilityCheck(input);
      validateSuffixMetadataRow(row);
    }
  });

  variablesBody.addEventListener("change", function (event) {
    const metadataCheck = event.target.closest(
      ".question-version-inherit-suffix-metadata"
    );
    if (!metadataCheck) return;
    const row = metadataCheck.closest("tr");
    if (row) {
      validateSuffixMetadataRow(row);
      validateLocalVariableRows();
    }
  });

  variablesBody.addEventListener("input", function (event) {
    const input = event.target.closest(".question-version-variable-name");
    if (input) scheduleAvailabilityCheck(input);
  });

  backButton.addEventListener("click", function () {
    setStep(1);
  });

  submitButton.addEventListener("click", function () {
    clearError();
    if (currentStep === 1 && sourceVariables.length) {
      if (!validateTargetStep()) return;
      setStep(2);
      return;
    }
    submitVersion();
  });

  modalEl.addEventListener("show.bs.modal", function () {
    clearError();
    sourceVariables = [];
    unlinkedVariableNames = [];
    if (groupNameInput) groupNameInput.value = "";
    if (versionReasonInput) versionReasonInput.value = "";
    setStep(1);
    setLoading(false);

    loadTargetSurveys().catch((error) => {
      showError(`Befragungen konnten nicht geladen werden: ${error.message}`);
      targetSurveySelect.disabled = true;
      resetPageSelection();
    });
  });
})();
