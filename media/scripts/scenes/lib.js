// Shared helpers for the deterministic scenes. Every scene builds its DOM once in setup() and then
// renderFrame(t) sets every animated property from t alone (no timers), so any frame can be rendered in any order.
const L = (window.L = {});
L.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
// deck easing: cubic-bezier(0.25, 0.6, 0.2, 1) approximated by an ease-out quint blend + smoothstep for in-out
L.easeOut = (x) => 1 - Math.pow(1 - L.clamp(x), 3.2);
L.easeInOut = (x) => { x = L.clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
L.p = (t, t0, dur = 0.6, ease = L.easeOut) => ease((t - t0) / dur);          // eased progress
L.lin = (t, t0, dur) => L.clamp((t - t0) / dur);
L.mix = (a, b, k) => a + (b - a) * k;
L.fade = (el, k, dy = 14) => { el.style.opacity = k; el.style.transform = `translateY(${(1 - k) * dy}px)`; };
L.usd = (x, d = 0) => (x < 0 ? '−$' : '$') + Math.abs(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
L.num = (x, d = 0) => x.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
L.hhmm = (min) => { const m = Math.round(min); return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`; };
L.hhmmss = (sec) => { sec = Math.round(sec); const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`; };
L.h = (tag, attrs = {}, parent, html) => {
  const svg = ['svg', 'g', 'path', 'line', 'circle', 'rect', 'text', 'polyline', 'tspan', 'defs', 'clipPath', 'mask'].includes(tag);
  const el = svg ? document.createElementNS('http://www.w3.org/2000/svg', tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (html != null) el.innerHTML = html;
  if (parent) parent.appendChild(el);
  return el;
};
// polyline helpers: cumulative length, partial polyline up to fraction k
L.cum = (pts) => { const c = [0]; for (let i = 1; i < pts.length; i++) c.push(c[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return c; };
L.partial = (pts, cum, k) => {
  if (!pts.length) return '';
  const total = cum[cum.length - 1], target = total * L.clamp(k);
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    if (cum[i] <= target) { d += `L${pts[i][0]} ${pts[i][1]}`; continue; }
    const seg = cum[i] - cum[i - 1], f = seg > 0 ? (target - cum[i - 1]) / seg : 0;
    d += `L${L.mix(pts[i - 1][0], pts[i][0], f).toFixed(1)} ${L.mix(pts[i - 1][1], pts[i][1], f).toFixed(1)}`;
    break;
  }
  return d;
};
L.at = (pts, cum, k) => {
  const total = cum[cum.length - 1], target = total * L.clamp(k);
  for (let i = 1; i < pts.length; i++) if (cum[i] >= target) { const seg = cum[i] - cum[i - 1], f = seg > 0 ? (target - cum[i - 1]) / seg : 0; return [L.mix(pts[i - 1][0], pts[i][0], f), L.mix(pts[i - 1][1], pts[i][1], f)]; }
  return pts[pts.length - 1];
};
// standard chrome: eyebrow, footer provenance
L.chrome = (eyebrow, foot) => {
  L.h('div', { class: 'eyebrow' }, document.body, `<span class="mark"></span>Lease Ledger <i>·</i> ${eyebrow}`);
  L.h('div', { class: 'foot' }, document.body, foot);
};
// short display names (presentation only; ids and full names stay in the JSON)
L.short = (id, name) => ({
  'icc-escher-double': 'ICC Escher House · double', 'icc-escher-single': 'ICC Escher House · single',
  'university-towers-2br': 'University Towers · 2BR', 'hillcrest-2br': 'Hillcrest Manor · 2BR',
  'um-northwood-1br': 'UM Northwood · 1BR', '1540-packard-room': '1540 Packard · room', 'courtyards-4x4': 'Courtyards · 4x4',
  '603-gott-2br': '603 Gott · 2BR', '322-n-state-1br': '322 N State · 1BR', '1141-s-forest-5br': '1141 S Forest · 5BR',
  'six11-4br': 'Six11 · 4BR', 'landmark-4br': 'Landmark · 4BR', '501-n-5th-1br': '501 N 5th · 1BR',
  'syn-burns-park-house-6br-11': 'Synthetic: Burns Park 6BR', 'syn-old-west-side-house-3br-06': 'Synthetic: Old West Side 3BR',
}[id] || (name || id).split(' - ')[0]);
