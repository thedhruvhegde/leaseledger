// III · How it works: five steps, each shown as ONE picture or ONE number (app screenshot, timetable count,
// a real day tour, the cost equation from GET /methods, the app's receipt) plus one short line.
import katex from 'katex';
import type { Chapter } from '../deck';
import { plan } from '../api';
import { html, num, esc, fmt } from '../lib';
import { F } from '../facts';
import { citeTag } from '../citations';
import { base, loadBase, bboxOf, routeLayer, streets } from '../routemap';

const M = 'api:GET /manifest';
export const tex = (latex: string, display = true) => {
  try { return katex.renderToString(latex, { displayMode: display, throwOnError: false, strict: 'ignore', output: 'html' }); }
  catch { return `<code>${esc(latex)}</code>`; }
};
export const eqOf = (id: string) => plan.methods?.equations?.find((e: any) => e.id === id);

const shot = (file: string, alt: string, pos = 'top left') =>
  html`<div class="plate-img hw-shot"><img src="./img/${file}" alt="${esc(alt)}" style="object-position:${pos}" decoding="async"/></div>`;

function dayTour() {
  const ev = plan.routes?.a;
  const b = base;
  if (!ev || !b) return html`<div class="plate-img hw-vis img-ph"></div>`;
  // the weekday of the #1 home with the most bus legs: home → events → home as one chained tour
  const buses = (t: any) => (t.trips ?? []).reduce((n: number, tr: any) => n + (tr.legs ?? []).filter((l: any) => l.kind === 'bus').length, 0);
  const tours = [...(ev.commute?.tours ?? [])].sort((x: any, y: any) => buses(y) - buses(x) || (y.trips?.length ?? 0) - (x.trips?.length ?? 0));
  const one = { commute: { tours: tours.slice(0, 1) } };
  const bb = bboxOf(b, [one]);
  const w = bb.x1 - bb.x0, h = bb.y1 - bb.y0, side = Math.max(w * 0.58, h) * 1.18;
  const W = side / 0.58, cx = (bb.x0 + bb.x1) / 2, cy = (bb.y0 + bb.y1) / 2;
  return html`<div class="plate-img hw-vis"><svg viewBox="${cx - W / 2} ${cy - side / 2} ${W} ${side}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">${streets(b)}${routeLayer(b, one, '', 90)}</svg></div>`;
}

type Step = { name: string; vis: () => string; line: () => string; cite?: string };
const STEPS: Step[] = [
  { name: 'Your week', vis: () => shot('03-your-week.png', 'Typing a week into the app'),
    line: () => html`Type it in plain English. <b>The AI proposes events; code checks them.</b>` },
  { name: 'Real timetables', cite: 'csa',
    vis: () => {
      const wk = plan.manifest?.provider?.daytypes?.[0];
      return html`<div class="hw-num"><div class="hero">${wk ? num(fmt(wk.connections, 'int'), M) : '—'}</div><div class="hero-cap">weekday bus connections, scanned once per building</div></div>`;
    },
    line: () => html`Every trip is door-to-door on <b>this fall’s schedule.</b>` },
  { name: 'Day tours', cite: 'kobus', vis: dayTour,
    line: () => html`Home only when the gap is <b>worth going home.</b>` },
  { name: 'Felt minutes', cite: 'wardman',
    vis: () => html`<div class="hw-num"><div class="hero">${F('param_time_multipliers.walk', { suffix: '×' })}</div><div class="hero-cap">a minute walking or waiting, counted against a minute on the bus</div></div>`,
    line: () => html`Walking, waiting and snow days <b>weigh more.</b>` },
  { name: 'One total', cite: 'usdot', vis: () => shot('05-results-receipt-scrolled.png', 'The receipt in the app', '50% top'),
    line: () => html`Hours × your value of time, next to rent: <b>one dollar total.</b>` },
];

function detail(i: number) {
  const s = STEPS[Math.max(0, i)];
  return html`<div class="hw-detail">
      <div class="hw-left">${s.vis()}</div>
      <div class="hw-right"><p class="hw-line">${s.line()}</p>${s.cite ? html`<div class="chips">${citeTag(s.cite)}</div>` : ''}</div>
    </div>`;
}

export const how: Chapter = {
  id: 'how',
  title: 'How it works',
  budget: 35,
  steps: STEPS.length - 1,
  deps: ['methods', 'manifest', 'routes'],
  render() {
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">From your week to <em>one number.</em></h2>
      <div class="hw-nodes enter" style="--i:2">
        ${STEPS.map((s, i) => html`<button class="hw-node" data-node="${i}"><i class="hw-dot"></i><span>${esc(s.name)}</span></button>`)}
      </div>
      <div class="hw-panel grow enter" style="--i:3"></div>`;
  },
  mount(el) {
    if (!base) loadBase().then((b) => b && el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
    el.querySelectorAll<HTMLElement>('.hw-node').forEach((n) => n.addEventListener('click', (e) => {
      e.stopPropagation();
      el.dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: Number(n.dataset.node) }));
    }));
  },
  step(el, n) {
    el.querySelectorAll<HTMLElement>('.hw-node').forEach((node, i) => {
      node.classList.toggle('on', i === n);
      node.classList.toggle('done', i < n);
      
    });
    const panel = el.querySelector<HTMLElement>('.hw-panel');
    if (panel) { panel.innerHTML = detail(n); panel.classList.remove('swap'); void panel.offsetWidth; panel.classList.add('swap'); }
  },
  notes() {
    return `<p><b>III · How it works (35 s) — the technical credibility beat.</b> → walks the five steps.</p>
      <p>1 · Your week: the AI only proposes events; code checks every building against the campus list and every quote against your text, and you confirm the grid. <b>The AI never ranks, prices or invents a number.</b> Switch it off and everything still works. Templates sample plausible semesters if you don't know next term yet.</p>
      <p>2 · Rehearsed line: "For every campus building and every 5-minute arrival deadline we scan the day's real bus connections backwards once (Connection Scan, Dibbelt et al. 2018). That gives the latest time you can leave any stop; add the walk from each apartment and we have door-to-door minutes for every listing at once."</p>
      <p>3 · Day tours (Kobus 2015): the map is one real weekday of the #1 home, chained home → events → home.</p>
      <p>4 · Generalized cost: walking/waiting 1.75×, snow days heavier (NOAA normals), timetable-forced early arrival 0.5× (Small 1982; Wardman 2016).</p>
      <p>5 · Receipt: hours × your value of time (USDOT: half the wage) next to rent, fees, a seasonal utility band and insurance. No arbitrary weights.</p>`;
  },
};
