import katex from 'katex';
import type { Chapter } from '../deck';
import { plan } from '../api';
import { html, num, esc, said, fmt, eyebrow, icon, ROMAN } from '../lib';
import { citeTag } from '../citations';

const M = 'api:GET /manifest';
export const tex = (latex: string, display = true) => {
  try { return katex.renderToString(latex, { displayMode: display, throwOnError: false, strict: 'ignore', output: 'html' }); }
  catch { return `<code>${esc(latex)}</code>`; }
};
export const eqOf = (id: string) => plan.methods?.equations?.find((e: any) => e.id === id);

const EXAMPLE = '“MWF 9-10:30 EECS, UgLi Sun-Thu till 1am, work Kerrytown Sat 10-4”';
type Step = { key: string; name: string; sub: string; eqs: string[]; body: () => string; cite?: string };

const STEPS: Step[] = [
  { key: 'week', name: 'Your week', sub: 'routine → events', eqs: [],
    body: () => html`<p>Type your routine in plain English. The AI only proposes events; code checks every building against the campus list and every quote against your text, and you confirm the grid.
      <b>The AI never ranks, prices or invents a number.</b> Switch it off and everything still works.</p>
      <p class="small">Unsure about next semester? Pick a program template and the engine samples plausible semesters around your fixed commitments.</p>` },
  { key: 'csa', name: 'Real timetables', sub: 'Connection Scan', eqs: ['csa_backward'], cite: 'csa',
    body: () => {
      const p = plan.manifest?.provider;
      const wk = p?.daytypes?.[0];
      return html`<p>One backward scan per building and deadline gives the latest time you can leave <i>every</i> stop — so a single pass serves every listing at once.</p>
      <div class="stats hw-stats">
        ${wk ? html`<div><span class="fig">${num(fmt(wk.connections, 'int'), M)}</span><span class="cap">weekday bus connections</span></div>` : ''}
        ${p?.network ? html`<div><span class="fig">${num(fmt(p.network.stops, 'int'), M)}</span><span class="cap">stops, UM + TheRide</span></div>` : ''}
        ${p?.labels ? html`<div><span class="fig">${num(fmt(p.labels.scans, 'int'), M)}</span><span class="cap">precomputed scans</span></div>` : ''}
        ${p?.labels ? html`<div><span class="fig">${num(p.labels.ms_per_scan.toFixed(2) + ' ms', M)}</span><span class="cap">per scan</span></div>` : ''}
      </div>
      ${p?.feeds ? html`<p class="micro feeds">${Object.values(p.feeds).map((f: any) => said(f.label, M)).join(' · ')}</p>` : ''}`;
    } },
  { key: 'tours', name: 'Day tours', sub: 'chain, don’t commute', eqs: ['day_tour'], cite: 'kobus',
    body: () => html`<p>Events of a day are chained: home → first event → … → home. You only go home in a gap when that is actually cheaper — the model never charges a trip you wouldn’t make.</p>` },
  { key: 'cost', name: 'Generalized cost', sub: 'minutes that feel real', eqs: ['generalized_trip_cost', 'weather_factor'], cite: 'wardman',
    body: () => html`<p>Riding, walking, waiting, transfers and timetable-forced early arrival are weighted separately, and outdoor minutes weigh more on snowy days (NOAA normals).</p>` },
  { key: 'receipt', name: 'Monthly receipt', sub: 'one dollar total', eqs: ['monthly_ledger', 'value_of_time'], cite: 'usdot',
    body: () => html`<p>Hours become dollars at <i>your</i> value of time, next to rent, monthly-ized fees, a seasonal utility band and insurance. The ranking is that one total — no arbitrary weights, no normalization.</p>` },
];

function detail(i: number) {
  if (i < 0) {
    return html`<div class="hw-intro"><span class="label">Five steps · press → to walk them</span><p class="hw-lede">Every equation on this page is served by the API’s methods endpoint — the same code path that computes the ranking.</p></div>`;
  }
  const s = STEPS[i];
  const eqs = s.eqs.map(eqOf).filter(Boolean);
  return html`
    <div class="hw-detail">
      <div class="hw-text">
        <div class="hw-h"><span class="hw-n">${ROMAN[i]}</span><h3>${esc(s.name)}</h3></div>
        ${s.body()}
      </div>
      <div class="hw-eqs">
        ${s.cite ? html`<div class="hw-cite">${citeTag(s.cite)}</div>` : ''}
        ${eqs.length ? eqs.map((e: any) => html`<div class="eqbox"><div class="label">${esc(e.title)}</div><div class="eq">${tex(e.latex)}</div><div class="small">${said(String(e.meaning ?? '').split(/(?<=\.)\s/)[0], 'api:GET /methods')}</div></div>`)
          : s.eqs.length ? html`<div class="pending"><b>Equations loading</b>from GET /api/methods</div>` : html`<div class="hw-quote"><span class="qmark">“</span>${said(EXAMPLE.replace(/^“|”$/g, ''), 'example: typed user input')}<div class="micro">→ validated events, each with its source quote</div></div>`}
      </div>
    </div>`;
}

export const how: Chapter = {
  id: 'how',
  title: 'How it works',
  numeral: 'III',
  gist: 'From your week to one honest number',
  budget: 35,
  steps: STEPS.length,
  deps: ['methods', 'manifest'],
  render() {
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'How it works')}
      <h2 class="enter" style="--i:1">From your week to <em>one honest number.</em></h2>
      <div class="pipe timeline enter" style="--i:2">
        ${STEPS.map((s, i) => html`
          <button class="node" data-node="${i}">${icon(ROMAN[i])}<span class="nd-n">${esc(s.name)}</span><span class="nd-s">${esc(s.sub)}</span></button>`)}
      </div>
      <div class="card hw-panel grow enter" style="--i:3"></div>`;
  },
  mount(el) {
    el.querySelectorAll<HTMLElement>('.node').forEach((n) => n.addEventListener('click', () => {
      const target = Number(n.dataset.node) + 1;
      el.dispatchEvent(new CustomEvent('deck:setstep', { bubbles: true, detail: target }));
    }));
  },
  step(el, n) {
    el.querySelectorAll<HTMLElement>('.node').forEach((node, i) => {
      node.classList.toggle('on', i === n - 1);
      node.classList.toggle('done', i < n - 1);
      node.querySelector('.card-icon')?.classList.toggle('on', i === n - 1);
    });
    const pipe = el.querySelector<HTMLElement>('.pipe');
    if (pipe) pipe.style.setProperty('--prog', n ? String(n / STEPS.length) : '0');
    const panel = el.querySelector<HTMLElement>('.hw-panel');
    if (panel) panel.innerHTML = detail(n - 1);
  },
  notes() {
    return `<p><b>III · How it works (35 s) — the technical credibility beat.</b> Walk the five nodes with →.</p>
      <p>Rehearsed line: "For every campus building and every 5-minute arrival deadline we scan the day's real bus connections backwards once. That gives the latest time you can leave any stop. Add the walk from each apartment and we have door-to-door minutes for every listing at once."</p>
      <p>Day tours: home only when the gap is worth it. Generalized cost: walking/waiting 1.75×, snow days heavier, forced early arrival 0.5×. Receipt: hours × your value of time next to rent — one dollar total.</p>
      <p>Q&A backup: CSA vs RAPTOR; property tests vs time-expanded Dijkstra.</p>`;
  },
};
