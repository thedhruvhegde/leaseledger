// Renders the Lease Ledger mark (house outline whose roofline is a bus route) to PNG app icons.
// Usage: node scripts/make-icons.cjs
const path = require('node:path');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const mark = (stroke) => `<path d="M3.5 16 L10 9.5 L14 12 L19 5.5 L23 9 L28.5 16" stroke-width="2"/><circle cx="10" cy="9.5" r="1.6" stroke-width="1.6" fill="${stroke === '#000' ? '#fff' : '#000'}"/><circle cx="19" cy="5.5" r="1.6" stroke-width="1.6" fill="${stroke === '#000' ? '#fff' : '#000'}"/><circle cx="23" cy="9" r="1.6" stroke-width="1.6" fill="${stroke === '#000' ? '#fff' : '#000'}"/><path d="M7 14v13.5h18V14" stroke-width="2"/><path d="M13.5 27.5v-6.5h5v6.5" stroke-width="1.8"/>`;
// any: white tile, black mark, 12% padding. maskable: black full-bleed tile, white mark inside the 80% safe zone.
const svg = (size, kind) => {
  const bg = kind === 'maskable' ? '#000' : '#fff';
  const fg = kind === 'maskable' ? '#fff' : '#000';
  const pad = kind === 'maskable' ? 0.24 : 0.12;
  const inner = size * (1 - 2 * pad);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><rect width="${size}" height="${size}" fill="${bg}"/><g transform="translate(${size * pad} ${size * pad}) scale(${inner / 32})" fill="none" stroke="${fg}" stroke-linecap="round" stroke-linejoin="round">${mark(fg)}</g></svg>`;
};
(async () => {
  const b = await pw.chromium.launch();
  const p = await b.newPage();
  for (const [size, kind, name] of [[192, 'any', 'icon-192.png'], [512, 'any', 'icon-512.png'], [512, 'maskable', 'icon-maskable-512.png'], [180, 'any', 'apple-touch-icon.png']]) {
    await p.setViewportSize({ width: size, height: size });
    await p.setContent(`<html><body style="margin:0">${svg(size, kind)}</body></html>`);
    await p.screenshot({ path: path.join(__dirname, '../public/icons', name), omitBackground: false });
  }
  await b.close();
})();
