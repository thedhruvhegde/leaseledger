// UI walkthrough of the running app, recorded with the Chrome DevTools screencast (real-time, not staged frames).
// Prereqs: API on :8000 (LLM_MODE=cached) and the web build served on an origin the API's CORS allows, e.g.
//   cd web && VITE_API_BASE=http://localhost:8000/api npx vite build --outDir /tmp/webdist --emptyOutDir
//   npx vite preview --outDir /tmp/webdist --port 4173 --strictPort
//   node media/scripts/record_walkthrough.mjs [http://localhost:4173]
// Output: media/videos/walkthrough.mp4 (+ .png poster, .json with what the app displayed at each step).
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const OUT = path.join(ROOT, 'media/videos');
const BASE = process.argv[2] || 'http://localhost:4173';
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'walk-'));
const WEEK = 'EECS 281 Tue/Thu 10-11:30 in EECS. EECS 370 Mon/Wed 1-2:30pm in BBB. Math 214 MWF 9:30-10:30 in GG Brown. Econ 101 Tue/Thu 2:30-4pm in LSA. Gym Tue/Thu 5:30-6:30pm at NCRB. Project team Mon/Thu 7-10:30pm at the Duderstadt.';

const OVERLAY = `
(() => {
  const css = \`
  #__cur{position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(26,26,26,.22);border:2px solid #1A1A1A;z-index:2147483647;pointer-events:none;transition:transform .12s}
  #__cur.down{transform:scale(.7);background:rgba(26,26,26,.5)}
  #__lt{position:fixed;left:24px;bottom:22px;z-index:2147483646;pointer-events:none;font:500 13px/1 'Inter Tight',system-ui,sans-serif;color:#4E4B47;background:rgba(237,232,224,.94);border:1px solid #B8B0A4;padding:8px 12px;border-radius:4px;letter-spacing:.01em}
  #__cap{position:fixed;right:24px;bottom:22px;z-index:2147483646;pointer-events:none;font:600 17px/1.2 'Inter Tight',system-ui,sans-serif;color:#EDE8E0;background:#1A1A1A;padding:10px 16px;border-radius:4px;opacity:0;transition:opacity .4s}
  \`;
  const add = () => {
    if (document.getElementById('__cur')) return;
    const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement('div'); c.id = '__cur'; document.body.appendChild(c);
    const lt = document.createElement('div'); lt.id = '__lt'; lt.textContent = 'listings: public listing text, Nov 20 2026 · synthetic ones labeled · recorded from the running app'; document.body.appendChild(lt);
    const cap = document.createElement('div'); cap.id = '__cap'; document.body.appendChild(cap);
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => c.classList.add('down'), true);
    addEventListener('mouseup', () => c.classList.remove('down'), true);
    window.__cap = (t) => { cap.textContent = t; cap.style.opacity = t ? 1 : 0; };
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();`;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
await ctx.addInitScript(OVERLAY);
const page = await ctx.newPage();
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
const cdp = await ctx.newCDPSession(page);
const frames = [];
cdp.on('Page.screencastFrame', async (f) => {
  const file = path.join(TMP, `${String(frames.length).padStart(6, '0')}.jpg`);
  fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
  frames.push({ file, ts: f.metadata.timestamp });
  cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
});
const log = [];
const cap = (t) => page.evaluate((t) => window.__cap && window.__cap(t), t);
const wait = (ms) => page.waitForTimeout(ms);
let mx = 800, my = 450;
async function moveTo(loc, opts = {}) {
  await loc.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
  const b = await loc.boundingBox();
  const x = b.x + (opts.fx ?? 0.5) * b.width, y = b.y + (opts.fy ?? 0.5) * b.height;
  const n = opts.steps ?? 22;
  for (let i = 1; i <= n; i++) { const k = i / n, e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; await page.mouse.move(mx + (x - mx) * e, my + (y - my) * e); await wait(12); }
  mx = x; my = y;
}
async function click(loc, opts) { await moveTo(loc, opts); await wait(150); await page.mouse.down(); await wait(90); await page.mouse.up(); }
async function snapshot(step) {
  const cards = await page.evaluate(() => [...document.querySelectorAll('ol[aria-label="Ranked homes"] > li')].slice(0, 4).map((e) => e.innerText.replace(/\s*\n\s*/g, ' | ').slice(0, 160)));
  const head = await page.evaluate(() => (document.querySelector('main h1, h1, h2') || {}).innerText || '');
  log.push({ step, t: frames.length ? frames[frames.length - 1].ts - frames[0].ts : 0, head, cards });
}

