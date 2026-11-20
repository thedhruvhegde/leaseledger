// Screenshot every screen in mock mode. Usage: VITE_API_MODE=mock npm run dev & ; node scripts/screenshots.mjs [baseUrl]
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const base = process.argv[2] ?? 'http://localhost:5173';
const out = new URL('../screenshots/', import.meta.url).pathname;
const screens = ['week', 'results', 'robustness', 'baseline', 'group', 'add', 'methods'];
const sizes = [{ name: 'desktop', width: 1920, height: 1080 }, { name: 'phone', width: 390, height: 844 }];
const only = process.env.ONLY?.split(',');
const demo = process.env.DEMO ?? 'maya-eecs';
const prefix = process.env.PREFIX ?? '';
const browser = await pw.chromium.launch();
for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: { width: s.width, height: s.height }, deviceScaleFactor: 1 });
  let page;
  const fresh = async () => {
    if (page) await page.close();
    page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
    page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
    if (process.env.DARK === '1') await page.emulateMedia({ colorScheme: 'dark' });
  };
  for (const sc of screens) {
    if (only && !only.includes(sc)) continue;
    await fresh();
    await page.goto(`${base}/?demo=${demo}#${sc}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(sc === 'robustness' || sc === 'results' ? 1800 : 1000);
    if (sc === 'add') {
      await page.getByText('Use example (fictional)').click();
      await page.getByRole('button', { name: 'Extract facts', exact: true }).click();
      await page.waitForTimeout(700);
    }
    await page.screenshot({ path: `${out}${prefix}${sc}-${s.name}${process.env.DARK === '1' ? '-dark' : ''}.png`, fullPage: process.env.FULL === '1' });
    console.log('shot', sc, s.name);
  }
  if (!only || only.includes('diff')) {
    // sensitivity: move a block and capture the drawer
    await fresh();
    await page.goto(`${base}/?demo=${demo}#results`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
      const st = window.__ll?.getState?.();
      if (st) st.setProfile((p) => ({ ...p, modes: ['walk', 'bus', 'bike'] }));
    });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${out}${prefix}diff-${s.name}.png` });
    console.log('shot diff', s.name);
  }
  await ctx.close();
}
await browser.close();
