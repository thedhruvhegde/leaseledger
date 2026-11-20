// Evidence chapter. Every number: presentation/data/facts.json (with its 95% CI where the fact has one).
// Framing (lead's rules): portal gap is mostly rent-normalisation + all-in accounting, not routing; the fair test is
// week vs single-destination commute; time value is the big lever; refinements are precision, not drivers;
// field ride validation is pending unless data/field.json exists.
import type { Chapter } from '../deck';
import { html, said, esc, eyebrow } from '../lib';
import { F, CI, factVal, getFact } from '../facts';

const fieldFiles = import.meta.glob('../../data/field.json', { eager: true, import: 'default' }) as Record<string, any>;
const FIELD: any = Object.values(fieldFiles)[0] ?? null;

/** Ablation bar: 1px ink-bordered bar on a bg-secondary track, CI as a dashed taupe span. */
const bar = (id: string, max = 100) => {
  const v = Number(factVal(id) ?? 0);
  const ci = getFact(id)?.ci95;
  return html`<span class="ab-track"><i class="ab-fill" style="width:${Math.max(0.3, (v / max) * 100)}%"></i>${ci ? html`<i class="ab-ci" style="left:${(ci[0] / max) * 100}%;width:${Math.max(0.3, ((ci[1] - ci[0]) / max) * 100)}%"></i>` : ''}</span>`;
};

export const evidence: Chapter = {
  id: 'evidence',
  title: 'Evidence',
  numeral: 'VI',
  gist: 'One anchor or two — ablation and validation',
  budget: 25,
  steps: 3,
  render() {
    const how = getFact('ablation_full_ne_single_dest')?.how ?? '';
    const BAND = 'ablation_band_1200-1400_full_ne_single_dest';
    const bm = BAND.match(/band_(\d+)-(\d+)/);
    const bandLabel = bm ? `$${Number(bm[1]).toLocaleString('en-US')}–${Number(bm[2]).toLocaleString('en-US')}` : '';
    const design = how.split(';').slice(1).join(';').replace(/; Wilson.*$/, '').trim();
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'Evidence · ablation on real listings')}
      <h2 class="ev-title enter" style="--i:1">One anchor? A commute filter is fine.<br/><em>Two anchors? It picks the wrong home most of the time.</em></h2>
      <div class="ev-grid grow">
        <div class="ev-main enter" style="--i:2">
          <div class="label">The fair test · full week vs a single-destination commute model</div>
          <div class="ev-pair">
            <div class="ev-a">
              <div class="ev-k micro">One anchor · all templates</div>
              <div class="ev-big">${F('ablation_full_ne_single_dest', { suffix: '%' })}</div>
              <div class="ev-l">of semesters, #1 changes</div>
              <div class="micro">${CI('ablation_full_ne_single_dest', '%')}</div>
            </div>
            <div class="ev-b">
              <span class="h-rule"></span>
              <div class="ev-k micro">Two anchors · classes + Kerrytown job</div>
              <div class="ev-big ev-hero">${F('ablation_lsa-kerrytown-job_full_ne_single_dest', { suffix: '%' })}</div>
              <div class="ev-l">of semesters, #1 changes</div>
              <div class="micro">${CI('ablation_lsa-kerrytown-job_full_ne_single_dest', '%')} · wrong pick costs ${F('ablation_kerrytown_regret_single_dest_mean', { prefix: '$', suffix: '/mo' })} on average</div>
            </div>
          </div>
          <div class="ev-notes">
            <p>Among homes renting for ${said(bandLabel, 'facts:' + BAND + ' (id)')}, where options are close: <b>${F(BAND, { suffix: '%' })}</b> <span class="micro">${CI(BAND, '%')}</span></p>
            <p>Against a listing portal (rent cap + distance), #1 differs in <b>${F('ablation_full_ne_baseline', { suffix: '%' })}</b> <span class="micro">${CI('ablation_full_ne_baseline', '%')}</span>, median gap ${F('ablation_regret_baseline_median', { prefix: '$', suffix: '/mo' })} — <em class="serif">mostly per-person rent and all-in accounting, not routing.</em></p>
          </div>
          ${design ? html`<div class="micro ev-design">${said(design, 'facts:ablation_full_ne_single_dest.how')}</div>` : ''}
        </div>
        <div class="ev-side">
          <div class="ev-block" data-step="1">
            <div class="label">Ablation · what moves #1 when one part is removed</div>
            <div class="ab">
              <div class="ab-r big"><span>Value time at zero</span>${bar('ablation_flip_vot_zero')}${F('ablation_flip_vot_zero', { suffix: '%' })}</div>
              <div class="ab-r"><span>Walk/wait weights = one</span>${bar('ablation_flip_walk_wait_mult_1')}${F('ablation_flip_walk_wait_mult_1', { suffix: '%' })}</div>
              <div class="ab-r"><span>No January weather</span>${bar('ablation_flip_no_weather_jan')}${F('ablation_flip_no_weather_jan', { suffix: '%' })}</div>
              <div class="ab-r"><span>No early-arrival cost</span>${bar('ablation_flip_no_early_arrival')}${F('ablation_flip_no_early_arrival', { suffix: '%' })}</div>
            </div>
            <p class="small">Valuing time is the lever. The refinements make the receipt precise and explainable; they rarely change #1 — and we say so.</p>
          </div>
          <div class="ev-block" data-step="2">
            <div class="label">Validation</div>
            <div class="val">
              <div><b>${F('desk_bus_legs_matched')}</b><span>bus legs match the GTFS schedule exactly (independent parser; max diff ${F('desk_max_ivt_diff_min', { suffix: ' min' })})</span></div>
              <div><b>${F('ugli_to_bbb_bus_total_min', { suffix: ' min' })}</b><span>UgLi → BBB by bus, vs ${F('ugli_to_bbb_walk_min', { suffix: ' min' })} walking</span></div>
              <div><b>${(() => { const t = factVal('tests'); return t ? html`<span class="num" data-src="facts:tests">${esc(t.passed)}</span>` : F('tests'); })()}</b><span>automated tests passing — routing vs independent Dijkstra, ledger, API</span></div>
              <div data-step="3" class="hide-until">${FIELD ? html`<b>${said(String(FIELD.headline ?? FIELD.summary ?? ''), 'facts:field.json')}</b><span>field rides vs prediction</span>` : html`<b class="pend">pending</b><span>Field ride validation: protocol written, not yet run — we have not ridden these trips</span>`}</div>
            </div>
          </div>
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>VI · Evidence (25 s) — be precise, judges will probe.</b></p>
      <p>Headline: "If your week has one anchor, a commute filter is fine. If it has two, it picks the wrong home most of the time." Overall the week changes #1 vs a single-destination commute model in ~8% of semesters; for a two-anchor week (classes + Kerrytown job) ~60%, ~$62/mo wrong-pick cost; ~21% among $1,200–1,400 homes.</p>
      <p>Portal comparison (~97%, $555/mo median) — say it's mostly per-person rent and all-in accounting, <b>not</b> routing.</p>
      <p>Reveal (→) ablation: valuing time is the big lever (~63%); walk/wait, weather, early-arrival rarely change #1 — precision, not drivers.</p>
      <p>Reveal (→) validation: 11/11 bus legs match GTFS. Reveal (→) field: <b>never say we rode the buses</b> unless the slide shows results.</p>`;
  },
};
