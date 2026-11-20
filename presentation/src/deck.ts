// Deck controller: chapters, 0.6 s cross-fade navigation (keys, wheel, nav dots, arrow buttons), reveal steps,
// Cartesian chrome (right-edge dots, bottom-left square arrows, bottom-right counter), presenter timer (T),
// speaker-notes window (S) over BroadcastChannel, appendix mode (A).
import { reducedMotion, runCountUps, syncMedia } from './lib';
import { onPlan, onStatus, status } from './api';

export interface Chapter {
  id: string;
  title: string;
  /** talk-time budget in seconds (appendix chapters: 0) */
  budget: number;
  appendix?: boolean;
  /** Roman numeral shown in the chapter eyebrow and on the agenda ("III"); cover/agenda/close have none */
  numeral?: string;
  /** short agenda line under the title */
  gist?: string;
  /** number of click-to-reveal steps (elements carrying data-step="1..n") */
  steps?: number;
  /** plan keys whose arrival re-renders this chapter */
  deps?: string[];
  render(): string;
  mount?(el: HTMLElement): void;
  enter?(el: HTMLElement): void;
  leave?(el: HTMLElement): void;
  step?(el: HTMLElement, n: number): void;
  notes(): string;
}

type St = { el: HTMLElement; stage: HTMLElement; step: number; ch: Chapter };
const TALK_BUDGET = () => chapters.filter((c) => !c.appendix).reduce((s, c) => s + c.budget, 0);

let chapters: Chapter[] = [];
/** read-only view for the agenda slide */
export const allChapters = () => chapters;
let states: St[] = [];
let cur = 0;
let appendix = new URLSearchParams(location.search).has('appendix');
const chan = 'BroadcastChannel' in window ? new BroadcastChannel('lease-ledger-deck') : null;

