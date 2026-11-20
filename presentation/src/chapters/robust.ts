// V · How sure are we: one frequency (n in 100) over a 100-mark array; step → the value-of-time breakeven.
import type { Chapter } from '../deck';
import { plan, ranked, sname, shortName } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, esc, fmt } from '../lib';
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

function numberLine(v: number, used: number, a: string, b: string) {
  const maxV = Math.max(20, Math.ceil((Math.max(v, used * 2) * 1.3) / 5) * 5);
  const W = 1300, x = (t: number) => (t / maxV) * W;
  const ticks = Array.from({ length: maxV / 5 + 1 }, (_, i) => i * 5);
  return html`
  <svg class="nl" viewBox="-40 -120 ${W + 80} 200" role="img" aria-label="Value-of-time breakeven">
    <line x1="0" x2="${x(v)}" y1="0" y2="0" class="nl-a"/>
    <line x1="${x(v)}" x2="${W}" y1="0" y2="0" class="nl-b"/>
    ${ticks.map((t) => html`<line x1="${x(t)}" x2="${x(t)}" y1="14" y2="26" class="nl-tick"/><text x="${x(t)}" y="62" class="nl-tl" data-src="derived:axis">$${t}</text>`)}
    <text x="${x(v / 2)}" y="-38" class="nl-lab" data-src="api:GET /listings name">${esc(shortName(a))}</text>
    <text x="${x(v + (maxV - v) / 2)}" y="-38" class="nl-lab nl-lab-b" data-src="api:GET /listings name">${esc(shortName(b))}</text>
    <g class="nl-be"><line x1="${x(v)}" x2="${x(v)}" y1="-26" y2="30" /></g>
    <g class="nl-you"><circle cx="${x(used)}" cy="0" r="13"/><text x="${x(used)}" y="-80" data-src="api:POST /evaluate value_of_time_used">you · ${fmt(used, 'usd')}/h</text></g>
  </svg>`;
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
    let left = html`<div class="pending"><b>Monte Carlo loading</b>POST /api/robustness</div>`, hero = '';
    if (r?.p_rank1) {
      const ia = iconArray(r.p_rank1);
      left = ia.grid;
      const w = ia.fl[0];
      hero = html`<div class="hero">${num(w.n, R)}<span class="rb-of"> in ${num(100, 'derived:icon-array size')}</span></div>
        <div class="hero-cap">plausible semesters keep <b>${sname(w.id)}</b> at #1</div>`;
    }
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">How sure is <em>the answer?</em></h2>
      <div class="rb-grid grow">
        <div class="rb-ia enter" style="--i:2">${left}</div>
        <div class="rb-main enter" style="--i:3">${hero}<div class="chips rb-chips">${citeTag('gigerenzer')}</div></div>
      </div>
      <div class="rb-be hide-until" data-step="1">
        ${vbe && ev && top[1] ? html`
          <div class="rb-be-head"><span class="hero sm">${num(fmt(vbe.value, 'usd2'), C)}<span class="rb-of">/h</span></span><span class="hero-cap">value your time above this and <b>${sname(vbe.b ?? top[1].listing_id)}</b> wins</span></div>
          ${numberLine(vbe.value, ev.value_of_time_used, vbe.a ?? top[0].listing_id, vbe.b ?? top[1].listing_id)}` : html`<div class="pending">Breakevens loading…</div>`}
      </div>`;
  },
  step(el, n) { el.querySelector('.rb-grid')?.classList.toggle('dim', n >= 1); },
  notes() {
    const r = plan.robustness;
    const drv = (r?.drivers ?? []).find((d: string) => /alone changes/.test(d));
    return `<p><b>V · How sure are we (28 s).</b> Frequency format, not a percentage (Gigerenzer & Hoffrage 1995). "In ${r ? Math.round(Object.values(r.p_rank1 as Record<string, number>).sort((a, b) => b - a)[0] * 100) : '…'} of 100 plausible semesters, this stays #1." Each mark is ${r ? Math.round(r.samples / 100) : '…'} of ${r?.samples ?? '…'} joint draws of the inputs you're unsure of — value of time, utility prices, walking weights, January weather, next semester's schedule. MC standard error ≤ ${r ? (r.mc_standard_error * 100).toFixed(1) : '…'} points.</p>
      <p>Reveal (→) the breakeven: "the tower wins only if your time is worth more than this — exactly the flip we just did live."</p>
      ${drv ? `<p>Driver, if asked: ${esc(drv)}</p>` : ''}
      <p>Press A (or End) for the math appendix in Q&A. "Is this a probability you'll be happy? No — a stability measure over the ranges you declared."</p>`;
  },
};
