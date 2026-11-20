#!/usr/bin/env python3
"""Assemble the recorded tour (media/videos/.work/seg*.mp4 + sections.json from record_full_demo.mjs) into:
  full-demo.mp4 (+ .png poster), full-demo-60s.mp4, walkthrough.mp4 (+ .png, .json), fast/walkthrough.mp4 + .gif,
  and presentation/public/video/walkthrough.{mp4,jpg}.
All outputs: 1920x1080 H.264 yuv420p 30 fps, faststart, silent. Cut points are offsets from the section marks the
recorder logged, so a re-recording keeps the cuts aligned.
  python3 media/scripts/make_demo_cuts.py
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
V = os.path.join(ROOT, 'media', 'videos')
W = os.path.join(V, '.work')
DECK = os.path.join(ROOT, 'presentation', 'public', 'video')
XF = 0.6  # crossfade seconds between segments / clips
ENC = ['-c:v', 'libx264', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an']

S = json.load(open(os.path.join(W, 'sections.json')))
mark = {s['id']: s['t'] for s in S['sections']}
seg_dur = {k: v['duration'] for k, v in S['segments'].items()}


def run(args):
    print('$', ' '.join(a if len(a) < 120 else a[:117] + '...' for a in args))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *args], check=True)


def dur(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ---------- phone segment on a 1920x1080 plate ----------
SCREEN_H = 940
SCREEN_W = round(390 * SCREEN_H / 844 / 2) * 2  # 434
SX, SY = (1920 - SCREEN_W) // 2, (1080 - SCREEN_H) // 2
FRAME_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:1920px;height:1080px;background:transparent;overflow:hidden}}
.win{{position:absolute;left:{SX}px;top:{SY}px;width:{SCREEN_W}px;height:{SCREEN_H}px;border-radius:44px;box-shadow:0 0 0 3000px #f5f5f5}}
.bez{{position:absolute;left:{SX - 12}px;top:{SY - 12}px;width:{SCREEN_W + 24}px;height:{SCREEN_H + 24}px;border-radius:56px;border:12px solid #0a0a0a;box-sizing:border-box;
  box-shadow:0 0 0 1px #d4d4d4}}
.cap{{position:absolute;left:24px;bottom:24px;display:flex;align-items:center;gap:10px;font:600 15px/1 'Inter Tight',system-ui,sans-serif;color:#0a0a0a;background:#fff;
  border:1px solid #d4d4d4;padding:10px 16px 10px 12px;border-radius:9999px}}
.cap .s{{font:500 13px/1 'Inter',system-ui,sans-serif;color:#737373}}
</style></head><body><div class="win"></div><div class="bez"></div>
<div class="cap"><span>On your phone</span><span class="s">same ranking, 390 px wide</span></div></body></html>"""


