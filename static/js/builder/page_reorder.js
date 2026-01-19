document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("pageCardList");
  if (!list) return;

  const canDnd = list.dataset.canDnd === "1";
  if (!canDnd) return;

  const reorderUrl = list.dataset.reorderUrl;

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
  }
  const csrftoken = getCookie("csrftoken");

  // Initialize SortableJS
  new Sortable(list, {
    animation: 150,
    handle: ".js-drag-handle",
    draggable: ".page-card",
    onEnd: async () => {
      const ordered = Array.from(list.querySelectorAll(".page-card"))
        .map(el => el.dataset.pageId);

      try {
        const resp = await fetch(reorderUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken
          },
          body: JSON.stringify({ ordered_page_ids: ordered })
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.ok) {
          console.error("Reorder failed:", data);
        }
      } catch (e) {
        console.error("Reorder request error:", e);
      }
    }
  });
});
