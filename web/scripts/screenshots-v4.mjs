// v4 screenshots against the live API (vite preview on :5173 + API on :8000).
// Usage: node scripts/screenshots-v4.mjs [baseUrl]
//   ONLY=vignettes,landing,results,category,detail,compare,week,robustness,group   SIZE=1440|phone
// "vignettes" writes the three landing-page crops to public/product/ (rebuild afterwards).
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const base = process.argv[2] ?? 'http://localhost:5173';
const out = new URL('../screenshots/v4/', import.meta.url).pathname;
const prod = new URL('../public/product/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
mkdirSync(prod, { recursive: true });
const demo = process.env.DEMO ?? 'north-engineer';
const only = process.env.ONLY?.split(',');
const want = (k) => !only || only.includes(k);
const sizes = [
  { name: '1440', width: 1440, height: 900 },
  { name: 'phone', width: 390, height: 844, mobile: true },
].filter((s) => !process.env.SIZE || process.env.SIZE.split(',').includes(s.name));
const browser = await pw.chromium.launch();
const log = (page) => {
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
};

if (want('vignettes')) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: 'light' });
  const page = await ctx.newPage(); log(page);
  await page.goto(`${base}/app?demo=${demo}#results`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await page.locator('.price-pin').first().click();
  await page.waitForTimeout(2000);
  // 1. receipt: the receipt card alone, padded to 4:3
  const r = await page.locator('#d-receipt [role=group]').first().boundingBox();
  const w = r.width + 48, h = Math.max(r.height + 48, w * 0.75);
  await page.locator('.results-pane').evaluate((el, y) => { el.scrollTop = y; }, 0);
  await page.locator('#d-receipt').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const r2 = await page.locator('#d-receipt [role=group]').first().boundingBox();
  await page.screenshot({ path: `${prod}receipt.png`, clip: { x: r2.x - 24, y: r2.y - (h - r2.height) / 2, width: w, height: h } });
  // 2. map with the selected home's routes: right pane, 4:3, chrome hidden
  await page.addStyleTag({ content: '.maplibregl-ctrl, .maplibregl-ctrl-attrib, .map-legend { display: none !important; }' });
  await page.waitForTimeout(300);
  const m = await page.locator('.maplibregl-canvas').boundingBox();
  const mw = Math.min(m.width - 24, (m.height - 24) * 4 / 3), mh = mw * 0.75;
  await page.screenshot({ path: `${prod}route.png`, clip: { x: m.x + (m.width - mw) / 2, y: m.y + (m.height - mh) / 2 - 20, width: mw, height: mh } });
  // 3. how sure: the headline card of the robustness screen, 4:3 from its top
  await page.goto(`${base}/app?demo=${demo}#robustness`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3500);
  const card = page.locator('#main .card.p-5').first();
  await card.evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 80));
  await page.waitForTimeout(400);
  const c = await card.boundingBox();
  await page.screenshot({ path: `${prod}sure.png`, clip: { x: c.x - 1, y: c.y - 1, width: c.width + 2, height: Math.min(c.height + 2, (c.width + 2) * 0.75) } });
  await ctx.close();
}

for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, deviceScaleFactor: s.mobile ? 2 : 1, isMobile: !!s.mobile, hasTouch: !!s.mobile, colorScheme: 'light' });
  const open = async (url, wait = 1500) => {
    const page = await ctx.newPage(); log(page);
    await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(wait);
    return page;
  };
  const shot = (page, name, opts = {}) => page.screenshot({ path: `${out}${name}-${s.name}.png`, ...opts });
  if (want('landing')) {
    const page = await open('/', 2000);
    await shot(page, 'landing');
    await shot(page, 'landing-full', { fullPage: true });
    await page.close();
  }
  if (want('results') || want('detail') || want('compare') || want('category')) {
    const page = await open(`/app?demo=${demo}#results`, 3000);
    if (want('results')) await shot(page, 'homes');
    if (want('results') && s.mobile) {
      await page.getByRole('button', { name: 'Map', exact: true }).click();
      await page.waitForTimeout(1800);
      await shot(page, 'homes-map');
      await page.getByRole('button', { name: 'List', exact: true }).click();
      await page.waitForTimeout(800);
    }
    if (want('category')) {
      await page.getByRole('tab', { name: /^Towers & apartments/ }).click();
      await page.waitForTimeout(1500);
      await shot(page, 'category');
      await page.getByRole('tab', { name: /^All homes/ }).click();
      await page.waitForTimeout(800);
    }
    if (want('detail')) {
      if (s.mobile) await page.locator('article h3 button').first().click();
      else await page.locator('.price-pin').first().click();
      await page.waitForTimeout(1800);
      await shot(page, 'detail');
      const sc = s.mobile ? '.sheet' : '.results-pane';
      const y = await page.evaluate(() => { const el = document.querySelector('#d-receipt'); return el ? el.offsetTop : 600; });
      await page.evaluate(([sel, top]) => { const el = document.querySelector(sel); if (el) el.scrollTop = top - 8; }, [sc, y]);
      await page.waitForTimeout(500);
      await shot(page, 'detail-receipt');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    }
    if (want('compare')) {
      const t = page.locator('article .compare-toggle');
      await t.nth(0).click();
      await t.nth(1).click();
      await page.waitForTimeout(400);
      await shot(page, 'compare-tray');
      await page.getByRole('button', { name: /^Compare 2 homes/ }).click();
      await page.waitForTimeout(2000);
      await shot(page, 'compare');
    }
    await page.close();
  }
  if (want('week')) {
    const page = await open(`/app#week`, 1500);
    const ta = page.locator('textarea').first();
    await ta.click();
    await ta.fill('');
    await ta.pressSequentially('MWF 9-10:30 EECS 281 in BBB, TTh 1-2:30 Ross, Mon/Wed gym at CCRB 6pm, UgLi till 1am Thursdays', { delay: 8 });
    await page.waitForTimeout(400);
    await shot(page, 'week-typing');
    const btn = page.getByRole('button', { name: /^(Build my week|Read|Parse)/ }).first();
    if (await btn.count()) { await btn.click(); await page.waitForTimeout(3500); await shot(page, 'week'); }
    await page.close();
  }
  for (const sc of ['robustness', 'group']) {
    if (!want(sc)) continue;
    const page = await open(`/app?demo=${demo}#${sc}`, 3500);
    await shot(page, sc === 'robustness' ? 'how-sure' : 'group');
    await page.close();
  }
  await ctx.close();
}
await browser.close();
console.log('done');
