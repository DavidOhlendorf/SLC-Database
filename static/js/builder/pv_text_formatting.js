// Kleine Eingabehilfe für die in Programmiervorlagen verwendeten Textmarker.
(function () {
  function wrapSelection(textarea, marker) {
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? start;
    const selectedText = textarea.value.slice(start, end);
    const replacement = marker + selectedText + marker;
    const scrollTop = textarea.scrollTop;

    textarea.setRangeText(replacement, start, end, "end");

    if (selectedText) {
      textarea.setSelectionRange(start + marker.length, end + marker.length);
    } else {
      const cursor = start + marker.length;
      textarea.setSelectionRange(cursor, cursor);
    }

    textarea.scrollTop = scrollTop;
    textarea.focus();
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-pv-format-toolbar]").forEach(function (toolbar) {
      const targetId = toolbar.dataset.target;
      const textarea = targetId ? document.getElementById(targetId) : null;
      if (!textarea) return;

      toolbar.querySelectorAll("[data-pv-marker]").forEach(function (button) {
        button.addEventListener("click", function () {
          wrapSelection(textarea, button.dataset.pvMarker || "");
        });
      });
    });
  });
})();
