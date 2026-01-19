document.addEventListener("DOMContentLoaded", () => {
  const wrapper = document.getElementById("pageListsWrapper");
  if (!wrapper) return;

  const canDnd = wrapper.dataset.canDnd === "1";
  if (!canDnd) return;

  const reorderUrl = wrapper.dataset.reorderUrl;

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
  }
  const csrftoken = getCookie("csrftoken");

  const lists = Array.from(wrapper.querySelectorAll(".js-page-list"));
  if (!lists.length) return;

  function buildPayload() {
    const containers = lists.map(list => {
      const raw = (list.dataset.moduleId || "").trim();
      const moduleId = raw ? parseInt(raw, 10) : null;

      const pageIds = Array.from(list.querySelectorAll(".page-card"))
        .map(el => parseInt(el.dataset.pageId, 10));

      return { module_id: moduleId, page_ids: pageIds };
    });
    return { containers };
  }

  async function save() {
    const payload = buildPayload();

    try {
      const resp = await fetch(reorderUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(payload)
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        console.error("Reorder failed:", data);
      }
    } catch (e) {
      console.error("Reorder request error:", e);
    }
  }

  lists.forEach(list => {
    new Sortable(list, {
      animation: 150,
      handle: ".js-drag-handle",
      draggable: ".page-card",
      group: "pages",
      onEnd: save
    });
  });
});
