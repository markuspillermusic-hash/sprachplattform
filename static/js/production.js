(() => {
  const root = document.querySelector('[data-production]');
  if (!root) return;
  let dirty = false;
  document.querySelectorAll('[data-production-edit]').forEach(form => {
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', () => { dirty = false; });
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  async function refresh() {
    if (root.dataset.busy !== 'true') return;
    try {
      const result = await fetch(root.dataset.statusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (result.ok) {
        const data = await result.json();
        const label = root.querySelector('[data-production-progress]');
        if (label) label.textContent = data.progress;
        if (!data.busy && !dirty) { window.location.reload(); return; }
      }
    } catch (_) { /* Keep the saved production visible while connection recovers. */ }
    window.setTimeout(refresh, document.hidden ? 8000 : 1800);
  }
  refresh();
})();