// ---- timer ----
const timer = { running: false, elapsed: 0, last: 0, per: {} as Record<string, number> };
function tick() {
  const now = performance.now();
  if (timer.running) {
    const dt = (now - timer.last) / 1000;
    timer.elapsed += dt;
    const id = states[cur]?.ch.id;
    if (id) timer.per[id] = (timer.per[id] ?? 0) + dt;
  }
  timer.last = now;
}
const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, '0')}`;

export function mountDeck(root: HTMLElement, list: Chapter[]) {
  chapters = list;
  root.innerHTML = '';
  states = chapters.map((ch) => {
    const el = document.createElement('section');
    el.className = 'chapter';
    el.id = ch.id;
    el.dataset.title = ch.title;
    const stage = document.createElement('div');
    stage.className = 'stage';
    el.appendChild(stage);
    root.appendChild(el);
    return { el, stage, step: 0, ch };
  });
  states.forEach((s) => s.el.addEventListener('deck:rerender', () => { renderChapter(s); if (s === states[cur]) { runCountUps(s.stage); s.ch.enter?.(s.stage); } }));
  states.forEach((s) => s.el.addEventListener('deck:setstep', (e) => { s.step = Math.min(s.ch.steps ?? 0, (e as CustomEvent).detail); applySteps(s); }));
  states.forEach(renderChapter);
  buildChrome();
  applyAppendix();
  fit();
  addEventListener('resize', fit);

  // wheel / trackpad: one gesture = one step (throttled), never inside the embedded app (iframes eat their own wheel)
  let wheelLock = 0;
  addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaY) < 24 || performance.now() < wheelLock) return;
    wheelLock = performance.now() + 750;
    e.deltaY > 0 ? next() : prev();
  }, { passive: true });

  onPlan((name) => {
    states.forEach((s) => {
      if (name === '__done' || s.ch.deps?.includes(name)) {
        renderChapter(s);
        if (s === states[cur]) { s.el.classList.add('active'); runCountUps(s.stage); s.ch.enter?.(s.stage); }
      }
    });
  });

  addEventListener('keydown', onKey);
  // chapters can link to each other: el.dispatchEvent(new CustomEvent('deck:goto', {bubbles:true, detail:'math'}))
  document.addEventListener('deck:goto', (e) => { const i = states.findIndex((s) => s.ch.id === (e as CustomEvent).detail); if (i >= 0) go(i); });
  // hash deep link (#demo, #robustness...)
  const h = location.hash.slice(1);
  const start = Math.max(0, states.findIndex((s) => s.ch.id === h));
  requestAnimationFrame(() => go(start, false));

  setInterval(() => { tick(); paintTimer(); broadcast(); }, 250);
  chan?.addEventListener('message', (ev) => {
    const m = ev.data;
    if (m?.type === 'hello') broadcast(true);
    if (m?.type === 'cmd') {
      if (m.cmd === 'next') next();
      if (m.cmd === 'prev') prev();
      if (m.cmd === 'timer') toggleTimer();
      if (m.cmd === 'reset') resetTimer();
      if (m.cmd === 'goto') go(m.idx);
    }
  });
}

function renderChapter(s: St) {
  s.stage.innerHTML = s.ch.render();
  s.ch.mount?.(s.stage);
  applySteps(s);
  // click-to-reveal: clicking a pending step reveals up to it
  s.stage.querySelectorAll<HTMLElement>('[data-step]').forEach((node) => {
    node.addEventListener('click', () => {
      const n = Number(node.dataset.step);
      if (n > s.step) { s.step = n; applySteps(s); }
    });
  });
}
function applySteps(s: St) {
  s.stage.querySelectorAll<HTMLElement>('[data-step]').forEach((node) => node.classList.toggle('shown', Number(node.dataset.step) <= s.step));
  s.ch.step?.(s.stage, s.step);
  syncMedia();
  broadcast();
}

function fit() {
  const sc = Math.min(innerWidth / 1920, innerHeight / 1080);
  document.documentElement.style.setProperty('--s', String(sc));
}

const visible = () => states.map((s, i) => i).filter((i) => appendix || !states[i].ch.appendix);

function setCurrent(i: number) {
  const prevS = states[cur];
  if (prevS && prevS !== states[i]) { prevS.el.classList.remove('active'); prevS.el.setAttribute('aria-hidden', 'true'); prevS.ch.leave?.(prevS.stage); }
  states[i].el.removeAttribute('aria-hidden');
  cur = i;
  const s = states[i];
  s.el.classList.add('active');
  runCountUps(s.stage);
  s.ch.enter?.(s.stage);
  syncMedia();
  paintRail();
  if (history.replaceState) history.replaceState(null, '', `${location.pathname}${location.search}#${s.ch.id}`);
  broadcast();
}

export function go(i: number, smooth = true) {
  i = Math.max(0, Math.min(states.length - 1, i));
  if (states[i].ch.appendix && !appendix) { appendix = true; applyAppendix(); }
  document.documentElement.classList.toggle('instant', !smooth || reducedMotion());
  if (i !== cur || !states[i].el.classList.contains('active')) setCurrent(i);
  if (!smooth) requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove('instant')));
}
function next() {
  const s = states[cur];
  const n = s.ch.steps ?? 0;
  if (s.step < n) { s.step++; applySteps(s); return; }
  const v = visible(); const k = v.indexOf(cur);
  if (k < v.length - 1) go(v[k + 1]);
}
function prev() {
  const s = states[cur];
  if (s.step > 0) { s.step--; applySteps(s); return; }
  const v = visible(); const k = v.indexOf(cur);
  if (k > 0) go(v[k - 1]);
}

function toggleTimer() { tick(); timer.running = !timer.running; document.querySelector('.timer')?.classList.add('on'); paintTimer(); toast(timer.running ? 'Timer running' : 'Timer paused'); }
function resetTimer() { timer.elapsed = 0; timer.per = {}; timer.running = false; paintTimer(); toast('Timer reset'); }

