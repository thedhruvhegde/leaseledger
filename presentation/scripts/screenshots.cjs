#!/usr/bin/env node
// Screenshot every chapter at 1920x1080 (all reveal steps shown) into screenshots/cartesian/, plus a few extra
// states (pipeline intro, demo before the flip, multi-city catalogue), and run the DOM honesty check: any visible
// text with a digit must sit inside an element carrying data-src (API / facts / derived) or data-ok (presenter chrome).
// Usage: npm run screenshots [-- --url=... --out=screenshots/cartesian --only=hook,demo]
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');

const arg = (k, d) => (process.argv.find((a) => a.startsWith(`--${k}=`)) ?? `=${d}`).split('=').slice(1).join('=');
const URL0 = arg('url', 'http://localhost:4400/');
const OUT = path.resolve(__dirname, '..', arg('out', 'screenshots/cartesian'));
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(URL0 + (URL0.includes('?') ? '&' : '?') + 'appendix', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__deck?.plan?.__done, null, { timeout: 60000 });
  const ids = await page.evaluate(() => window.__deck.chapters);
  const only = arg('only', '');
  let violations = 0;
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i];
    if (only && !only.split(',').includes(id)) continue;
    await page.evaluate((k) => window.__deck.go(k, false), i);
    await page.waitForTimeout(400);
    const pre = async (suffix) => { await page.waitForTimeout(1800); await page.screenshot({ path: path.join(OUT, `${String(i + 1).padStart(2, '0')}${suffix}-${id}.png`) }); };
    if (id === 'how' || id === 'demo' || id === 'problem') await pre('a');
    await page.evaluate((cid) => document.getElementById(cid).dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: 99 })), id);
    if (id === 'demo') {
      await page.click('.flip-btn[data-flip="vot"]');
      await page.waitForTimeout(3500);
    }
    if (id === 'how') await page.evaluate(() => document.getElementById('how').dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: 2 })));
    await page.waitForTimeout(id === 'demo' ? 600 : 2600);
    const file = path.join(OUT, `${String(i + 1).padStart(2, '0')}-${id}.png`);
    await page.screenshot({ path: file });
    if (id === 'multicity') {
      for (const [k, suf] of [[-2, 'b'], [-1, 'c']]) {
        await page.evaluate((kk) => { const s = document.querySelectorAll('#multicity .mc-index span'); s[s.length + kk]?.dispatchEvent(new MouseEvent('click', { bubbles: true })); }, k);
        await page.waitForTimeout(1500);
        await page.screenshot({ path: path.join(OUT, `${String(i + 1).padStart(2, '0')}${suf}-${id}.png`) });
      }
    }
    const bad = await page.evaluate((cid) => {
      const root = document.getElementById(cid);
      const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const out = [];
      for (let n = w.nextNode(); n; n = w.nextNode()) {
        const t = n.textContent.trim().replace(/#[12]\b/g, '');
        if (!/\d/.test(t)) continue;
        const el = n.parentElement;
        if (el.closest('[data-src],[data-ok],.katex,title,script,style,.ph,code')) continue;
        if (/^#[12]$/.test(t)) continue;
        out.push(t.slice(0, 80));
      }
      return out;
    }, id);
    violations += bad.length;
    console.log(`${path.basename(file)}${bad.length ? `  !! unbound digits: ${JSON.stringify(bad.slice(0, 5))}` : ''}`);
  }
  if (errors.length) console.log('console errors:\n  ' + [...new Set(errors)].slice(0, 10).join('\n  '));
  await browser.close();
  console.log(violations ? `${violations} unbound number(s) on slides` : 'DOM check: every number on every slide is data-bound');
  process.exit(violations ? 1 : 0);
})();
