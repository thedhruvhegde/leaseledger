#!/usr/bin/env node
// Backup PDF of the whole deck: every chapter at 1920x1080 with all reveal steps shown, the demo after flip I,
// and every multi-city plate (final frames) plus the catalogue. Pages are JPEG screenshots combined into one PDF.
// Usage (deck running on :4400): npm run export [-- --url=http://localhost:4400/ --out=export/lease-ledger-deck.pdf]
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');

const arg = (k, d) => (process.argv.find((a) => a.startsWith(`--${k}=`)) ?? `=${d}`).split('=').slice(1).join('=');
const URL0 = arg('url', 'http://localhost:4400/');
const OUT = path.resolve(__dirname, '..', arg('out', 'export/lease-ledger-deck.pdf'));
fs.mkdirSync(path.dirname(OUT), { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(URL0 + (URL0.includes('?') ? '&' : '?') + 'appendix', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__deck?.plan?.__done, null, { timeout: 60000 });
  await page.evaluate(() => document.documentElement.classList.add('export'));
  const ids = await page.evaluate(() => window.__deck.chapters);
  const shots = [];
  const snap = async () => { shots.push((await page.screenshot({ type: 'jpeg', quality: 88 })).toString('base64')); };
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i];
    await page.evaluate((k) => window.__deck.go(k, false), i);
    await page.waitForTimeout(500);
    await page.evaluate((cid) => document.getElementById(cid).dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: 99 })), id);
    if (id === 'how') await page.evaluate(() => document.getElementById('how').dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: 2 })));
    if (id === 'demo') { await page.waitForTimeout(2500); await page.click('.flip-btn[data-flip="vot"]'); await page.waitForTimeout(3000); }
    if (id === 'multicity') {
      await page.evaluate(() => document.querySelector('#multicity .mc-full')?.dispatchEvent(new MouseEvent('click', { bubbles: true }))); // pause
      // v5: the seven-cities loop (mid-run frame), then the catalogue
      for (let k = 0; k < 2; k++) {
        await page.evaluate((kk) => document.querySelectorAll('#multicity .mc-ticks i')[kk]?.dispatchEvent(new MouseEvent('click', { bubbles: true })), k);
        await page.waitForTimeout(k === 0 ? 2600 : 1300);
        await snap();
      }
      process.stdout.write(`${id} `);
      continue;
    }
    await page.waitForTimeout(2600);
    await snap();
    process.stdout.write(`${id} `);
  }
  const doc = await browser.newPage();
  await doc.setContent(`<!doctype html><html><head><style>@page{size:1920px 1080px;margin:0}html,body{margin:0}img{display:block;width:1920px;height:1080px;page-break-after:always;break-after:page}</style></head><body>${shots.map((s) => `<img src="data:image/jpeg;base64,${s}">`).join('')}</body></html>`);
  await doc.pdf({ path: OUT, width: '1920px', height: '1080px', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await browser.close();
  console.log(`\nwrote ${OUT} (${shots.length} pages)`);
})();
