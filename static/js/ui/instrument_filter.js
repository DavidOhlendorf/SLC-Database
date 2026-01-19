document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll(".js-instr-filter");
  if (!buttons.length) return;

  const blocks = Array.from(document.querySelectorAll("[id^='block-'][data-instrument]"));
  if (!blocks.length) return;

  function setActive(btn) {
    buttons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  }

  function apply(filter) {
    blocks.forEach(block => {
      const instr = (block.dataset.instrument || "");

      if (filter === "all") {
        block.classList.remove("d-none");
      } else {

        if (instr === filter) block.classList.remove("d-none");
        else block.classList.add("d-none");
      }
    });
  }

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      setActive(btn);
      apply(filter);

      // Zustand in URL merken (optional, aber praktisch)
      const url = new URL(window.location.href);
      if (filter === "all") url.searchParams.delete("instr");
      else url.searchParams.set("instr", filter);
      window.history.replaceState({}, "", url);
    });
  });

  // Initialzustand aus URL (?instr=papi / ?instr=cawi / default all)
  const url = new URL(window.location.href);
  const initial = (url.searchParams.get("instr") || "all");
  const initialBtn = document.querySelector(`.js-instr-filter[data-filter="${initial}"]`);
  if (initialBtn) {
    setActive(initialBtn);
    apply(initial);
  } else {
    apply("all");
  }
});
