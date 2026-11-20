// Full guided tour of the running Lease Ledger site (~3 min), recorded with the Chrome DevTools screencast.
// Prereqs: API on :8000 (LLM_MODE=cached, warmup done) and the current web build served by `vite preview --port 5173`.
//   node media/scripts/record_full_demo.mjs [http://localhost:5173]
// Writes raw segment MP4s + section timestamps to media/videos/.work/ (git-ignored); assemble with make_demo_cuts.sh.
// Every number on screen is the app's live output; nothing is typed in except the user's week and a fictional sample listing.
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
const WORK = path.join(ROOT, 'media/videos/.work');
fs.mkdirSync(WORK, { recursive: true });
const BASE = process.argv[2] || 'http://localhost:5173';
const PACE = Number(process.env.PACE || 0.64); // scales every pause (not typing or mouse motion)
const WEEK = 'MWF 9-10:30 EECS 281 in BBB · TTh 2:30 Ross · UgLi Sun-Thu till 1am · Sat 10-4 Kerrytown';

const OVERLAY = `
(() => {
  const css = \`
  html{scroll-behavior:auto!important}
  #__cur{position:fixed;left:-40px;top:-40px;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:rgba(10,10,10,.82);box-shadow:0 0 0 2px rgba(255,255,255,.95),0 0 0 3px rgba(10,10,10,.18);z-index:2147483647;pointer-events:none;transition:transform .14s ease}
  #__cur.down{transform:scale(.62)}
  #__cur.ring::after{content:'';position:absolute;inset:-10px;border-radius:50%;border:2px solid rgba(10,10,10,.35);animation:__r .45s ease-out forwards}
  @keyframes __r{from{transform:scale(.4);opacity:1}to{transform:scale(1.25);opacity:0}}
  #__cap{position:fixed;left:24px;bottom:24px;z-index:2147483646;pointer-events:none;display:flex;align-items:center;gap:10px;
    font:600 15px/1 'Inter Tight Variable','Inter Tight','Inter Variable',system-ui,sans-serif;letter-spacing:-.005em;color:#0a0a0a;
    background:#fff;border:1px solid #d4d4d4;padding:10px 16px 10px 12px;border-radius:9999px;opacity:0;transform:translateY(6px);transition:opacity .35s ease,transform .35s ease}
  #__cap.on{opacity:1;transform:none}
  #__cap .n{font:600 11px/1 'Inter Variable',system-ui,sans-serif;font-variant-numeric:tabular-nums;color:#fff;background:#0a0a0a;border-radius:9999px;min-width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;padding:0 6px}
  #__cap .s{font:500 13px/1 'Inter Variable',system-ui,sans-serif;color:#737373}
  \`;
  const add = () => {
    if (document.getElementById('__cur')) return;
    const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement('div'); c.id = '__cur'; document.body.appendChild(c);
    const cap = document.createElement('div'); cap.id = '__cap'; document.body.appendChild(cap);
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.classList.add('down'); c.classList.remove('ring'); void c.offsetWidth; c.classList.add('ring'); }, true);
    addEventListener('mouseup', () => c.classList.remove('down'), true);
    window.__cap = (t, sub, n) => {
      if (!t) { cap.classList.remove('on'); return; }
      const set = () => { cap.innerHTML = (n ? '<span class="n">' + n + '</span>' : '') + '<span></span>' + (sub ? '<span class="s"></span>' : '');
        const sp = cap.querySelectorAll('span'); sp[n ? 1 : 0].textContent = t; if (sub) sp[sp.length - 1].textContent = sub; cap.classList.add('on'); };
      if (cap.classList.contains('on')) { cap.classList.remove('on'); setTimeout(set, 280); } else set();
    };
    window.__scrollAnim = (sel, to, ms) => new Promise((res) => {
      const el = sel ? document.querySelector(sel) : document.scrollingElement;
      if (!el) return res(0);
      const from = el.scrollTop, max = el.scrollHeight - el.clientHeight; to = Math.max(0, Math.min(max, to));
      const t0 = performance.now();
      const f = (t) => { const k = Math.min(1, (t - t0) / ms); const e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        el.scrollTop = from + (to - from) * e; if (k < 1) requestAnimationFrame(f); else res(to); };
      requestAnimationFrame(f);
    });
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();`;

