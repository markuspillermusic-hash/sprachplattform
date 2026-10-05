(() => {
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  document.querySelectorAll('select[data-voice-picker]').forEach(select => {
    const options = Array.from(select.options);
    const voices = options.filter(option => option.value);
    const empty = options.filter(option => !option.value);
    const tools = document.createElement('div');
    tools.className = 'voice-picker-tools';
    // Searching changes the view, not the saved production or speaker form.
    ['input', 'change'].forEach(type => tools.addEventListener(type, event => event.stopPropagation()));
    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'Name, Akzent oder Beschreibung suchen';
    search.setAttribute('aria-label', `Stimme suchen: ${select.labels[0]?.textContent.trim() || 'Stimme'}`);
    search.setAttribute('aria-controls', select.id);
    tools.append(search);
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Stimmen filtern';
    details.append(summary);
    const filters = document.createElement('div');
    filters.className = 'voice-picker-filters';
    const makeFilter = (label, values) => {
      const wrapper = document.createElement('label');
      wrapper.append(document.createTextNode(label));
      const field = document.createElement('select');
      field.setAttribute('aria-label', `${label}: ${select.labels[0]?.textContent.trim() || 'Stimme'}`);
      Object.entries(values).forEach(([value, text]) => field.add(new Option(text, value)));
      wrapper.append(field);
      filters.append(wrapper);
      return field;
    };
    const gender = makeFilter('Stimmtyp', {'': 'Alle Stimmtypen', female: 'Weiblich', male: 'Männlich', neutral: 'Neutral'});
    const age = makeFilter('Alter', {'': 'Alle Altersgruppen', young: 'Jung', middle_aged: 'Mittleres Alter', old: 'Älter'});
    const checkbox = text => {
      const label = document.createElement('label');
      label.className = 'voice-picker-checkbox';
      const input = document.createElement('input');
      input.type = 'checkbox';
      label.append(input, document.createTextNode(text));
      filters.append(label);
      return input;
    };
    const favorites = checkbox('Nur meine Favoriten');
    const recommended = checkbox('Für die Projektsprache empfohlen');
    details.append(filters);
    tools.append(details);
    const status = document.createElement('p');
    status.className = 'voice-picker-status';
    status.id = `${select.id}-voice-search-status`;
    status.setAttribute('role', 'status');
    tools.append(status);
    select.setAttribute('aria-describedby', [select.getAttribute('aria-describedby'), status.id].filter(Boolean).join(' '));
    select.before(tools);
    const form = select.closest('form');
    const language = form?.querySelector('[name="language"], [name="project-language"]') || document.querySelector('.project-meta [name="project-language"]');
    const fixedLanguage = select.dataset.projectLanguage || '';
    recommended.closest('label').hidden = !language && !fixedLanguage;
    const update = () => {
      const value = select.value;
      const targetLanguage = language?.value || fixedLanguage;
      const terms = normalize(search.value).split(/\s+/).filter(Boolean);
      let matches = 0;
      const visible = voices.filter(option => {
        const text = normalize(option.dataset.search || option.textContent);
        const match = terms.every(term => text.includes(term))
          && (!gender.value || option.dataset.gender === gender.value)
          && (!age.value || option.dataset.age === age.value)
          && (!favorites.checked || option.dataset.favorite === 'true')
          && (!recommended.checked || !targetLanguage || JSON.parse(option.dataset.languages || '[]').includes(targetLanguage));
        if (match) matches++;
        // Filtering never changes a saved/selected voice or silently clears it.
        return match || option.value === value;
      });
      select.replaceChildren(...empty, ...visible);
      select.value = value;
      const selectedOutside = value && !visible.some(option => option.value === value && terms.every(term => normalize(option.dataset.search || option.textContent).includes(term))
        && (!gender.value || option.dataset.gender === gender.value) && (!age.value || option.dataset.age === age.value)
        && (!favorites.checked || option.dataset.favorite === 'true')
        && (!recommended.checked || !targetLanguage || JSON.parse(option.dataset.languages || '[]').includes(targetLanguage)));
      status.textContent = `${matches} von ${voices.length} Stimmen${selectedOutside ? ' · Gewählte Stimme bleibt erhalten' : ''}`;
    };
    [search, gender, age, favorites, recommended].forEach(field => field.addEventListener(field === search ? 'input' : 'change', update));
    select.addEventListener('change', update);
    language?.addEventListener('change', update);
    update();
  });
})();
