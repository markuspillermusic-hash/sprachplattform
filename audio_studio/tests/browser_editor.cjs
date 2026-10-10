// Run against an isolated local QA project. Provider calls are intercepted.
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
  const studio = `${base}/studio/${fixture.project}/`;
  let simulatedJob = null, generateCalls = 0, submitted = null;
  await page.route(`${studio}state/`, async route => {
   const response = await route.fetch(), data = await response.json();
   for (const kind of ['music', 'effects']) data.generation[kind].enabled = true;
   if (simulatedJob) data.jobs = [simulatedJob];
   await route.fulfill({response, json: data});
  });
  await page.route(`${studio}generate/`, async route => {
   generateCalls++; submitted = route.request().postDataJSON();
   if (generateCalls === 1) return route.fulfill({status: 422, json: {error: 'QA: Bitte den Prompt ergänzen.'}});
   simulatedJob = {id: 'mock-generated-job', kind: submitted.kind, status: 'queued', label: 'Wartet', error: '', asset: null, placement: submitted.placement};
   await route.fulfill({status: 202, json: {job: simulatedJob}});
  });
  await page.route(`${studio}jobs/`, route => route.fulfill({json: {jobs: simulatedJob ? [{...simulatedJob, status: 'succeeded', label: 'Fertig', asset: {...fixture.generated, duration: submitted.duration}}] : []}}));
  await page.goto(studio);
  await page.locator('[name=username]').fill(fixture.username || 'studio-gestures-qa');
  await page.locator('[name=password]').fill(fixture.password || 'local-qa-only');
  await page.getByRole('button', {name: 'Sicher anmelden'}).click();
  await page.waitForFunction(() => !document.getElementById('studio-play').disabled);
  assert((await page.locator('h1').innerText()).startsWith('QA '), 'Only an isolated QA project may be reset');
  const before = await (await page.request.get(`${studio}state/`)).json();
  const reset = await page.request.post(`${studio}save/`, {headers: {'X-CSRFToken': await page.locator('#audio-studio [name=csrfmiddlewaretoken]').inputValue()}, data: {revision: before.revision, state: fixture.state}});
  assert(reset.ok()); await page.reload(); await page.waitForFunction(() => !document.getElementById('studio-play').disabled);
  const clips = page.locator('.studio-clip');
  const original = fixture.state.clips.find(c => c.track === 'effects'), music = fixture.state.clips.find(c => c.track === 'music');
  const clip = id => page.locator(`.studio-clip[data-id="${id}"]`);
  const select = async id => clip(id).click({position: {x: 30, y: 25}});
  const selected = async () => page.locator('.studio-clip.is-selected').getAttribute('data-id');
  const value = name => page.locator(`#studio-clip-form [name=${name}]`).inputValue().then(Number);
  async function cursor(seconds) {
   await page.locator('#studio-position').fill(String(seconds)); await page.locator('#studio-position').press('Tab'); await page.locator('h1').click();
  }
  async function saveState() {
   if (await page.locator('#studio-save').isEnabled()) {
    await page.locator('#studio-save').click(); await page.waitForFunction(() => document.getElementById('studio-save-status').textContent.startsWith('Gespeichert'));
   }
   return (await (await page.request.get(`${studio}state/`)).json()).state;
  }
  await page.locator('#studio-zoom').fill('60');
  await page.locator('#studio-timeline').evaluate(node => {node.scrollLeft = 2000;});
  await page.waitForTimeout(100);
  const label = await clip(music.id).locator('.studio-gain-value').boundingBox(), viewport = await page.locator('#studio-timeline').boundingBox();
  assert(label.x >= viewport.x + 156 && label.x + label.width <= viewport.x + viewport.width, 'Gain label must stay in visible clip area');
  assert.equal(await clip(music.id).locator('.studio-gain-value').innerText(), '-15.0 dB');
  await page.locator('#studio-timeline').evaluate(node => {node.scrollLeft = 0;});
  await select(original.id); await page.keyboard.press('Control+c'); await cursor(20); await page.keyboard.press('Control+v');
  assert.equal(await clips.count(), 3); assert.equal(await value('start'), 20);
  const pasted = await selected(); let saved = await saveState();
  for (const field of ['trim_start', 'trim_end', 'gain_db', 'fade_in', 'fade_out']) assert.equal(saved.clips.find(c => c.id === pasted)[field], original[field]);
  await clip(pasted).click({button: 'right', position: {x: 30, y: 25}});
  await page.getByRole('menuitem', {name: 'Duplizieren'}).click(); assert.equal(await clips.count(), 4); assert.equal(await value('start'), 25);
  const duplicate = await selected();
  await clip(duplicate).click({button: 'right', position: {x: 30, y: 25}});
  await page.getByRole('menuitem', {name: 'Clip bearbeiten'}).click(); assert.equal(await page.locator('#studio-clip-form [name=start]').evaluate(n => n === document.activeElement), true);
  await page.locator('#studio-clip-form [name=gain_db]').fill('-11.5'); await page.keyboard.press('Control+a'); await page.keyboard.press('Control+c');
  await page.getByRole('button', {name: 'Werte übernehmen'}).click();
  await select(duplicate); await page.keyboard.press('Delete'); assert.equal(await clips.count(), 3);
  await page.keyboard.press('Control+z'); assert.equal(await clips.count(), 4);
  await page.keyboard.press('Control+Shift+z'); assert.equal(await clips.count(), 3);
  await select(original.id); await cursor(40); await page.keyboard.press('Control+x'); assert.equal(await clips.count(), 2);
  await page.keyboard.press('Control+v'); assert.equal(await value('start'), 40); assert.equal(await value('gain_db'), -8, 'Typing must not replace the clip clipboard');
  await page.keyboard.press('Control+z'); await page.keyboard.press('Control+z'); assert.equal(await clips.count(), 3);
  await select(original.id); const rect = await clip(original.id).boundingBox();
  await page.keyboard.down('Control'); await page.mouse.move(rect.x + 30, rect.y + 25); await page.mouse.down(); await page.mouse.move(rect.x + 150, rect.y + 25, {steps: 8}); await page.mouse.up(); await page.keyboard.up('Control');
  assert.equal(await clips.count(), 4); const draggedCopy = await selected(); assert.notEqual(draggedCopy, original.id); assert.equal(await value('start'), 6);
  saved = await saveState(); assert.equal(saved.clips.find(c => c.id === original.id).start, 4);
  await page.keyboard.press('Control+z'); assert.equal(await clips.count(), 3); await page.keyboard.press('Control+Shift+z'); assert.equal(await clips.count(), 4);
  await select(draggedCopy);
  const gain = await clip(draggedCopy).locator('.studio-gain-handle').boundingBox();
  await page.mouse.move(gain.x + 30, gain.y + gain.height / 2); await page.mouse.down(); await page.mouse.move(gain.x + 30, gain.y + gain.height / 2 - 10, {steps: 5}); await page.mouse.up();
  assert.equal(await value('gain_db'), -4);
  const gain2 = await clip(draggedCopy).locator('.studio-gain-handle').boundingBox();
  await page.keyboard.down('Shift'); await page.mouse.move(gain2.x + 30, gain2.y + gain2.height / 2); await page.mouse.down(); await page.mouse.move(gain2.x + 30, gain2.y + gain2.height / 2 - 10, {steps: 5}); await page.mouse.up(); await page.keyboard.up('Shift');
  assert.equal(await value('gain_db'), -3.5);
  const waveWidth = await clip(draggedCopy).locator('canvas').evaluate(n => n.style.width);
  const edge = await clip(draggedCopy).locator('.studio-trim-right').boundingBox();
  await page.mouse.move(edge.x + edge.width / 2, edge.y + 25); await page.mouse.down(); await page.mouse.move(edge.x + edge.width / 2 + 60, edge.y + 25, {steps: 5}); await page.mouse.up();
  assert.equal(await value('trim_end'), 7); assert.equal(await clip(draggedCopy).locator('canvas').evaluate(n => n.style.width), waveWidth);
  await cursor(8); await select(draggedCopy); await page.keyboard.press('t'); assert.equal(await clips.count(), 5);
  await saveState(); await page.locator('#studio-zoom').fill('10');
  const lane = page.locator('.studio-lane[data-track=music]');
  await lane.click({position: {x: 150, y: 130}}); assert.equal(await page.locator('#studio-generate-dialog').evaluate(n => n.open), true);
  assert.equal(await page.locator('#studio-generate-form [name=kind]').inputValue(), 'music');
  await page.locator('#studio-generate-form [name=prompt]').fill('Mein eigener Musikprompt');
  await page.locator('#studio-generate-form [name=duration]').fill('3');
  await page.locator('#studio-generate').click(); await page.locator('#studio-generation-error').waitFor({state: 'visible'});
  assert.equal(await page.locator('#studio-generate-form [name=prompt]').inputValue(), 'Mein eigener Musikprompt');
  await page.keyboard.press('Escape'); assert.equal(await page.locator('#studio-generate-dialog').evaluate(n => n.open), false);
  const effectLane = page.locator('.studio-lane[data-track=effects]');
  await effectLane.click({position: {x: 312.5, y: 145}});
  await page.locator('#studio-sounds-generate').click();
  await page.locator('#studio-generate-form [name=duration]').fill('2');
  await page.locator('#studio-generate-form [name=prompt]').fill('Eine Tür schließt sich leise'); await page.locator('#studio-generate').click();
  await page.waitForFunction(() => !document.getElementById('studio-generate-dialog').open);
  assert.equal(submitted.placement.track, 'effects'); assert(Math.abs(submitted.placement.start - 31.25) < .1);
  await cursor(77); await page.reload(); await page.waitForFunction(() => !document.getElementById('studio-play').disabled);
  await page.waitForFunction(() => document.getElementById('studio-message').textContent.includes('wurde bei'));
  saved = await saveState(); const inserted = saved.clips.filter(c => c.asset_id === fixture.generated.id);
  assert.equal(inserted.length, 1); assert.equal(inserted[0].start, submitted.placement.start); assert.equal(inserted[0].track, 'effects'); assert.equal(inserted[0].trim_end, 2);
  await page.locator('#studio-timeline').evaluate(node => {node.scrollLeft = 0;});
  await clip(inserted[0].id).click({button: 'right', position: {x: 9, y: 25}});
  await page.keyboard.press('ArrowDown'); await page.keyboard.press('Escape'); assert.equal(await page.locator('#studio-context-menu').isVisible(), false);
  await page.setViewportSize({width: 390, height: 844}); await page.getByRole('button', {name: 'Neu generieren …', exact: true}).click();
  assert(await page.locator('#studio-generate-dialog').isVisible());
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  if (process.env.STUDIO_TEST_SCREENSHOT) await page.screenshot({path: process.env.STUDIO_TEST_SCREENSHOT});
  await page.keyboard.press('Escape'); assert.deepEqual(errors, []);
  console.log('Browser: Kontextmenü, Copy/Paste, Ausschneiden, Strg-Ziehen, Undo/Redo, Fades/Schnitt, Gain, Zoom/Scroll, Dialogfehler und Einfügen nach Neuladen erfolgreich. Keine Provideraufrufe.');
 } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
