// II · A listing prices one trip; you live a week. One picture (the week), one number (trips routed), author-year chips.
import type { Chapter } from '../deck';
import { plan, ranked, profile } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, esc, DAY_NAME, minToClock } from '../lib';
import { citeTag } from '../citations';

const DAYS = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
const T0 = 420, T1 = 1500; // 07:00 .. 01:00

export const nTrips = (e: any): number | null =>
  e?.commute?.tours ? e.commute.tours.reduce((n: number, t: any) => n + (t.trips?.length ?? 0), 0) : e?.commute?.n_trips ?? null;

function weekStrip(events: any[]) {
  const W = 1000, rowH = 58;
  const x = (m: number) => ((m - T0) / (T1 - T0)) * W;
  const ticks = [480, 720, 960, 1200, 1440];
  return html`
  <svg class="week" viewBox="-70 -46 ${W + 84} ${DAYS.length * rowH + 50}" role="img" aria-label="Weekly routine">
    ${ticks.map((t) => html`<line x1="${x(t)}" x2="${x(t)}" y1="-8" y2="${DAYS.length * rowH}" class="wk-grid"/><text x="${x(t)}" y="-20" class="wk-tick" data-src="derived:axis">${minToClock(t)}</text>`)}
    ${DAYS.map((d, i) => html`
      <text x="-16" y="${i * rowH + 33}" class="wk-day">${DAY_NAME[d]}</text>
      <line x1="0" x2="${W}" y1="${i * rowH + 26}" y2="${i * rowH + 26}" class="wk-base"/>
      ${events.filter((e) => e.days.includes(d)).map((e, k) => html`<rect class="wk-ev" style="--k:${i * 3 + k}" x="${x(Math.max(T0, e.start_min))}" y="${i * rowH + 12}" width="${Math.max(6, x(Math.min(T1, e.end_min)) - x(Math.max(T0, e.start_min)))}" height="28"><title>${esc(e.label)}</title></rect>`)}
    `)}
  </svg>`;
}

export const problem: Chapter = {
  id: 'problem',
  title: 'A whole week',
  budget: 23,
  deps: ['demoProfiles', `eval:${PROFILE.hook}`],
  render() {
    const p = profile(PROFILE.hook)?.profile;
    const top = ranked(plan[`eval:${PROFILE.hook}`])[0];
    const trips = nTrips(top);
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">A listing prices one trip. <em>You live a week.</em></h2>
      <div class="pb-grid grow">
        <figure class="pb-week enter" style="--i:2">${p ? weekStrip(p.events ?? []) : html`<div class="pending">Loading the routine…</div>`}</figure>
        <div class="pb-num enter" style="--i:3">
          <div class="hero">${trips != null ? num(trips, `api:POST /evaluate ${PROFILE.hook}`) : '—'}</div>
          <div class="hero-cap">trips a week, each routed <b>at its own time of day</b></div>
        </div>
      </div>
      <div class="chips pb-chips enter" style="--i:4">${['stutzer', 'burzacchi', 'kobus'].map(citeTag)}</div>`;
  },
  notes() {
    return `<p><b>II · A whole week (23 s; 13 s when the interviews slide is in).</b> One sentence on the grid: classes on North and Central, a project team at night. Then the number: every one of those trips is routed door-to-door at its own time of day on the real timetable.</p>
      <p>Research (chips at the bottom): long commutes lower life satisfaction and aren't compensated — the "commuting paradox" (Stutzer & Frey 2008); GPS-measured commute time lowers first-year engineering GPA (Burzacchi et al. 2024); students with long commutes chain trips into fewer, longer days (Kobus et al. 2015) — which is why we model day tours.</p>
      <p>Ann Arbor specifics if asked: hidden waitlist/application/admin fees (Michigan Daily; Ann Arbor Tenants Union 2024); winter heating shock in older houses (r/AnnArbor; Michigan Daily 2025).</p>
      <p>Interviews: only mention them if the "What students told us" slide is in the deck (it appears only once real interview data is in presentation/data/interviews.json or presentation/public/interviews/). Never estimate counts.</p>`;
  },
};
