// Small helpers: tagged html templates, number formatting and data-bound number spans.
//
// RULE: slide copy (text inside html`...`) must not contain digits. Every number reaches the page
// through `${...}` interpolation of API/facts data, wrapped by `num()` so it carries data-src.
// scripts/check-copy.mjs enforces the rule statically; scripts/screenshots.mjs re-checks the DOM.

export const html = (s: TemplateStringsArray, ...v: unknown[]): string =>
  s.reduce((acc, str, i) => acc + str + (i < v.length ? toStr(v[i]) : ''), '');
const toStr = (x: unknown): string => (x == null || x === false ? '' : Array.isArray(x) ? x.join('') : String(x));

export const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

export type Src = string; // e.g. "api:/evaluate north-engineer", "facts:test_count", "param:FLIPS.vot"

/** A data-bound number (or any text containing numbers) with provenance attached. */
export const num = (text: string | number, src: Src, cls = ''): string =>
  `<span class="num ${cls}" data-src="${esc(src)}">${esc(text)}</span>`;

/** API-sourced sentence (may contain numbers): escaped, tagged with its source. */
export const said = (text: string, src: Src, cls = ''): string =>
  `<span class="said ${cls}" data-src="${esc(src)}">${esc(text)}</span>`;

/** Count-up number; final text is reserved in a ghost so the animation causes no layout shift. */
export const countUp = (value: number, fmt: Fmt, src: Src, cls = ''): string => {
  const final = FMT[fmt](value);
  return `<span class="num count ${cls}" data-src="${esc(src)}" data-count="${value}" data-fmt="${fmt}"><span class="ghost" aria-hidden="true">${esc(final)}</span><span class="live">${esc(final)}</span></span>`;
};

export type Fmt = 'usd' | 'usd2' | 'int' | 'pct' | 'pct1' | 'hours' | 'usdh' | 'mult';
export const FMT: Record<Fmt, (n: number) => string> = {
  usd: (n) => (n < 0 ? '−' : '') + '$' + Math.round(Math.abs(n)).toLocaleString('en-US'),
  usd2: (n) => (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  int: (n) => Math.round(n).toLocaleString('en-US'),
  pct: (n) => Math.round(n * 100) + '%',
  pct1: (n) => (n * 100).toFixed(1) + '%',
  hours: (n) => n.toFixed(1) + ' h',
  usdh: (n) => '$' + n.toFixed(2) + '/h',
  mult: (n) => n.toFixed(2) + '×',
};
export const fmt = (n: number, f: Fmt) => FMT[f](n);

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
export function runCountUps(root: ParentNode, ms = 1400) {
  root.querySelectorAll<HTMLElement>('.count[data-count]').forEach((el) => {
    const target = Number(el.dataset.count);
    const f = el.dataset.fmt as Fmt;
    const live = el.querySelector<HTMLElement>('.live');
    if (!live || !Number.isFinite(target)) return;
    if (reducedMotion()) { live.textContent = FMT[f](target); return; }
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / ms);
      live.textContent = FMT[f](target * easeOut(t));
      if (t < 1) requestAnimationFrame(tick);
    };
    live.textContent = FMT[f](0);
    requestAnimationFrame(tick);
  });
}

export const minToClock = (m: number) => {
  const mm = ((Math.round(m) % 1440) + 1440) % 1440;
  const h = Math.floor(mm / 60), r = mm % 60;
  const h12 = ((h + 11) % 12) + 1;
  return `${h12}${r ? ':' + String(r).padStart(2, '0') : ''}${h < 12 ? 'am' : 'pm'}`;
};

export const DAY_NAME: Record<string, string> = { M: 'Mon', T: 'Tue', W: 'Wed', R: 'Thu', F: 'Fri', S: 'Sat', U: 'Sun' };

// ---------- deck helpers ----------
export const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];
/** 44px circle with a short mark (flip buttons, step nodes). */
export const icon = (mark: string, cls = ''): string => `<span class="card-icon ${cls}">${esc(mark)}</span>`;
/** The one small honesty tag a slide may carry, e.g. "simulated · travel-only". Legible (22px), never decorative. */
export const tag = (text: string, cls = ''): string => `<span class="tag ${cls}">${esc(text)}</span>`;
