// X · Limits & next. Four short limits (the API serves the full list; the app shows all of them), the honesty items
// moved off earlier slides, and the plan (clearly a plan, not traction).
import type { Chapter } from '../deck';
import { plan } from '../api';
import { html, num } from '../lib';

const SHOW = 4;

export const limits: Chapter = {
  id: 'limits',
  title: 'Limits & next',
  budget: 12,
  steps: 1,
  deps: ['methods'],
  render() {
    const lims: string[] = plan.methods?.limitations ?? [];
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">What we don’t know <em>yet.</em></h2>
      <div class="lm-grid grow">
        <ul class="lm-list enter" style="--i:2">
          <li>Scheduled timetables, not real-time buses</li>
          <li>No delays or ride-to-ride variability</li>
          <li>Prices from search results, not verified pages</li>
          <li>Utilities are estimates, shown as bands</li>
          <li>Other cities: simulated weeks, travel time only</li>
          <li>Field rides: not yet run</li>
          ${lims.length > SHOW ? html`<li class="lm-more">+ ${num(lims.length - SHOW, 'api:GET /methods limitations')} more, listed in the app</li>` : ''}
        </ul>
        <div class="lm-plan hide-until" data-step="1">
          <div class="lm-k">The plan <span>— not traction</span></div>
          <div class="lm-p"><b>Free</b> for students</div>
          <div class="lm-p"><b>Campus licence</b> for housing offices</div>
          <div class="lm-p"><b>Verified listings</b> — never paid ranking</div>
        </div>
      </div>`;
  },
  notes() {
    const lims: string[] = plan.methods?.limitations ?? [];
    return `<p><b>X · Limits & next (12 s).</b> "Here is what we don't know" — point at the list; don't read it. Full list (served by GET /methods, shown in the app):</p><ol>${lims.map((l) => `<li>${l.replace(/[<>&]/g, '')}</li>`).join('')}</ol>
      <p>Reveal (→) the plan: free for students, always — no accounts, no data sale. Campus licence: off-campus housing offices embed it for incoming and transfer students. Verified listings: landlords pay to have fees and utilities checked — never to rank higher. A new campus is three inputs: GTFS timetables, OSM streets, a building list. Then → to the closing plate.</p>`;
  },
};
