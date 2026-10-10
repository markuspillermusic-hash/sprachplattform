// Only against the isolated local library-browser fixture; never approves real sounds.
const fs=require('node:fs'), assert=require('node:assert/strict');
const {chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync(process.env.STUDIO_TEST_FIXTURE,'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.STUDIO_TEST_CHANNEL||'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}}), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  // The stock Django admin login has no favicon declaration.
  await page.route('**/favicon.ico',route=>route.fulfill({status:204}));
  const url='http://127.0.0.1:8097/admin/audio_studio/soundlibraryasset/hoerpruefung/';
  await page.goto(url);
  await page.locator('[name=username]').fill(fixture.username);
  await page.locator('[name=password]').fill(fixture.password);
  await page.getByRole('button',{name:'Anmelden',exact:true}).click();
  await page.locator('.sound-review-card').first().waitFor();
  assert.equal(await page.locator('.sound-review-card').count(),2);
  assert.equal(await page.locator('.sound-review-list').evaluate(n=>getComputedStyle(n).display),'grid');
  assert((await page.locator('.sound-review-card h2').allTextContents()).every(t=>t.startsWith('QA ')));
  let card=page.locator(`#sound-${fixture.atmosphere}`);
  await card.locator('audio').evaluate(async a=>{await a.play();});
  await page.waitForFunction(id=>document.querySelector(`#sound-${id} audio`).currentTime>.1,fixture.atmosphere);
  await page.locator(`#sound-${fixture.oneshot} audio`).evaluate(async a=>{await a.play();});
  assert(await card.locator('audio').evaluate(a=>a.paused));
  await card.locator('[name=heard]').check();
  await card.getByRole('button',{name:'Diesen Klang freigeben'}).click();
  await page.getByText('QA Wald ist jetzt im Studio und im Assistenten verfügbar.').waitFor();
  card=page.locator(`#sound-${fixture.atmosphere}`);
  assert((await card.locator('.sound-review-status').innerText()).includes('Freigegeben'));
  assert.equal(await card.getByRole('button',{name:'Diesen Klang freigeben'}).count(),0);
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(process.env.STUDIO_TEST_SCREENSHOT) await page.screenshot({path:process.env.STUDIO_TEST_SCREENSHOT,fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Hörprüfseite: vollständiges Audio abgespielt, Freigabe mit echtem CSRF-Formular, Statuswechsel und Mobilansicht bestanden. Nur isolierte QA-Datei freigegeben.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
