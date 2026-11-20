"""Animated GIFs for the rapid-fire presentation sequence (offline; matplotlib + Pillow).

    python3 analysis/multicity/gifs.py [city ...]      # writes presentation/media/multicity/*.gif + *_final.png

Style: paper-white canvas, ink-black text, gray hairlines (web/design/DESIGN-reference.md); one muted accent for
"with platform" and gray for "naive". Frames are quantised to one shared adaptive palette without dithering so a
1600x900, 8-10 s GIF stays well under 8 MB.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
RES = REPO / "analysis" / "multicity" / "results"
MEDIA = REPO / "presentation" / "media" / "multicity"
CITY_ORDER = ["annarbor", "austin", "uiuc", "princeton", "boston", "nyc", "sf"]

INK, BODY, MUTE, HAIR, CANVAS = "#000000", "#525252", "#8a8a8a", "#e5e5e5", "#ffffff"
ACCENT = "#2f6496"          # with platform
NAIVE = "#9a9a9a"           # naive rule
W, H, DPI = 16, 9, 100      # 1600 x 900
FPS = 15

for f in Path("/usr/share/fonts/opentype/inter").glob("Inter-*.otf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "Inter", "font.size": 15, "axes.edgecolor": HAIR, "axes.labelcolor": BODY,
                     "xtick.color": BODY, "ytick.color": BODY, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": CANVAS, "axes.facecolor": CANVAS})


def fig_to_img(fig) -> Image.Image:
    fig.canvas.draw()
    return Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())


def save_gif(frames: list[Image.Image], path: Path, fps: int = FPS, hold_last: int = 0) -> None:
    frames = frames + [frames[-1]] * hold_last
    # shared palette from a mosaic of sample frames
    sample = [frames[i] for i in np.linspace(0, len(frames) - 1, 6).astype(int)]
    mosaic = Image.new("RGB", (sample[0].width, sample[0].height * len(sample)))
    for i, s in enumerate(sample):
        mosaic.paste(s, (0, i * s.height))
    pal = mosaic.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=int(1000 / fps), loop=0, optimize=True,
              disposal=1)
    frames[-1].save(path.with_name(path.stem + "_final.png"))
    print(path.name, f"{path.stat().st_size / 1e6:.2f} MB, {len(frames)} frames", flush=True)


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------------------------------------ city GIF
def network_raster(key: str, extent) -> np.ndarray:
    z = np.load(REPO / "data" / "multicity" / key / "model.npz")
    xy = z["g_node_xy"]
    seg = np.stack([xy[z["g_edge_u"]], xy[z["g_edge_v"]]], axis=1)
    f = plt.figure(figsize=(9, 9), dpi=DPI)
    ax = f.add_axes([0, 0, 1, 1])
    ax.add_collection(LineCollection(seg, colors="#bdbdbd", linewidths=0.35))
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3]); ax.set_aspect("equal"); ax.axis("off")
    img = np.asarray(fig_to_img(f)).astype(float) / 255
    plt.close(f)
    return img


def city_gif(key: str, n_frames: int = 135) -> dict:
    r = json.loads((RES / f"{key}.json").read_text())
    F = np.load(RES / f"{key}_futures.npz")
    trips = json.loads((RES / f"{key}_trips.json").read_text())
    T = np.load(REPO / "data" / "multicity" / key / "tables.npz")
    px, py = T["pool_x"], T["pool_y"]
    dx, dy = T["dest_x"], T["dest_y"]
    n = len(F["opt"])
    idx = np.arange(n)
    reg = (F["cost"][idx, F["pick_a"]] - F["cost"][idx, F["opt"]]) / 3600 * 15
    hx = np.concatenate([px, dx])
    hy = np.concatenate([py, dy])
    cx, cy = np.median(hx), np.median(hy)
    half = max(np.ptp(hx), np.ptp(hy)) / 2 * 1.02
    extent = (cx - half, cx + half, cy - half, cy + half)
    net = network_raster(key, extent)
    fa = r["futures"]["a_straight_line"]
    differs = fa["pick_differs"]
    cond = reg[reg > 1e-9]
    cond_med = float(np.median(cond)) if len(cond) else 0.0
    bins = np.linspace(0, max(np.quantile(reg, 0.98), 5), 31)
    hist_max = np.histogram(reg, bins)[0].max() * 1.08
    # schedule: 0-14 network fade; 15-104 stream futures; 105-134 final counter
    n_show = np.concatenate([np.zeros(15), np.round(np.geomspace(1, n, 90)), np.full(n_frames - 105, n)]).astype(int)
    frames = []
    for fi in range(n_frames):
        fig = plt.figure(figsize=(W, H), dpi=DPI)
        axm = fig.add_axes([0.02, 0.04, 0.5, 0.86])
        a = ease(fi / 14)
        axm.imshow(1 - a * (1 - net), extent=extent, origin="upper", interpolation="bilinear")
        axm.set_xlim(extent[0], extent[1]); axm.set_ylim(extent[2], extent[3]); axm.axis("off")
        for ax_, ay_ in T["anchors_xy"]:
            axm.plot(ax_, ay_, marker="*", ms=16, color=INK, zorder=6, alpha=a)
        m = n_show[fi]
        if m > 0:
            k = min(m, 400) - 1
            hs = F["homes"][:min(m, 400)]
            o = hs[np.arange(len(hs)), F["opt"][:len(hs)]]
            na = hs[np.arange(len(hs)), F["pick_a"][:len(hs)]]
            axm.scatter(px[na], py[na], s=9, color=NAIVE, alpha=0.35, lw=0, zorder=3)
            axm.scatter(px[o], py[o], s=9, color=ACCENT, alpha=0.45, lw=0, zorder=4)
            if fi < 105:
                h_o, h_n = F["homes"][k, F["opt"][k]], F["homes"][k, F["pick_a"][k]]
                cand = F["homes"][k]
                axm.scatter(px[cand], py[cand], s=30, facecolor="white", edgecolor=INK, lw=0.8, zorder=5)
                js = sorted({t[1] for t in trips[k]})
                for j in js:
                    axm.plot([px[h_n], dx[j]], [py[h_n], dy[j]], color=NAIVE, lw=1.0, zorder=5)
                    axm.plot([px[h_o], dx[j]], [py[h_o], dy[j]], color=ACCENT, lw=1.6, zorder=6)
                axm.scatter(dx[js], dy[js], s=36, marker="s", color=INK, zorder=7)
                axm.scatter([px[h_n]], [py[h_n]], s=110, color=NAIVE, edgecolor="white", lw=1.5, zorder=8)
                axm.scatter([px[h_o]], [py[h_o]], s=110, color=ACCENT, edgecolor="white", lw=1.5, zorder=9)
        fig.text(0.03, 0.935, f"{r['name']}  ·  {r['campus']}", fontsize=30, weight="medium", color=INK)
        fig.text(0.03, 0.905, f"{r['model']['transit']['connections']:,} weekday connections · "
                              f"{r['model']['graph']['nodes']:,} street nodes · "
                              f"feed service date {', '.join(sorted({fd['service_date'] for fd in r['model']['feeds']}))}",
                 fontsize=13, color=BODY)
        # histogram panel
        axh = fig.add_axes([0.58, 0.40, 0.38, 0.42])
        rr = reg[:m]
        if m:
            cnt, _ = np.histogram(rr, bins)
            axh.bar(bins[:-1], cnt, width=np.diff(bins) * 0.88, align="edge", color=NAIVE, lw=0)
            mu = rr.mean()
            se = rr.std(ddof=1) / np.sqrt(m) if m > 1 else 0
            axh.axvline(mu, color=INK, lw=1.5)
            axh.axvspan(mu - 1.96 * se, mu + 1.96 * se, color=ACCENT, alpha=0.18, lw=0)
            axh.text(mu, hist_max * 0.97, f"  mean {mu:.1f} h  ± {1.96 * se:.1f}", fontsize=14, color=INK, va="top")
        axh.set_xlim(bins[0], bins[-1]); axh.set_ylim(0, hist_max)
        axh.set_xlabel("regret of the straight-line pick, hours / semester (generalized)", fontsize=13)
        axh.set_ylabel("futures", fontsize=13)
        fig.text(0.58, 0.86, f"futures simulated  {m:,}", fontsize=24, color=INK)
        fig.text(0.58, 0.835, "each = 12 random homes + a random semester routine; full-week CSA tours",
                 fontsize=12, color=BODY)
        # legend
        fig.text(0.58, 0.30, "●", color=ACCENT, fontsize=18); fig.text(0.60, 0.302, "with platform: min full-week generalized minutes", fontsize=14, color=INK)
        fig.text(0.58, 0.26, "●", color=NAIVE, fontsize=18); fig.text(0.60, 0.262, "naive: closest to campus (straight line)", fontsize=14, color=INK)
        if fi >= 105:
            b = ease((fi - 105) / 10)
            fig.text(0.58, 0.15, f"pick differs in {100 * differs['p']:.0f}%  "
                                 f"({100 * differs['lo']:.0f}–{100 * differs['hi']:.0f}%)", fontsize=28,
                     color=INK, alpha=b, weight="medium")
            rh = fa["regret_h_semester"]
            fig.text(0.58, 0.095, f"mean regret {rh['mean']:.1f} h/semester ({rh['mean_ci'][0]:.1f}–{rh['mean_ci'][1]:.1f})"
                                  f" · if it differs: median {cond_med:.1f} h", fontsize=15, color=BODY, alpha=b)
            fig.text(0.58, 0.05, f"n = {n:,} futures · travel-only objective · 95% CIs (Wilson / bootstrap)",
                     fontsize=12, color=MUTE, alpha=b)
        frames.append(fig_to_img(fig))
        plt.close(fig)
    save_gif(frames, MEDIA / f"{key}.gif", hold_last=15)
    return {"conditional_median_regret_h_semester_rule_a": cond_med}


# ------------------------------------------------------------------------------------------------ sawtooth
def sawtooth_gif(key: str = "annarbor", n_frames: int = 120) -> None:
    r = json.loads((RES / f"{key}.json").read_text())
    ex = r["tau"]["example"]
    g = np.array(ex["grid_s"]) / 3600
    tau = np.array(ex["tau_min"])
    W_ = ex["walk_min"]
    # densify with exact breakpoints for a crisp sawtooth (t_k jumps)
    tk = np.array(ex["t_k"]) / 3600
    dk = np.array(ex["dep_k"]) / 3600
    o = np.argsort(tk); tk, dk = tk[o], np.maximum.accumulate(dk[o])
    tt = np.sort(np.concatenate([g, tk - 1e-6, tk]))
    tt = tt[(tt >= g[0]) & (tt <= g[-1])]
    pos = np.searchsorted(tk, tt, "right") - 1
    D = np.where(pos >= 0, dk[np.maximum(pos, 0)], -np.inf)
    tau_d = np.minimum(W_, (tt - D) * 60)
    frames = []
    for fi in range(n_frames):
        fig = plt.figure(figsize=(W, H), dpi=DPI)
        ax = fig.add_axes([0.07, 0.14, 0.88, 0.62])
        p = ease(fi / (n_frames - 25))
        tcut = g[0] + p * (g[-1] - g[0])
        m = tt <= tcut
        ax.fill_between(tt[m], 0, tau_d[m], color=ACCENT, alpha=0.16, lw=0)
        ax.plot(tt[m], tau_d[m], color=ACCENT, lw=2)
        ax.axhline(W_, color=NAIVE, lw=1.3, ls=(0, (4, 3)))
        ax.text(g[0] + 0.05, W_ + 1, f"walk only {W_:.0f} min", color=BODY, fontsize=13)
        if m.sum() > 2:
            run = np.trapezoid(tau_d[m], tt[m]) / max(tt[m][-1] - tt[m][0], 1e-9)
            ax.axhline(run, color=INK, lw=1.2)
            ax.text(g[-1], run + 1, rf"$\bar{{\tau}}$ = {run:.1f} min ", ha="right", fontsize=16, color=INK)
        ax.set_xlim(g[0], g[-1]); ax.set_ylim(0, W_ * 1.15)
        ax.set_xticks(np.arange(7, 23, 2)); ax.set_xticklabels([f"{h:02d}:00" for h in range(7, 23, 2)])
        ax.set_xlabel("arrival deadline t (arrive-by)"); ax.set_ylabel("door-to-door minutes τ(t)")
        fig.text(0.07, 0.90, "The price of a rigid timetable", fontsize=30, weight="medium")
        fig.text(0.07, 0.855, f"{r['name']}: one home → {ex['dest_name']}. CSA profile: slope 1 while you wait for the "
                              f"next useful arrival, a drop when it comes (FIFO).", fontsize=14, color=BODY)
        fig.text(0.07, 0.03, r"$\bar\tau = \frac{1}{T}\int_{T_0}^{T_1} \tau(t)\,dt$" +
                 f"   exact over {len(tk)} journeys  ·  mean {ex['mean_min']:.1f} min, sd {ex['sd_min']:.1f} min, "
                 f"best case {tau.min():.1f} min", fontsize=15, color=INK)
        frames.append(fig_to_img(fig)); plt.close(fig)
    save_gif(frames, MEDIA / "sawtooth_profile.gif", hold_last=10)


# ------------------------------------------------------------------------------------------------ isochrone morph
def isochrone_gif(key: str = "boston", n_frames: int = 135) -> None:
    from matplotlib.tri import Triangulation
    from ledger.multicity.csa_cost import NEG, CostScanner
    from ledger.multicity.network import CityModel
    r = json.loads((RES / f"{key}.json").read_text())
    T = np.load(REPO / "data" / "multicity" / key / "tables.npz")
    model = CityModel.load(key)
    NH = len(T["pool_node"])
    # destination = campus class building nearest the anchor
    ax0, ay0 = T["anchors_xy"][0]
    cls = np.flatnonzero(T["dest_kind"] == "class")
    j = cls[np.argmin(np.hypot(T["dest_x"][cls] - ax0, T["dest_y"][cls] - ay0))]
    es, ew = T["acc_stop"][NH + j], T["acc_s"][NH + j].astype(float)
    sc = CostScanner(model.tt)
    times = np.arange(6 * 60, 25 * 60 + 1, 30)
    acc_stop, acc_s = T["acc_stop"][:NH], T["acc_s"][:NH].astype(float)
    walk = T["walk_s"][j, :NH].astype(float)
    surf = []
    for t in times:
        LV, _ = sc.backward(es, ew, int(t * 60))
        valid = acc_stop >= 0
        lv = np.where(valid, LV[np.maximum(acc_stop, 0)], NEG)
        dep = np.where(lv > NEG, lv - np.rint(np.where(valid, acc_s, 0)).astype(np.int64), NEG).max(axis=1)
        dep = np.maximum(dep, t * 60 - np.rint(walk))
        surf.append((t * 60 - dep) / 60)
    surf = np.array(surf)
    x, y = T["pool_x"], T["pool_y"]
    tri = Triangulation(x, y)
    e = tri.edges
    L = np.hypot(x[tri.triangles] - np.roll(x[tri.triangles], 1, 1), y[tri.triangles] - np.roll(y[tri.triangles], 1, 1))
    tri.set_mask(L.max(axis=1) > 900)
    levels = [0, 10, 20, 30, 40, 50, 60, 90]
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("acc", ["#16385a", ACCENT, "#9fbbd6", "#eef3f8"])
    A = np.load(RES / f"{key}_futures.npz")  # noqa: F841  (kept for parity with other gifs)
    frames = []
    for fi in range(n_frames):
        s = fi / (n_frames - 1) * (len(times) - 1)
        i0 = int(np.floor(s)); i1 = min(i0 + 1, len(times) - 1); w = s - i0
        Z = (1 - w) * surf[i0] + w * surf[i1]
        tnow = (1 - w) * times[i0] + w * times[i1]
        fig = plt.figure(figsize=(W, H), dpi=DPI)
        ax = fig.add_axes([0.02, 0.03, 0.56, 0.86])
        ax.tricontourf(tri, np.minimum(Z, 89.9), levels=levels, cmap=cmap)
        ax.plot(T["dest_x"][j], T["dest_y"][j], marker="*", ms=18, color=INK)
        ax.set_aspect("equal"); ax.axis("off")
        fig.text(0.03, 0.93, f"{r['name']}: minutes to {T['dest_name'][j]}", fontsize=28, weight="medium")
        fig.text(0.03, 0.90, "door-to-door, arrive-by the deadline, best of walk and transit (exact CSA per deadline)",
                 fontsize=13, color=BODY)
        hh, mm = divmod(int(round(tnow)), 60)
        fig.text(0.62, 0.78, f"arrive by {hh % 24:02d}:{mm:02d}", fontsize=40, color=INK)
        axb = fig.add_axes([0.62, 0.35, 0.33, 0.33])
        th = np.arange(0, 61)
        axb.plot(th, (Z[None, :] <= th[:, None]).mean(axis=1), color=ACCENT, lw=2.2)
        axb.plot(th, (surf.min(axis=0)[None, :] <= th[:, None]).mean(axis=1), color=NAIVE, lw=1.2, ls=(0, (4, 3)))
        axb.set_xlim(0, 60); axb.set_ylim(0, 1)
        axb.set_xlabel("θ (minutes)"); axb.set_ylabel("share of homes within θ")
        axb.text(1, 0.93, "A(θ) now", color=ACCENT, fontsize=13); axb.text(1, 0.84, "best time of day", color=MUTE, fontsize=13)
        axl = fig.add_axes([0.62, 0.19, 0.33, 0.035])
        for k in range(len(levels) - 1):
            axl.add_patch(matplotlib.patches.Rectangle((k, 0), 0.92, 1, color=cmap(k / (len(levels) - 2))))
            axl.text(k + 0.46, -0.35, f"{levels[k]}–{levels[k + 1]}", ha="center", va="top", fontsize=11, color=BODY)
        axl.set_xlim(0, len(levels) - 1); axl.set_ylim(0, 1); axl.axis("off")
        fig.text(0.62, 0.10, r"cumulative opportunities $A_i(\theta)=\sum_j \mathbf{1}[c_{ij}\leq\theta]$", fontsize=15)
        frames.append(fig_to_img(fig)); plt.close(fig)
    save_gif(frames, MEDIA / "isochrone_morph.gif", hold_last=10)


# ------------------------------------------------------------------------------------------------ EVPI bars
def load_all():
    return {c: json.loads((RES / f"{c}.json").read_text()) for c in CITY_ORDER if (RES / f"{c}.json").exists()}


def evpi_gif(n_frames: int = 110) -> None:
    R = load_all()
    cs = list(R)
    v = np.array([R[c]["evpi_cvar"]["evpi_h_semester"]["mean"] for c in cs])
    lo = np.array([R[c]["evpi_cvar"]["evpi_h_semester"]["mean_ci"][0] for c in cs])
    hi = np.array([R[c]["evpi_cvar"]["evpi_h_semester"]["mean_ci"][1] for c in cs])
    usd = np.array([R[c]["evpi_cvar"]["evpi_usd_semester"]["mean"] for c in cs])
    frames = []
    for fi in range(n_frames):
        fig = plt.figure(figsize=(W, H), dpi=DPI)
        ax = fig.add_axes([0.2, 0.12, 0.72, 0.66])
        p = ease(fi / 60)
        y = np.arange(len(cs))[::-1]
        ax.barh(y, v * p, height=0.56, color=ACCENT)
        if fi > 60:
            b = ease((fi - 60) / 15)
            ax.errorbar(v, y, xerr=[v - lo, hi - v], fmt="none", ecolor=INK, elinewidth=1.2, capsize=4, alpha=b)
            for yi, vv, hh, uu in zip(y, v, hi, usd):
                ax.text(hh + 0.15, yi, f"{vv:.1f} h  (${uu:.0f})", va="center", fontsize=14, alpha=b)
        ax.set_yticks(y); ax.set_yticklabels([R[c]["name"] for c in cs], fontsize=16)
        ax.set_xlim(0, hi.max() * 1.35)
        ax.set_xlabel("EVPI, hours per semester (generalized)")
        ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
        fig.text(0.05, 0.9, "What is knowing next semester's schedule worth?", fontsize=30, weight="medium")
        fig.text(0.05, 0.855, r"EVPI $= \min_h \mathbb{E}_s[C(h,s)] - \mathbb{E}_s[\min_h C(h,s)]$"
                              "   ·   same student (campus, job, gym) · 128 semesters × 12 homes × 300 students per city",
                 fontsize=14, color=BODY)
        fig.text(0.05, 0.012, "small EVPI ⇒ sign with confidence on the model's pick; it is robust to schedule churn",
                 fontsize=14, color=MUTE)
        frames.append(fig_to_img(fig)); plt.close(fig)
    save_gif(frames, MEDIA / "evpi_bars.gif", hold_last=10)


def finale_gif(n_frames: int = 135) -> None:
    R = load_all()
    cs = list(R)
    pa = np.array([R[c]["futures"]["a_straight_line"]["pick_differs"]["p"] for c in cs]) * 100
    plo = np.array([R[c]["futures"]["a_straight_line"]["pick_differs"]["lo"] for c in cs]) * 100
    phi = np.array([R[c]["futures"]["a_straight_line"]["pick_differs"]["hi"] for c in cs]) * 100
    rm = np.array([R[c]["futures"]["a_straight_line"]["regret_h_semester"]["mean"] for c in cs])
    rlo = np.array([R[c]["futures"]["a_straight_line"]["regret_h_semester"]["mean_ci"][0] for c in cs])
    rhi = np.array([R[c]["futures"]["a_straight_line"]["regret_h_semester"]["mean_ci"][1] for c in cs])
    total = sum(R[c]["futures"]["n_futures"] + R[c]["futures_near_campus"]["n_futures"] for c in cs)
    frames = []
    for fi in range(n_frames):
        fig = plt.figure(figsize=(W, H), dpi=DPI)
        p = ease(fi / 70)
        y = np.arange(len(cs))[::-1]
        ax1 = fig.add_axes([0.16, 0.12, 0.36, 0.62])
        ax2 = fig.add_axes([0.6, 0.12, 0.36, 0.62])
        ax1.barh(y, pa * p, height=0.56, color=ACCENT)
        ax2.barh(y, rm * p, height=0.56, color=ACCENT)
        if fi > 70:
            b = ease((fi - 70) / 15)
            ax1.errorbar(pa, y, xerr=[pa - plo, phi - pa], fmt="none", ecolor=INK, capsize=4, alpha=b)
            ax2.errorbar(rm, y, xerr=[rm - rlo, rhi - rm], fmt="none", ecolor=INK, capsize=4, alpha=b)
            for yi, a, r_ in zip(y, pa, rm):
                ax1.text(2, yi, f"{a:.0f}%", va="center", color="white", fontsize=14, alpha=b, weight="medium")
                ax2.text(0.3, yi, f"{r_:.1f} h", va="center", color="white", fontsize=14, alpha=b, weight="medium")
        ax1.set_yticks(y); ax1.set_yticklabels([R[c]["name"] for c in cs], fontsize=16)
        ax2.set_yticks(y); ax2.set_yticklabels([])
        ax1.set_xlim(0, 100); ax2.set_xlim(0, rhi.max() * 1.15)
        for a_ in (ax1, ax2):
            a_.spines["left"].set_visible(False); a_.tick_params(axis="y", length=0)
        ax1.set_xlabel("naive pick ≠ full-week optimum (%)")
        ax2.set_xlabel("mean regret, hours / semester")
        cnt = int(total * ease(fi / 50))
        fig.text(0.05, 0.9, f"{cnt:,} simulated student-semesters · 7 transit networks", fontsize=30, weight="medium")
        fig.text(0.05, 0.855, "naive rule = closest home to campus (straight line); platform = min full-week generalized "
                              "minutes (real GTFS timetables, CSA, day tours)", fontsize=14, color=BODY)
        fig.text(0.05, 0.012, "bars: study-area futures (2,000/city; total incl. 2,000/city near-campus shortlist). 95% CIs: Wilson (shares), bootstrap 10k (means). Travel-only objective.",
                 fontsize=13, color=MUTE)
        frames.append(fig_to_img(fig)); plt.close(fig)
    save_gif(frames, MEDIA / "finale_all_cities.gif", hold_last=15)


if __name__ == "__main__":
    MEDIA.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:] or CITY_ORDER + ["sawtooth", "isochrone", "evpi", "finale"]
    extra = {}
    for a in args:
        if a in CITY_ORDER:
            extra[a] = city_gif(a)
        elif a == "sawtooth":
            sawtooth_gif()
        elif a == "isochrone":
            isochrone_gif()
        elif a == "evpi":
            evpi_gif()
        elif a == "finale":
            finale_gif()
    if extra:
        p = RES / "gif_extras.json"
        old = json.loads(p.read_text()) if p.exists() else {}
        old.update(extra)
        p.write_text(json.dumps(old, indent=1))