def phone_plate():
    html = os.path.join(W, 'phone-frame.html')
    png = os.path.join(W, 'phone-frame.png')
    open(html, 'w').write(FRAME_HTML)
    fonts = [os.path.join(ROOT, 'web', 'node_modules', '@fontsource-variable', f) for f in ('inter-tight', 'inter')]
    js = f"""
const {{ chromium }} = require('playwright'); const fs = require('fs');
(async () => {{
  const b = await chromium.launch(); const p = await b.newPage({{ viewport: {{ width: 1920, height: 1080 }} }});
  let html = fs.readFileSync({json.dumps(html)}, 'utf8');
  const ff = (dir, fam) => {{ const f = fs.readdirSync(dir + '/files').find((x) => /latin-wght-normal\\.woff2$/.test(x));
    return f ? `@font-face{{font-family:'${{fam}}';font-weight:100 900;src:url(data:font/woff2;base64,${{fs.readFileSync(dir + '/files/' + f).toString('base64')}}) format('woff2')}}` : ''; }};
  html = html.replace('<style>', '<style>' + ff({json.dumps(fonts[0])}, 'Inter Tight') + ff({json.dumps(fonts[1])}, 'Inter'));
  await p.setContent(html); await p.evaluate(() => document.fonts.ready);
  await p.screenshot({{ path: {json.dumps(png)}, omitBackground: true }}); await b.close();
}})();"""
    subprocess.run(['node', '-e', js], check=True, cwd=os.path.join(ROOT, 'web'))
    out = os.path.join(W, 'seg2-plate.mp4')
    d = seg_dur['seg2']
    run(['-f', 'lavfi', '-i', f'color=c=#f5f5f5:s=1920x1080:r=30:d={d:.3f}', '-i', os.path.join(W, 'seg2.mp4'), '-i', png,
         '-filter_complex', f'[1:v]scale={SCREEN_W}:{SCREEN_H}:flags=lanczos,setpts=PTS-STARTPTS[ph];[0:v][ph]overlay={SX}:{SY}:shortest=1[a];[a][2:v]overlay=0:0,format=yuv420p[v]',
         '-map', '[v]', '-t', f'{d:.3f}', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', '30', out])
    return out


def xfade_concat(clips, out, crf, xf=XF):
    """clips: list of (path, start, end). Trims each, then chains xfade transitions."""
    args, fl = [], []
    for i, (p, a, b) in enumerate(clips):
        args += ['-i', p]
        fl.append(f'[{i}:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,fps=30,format=yuv420p,settb=1/30[c{i}]')
    cur, t = 'c0', clips[0][2] - clips[0][1]
    for i in range(1, len(clips)):
        off = t - xf
        fl.append(f'[{cur}][c{i}]xfade=transition=fade:duration={xf}:offset={off:.3f}[x{i}]')
        cur, t = f'x{i}', off + (clips[i][2] - clips[i][1])
    run([*args, '-filter_complex', ';'.join(fl), '-map', f'[{cur}]', '-crf', str(crf), *ENC, out])
    return t


def poster(src, t, out):
    run(['-ss', f'{t:.2f}', '-i', src, '-frames:v', '1', '-update', '1', out])


seg1, seg3 = os.path.join(W, 'seg1.mp4'), os.path.join(W, 'seg3.mp4')
seg2 = phone_plate()
d1, d2, d3 = dur(seg1), dur(seg2), dur(seg3)
m = lambda k, off=0.0: mark[k] + off  # noqa: E731  (times inside seg1)
P = {s['id']: s['t'] for s in S['sections'] if s['seg'] == 'phone'}

# ---------- 1) full demo ----------
full = os.path.join(V, 'full-demo.mp4')
head = max(0.0, m('landing') - 0.2)
t_full = xfade_concat([(seg1, head, d1 - 0.1), (seg2, 0.0, d2 - 0.1), (seg3, 0.0, d3 - 0.05)], full, crf=24)
poster(full, m('homes', 3.0) - head, os.path.join(V, 'full-demo.png'))

# ---------- 2) 60-s highlights ----------
hl = [
    (seg1, head, m('landing', 3.2)),
    (seg1, m('type-week', 3.0), m('type-week', 8.0)),
    (seg1, m('week-grid', 1.8), m('week-grid', 6.3)),
    (seg1, m('homes', 0.3), m('homes', 6.0)),
    (seg1, m('detail', 1.2), m('detail', 6.5)),
    (seg1, m('compare', 6.8), m('compare', 11.0)),
    (seg1, m('vot', 3.6), m('vot', 11.5)),
    (seg1, m('robustness', 0.8), m('robustness', 5.6)),
    (seg1, m('baseline', 0.8), m('baseline', 4.6)),
    (seg1, m('group', 3.6), m('group', 8.0)),
    (seg1, m('add', 3.2), m('add', 8.0)),
    (seg1, m('methods', 10.0), m('methods', 14.0)),
    (seg2, P['phone-sheet'] - 0.6, P['phone-sheet'] + 4.4),
]
raw = sum(b - a for _, a, b in hl) - XF * (len(hl) - 1)
# stretch/shrink the last-but-one clips evenly so the cut lands on 60 s
adj = (60.0 - raw) / len(hl)
hl = [(p, a, b + adj) for p, a, b in hl]
t_hl = xfade_concat(hl, os.path.join(V, 'full-demo-60s.mp4'), crf=24)

# ---------- 3) walkthrough (~48 s, canonical demo only) ----------
wt = [
    (seg1, head, m('landing', 3.4)),
    (seg1, m('homes', 0.3), m('homes', 9.5)),
    (seg1, m('detail', 0.4), m('detail', 10.5)),
    (seg1, m('compare', 6.8), m('compare', 13.5)),
    (seg1, m('vot', 2.6), m('vot', 15.5)),
    (seg1, m('robustness', 0.6), m('robustness', 9.0)),
]
wpath = os.path.join(V, 'walkthrough.mp4')
t_wt = xfade_concat(wt, wpath, crf=23)
poster(wpath, (m('vot', 12.0) - m('vot', 2.6)) + sum(b - a for _, a, b in wt[:4]) - 4 * XF, os.path.join(V, 'walkthrough.png'))

# fast (10x) + GIF
os.makedirs(os.path.join(V, 'fast'), exist_ok=True)
fast = os.path.join(V, 'fast', 'walkthrough.mp4')
run(['-i', wpath, '-vf', 'setpts=PTS/10,fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '26', '-g', '300',
     '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an', fast])
gif = os.path.join(V, 'fast', 'walkthrough.gif')
for colors in (128, 96, 64, 48, 32):
    run(['-i', fast, '-vf', f'fps=15,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle', gif])
    if os.path.getsize(gif) <= 2_000_000:
        break

# deck copies (poster as JPEG)
os.makedirs(DECK, exist_ok=True)
shutil.copyfile(fast, os.path.join(DECK, 'walkthrough.mp4'))
run(['-i', os.path.join(V, 'walkthrough.png'), '-q:v', '3', os.path.join(DECK, 'walkthrough.jpg')])

# provenance for the walkthrough
json.dump({
    '_provenance': {**S['_provenance'], 'cut_from': 'full-demo recording (media/scripts/record_full_demo.mjs → make_demo_cuts.py)'},
    'what': 'North Campus engineer sample week, ranked against all observed listings (the Homes default): homes, #1 receipt, compare vs the lowest rent, value of time $8→$20, how sure.',
    'shown': {k: S['shown'].get(k) for k in ('homes', 'receipt', 'compare', 'vot20', 'drawer', 'robustness')},
    'durations_s': {'full-demo': round(t_full, 2), 'full-demo-60s': round(t_hl, 2), 'walkthrough': round(t_wt, 2)},
}, open(os.path.join(V, 'walkthrough.json'), 'w'), indent=1)

for f in ('full-demo.mp4', 'full-demo-60s.mp4', 'walkthrough.mp4', 'fast/walkthrough.mp4', 'fast/walkthrough.gif', 'full-demo.png', 'walkthrough.png'):
    p = os.path.join(V, f)
    extra = f' {dur(p):.2f}s' if f.endswith('.mp4') else ''
    print(f'{f}: {os.path.getsize(p) / 1e6:.2f} MB{extra}')
sys.exit(0)
