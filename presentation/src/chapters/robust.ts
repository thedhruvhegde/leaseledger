// V · How sure are we: one frequency (n in 100) over a 100-mark array; step → the value-of-time breakeven.
import type { Chapter } from '../deck';
import { plan, ranked, sname } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, esc, fmt, loop } from '../lib';
import { citeTag } from '../citations';

const R = `api:POST /robustness ${PROFILE.robustness}`;
const C = `api:POST /compare ${PROFILE.robustness}`;

function iconArray(p: Record<string, number>) {
  const entries = Object.entries(p).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  // largest-remainder rounding to exactly 100 marks
  const fl = entries.map(([id, v]) => ({ id, x: v * 100, n: Math.floor(v * 100) }));
  let left = 100 - fl.reduce((s, r) => s + r.n, 0);
  [...fl].sort((a, b) => (b.x - b.n) - (a.x - a.n)).forEach((r) => { if (left > 0) { r.n++; left--; } });
  const cells: string[] = [];
  fl.forEach((r, k) => { for (let i = 0; i < r.n; i++) cells.push(k === 0 ? 'ia-0' : 'ia-1'); });
  return { grid: html`<div class="ia">${cells.map((c, i) => html`<span class="${c}" style="--d:${(i % 10) * 22 + Math.floor(i / 10) * 22}ms"></span>`)}</div>`, fl };
}

export const robust: Chapter = {
  id: 'robust',
  title: 'How sure are we',
  budget: 28,
  steps: 1,
  deps: ['robustness', 'compare', `eval:${PROFILE.robustness}`, 'listings'],
  render() {
    const r = plan.robustness, c = plan.compare;
    const ev = plan[`eval:${PROFILE.robustness}`];
    const top = ranked(ev);
    const vbe = c?.breakevens?.find((b: any) => b.parameter === 'value_of_time' && b.value != null);
    let hero = '';
    if (r?.p_rank1) {
      const ia = iconArray(r.p_rank1);
      const w = ia.fl[0];
      hero = html`<div class="hero">${num(w.n, R)}<span class="rb-of"> in ${num(100, 'derived:icon-array size')}</span></div>
        <div class="hero-cap">plausible semesters keep <b>${sname(w.id)}</b> at #1</div>`;
    }
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">How sure is <em>the answer?</em></h2>
      <div class="rb-wrap grow">
        <div class="rb-grid">
          <div class="rb-ia enter" style="--i:2">${loop('how-sure', 'every semester, redrawn')}</div>
          <div class="rb-main enter" style="--i:3">${hero || html`<div class="pending"><b>Monte Carlo loading</b>POST /api/robustness</div>`}<div class="chips rb-chips">${citeTag('gigerenzer')}</div></div>
        </div>
        <div class="rb-be hide-until" data-step="1">
          <div class="rb-ia">${loop('the-flip', 'sliding the value of time')}</div>
          ${vbe && ev && top[1] ? html`
            <div class="rb-main"><div class="hero sm">${num(fmt(vbe.value, 'usd2'), C)}<span class="rb-of">/h</span></div><div class="hero-cap">value your time above this and <b>${sname(vbe.b ?? top[1].listing_id)}</b> wins</div></div>` : html`<div class="pending">Breakevens loading…</div>`}
        </div>
      </div>`;
  },
  step(el, n) { el.querySelector('.rb-grid')?.classList.toggle('dim', n >= 1); },
  notes() {
    const r = plan.robustness;
    const drv = (r?.drivers ?? []).find((d: string) => /alone changes/.test(d));
    return `<p><b>V · How sure are we (28 s).</b> Frequency format, not a percentage (Gigerenzer & Hoffrage 1995). "In ${r ? Math.round(Object.values(r.p_rank1 as Record<string, number>).sort((a, b) => b - a)[0] * 100) : '…'} of 100 plausible semesters, this stays #1." Each mark is ${r ? Math.round(r.samples / 100) : '…'} of ${r?.samples ?? '…'} joint draws of the inputs you're unsure of — value of time, utility prices, walking weights, January weather, next semester's schedule. MC standard error ≤ ${r ? (r.mc_standard_error * 100).toFixed(1) : '…'} points.</p>
      <p>The left plates are explainer loops (media/videos/fast/how-sure.mp4, then the-flip.mp4; 10× speed): the 2,000-draw dot array filling in, then the all-in lines crossing as the value of time slides. Same engine run (seed 42) as the number.</p>
      <p>Reveal (→) the breakeven: "the tower wins only if your time is worth more than this — exactly the flip we just did live."</p>
      ${drv ? `<p>Driver, if asked: ${esc(drv)}</p>` : ''}
      <p>Press A (or End) for the math appendix in Q&A. "Is this a probability you'll be happy? No — a stability measure over the ranges you declared."</p>`;
  },
};
