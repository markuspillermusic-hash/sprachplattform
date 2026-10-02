(() => {
  const brief = document.querySelector('[data-production-brief]');
  if (brief) {
    const language = brief.querySelector('[name=language]');
    const count = brief.querySelector('[name=speaker_count]');
    const format = brief.querySelector('[name=format]');
    const updateVoices = () => {
      const roles = format.value === 'monologue' ? 1 : Number(count.value);
      for (let index = 1; index <= 4; index++) {
        const select = brief.querySelector(`[name=voice_${index}]`);
        select.closest('.field').hidden = index > roles;
        select.disabled = index > roles;
        for (const option of select.options) {
          const languages = JSON.parse(option.dataset.languages || '[]');
          option.disabled = languages.length > 0 && !languages.includes(language.value);
          option.hidden = option.disabled;
        }
        if (select.selectedOptions[0]?.disabled) select.value = '';
      }
    };
    [language, count, format].forEach(field => field.addEventListener('change', updateVoices));
    updateVoices();
  }
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
