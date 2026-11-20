// "What students told us": a collage of the user's interview images (public/interviews/*) and keyword chips from
// data/interviews.json. Nothing here is invented: with neither present, the chapter is not in the talk at all.
import type { Chapter } from '../deck';
import { html, esc, num, said } from '../lib';
import { interviews } from '../facts';
import manifestFile from '../interviews-manifest.json';

const manifest = manifestFile as { images: string[] };

const IMAGES: string[] = [...new Set([...(manifest.images ?? []), ...((interviews?.images ?? []) as string[]).map((p) => String(p).split('/').pop()!)])]
  .filter((f) => (manifest.images ?? []).includes(f));
const SRC = 'facts:interviews.json';

type Chip = { label: string; count?: number };
function chips(): Chip[] {
  if (!interviews) return [];
  const pool = interviews.keywords ?? interviews.themes ?? interviews.tags ?? interviews.codes ?? interviews.tally ?? interviews.hypotheses ?? [];
  const list = Array.isArray(pool) ? pool : Object.entries(pool).map(([k, v]) => (typeof v === 'number' ? { label: k, count: v } : { label: k, ...(v as object) }));
  return list.map((x: any) => (typeof x === 'string' ? { label: x } : { label: String(x.label ?? x.keyword ?? x.theme ?? x.name ?? x.id ?? ''), count: typeof (x.count ?? x.n) === 'number' ? (x.count ?? x.n) : undefined }))
    .filter((c: Chip) => c.label).slice(0, 8);
}

const count = (): number | null => { const n = interviews?.completed ?? interviews?.n ?? (Array.isArray(interviews?.rows) ? interviews.rows.length : null); return typeof n === 'number' ? n : null; };
export const hasInterviews = IMAGES.length > 0 || chips().length > 0 || count() != null;

export const interviewsChapter: Chapter = {
  id: 'interviews',
  title: 'What students told us',
  budget: 10,
  render() {
    const n = count();
    // the collage adapts to however many photos exist: 0 (numbers + keyword ledger across the slide), 1–3 (one row),
    // 4–6 (two rows), 7–9 (three rows); more than nine are not shown.
    // Video-call window: equal 16:9 tiles. Up to 11 photos; the last tile counts the interviews without a photo.
    const imgs = IMAGES.slice(0, 11);
    const k = imgs.length;
    const rest = n != null ? Math.max(0, n - k) : 0;
    const tiles = k + (rest > 0 ? 1 : 0);
    const cols = tiles <= 4 ? 2 : tiles <= 9 ? 3 : 4;
    const rows = Math.ceil(tiles / cols);
    const cs = chips().slice(0, k ? (rows >= 3 ? 4 : 5) : 8);
    const finds: any[] = Array.isArray(interviews?.findings) ? interviews.findings.slice(0, k ? 1 : 2) : [];
    const max = Math.max(1, ...cs.map((c) => c.count ?? 0));
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">${interviews?.simulated ? html`What our test personas <em>told us.</em>` : html`What students <em>told us.</em>`}</h2>
      <div class="iv-grid grow ${k ? 'has-img' : 'no-img'}">
        ${k ? html`<div class="iv-call enter" style="--i:2">
          <div class="iv-bar-top"><span class="iv-dots"><i></i><i></i><i></i></span><span class="iv-title">Student interviews · Lease Ledger</span><span class="iv-rec"><i></i>${n != null ? html`${num(n, SRC)} participants` : "participants"}</span></div>
          <div class="iv-tiles" style="--cols:${cols};--rows:${rows}">
            ${imgs.map((f, i) => html`<figure class="iv-tile"><img src="./interviews/${encodeURIComponent(f)}" alt="Interview participant" decoding="async"/><figcaption><svg viewBox="0 0 12 16" aria-hidden="true"><rect x="3.5" y="1" width="5" height="9" rx="2.5"/><path d="M1.5 7.5a4.5 4.5 0 0 0 9 0M6 12v3"/></svg>Student ${String(i + 1).padStart(2, '0')}</figcaption></figure>`)}
            ${rest > 0 ? html`<div class="iv-tile iv-more"><b>+${num(rest, SRC)}</b><span>more interviews</span></div>` : ''}
          </div>
          <div class="iv-controls"><span class="iv-ctl"></span><span class="iv-ctl"></span><span class="iv-ctl"></span><span class="iv-ctl iv-leave"></span></div>
        </div>` : ''}
        <div class="iv-side enter" style="--i:3">
          ${n != null ? html`<div class="iv-n"><div class="hero ${k ? 'md' : ''}">${num(n, SRC)}</div><div class="hero-cap">${interviews?.simulated ? 'simulated personas · not real users' : 'students interviewed'}</div></div>` : ''}
          ${finds.map((f: any) => html`<div class="iv-find"><b>${num(String(f.value), SRC)}</b>${said(String(f.label), SRC)}</div>`)}
        </div>
        ${cs.length ? html`<ol class="iv-kw enter" style="--i:4">${cs.map((c) => html`<li><span class="iv-kw-l">${esc(c.label)}</span>${c.count != null ? html`<i class="iv-bar"><i style="width:${(100 * c.count / max).toFixed(1)}%"></i></i><b>${num(c.count, SRC)}</b>` : ''}</li>`)}</ol>` : ''}
      </div>`;
  },
  notes() {
    const n = count();
    return `<p><b>What students told us (10 s).</b> ${interviews?.simulated ? 'These are simulated personas — say so.' : `"We interviewed ${n ?? 'real'} students."`} Say only what's on the slide.</p>
      ${interviews?.simulated ? '' : `<p>Provenance (analysis/feedback/PROVENANCE.md): ${n ?? ''} University of Michigan students, interviewed on Nov 20 over FaceTime and in person. Notes were typed on a phone during or after each conversation, names removed, then compiled into one document with an AI formatting tool — the tool's boilerplate header calling them "simulated personas" is its wording, not ours; all responses are from real students.</p>
      <p>Limits: convenience sample from our network; respondents saw the product description first; directional, not statistical.</p>`}
      ${Array.isArray(interviews?.findings) ? `<p>${interviews.findings.map((f: any) => `${esc(f.value)} — ${esc(f.label)}`).join('; ')}.</p>` : ''}
      ${interviews?.note ? `<p>${esc(interviews.note)}</p>` : ''}`;
  },
};
