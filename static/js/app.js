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

  const voicePreviewDataElement = document.getElementById('voice-preview-data');
  let voicePreviewData = {};
  if (voicePreviewDataElement) {
    try {
      voicePreviewData = JSON.parse(voicePreviewDataElement.textContent);
    } catch (_) {
      voicePreviewData = {};
    }
  }

  document.querySelectorAll('[data-voice-select]').forEach((select) => {
    const form = select.closest('form');
    const panel = form?.querySelector('[data-voice-preview-panel]');
    const audio = panel?.querySelector('[data-voice-preview]');
    const label = panel?.querySelector('[data-voice-preview-label]');
    if (!panel || !audio || !label) return;

    const updatePreview = () => {
      const voice = voicePreviewData[select.value];
      audio.pause();
      audio.removeAttribute('src');
      audio.load();

      if (!voice?.url) {
        panel.hidden = true;
        return;
      }

      label.textContent = `Stimmenprobe: ${voice.name}`;
      audio.src = voice.url;
      audio.setAttribute('aria-label', `Stimmenprobe: ${voice.name}`);
      panel.hidden = false;
      audio.load();
    };

    select.addEventListener('change', updatePreview);
    updatePreview();
  });

  const catalogAudios = document.querySelectorAll('[data-catalog-audio]');
  catalogAudios.forEach((audio) => {
    audio.addEventListener('play', () => {
      catalogAudios.forEach((otherAudio) => {
        if (otherAudio !== audio) otherAudio.pause();
      });
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

  document.querySelectorAll('[data-assistant-prompt]').forEach((button) => {
    button.addEventListener('click', () => {
      const form = button.closest('.assistant-chat, form')?.querySelector('form[data-assistant-submit]')
        || button.closest('form[data-assistant-submit]');
      const input = form?.querySelector('[data-assistant-instruction]');
      if (!input) return;
      input.value = button.dataset.assistantPrompt;
      input.focus();
    });
  });

  const assistantLanguage = document.querySelector('.assistant-brief-card [name="language"]');
  const accentField = document.querySelector('.assistant-brief-card .field-english_accent');
  if (assistantLanguage && accentField) {
    const accentSelect = accentField.querySelector('select');
    const updateAccentVisibility = () => {
      const isEnglish = assistantLanguage.value === 'en';
      accentField.hidden = !isEnglish;
      if (!isEnglish && accentSelect) accentSelect.value = 'unspecified';
    };
    assistantLanguage.addEventListener('change', updateAccentVisibility);
    updateAccentVisibility();
  }
})();
