// IX · Group Week: the app's Group Week screen + ONE number (each roommate's fair rent) + the envy check.
import type { Chapter } from '../deck';
import { plan, listing, sname } from '../api';
import { html, num, fmt, tag } from '../lib';
import { citeTag } from '../citations';

const G = 'api:POST /group';

export const group: Chapter = {
  id: 'group',
  title: 'Group Week',
  budget: 15,
  deps: ['group', 'listings'],
  render() {
    const g = plan.group;
    if (!g?.splits?.length) {
      return html`<h2>Roommates, priced fairly.</h2><div class="pending" style="margin-top:40px"><b>Loading</b>POST /api/group</div>`;
    }
    const order: string[] = g.ranking ?? g.splits.map((s: any) => s.listing_id);
    const win = order.map((id) => g.splits.find((s: any) => s.listing_id === id)).filter(Boolean)[0];
    const members = Object.keys(win.rent);
    const rents = members.map((m) => win.rent[m] as number);
    const equal = Math.max(...rents) - Math.min(...rents) < 0.5;
    const maxEnvy = Math.max(...win.envy_matrix.flat().map((x: number) => Math.abs(x)));
    const syn = /synthetic/i.test(listing(win.listing_id)?.provenance ?? '');
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">Roommates: <em>one split nobody envies.</em></h2>
      <div class="gw-grid grow">
        <div class="plate-img gw-shot enter" style="--i:2"><img src="./img/10-group-week.png" alt="Group Week in the app: three roommates, three weeks" decoding="async"/></div>
        <div class="gw-side enter" style="--i:3">
          <div class="gw-home">${sname(win.listing_id)}</div>
          ${equal
            ? html`<div class="hero md">${num(fmt(rents[0], 'usd'), G)}</div><div class="hero-cap">each, for ${num(members.length, G)} roommates with their own weeks</div>`
            : html`<div class="gw-rents">${members.map((m) => html`<div><span class="hero sm">${num(fmt(win.rent[m], 'usd'), G)}</span><span class="gw-m">${m}</span></div>`)}</div>`}
          <div class="gw-envy"><span class="hero sm">${num(fmt(maxEnvy < 0.005 ? 0 : maxEnvy, 'usd'), G)}</span><span class="hero-cap">largest envy: <b>nobody wants to swap</b></span></div>
          <div class="chips">${citeTag('gal')}${syn ? tag('synthetic listing') : ''}</div>
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>IX · Group Week (15 s).</b> "Each roommate's own routine priced from each home. We rank homes by how well-off the worst-off roommate is, then split rent with the envy-free maximin LP (Gal et al. 2017)."</p>
      <p>Honest point if asked: the demo homes have identical rooms, so envy-freeness forces equal rent; the commute changes <i>which home</i> wins. Not strategy-proof (Dufton & Larson 2011). The demo roommates are template-based examples, not real people.</p>`;
  },
};