const browser = await chromium.launch();
const sections = [];
let T0 = null; // epoch seconds of first frame of the current segment

function makeRecorder(page, cdp, name, maxW, maxH) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `demo-${name}-`));
  const frames = [];
  cdp.on('Page.screencastFrame', async (f) => {
    const file = path.join(dir, `${String(frames.length).padStart(6, '0')}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
    frames.push({ file, ts: f.metadata.timestamp });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  return {
    frames, dir,
    start: () => cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: maxW, maxHeight: maxH, everyNthFrame: 1 }),
    async stop() { await page.waitForTimeout(300); await cdp.send('Page.stopScreencast'); this.end = Date.now() / 1000; },
    assemble(out, vf) {
      const fr = frames;
      const list = fr.map((f, i) => `file '${f.file}'\nduration ${Math.max(0.001, ((fr[i + 1]?.ts ?? this.end) - f.ts)).toFixed(4)}`).join('\n') + `\nfile '${fr[fr.length - 1].file}'\n`;
      fs.writeFileSync(path.join(dir, 'list.txt'), list);
      const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'),
        '-vf', vf, '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', out], { stdio: 'inherit' });
      const dur = this.end - fr[0].ts;
      console.log(name, fr.length, 'frames', dur.toFixed(1), 's', (fr.length / dur).toFixed(1), 'fps', r.status === 0 ? 'ok' : 'FAIL');
      fs.rmSync(dir, { recursive: true, force: true });
      return { frames: fr.length, duration: dur, first: fr[0].ts };
    },
  };
}

function helpers(page, segName) {
  let mx = 960, my = 540;
  const wait = (ms) => page.waitForTimeout(Math.round(ms * PACE));
  const rawWait = (ms) => page.waitForTimeout(ms);
  const mark = (id) => { sections.push({ seg: segName, id, at: Date.now() / 1000 }); };
  const cap = (t, sub, n) => page.evaluate(([t, sub, n]) => window.__cap && window.__cap(t, sub, n), [t, sub ?? null, n ?? null]);
  async function moveXY(x, y, speed = 1) {
    const d = Math.hypot(x - mx, y - my);
    const n = Math.max(8, Math.min(30, Math.round(d / 30 / speed)));
    const sx = mx, sy = my;
    for (let i = 1; i <= n; i++) {
      const k = i / n, e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      await page.mouse.move(sx + (x - sx) * e, sy + (y - sy) * e);
      await rawWait(11);
    }
    mx = x; my = y;
  }
  async function box(loc, scroll = true) {
    if (scroll) await loc.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
    return loc.boundingBox();
  }
  async function moveTo(loc, o = {}) {
    const b = await box(loc, o.scroll !== false);
    if (!b) throw new Error('no box');
    await moveXY(b.x + (o.fx ?? 0.5) * b.width, b.y + (o.fy ?? 0.5) * b.height, o.speed);
  }
  async function click(loc, o = {}) { await moveTo(loc, o); await wait(o.pre ?? 180); await page.mouse.down(); await wait(80); await page.mouse.up(); await wait(o.post ?? 0); }
  async function type(text) {
    for (const ch of text) {
      await page.keyboard.type(ch);
      let d = 48 + Math.random() * 40;
      if (ch === ' ') d += 25;
      if (ch === '·') d += 160;
      await rawWait(d);
    }
  }
  const scrollTo = (sel, to, ms) => page.evaluate(([s, t, m]) => window.__scrollAnim(s, t, m), [sel, to, Math.round(ms * 0.85)]);
  const scrollBy = async (sel, dy, ms) => { const cur = await page.evaluate((s) => (s ? document.querySelector(s) : document.scrollingElement).scrollTop, sel); return scrollTo(sel, cur + dy, ms); };
  // scroll so that element top sits `off` px below the scroller's top
  async function scrollToEl(sel, elSel, off, ms) {
    const to = await page.evaluate(([s, e, off]) => {
      const sc = s ? document.querySelector(s) : document.scrollingElement; const el = document.querySelector(e);
      const top = s ? sc.getBoundingClientRect().top : 0;
      return sc.scrollTop + el.getBoundingClientRect().top - top - off;
    }, [sel, elSel, off]);
    return scrollTo(sel, to, ms);
  }
  return { wait, mark, cap, moveXY, moveTo, click, type, scrollTo, scrollBy, scrollToEl, pos: () => [mx, my], setPos: (x, y) => { mx = x; my = y; } };
}

const log = {};
const snap = async (page, k, fn) => { try { log[k] = await page.evaluate(fn); } catch (e) { log[k] = String(e); } };
const cardsFn = () => [...document.querySelectorAll('ol[aria-label="Ranked homes"] > li')].slice(0, 9).map((e) => e.innerText.replace(/\s*\n\s*/g, ' | ').slice(0, 140));

// ======================= Segment 1: desktop tour =======================
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await ctx.addInitScript(OVERLAY);
const page = await ctx.newPage();
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
const cdp = await ctx.newCDPSession(page);
const rec1 = makeRecorder(page, cdp, 'desktop', 1920, 1080);
const H = helpers(page, 'desktop');
const { wait, mark, cap, moveXY, moveTo, click, type, scrollTo, scrollBy, scrollToEl } = H;

await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await page.waitForSelector('#hero-week');
await page.waitForFunction(() => document.querySelectorAll('#homes li').length > 0, null, { timeout: 20000 });
await page.waitForFunction(() => /#1 is/.test(document.querySelector('[data-testid=canon-caption]')?.textContent || ''), null, { timeout: 30000 }).catch(() => {});
// preload the fonts used by the caption
await page.evaluate(() => document.fonts.ready);
await page.mouse.move(1180, 700); H.setPos(1180, 700);
await rec1.start();
await wait(600);

// --- Landing
mark('landing');
await cap('Lease Ledger', 'Ann Arbor rentals, ranked by what your week costs');
await wait(2200);
await moveTo(page.locator('#hero-h'), { fx: 0.3 }); await wait(500);
const samples = page.locator('#hero a[href*="demo="]');
for (const i of [0, 3]) { await moveTo(samples.nth(i), { speed: 1.4 }); await wait(450); }
await wait(400);
mark('landing-vignettes');
await scrollToEl(null, '#shot-h', 90, 1500);
await moveTo(page.locator('.vignette').nth(0)); await wait(1000);
await moveTo(page.locator('.vignette').nth(1)); await wait(1000);
await moveTo(page.locator('.vignette').nth(2)); await wait(1100);
mark('landing-homes');
await scrollToEl(null, '#homes', 70, 1500);
await wait(700);
await click(page.locator('#homes [role=tab]').nth(1)); await wait(1300);
await click(page.locator('#homes [role=tab]').nth(0)); await wait(500);
await moveTo(page.locator('#homes li').nth(0)); await wait(700);
await moveTo(page.locator('#homes li').nth(1)); await wait(700);
mark('landing-sources');
await scrollToEl(null, '#sources', 70, 1500);
await moveTo(page.locator('#sources dl'), { fx: 0.4, fy: 0.3 }); await wait(2000);
await scrollTo(null, 0, 1600);
await wait(300);

// --- Describe your week (landing search bar)
mark('type-week');
await cap('Describe your week', 'in plain words, the way you would text a friend');
const hero = page.locator('#hero #hero-week');
await click(hero, { fx: 0.15 });
await wait(400);
await type(WEEK);
await wait(900);
await click(page.locator('#hero form button[type=submit]'));
await page.waitForSelector('ol[aria-label="Ranked homes"] > li', { timeout: 20000 });
await wait(2600);
await snap(page, 'typed_week_results', cardsFn);
// Your week: parsed blocks with their quotes
mark('week-grid');
await click(page.getByRole('button', { name: 'Your week', exact: true }).first());
await wait(1500);
const bbb = page.locator('[title^="EECS 281 in BBB"]').first();
await wait(600);
await moveTo(bbb); await wait(900);
await click(bbb); await wait(900);
const ed = page.locator('[role=dialog][aria-label^="Edit EECS 281"]');
if (await ed.count()) { await ed.first().scrollIntoViewIfNeeded().catch(() => {}); await moveTo(ed.locator('blockquote').first()); }
await snap(page, 'bbb_editor', () => document.querySelector('[role=dialog][aria-label^="Edit EECS 281"]')?.innerText.slice(0, 300));
await wait(2600);
const closeEd = page.getByRole('button', { name: 'Close editor' });
if (await closeEd.count()) { await click(closeEd.first()); await wait(400); }
const kt = page.locator('[title^="Kerrytown"]').first();
if (await kt.count()) { await moveTo(kt); await wait(900); }
await wait(400);

// --- Switch to the canonical sample week
mark('sample-week');
await cap('Sample week', 'North Campus engineer');
await scrollTo(null, 0, 700);
await click(page.locator('header a[aria-label$="home"]').first());
await page.waitForSelector('#hero-week');
await wait(900);
await click(page.locator('#hero a', { hasText: 'North Campus engineer' }));
await page.waitForFunction(() => /\$8\.00\/h/.test(document.body.innerText) && document.querySelectorAll('ol[aria-label="Ranked homes"] > li').length > 10, null, { timeout: 30000 });
await page.waitForFunction(() => !/Updating/.test(document.body.innerText), null, { timeout: 15000 }).catch(() => {});
await wait(1200);

// --- Homes
mark('homes');
await cap('Homes ranked by all-in cost', 'all 69 observed listings, list + map');
await snap(page, 'homes', cardsFn);
await snap(page, 'homes_head', () => document.querySelector('.results-pane')?.innerText.slice(0, 400));
await moveTo(page.locator('.results-pane h1, .results-pane h2').first(), { fx: 0.3 }); await wait(1200);
await moveTo(page.getByText(/Lowest rent isn.t the cheapest week/).first(), { fx: 0.3 }); await wait(2200);
const tabs = page.locator('[role=tablist][aria-label="Home type"] [role=tab], [role=tablist][aria-label="Home type"] button');
await click(tabs.nth(3)); await wait(1500);
await click(tabs.nth(1)); await wait(1300);
await click(tabs.nth(0)); await wait(900);
// hover pins on the map
for (const r of [2, 3, 1]) {
  const pin = page.locator(`button.price-pin[aria-label^="Rank ${r},"]`).first();
  if (await pin.count()) { await moveTo(pin, { scroll: false }); await wait(850); }
}
// open #1
mark('detail');
await cap('The receipt', '#1 for this week, line by line');
const first = page.locator('ol[aria-label="Ranked homes"] > li').first();
await click(first, { fy: 0.72 });
await page.waitForSelector('#d-receipt', { timeout: 10000 });
await wait(1500);
await snap(page, 'detail_top', () => document.querySelector('.results-pane')?.innerText.slice(0, 600));
await scrollToEl('.results-pane', '#d-receipt', 10, 1300);
await moveTo(page.locator('#d-receipt'), { fx: 0.3, fy: 0.25, scroll: false }); await wait(1600);
await moveTo(page.locator('#d-receipt'), { fx: 0.3, fy: 0.75, scroll: false }); await wait(1600);
await snap(page, 'receipt', () => document.querySelector('#d-receipt')?.innerText.slice(0, 900));
await scrollToEl('.results-pane', '#d-why', 10, 1100); await wait(2600);
await scrollToEl('.results-pane', '#d-week', 10, 1100);
await moveTo(page.locator('#d-week'), { fx: 0.5, fy: 0.5, scroll: false }); await wait(2400);
await scrollToEl('.results-pane', '#d-facts', 10, 1100); await wait(1800);
await scrollToEl('.results-pane', '#d-sources', 10, 1100); await wait(1800);

// --- Compare #1 vs the lowest rent
mark('compare');
await cap('Compare', '#1 vs the lowest rent');
await click(page.getByRole('button', { name: /All homes/ }).first());
await wait(1200);
await scrollTo('.results-pane', 0, 400);
await click(page.locator('button[aria-label^="Add to compare: ICC Escher House - double"]').first()); await wait(600);
const hill = page.locator('button[aria-label^="Add to compare: Hillcrest Manor"]').first();
await scrollToEl('.results-pane', 'ol[aria-label="Ranked homes"] > li:nth-child(7)', 20, 1200);
await click(hill, { scroll: false }); await wait(700);
await click(page.getByRole('button', { name: /Compare 2 homes/ })); await wait(1800);
await snap(page, 'compare', () => document.querySelector('.results-pane')?.innerText.slice(0, 1200));
await moveTo(page.locator('.results-pane').getByText('Line by line').first(), { scroll: false }); await wait(800);
await scrollBy('.results-pane', 380, 1400); await wait(2600);
await scrollBy('.results-pane', 380, 1300); await wait(1500);

// --- Change one thing: value of time $8 -> $20
mark('vot');
await cap('Change one thing', 'value of time $8 → $20 an hour');
await click(page.getByRole('button', { name: /All homes/ }).first()); await wait(600);
const clear = page.getByRole('region', { name: 'Compare tray' }).getByRole('button', { name: 'Clear' });
if (await clear.count()) { await click(clear); await wait(500); }
await click(page.getByRole('button', { name: /All filters/ }).first()); await wait(900);
const slider = page.getByLabel('Value of time').first();
const sb = await slider.boundingBox();
const min = 0, max = 40, v0 = Number(await slider.inputValue());
const xOf = (v) => sb.x + 8 + (sb.width - 16) * (v - min) / (max - min);
await moveXY(xOf(v0), sb.y + sb.height / 2); await wait(300);
await page.mouse.down();
// one quick drag (< 1.5 s) so the app's 'What changed' burst compares against $8, not a mid-drag value
for (let i = 1; i <= 24; i++) { const k = i / 24, e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; const v = v0 + (20 - v0) * e; await page.mouse.move(xOf(v), sb.y + sb.height / 2); H.setPos(xOf(v), sb.y + sb.height / 2); await page.waitForTimeout(28); }
await page.mouse.up();
// make sure it landed on exactly 20
if (Number(await slider.inputValue()) !== 20) { await slider.fill('20'); }
await wait(400);
await wait(1200);
await page.keyboard.press('Escape');
await page.waitForFunction(() => /\$20\.00\/h/.test(document.body.innerText), null, { timeout: 10000 }).catch(() => {});
await wait(1500);
await snap(page, 'vot20', cardsFn);
await snap(page, 'drawer', () => document.querySelector('.drawer')?.innerText.slice(0, 700));
await moveTo(page.locator('ol[aria-label="Ranked homes"] > li').first(), { fy: 0.6 }); await wait(1400);
await moveTo(page.locator('ol[aria-label="Ranked homes"] > li').nth(1), { fy: 0.6 }); await wait(1200);
const drawer = page.locator('.drawer');
if (await drawer.count()) {
  await moveTo(drawer.getByText('Your #1 changed').first(), { scroll: false }).catch(() => {}); await wait(1200);
  const bef = drawer.getByRole('button', { name: 'Before' });
  if (await bef.count()) { await click(bef.first(), { scroll: false }); await wait(1500); await click(drawer.getByRole('button', { name: 'After' }).first(), { scroll: false }); await wait(1300); }
}
// put the value of time back (50% of wage = $8) so the next pages match the deck
await click(page.getByRole('button', { name: /All filters/ }).first()); await wait(700);
await click(page.getByRole('button', { name: 'Use 50% of my wage instead' }).first()); await wait(900);
await page.keyboard.press('Escape'); await wait(300);
const close = page.getByRole('button', { name: /Close what changed/ });
if (await close.count()) { await click(close.first(), { scroll: false }); }
await page.waitForFunction(() => /\$8\.00\/h/.test(document.body.innerText), null, { timeout: 10000 }).catch(() => {});
await wait(900);

// --- How sure
const nav = (label) => page.locator('header nav button', { hasText: label }).first();
mark('robustness');
await cap('How sure are we', '2,000 plausible semesters');
await click(nav('How sure are we?'));
await page.waitForFunction(() => /of 2,000 plausible semesters/.test(document.body.innerText), null, { timeout: 30000 });
await wait(1200);
await snap(page, 'robustness', () => document.querySelector('main')?.innerText.slice(0, 900));
await moveTo(page.getByText(/plausible semesters/).first(), { fx: 0.4 }); await wait(2600);
await moveTo(page.getByText('What could flip it').first()); await wait(2200);
await scrollBy(null, 760, 1800); await wait(2400);
await scrollTo(null, 0, 900);

// --- Portal vs your week
mark('baseline');
await cap('Portal vs your week', 'rent + distance vs the whole week');
await click(nav('Portal vs. your week'));
await wait(2200);
await snap(page, 'baseline', () => document.querySelector('main')?.innerText.slice(0, 500));
await moveTo(page.getByText('Homes that change position').first()); await wait(1600);
await scrollBy(null, 330, 1300); await wait(1200);
await scrollBy(null, 700, 3200); await wait(1200);
await scrollTo(null, 0, 900);

// --- Group Week
mark('group');
await cap('Group Week', '3 roommates, envy-free rent split');
await click(nav('Group Week'));
await wait(2500);
await moveTo(page.locator('main input[aria-label="Alias"]').nth(1)); await wait(1200);
const envy = page.getByText('Envy matrix').first();
await page.evaluate(() => { const el = [...document.querySelectorAll('main *')].find((e) => e.childElementCount === 0 && /Apartments for/.test(e.textContent)); if (el) el.setAttribute('data-x', 'apts'); });
await scrollToEl(null, '[data-x=apts]', 90, 1500); await wait(800);
await moveTo(page.getByText('Fair split').first()); await wait(1600);
await snap(page, 'group', () => document.querySelector('main')?.innerText.slice(0, 1500));
await moveTo(envy, { scroll: false }); await wait(900);
await moveTo(page.getByText('envy-free').first(), { scroll: false }); await wait(2200);
await scrollTo(null, 0, 900);

// --- Add a listing
mark('add');
await cap('Add a listing', 'sample text, fictional');
await click(nav('Add a listing'));
await wait(1500);
const lt = page.locator('#ltext');
await click(lt, { fx: 0.3, fy: 0.3 });
await click(page.getByRole('button', { name: 'Use example (fictional)' })); await wait(1300);
await click(page.getByRole('button', { name: 'Extract facts', exact: true })); await wait(2200);
await snap(page, 'add', () => document.querySelector('main')?.innerText.slice(0, 1400));
await moveTo(page.getByText('Where each fact came from').first(), { fx: 0.2 }); await wait(700);
const marks = page.locator('main mark');
const nm = await marks.count();
for (const i of [2, 7, 8]) if (i < nm) { await moveTo(marks.nth(i), { scroll: false }); await wait(700); }
await moveTo(page.getByText(/Application fee over/).first()); await wait(2400);
await moveTo(page.getByText('Extracted facts').first(), { fx: 0.3 }); await wait(500);
await moveTo(page.getByText('Admin fee', { exact: true }).first(), { scroll: false }); await wait(1600);

// --- Methods & sources
mark('methods');
await cap('Methods & sources', 'data, assumptions, equations, limits');
await click(nav('Methods & sources'));
await wait(1800);
await scrollBy(null, 420, 1500); await wait(1500);
const hpos = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('main h3')].map((h) => [h.innerText.slice(0, 12), Math.round(h.getBoundingClientRect().top + scrollY)])));
await scrollTo(null, hpos['Assumptions '] - 80, 1600); await wait(1500);
await scrollTo(null, hpos['Equations'] - 80, 2200); await wait(2200);
await scrollBy(null, 560, 2000); await wait(1800);
await scrollBy(null, 560, 2000); await wait(1200);
const lim = Object.entries(hpos).find(([k]) => k.startsWith('Limitations'));
await scrollTo(null, lim[1] - 80, 1600); await wait(2600);
await cap('');
await wait(500);
await rec1.stop();
const seg1 = rec1.assemble(path.join(WORK, 'seg1.mp4'), 'scale=1920:1080:flags=lanczos');

// ======================= Segment 2: phone =======================
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await mctx.addInitScript(OVERLAY);
await mctx.addInitScript(() => { addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = '#__cap{display:none!important} #__cur{width:22px!important;height:22px!important;margin:-11px 0 0 -11px!important;background:rgba(10,10,10,.35)!important}'; document.head.appendChild(s); }); });
const mp = await mctx.newPage();
const mcdp = await mctx.newCDPSession(mp);
const rec2 = makeRecorder(mp, mcdp, 'phone', 780, 1688);
const M = helpers(mp, 'phone');
await mp.goto(`${BASE}/app?demo=north-engineer#results`, { waitUntil: 'networkidle' });
await mp.waitForFunction(() => /\$8\.00\/h/.test(document.body.innerText) && document.querySelectorAll('ol[aria-label="Ranked homes"] > li').length > 10, null, { timeout: 30000 });
await mp.waitForTimeout(1200);
await mp.mouse.move(300, 700); M.setPos(300, 700);
await rec2.start();
M.mark('phone');
await M.wait(1500);
await M.moveTo(mp.getByText(/Lowest rent isn.t the cheapest week/).first(), { fx: 0.5 }); await M.wait(1400);
const pscroll = await mp.evaluate(() => { const ol = document.querySelector('ol[aria-label="Ranked homes"]'); let e = ol; while (e && e !== document.body) { const s = getComputedStyle(e); if (/(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight) { e.setAttribute('data-ps', '1'); return '[data-ps]'; } e = e.parentElement; } return null; });
await M.scrollBy(pscroll, 520, 1500); await M.wait(1200);
await M.scrollBy(pscroll, -520, 1000); await M.wait(400);
const mapBtn = mp.getByRole('button', { name: /^Map$/ }).first();
if (await mapBtn.count()) {
  await M.click(mapBtn, { scroll: false }); await M.wait(3000);
  const mpin = mp.locator('button.price-pin[aria-label^="Rank 1,"]').first();
  if (await mpin.count()) { await M.moveTo(mpin, { scroll: false }); await M.wait(1400); }
  const listBtn = mp.getByRole('button', { name: /^List$/ }).first();
  if (await listBtn.count()) { await M.click(listBtn, { scroll: false }); await M.wait(1000); }
}
M.mark('phone-sheet');
await M.click(mp.locator('ol[aria-label="Ranked homes"] > li').first(), { fx: 0.3, fy: 0.12, scroll: false });
await M.wait(2200);
const sheet = '.sheet';
await M.scrollToEl(sheet, '#d-receipt', 50, 1400).catch(() => {}); await M.wait(2600);
await M.scrollToEl(sheet, '#d-week', 50, 1400).catch(() => {}); await M.wait(2000);
await M.scrollTo(sheet, 0, 900).catch(() => {}); await M.wait(600);
await M.wait(600);
await rec2.stop();
await mp.screenshot({ path: path.join(WORK, 'phone-last.png') });
const seg2 = rec2.assemble(path.join(WORK, 'seg2.mp4'), 'scale=780:1688:flags=lanczos');
await mctx.close();

// ======================= Segment 3: back to the landing hero =======================
const cdp3 = await ctx.newCDPSession(page);
const rec3 = makeRecorder(page, cdp3, 'end', 1920, 1080);
const E = helpers(page, 'end');
await page.evaluate(() => window.__cap(''));
await page.locator('header a[aria-label$="home"]').first().click();
await page.waitForSelector('#hero-week');
await page.evaluate(() => window.scrollTo(0, 0));
await page.mouse.move(1300, 760); E.setPos(1300, 760);
await page.waitForTimeout(1200);
await rec3.start();
E.mark('end');
await E.wait(500);
await E.cap('Lease Ledger', 'one monthly number per home, for your week');
await E.moveTo(page.locator('#hero #hero-week'), { fx: 0.55 }); await E.wait(3800);
await E.moveXY(1300, 760); await E.wait(2400);
await rec3.stop();
const seg3 = rec3.assemble(path.join(WORK, 'seg3.mp4'), 'scale=1920:1080:flags=lanczos');
await browser.close();

const firsts = { desktop: seg1.first, phone: seg2.first, end: seg3.first };
const out = {
  _provenance: { recorded: new Date().toISOString(), app: BASE, api: 'http://localhost:8000/api (LLM_MODE=cached)', web_build: 'current web/ (vite build + preview)',
    note: 'Typed week first (landing search bar), then the "North Campus engineer" sample week ranked against all observed listings (the Homes default).' },
  typed_week: WEEK,
  segments: { seg1: { duration: seg1.duration, frames: seg1.frames }, seg2: { duration: seg2.duration, frames: seg2.frames }, seg3: { duration: seg3.duration, frames: seg3.frames } },
  sections: sections.map((s) => ({ seg: s.seg, id: s.id, t: +(s.at - firsts[s.seg]).toFixed(2) })),
  shown: log,
};
fs.writeFileSync(path.join(WORK, 'sections.json'), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.sections));
