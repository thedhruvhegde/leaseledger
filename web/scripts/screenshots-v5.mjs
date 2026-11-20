// v5 screenshots + click-through QA against the live API (vite preview on :5173 + API on :8000).
// Usage: node scripts/screenshots-v5.mjs [baseUrl]
//   ONLY=vignettes,landing,results,detail,compare,week,robustness,baseline,group,add,methods,dark,present   SIZE=1440|phone
// "vignettes" writes the three landing-page crops to public/product/ from the canonical demo state
// (north-engineer, all observed listings, rank-1 home), so the landing caption, crops, deck and videos agree.
// Every console error / warning and page error is printed and counted; exit code 1 if any.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const base = process.argv[2] ?? 'http://localhost:5173';
const out = new URL('../screenshots/v5/', import.meta.url).pathname;
const prod = new URL('../public/product/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const demo = process.env.DEMO ?? 'north-engineer';
const only = process.env.ONLY?.split(',');
const want = (k) => !only || only.includes(k);
const sizes = [
  { name: '1440', width: 1440, height: 900 },
  { name: 'phone', width: 390, height: 844, mobile: true },
].filter((s) => !process.env.SIZE || process.env.SIZE.split(',').includes(s.name));
const browser = await pw.chromium.launch();
const problems = [];
const IGNORE = [/WebGL/i, /GPU stall/i, /Automatic fallback to software WebGL/i, /favicon/i];
const log = (page, tag) => {
  page.on('pageerror', (e) => { problems.push(`[${tag}] PAGEERROR ${e.message}`); console.log('PAGEERROR', tag, e.message); });
  page.on('console', (m) => {
    if (m.type() !== 'error' && m.type() !== 'warning') return;
    const t = m.text();
    if (IGNORE.some((r) => r.test(t))) return;
    problems.push(`[${tag}] ${m.type().toUpperCase()} ${t}`);
    console.log(m.type().toUpperCase(), tag, t.slice(0, 300));
  });
};
const clickRank1 = async (page) => {
  const pin = page.locator('.price-pin', { has: page.locator('.pin-rank', { hasText: /^1$/ }) }).first();
  if (await pin.count()) await pin.click(); else await page.locator('.price-pin').first().click();
};

if (want('vignettes')) {
  mkdirSync(prod, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: 'light' });
  const page = await ctx.newPage(); log(page, 'vignettes');
  await page.goto(`${base}/app?demo=${demo}#results`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await clickRank1(page);
  await page.waitForTimeout(2000);
  const r = await page.locator('#d-receipt [role=group]').first().boundingBox();
  const w = r.width + 48, h = Math.max(r.height + 48, w * 0.75);
  await page.locator('#d-receipt').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const r2 = await page.locator('#d-receipt [role=group]').first().boundingBox();
  await page.screenshot({ path: `${prod}receipt.png`, clip: { x: r2.x - 24, y: r2.y - (h - r2.height) / 2, width: w, height: h } });
  await page.addStyleTag({ content: '.maplibregl-ctrl, .maplibregl-ctrl-attrib, .map-legend { display: none !important; }' });
  await page.waitForTimeout(300);
  const m = await page.locator('.maplibregl-canvas').boundingBox();
  const mw = Math.min(m.width - 24, (m.height - 24) * 4 / 3), mh = mw * 0.75;
  await page.screenshot({ path: `${prod}route.png`, clip: { x: m.x + (m.width - mw) / 2, y: m.y + (m.height - mh) / 2 - 20, width: mw, height: mh } });
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
  for (const scheme of want('dark') ? ['light', 'dark'] : ['light']) {
    const dark = scheme === 'dark';
    const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, deviceScaleFactor: s.mobile ? 2 : 1, isMobile: !!s.mobile, hasTouch: !!s.mobile, colorScheme: scheme });
    const sfx = `${s.name}${dark ? '-dark' : ''}`;
    const open = async (url, wait = 1500, tag = url) => {
      const page = await ctx.newPage(); log(page, `${tag} ${sfx}`);
      await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(wait);
      return page;
    };
    const shot = (page, name, opts = {}) => page.screenshot({ path: `${out}${name}-${sfx}.png`, ...opts });
    if (dark) {
      // dark pass: the main screens only
      for (const [url, name] of [['/', 'landing'], [`/app?demo=${demo}#results`, 'homes'], [`/app?demo=${demo}#group`, 'group'], [`/app?demo=${demo}#week`, 'week']]) {
        const page = await open(url, 3000, name);
        await shot(page, name);
        await page.close();
      }
      await ctx.close();
      continue;
    }
    if (want('landing')) {
      const page = await open('/', 3000, 'landing');
      await shot(page, 'landing');
      await shot(page, 'landing-full', { fullPage: true });
      for (const tab of [/^Houses/, /^Co-ops/]) {
        await page.getByRole('tab', { name: tab }).click();
        await page.waitForTimeout(500);
      }
      await page.locator('#homes').screenshot({ path: `${out}landing-homes-coops-${sfx}.png` });
      await page.close();
    }
    if (want('results') || want('detail') || want('compare')) {
      const page = await open(`/app?demo=${demo}#results`, 3500, 'homes');
      if (want('results')) {
        await shot(page, 'homes');
        if (s.mobile) {
          await page.getByRole('button', { name: 'Map', exact: true }).click();
          await page.waitForTimeout(1800);
          await shot(page, 'homes-map');
          await page.getByRole('button', { name: 'List', exact: true }).click();
          await page.waitForTimeout(800);
        }
        await page.getByRole('tab', { name: /^Towers & apartments/ }).click();
        await page.waitForTimeout(1200);
        await shot(page, 'category');
        await page.getByRole('tab', { name: /^All homes/ }).click();
        await page.waitForTimeout(800);
      }
      if (want('detail')) {
        if (s.mobile) await page.locator('article h3 button').first().click();
        else await clickRank1(page);
        await page.waitForTimeout(1800);
        await shot(page, 'detail');
        const sc = s.mobile ? '.sheet' : '.results-pane';
        for (const sec of ['receipt', 'why', 'week', 'facts']) {
          const y = await page.evaluate((id) => { const el = document.querySelector(`#d-${id}`); return el ? el.offsetTop : null; }, sec);
          if (y == null) continue;
          await page.evaluate(([sel, top]) => { const el = document.querySelector(sel); if (el) el.scrollTop = top - 8; else window.scrollTo(0, top); }, [sc, y]);
          await page.waitForTimeout(500);
          await shot(page, `detail-${sec}`);
          if (sec === 'week') {
            const t = page.getByRole('radio', { name: 'Trip list' }).or(page.getByRole('button', { name: 'Trip list' })).first();
            if (await t.count()) { await t.click(); await page.waitForTimeout(300); await shot(page, 'detail-week-list'); await page.getByRole('radio', { name: 'Timeline' }).or(page.getByRole('button', { name: 'Timeline' })).first().click(); }
          }
        }
        await page.keyboard.press('Escape');
        await page.waitForTimeout(600);
      }
      if (want('compare')) {
        const t = page.locator('article .compare-toggle');
        await t.nth(0).click();
        await t.nth(1).click();
        await page.waitForTimeout(400);
        await shot(page, 'compare-tray');
        await page.getByRole('button', { name: /^Compare 2 homes/ }).click();
        await page.waitForTimeout(2500);
        await shot(page, 'compare');
      }
      await page.close();
    }
    if (want('week')) {
      const page = await open(`/app?demo=${demo}#week`, 2000, 'week');
      await shot(page, 'week-demo');
      await page.getByRole('button', { name: 'Clear grid' }).click().catch(() => {});
      const ta = page.locator('#describe');
      await ta.click();
      await ta.fill('');
      await ta.pressSequentially('EECS 281 lecture MWF 9-10:30 in BBB, Math 214 TTh 10 at East Hall, Chem 130 lab Tue 1-4 in the Chem building, gym at CCRB Mon/Wed 6pm, UgLi till 1am Thursdays', { delay: 4 });
      await page.waitForTimeout(300);
      await shot(page, 'week-typing');
      await page.getByRole('button', { name: /^(Build my week|Add to my week)/ }).click();
      await page.waitForTimeout(3500);
      await shot(page, 'week');
      if (!s.mobile) {
        // drag the first block down one hour, then resize it
        const ev = page.getByTestId('grid-event').first();
        const b = await ev.boundingBox();
        if (b) {
          await page.mouse.move(b.x + b.width / 2, b.y + 6); await page.mouse.down();
          await page.mouse.move(b.x + b.width / 2, b.y + 6 + 42, { steps: 6 }); await page.mouse.up();
          await page.waitForTimeout(600);
          const b2 = await ev.boundingBox();
          await page.mouse.move(b2.x + b2.width / 2, b2.y + b2.height - 2); await page.mouse.down();
          await page.mouse.move(b2.x + b2.width / 2, b2.y + b2.height + 30, { steps: 5 }); await page.mouse.up();
          await page.waitForTimeout(1200);
          await shot(page, 'week-dragged');
        }
      }
      await page.close();
    }
    for (const [sc, name] of [['robustness', 'how-sure'], ['baseline', 'portal'], ['methods', 'methods']]) {
      if (!want(sc)) continue;
      const page = await open(`/app?demo=${demo}#${sc}`, 4000, name);
      await shot(page, name);
      await shot(page, `${name}-full`, { fullPage: true });
      await page.close();
    }
    if (want('group')) {
      const page = await open(`/app?demo=${demo}#group`, 4500, 'group');
      await shot(page, 'group');
      await shot(page, 'group-full', { fullPage: true });
      await page.getByRole('button', { name: /Add roommate/ }).click();
      await page.waitForTimeout(3500);
      await shot(page, 'group-added', { fullPage: true });
      await page.getByRole('button', { name: /^Remove / }).last().click();
      await page.waitForTimeout(3000);
      await page.close();
    }
    if (want('add')) {
      const page = await open(`/app#add`, 1500, 'add');
      await shot(page, 'add');
      await page.getByRole('button', { name: /Use example/ }).click();
      await page.getByRole('button', { name: 'Extract facts', exact: true }).click();
      await page.waitForTimeout(3500);
      await shot(page, 'add-extracted', { fullPage: true });
      await page.close();
    }
    if (want('present') && !s.mobile) {
      const page = await open(`/app?demo=${demo}#results`, 3500, 'present');
      await page.keyboard.press('p');
      await page.waitForTimeout(1200);
      await shot(page, 'present-homes');
      await page.keyboard.press('3');
      await page.waitForTimeout(3000);
      await shot(page, 'present-how-sure');
      await page.close();
    }
    await ctx.close();
  }
}
await browser.close();
console.log(`done · ${problems.length} console problem(s)`);
for (const p of problems) console.log('  ', p.slice(0, 400));
process.exit(problems.length ? 1 : 0);
