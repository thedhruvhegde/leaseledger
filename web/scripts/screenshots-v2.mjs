// v2 screenshots against the live API: landing + every app screen at 1920x1080 and 390x844.
// Usage: npm run dev & ; node scripts/screenshots-v2.mjs [baseUrl]   (ONLY=landing,results  PRESENT=1  DARK=1  FULL=1)
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const base = process.argv[2] ?? 'http://localhost:5173';
const out = new URL('../screenshots/v2/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const demo = process.env.DEMO ?? 'north-engineer';
const only = process.env.ONLY?.split(',');
const want = (k) => !only || only.includes(k);
const sizes = [{ name: 'desktop', width: 1920, height: 1080 }, { name: 'phone', width: 390, height: 844 }].filter((s) => !process.env.SIZE || s.name === process.env.SIZE);
const suffix = `${process.env.DARK === '1' ? '-dark' : ''}${process.env.PRESENT === '1' ? '-present' : ''}`;
const browser = await pw.chromium.launch();
for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, deviceScaleFactor: 1, colorScheme: process.env.DARK === '1' ? 'dark' : 'light' });
  const open = async (url, wait = 1500) => {
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
    page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
    await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
    if (process.env.PRESENT === '1') await page.keyboard.press('p');
    await page.waitForTimeout(wait);
    return page;
  };
  if (want('landing')) {
    const page = await open('/', 2200);
    await page.screenshot({ path: `${out}landing-${s.name}${suffix}.png` });
    // one shot per screen of the page
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    for (let i = 1, y = s.height; y < h; i++, y += s.height) {
      await page.evaluate((yy) => window.scrollTo(0, yy), y);
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${out}landing-${s.name}${suffix}-${i}.png` });
    }
    if (process.env.FULL === '1') await page.screenshot({ path: `${out}landing-${s.name}${suffix}-full.png`, fullPage: true });
    await page.close();
  }
  for (const sc of ['week', 'results', 'robustness', 'baseline', 'group', 'add', 'methods']) {
    if (!want(sc)) continue;
    const page = await open(`/app?demo=${demo}#${sc}`, sc === 'robustness' || sc === 'results' ? 2200 : 1400);
    if (sc === 'add') {
      await page.getByText('Use example (fictional)').click();
      await page.getByRole('button', { name: 'Extract facts', exact: true }).click();
      await page.waitForTimeout(900);
    }
    await page.screenshot({ path: `${out}${sc}-${s.name}${suffix}.png`, fullPage: process.env.FULL === '1' });
    await page.close();
  }
  if (want('diff')) {
    const page = await open(`/app?demo=${demo}#results`, 1800);
    await page.evaluate(() => window.__ll?.getState?.().setProfile((p) => ({ ...p, modes: ['walk', 'bus', 'bike'] })));
    await page.waitForTimeout(4500);
    await page.screenshot({ path: `${out}diff-${s.name}${suffix}.png` });
    await page.close();
  }
  if (want('why')) {
    const page = await open(`/app?demo=${demo}#results`, 1800);
    await page.getByText('Show all reasoning').click();
    await page.waitForTimeout(800);
    await page.getByText('Show all reasoning').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${out}why-open-${s.name}${suffix}.png` });
    await page.close();
  }
  await ctx.close();
}
await browser.close();
console.log('done');
