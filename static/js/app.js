(() => {
  const timers = new WeakMap();

  document.querySelectorAll('[data-autosave]').forEach((form) => {
    const schedule = () => {
      const status = form.querySelector('[data-save-status]');
      if (!status) return;
      status.textContent = 'Speichert …';
      clearTimeout(timers.get(form));
      timers.set(form, setTimeout(() => save(form, status), 700));
    };
    form.addEventListener('input', schedule);
    form.addEventListener('change', schedule);
  });

  async function save(form, status) {
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {'X-Requested-With': 'XMLHttpRequest'},
      });
      status.textContent = response.ok ? 'Gespeichert' : 'Nicht gespeichert – Eingaben prüfen';
      status.classList.toggle('save-error', !response.ok);
    } catch (_) {
      status.textContent = 'Speichern fehlgeschlagen – Verbindung prüfen';
      status.classList.add('save-error');
    }
  }

  document.querySelectorAll('[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  const activeJobs = document.querySelectorAll('[data-job-url] .status-queued, [data-job-url] .status-running');
  if (activeJobs.length) {
    window.setInterval(async () => {
      for (const badge of activeJobs) {
        const item = badge.closest('[data-job-url]');
        try {
          const response = await fetch(item.dataset.jobUrl, {headers: {'Accept': 'application/json'}});
          if (!response.ok) continue;
          const job = await response.json();
          if (job.status === 'succeeded' || job.status === 'failed') window.location.reload();
          badge.textContent = `${job.status_label} (${job.completed_parts}/${job.total_parts})`;
        } catch (_) {
          badge.textContent = 'Status derzeit nicht erreichbar';
        }
      }
    }, 5000);
  }
})();