// ---- go
await page.goto(`${BASE}/app#week`);
await page.waitForSelector('#describe');
await page.mouse.move(mx, my);
await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
await wait(1200);
await cap('1 · Describe your week in plain English');
const box = page.locator('#describe');
await moveTo(box); await box.click();
await box.pressSequentially(WEEK, { delay: 14 });
await wait(500);
await click(page.getByRole('button', { name: /Build my week|Add to my week/ }).locator('visible=true').first());
await wait(2600);
await cap('2 · Parsed into a weekly grid (every block keeps its source words)');
await page.mouse.wheel(0, 380); await wait(1600);
await page.mouse.wheel(0, 260); await wait(1500);
await snapshot('parsed');
await page.mouse.wheel(0, -640); await wait(900);
await cap('3 · Budget and household');
const cap$ = page.getByLabel('Rent cap (per person)').locator('visible=true').first();
await moveTo(cap$); await cap$.click(); await cap$.selectText(); await cap$.pressSequentially('1400', { delay: 80 }); await cap$.press('Tab');
await wait(500);
const wage = page.getByLabel('Your hourly wage').locator('visible=true').first();
await wage.scrollIntoViewIfNeeded();
await moveTo(wage); await wage.click(); await wage.selectText(); await wage.pressSequentially('16', { delay: 100 }); await wage.press('Tab');
await wait(1500);
await cap('4 · Every home priced against this week: list + map');
const wc = page.getByRole('button', { name: 'Close what changed' }).locator('visible=true');
if (await wc.count()) { await click(wc.first()); await wait(600); }
await page.mouse.wheel(0, -3000); await wait(900);
const see = page.getByRole('button', { name: 'See homes on the map' }).locator('visible=true').first();
await click(see);
await page.waitForSelector('ol[aria-label="Ranked homes"] > li', { timeout: 4000 }).catch(async () => { await see.click(); await page.waitForSelector('ol[aria-label="Ranked homes"] > li'); });
await wait(3200);
await snapshot('results');
const first = page.locator('ol[aria-label="Ranked homes"] > li').first();
await moveTo(page.locator('ol[aria-label="Ranked homes"] > li').nth(1)); await wait(900);
await moveTo(first); await wait(700);
await cap('5 · Open #1: the all-in monthly receipt');
await click(first, { fy: 0.75 });
await wait(2200);
const mc = page.getByRole('button', { name: 'Monthly cost' }).locator('visible=true').first();
if (await mc.count()) { await click(mc); }
await wait(3600);
await snapshot('receipt');
await cap('6 · Value of time $8 → $20 an hour: does #1 flip?');
const back = page.getByRole('button', { name: /All homes/ }).locator('visible=true').first();
if (await back.count()) { await click(back); await wait(1500); }
await click(page.getByRole('button', { name: /All filters/ }).locator('visible=true').first());
await wait(1200);
const slider = page.getByLabel('Value of time').locator('visible=true').first();
const sb = await slider.boundingBox();
const val = Number(await slider.inputValue()), min = Number(await slider.getAttribute('min')), max = Number(await slider.getAttribute('max'));
const xOf = (v) => sb.x + 9 + (sb.width - 18) * (v - min) / (max - min);
await moveTo(slider, { fx: (xOf(val) - sb.x) / sb.width });
await page.mouse.down();
for (let i = 1; i <= 40; i++) { const v = val + (20 - val) * i / 40; await page.mouse.move(xOf(v), sb.y + sb.height / 2); mx = xOf(v); await wait(35); }
await page.mouse.up();
await wait(900);
await page.keyboard.press('Escape');
await moveTo(page.locator('ol[aria-label="Ranked homes"]').first(), { fy: 0.05 });
await wait(4200);
await snapshot('vot20');
await cap('');
await wait(800);
await cdp.send('Page.stopScreencast');
await page.screenshot({ path: path.join(OUT, 'walkthrough.png') });
await browser.close();

// ---- assemble (variable frame timing -> constant 30 fps)
const list = frames.map((f, i) => `file '${f.file}'\nduration ${Math.max(0.001, ((frames[i + 1]?.ts ?? f.ts + 1.0) - f.ts)).toFixed(4)}`).join('\n') + `\nfile '${frames[frames.length - 1].file}'\n`;
fs.writeFileSync(path.join(TMP, 'list.txt'), list);
const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(TMP, 'list.txt'),
  '-vf', 'scale=1920:1080:flags=lanczos,fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-movflags', '+faststart',
  path.join(OUT, 'walkthrough.mp4')], { stdio: 'inherit' });
fs.writeFileSync(path.join(OUT, 'walkthrough.json'), JSON.stringify({
  _provenance: { recorded: new Date().toISOString(), app: BASE + '/app', api: 'http://localhost:8000/api (LLM_MODE=cached)', web_build: 'current web/ (vite build)',
    note: 'Numbers on screen are the running app\'s own output for the typed week (no demo template, wage $16/h, rent cap $1,400).' },
  typed_week: WEEK, frames: frames.length, duration_s: frames[frames.length - 1].ts - frames[0].ts, steps: log }, null, 1));
fs.rmSync(TMP, { recursive: true, force: true });
console.log('walkthrough:', frames.length, 'frames', r.status === 0 ? 'ok' : 'ffmpeg failed');
