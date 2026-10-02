// Real Web Audio regression: isolated QA files, no provider calls.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const fixture = JSON.parse(fs.readFileSync(process.env.STUDIO_TEST_FIXTURE, 'utf8'));
const base = process.env.STUDIO_TEST_URL || 'http://127.0.0.1:8097';

(async () => {
 const browser = await chromium.launch({headless: true, ...(process.env.STUDIO_TEST_CHANNEL ? {channel: process.env.STUDIO_TEST_CHANNEL} : {})});
 try {
  const page = await browser.newPage({viewport: {width: 1366, height: 900}});
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  // Observe actual native nodes rather than replacing audio with a mock.
  await page.addInitScript(() => {
   const Native = window.AudioContext;
   window.audioQA = {sources: [], gains: [], compressors: []};
   window.AudioContext = class extends Native {
    constructor(...args) {super(...args); window.audioQA.context = this;}
    createGain() {const node = super.createGain(); window.audioQA.gains.push(node); return node;}
    createDynamicsCompressor() {const node = super.createDynamicsCompressor(); window.audioQA.compressors.push(node); return node;}
    createBufferSource() {
     const node = super.createBufferSource(), record = {node, stopped: false};
     const start = node.start.bind(node), stop = node.stop.bind(node);
     node.start = (...args) => {record.args = args; record.duration = node.buffer.duration; start(...args);};
     node.stop = (...args) => {record.stopped = true; stop(...args);};
     window.audioQA.sources.push(record); return node;
    }
   };
  });
  const studio = `${base}/studio/${fixture.project}/`;
  await page.goto(studio);
  if (fixture.cookie) {
   await page.context().addCookies([{name: fixture.cookieName, value: fixture.cookie, url: base, secure: base.startsWith('https:')}]);
   await page.goto(studio);
  } else {
   await page.locator('[name=username]').fill(fixture.username);
   await page.locator('[name=password]').fill(fixture.password);
   await page.getByRole('button', {name: 'Sicher anmelden'}).click();
  }
  await page.waitForFunction(() => !document.getElementById('studio-play').disabled);
  assert((await page.locator('h1').innerText()).startsWith('QA '), 'Only an isolated QA project may be reset');
  const original = structuredClone(fixture.state), music = original.clips.find(c => c.track === 'music');
  const effects = original.clips.find(c => c.track === 'effects');
  original.clips.push({...effects, id: require('node:crypto').randomUUID(), track: 'speech', start: 2});
  const before = await (await page.request.get(`${studio}state/`)).json();
  const reset = await page.request.post(`${studio}save/`, {headers: {Origin: base, Referer: studio, 'X-CSRFToken': await page.locator('#audio-studio [name=csrfmiddlewaretoken]').inputValue()}, data: {revision: before.revision, state: original}});
  assert(reset.ok(), await reset.text()); await page.reload(); await page.waitForFunction(() => !document.getElementById('studio-play').disabled);
  const clip = id => page.locator(`.studio-clip[data-id="${id}"]`);
  const position = () => page.locator('#studio-position').inputValue().then(Number);
  async function cursor(value) {
   await page.locator('#studio-position').fill(String(value)); await page.locator('#studio-position').press('Tab');
   await page.locator('h1').click();
  }
  async function remainsPlaying(previous) {
   await page.waitForTimeout(250);
   assert((await page.locator('#studio-play').innerText()).includes('Pause'));
   assert(await page.locator('#studio-play').isEnabled());
   assert(await position() >= previous, 'Editing must not rewind the transport');
   assert.equal(await page.locator('#studio-message').innerText(), '', 'Live audio scheduling must not fail');
  }
  async function edit(values) {
   for (const [key, value] of Object.entries(values)) await page.locator(`#studio-clip-form [name=${key}]`).fill(String(value));
   await page.getByRole('button', {name: 'Werte übernehmen'}).click();
  }
  async function start() {
   await page.locator('#studio-play').click();
   await page.waitForFunction(() => document.getElementById('studio-play').textContent.includes('Pause'));
  }
  await cursor(5); await clip(music.id).click({position: {x: 25, y: 25}});
  await start(); await remainsPlaying(5);
  const initialSources = await page.evaluate(() => window.audioQA.sources.length);
  const firstMusic = await page.evaluate(() => window.audioQA.sources.find(s => s.duration > 100).args);
  assert.equal(initialSources, 3);
  const previous = await position(); await edit({gain_db: -6, fade_in: 2, fade_out: 3});
  await remainsPlaying(previous);
  assert.equal(await page.evaluate(() => window.audioQA.sources.length), initialSources, 'Gain and fade edits must preserve running sources');
  assert.equal(await page.evaluate(() => window.audioQA.sources.filter(s => s.stopped).length), 0);
  assert(Math.abs(await page.evaluate(() => window.audioQA.gains[5].gain.value) - 10 ** (-6 / 20)) < .01, 'Live clip gain must become audible');
  await edit({fade_in: 20}); await remainsPlaying(previous);
  const faded = await page.evaluate(() => window.audioQA.gains[5].gain.value);
  assert(Math.abs(faded - 10 ** (-6 / 20) * (await position() - 2) / 20) < .02, 'Live fade must follow the elapsed clip time');
  await edit({fade_in: 2});
  await page.locator('[data-track-control=music-gain]').fill('-9'); await page.locator('[data-track-control=music-gain]').press('Tab');
  await remainsPlaying(previous);
  await page.locator('[data-track-control=music-mute]').check(); await remainsPlaying(previous);
  assert(Math.abs(await page.evaluate(() => window.audioQA.gains[3].gain.value)) < .001);
  await page.locator('[data-track-control=music-mute]').uncheck(); await remainsPlaying(previous);
  assert(await page.evaluate(() => window.audioQA.gains[3].gain.value) > 0);
  await page.locator('[data-track-control=effects-solo]').check(); await remainsPlaying(previous);
  assert(Math.abs(await page.evaluate(() => window.audioQA.gains[3].gain.value)) < .001);
  await page.locator('[data-track-control=effects-solo]').uncheck();
  for (const value of ['8', '3', '9']) {
   await page.locator('[data-mix=music_duck_db]').fill(value); await remainsPlaying(previous);
  }
  await page.locator('[data-mix=compression]').fill('80'); await remainsPlaying(previous);
  assert(Math.abs(await page.evaluate(() => window.audioQA.compressors[1].ratio.value) - 2.6) < .01);
  await page.locator('#studio-zoom').fill('12'); await remainsPlaying(previous);
  const gain = await clip(music.id).locator('.studio-gain-handle').boundingBox();
  await page.mouse.move(gain.x + 25, gain.y + gain.height / 2); await page.mouse.down();
  await page.mouse.move(gain.x + 25, gain.y + gain.height / 2 - 10, {steps: 5});
  await remainsPlaying(previous); await page.mouse.up();
  assert.equal(await page.evaluate(() => window.audioQA.sources.length), initialSources);
  await clip(music.id).click({button: 'right', position: {x: 25, y: 25}}); await remainsPlaying(previous);
  await page.keyboard.press('Escape');
  await page.locator('.studio-lane[data-track=effects]').click({position: {x: 360, y: 135}});
  await remainsPlaying(previous); assert(await page.locator('#studio-generate-dialog').evaluate(n => n.open));
  assert((await page.locator('#studio-generation-placement').innerText()).includes('30.00 s'));
  await page.locator('#studio-dialog-cancel').click();
  await clip(music.id).click({position: {x: 25, y: 25}});
  await edit({start: 1}); await remainsPlaying(previous);
  const replacement = await page.evaluate(() => {const s = window.audioQA.sources.findLast(s => s.duration > 100); return {args: s.args, now: window.audioQA.context.currentTime};});
  assert(Math.abs(replacement.args[1] - (14 + replacement.args[0] - firstMusic[0])) < .001, 'Moved audio must resume at the exact elapsed source offset');
  await page.locator('#studio-save').click();
  await page.waitForFunction(() => document.getElementById('studio-save-status').textContent.startsWith('Gespeichert'));
  await page.locator('#studio-reload').click(); await remainsPlaying(previous);
  await page.locator('h1').click(); await page.keyboard.press('Control+z'); await remainsPlaying(previous);
  await cursor(20); await remainsPlaying(20);
  assert(await position() < 23, 'Seeking must continue from the requested position');
  await clip(music.id).click({position: {x: 25, y: 25}}); await page.keyboard.press('t'); await remainsPlaying(20);
  assert.equal(await page.locator('.studio-clip').count(), 4);
  await page.keyboard.press('Control+c'); await page.keyboard.press('Control+v'); await remainsPlaying(20);
  assert.equal(await page.locator('.studio-clip').count(), 5);
  // Trim and then advance beyond every source: transport continues through silence.
  await clip(music.id).click({position: {x: 25, y: 25}}); await edit({trim_end: 14, fade_in: 0, fade_out: 0}); await remainsPlaying(20);
  await cursor(100); await remainsPlaying(100);
  assert(await position() > 100);
  for (const id of await page.locator('.studio-clip').evaluateAll(nodes => nodes.map(n => n.dataset.id))) {
   await clip(id).click({position: {x: 5, y: 25}}); await page.keyboard.press('Delete');
  }
  await remainsPlaying(100); assert.equal(await page.locator('.studio-clip').count(), 0);
  await page.locator('h1').click(); await page.keyboard.press('Space');
  assert((await page.locator('#studio-play').innerText()).includes('Abspielen'));
  const paused = await position(); await page.waitForTimeout(250); assert.equal(await position(), paused);
  await page.locator('#studio-undo').click(); await start(); await remainsPlaying(0);
  await page.locator('#studio-stop').click(); assert.equal(await position(), 0);
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(() => window.audioQA.sources.filter(s => !s.stopped).length), 0, 'Stop must dispose all graphs');
  // A late decode must never resurrect playback after an explicit stop.
  let release, pending = false;
  const gate = new Promise(resolve => {release = resolve;});
  await page.route(new URL(fixture.generated.url, base).href, async route => {
   pending = true; await gate; await route.continue();
  });
  await start(); await remainsPlaying(0);
  await page.locator('.studio-library-item').filter({has: page.locator('strong', {hasText: fixture.generated.title})}).getByRole('button', {name: 'Einfügen'}).click();
  for (let i = 0; i < 30 && !pending; i++) await page.waitForTimeout(50);
  assert(pending, 'New audio should load while the old graph continues');
  const sourcesBeforeStop = await page.evaluate(() => window.audioQA.sources.length);
  await remainsPlaying(0); await page.locator('#studio-stop').click(); release();
  await page.waitForTimeout(500);
  assert((await page.locator('#studio-play').innerText()).includes('Abspielen'));
  assert.equal(await position(), 0);
  assert.equal(await page.evaluate(() => window.audioQA.sources.length), sourcesBeforeStop);
  assert.equal(await page.evaluate(() => window.audioQA.sources.filter(s => !s.stopped).length), 0);
  assert.deepEqual(errors, []);
  console.log('PASS: native audio continues through gain/fades, mix, mute/solo, drag, menus, generation dialog, move, save/reload, undo, seek, cut/paste, trim, silence and deleting every clip; Pause/Stop halt playback and late decoding cannot restart it.');
 } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