function onKey(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  const help = document.querySelector('.help')!;
  if (k === 'Escape') { help.classList.remove('on'); return; }
  if (['ArrowRight', 'ArrowDown', 'PageDown', 'Enter'].includes(k) || (k === ' ' && !e.shiftKey)) { e.preventDefault(); next(); }
  else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(k) || (k === ' ' && e.shiftKey)) { e.preventDefault(); prev(); }
  else if (k === 'Home') { e.preventDefault(); go(0); }
  else if (k === 'End') { e.preventDefault(); const v = visible(); go(v[v.length - 1]); }
  else if (/^[0-9]$/.test(k)) { const i = k === '0' ? 9 : Number(k) - 1; if (i < states.length) go(i); }
  else if (k === 't') toggleTimer();
  else if (k === 'T' || k === 'r') resetTimer();
  else if (k === 's' || k === 'S') openNotes();
  else if (k === 'a' || k === 'A') { appendix = !appendix; applyAppendix(); toast(appendix ? 'Appendix chapters shown' : 'Talk mode: appendix hidden'); }
  else if (k === 'f' || k === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(() => {}); }
  else if (k === '?' || k === 'h') help.classList.toggle('on');
}

function applyAppendix() {
  states.forEach((s, i) => s.el.classList.toggle('appendix-hidden', !!s.ch.appendix && !appendix && i !== cur));
  paintRail();
}

export function openNotes() {
  const w = window.open(`./notes.html${location.search}`, 'lease-ledger-notes', 'width=1100,height=760');
  if (!w) toast('Pop-up blocked: allow pop-ups for this page, then press S again');
  setTimeout(() => broadcast(true), 600);
}

