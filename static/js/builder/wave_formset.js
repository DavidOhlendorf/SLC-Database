document.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("add-wave");
  const formsDiv = document.getElementById("wave-forms");
  const template = document.getElementById("empty-wave-form");

  if (!addBtn || !formsDiv || !template) return;

  const prefix = formsDiv.dataset.formsetPrefix || "waves";
  const totalForms = document.getElementById(`id_${prefix}-TOTAL_FORMS`);

  if (!totalForms) return;

  addBtn.addEventListener("click", () => {
    const formIndex = parseInt(totalForms.value, 10);
    const html = template.innerHTML.replaceAll("__prefix__", formIndex);

    formsDiv.insertAdjacentHTML("beforeend", html);
    totalForms.value = formIndex + 1;
  });
});
