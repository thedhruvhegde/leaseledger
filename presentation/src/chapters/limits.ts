import type { Chapter } from '../deck';
import { plan } from '../api';
import { html, said, esc, num, fmt, eyebrow, icon } from '../lib';

const SHOW = 10;

export const limits: Chapter = {
  id: 'limits',
  title: 'Limits & next',
  numeral: 'X',
  gist: 'What we don’t know, and where this goes',
  budget: 12,
  steps: 1,
  deps: ['methods', 'manifest'],
  render() {
    const lims: string[] = plan.methods?.limitations ?? [];
    const m = plan.manifest?.provider;
    const short = (s: string) => s.split(/(?<=[a-z)])[;:] /)[0].replace(/\.$/, '');
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'Limits & what’s next')}
      <h2 class="enter" style="--i:1">What we don’t know — <em>and where this goes.</em></h2>
      <div class="lm-grid grow">
        <div class="lm-left enter" style="--i:2">
          <div class="label">Stated limits, served by the API · ${lims.length ? num(lims.length, 'api:GET /methods limitations') : '…'} of them, all shown in the app</div>
          <ol class="lims">${lims.slice(0, SHOW).map((l) => html`<li>${said(short(l), 'api:GET /methods limitations')}</li>`)}</ol>
          ${lims.length > SHOW ? html`<ol class="lims more hide-until" data-step="2" start="${SHOW + 1}">${lims.slice(SHOW).map((l) => html`<li>${said(short(l), 'api:GET /methods limitations')}</li>`)}</ol>` : ''}
        </div>
        <div class="lm-right">
          <div class="lm-block enter" style="--i:3">
            <div class="label">A new campus is three inputs</div>
            <div class="scale">
              <div class="sc-in"><span>${icon('I')}GTFS timetables</span><span>${icon('II')}OSM / Overture streets</span><span>${icon('III')}Building list</span></div>
              <div class="sc-arrow"></div>
              <div class="sc-eng"><span class="label">Output</span><h3>Same engine</h3></div>
            </div>
            ${m?.timings_s ? html`<p class="micro">Ann Arbor build · ${num(fmt(m.walk_graph?.nodes ?? 0, 'int'), 'api:GET /manifest')} street nodes · ${num(fmt(m.labels?.scans ?? 0, 'int'), 'api:GET /manifest')} timetable scans</p>` : ''}
          </div>
          <div class="lm-block lm-plan enter" style="--i:4" data-step="1">
            <div class="label">Plan — not traction</div>
            <h3>Business model sketch</h3>
            <div class="biz">
              <div class="agenda-row"><span class="an">I</span><p><b>Free for students</b>, always: no accounts, no data sale.</p></div>
              <div class="agenda-row"><span class="an">II</span><p><b>Campus licence</b>: off-campus housing offices embed it for incoming and transfer students.</p></div>
              <div class="agenda-row"><span class="an">III</span><p><b>Verified listings</b>: landlords pay to have fees and utilities checked — never to rank higher.</p></div>
            </div>
          </div>
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>X · Limits & next (12 s).</b> "Here is what we don't know" — point at the list; don't read it. Representative service week, no real-time delays, listing prices from search extracts, utilities are estimates.</p>
      <p>Reveal (→) business sketch: clearly a plan. Reveal (→) the remaining limits if asked.</p><p>Then → to the closing plate.</p>`;
  },
};

export { esc };
