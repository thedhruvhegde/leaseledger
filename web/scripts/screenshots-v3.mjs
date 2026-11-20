// v3 screenshots against the live API (vite preview on :5173 + API on :8000).
// Usage: node scripts/screenshots-v3.mjs [baseUrl]   (ONLY=product,landing,results,detail,compare,week,robustness,group  SIZE=1440|1920|phone)
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const base = process.argv[2] ?? 'http://localhost:5173';
const out = new URL('../screenshots/v3/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const demo = process.env.DEMO ?? 'north-engineer';
const only = process.env.ONLY?.split(',');
const want = (k) => !only || only.includes(k);
const sizes = [
  { name: '1440', width: 1440, height: 900 },
  { name: '1920', width: 1920, height: 1080 },
  { name: 'phone', width: 390, height: 844, mobile: true },
].filter((s) => !process.env.SIZE || process.env.SIZE.split(',').includes(s.name));
const browser = await pw.chromium.launch();
if (want('product')) {
  // The one product screenshot on the landing page: the real results page for the sample week.
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, colorScheme: 'light' });
  const page = await ctx.newPage();
  await page.goto(`${base}/app?demo=${demo}#results`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: new URL('../public/product-results.jpg', import.meta.url).pathname, type: 'jpeg', quality: 82 });
  await ctx.close();
}
for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, deviceScaleFactor: s.mobile ? 2 : 1, isMobile: !!s.mobile, hasTouch: !!s.mobile, colorScheme: process.env.DARK === '1' ? 'dark' : 'light' });
  const open = async (url, wait = 1500) => {
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
    page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
    await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(wait);
    return page;
  };
  const shot = (page, name, opts = {}) => page.screenshot({ path: `${out}${name}-${s.name}${process.env.DARK === '1' ? '-dark' : ''}.png`, ...opts });
  if (want('landing')) {
    const page = await open('/', 2000);
    await shot(page, 'landing');
    if (process.env.FULL === '1') await shot(page, 'landing-full', { fullPage: true });
    await page.close();
  }
  if (want('results') || want('detail') || want('compare')) {
    const page = await open(`/app?demo=${demo}#results`, 2500);
    if (want('results')) await shot(page, 'results');
    if (want('detail')) {
      if (s.mobile) {
        await page.locator('article h3 button').first().click();
      } else {
        await page.locator('.price-pin').first().click();
      }
      await page.waitForTimeout(1500);
      await shot(page, 'detail');
      if (process.env.FULL === '1' || process.env.SCROLL === '1') {
        const sc = s.mobile ? '.sheet' : '.results-pane';
        await page.evaluate((sel) => { const el = document.querySelector(sel); if (el) el.scrollTop = 900; }, sc);
        await page.waitForTimeout(500);
        await shot(page, 'detail-2');
      }
      await page.keyboard.press('Escape');
      await page.waitForTimeout(400);
    }
    if (want('compare') && !s.mobile) {
      const boxes = page.locator('article input[type=checkbox]');
      await boxes.nth(0).check();
      await boxes.nth(3).check();
      await page.waitForTimeout(300);
      await shot(page, 'compare-tray');
      await page.getByRole('button', { name: 'Compare', exact: true }).click();
      await page.waitForTimeout(1500);
      await shot(page, 'compare');
    }
    await page.close();
  }
  if (want('map') && s.mobile) {
    const page = await open(`/app?demo=${demo}#results`, 2000);
    await page.getByRole('button', { name: 'Map', exact: true }).click();
    await page.waitForTimeout(1800);
    await shot(page, 'results-map');
    await page.close();
  }
  for (const sc of ['week', 'robustness', 'group', 'baseline', 'add', 'methods']) {
    if (!want(sc)) continue;
    const page = await open(`/app?demo=${demo}#${sc}`, sc === 'robustness' || sc === 'group' ? 2500 : 1500);
    await shot(page, sc);
    await page.close();
  }
  await ctx.close();
}
await browser.close();
console.log('done');
