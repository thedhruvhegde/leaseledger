import type { Chapter } from '../deck';
import { plan, ranked, profile } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, esc, DAY_NAME, minToClock, eyebrow } from '../lib';
import { CITES, citeTag } from '../citations';
import { interviews } from '../facts';

const SRC = `api:GET /demo-profiles ${PROFILE.hook}`;
const DAYS = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
const T0 = 360, T1 = 1560; // 06:00 .. 02:00 next day

export const nTrips = (e: any): number | null =>
  e?.commute?.tours ? e.commute.tours.reduce((n: number, t: any) => n + (t.trips?.length ?? 0), 0) : e?.commute?.n_trips ?? null;

function weekStrip(events: any[]) {
  const W = 760, rowH = 50;
  const x = (m: number) => ((m - T0) / (T1 - T0)) * W;
  const ticks = [480, 720, 960, 1200, 1440];
  return html`
  <svg class="week" viewBox="-74 -40 ${W + 94} ${DAYS.length * rowH + 44}" role="img" aria-label="Weekly routine">
    ${ticks.map((t) => html`<line x1="${x(t)}" x2="${x(t)}" y1="-8" y2="${DAYS.length * rowH}" class="wk-grid"/><text x="${x(t)}" y="-16" class="wk-tick" data-src="derived:axis">${minToClock(t)}</text>`)}
    ${DAYS.map((d, i) => html`
      <text x="-16" y="${i * rowH + 29}" class="wk-day">${DAY_NAME[d]}</text>
      <line x1="0" x2="${W}" y1="${i * rowH + 22}" y2="${i * rowH + 22}" class="wk-base"/>
      ${events.filter((e) => e.days.includes(d)).map((e, k) => html`<rect class="wk-ev" style="--k:${i * 3 + k}" x="${x(e.start_min)}" y="${i * rowH + 11}" width="${Math.max(6, x(e.end_min) - x(e.start_min))}" height="22"><title>${esc(e.label)}</title></rect>`)}
    `)}
  </svg>`;
}

function interviewBlock() {
  if (!interviews) {
    return html`<div class="iv-pending enter" style="--i:7"><span class="label">Student interviews</span><span class="iv-t">In progress. Tallies appear here only once real intercepts are logged — we do not show invented counts.</span></div>`;
  }
  const n = interviews.completed ?? interviews.n ?? interviews.count ?? (Array.isArray(interviews.rows) ? interviews.rows.length : null);
  const rows: any[] = interviews.tally ?? interviews.hypotheses ?? interviews.codes ?? [];
  return html`<div class="iv-pending enter" style="--i:7">
    <span class="label">Interviews logged</span>
    <div class="stats" style="border:0;padding:0">${html`<div><span class="fig">${n != null ? num(n, 'facts:interviews.json') : '—'}</span><span class="cap">students</span></div>`}
    ${rows.slice(0, 3).map((r: any) => html`<div><span class="fig">${num(String(r.count ?? r.n ?? r.value ?? r.n_discussed ?? ''), 'facts:interviews.json')}</span><span class="cap">${esc(r.label ?? r.name ?? r.id ?? '')}</span></div>`)}</div>
    ${interviews.note ? html`<div class="small">${esc(interviews.note)}</div>` : ''}
  </div>`;
}

export const problem: Chapter = {
  id: 'problem',
  title: 'Why it’s hard',
  numeral: 'II',
  gist: 'A listing prices one trip; you live a week',
  budget: 25,
  steps: 2,
  deps: ['demoProfiles', `eval:${PROFILE.hook}`],
  render() {
    const p = profile(PROFILE.hook)?.profile;
    const top = ranked(plan[`eval:${PROFILE.hook}`])[0];
    const trips = nTrips(top);
    const events = p?.events ?? [];
    const occ = events.reduce((s: number, e: any) => s + e.days.length, 0);
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'Why it’s hard')}
      <h2 class="enter" style="--i:1">A listing prices one trip. <em>You live a whole week.</em></h2>
      <div class="pb-top grow">
        <div class="pb-left">
          <figure class="pb-week enter" style="--i:2">
            <figcaption class="pb-cap"><span class="label">Plate I · one student’s week</span><span class="micro">North Campus engineer</span></figcaption>
            ${p ? weekStrip(events) : html`<div class="pending">Loading the routine…</div>`}
          </figure>
          <div class="stats pb-stats" data-step="1">
            <div><span class="fig">${num(occ, SRC)}</span><span class="cap">events in one week</span></div>
            <div><span class="fig">${trips != null ? num(trips, `api:POST /evaluate ${PROFILE.hook}`) : '—'}</span><span class="cap">door-to-door trips, each routed at its own time of day</span></div>
          </div>
          ${interviewBlock()}
        </div>
        <div class="pb-right">
          <span class="qmark enter" style="--i:3">“</span>
          ${['stutzer', 'burzacchi', 'kobus'].map((id, i) => html`<div class="cite-row enter" style="--i:${4 + i}"><p>${esc(CITES[id].finding)}</p>${citeTag(id)}</div>`)}
          <div class="pb-local" data-step="2">
            <div class="label">And in Ann Arbor</div>
            <div class="pb-local-in">${['fees', 'winter'].map((id) => html`<div class="cite-row"><p>${esc(CITES[id].finding)}</p>${citeTag(id)}</div>`)}</div>
          </div>
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>II · Why it's hard (25 s).</b> One sentence on the week grid: classes on North, Central, a project team at night. Reveal (→): the number of trips we route per week.</p>
      <p>Evidence: commuting paradox (Stutzer & Frey), commute lowers first-year GPA (Burzacchi 2024), students chain trips (Kobus 2015) — that's why day tours. Reveal (→): Ann Arbor's best-documented renter complaints are hidden fees and winter heating.</p>
      <p>Interviews: say exactly what the slide says. If none are logged, say "interviews in progress"; never estimate.</p>`;
  },
};
