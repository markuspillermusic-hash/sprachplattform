/* Run against the separate local feedback fixture database, never production. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const fixture = JSON.parse(fs.readFileSync(process.env.FEEDBACK_TEST_FIXTURE || 'var/feedback-fixture.json', 'utf8'));
const base = process.env.FEEDBACK_TEST_URL || 'http://127.0.0.1:8096';
(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.FEEDBACK_TEST_CHANNEL ? {channel: process.env.FEEDBACK_TEST_CHANNEL} : {})});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addCookies([{name: 'sessionid', value: fixture.cookie, url: base}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    for (const path of ['/projekte/neu/?mode=assistant', '/produktion/neu/']) {
      await page.goto(base + path);
      const slider = page.locator('[data-duration-slider]');
      await slider.fill('255');
      assert.equal(await page.locator('[data-duration-output]').textContent(), 'Etwa 4 Min. 15 Sek.');
      await page.locator('[name=language]').selectOption('en');
      assert.equal(await page.locator('.field-english_accent').isVisible(), true);
      await page.locator('[name=language]').selectOption('fr');
      assert.equal(await page.locator('.field-english_accent').isVisible(), false);
      await page.getByText('Rollen und Stimmen (optional)', {exact: true}).click();
      assert.equal(await page.locator('[name=voice_preferences]').isVisible(), true);
      await page.screenshot({path: `var/feedback-${path.includes('produktion') ? 'production' : 'text'}-desktop.png`, fullPage: true});
      await page.setViewportSize({width: 390, height: 844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path: `var/feedback-${path.includes('produktion') ? 'production' : 'text'}-mobile.png`, fullPage: true});
      await page.setViewportSize({width: 1440, height: 1000});
    }
    await page.goto(`${base}/produktion/${fixture.project}/`);
    const rows = page.locator('[data-script-row]');
    assert.equal(await rows.count(), 3);
    await rows.nth(0).locator('[data-script-add]').click();
    await rows.nth(0).locator('[data-script-text]').fill('Un début oublié.');
    await rows.nth(2).locator('[data-script-add]').click();
    await rows.nth(2).locator('[data-script-text]').fill('Une nouvelle question.');
    await page.getByRole('button', {name: 'Sprechbeitrag am Ende hinzufügen'}).click();
    await rows.last().locator('[data-script-text]').fill('Une fin ajoutée.');
    assert.equal(await page.locator('[name=script-TOTAL_FORMS]').inputValue(), '6');
    assert.equal(await rows.nth(3).locator('[name$="-speaker"]').inputValue(), 'Louis');
    assert.equal(await rows.nth(0).locator('[data-script-text]').getAttribute('lang'), 'fr');
    const texts = await rows.locator('[data-script-text]').evaluateAll(fields => fields.map(f => f.value));
    assert.deepEqual(texts, ['Un début oublié.', 'Bonjour.', 'Une nouvelle question.', 'Salut.', 'Au revoir.', 'Une fin ajoutée.']);
    const names = await rows.locator('[data-script-text]').evaluateAll(fields => fields.map(f => f.name));
    assert.equal(new Set(names).size, 6);
    await page.getByRole('button', {name: 'Entwurf speichern', exact: true}).click();
    await page.waitForURL(`${base}/produktion/${fixture.project}/`);
    await page.reload();
    assert.deepEqual(await rows.locator('[data-script-text]').evaluateAll(fields => fields.map(f => f.value)), texts);
    await page.screenshot({path: 'var/feedback-insert-production.png', fullPage: true});
    await page.goto(`${base}/projekte/${fixture.project}/`);
    const fields = page.locator('[data-script-text]');
    assert.equal(await fields.first().getAttribute('lang'), 'fr');
    await fields.first().fill('Bonjour, un changement immédiat.');
    await page.getByRole('button', {name: /Sprechbeitrag am Anfang einfügen/}).click();
    await page.waitForURL(/#segment-/);
    assert.equal(await fields.count(), 4);
    assert.equal(await fields.nth(1).inputValue(), 'Bonjour, un changement immédiat.');
    await page.screenshot({path: 'var/feedback-insert-editor.png', fullPage: true});
    await fields.first().fill('');
    await fields.first().dispatchEvent('input');
    const failedSave = page.waitForResponse(response => response.url().includes('/speichern/') && response.status() === 422);
    await page.getByRole('button', {name: /Sprechbeitrag am Anfang einfügen/}).click();
    await failedSave;
    await page.locator('[data-script-text][aria-invalid="true"]').waitFor();
    assert.equal(await fields.count(), 4);
    assert.equal(await page.getByRole('button', {name: /Sprechbeitrag am Anfang einfügen/}).isEnabled(), true);
    assert.equal(await fields.first().getAttribute('aria-invalid'), 'true');
    assert.deepEqual(errors, []);
    console.log('PASS: sliders, shared forms, mobile layouts, language, start/middle/end insertion, saved order, autosave before insertion, blocked insertion on save error; no JS errors.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
