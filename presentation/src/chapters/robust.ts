import type { Chapter } from '../deck';
import { plan, ranked, sname, shortName } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, said, esc, fmt, eyebrow } from '../lib';
import { citeTag } from '../citations';

const R = `api:POST /robustness ${PROFILE.robustness}`;
const C = `api:POST /compare ${PROFILE.robustness}`;

function iconArray(p: Record<string, number>) {
  const entries = Object.entries(p).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  // largest-remainder rounding to exactly 100 icons
  const raw = entries.map(([id, v]) => ({ id, x: v * 100 }));
  const fl = raw.map((r) => ({ ...r, n: Math.floor(r.x) }));
  let left = 100 - fl.reduce((s, r) => s + r.n, 0);
  [...fl].sort((a, b) => (b.x - b.n) - (a.x - a.n)).forEach((r) => { if (left > 0) { r.n++; left--; } });
  const shades = ['ia-0', 'ia-1', 'ia-2', 'ia-3'];
  const cells: string[] = [];
  fl.forEach((r, k) => { for (let i = 0; i < r.n; i++) cells.push(shades[Math.min(k, 3)]); });
  return {
    grid: html`<div class="ia">${cells.map((c, i) => html`<span class="${c}" style="--d:${(i % 10) * 22 + Math.floor(i / 10) * 22}ms"></span>`)}</div>`,
    legend: fl.slice(0, 3).map((r, k) => ({ id: r.id, n: r.n, cls: shades[Math.min(k, 3)] })),
  };
}

function numberLine(be: any, used: number, a: string, b: string) {
  const v = be.value as number;
  const maxV = Math.max(20, Math.ceil((Math.max(v, used * 2) * 1.35) / 5) * 5);
  const W = 900, x = (t: number) => (t / maxV) * W;
  const ticks = Array.from({ length: maxV / 5 + 1 }, (_, i) => i * 5);
  const lo = used / 2, hi = used * 2;
  return html`
  <svg class="nl" viewBox="-30 -130 ${W + 60} 300" role="img" aria-label="Value-of-time breakeven">
    <rect x="${x(lo)}" y="-12" width="${x(hi) - x(lo)}" height="24" class="nl-range"/>
    <line x1="0" x2="${x(v)}" y1="0" y2="0" class="nl-a"/>
    <line x1="${x(v)}" x2="${W}" y1="0" y2="0" class="nl-b"/>
    ${ticks.map((t) => html`<line x1="${x(t)}" x2="${x(t)}" y1="18" y2="28" class="nl-tick"/><text x="${x(t)}" y="56" class="nl-tl" data-src="derived:axis">$${t}</text>`)}
    <text x="${x(v / 2)}" y="-42" class="nl-lab" data-src="api:GET /listings name">${esc(shortName(a))} wins</text>
    <text x="${x(v + (maxV - v) / 2)}" y="-42" class="nl-lab nl-lab-b" data-src="api:GET /listings name">${esc(shortName(b))} wins</text>
    <g class="nl-be"><line x1="${x(v)}" x2="${x(v)}" y1="-28" y2="32" /><text x="${x(v)}" y="98" data-src="${C}">breakeven ${fmt(v, 'usdh')}</text></g>
    <g class="nl-you"><circle cx="${x(used)}" cy="0" r="11"/><text x="${x(used)}" y="-86" data-src="api:POST /evaluate value_of_time_used">you · ${fmt(used, 'usdh')}</text></g>
    <text x="${x((lo + hi) / 2)}" y="146" class="nl-rl" text-anchor="middle" data-src="engine:range 0.5v..2v">MONTE CARLO RANGE ${fmt(lo, 'usd')}–${fmt(hi, 'usd')}/H</text>
  </svg>`;
}