// ---- chrome (Cartesian: right-edge dots, bottom-left square arrows, bottom-right counter; no top bar) ----
function buildChrome() {
  // bottom-edge glow: three soft hues, very low opacity, below every piece of chrome
  const glow = document.createElement('div'); glow.className = 'glow'; glow.setAttribute('aria-hidden', 'true'); document.body.append(glow);
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener?.('change', syncMedia);
  const rail = document.createElement('nav');
  rail.className = 'rail';
  rail.setAttribute('aria-label', 'Chapters');
  rail.innerHTML = states.map((s, i) => `<button data-i="${i}" class="${s.ch.appendix ? 'appendix' : ''}" aria-label="${s.ch.title}"><span class="lbl">${s.ch.numeral ? s.ch.numeral + ' · ' : ''}${s.ch.title}</span><span class="dot"></span></button>`).join('');
  rail.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest('button'); if (b) go(Number(b.dataset.i)); });
  document.body.append(rail);

  const nav = document.createElement('div');
  nav.className = 'navbtns';
  nav.innerHTML = `<button class="nav-arrow" data-d="-1" aria-label="Previous"><svg viewBox="0 0 16 16" width="16" height="16"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1"/></svg></button><button class="nav-arrow" data-d="1" aria-label="Next"><svg viewBox="0 0 16 16" width="16" height="16"><path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1"/></svg></button>`;
  nav.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest('button'); if (b) (b.dataset.d === '1' ? next() : prev()); });
  document.body.append(nav);

  const ctr = document.createElement('div'); ctr.className = 'counter'; ctr.setAttribute('data-ok', ''); document.body.append(ctr);
  const st = document.createElement('div'); st.className = 'status'; st.setAttribute('data-ok', ''); document.body.append(st);
  onStatus(() => {
    st.dataset.mode = status.mode;
    const when = status.capturedAt ? new Date(status.capturedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
    st.innerHTML = `<i></i>${{ connecting: 'connecting', live: 'Live API', snapshot: `Snapshot · ${when}`, mixed: `Live + snapshot`, none: 'No data' }[status.mode]}`;
    st.title = `live responses ${status.live}, snapshot ${status.cached}, missing ${status.missing}`;
  });
  const tm = document.createElement('div'); tm.className = 'timer'; tm.setAttribute('data-ok', ''); document.body.append(tm);
  const help = document.createElement('div'); help.className = 'help'; help.setAttribute('data-ok', '');
  help.innerHTML = `<div class="help-card"><div class="label">Presenter keys</div><h3>Keyboard</h3><table>
    <tr><td><kbd>→</kbd> <kbd>Space</kbd> <kbd>PgDn</kbd></td><td>next reveal / next chapter</td></tr>
    <tr><td><kbd>←</kbd> <kbd>Shift+Space</kbd> <kbd>PgUp</kbd></td><td>previous</td></tr>
    <tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>jump to chapter</td></tr>
    <tr><td><kbd>T</kbd> / <kbd>Shift+T</kbd></td><td>start-pause / reset timer</td></tr>
    <tr><td><kbd>S</kbd></td><td>speaker notes window (synced)</td></tr>
    <tr><td><kbd>A</kbd></td><td>show / hide appendix</td></tr>
    <tr><td><kbd>F</kbd></td><td>fullscreen</td></tr>
    <tr><td><kbd>?</kbd></td><td>this help</td></tr></table>
    <p class="micro">After clicking inside the embedded app, click the slide margin to get the keys back.</p></div>`;
  help.addEventListener('click', () => help.classList.remove('on'));
  document.body.append(help);
  const t = document.createElement('div'); t.className = 'toast'; t.setAttribute('data-ok', ''); document.body.append(t);
}
let toastT = 0;
function toast(msg: string) {
  const t = document.querySelector<HTMLElement>('.toast')!;
  t.textContent = msg; t.classList.add('on');
  clearTimeout(toastT); toastT = window.setTimeout(() => t.classList.remove('on'), 1400);
}
function paintRail() {
  document.querySelectorAll<HTMLElement>('.rail button').forEach((b, i) => {
    b.classList.toggle('cur', i === cur);
    b.style.display = states[i].ch.appendix && !appendix ? 'none' : '';
  });
  const v = visible(); const k = Math.max(0, v.indexOf(cur));
  const c = document.querySelector<HTMLElement>('.counter');
  const pad = (n: number) => String(n).padStart(2, '0');
  if (c) c.innerHTML = `<b>${pad(k + 1)}</b> / ${pad(v.length)}`;
  const s = states[cur];
  document.body.dataset.chapter = s?.ch.id ?? '';
}
function paintTimer() {
  const el = document.querySelector<HTMLElement>('.timer');
  if (!el) return;
  const s = states[cur];
  const total = TALK_BUDGET();
  const ch = timer.per[s.ch.id] ?? 0;
  const overT = timer.elapsed > total, overC = s.ch.budget > 0 && ch > s.ch.budget;
  el.innerHTML = `<span class="t-state">${timer.running ? 'Running' : 'Paused'}</span>
    <span class="t-big ${overT ? 'over' : ''}">${mmss(timer.elapsed)}<small> / ${mmss(total)}</small></span>
    <span class="bar"><b style="width:${Math.min(100, (timer.elapsed / total) * 100)}%"></b></span>
    <span class="t-ch ${overC ? 'over' : ''}">${s.ch.numeral ? s.ch.numeral + ' · ' : ''}${s.ch.title} <b>${mmss(ch)}</b> / ${s.ch.budget ? mmss(s.ch.budget) : 'appendix'}</span>`;
}

let lastSent = '';
function broadcast(force = false) {
  if (!chan || !states.length) return;
  const s = states[cur];
  const v = visible(); const k = v.indexOf(cur);
  const nxt = k >= 0 && k < v.length - 1 ? states[v[k + 1]].ch.title : '— end —';
  let budgetStart = 0;
  for (const i of v) { if (i === cur) break; budgetStart += states[i].ch.budget; }
  const msg = {
    type: 'state', idx: cur, id: s.ch.id, title: s.ch.title, step: s.step, steps: s.ch.steps ?? 0, next: nxt, appendix: !!s.ch.appendix,
    notes: s.ch.notes(), chapters: states.map((x, i) => ({ i, title: x.ch.title, budget: x.ch.budget, appendix: !!x.ch.appendix })),
    timer: { running: timer.running, elapsed: timer.elapsed, total: TALK_BUDGET(), ch: timer.per[s.ch.id] ?? 0, budget: s.ch.budget, budgetStart },
    data: status.mode,
  };
  const j = JSON.stringify(msg);
  if (force || j !== lastSent) { chan.postMessage(msg); lastSent = j; }
}
