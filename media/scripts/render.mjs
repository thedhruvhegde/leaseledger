// Deterministic frame-by-frame renderer: loads media/scripts/scenes/<name>.html in headless Chromium, injects
// media/videos/<name>.json as window.DATA plus the deck fonts (base64), calls window.renderFrame(t) for every
// frame and pipes JPEG screenshots into ffmpeg (H.264, yuv420p, 1920x1080, 30 fps, faststart).
//   node media/scripts/render.mjs <name> [--from s] [--to s] [--frames t1,t2,...]   (frames: PNG stills only)
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const OUT = path.join(ROOT, 'media/videos');
const name = process.argv[2];
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const FPS = 30;

const fontDir = path.join(ROOT, 'presentation/node_modules/@fontsource-variable');
const f64 = (p) => fs.readFileSync(path.join(fontDir, p)).toString('base64');
const FONT_CSS = `
@font-face{font-family:'Fraunces';font-style:normal;font-weight:100 900;src:url(data:font/woff2;base64,${f64('fraunces/files/fraunces-latin-full-normal.woff2')}) format('woff2');}
@font-face{font-family:'Fraunces';font-style:italic;font-weight:100 900;src:url(data:font/woff2;base64,${f64('fraunces/files/fraunces-latin-full-italic.woff2')}) format('woff2');}
@font-face{font-family:'Inter Tight';font-style:normal;font-weight:100 900;src:url(data:font/woff2;base64,${f64('inter-tight/files/inter-tight-latin-wght-normal.woff2')}) format('woff2');}
@font-face{font-family:'Inter Tight';font-style:italic;font-weight:100 900;src:url(data:font/woff2;base64,${f64('inter-tight/files/inter-tight-latin-wght-italic.woff2')}) format('woff2');}
`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const dataPath = path.join(OUT, `${name}.json`);
const data = fs.existsSync(dataPath) ? fs.readFileSync(dataPath, 'utf8') : 'null';
await page.addInitScript(`window.DATA = ${data};`);
page.on('console', (m) => { if (m.type() === 'error') console.error('[page]', m.text()); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.goto('file://' + path.join(HERE, 'scenes', `${name}.html`));
await page.addStyleTag({ content: FONT_CSS });
await page.evaluate(async () => { await document.fonts.load('400 40px Fraunces'); await document.fonts.load('400 40px "Inter Tight"'); await document.fonts.load('italic 400 40px Fraunces'); await document.fonts.ready; });
await page.evaluate(() => window.setup && window.setup());
const DURATION = await page.evaluate(() => window.DURATION);
const POSTER = await page.evaluate(() => window.POSTER_T ?? window.DURATION * 0.8);

const stills = arg('--frames');
if (stills) {
  const dir = path.join(ROOT, 'media/check', name); fs.mkdirSync(dir, { recursive: true });
  for (const t of stills.split(',').map(Number)) {
    await page.evaluate((t) => window.renderFrame(t), t);
    await page.screenshot({ path: path.join(dir, `t${String(t).padStart(5, '0')}.png`) });
  }
  console.log('stills ->', dir);
  await browser.close();
  process.exit(0);
}

const t0 = Number(arg('--from', 0)), t1 = Number(arg('--to', DURATION));
const nFrames = Math.round((t1 - t0) * FPS);
const mp4 = path.join(OUT, `${name}.mp4`);
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-tune', 'animation', '-pix_fmt', 'yuv420p', '-r', String(FPS),
  '-movflags', '+faststart', mp4], { stdio: ['pipe', 'inherit', 'inherit'] });
const started = Date.now();
for (let i = 0; i < nFrames; i++) {
  const t = t0 + i / FPS;
  await page.evaluate((t) => window.renderFrame(t), t);
  const buf = await page.screenshot({ type: 'jpeg', quality: 94 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (i % 150 === 0) console.log(`${name}: frame ${i}/${nFrames} (${((Date.now() - started) / 1000).toFixed(0)} s)`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
// poster
await page.evaluate((t) => window.renderFrame(t), POSTER);
await page.screenshot({ path: path.join(OUT, `${name}.png`) });
await browser.close();
console.log(`${name}: ${nFrames} frames in ${((Date.now() - started) / 1000).toFixed(0)} s -> ${mp4}`);
