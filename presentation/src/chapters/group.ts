import type { Chapter } from '../deck';
import { plan, listing, sname } from '../api';
import { html, num, esc, fmt, eyebrow } from '../lib';
import { citeTag } from '../citations';
import { tex, eqOf } from './how';

const G = 'api:POST /group';

export const group: Chapter = {
  id: 'group',
  title: 'Group Week',
  numeral: 'IX',
  gist: 'A fair, envy-free rent split',
  budget: 18,
  steps: 1,
  deps: ['group', 'listings', 'methods'],
  render() {
    const g = plan.group;
    if (!g?.splits?.length) {
      return html`${eyebrow(this.numeral, 'Group Week')}<h2>Roommates, priced fairly.</h2><div class="pending" style="margin-top:40px"><b>Loading</b>POST /api/group</div>`;
    }
    const order: string[] = g.ranking ?? g.splits.map((s: any) => s.listing_id);
    const splits = order.map((id) => g.splits.find((s: any) => s.listing_id === id)).filter(Boolean);
    const members = Object.keys(splits[0].rent);
    const win = splits[0];
    const maxEnvy = Math.max(...win.envy_matrix.flat().map((x: number) => Math.abs(x)));
    const eq = eqOf('envy_free_lp');
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'Group Week', citeTag('gal'))}
      <h2 class="enter" style="--i:1">Roommates, each with their own week. <em>One split nobody envies.</em></h2>
      <div class="gw-grid grow">
        <div class="gw-left enter" style="--i:2">
          <div class="label">Monthly surplus per roommate · room value − rent − their own travel cost</div>
          <table class="gtab">
            <thead><tr><th>Home</th>${members.map((m) => html`<th class="r">${esc(m)}</th>`)}<th class="r">Worst-off</th></tr></thead>
            <tbody>${splits.map((s: any, i: number) => {
              const worst = Math.min(...members.map((m) => s.utility[m]));
              return html`<tr class="${i === 0 ? 'win' : ''}">
              <td><div class="gt-n">${sname(s.listing_id)}</div><div class="gt-s micro">${esc(listing(s.listing_id)?.provenance ?? '')}${s.feasible ? '' : ' · over a budget cap'}</div></td>
              ${members.map((m) => html`<td class="r"><span class="gcell ${s.utility[m] === worst ? 'lo' : ''}">${num(fmt(s.utility[m], 'usd'), G)}</span></td>`)}
              <td class="r mm">${num(fmt(s.maximin_utility, 'usd'), G)}</td></tr>`;
            })}</tbody>
          </table>
          <p class="micro gw-note">Ranked by the worst-off roommate (max-of-maximin) · lowest surplus per row underlined · synthetic homes labelled</p>
          <div data-step="1" class="hide-until g-eq">${eq ? html`<div class="eq">${tex(eq.latex)}</div>` : ''}</div>
        </div>
        <div class="gw-right enter" style="--i:3">
          <div class="label">Fair split · ${sname(win.listing_id)}</div>
          <div class="stats g-rents">${members.map((m) => html`<div><span class="fig">${num(fmt(win.rent[m], 'usd'), G)}</span><span class="cap">${esc(m)}</span></div>`)}</div>
          <div class="label" style="margin-top:12px">Envy matrix · gain from swapping rooms</div>
          <div class="envy" style="grid-template-columns:repeat(${members.length},1fr)">${win.envy_matrix.flat().map((x: number) => html`<span>${num(fmt(Math.abs(x) < 0.005 ? 0 : x, 'usd2'), G)}</span>`)}</div>
          <p class="small">Largest envy ${num(fmt(maxEnvy < 0.005 ? 0 : maxEnvy, 'usd2'), G)}: nobody prefers another room at its price. With identical rooms, envy-freeness forces equal rent — what the commute changes is <em class="serif">which home</em>.</p>
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>IX · Group Week (18 s).</b> "Group Week: each roommate's own routine priced from each home. We rank homes by how well-off the worst-off roommate is, then split rent with the envy-free maximin LP (Gal et al.)."</p>
      <p>Honest point if asked: the demo homes have identical rooms, so the fair split is equal rent; the commute changes which home wins. Not strategy-proof (Dufton & Larson). Reveal (→) shows the LP.</p>`;
  },
};
