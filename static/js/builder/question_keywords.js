document.addEventListener("DOMContentLoaded", function () {

  const container = document.getElementById("keyword-widget");
  const minLengthHint = document.getElementById("keyword-minlength-hint");

  if (!container) return;

  const selectEl = container.querySelector("select");
  if (!selectEl) return;

  const searchUrl = container.dataset.searchUrl;
  const createUrl = container.dataset.createUrl;

  function getCSRFToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
  }


  new TomSelect(selectEl, {
    plugins: ["remove_button"],
    persist: false,

    valueField: "value",
    labelField: "text",
    searchField: "text",

    onType: function () {
      if (minLengthHint) {
        minLengthHint.classList.add("d-none");
      }
    },

    // Minimum input length before triggering load
    shouldLoad: function (query) {
      return (query || "").trim().length >= 2;
    },

    load: function (query, callback) {
      query = (query || "").trim();
      if (query.length < 2) return callback();

      fetch(`${searchUrl}?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(items => callback(items))
        .catch(() => callback());
    },

    create: function (input, callback) {
      input = (input || "").trim();
        if (input.length < 2) {
          if (minLengthHint) {
            minLengthHint.classList.remove("d-none");
          }
          return callback();
        }

          if (minLengthHint) {
            minLengthHint.classList.add("d-none");
  }

      const formData = new FormData();
      formData.append("name", input);

      fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCSRFToken() },
        body: formData
      })
      .then(r => r.json().then(data => ({ ok: r.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) return callback();
        callback({ value: data.value, text: data.text });
      })
      .catch(() => callback());
    },
  });
});
