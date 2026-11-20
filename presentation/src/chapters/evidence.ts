// VI · Evidence. Every number: presentation/data/facts.json. One hero (the two-anchor week), one quiet comparison
// (one anchor), one step of validation. Portal comparison, ablation and the CIs live in the notes (judges will probe).
// Field-ride validation is never claimed unless data/field.json exists.
import type { Chapter } from '../deck';
import { html, esc } from '../lib';
import { F, factVal, getFact } from '../facts';

const fieldFiles = import.meta.glob('../../data/field.json', { eager: true, import: 'default' }) as Record<string, any>;
const FIELD: any = Object.values(fieldFiles)[0] ?? null;

export const evidence: Chapter = {
  id: 'evidence',
  title: 'Evidence',
  budget: 25,
  steps: 1,
  render() {
    const tests = factVal('tests');
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">Class and a job? <em>Commute filters fail.</em></h2>
      <div class="ev-grid grow">
        <div class="ev-hero enter" style="--i:2">
          <div class="hero">${F('ablation_lsa-kerrytown-job_full_ne_single_dest', { digits: 0, suffix: '%' })}</div>
          <div class="hero-cap">of semesters, a single-destination commute model picks a different #1 for <b>classes + a Kerrytown job</b></div>
        </div>
        <div class="ev-side enter" style="--i:3">
          <div class="hero sm mute">${F('ablation_full_ne_single_dest', { digits: 0, suffix: '%' })}</div>
          <div class="ev-cap">with one anchor, a commute filter is <b>mostly fine</b></div>
        </div>
      </div>
      <div class="ev-val hide-until" data-step="1">
        <div><span class="ev-v">${F('desk_bus_legs_matched')}</span><span class="ev-l">bus legs match the published timetable</span></div>
        <div><span class="ev-v">${tests ? html`<span class="num" data-src="facts:tests">${esc(tests.passed)}</span>` : F('tests')}</span><span class="ev-l">automated tests passing</span></div>
        ${FIELD ? html`<div><span class="ev-v">${esc(String(FIELD.headline ?? ''))}</span><span class="ev-l">field rides vs prediction</span></div>` : html`<div><span class="ev-v ev-pend">not yet</span><span class="ev-l">field rides — protocol written, not run</span></div>`}
      </div>`;
  },
  notes() {
    const f = (id: string) => { const x = getFact(id); return x ? `${typeof x.value === 'object' ? JSON.stringify(x.value) : x.value}${x.ci95 ? ` (95% CI ${x.ci95[0]}–${x.ci95[1]})` : ''}` : '…'; };
    return `<p><b>VI · Evidence (25 s) — be precise, judges will probe.</b></p>
      <p>Headline: "If your week has one anchor, a commute filter is fine. If it has two, it picks the wrong home most of the time." Two-anchor week (classes + Kerrytown job): #1 differs from a single-destination commute model in ${f('ablation_lsa-kerrytown-job_full_ne_single_dest')}% of semesters; wrong pick costs ~$${f('ablation_kerrytown_regret_single_dest_mean')}/mo on average. One anchor, all templates: ${f('ablation_full_ne_single_dest')}%. Among homes renting $1,200–1,400 where options are close: ${f('ablation_band_1200-1400_full_ne_single_dest')}%.</p>
      <p>Portal comparison (rent cap + distance): #1 differs in ${f('ablation_full_ne_baseline')}%, median gap $${f('ablation_regret_baseline_median')}/mo — say it's <b>mostly per-person rent and all-in accounting, not routing</b>.</p>
      <p>Ablation: valuing time is the big lever (${f('ablation_flip_vot_zero')}% of #1s change at VOT = 0); walk/wait weights ${f('ablation_flip_walk_wait_mult_1')}%, January weather ${f('ablation_flip_no_weather_jan')}%, early-arrival ${f('ablation_flip_no_early_arrival')}% — precision, not drivers.</p>
      <p>Reveal (→) validation: ${f('desk_bus_legs_matched')} bus legs match GTFS (independent parser, max diff ${f('desk_max_ivt_diff_min')} min); UgLi→BBB ${f('ugli_to_bbb_bus_total_min')} min by bus vs ${f('ugli_to_bbb_walk_min')} walking. <b>Never say we rode the buses</b> unless the slide shows field results.</p>
      <p>Design: 300 sampled semesters × 8 templates, 69 observed listings, rent cap $1,400/person, VOT $7.50/h, fall.</p>`;
  },
};
