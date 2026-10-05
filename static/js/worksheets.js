(() => {
  const root = document.querySelector('[data-worksheet-status]');
  if (!root) return;
  if (['queued', 'running'].includes(root.dataset.worksheetStatus)) {
    let failures = 0;
    const poll = async () => {
      try {
        const response = await fetch(root.dataset.statusUrl, {headers: {Accept: 'application/json'}, cache: 'no-store'});
        if (!response.ok) throw new Error('status');
        const data = await response.json();
        if (['ready', 'failed'].includes(data.status)) { window.location.reload(); return; }
        failures = 0;
      } catch (_) { failures += 1; }
      if (failures >= 5) {
        root.querySelector('[data-poll-message]').textContent = 'Die Statusabfrage ist unterbrochen. Bitte laden Sie die Seite erneut.';
        return;
      }
      window.setTimeout(poll, 4000);
    };
    window.setTimeout(poll, 2500);
  }
  const form = document.getElementById('worksheet-edit-form');
  if (!form) return;
  let dirty = false;
  const markDirty = () => {
    dirty = true;
    form.querySelector('[data-dirty-message]').hidden = false;
    root.querySelectorAll('[data-worksheet-export]').forEach(link => link.setAttribute('aria-disabled', 'true'));
  };
  form.addEventListener('input', markDirty);
  form.addEventListener('change', markDirty);
  const requireSaved = event => {
    if (dirty) {event.preventDefault(); form.querySelector('button[type=submit]').focus();}
  };
  root.querySelectorAll('[data-worksheet-export]').forEach(link => link.addEventListener('click', requireSaved));
  root.querySelector('[data-worksheet-refine]')?.addEventListener('submit', requireSaved);
})();
