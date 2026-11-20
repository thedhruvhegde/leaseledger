#!/usr/bin/env node
// Build-time honesty checks.
//  1. Slide copy (literal text inside html`...` templates in src/chapters/*.ts) contains NO digits,
//     except tokens in scripts/copy-whitelist.json. Numbers must arrive via ${...} from the API / facts.
//  2. Citation `finding` prose (src/citations.ts) contains no digits.
//  3. Evidence placeholders: presentation/data/ must satisfy src/required-data.json.
//     --strict (used by `npm run build`) FAILS when anything is unresolved; otherwise it only warns.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const strict = process.argv.includes('--strict');
const wl = JSON.parse(readFileSync(join(root, 'scripts/copy-whitelist.json'), 'utf8'));
const allowed = wl.tokens.map((t) => new RegExp(t, 'g'));
let errors = 0, warnings = 0;
const err = (m) => { errors++; console.error('  ✗ ' + m); };
const warn = (m) => { warnings++; console.warn('  ! ' + m); };

// ---------- 1. html`` literal scanner ----------
function scanTemplates(src) {
  const out = []; // { text, line }
  const lineAt = (i) => src.slice(0, i).split('\n').length;
  function skipString(i, q) { i++; while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++; } return i + 1; }
  // parse template starting at src[i] === '`'; collect literals if `collect`
  function template(i, collect) {
    i++; let buf = '', start = i;
    while (i < src.length) {
      const c = src[i];
      if (c === '\\') { buf += src[i + 1] ?? ''; i += 2; continue; }
      if (c === '`') { if (collect) out.push({ text: buf, line: lineAt(start) }); return i + 1; }
      if (c === '$' && src[i + 1] === '{') { buf += '\u0000'; i = expr(i + 2); continue; }
      buf += c; i++;
    }
    return i;
  }
  function expr(i) {
    let depth = 1;
    while (i < src.length && depth > 0) {
      const c = src[i];
      if (c === "'" || c === '"') { i = skipString(i, c); continue; }
      if (c === '`') { const isHtml = /html$/.test(src.slice(Math.max(0, i - 4), i)); i = template(i, isHtml); continue; }
      if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue; }
      if (c === '{') depth++;
      if (c === '}') depth--;
      i++;
    }
    return i;
  }
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue; }
    if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i + 2) + 1; continue; }
    if (c === "'" || c === '"') { i = skipString(i, c) - 1; continue; }
    if (c === '`') { const isHtml = /html$/.test(src.slice(Math.max(0, i - 4), i)); i = template(i, isHtml) - 1; }
  }
  return out;
}
const visible = (t) => t
  .replace(/<style[\s\S]*?<\/style>/g, ' ')
  .replace(/<[^>]*>/g, ' ')          // tags (with attributes, even when an attribute is an interpolation)
  .replace(/&[a-z#0-9]+;/gi, ' ')
  .replace(/\u0000/g, ' ');

console.log('check-copy: slide copy must not contain hard-coded digits');
const dir = join(root, 'src/chapters');
for (const f of readdirSync(dir).filter((f) => f.endsWith('.ts'))) {
  const src = readFileSync(join(dir, f), 'utf8');
  for (const { text, line } of scanTemplates(src)) {
    let v = visible(text);
    for (const re of allowed) v = v.replace(re, ' ');
    const m = v.match(/[^\s]*\d[^\s]*/g);
    if (m) err(`src/chapters/${f}:${line}: digits in slide copy: ${m.slice(0, 4).join(' ')}  (bind the number via \${num(...)} from API/facts, or whitelist a non-numeric token)`);
  }
}
{
  const src = readFileSync(join(root, 'src/citations.ts'), 'utf8');
  for (const m of src.matchAll(/finding:\s*'([^']*)'/g)) if (/\d/.test(m[1])) err(`src/citations.ts: digits in citation finding: "${m[1].slice(0, 60)}…"`);
}

// ---------- 3. evidence data ----------
console.log('check-copy: evidence from presentation/data/');
const req = JSON.parse(readFileSync(join(root, 'src/required-data.json'), 'utf8'));
const dataDir = join(root, 'data');
const unresolved = [];
const factsPath = join(dataDir, req.facts_file);
let facts = null;
if (!existsSync(factsPath)) unresolved.push(`${req.facts_file} missing`);
else {
  try { facts = JSON.parse(readFileSync(factsPath, 'utf8')); } catch (e) { unresolved.push(`${req.facts_file} is not valid JSON (${e.message})`); }
}
const has = (k) => {
  if (!facts) return false;
  for (const p of [facts.facts, facts.sections, facts]) {
    if (!p) continue;
    if (Array.isArray(p) ? p.some((x) => x && (x.id === k || x.key === k || x.name === k)) : typeof p === 'object' && k in p) return true;
  }
  return false;
};
if (facts) for (const s of req.facts_required) if (!has(s.id)) unresolved.push(`${req.facts_file} has no fact "${s.id}" — ${s.why}`);
const surf = existsSync(dataDir) ? readdirSync(dataDir).filter((f) => /^surface-.*\.geojson$/.test(f)) : [];
if (surf.length < req.surfaces_min) unresolved.push(`${surf.length} of ${req.surfaces_min} ${req.surface_glob} files present`);
for (const u of unresolved) (strict ? err : warn)(`PLACEHOLDER unresolved: ${u}`);
for (const [f, why] of Object.entries(req.optional)) if (!existsSync(join(dataDir, f))) console.log(`  · optional ${f} absent: ${why}`);
if (!existsSync(join(root, 'data/multicity.json'))) console.log('  · optional data/multicity.json absent: multi-city chapter shows "pending"');
if (!existsSync(join(root, 'public/snapshot.json'))) (strict ? err : warn)('public/snapshot.json missing — run `npm run snapshot` with the API up (offline fallback)');

console.log(errors ? `check-copy: ${errors} error(s), ${warnings} warning(s)` : `check-copy: ok (${warnings} warning(s))`);
process.exit(errors ? 1 : 0);
