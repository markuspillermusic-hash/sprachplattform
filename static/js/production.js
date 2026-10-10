(() => {
  const brief = document.querySelector('[data-production-brief]');
  if (brief) {
    const language = brief.querySelector('[name=language]');
    const count = brief.querySelector('[name=speaker_count]');
    const format = brief.querySelector('[name=format]');
    const updateVoices = () => {
      const roles = format.value === 'monologue' ? 1 : Number(count.value);
      brief.querySelectorAll('select[name^="voice_"]').forEach(select => {
        const index = Number(select.name.slice(6));
        select.closest('.field').hidden = index > roles;
        select.disabled = index > roles;
      });
    };
    [language, count, format].forEach(field => field.addEventListener('change', updateVoices));
    updateVoices();
  }
  const root = document.querySelector('[data-production]');
  if (!root) return;
  const soundData = document.getElementById('production-sound-library');
  if (soundData) {
    const sounds = new Map(JSON.parse(soundData.textContent).map(a => [a.id, a]));
    root.querySelectorAll('select[name$="-library_id"]').forEach(select => {
      const cue = select.closest('.production-cue'), prefix = select.name.slice(0, -'library_id'.length);
      const audio = document.createElement('audio'); audio.controls = true; audio.preload = 'none'; audio.hidden = true;
      audio.setAttribute('aria-label', 'Gewähltes Bibliotheksgeräusch vorhören'); select.parentElement.append(audio);
      const sourceInfo = document.createElement('small'); select.parentElement.append(sourceInfo);
      const field = name => cue.querySelector(`[name="${prefix}${name}"]`);
      const update = (changed = false) => {
        const sound = sounds.get(select.value); audio.pause(); audio.hidden = !sound; sourceInfo.textContent = '';
        if (!sound) { audio.removeAttribute('src'); return; }
        audio.src = sound.url; sourceInfo.textContent = `${sound.description} · ${sound.loopable ? 'verlängerbar' : 'einmalig'} · keine neuen Audio-Credits`;
        if (changed) {
          field('asset_id').value = ''; field('prompt').value = ''; field('generation_duration').value = '0'; field('kind').value = 'effects';
          field('title').value = sound.title; field('duration').value = sound.loopable ? 120 : sound.duration;
          field('gain_db').value = sound.gain_db; field('fade_in').value = sound.fade_in; field('fade_out').value = sound.fade_out;
        }
      };
      select.addEventListener('change', () => update(true));
      field('asset_id').addEventListener('change', () => { if (field('asset_id').value) { select.value = ''; update(); } });
      audio.addEventListener('play', () => root.querySelectorAll('audio').forEach(other => { if (other !== audio) other.pause(); }));
      update();
    });
  }
  const scriptForm = root.querySelector('#production-script-form');
  if (scriptForm) {
    const container = scriptForm.querySelector('[data-script-lines]');
    const template = scriptForm.querySelector('[data-script-empty]');
    const total = scriptForm.querySelector('[name="script-TOTAL_FORMS"]');
    const maximum = Number(scriptForm.querySelector('[name="script-MAX_NUM_FORMS"]').value);
    const status = scriptForm.querySelector('[data-script-insert-status]');
    const renumber = () => {
      const rows = container.querySelectorAll('[data-script-row]');
      rows.forEach((row, index) => {
        row.querySelector('[data-script-number]').textContent = `Beitrag ${index + 1}`;
        row.querySelector('[data-script-add]').textContent = index === 0
          ? '＋ Sprechbeitrag am Anfang einfügen' : '＋ Sprechbeitrag hier einfügen';
        row.querySelectorAll('[name], [id], [for], [aria-describedby]').forEach((element) => {
          ['name', 'id', 'for', 'aria-describedby'].forEach((attribute) => {
            if (element.hasAttribute(attribute)) {
              element.setAttribute(attribute, element.getAttribute(attribute).replace(/script-\d+-/g, `script-${index}-`));
            }
          });
        });
      });
      total.value = rows.length;
    };
    container.addEventListener('click', (event) => {
      const button = event.target.closest('[data-script-add]');
      if (!button || button.disabled) return;
      if (Number(total.value) >= maximum) {
        status.textContent = `Es sind höchstens ${maximum} Sprechbeiträge möglich.`;
        return;
      }
      const fragment = template.content.cloneNode(true);
      fragment.querySelectorAll('[name], [id], [for]').forEach((element) => {
        ['name', 'id', 'for'].forEach((attribute) => {
          if (element.hasAttribute(attribute)) element.setAttribute(attribute, element.getAttribute(attribute).replaceAll('__prefix__', total.value));
        });
      });
      const row = fragment.querySelector('[data-script-row]');
      const nextRow = button.closest('[data-script-row]');
      if (nextRow) row.querySelector('[name$="-speaker"]').value = nextRow.querySelector('[name$="-speaker"]').value;
      container.insertBefore(fragment, nextRow || button);
      renumber();
      const text = row.querySelector('[data-script-text]');
      text.focus();
      text.dispatchEvent(new Event('input', {bubbles: true}));
      status.textContent = 'Sprechbeitrag eingefügt. Ergänzen Sie den Text und speichern Sie den Entwurf.';
    });
    renumber();
  }
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
