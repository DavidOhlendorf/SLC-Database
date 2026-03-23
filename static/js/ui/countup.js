document.addEventListener("DOMContentLoaded", () => {
  const counters = document.querySelectorAll(".stat-number");

  const duration = 800; // Dauer der Animation in ms

  counters.forEach(counter => {
    const target = parseInt(counter.dataset.target, 10) || 0;
    const startTime = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // easing (macht es weicher als linear)
      const easeOut = 1 - Math.pow(1 - progress, 3);

      const currentValue = Math.floor(target * easeOut);

      counter.textContent = formatNumber(currentValue);

      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        counter.textContent = formatNumber(target);
      }
    }

    requestAnimationFrame(update);
  });

  function formatNumber(num) {
    return num.toLocaleString("de-DE");
  }
});