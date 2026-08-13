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
      let payload = {};
      try {
        payload = await response.json();
      } catch (_) {
        payload = {};
      }
      status.textContent = response.ok ? 'Gespeichert' : 'Nicht gespeichert – Eingaben prüfen';
      status.classList.toggle('save-error', !response.ok);
      if (response.ok && form.matches('[data-segment-autosave]')) {
        updateSegmentAppearance(form, payload.speaker);
      }
    } catch (_) {
      status.textContent = 'Speichern fehlgeschlagen – Verbindung prüfen';
      status.classList.add('save-error');
    }
  }

  function updateSegmentAppearance(form, speaker) {
    if (!speaker?.name || !speaker?.color) return;
    const card = form.closest('[data-segment-card]');
    if (!card) return;
    Array.from(card.classList).forEach((className) => {
      if (className.startsWith('segment-') && className !== 'segment-card') {
        card.classList.remove(className);
      }
    });
    card.classList.add(`segment-${speaker.color}`);
    const heading = card.querySelector('.segment-heading strong');
    if (heading) heading.textContent = speaker.name;
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

  const favoriteCount = document.querySelector('[data-favorite-count]');
  const favoriteStatus = document.querySelector('[data-favorite-status]');
  document.querySelectorAll('[data-favorite-form]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('.favorite-button');
      const card = form.closest('[data-voice-card]');
      if (!button || !card || button.disabled) return;

      button.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {'X-Requested-With': 'XMLHttpRequest'},
        });
        if (!response.ok) throw new Error('favorite request failed');
        const payload = await response.json();
        const isFavorite = Boolean(payload.is_favorite);
        const voiceName = form.dataset.voiceName || 'Stimme';
        const wasFavorite = button.getAttribute('aria-pressed') === 'true';

        card.classList.toggle('is-favorite', isFavorite);
        button.setAttribute('aria-pressed', String(isFavorite));
        button.setAttribute(
          'aria-label',
          isFavorite ? `${voiceName} aus Favoriten entfernen` : `${voiceName} als Favorit merken`,
        );
        button.title = isFavorite ? 'Aus Favoriten entfernen' : 'Als Favorit merken';
        const star = button.querySelector('[aria-hidden="true"]');
        if (star) star.textContent = isFavorite ? '★' : '☆';

        const heading = card.querySelector('.voice-card-heading > div');
        let kicker = heading?.querySelector('.favorite-kicker');
        if (isFavorite && heading && !kicker) {
          kicker = document.createElement('span');
          kicker.className = 'favorite-kicker';
          kicker.textContent = 'Persönlicher Favorit';
          heading.prepend(kicker);
        } else if (!isFavorite && kicker) {
          kicker.remove();
        }

        if (favoriteCount && wasFavorite !== isFavorite) {
          const currentCount = Number.parseInt(favoriteCount.textContent, 10) || 0;
          favoriteCount.textContent = String(Math.max(0, currentCount + (isFavorite ? 1 : -1)));
        }
        if (favoriteStatus) {
          favoriteStatus.textContent = isFavorite
            ? 'Als Favorit gespeichert. Die Reihenfolge ändert sich beim nächsten Laden.'
            : 'Aus den Favoriten entfernt. Die Reihenfolge ändert sich beim nächsten Laden.';
        }
      } catch (_) {
        if (favoriteStatus) favoriteStatus.textContent = 'Favorit konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.';
      } finally {
        button.disabled = false;
      }
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
