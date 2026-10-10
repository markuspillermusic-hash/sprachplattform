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
  let assets = new Map(), history = [], jobs = [], generation = {}, creditBudget = null, undo = [], redo = [];
  let context, playing = false, graph = null, started = 0, playFrom = 0, frame, playOnlyId = null;
  let syncTimer, syncRequest = 0, seekRevision = 0, appliedPlaybackState = "";
  const retiringGraphs = new Set(), bufferLoads = new Map();
  let saving, polling, ready = false, loadingAudio = false, playbackToken = 0;
  let clipClipboard = null, activeTrack = "speech", generationPlacement = null, dragging = false, generationSubmitting = false, menuScrollLeft = 0;
  let generationKind = "music";
  const generationDrafts = new Map();
  const hasLibrary = root.dataset.libraryEnabled === "true";
  let soundCatalog = [], soundRole = "atmosphere", soundChoice = null, soundStart = 0, soundReplace = null, soundBusy = false, soundToken = 0;
  let soundOpener = null;
  const pendingKey = `studio-generation:${root.dataset.stateUrl}`;
  let pendingInsertions = new Map();
  try { pendingInsertions = new Map(JSON.parse(sessionStorage.getItem(pendingKey) || "[]")); } catch {}
  const rememberInsertions = () => { try { sessionStorage.setItem(pendingKey, JSON.stringify([...pendingInsertions])); } catch {} };
  const menu = elMenu();
  function elMenu() {
    const node = document.createElement("div"); node.id = "studio-context-menu";
    node.className = "studio-context-menu"; node.hidden = true; node.setAttribute("role", "menu");
    node.setAttribute("aria-label", "Clip bearbeiten"); root.append(node); return node;
  }
  const buffers = new Map();
  const length = (clip) => clip.trim_end - clip.trim_start;
  const mixSettings = () => ({music_duck_db: state.ducking ? 4 : 0,
    effects_duck_db: state.effects_ducking ? 2 : 0, compression: state.speech_compression ? 35 : 0,
    duck_attack_ms: 250, duck_release_ms: 900, compressor_attack_ms: 25, compressor_release_ms: 350,
    ...state.mix});
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
    $("play").disabled = !ready || (!playing && (!state.clips.length || loadingAudio));
    $("stop").disabled = !ready;
    $("export").disabled = !ready || !state.clips.length || jobs.some(j => j.kind === "export" && ["queued", "running"].includes(j.status));
  }
  function checkpoint() {
    undo.push(clone(state));
    if (undo.length > 60) undo.shift();
    redo = [];
  }
  function change(fn) { checkpoint(); fn(); render(); }
  function updatePosition(value) {
    position = clamp(value, 0, 1800);
    if (document.activeElement !== $("position")) $("position").value = position.toFixed(2);
    $("time").textContent = `${time(position)} / ${time(duration())}`;
    root.querySelectorAll(".studio-playhead").forEach(p => { p.style.left = `${position * zoom}px`; });
  }
  const playbackPosition = (at = context?.currentTime || 0) => clamp(playFrom + Math.max(0, at - started), 0, 1800);
  function disposeGraph(value) {
    if (!value) return;
    clearTimeout(value.cleanup);
    value.nodes.forEach(node => { try { node.stop(); } catch {} try { node.disconnect(); } catch {} });
    retiringGraphs.delete(value);
  }
  function stop(reset = false) {
    playbackToken++;
    syncRequest++; clearTimeout(syncTimer); syncTimer = null;
    if (playing) position = playbackPosition();
    playing = false;
    disposeGraph(graph); graph = null;
    [...retiringGraphs].forEach(disposeGraph);
    cancelAnimationFrame(frame);
    if (reset) position = 0;
    $("play").textContent = "▶ Abspielen";
    if (state) updatePosition(position);
    if (state) mark();
  }
  function seek(value) {
    updatePosition(value);
    if (playing) { playFrom = clamp(value, 0, 1800); started = context.currentTime; seekRevision++; schedulePlaybackSync(); }
  }
  function audible() {
    const solo = Object.values(state.tracks).some(t => t.solo);
    return new Set(Object.keys(names).filter(name => !state.tracks[name].mute && (!solo || state.tracks[name].solo)));
  }
  function intervals() {
    const result = [];
    state.clips.filter(c => c.track === "speech").sort((a,b) => a.start - b.start).forEach(c => {
      const last = result[result.length - 1];
      if (last && c.start <= last[1] + mixSettings().duck_release_ms / 1000) last[1] = Math.max(last[1], c.start + length(c));
      else result.push([c.start, c.start + length(c)]);
    });
    return result;
  }
  async function getBuffer(assetId) {
    if (buffers.has(assetId)) return buffers.get(assetId);
    if (bufferLoads.has(assetId)) return bufferLoads.get(assetId);
    const asset = assets.get(assetId);
    if (!asset) throw new Error("Eine Audiodatei ist abgelaufen. Entfernen Sie den Clip oder fügen Sie die Datei erneut hinzu.");
    const loading = (async () => {
      const response = await fetch(asset.url, {credentials: "same-origin", cache: "no-store"});
      if (!response.ok) throw new Error("Die Audiodatei ist nicht mehr verfügbar.");
      let buffer;
      try { buffer = await context.decodeAudioData(await response.arrayBuffer()); }
      catch { throw new Error("Der Browser konnte diese Audiodatei nicht öffnen."); }
      buffers.set(assetId, buffer); return buffer;
    })();
    bufferLoads.set(assetId, loading);
    try { return await loading; } finally { bufferLoads.delete(assetId); }
  }
  const playbackClips = () => state.clips.filter(c => !playOnlyId || c.id === playOnlyId);
  const geometry = clips => JSON.stringify([seekRevision, clips.map(c => [c.id, c.asset_id, c.track, c.start, c.trim_start, c.trim_end])]);
  function hold(param, at) {
    // Removing the entire old curve also avoids Web Audio curve-overlap errors.
    // Retain the current level until the new automation starts.
    const value = param.value;
    param.cancelScheduledValues(0);
    param.setValueAtTime(value, context.currentTime);
    param.setValueAtTime(value, at);
  }
  function updatePlaybackParameters(value, clips, from, at, smooth = true) {
    const mix = mixSettings(), allowed = audible(), end = Math.max(from + .02, ...clips.map(c => c.start + length(c)));
    const speech = intervals();
    for (const name of Object.keys(names)) {
      const track = value.tracks[name], gain = track.gain.gain;
      const base = playOnlyId || allowed.has(name) ? db(state.tracks[name].gain_db) : 0;
      const duckDb = !playOnlyId && allowed.has("speech") ? (name === "music" ? mix.music_duck_db : name === "effects" ? mix.effects_duck_db : 0) : 0;
      const previous = gain.value; hold(gain, at);
      if (duckDb > 0 && base > 0) {
        const span = end - from, attack = mix.duck_attack_ms / 1000, release = mix.duck_release_ms / 1000;
        const count = Math.max(2, Math.ceil(span / .02) + 1), values = new Float32Array(count);
        for (let i = 0; i < count; i++) {
          const elapsed = i / (count - 1) * span, t = from + elapsed;
          const envelope = Math.max(0, ...speech.map(([s,e]) => Math.min(1, Math.max(0,(t - s + attack)/attack), Math.max(0,(e + release - t)/release))));
          const level = base * db(-duckDb * envelope * envelope * (3 - 2 * envelope));
          values[i] = smooth ? previous + (level - previous) * Math.min(1, elapsed / .02) : level;
        }
        gain.setValueCurveAtTime(values, at, span);
      } else {
        gain.setValueAtTime(smooth ? previous : base, at); gain.linearRampToValueAtTime(base, at + .02);
      }
      if (track.compressor) {
        const amount = mix.compression / 100;
        track.compressor.ratio.setTargetAtTime(1 + 2 * amount, at, .015);
        track.compressor.attack.setTargetAtTime(mix.compressor_attack_ms / 1000, at, .015);
        track.compressor.release.setTargetAtTime(mix.compressor_release_ms / 1000, at, .015);
        track.makeup.gain.setTargetAtTime(db(2 * amount), at, .015);
      }
    }
    for (const c of clips) {
      const gain = value.clips.get(c.id)?.gain.gain; if (!gain) continue;
      const total = length(c), passed = Math.max(0, from - c.start), remaining = total - passed;
      if (remaining <= .001) continue;
      const when = at + Math.max(0, c.start - from), ramp = smooth && passed > 0 ? Math.min(.012, remaining) : 0;
      const factor = t => Math.max(0, Math.min(1, c.fade_in ? t / c.fade_in : 1, c.fade_out ? (total - t) / c.fade_out : 1));
      hold(gain, at);
      if (ramp) gain.linearRampToValueAtTime(db(c.gain_db) * factor(passed + ramp), when + ramp);
      else gain.setValueAtTime(db(c.gain_db) * factor(passed), when);
      if (c.fade_in > passed + ramp) gain.linearRampToValueAtTime(db(c.gain_db), when + c.fade_in - passed);
      if (c.fade_out) {
        if (total - c.fade_out > passed + ramp) gain.setValueAtTime(db(c.gain_db), when + total - c.fade_out - passed);
        gain.linearRampToValueAtTime(0, when + remaining);
      }
    }
  }
  function createPlaybackGraph(clips, from, at, fade = false) {
    const value = {nodes: [], tracks: {}, clips: new Map(), signature: geometry(clips)};
    try {
      const master = context.createGain(), limiter = context.createDynamicsCompressor(); value.master = master;
      master.gain.setValueAtTime(fade ? 0 : .8, at); if (fade) master.gain.linearRampToValueAtTime(.8, at + .015);
      limiter.threshold.value = -1; limiter.knee.value = 0; limiter.ratio.value = 20;
      limiter.attack.value = .005; limiter.release.value = .25;
      master.connect(limiter); limiter.connect(context.destination); value.nodes.push(master, limiter);
      for (const name of Object.keys(names)) {
        const gain = context.createGain(), track = {gain}; value.tracks[name] = track; value.nodes.push(gain);
        if (name === "speech") {
          const compressor = context.createDynamicsCompressor(), makeup = context.createGain();
          compressor.threshold.value = -18; compressor.knee.value = 6;
          const mix = mixSettings();
          compressor.ratio.value = 1 + 2 * mix.compression / 100;
          compressor.attack.value = mix.compressor_attack_ms / 1000;
          compressor.release.value = mix.compressor_release_ms / 1000;
          makeup.gain.value = db(2 * mix.compression / 100);
          gain.connect(compressor); compressor.connect(makeup); makeup.connect(master);
          Object.assign(track, {compressor, makeup}); value.nodes.push(compressor, makeup);
        } else gain.connect(master);
      }
      for (const c of clips) {
        const passed = Math.max(0, from - c.start), remaining = length(c) - passed;
        if (remaining <= .001) continue;
        const source = context.createBufferSource(), gain = context.createGain(); source.buffer = buffers.get(c.asset_id);
        source.connect(gain); gain.connect(value.tracks[c.track].gain);
        value.clips.set(c.id, {source, gain}); value.nodes.push(source, gain);
        source.start(at + Math.max(0, c.start - from), c.trim_start + passed, remaining);
      }
      updatePlaybackParameters(value, clips, from, at, false);
      return value;
    } catch (error) { disposeGraph(value); throw error; }
  }
  function schedulePlaybackSync() {
    if (!playing) return;
    syncRequest++;
    if (syncTimer) return;
    syncTimer = setTimeout(async () => {
      syncTimer = null; const request = syncRequest, token = playbackToken;
      try {
        const snapshot = JSON.stringify(state); if (snapshot === appliedPlaybackState && graph?.signature === geometry(playbackClips())) return;
        await Promise.all(playbackClips().map(c => getBuffer(c.asset_id)));
        if (!playing || token !== playbackToken || request !== syncRequest) return;
        const clips = playbackClips(), at = context.currentTime + .012, from = playbackPosition(at);
        if (graph?.signature === geometry(clips)) updatePlaybackParameters(graph, clips, from, at);
        else {
          const old = graph; graph = createPlaybackGraph(clips, from, at, true);
          if (old) {
            hold(old.master.gain, at); old.master.gain.linearRampToValueAtTime(0, at + .015);
            retiringGraphs.add(old); old.cleanup = setTimeout(() => disposeGraph(old), 80);
          }
        }
        appliedPlaybackState = JSON.stringify(state);
      } catch (error) { if (playing && token === playbackToken) message(error.message); }
    }, 60);
  }
  async function play(onlyId) {
    if (playing) { stop(); return; }
    if (loadingAudio) return;
    root.querySelectorAll("audio").forEach(audio => audio.pause());
    if (!context) context = new (window.AudioContext || window.webkitAudioContext)();
    playOnlyId = onlyId || null;
    const clips = playbackClips(), allowed = audible();
    if (!clips.some(c => playOnlyId || allowed.has(c.track))) throw new Error("Es sind keine hörbaren Clips ausgewählt.");
    if (onlyId) updatePosition(clips[0].start);
    if (position >= Math.max(...clips.map(c => c.start + length(c)))) updatePosition(onlyId ? clips[0].start : 0);
    const token = ++playbackToken;
    loadingAudio = true; mark();
    try {
      await context.resume();
      // Edits made while loading may introduce another asset. Decode the latest selection.
      do {
        await Promise.all(playbackClips().map(c => getBuffer(c.asset_id)));
        if (token !== playbackToken) return;
      } while (playbackClips().some(c => !buffers.has(c.asset_id)));
      playFrom = position; started = context.currentTime + .06;
      graph = createPlaybackGraph(playbackClips(), playFrom, started);
      appliedPlaybackState = JSON.stringify(state);
      playing = true; $("play").textContent = "Ⅱ Pause";
      const tick = () => {
        if (!playing) return;
        updatePosition(playbackPosition());
        frame = requestAnimationFrame(tick);
      };
      tick();
    } finally { loadingAudio = false; mark(); }
  }
  function drawWave(canvas, clip, width) {
    const asset = assets.get(clip.asset_id);
    if (!asset || !asset.waveform.length) return;
    // The canvas represents the entire source. Trimming only moves or crops it.
    const sourceWidth = asset.duration * zoom;
    canvas.style.width = `${sourceWidth}px`;
    canvas.style.left = `${-clip.trim_start * zoom}px`;
    canvas.width = Math.max(1, Math.min(8192, Math.round(sourceWidth))); canvas.height = 38;
    const ctx = canvas.getContext("2d");
    ctx.strokeStyle = getComputedStyle(canvas.parentElement).color;
    ctx.globalAlpha = .65; ctx.beginPath();
    for (let x = 0; x < canvas.width; x += 2) {
      const t = x / canvas.width * asset.duration;
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
    $("change-duration").hidden = !hasLibrary || !c || !assets.get(c.asset_id)?.loopable;
    if (!c) return;
    for (const field of ["track", "start", "trim_start", "trim_end", "gain_db", "fade_in", "fade_out"]) {
      $("clip-form").elements[field].value = c[field];
    }
  }
  function select(id) {
    selected = id;
    const clip = state.clips.find(c => c.id === id);
    if (clip) activeTrack = clip.track;
    root.querySelectorAll(".studio-clip").forEach(b => b.classList.toggle("is-selected", b.dataset.id === id));
    inspector();
  }
  function render() {
    if (!state) return;
    const focusedTrackControl = document.activeElement?.dataset.trackControl;
    closeMenu();
    $("timeline").replaceChildren();
    const width = Math.max(650, (duration() + 10) * zoom);
    const labelWidth = window.innerWidth <= 780 ? 130 : 156;
    const step = zoom < 5 ? 30 : zoom < 15 ? 10 : zoom < 35 ? 5 : 1;
    const ruler = el("div", null, "studio-ruler"); ruler.style.width = `${width + labelWidth}px`;
    ruler.append(el("div", "Zeit (min:s)", "studio-ruler-label"));
    const ruleLane = el("div", null, "studio-ruler-lane");
    for (let t = 0; t < width / zoom; t += step) { const tick = el("span", time(t), "studio-tick"); tick.style.left = `${t * zoom}px`; ruleLane.append(tick); }
    ruleLane.addEventListener("click", e => seek((e.clientX - ruleLane.getBoundingClientRect().left)/zoom));
    ruleLane.append(el("div", null, "studio-playhead")); ruler.append(ruleLane); $("timeline").append(ruler);
    for (const name of Object.keys(names)) {
      const row = el("div", null, `studio-track studio-track-${name}`); row.style.width = `${width + labelWidth}px`;
      row.setAttribute("role", "group"); row.setAttribute("aria-label", `${names[name]}spur`);
      const label = el("div", null, "studio-track-label"); label.append(el("strong", names[name]));
      const controls = el("div", null, "studio-track-buttons");
      for (const [key, text] of [["mute", "Stumm"], ["solo", "Solo"]]) {
        const l = el("label"); const input = el("input"); input.type = "checkbox"; input.checked = state.tracks[name][key];
        input.dataset.trackControl = `${name}-${key}`; input.setAttribute("aria-label", `${text} · ${names[name]}`);
        input.addEventListener("change", () => change(() => { state.tracks[name][key] = input.checked; })); l.append(input, document.createTextNode(text)); controls.append(l);
      }
      label.append(controls);
      if (name !== "speech") label.append(action(name === "effects" && hasLibrary ? "＋ Geräusch hinzufügen" : `＋ ${names[name]}`, () => name === "effects" && hasLibrary ? openSounds(position) : openGeneration(name, position), "button button-quiet studio-track-add"));
      const volume = el("label", "Pegel (dB)"); const input = el("input");
      input.dataset.trackControl = `${name}-gain`; input.setAttribute("aria-label", `Pegel (dB) · ${names[name]}`);
      input.type = "number"; input.min = -60; input.max = 12; input.value = state.tracks[name].gain_db;
      input.addEventListener("change", safe(() => {
        if (!input.checkValidity() || input.value === "") { render(); throw new Error("Der Spurpegel muss zwischen −60 und +12 dB liegen."); }
        change(() => { state.tracks[name].gain_db = Number(input.value); });
      })); volume.append(input); label.append(volume);
      const lane = el("div", null, "studio-lane"); lane.dataset.track = name; lane.style.setProperty("--tick-width", `${zoom * step}px`);
      lane.addEventListener("click", e => {
        if (e.target.closest(".studio-clip") || dragging) return;
        closeMenu(); activeTrack = name;
        const target = clamp((e.clientX - lane.getBoundingClientRect().left) / zoom, 0, 1800);
        if (name === "effects" && hasLibrary) openSounds(target);
        else if (name !== "speech") openGeneration(name, target);
        else seek(target);
      });
      lane.addEventListener("contextmenu", e => {
        if (e.target.closest(".studio-clip")) return;
        e.preventDefault(); activeTrack = name;
        const target = clamp((e.clientX - lane.getBoundingClientRect().left) / zoom, 0, 1800);
        if (!playing) updatePosition(target);
        showLaneMenu(e.clientX, e.clientY, name, target);
      });
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
        const gainHandle = el("span", null, "studio-gain-handle"); gainHandle.dataset.gain = "true";
        gainHandle.setAttribute("aria-hidden", "true"); gainHandle.append(el("span", null, "studio-gain-value"));
        gainHandle.addEventListener("dblclick", e => { e.stopPropagation(); change(() => { c.gain_db = 0; }); });
        button.append(gainHandle);
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
        button.addEventListener("contextmenu", e => { e.preventDefault(); e.stopPropagation(); select(c.id); showClipMenu(e.clientX, e.clientY); });
        lane.append(button); row.append(label, lane); $("timeline").append(row); drawWave(canvas, c, w);
      }
      if (!clips.length) lane.append(el("span", name === "speech" ? "Sprachfassung übernehmen oder Audio hochladen." : name === "effects" && hasLibrary ? "Hier klicken: Atmosphäre oder Geräusch auswählen." : `Hier klicken, um ${names[name]} zu erzeugen.`, "studio-empty-lane"));
      lane.style.height = `${Math.max(150, placed.length * 76 + 20)}px`;
      lane.append(el("div", null, "studio-playhead")); row.append(label, lane); $("timeline").append(row);
    }
    renderMixSettings();
    inspector(); updatePosition(position); updateGainLabels(); mark(); schedulePlaybackSync();
    if (focusedTrackControl) {
      Array.from($("timeline").querySelectorAll("[data-track-control]"))
        .find(control => control.dataset.trackControl === focusedTrackControl)?.focus({preventScroll: true});
    }
  }
  function updateGainLabels() {
    const viewport = $("timeline").getBoundingClientRect();
    const labelWidth = window.innerWidth <= 780 ? 130 : 156;
    root.querySelectorAll(".studio-clip").forEach(button => {
      const label = button.querySelector(".studio-gain-value");
      const rect = button.getBoundingClientRect(), inset = button.classList.contains("studio-clip-compact") ? 2 : 8;
      const left = Math.max(inset, viewport.left + labelWidth + 5 - rect.left);
      const right = Math.min(rect.width - inset, viewport.right - 5 - rect.left);
      label.style.right = "auto";
      label.style.left = `${Math.max(0, Math.min(left + 2, right - label.offsetWidth) - inset)}px`;
    });
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
    const gainHandle = button.querySelector(".studio-gain-handle");
    gainHandle.style.top = `${clamp(c.gain_db >= 0 ? 38 - c.gain_db * 1.1 : 38 - c.gain_db * .3, 25, 52)}px`;
    gainHandle.title = `Cliplautstärke: ${c.gain_db.toFixed(1)} dB · hoch/runter ziehen · Umschalt für feine Schritte · Doppelklick: 0 dB`;
    gainHandle.firstChild.textContent = `${c.gain_db > 0 ? "+" : ""}${c.gain_db.toFixed(1)} dB`;
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
    closeMenu(); select(c.id);
    const old = clone(state), initial = clone(c), x = event.clientX, y = event.clientY,
      side = event.target.dataset.trim, fade = event.target.dataset.fade,
      gainDrag = Boolean(event.target.closest(".studio-gain-handle"));
    const copyGesture = (event.ctrlKey || event.metaKey) && !side && !fade && !gainDrag;
    if (copyGesture && state.clips.length >= 60) { message("Es sind höchstens 60 Clips möglich."); return; }
    let dragged = c, movingButton = button;
    let lastY = y, gainValue = initial.gain_db;
    const captureElement = gainDrag ? event.target.closest(".studio-gain-handle") : button;
    let moved = false, cancelled = false; captureElement.setPointerCapture(event.pointerId);
    const move = e => {
      const delta = Math.round((e.clientX - x) / zoom * 100) / 100;
      if (Math.abs((gainDrag ? e.clientY - y : e.clientX - x)) < 3 && !moved) return;
      if (!moved && copyGesture) {
        dragged = clone(initial); dragged.id = crypto.randomUUID(); state.clips.push(dragged);
        movingButton = button.cloneNode(true); movingButton.dataset.id = dragged.id;
        movingButton.classList.add("is-copying"); button.parentElement.append(movingButton); drawWave(movingButton.querySelector("canvas"), dragged); select(dragged.id);
      }
      moved = true;
      dragging = true;
      const id = dragged.id; Object.assign(dragged, initial, {id});
      if (gainDrag) {
        gainValue = clamp(gainValue + (lastY - e.clientY) * (e.shiftKey ? .05 : .4), -60, 12);
        lastY = e.clientY; dragged.gain_db = Math.round(gainValue * 10) / 10;
      } else if (fade) {
        const other = fade === "in" ? "fade_out" : "fade_in";
        dragged[`fade_${fade}`] = clamp(initial[`fade_${fade}`] + (fade === "in" ? delta : -delta), 0, length(initial) - initial[other]);
      } else if (side === "left") {
        const d = clamp(delta, -Math.min(initial.trim_start, initial.start), length(initial) - .01);
        dragged.start += d; dragged.trim_start += d;
      } else if (side === "right") dragged.trim_end = clamp(initial.trim_end + delta, initial.trim_start + .01, Math.min(assets.get(c.asset_id)?.duration || initial.trim_end, initial.trim_start + 1800 - c.start));
      else dragged.start = clamp(initial.start + delta, 0, 1800 - length(dragged));
      fitFades(dragged);
      movingButton.style.left = `${dragged.start * zoom}px`; movingButton.style.width = `${Math.max(14, length(dragged) * zoom)}px`;
      movingButton.querySelector("canvas").style.left = `${-dragged.trim_start * zoom}px`;
      updateFadeVisuals(movingButton, dragged); updateGainLabels();
      inspector(); schedulePlaybackSync();
    };
    const end = e => {
      button.removeEventListener("pointermove", move); button.removeEventListener("pointerup", end); button.removeEventListener("pointercancel", cancel);
      if (captureElement.hasPointerCapture(event.pointerId)) captureElement.releasePointerCapture(event.pointerId);
      if (moved) { undo.push(old); if (undo.length > 60) undo.shift(); redo = []; }
      if (moved || cancelled) render();
      else { inspector(); mark(); }
      // Suppress the click generated by releasing a drag over a free lane.
      setTimeout(() => { dragging = false; }, 0);
    };
    const cancel = e => { state = old; selected = c.id; moved = false; cancelled = true; end(e); };
    button.addEventListener("pointermove", move); button.addEventListener("pointerup", end); button.addEventListener("pointercancel", cancel);
  }
  function addAsset(asset, placement = null) {
    if (state.clips.length >= 60) throw new Error("Es sind höchstens 60 Clips möglich.");
    assets.set(asset.id, asset);
    const choice = $("add-track").value;
    const track = placement?.track || (choice === "auto" ? (names[asset.kind] ? asset.kind : "effects") : choice);
    const start = placement?.start ?? position;
    const remaining = Math.min(placement?.duration ?? asset.duration, asset.duration, 1800 - start);
    if (remaining < .01) throw new Error("Setzen Sie die Abspielposition vor das Ende der 30 Minuten.");
    change(() => {
      const c = {id: placement?.clip_id || crypto.randomUUID(), asset_id: asset.id, track, start, trim_start: 0, trim_end: remaining,
        gain_db: placement?.gain_db ?? (track === "music" ? -16 : track === "effects" ? -10 : 0), fade_in: placement?.fade_in || 0, fade_out: placement?.fade_out || 0};
      fitFades(c);
      state.clips.push(c); selected = c.id; activeTrack = track;
    });
    renderLibrary();
  }
  function renderLibrary() {
    $("library").replaceChildren();
    const filter = $("library-filter").value;
    const items = [...assets.values()].filter(a => a.kind !== "mix" && (filter === "all" || a.kind === filter));
    $("library-summary").textContent = `Sprache: ${[...assets.values()].filter(a => a.kind === "speech").length} · Musik: ${[...assets.values()].filter(a => a.kind === "music").length} · Geräusche: ${[...assets.values()].filter(a => a.kind === "effects").length}`;
    if (!items.length) $("library").append(el("p", "Übernehmen Sie eine Sprachversion, laden Sie Audio hoch oder erzeugen Sie Musik und Geräusche.", "studio-hint"));
    for (const a of items) {
      const item = el("article", null, "studio-library-item"); const info = el("div");
      const availability = a.expires_at ? `verfügbar bis ${new Date(a.expires_at).toLocaleDateString("de-DE")}` : "Dauerhaftes Demo-Hörbeispiel";
      info.append(el("strong", a.title), el("small", `${names[a.kind] || "Eigene Datei"} · ${a.duration.toFixed(1)} s · ${availability}`));
      item.append(info, action("＋ Einfügen", () => addAsset(a), "button button-secondary"));
      if (hasLibrary && ["effects", "upload"].includes(a.kind) && !a.library_id) item.append(action("Für Bibliothek vorschlagen", async () => { const result = await api("request", {asset_id: a.id, label: a.title}); message(result.message); }));
      const audio = el("audio"); audio.controls = true; audio.preload = "none"; audio.src = a.url;
      audio.setAttribute("aria-label", a.title); audio.addEventListener("play", () => stop()); item.append(audio); $("library").append(item);
    }
  }
  function closeMenu(focusClip = false) {
    menu.hidden = true;
    if (focusClip && selected) root.querySelector(`.studio-clip[data-id="${selected}"]`)?.focus({preventScroll: true});
  }
  function showMenu(x, y, entries) {
    menu.replaceChildren();
    for (const [label, shortcut, fn, enabled = true] of entries) {
      const item = action(null, () => { closeMenu(); fn(); }, "");
      item.append(el("span", label), el("small", shortcut)); item.disabled = !enabled;
      item.setAttribute("role", "menuitem"); menu.append(item);
    }
    menu.hidden = false;
    menuScrollLeft = $("timeline").scrollLeft;
    menu.style.left = `${clamp(x, 4, window.innerWidth - menu.offsetWidth - 4)}px`;
    menu.style.top = `${clamp(y, 4, window.innerHeight - menu.offsetHeight - 4)}px`;
    menu.querySelector("button:not(:disabled)")?.focus({preventScroll: true});
  }
  function copySelected() {
    const c = state.clips.find(c => c.id === selected); if (!c) return false;
    clipClipboard = clone(c); return true;
  }
  function removeSelected() {
    if (!state.clips.some(c => c.id === selected)) return;
    change(() => { state.clips = state.clips.filter(c => c.id !== selected); selected = null; });
  }
  function insertCopy(source, start, track = source.track) {
    if (!assets.has(source.asset_id)) throw new Error("Diese Audiodatei ist nicht mehr verfügbar.");
    if (state.clips.length >= 60 || start < 0 || start + length(source) > 1800) throw new Error("Der neue Clip überschreitet die zulässige Clipzahl oder Gesamtdauer.");
    change(() => {
      const copy = clone(source); copy.id = crypto.randomUUID(); copy.start = start; copy.track = track;
      state.clips.push(copy); selected = copy.id; activeTrack = track;
    });
  }
  function pasteClip(track = activeTrack, start = position) {
    if (!clipClipboard) return;
    insertCopy(clipClipboard, start, track);
  }
  function duplicateSelected() {
    const c = state.clips.find(c => c.id === selected); if (c) insertCopy(c, c.start + length(c));
  }
  function editSelected() {
    inspector(); $("clip-form").scrollIntoView({block: "center"}); $("clip-form").elements.start.focus({preventScroll: true});
  }
  function showClipMenu(x, y) {
    const c = state.clips.find(c => c.id === selected); if (!c) return;
    showMenu(x, y, [
      ["Clip bearbeiten …", "", editSelected],
      ["Kopieren", "Strg+C", copySelected],
      ["Ausschneiden", "Strg+X", () => { if (copySelected()) removeSelected(); }],
      ["Am Cursor einfügen", "Strg+V", () => pasteClip(), Boolean(clipClipboard)],
      ["Duplizieren", "Strg+D", duplicateSelected],
      ["Am Cursor teilen", "T", splitSelected, position > c.start + .01 && position < c.start + length(c) - .01],
      ["Löschen", "Entf", removeSelected],
    ]);
  }
  function showLaneMenu(x, y, track, start) {
    const entries = [["Hier einfügen", "Strg+V", () => pasteClip(track, start), Boolean(clipClipboard)]];
    if (track !== "speech") entries.unshift([`${names[track]} hier erzeugen …`, "", () => openGeneration(track, start)]);
    if (track === "effects" && hasLibrary) entries.unshift(
      ["Atmosphären auswählen …", "", () => openSounds(start, "atmosphere")],
      ["Einzelgeräusche auswählen …", "", () => openSounds(start, "oneshot")],
      ["Eigene Projektdateien …", "", () => openSounds(start, "project")]);
    showMenu(x, y, entries);
  }
  function openGeneration(track, start) {
    if (!ready || dragging || generationSubmitting) return;
    closeMenu(); activeTrack = track;
    const target = clamp(start, 0, 1800);
    if (!playing) updatePosition(target);
    generationPlacement = {track, start: target};
    $("generate-form").elements.kind.value = track;
    $("generation-error").hidden = true;
    generationInfo();
    if (!$("generate-dialog").open) $("generate-dialog").showModal();
    $("generate-form").elements.prompt.focus();
  }
  function renderJobs() {
    $("jobs").replaceChildren();
    for (const job of jobs) {
      if (pendingInsertions.has(job.id) && ["succeeded", "failed"].includes(job.status)) {
        const placement = pendingInsertions.get(job.id); pendingInsertions.delete(job.id); rememberInsertions();
        if (job.status === "failed") message(job.error || "Die Audioerzeugung wurde nicht abgeschlossen. Ihr Prompt bleibt im Erzeugungsfenster erhalten.");
        if (job.asset && job.status === "succeeded" && !state.clips.some(c => placement.clip_id ? c.id === placement.clip_id : c.asset_id === job.asset.id)) {
          try {
            if (placement.replace) {
              const current = state.clips.find(c => c.id === placement.replace.id);
              assets.set(job.asset.id, job.asset);
              if (!current || JSON.stringify(current) !== JSON.stringify(placement.replace)) throw new Error("Der Clip wurde inzwischen geändert. Die verlängerte Datei bleibt in den Projektdateien.");
              change(() => { current.asset_id = job.asset.id; current.trim_end = current.trim_start + placement.duration; fitFades(current); });
            } else addAsset(job.asset, placement);
            message(`${names[placement.track]} wurde bei ${time(placement.start)} eingefügt. Speichern Sie Ihren Stand.`); }
          catch (error) { message(`${error.message} Das fertige Audio bleibt in der Bibliothek und kann später eingefügt werden.`); }
        }
      }
      const row = el("div", null, "studio-job");
      row.append(el("strong", `${job.kind === "export" ? `Mix · Stand ${job.revision}` : job.kind === "library_prepare" ? "Bibliotheksaudio · keine neuen Credits" : names[job.kind]} · ${job.label}`));
      if (job.error) row.append(el("p", job.error, "job-error"));
      if (job.asset) {
        assets.set(job.asset.id, job.asset);
        if (job.kind === "export") {
          const audio = el("audio"); audio.controls = true; audio.preload = "none"; audio.src = job.asset.url;
          audio.setAttribute("aria-label", job.asset.title); audio.addEventListener("play", () => stop()); row.append(audio);
          const link = el("a", "Mix herunterladen", "button button-secondary"); link.href = job.asset.download_url; row.append(link);
        } else row.append(action(job.placement ? `Bei ${time(job.placement.start)} einfügen` : "In Spur einfügen", () => addAsset(job.asset, {...job.placement, duration: job.duration})));
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
    if (kind !== generationKind) {
      generationDrafts.set(generationKind, {prompt: form.elements.prompt.value, duration: form.elements.duration.value, loop: form.elements.loop.checked});
      const draft = generationDrafts.get(kind) || {prompt: "", duration: kind === "music" ? 15 : 3, loop: false};
      form.elements.prompt.value = draft.prompt; form.elements.duration.value = draft.duration; form.elements.loop.checked = draft.loop;
      generationKind = kind;
    }
    $("dialog-title").textContent = kind === "music" ? "Musik oder Jingle erzeugen" : "Geräusch oder Atmosphäre erzeugen";
    form.elements.prompt.placeholder = kind === "music" ? "Zum Beispiel: ruhige instrumentale Klaviermusik für eine geheimnisvolle Waldszene, ohne Gesang" : "Zum Beispiel: eine Holztür öffnet sich langsam und knarrt, ohne Sprache und Musik";
    form.elements.duration.min = kind === "music" ? 3 : .5;
    const maximum = Math.min(kind === "music" ? 600 : 30, 1800 - (generationPlacement?.start || 0));
    form.elements.duration.max = maximum;
    if (maximum >= Number(form.elements.duration.min)) form.elements.duration.value = clamp(Number(form.elements.duration.value), Number(form.elements.duration.min), maximum);
    $("loop-label").hidden = kind !== "effects";
    $("generation-length-label").hidden = kind !== "effects" || !form.elements.loop.checked;
    $("generate").disabled = generationSubmitting || !config?.enabled || maximum < Number(form.elements.duration.min);
    if (generationPlacement) {
      generationPlacement.track = kind;
      $("generation-placement").textContent = `Einfügen auf „${names[kind]}“ bei ${time(generationPlacement.start)} (${generationPlacement.start.toFixed(2)} s). Das fertige Audio wird an dieser Stelle als Clip eingefügt.`;
    }
    root.querySelectorAll("[data-studio-generate]").forEach(button => { button.disabled = !ready; });
    $("generation-info").textContent = config?.enabled
      ? `Geschätzter Verbrauch: ${Math.ceil(Number(form.elements.duration.value) * config.credits_per_second).toLocaleString("de-DE")} Credits · ca. ${(Number(form.elements.duration.value) / 60 * Number(config.rate)).toLocaleString("de-DE", {maximumFractionDigits: 4})} EUR · persönliches Monatskontingent: ${(config.seconds_limit / 60).toLocaleString("de-DE")} min.${creditBudget ? ` Gemeinsamer Rahmen beim Laden: ${Math.floor(creditBudget.remaining).toLocaleString("de-DE")} Credits verfügbar.` : ""} ${kind === "effects" ? "Nur die erzeugte Quelle wird berechnet. Wiederholbare Atmosphäre kann lokal verlängert werden." : "Musik wird ohne Gesang erzeugt."}`
      : "Die Administration muss diese Audioart unter Verwaltung → Musik- und Geräuschanbindung freigeben und einen Tarifwert hinterlegen.";
    if (maximum < Number(form.elements.duration.min)) $("generation-info").textContent = "An dieser Position ist nicht genug Platz. Setzen Sie den Cursor vor das Ende der 30 Minuten.";
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
    const data = await api("state");
    state = data.state; revision = data.revision; saved = JSON.stringify(state); selected = null;
    assets = new Map(data.assets.map(a => [a.id,a])); if (!playing && !loadingAudio) buffers.clear(); undo = []; redo = [];
    history = data.history; jobs = data.jobs; generation = data.generation; creditBudget = data.credit_budget;
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
  $("position").addEventListener("change", safe(() => { if (!$("position").checkValidity()) throw new Error("Die Abspielposition muss zwischen 0 und 1.800 Sekunden liegen."); const value = Number($("position").value); seek(value); }));
  $("zoom").addEventListener("input", () => { zoom = Number($("zoom").value); render(); });
  function undoEdit(forward = false) {
    const source = forward ? redo : undo, target = forward ? undo : redo;
    if (!source.length) return;
    target.push(clone(state)); state = source.pop(); render();
  }
  $("undo").addEventListener("click", () => undoEdit());
  $("redo").addEventListener("click", () => undoEdit(true));
  $("timeline").addEventListener("scroll", () => {
    updateGainLabels(); if (!menu.hidden && $("timeline").scrollLeft !== menuScrollLeft) closeMenu();
  }, {passive: true});
  document.addEventListener("pointerdown", e => { if (!menu.contains(e.target)) closeMenu(); }, true);
  menu.addEventListener("keydown", e => {
    if (!["ArrowDown", "ArrowUp", "Home", "End", "Escape"].includes(e.key)) return;
    e.preventDefault(); e.stopPropagation();
    if (e.key === "Escape") { closeMenu(true); return; }
    const items = [...menu.querySelectorAll("button:not(:disabled)")], index = items.indexOf(document.activeElement);
    const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (index + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items[next]?.focus();
  });
  function renderMixSettings() {
    const mix = mixSettings();
    root.querySelectorAll("[data-mix]").forEach(input => {
      const key = input.dataset.mix, value = mix[key]; input.value = value;
      $(`${input.id.slice(7)}-value`).textContent = key.endsWith("_db") ? (value ? `${value} dB` : "Aus")
        : key === "compression" ? (value ? `${value} %` : "Aus") : `${value} ms`;
    });
  }
  root.querySelectorAll("[data-mix]").forEach(input => {
    input.addEventListener("input", () => {
      if (!ready) return;
      // One undo step per slider gesture, including keyboard changes.
      if (!input.dataset.editing) { checkpoint(); input.dataset.editing = "true"; }
      state.mix = {...mixSettings(), [input.dataset.mix]: Number(input.value)};
      state.ducking = state.mix.music_duck_db > 0; state.effects_ducking = state.mix.effects_duck_db > 0;
      state.speech_compression = state.mix.compression > 0;
      renderMixSettings(); mark(); schedulePlaybackSync();
    });
    input.addEventListener("change", () => { delete input.dataset.editing; });
    input.addEventListener("blur", () => { delete input.dataset.editing; });
  });
  $("library-filter").addEventListener("change", renderLibrary);
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
  $("remove").addEventListener("click", removeSelected);
  $("duplicate").addEventListener("click", safe(duplicateSelected));
  function splitSelected() {
    if (playing) updatePosition(playbackPosition());
    const c = state.clips.find(c => c.id === selected); if (!c) return;
    const cut = position - c.start;
    if (state.clips.length >= 60 || cut < .01 || cut > length(c) - .01) throw new Error("Setzen Sie die Abspielposition innerhalb des Clips; maximal 60 Clips sind möglich.");
    change(() => {
      const right = clone(c); right.id = crypto.randomUUID(); right.start = position;
      right.trim_start = c.trim_start + cut; right.fade_in = 0;
      c.trim_end = right.trim_start; c.fade_out = 0; fitFades(c); fitFades(right);
      state.clips.push(right); selected = right.id;
    });
  }
  $("split").addEventListener("click", safe(splitSelected));
  window.addEventListener("keydown", e => {
    if (!ready || e.isComposing || $("generate-dialog").open || $("sounds-dialog").open || dragging) return;
    if (e.target.closest("input, textarea, select, audio, [contenteditable]:not([contenteditable=false])")) return;
    const key = e.key.toLowerCase();
    if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
      const button = root.querySelector(`.studio-clip[data-id="${selected}"]`); if (!button) return;
      e.preventDefault(); const rect = button.getBoundingClientRect(); showClipMenu(rect.left + 20, rect.top + 20); return;
    }
    const modifier = e.ctrlKey || e.metaKey;
    let fn;
    if (modifier && !e.altKey) {
      if (key === "z") fn = () => undoEdit(e.shiftKey);
      else if (key === "y") fn = () => undoEdit(true);
      else if (key === "v" && clipClipboard) fn = () => pasteClip();
      else if (selected && state.clips.some(c => c.id === selected)) {
        if (key === "c") fn = copySelected;
        else if (key === "x") fn = () => { if (copySelected()) removeSelected(); };
        else if (key === "d") fn = duplicateSelected;
      }
    } else if (!modifier && !e.altKey) {
      if (key === "t") fn = splitSelected;
      else if (key === " ") fn = () => play();
      else if (["delete", "backspace"].includes(key) && selected) fn = removeSelected;
      else if (key === "escape") fn = () => closeMenu(true);
    }
    if (!fn) return;
    e.preventDefault();
    if (e.repeat || (key === " " && loadingAudio)) return;
    closeMenu(); safe(fn)();
  });
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
    const uploadPosition = position, choice = $("add-track").value;
    for (const file of files) {
      const data = new FormData(); data.append("audio", file);
      const result = await api("upload", data, true);
      addAsset(result.asset, {start: uploadPosition, track: choice === "auto" ? (names[result.asset.kind] ? result.asset.kind : "effects") : choice});
    }
    $("upload-form").reset();
  })));
  $("generate-form").elements.kind.addEventListener("change", generationInfo);
  $("generate-form").elements.duration.addEventListener("input", generationInfo);
  $("generate-form").elements.loop.addEventListener("change", generationInfo);
  root.querySelectorAll("[data-studio-generate]").forEach(button => button.addEventListener("click", () => openGeneration(button.dataset.studioGenerate, position)));
  $("dialog-close").addEventListener("click", () => $("generate-dialog").close());
  $("dialog-cancel").addEventListener("click", () => $("generate-dialog").close());
  $("generate-form").addEventListener("submit", async e => {
    e.preventDefault(); if (generationSubmitting) return;
    const form = $("generate-form"), placement = clone(generationPlacement);
    generationSubmitting = true; generationInfo(); $("generation-error").hidden = true;
    try {
      if (state.clips.length >= 60) throw new Error("Es sind höchstens 60 Clips möglich. Entfernen Sie zuerst einen Clip oder erzeugen Sie das Audio später.");
      const result = await api("generate", {kind: form.elements.kind.value, prompt: form.elements.prompt.value,
        duration: Number(form.elements.duration.value), loop: form.elements.kind.value === "effects" && form.elements.loop.checked,
        playback_duration: form.elements.kind.value === "effects" && form.elements.loop.checked && form.elements.playback_duration.value ? Number(form.elements.playback_duration.value) : Number(form.elements.duration.value), placement});
      pendingInsertions.set(result.job.id, {...placement, duration: result.job.duration}); rememberInsertions(); jobs.unshift(result.job);
      $("generate-dialog").close(); message(`Audio wird für „${names[placement.track]}“ bei ${time(placement.start)} erzeugt und anschließend dort eingefügt.`);
      renderJobs(); renderLibrary();
    } catch (error) {
      $("generation-error").textContent = error.message; $("generation-error").hidden = false;
      if (!$("generate-dialog").open) message(error.message);
    } finally { generationSubmitting = false; generationInfo(); }
  });
  function soundDuration() {
    const mode = $("sounds-duration").value;
    if (mode === "natural") return soundChoice?.duration || 0;
    if (mode === "custom") return Number($("sounds-custom").value);
    if (mode === "speech") return Math.max(0, ...state.clips.filter(c => c.track === "speech").map(c => c.start + length(c))) - soundStart;
    return Number(mode);
  }
  function updateSoundSelection() {
    $("sounds-custom-label").hidden = $("sounds-duration").value !== "custom";
    const seconds = soundDuration();
    $("sounds-insert").disabled = soundBusy || !soundChoice || !Number.isFinite(seconds) || seconds < .01 || soundStart + seconds > 1800 || (!soundChoice.loopable && seconds > soundChoice.duration + .001);
    $("sounds-selection").textContent = soundChoice ? `${soundChoice.title} · ${Number.isFinite(seconds) ? seconds.toFixed(2) : "–"} Sekunden · ${soundRole === "project" ? "vorhandene Projektdatei" : "Bibliothek"} · keine neue Geräuschgenerierung` : "Eine Quelle auswählen und bei Bedarf vorhören.";
    if (soundReplace) $("sounds-insert").textContent = "Dauer übernehmen";
    else $("sounds-insert").textContent = "In Geräuschespur einfügen";
  }
  function chooseSound(sound) {
    soundChoice = sound;
    if (!soundReplace) {
      const speechEnd = Math.max(0, ...state.clips.filter(c => c.track === "speech").map(c => c.start + length(c)));
      $("sounds-duration").value = sound.loopable ? (speechEnd > soundStart ? "speech" : "120") : "natural";
    }
    renderSounds();
  }
  function renderSounds() {
    const list = $("sounds-list"); list.replaceChildren();
    const query = $("sounds-search").value.trim().toLocaleLowerCase("de-DE"), category = $("sounds-category").value;
    const options = soundRole === "project" ? [...assets.values()].filter(a => ["effects", "upload"].includes(a.kind)) : soundCatalog.filter(a => a.role === soundRole);
    const items = options.filter(a => (!category || soundRole === "project" || a.category === category) && `${a.title} ${a.description || ""} ${a.tags || ""} ${a.category_label || ""}`.toLocaleLowerCase("de-DE").includes(query));
    if (!items.length) list.append(el("p", "Kein passendes Geräusch gefunden. Kategorie ändern, neu generieren oder den fehlenden Wunsch vormerken.", "studio-hint"));
    for (const sound of items) {
      const row = el("article", null, `studio-sound-row${soundChoice?.id === sound.id ? " is-selected" : ""}`);
      const choice = action(sound.title, () => chooseSound(sound), "studio-sound-choice");
      choice.setAttribute("aria-pressed", String(soundChoice?.id === sound.id));
      const info = el("div"); info.append(choice, el("p", sound.description || "Audio aus diesem Projekt"), el("small", `${sound.duration.toFixed(1)} s${sound.loopable ? " · verlängerbar" : " · einmalig"}`));
      const audio = el("audio"); audio.controls = true; audio.preload = "none"; audio.src = sound.url; audio.setAttribute("aria-label", `${sound.title} vorhören`);
      audio.addEventListener("play", () => { stop(); $("sounds-list").querySelectorAll("audio").forEach(other => { if (other !== audio) other.pause(); }); });
      row.append(info, audio); list.append(row);
    }
    root.querySelectorAll("[data-sound-role]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.soundRole === soundRole)));
    updateSoundSelection();
  }
  async function openSounds(start, role = "atmosphere", replace = null) {
    if (!ready || dragging || !hasLibrary || soundBusy) return;
    closeMenu(); soundOpener = document.activeElement; soundStart = clamp(start, 0, 1800); soundRole = role; soundReplace = replace ? clone(replace) : null; soundChoice = null;
    $("sounds-error").hidden = true; $("sounds-search").value = ""; $("sounds-category").value = "";
    $("sounds-insert").disabled = true;
    $("sounds-title").textContent = replace ? "Dauer der Atmosphäre ändern" : "Geräusch hinzufügen";
    if (replace) { soundChoice = assets.get(replace.asset_id); $("sounds-duration").value = "custom"; $("sounds-custom").value = length(replace); }
    $("sounds-position").textContent = `Geräuschespur bei ${time(soundStart)} (${soundStart.toFixed(2)} s). Die Einfügestelle bleibt während des Vorhörens erhalten.`;
    const token = ++soundToken;
    if (!$("sounds-dialog").open) $("sounds-dialog").showModal();
    $("sounds-search").focus();
    $("sounds-list").replaceChildren(el("p", "Geräusche werden geladen …"));
    try {
      const data = await api("catalog"); if (token !== soundToken || !$("sounds-dialog").open) return;
      soundCatalog = data.sounds;
      $("sounds-category").replaceChildren(el("option", "Alle Kategorien")); $("sounds-category").firstChild.value = "";
      Object.entries(data.categories).forEach(([key, title]) => { const option = el("option", title); option.value = key; $("sounds-category").append(option); });
      renderSounds();
    } catch (error) { $("sounds-error").textContent = error.message; $("sounds-error").hidden = false; $("sounds-list").replaceChildren(); }
  }
  function closeSounds() { $("sounds-dialog").close(); }
  $("sounds-dialog").addEventListener("close", () => { soundToken++; $("sounds-list").querySelectorAll("audio").forEach(a => a.pause()); soundOpener?.focus?.({preventScroll: true}); });
  $("open-sounds")?.addEventListener("click", safe(() => openSounds(position)));
  $("sounds-close").addEventListener("click", closeSounds);
  $("sounds-search").addEventListener("input", renderSounds);
  $("sounds-category").addEventListener("change", renderSounds);
  $("sounds-duration").addEventListener("change", updateSoundSelection);
  $("sounds-custom").addEventListener("input", updateSoundSelection);
  root.querySelectorAll("[data-sound-role]").forEach(button => button.addEventListener("click", () => { if (soundReplace) return; soundRole = button.dataset.soundRole; soundChoice = null; renderSounds(); }));
  $("change-duration").addEventListener("click", safe(() => { const clip = state.clips.find(c => c.id === selected); if (clip) return openSounds(clip.start, "project", clip); }));
  $("sounds-generate").addEventListener("click", () => { const prompt = $("sounds-search").value, start = soundStart; closeSounds(); openGeneration("effects", start); if (prompt) $("generate-form").elements.prompt.value = prompt; });
  $("sounds-request").addEventListener("click", async () => {
    try { const result = await api("request", {label: $("sounds-search").value}); $("sounds-selection").textContent = result.message; $("sounds-error").hidden = true; }
    catch (error) { $("sounds-error").textContent = error.message; $("sounds-error").hidden = false; }
  });
  $("sounds-form").addEventListener("submit", async event => {
    event.preventDefault(); if (soundBusy || $("sounds-insert").disabled) return;
    const seconds = soundDuration(), source = soundChoice, replace = soundReplace, requestId = crypto.randomUUID();
    const placement = {track: "effects", start: soundStart, duration: seconds, clip_id: requestId,
      gain_db: (source.gain_db ?? (source.loopable ? -20 : -10)) + ($("sounds-level").value === "normal" ? 6 : 0),
      fade_in: source.fade_in ?? (source.loopable ? 1 : 0), fade_out: source.fade_out ?? (source.loopable ? 2 : 0)};
    $("sounds-error").hidden = true; soundBusy = true; updateSoundSelection();
    try {
      if (!replace && state.clips.length >= 60) throw new Error("Höchstens 60 Clips möglich. Zuerst einen Clip entfernen.");
      if (soundRole === "project" && !replace && seconds <= source.duration + .001) { addAsset(source, placement); closeSounds(); return; }
      if (replace && seconds + replace.trim_start <= source.duration + .001) {
        const current = state.clips.find(c => c.id === replace.id);
        if (!current || JSON.stringify(current) !== JSON.stringify(replace)) throw new Error("Der Clip wurde inzwischen geändert. Bitte erneut auswählen.");
        change(() => { current.trim_end = current.trim_start + seconds; fitFades(current); }); closeSounds(); return;
      }
      const request = {request_id: requestId, duration: seconds + (replace?.trim_start || 0), placement: {track: "effects", start: soundStart}};
      if (soundRole === "project") request.asset_id = source.id; else request.library_id = source.id;
      if (replace) { request.replace_clip_id = replace.id; request.trim_start = replace.trim_start; placement.replace = replace; }
      const result = await api("prepare", request);
      pendingInsertions.set(result.job.id, placement); rememberInsertions(); jobs.unshift(result.job);
      closeSounds(); renderJobs(); renderLibrary(); message("Die Atmosphäre wird lokal vorbereitet. Es werden keine neuen Anbieter-Credits verbraucht.");
    } catch (error) { $("sounds-error").textContent = error.message; $("sounds-error").hidden = false; }
    finally { soundBusy = false; updateSoundSelection(); }
  });
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
