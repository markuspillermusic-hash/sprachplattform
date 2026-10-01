(() => {
  "use strict";
  const root = document.querySelector("#audio-studio");
  if (!root) return;
  const $ = (id) => document.getElementById(`studio-${id}`);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const names = {speech: "Sprache", music: "Musik", effects: "Geräusche"};
  const db = (value) => Math.pow(10, value / 20);
  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  let state, revision = 0, saved = "", selected = null, position = 0, zoom = 12;
  let assets = new Map(), history = [], jobs = [], generation = {}, undo = [], redo = [];
  let context, playing = false, nodes = [], started = 0, playFrom = 0, playUntil = 0, frame;
  let saving, polling, ready = false, loadingAudio = false, playbackToken = 0;
  const buffers = new Map();
  const length = (clip) => clip.trim_end - clip.trim_start;
  const duration = () => state ? Math.max(0, ...state.clips.map(c => c.start + length(c))) : 0;
  const time = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
  const message = (value = "") => { $("message").textContent = value; $("message").hidden = !value; };
  const safe = (fn) => async (event) => {
    if (event) event.preventDefault();
    try { message(); await fn(event); } catch (error) { message(error.message); }
  };
  const el = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text != null) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const action = (text, fn, className = "button button-quiet") => {
    const button = el("button", text, className);
    button.type = "button";
    button.addEventListener("click", safe(fn));
    return button;
  };
  async function api(name, data, isForm = false) {
    const options = {credentials: "same-origin", cache: "no-store"};
    if (data !== undefined) {
      options.method = "POST";
      options.headers = {"X-CSRFToken": root.querySelector("[name=csrfmiddlewaretoken]").value};
      if (isForm) options.body = data;
      else { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(data); }
    }
    const response = await fetch(root.dataset[`${name}Url`], options);
    let result;
    try { result = await response.json(); } catch { throw new Error("Die Anfrage konnte nicht verarbeitet werden. Prüfen Sie Verbindung, Anmeldung und Dateigröße."); }
    if (!response.ok) throw new Error(result.error || "Die Anfrage ist fehlgeschlagen. Laden Sie die Seite nach Prüfung Ihrer Anmeldung neu.");
    return result;
  }
  function mark() {
    const dirty = JSON.stringify(state) !== saved;
    $("save-status").textContent = saving ? "Wird gespeichert …" : dirty ? "Ungespeicherte Änderungen" : `Gespeichert · Stand ${revision}`;
    $("save").disabled = !ready || Boolean(saving) || !dirty;
    $("undo").disabled = !undo.length;
    $("redo").disabled = !redo.length;
    $("play").disabled = !ready || !state.clips.length || loadingAudio;
    $("stop").disabled = !ready;
    $("export").disabled = !ready || !state.clips.length || jobs.some(j => j.kind === "export" && ["queued", "running"].includes(j.status));
  }
  function checkpoint() {
    stop();
    undo.push(clone(state));
    if (undo.length > 60) undo.shift();
    redo = [];
  }
  function change(fn) { checkpoint(); fn(); render(); }
  function updatePosition(value) {
    position = clamp(value, 0, 1800);
    $("position").value = position.toFixed(2);
    $("time").textContent = `${time(position)} / ${time(duration())}`;
    root.querySelectorAll(".studio-playhead").forEach(p => { p.style.left = `${position * zoom}px`; });
  }
  function stop(reset = false) {
    playbackToken++;
    if (playing) position = clamp(playFrom + context.currentTime - started, 0, playUntil);
    playing = false;
    nodes.forEach(n => { try { n.stop(); } catch {} try { n.disconnect(); } catch {} });
    nodes = [];
    cancelAnimationFrame(frame);
    if (reset) position = 0;
    $("play").textContent = "▶ Abspielen";
    if (state) updatePosition(position);
  }
  function audible() {
    const solo = Object.values(state.tracks).some(t => t.solo);
    return new Set(Object.keys(names).filter(name => !state.tracks[name].mute && (!solo || state.tracks[name].solo)));
  }
  function intervals() {
    const result = [];
    state.clips.filter(c => c.track === "speech").sort((a,b) => a.start - b.start).forEach(c => {
      const last = result[result.length - 1];
      if (last && c.start <= last[1] + .3) last[1] = Math.max(last[1], c.start + length(c));
      else result.push([c.start, c.start + length(c)]);
    });
    return result;
  }
  async function getBuffer(assetId) {
    if (buffers.has(assetId)) return buffers.get(assetId);
    const asset = assets.get(assetId);
    if (!asset) throw new Error("Eine Audiodatei ist abgelaufen. Entfernen Sie den Clip oder fügen Sie die Datei erneut hinzu.");
    const response = await fetch(asset.url, {credentials: "same-origin", cache: "no-store"});
    if (!response.ok) throw new Error("Die Audiodatei ist nicht mehr verfügbar.");
    let buffer;
    try { buffer = await context.decodeAudioData(await response.arrayBuffer()); }
    catch { throw new Error("Der Browser konnte diese Audiodatei nicht öffnen."); }
    buffers.set(assetId, buffer);
    return buffer;
  }
  async function play(onlyId) {
    if (playing) { stop(); return; }
    root.querySelectorAll("audio").forEach(audio => audio.pause());
    if (!context) context = new (window.AudioContext || window.webkitAudioContext)();
    await context.resume();
    const allowed = audible();
    const clips = state.clips.filter(c => onlyId ? c.id === onlyId : allowed.has(c.track));
    if (!clips.length) throw new Error("Es sind keine hörbaren Clips ausgewählt.");
    if (onlyId) updatePosition(clips[0].start);
    const end = Math.max(...clips.map(c => c.start + length(c)));
    if (position >= end) updatePosition(onlyId ? clips[0].start : 0);
    const token = ++playbackToken;
    loadingAudio = true; mark();
    try {
      await Promise.all(clips.map(c => getBuffer(c.asset_id)));
      if (token !== playbackToken) return;
      playFrom = position; playUntil = end; started = context.currentTime + .06;
      const master = context.createGain(); master.gain.value = .8;
      const limiter = context.createDynamicsCompressor();
      limiter.threshold.value = -1; limiter.knee.value = 0; limiter.ratio.value = 20;
      limiter.attack.value = .003; limiter.release.value = .05;
      master.connect(limiter); limiter.connect(context.destination);
      nodes.push(master, limiter);
      const trackNodes = {};
      for (const name of Object.keys(names)) {
        const gain = context.createGain();
        gain.gain.value = db(state.tracks[name].gain_db);
        if (name === "speech" && state.speech_compression) {
          const compressor = context.createDynamicsCompressor(), makeup = context.createGain();
          compressor.threshold.value = -18; compressor.ratio.value = 3; compressor.knee.value = 6;
          compressor.attack.value = .01; compressor.release.value = .15; makeup.gain.value = db(3);
          gain.connect(compressor); compressor.connect(makeup); makeup.connect(master);
          nodes.push(compressor, makeup);
        } else gain.connect(master);
        trackNodes[name] = gain; nodes.push(gain);
        const duck = (name === "music" && state.ducking) || (name === "effects" && state.effects_ducking);
        if (!onlyId && duck && allowed.has("speech")) {
          const speech = intervals();
          const count = Math.max(2, Math.ceil((end - position) / .02) + 1);
          const values = new Float32Array(count);
          for (let i = 0; i < count; i++) {
            const t = position + i / (count - 1) * (end - position);
            const envelope = Math.max(0, ...speech.map(([s,e]) => Math.min(1, Math.max(0,(t - s + .15)/.15), Math.max(0,(e + .15 - t)/.15))));
            values[i] = db(state.tracks[name].gain_db) * (1 - (name === "music" ? .75 : .5) * envelope);
          }
          gain.gain.setValueCurveAtTime(values, started, end - position);
        }
      }
      for (const c of clips) {
        const passed = Math.max(0, position - c.start), remaining = length(c) - passed;
        if (remaining <= .001) continue;
        const source = context.createBufferSource(), gain = context.createGain();
        source.buffer = buffers.get(c.asset_id);
        source.connect(gain); gain.connect(trackNodes[c.track]);
        const when = started + Math.max(0, c.start - position), total = length(c);
        const factor = (t) => Math.min(1, c.fade_in ? t / c.fade_in : 1, c.fade_out ? (total - t) / c.fade_out : 1);
        gain.gain.setValueAtTime(db(c.gain_db) * factor(passed), when);
        if (c.fade_in > passed) gain.gain.linearRampToValueAtTime(db(c.gain_db), when + c.fade_in - passed);
        if (c.fade_out) {
          if (total - c.fade_out > passed) gain.gain.setValueAtTime(db(c.gain_db), when + total - c.fade_out - passed);
          gain.gain.linearRampToValueAtTime(0, when + remaining);
        }
        source.start(when, c.trim_start + passed, remaining); nodes.push(source, gain);
      }
      playing = true; $("play").textContent = "Ⅱ Pause";
      const tick = () => {
        if (!playing) return;
        updatePosition(playFrom + Math.max(0, context.currentTime - started));
        if (position >= playUntil) { stop(); updatePosition(playUntil); return; }
        frame = requestAnimationFrame(tick);
      };
      tick();
    } finally { loadingAudio = false; mark(); }
  }
  function drawWave(canvas, clip, width) {
    const asset = assets.get(clip.asset_id);
    if (!asset || !asset.waveform.length) return;
    canvas.width = Math.max(1, Math.min(2000, Math.round(width))); canvas.height = 38;
    const ctx = canvas.getContext("2d");
    ctx.strokeStyle = getComputedStyle(canvas.parentElement).color;
    ctx.globalAlpha = .65; ctx.beginPath();
    for (let x = 0; x < canvas.width; x += 2) {
      const t = clip.trim_start + x / canvas.width * length(clip);
      const peak = asset.waveform[Math.min(asset.waveform.length - 1, Math.floor(t / asset.duration * asset.waveform.length))];
      const h = Math.max(1, peak * 17);
      ctx.moveTo(x, 19 - h); ctx.lineTo(x, 19 + h);
    }
    ctx.stroke();
  }
  function inspector() {
    const c = state.clips.find(c => c.id === selected);
    $("clip-form").hidden = !c;
    $("clip-title").textContent = c ? (assets.get(c.asset_id)?.title || "Abgelaufene Audiodatei") : "Clip auf der Zeitachse auswählen";
    if (!c) return;
    for (const field of ["track", "start", "trim_start", "trim_end", "gain_db", "fade_in", "fade_out"]) {
      $("clip-form").elements[field].value = c[field];
    }
  }
  function select(id) {
    selected = id;
    root.querySelectorAll(".studio-clip").forEach(b => b.classList.toggle("is-selected", b.dataset.id === id));
    inspector();
  }
  function render() {
    if (!state) return;
    $("timeline").replaceChildren();
    const width = Math.max(650, (duration() + 10) * zoom);
    const labelWidth = window.innerWidth <= 780 ? 130 : 156;
    const step = zoom < 5 ? 30 : zoom < 15 ? 10 : zoom < 35 ? 5 : 1;
    const ruler = el("div", null, "studio-ruler"); ruler.style.width = `${width + labelWidth}px`;
    ruler.append(el("div", "Zeit (min:s)", "studio-ruler-label"));
    const ruleLane = el("div", null, "studio-ruler-lane");
    for (let t = 0; t < width / zoom; t += step) { const tick = el("span", time(t), "studio-tick"); tick.style.left = `${t * zoom}px`; ruleLane.append(tick); }
    ruleLane.addEventListener("click", e => { stop(); updatePosition((e.clientX - ruleLane.getBoundingClientRect().left)/zoom); });
    ruleLane.append(el("div", null, "studio-playhead")); ruler.append(ruleLane); $("timeline").append(ruler);
    for (const name of Object.keys(names)) {
      const row = el("div", null, `studio-track studio-track-${name}`); row.style.width = `${width + labelWidth}px`;
      const label = el("div", null, "studio-track-label"); label.append(el("strong", names[name]));
      const controls = el("div", null, "studio-track-buttons");
      for (const [key, text] of [["mute", "Stumm"], ["solo", "Solo"]]) {
        const l = el("label"); const input = el("input"); input.type = "checkbox"; input.checked = state.tracks[name][key];
        input.addEventListener("change", () => change(() => { state.tracks[name][key] = input.checked; })); l.append(input, document.createTextNode(text)); controls.append(l);
      }
      label.append(controls);
      const volume = el("label", "Pegel (dB)"); const input = el("input");
      input.type = "number"; input.min = -60; input.max = 12; input.value = state.tracks[name].gain_db;
      input.addEventListener("change", safe(() => {
        if (!input.checkValidity() || input.value === "") { render(); throw new Error("Der Spurpegel muss zwischen −60 und +12 dB liegen."); }
        change(() => { state.tracks[name].gain_db = Number(input.value); });
      })); volume.append(input); label.append(volume);
      const lane = el("div", null, "studio-lane"); lane.style.setProperty("--tick-width", `${zoom * step}px`);
      const placed = [];
      const clips = state.clips.filter(c => c.track === name).sort((a,b) => a.start - b.start);
      for (const c of clips) {
        let level = 0;
        while (placed[level]?.some(other => c.start < other.start + length(other) && c.start + length(c) > other.start)) level++;
        (placed[level] ||= []).push(c);
        const asset = assets.get(c.asset_id), w = Math.max(14, length(c) * zoom);
        const button = el("button", null, `studio-clip${c.id === selected ? " is-selected" : ""}${asset ? "" : " is-missing"}`);
        button.type = "button"; button.dataset.id = c.id; button.style.left = `${c.start * zoom}px`;
        button.style.top = `${10 + level * 76}px`; button.style.width = `${w}px`;
        button.setAttribute("aria-label", `${asset?.title || "Datei abgelaufen"}, ${names[name]}, Position ${c.start.toFixed(2)} Sekunden, Dauer ${length(c).toFixed(2)} Sekunden`);
        button.append(el("span", asset?.title || "Datei abgelaufen", "studio-clip-title"));
        const canvas = el("canvas"); canvas.setAttribute("aria-hidden", "true"); button.append(canvas);
        for (const side of ["in", "out"]) { const fade = el("span", null, `studio-fade studio-fade-${side}`); fade.style.width = `${c[`fade_${side}`] * zoom}px`; button.append(fade); }
        const curve = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        curve.classList.add("studio-fade-curve"); curve.setAttribute("aria-hidden", "true");
        curve.append(document.createElementNS("http://www.w3.org/2000/svg", "polyline")); button.append(curve);
        for (const side of ["in", "out"]) {
          const handle = el("span", null, `studio-fade-handle studio-fade-handle-${side}`);
          handle.dataset.fade = side; handle.setAttribute("aria-hidden", "true"); button.append(handle);
        }
        for (const side of ["left", "right"]) { const handle = el("span", null, `studio-trim-handle studio-trim-${side}`); handle.dataset.trim = side; handle.setAttribute("aria-hidden", "true"); button.append(handle); }
        updateFadeVisuals(button, c);
        button.addEventListener("click", () => select(c.id));
        button.addEventListener("pointerdown", e => drag(e, c, button));
        lane.append(button); row.append(label, lane); $("timeline").append(row); drawWave(canvas, c, w);
      }
      if (!clips.length) lane.append(el("span", "Audiodatei hinzufügen, um diese Spur zu belegen.", "studio-empty-lane"));
      lane.style.height = `${Math.max(150, placed.length * 76 + 20)}px`;
      lane.append(el("div", null, "studio-playhead")); row.append(label, lane); $("timeline").append(row);
    }
    $("ducking").checked = state.ducking;
    $("effects-ducking").checked = Boolean(state.effects_ducking);
    $("speech-compression").checked = Boolean(state.speech_compression);
    inspector(); updatePosition(position); mark();
  }
  function fitFades(c) {
    const sum = c.fade_in + c.fade_out, total = length(c);
    if (sum > total) { c.fade_in *= total / sum; c.fade_out *= total / sum; }
  }
  function updateFadeVisuals(button, c) {
    const width = Math.max(1, parseFloat(button.style.width) - 2), total = length(c);
    const fadeIn = c.fade_in / total * width, fadeOut = c.fade_out / total * width;
    let left = clamp(fadeIn - 8, 0, width - 16), right = width - 16 - clamp(fadeOut - 8, 0, width - 16);
    if (width >= 40 && right - left < 16) {
      const midpoint = (left + right) / 2 + 8;
      left = clamp(midpoint - 16, 0, width - 32); right = left + 16;
    }
    button.classList.toggle("studio-clip-compact", width < 40);
    for (const side of ["in", "out"]) {
      const value = side === "in" ? fadeIn : fadeOut;
      button.querySelector(`.studio-fade-${side}`).style.width = `${value}px`;
      const handle = button.querySelector(`.studio-fade-handle-${side}`);
      handle.style[side === "in" ? "left" : "right"] = `${side === "in" ? left : width - 16 - right}px`;
      handle.title = `${side === "in" ? "Einblenden" : "Ausblenden"}: ${c[`fade_${side}`].toFixed(2)} s · nach innen ziehen`;
    }
    const curve = button.querySelector(".studio-fade-curve");
    curve.setAttribute("viewBox", `0 0 ${width} 38`);
    const points = [];
    if (fadeIn) points.push("0,37");
    points.push(`${fadeIn},2`, `${width - fadeOut},2`);
    if (fadeOut) points.push(`${width},37`);
    curve.firstChild.setAttribute("points", points.join(" "));
  }
  function drag(event, c, button) {
    if (event.button !== 0) return;
    select(c.id); stop();
    const old = clone(state), initial = clone(c), x = event.clientX, side = event.target.dataset.trim, fade = event.target.dataset.fade;
    let moved = false; button.setPointerCapture(event.pointerId);
    const move = e => {
      const delta = Math.round((e.clientX - x) / zoom * 100) / 100;
      if (Math.abs(e.clientX - x) < 3 && !moved) return;
      moved = true;
      Object.assign(c, initial);
      if (fade) {
        const other = fade === "in" ? "fade_out" : "fade_in";
        c[`fade_${fade}`] = clamp(initial[`fade_${fade}`] + (fade === "in" ? delta : -delta), 0, length(initial) - initial[other]);
      } else if (side === "left") {
        const d = clamp(delta, -Math.min(initial.trim_start, initial.start), length(initial) - .01);
        c.start += d; c.trim_start += d;
      } else if (side === "right") c.trim_end = clamp(initial.trim_end + delta, initial.trim_start + .01, Math.min(assets.get(c.asset_id)?.duration || initial.trim_end, initial.trim_start + 1800 - c.start));
      else c.start = clamp(initial.start + delta, 0, 1800 - length(c));
      fitFades(c);
      button.style.left = `${c.start * zoom}px`; button.style.width = `${Math.max(14, length(c) * zoom)}px`;
      updateFadeVisuals(button, c);
      inspector();
    };
    const end = e => {
      button.removeEventListener("pointermove", move); button.removeEventListener("pointerup", end); button.removeEventListener("pointercancel", cancel);
      if (button.hasPointerCapture(event.pointerId)) button.releasePointerCapture(event.pointerId);
      if (moved) { undo.push(old); if (undo.length > 60) undo.shift(); redo = []; }
      render();
    };
    const cancel = e => { state = old; moved = false; end(e); };
    button.addEventListener("pointermove", move); button.addEventListener("pointerup", end); button.addEventListener("pointercancel", cancel);
  }
  function addAsset(asset) {
    if (state.clips.length >= 60) throw new Error("Es sind höchstens 60 Clips möglich.");
    assets.set(asset.id, asset);
    const choice = $("add-track").value;
    const track = choice === "auto" ? (names[asset.kind] ? asset.kind : "effects") : choice;
    const start = position;
    const remaining = Math.min(asset.duration, 1800 - start);
    if (remaining < .01) throw new Error("Setzen Sie die Abspielposition vor das Ende der 30 Minuten.");
    change(() => {
      const c = {id: crypto.randomUUID(), asset_id: asset.id, track, start, trim_start: 0, trim_end: remaining,
        gain_db: track === "music" ? -16 : track === "effects" ? -10 : 0, fade_in: 0, fade_out: 0};
      state.clips.push(c); selected = c.id;
    });
    renderLibrary();
  }
  function renderLibrary() {
    $("library").replaceChildren();
    const items = [...assets.values()].filter(a => a.kind !== "mix");
    if (!items.length) $("library").append(el("p", "Übernehmen Sie eine Sprachversion, laden Sie Audio hoch oder erzeugen Sie Musik und Geräusche.", "studio-hint"));
    for (const a of items) {
      const item = el("article", null, "studio-library-item"); const info = el("div");
      const availability = a.expires_at ? `verfügbar bis ${new Date(a.expires_at).toLocaleDateString("de-DE")}` : "Dauerhaftes Demo-Hörbeispiel";
      info.append(el("strong", a.title), el("small", `${names[a.kind] || "Eigene Datei"} · ${a.duration.toFixed(1)} s · ${availability}`));
      item.append(info, action("＋ Einfügen", () => addAsset(a), "button button-secondary"));
      const audio = el("audio"); audio.controls = true; audio.preload = "none"; audio.src = a.url;
      audio.setAttribute("aria-label", a.title); audio.addEventListener("play", () => stop()); item.append(audio); $("library").append(item);
    }
  }
  function renderJobs() {
    $("jobs").replaceChildren();
    for (const job of jobs) {
      const row = el("div", null, "studio-job");
      row.append(el("strong", `${job.kind === "export" ? `Mix · Stand ${job.revision}` : names[job.kind]} · ${job.label}`));
      if (job.error) row.append(el("p", job.error, "job-error"));
      if (job.asset) {
        assets.set(job.asset.id, job.asset);
        if (job.kind === "export") {
          const audio = el("audio"); audio.controls = true; audio.preload = "none"; audio.src = job.asset.url;
          audio.setAttribute("aria-label", job.asset.title); audio.addEventListener("play", () => stop()); row.append(audio);
          const link = el("a", "Mix herunterladen", "button button-secondary"); link.href = job.asset.download_url; row.append(link);
        } else row.append(action("In Spur einfügen", () => addAsset(job.asset)));
      }
      $("jobs").append(row);
    }
    mark();
    clearTimeout(polling);
    if (jobs.some(j => ["queued", "running"].includes(j.status))) polling = setTimeout(pollJobs, 2500);
  }
  async function pollJobs() {
    try {
      const data = await api("jobs");
      const old = JSON.stringify(jobs); jobs = data.jobs;
      if (old !== JSON.stringify(jobs)) { renderJobs(); renderLibrary(); }
      else polling = setTimeout(pollJobs, 2500);
    } catch (error) { message(error.message); polling = setTimeout(pollJobs, 10000); }
  }
  function generationInfo() {
    const form = $("generate-form"), kind = form.elements.kind.value, config = generation[kind];
    form.elements.duration.min = kind === "music" ? 3 : .5;
    form.elements.duration.max = kind === "music" ? 600 : 30;
    form.elements.duration.value = clamp(Number(form.elements.duration.value), Number(form.elements.duration.min), Number(form.elements.duration.max));
    $("loop-label").hidden = kind !== "effects";
    $("generate").disabled = !config?.enabled;
    $("generation-info").textContent = config?.enabled
      ? `Geschätzter Tarifwert: ${(Number(form.elements.duration.value) / 60 * Number(config.rate)).toFixed(4)} € · Monatskontingent: ${config.seconds_limit} s. ${kind === "effects" ? "Für längere Atmosphäre den Clip duplizieren." : "Musik wird ohne Gesang erzeugt."}`
      : "Die Administration muss diese Audioart unter Verwaltung → Musik- und Geräuschanbindung freigeben und einen Tarifwert hinterlegen.";
  }
  async function save() {
    if (saving) return saving;
    if (JSON.stringify(state) === saved) return;
    const snapshot = clone(state);
    saving = api("save", {revision, state: snapshot}); mark();
    try {
      const result = await saving;
      revision = result.revision; saved = JSON.stringify(result.state);
      if (JSON.stringify(state) === JSON.stringify(snapshot)) state = result.state;
      history.unshift({number: revision, state: clone(result.state)}); renderHistory();
    } finally { saving = null; mark(); }
  }
  function renderHistory() {
    $("history").replaceChildren(el("option", "Stand auswählen …")); $("history").firstChild.value = "";
    history.slice(0,20).forEach((h,i) => { const option = el("option", `Stand ${h.number}`); option.value = String(i); $("history").append(option); });
  }
  async function load() {
    if (saving) throw new Error("Warten Sie, bis der Stand gespeichert ist.");
    stop();
    const data = await api("state");
    state = data.state; revision = data.revision; saved = JSON.stringify(state); selected = null;
    assets = new Map(data.assets.map(a => [a.id,a])); buffers.clear(); undo = []; redo = [];
    history = data.history; jobs = data.jobs; generation = data.generation;
    zoom = clamp(($("timeline").clientWidth - (window.innerWidth <= 780 ? 130 : 156)) / Math.max(20, duration() + 8), 2, 60);
    $("zoom").value = zoom;
    $("speech").replaceChildren();
    if (!data.speech.length) { const option = el("option", "Zuerst im Skript Sprache erzeugen"); option.value = ""; $("speech").append(option); }
    data.speech.forEach(a => { const option = el("option", a.title); option.value = a.id; $("speech").append(option); });
    ready = true; render(); renderHistory(); renderJobs(); renderLibrary(); generationInfo();
  }
  $("save").addEventListener("click", safe(save));
  $("play").addEventListener("click", safe(() => play()));
  $("stop").addEventListener("click", () => stop(true));
  $("position").addEventListener("change", safe(() => { if (!$("position").checkValidity()) throw new Error("Die Abspielposition muss zwischen 0 und 1.800 Sekunden liegen."); const value = Number($("position").value); stop(); updatePosition(value); }));
  $("zoom").addEventListener("input", () => { zoom = Number($("zoom").value); render(); });
  $("undo").addEventListener("click", () => { if (!undo.length) return; stop(); redo.push(clone(state)); state = undo.pop(); render(); });
  $("redo").addEventListener("click", () => { if (!redo.length) return; stop(); undo.push(clone(state)); state = redo.pop(); render(); });
  $("ducking").addEventListener("change", () => { if (ready) change(() => { state.ducking = $("ducking").checked; }); });
  for (const [id, key] of [["effects-ducking", "effects_ducking"], ["speech-compression", "speech_compression"]]) {
    $(id).addEventListener("change", () => { if (ready) change(() => { state[key] = $(id).checked; }); });
  }
  $("reload").addEventListener("click", safe(async () => { if (!ready || JSON.stringify(state) === saved || window.confirm("Ungespeicherte Änderungen verwerfen und den gespeicherten Stand laden?")) await load(); }));
  $("history").addEventListener("change", safe(() => { if (!$("history").value) return; const h = history[Number($("history").value)]; change(() => { state = clone(h.state); selected = null; }); message(`Stand ${h.number} geladen. Speichern Sie ihn, um ihn als neuen Stand zu übernehmen.`); }));
  $("clip-form").addEventListener("submit", safe(() => {
    const c = state.clips.find(c => c.id === selected); if (!c) return;
    const next = clone(c), form = $("clip-form");
    for (const key of ["start", "trim_start", "trim_end", "gain_db", "fade_in", "fade_out"]) next[key] = Number(form.elements[key].value);
    next.track = form.elements.track.value;
    const asset = assets.get(next.asset_id);
    if (!asset || length(next) < .01 || next.trim_end > asset.duration + .001 || next.start + length(next) > 1800 || next.fade_in + next.fade_out > length(next) + .000001) throw new Error("Schnittgrenzen und Fades müssen innerhalb der Audiodatei liegen. Die Gesamtdauer darf 30 Minuten nicht überschreiten.");
    change(() => Object.assign(c,next));
  }));
  $("remove").addEventListener("click", () => change(() => { state.clips = state.clips.filter(c => c.id !== selected); selected = null; }));
  $("duplicate").addEventListener("click", safe(() => {
    const c = state.clips.find(c => c.id === selected); if (!c) return;
    if (state.clips.length >= 60 || c.start + length(c) * 2 > 1800) throw new Error("Der duplizierte Clip überschreitet die zulässige Clipzahl oder Gesamtdauer.");
    change(() => { const copy = clone(c); copy.id = crypto.randomUUID(); copy.start += length(c); state.clips.push(copy); selected = copy.id; });
  }));
  $("split").addEventListener("click", safe(() => {
    const c = state.clips.find(c => c.id === selected); if (!c) return;
    const cut = position - c.start;
    if (state.clips.length >= 60 || cut < .01 || cut > length(c) - .01) throw new Error("Setzen Sie die Abspielposition innerhalb des Clips; maximal 60 Clips sind möglich.");
    change(() => {
      const right = clone(c); right.id = crypto.randomUUID(); right.start = position;
      right.trim_start = c.trim_start + cut; right.fade_in = 0;
      c.trim_end = right.trim_start; c.fade_out = 0; fitFades(c); fitFades(right);
      state.clips.push(right); selected = right.id;
    });
  }));
  $("clip-play").addEventListener("click", safe(() => { if (playing) stop(); return play(selected); }));
  async function busyForm(form, operation) {
    const button = form.querySelector("button[type=submit]"); button.disabled = true;
    try { await operation(); } finally { button.disabled = false; }
  }
  $("import-form").addEventListener("submit", safe(() => busyForm($("import-form"), async () => {
    if (!$("speech").value) throw new Error("Erzeugen Sie zuerst im Skripteditor eine Sprachversion.");
    const result = await api("import", {asset_id: $("speech").value}); addAsset(result.asset);
  })));
  $("upload-form").addEventListener("submit", safe(() => busyForm($("upload-form"), async () => {
    const files = [...$("upload-form").elements.audio.files];
    if (!files.length || files.some(file => file.size > 50 * 1024 * 1024)) throw new Error("Wählen Sie Audiodateien mit jeweils höchstens 50 MB.");
    if (state.clips.length + files.length > 60) throw new Error("Die Auswahl überschreitet die Grenze von 60 Clips. Wählen Sie weniger Dateien.");
    const uploadPosition = position;
    for (const file of files) {
      const data = new FormData(); data.append("audio", file);
      const result = await api("upload", data, true);
      updatePosition(uploadPosition); addAsset(result.asset);
    }
    $("upload-form").reset();
  })));
  $("generate-form").elements.kind.addEventListener("change", generationInfo);
  $("generate-form").elements.duration.addEventListener("input", generationInfo);
  $("generate-form").addEventListener("submit", safe(() => busyForm($("generate-form"), async () => {
    const form = $("generate-form"); const result = await api("generate", {kind: form.elements.kind.value, prompt: form.elements.prompt.value, duration: Number(form.elements.duration.value), loop: form.elements.loop.checked});
    jobs.unshift(result.job); renderJobs(); renderLibrary();
  })));
  $("export-form").addEventListener("submit", safe(async () => {
    $("export").disabled = true;
    try {
      await save();
      if (JSON.stringify(state) !== saved) throw new Error("Während des Speicherns wurde weiterbearbeitet. Speichern Sie diese Änderungen vor dem Export.");
      const result = await api("export", {revision, format: $("export-form").elements.format.value});
      jobs.unshift(result.job); renderJobs();
    } finally { mark(); }
  }));
  window.addEventListener("beforeunload", e => { if (ready && JSON.stringify(state) !== saved) { e.preventDefault(); e.returnValue = ""; } });
  window.addEventListener("resize", () => { if (ready) render(); });
  safe(load)();
})();