export const robust: Chapter = {
  id: 'robust',
  title: 'How sure are we',
  numeral: 'V',
  gist: 'A frequency, a breakeven, a driver',
  budget: 28,
  steps: 2,
  deps: ['robustness', 'compare', `eval:${PROFILE.robustness}`, 'listings'],
  render() {
    const r = plan.robustness, c = plan.compare;
    const ev = plan[`eval:${PROFILE.robustness}`];
    const top = ranked(ev);
    let left = html`<div class="pending"><b>Monte Carlo loading</b>POST /api/robustness</div>`;
    if (r?.p_rank1) {
      const ia = iconArray(r.p_rank1);
      left = html`
        <div class="ia-wrap">${ia.grid}
          <div class="ia-legend">
            ${ia.legend.map((l) => html`<div class="ia-li"><span class="sw ${l.cls}"></span><div><div class="ia-n">${num(l.n, R)}<span class="ia-of"> in </span>${num(100, 'derived:icon-array size')}</div><div class="ia-name">${sname(l.id)}</div></div></div>`)}
          </div>
        </div>
        <p class="ia-foot">Each mark is ${num(fmt(r.samples / 100, 'int'), R)} of ${num(fmt(r.samples, 'int'), R)} joint draws of the inputs you said you’re unsure of — value of time, utility prices, walking weights, January weather, next semester’s schedule. Monte Carlo standard error ≤ ${num((r.mc_standard_error * 100).toFixed(1) + ' points', R)}.</p>`;
    }
    const vbe = c?.breakevens?.find((b: any) => b.parameter === 'value_of_time' && b.value != null);
    const other = (c?.breakevens ?? []).filter((b: any) => b.parameter !== 'value_of_time');
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'How sure are we', html`${citeTag('gigerenzer')}<button class="btn to-math">Under the hood · Sobol · τ(t) · CVaR · EVPI →</button>`)}
      <h2 class="enter" style="--i:1">Not “${top[0] ? sname(top[0].listing_id) : 'this home'} is best.” <em>How often — and what would flip it.</em></h2>
      <div class="rb-grid grow">
        <div class="rb-left enter" style="--i:2">
          <div class="label">Out of every hundred plausible semesters, the #1 home is</div>
          ${left}
        </div>
        <div class="rb-right">
          <div class="rb-be enter" style="--i:3" data-step="1">
            <div class="label">Closed-form breakeven${top[0] && top[1] ? html` · ${sname(top[0].listing_id)} vs ${sname(top[1].listing_id)}` : ''}</div>
            ${vbe && ev ? numberLine(vbe, ev.value_of_time_used, vbe.a, vbe.b) : html`<div class="pending">Breakevens loading…</div>`}
            ${other.filter((b: any) => b.parameter === 'rent_b').slice(0, 1).map((b: any) => html`<p class="be-alt">${said(b.direction, C)}</p>`)}
          </div>
          <div class="drivers enter" style="--i:4" data-step="2">
            <div class="label">What moves it most · one input at a time</div>
            ${(r?.drivers ?? []).filter((d: string) => /alone changes/.test(d)).slice(0, 1).map((d: string) => html`<p class="drv">${said(d, R)}</p>`)}
          </div>
        </div>
      </div>`;
  },
  mount(el) {
    el.querySelector('.to-math')?.addEventListener('click', (e) => { e.stopPropagation(); el.dispatchEvent(new CustomEvent('deck:goto', { bubbles: true, detail: 'math' })); });
  },
  notes() {
    const r = plan.robustness;
    return `<p><b>V · How sure are we (28 s).</b> Frequency format, not a percentage (Gigerenzer & Hoffrage). Read the big legend line: "In ${r ? Math.round(Object.values(r.p_rank1 as Record<string, number>).sort((a, b) => b - a)[0] * 100) : '…'} of 100 plausible semesters, this stays #1."</p>
      <p>Reveal (→) the breakeven: "the tower wins only if your time is worth more than the marked value — that's exactly the flip we just did live."</p>
      <p>Reveal (→) drivers. The pill top-right (or End / press A) jumps to the math appendix for Q&A. Q&A: "Is this a probability you'll be happy? No — a stability measure over the ranges you declared."</p>`;
  },
};
