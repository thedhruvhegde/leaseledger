// Cover: full-bleed Ann Arbor, with one student's real week of trips drawn on in ink.
// Geometry: POST /compare (plan.routes) — every leg the engine routed for the #1 home, on the real timetable.
import type { Chapter } from '../deck';
import { html, loop } from '../lib';
import { plan } from '../api';
import { base, loadBase, bboxOf, routeLayer, streets } from '../routemap';

export function cityMap(cls: string, stagger = 40): string {
  const b = base;
  const ev = plan.routes?.a;
  if (!b) return '';
  // 16:9 window around the route bbox (falls back to central Ann Arbor + North Campus)
  const bb = ev ? bboxOf(b, [ev]) : { x0: 368, y0: 192, x1: 720, y1: 576 };
  const H = Math.max(520, (bb.y1 - bb.y0) * 1.5), W = (H * 16) / 9;
  const cx = (bb.x0 + bb.x1) / 2 - W * 0.17, cy = (bb.y0 + bb.y1) / 2 + H * 0.03;
  return html`<svg class="${cls}" viewBox="${cx - W / 2} ${cy - H / 2} ${W} ${H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    ${streets(b)}
    ${ev ? routeLayer(b, ev, '', stagger) : ''}
  </svg>`;
}

export const cover: Chapter = {
  id: 'cover',
  title: 'Lease Ledger',
  budget: 8,
  deps: ['routes'],
  render() {
    return html`
      <div class="geo cv-map">${cityMap('cv-svg')}</div>
      <div class="cv-vid enter" style="--i:2">${loop('one-week', 'one week, routed')}</div>
      <div class="cv-panel enter" style="--i:1">
        <h1 class="cv-title">Lease Ledger</h1>
        <p class="cv-sub">What a home costs <em>the week you live&nbsp;it.</em></p>
      </div>
      <div class="cv-key enter" style="--i:3"><span class="cv-k"><i class="k-bus"></i>bus</span><span class="cv-k"><i class="k-walk"></i>walk</span><span class="cv-k">one engineer’s week, routed on real timetables</span></div>`;
  },
  mount(el) {
    if (!base) loadBase().then((b) => b && el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
  },
  notes() {
    return `<p><b>Cover (≈8 s).</b> "We're Lease Ledger." Press T as you start talking. The ink lines are one North Campus engineer's real week of trips from the home our engine ranks #1 — every bus leg is a scheduled trip on this fall's UM + TheRide timetables.</p>
      <p>The plate above the title is the one-week explainer loop (media/videos/fast/one-week.mp4, 10× speed): the same #1 home's day tours, routed trip by trip. Don't narrate it; it's atmosphere.</p>`;
  },
};
