document.addEventListener("DOMContentLoaded", () => {
  const wrapper = document.getElementById("pageListsWrapper");
  if (!wrapper) return;

  // ----------------------------
  // 1) Collapse state restore/persist (läuft IMMER, unabhängig von canDnd)
  // ----------------------------
  (function initModuleCollapsePersistence() {
    const waveId = wrapper.dataset.waveId || "wave";
    const keyPrefix = `slc.moduleCollapse.${waveId}.`;

    document.querySelectorAll('[id^="moduleCollapse-"]').forEach((el) => {
      const key = keyPrefix + el.id;

      // Restore (nur Klassen setzen -> kein Flackern durch toggle)
      const saved = localStorage.getItem(key);
      if (saved === "hide") el.classList.remove("show");
      else if (saved === "show") el.classList.add("show");

      // Persist
      el.addEventListener("shown.bs.collapse", () => localStorage.setItem(key, "show"));
      el.addEventListener("hidden.bs.collapse", () => localStorage.setItem(key, "hide"));
    });
  })();

  // ----------------------------
  // 2) Alles ab hier nur für Drag&Drop
  // ----------------------------
  const canDnd = wrapper.dataset.canDnd === "1";
  if (!canDnd) return;

  const reorderUrl = wrapper.dataset.reorderUrl;

  const csrftoken =
    wrapper.dataset.csrfToken ||
    document.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
    "";

  if (!csrftoken) {
    console.error("CSRF token missing");
    return;
  }

  const lists = Array.from(wrapper.querySelectorAll(".js-page-list"));
  if (!lists.length) return;


  // Prüfen, ob eine Seite in den Zielcontainer verschoben werden darf
  function canDropPage(pageEl, targetList) {
    // Der Bereich "Ohne Modul" erlaubt beide Fragebogenteile
    if (!targetList.dataset.moduleId) {
      return true;
    }

    const pagePart = pageEl.dataset.questionnairePart;
    const modulePart = targetList.dataset.questionnairePart;

    return Boolean(pagePart && modulePart && pagePart === modulePart);
  }

  // Aktuell gezogene Seite
  let draggedPage = null;

  // Mauszeiger abhängig vom Zielmodul aktualisieren
  function updateDropCursor(event) {
    if (!draggedPage) return;

    const target = document.elementFromPoint(
      event.clientX,
      event.clientY
    );

    const targetList = lists.find((list) => {
      const moduleCard = list.closest(".card");
      return moduleCard && moduleCard.contains(target);
    });

    const forbidden = Boolean(
      targetList && !canDropPage(draggedPage, targetList)
    );

    document.body.classList.toggle(
      "page-drop-forbidden",
      forbidden
    );
  }

  // Mauszeiger nach Ende des Ziehvorgangs zurücksetzen
  function resetDropCursor() {
    draggedPage = null;

    document.removeEventListener(
      "mousemove",
      updateDropCursor
    );

    document.body.classList.remove(
      "page-drop-forbidden"
    );
  }


  // UI refresh (Badges, Empty hints)
  function refreshModuleUI() {
    wrapper.querySelectorAll(".js-page-list").forEach((listEl) => {
      const cardEl = listEl.closest(".card");
      if (!cardEl) return;

      const countEl = cardEl.querySelector(".js-page-count");
      const cards = listEl.querySelectorAll(".page-card");
      const count = cards.length;

      if (countEl) countEl.textContent = String(count);

      const existingHint = listEl.querySelector(".js-empty-hint");
      if (count === 0) {
        if (!existingHint) {
          const div = document.createElement("div");
          div.className = "text-muted small js-empty-hint";

          const isUnassigned = (listEl.dataset.moduleId || "").trim() === "";
          div.textContent = isUnassigned
            ? "Keine unzugeordneten Seiten."
            : "Keine Seiten in diesem Modul.";

          listEl.appendChild(div);
        }
      } else {
        if (existingHint) existingHint.remove();
      }
    });
  }

  function buildPayload() {
    const containers = lists.map((list) => {
      const raw = (list.dataset.moduleId || "").trim();
      const moduleId = raw ? parseInt(raw, 10) : null;

      const pageIds = Array.from(list.querySelectorAll(".page-card"))
        .map((el) => parseInt(el.dataset.pageId, 10));

      return { module_id: moduleId, page_ids: pageIds };
    });
    return { containers };
  }

  async function save() {
    const payload = buildPayload();

    try {
      const resp = await fetch(reorderUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
          "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify(payload)
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        console.error("Reorder failed:", data);

        alert(
          data.error ||
          "Die neue Seitenzuordnung konnte nicht gespeichert werden."
        );

        window.location.reload();
      }
    } catch (e) {
      console.error("Reorder request error:", e);

      alert("Die Seitenreihenfolge konnte nicht gespeichert werden.");

      window.location.reload();
    }
  }

  // Initial UI refresh
  refreshModuleUI();

  lists.forEach((list) => {
    new Sortable(list, {
      animation: 150,
      handle: ".js-drag-handle",
      draggable: ".page-card",

      // SortableJS übernimmt die Darstellung beim Ziehen
      forceFallback: true,
      fallbackOnBody: true,

      // Zulässige Modulzuordnungen
      group: {
        name: "pages",
        pull: true,
        put: (to, from, dragEl) => {
          return canDropPage(dragEl, to.el);
        },
      },

      // Ziehvorgang beginnt
      onStart: (evt) => {
        draggedPage = evt.item;

        document.addEventListener(
          "mousemove",
          updateDropCursor
        );
      },

      onAdd: () => refreshModuleUI(),
      onRemove: () => refreshModuleUI(),

      // Ziehvorgang endet
      onEnd: (evt) => {
        resetDropCursor();
        refreshModuleUI();

        // Nur speichern, wenn sich die Position geändert hat
        if (
          evt.from !== evt.to ||
          evt.oldIndex !== evt.newIndex
        ) {
          save();
        }
      },
    });
  });
});
