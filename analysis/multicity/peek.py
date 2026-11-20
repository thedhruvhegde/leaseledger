"""Quick console summary of analysis/multicity/results/*.json."""
import json, sys
from pathlib import Path
R = Path(__file__).parent / "results"
for c in sys.argv[1:] or ["annarbor", "austin", "uiuc", "princeton", "boston", "nyc", "sf"]:
    p = R / f"{c}.json"
    if not p.exists():
        continue
    r = json.loads(p.read_text())
    f, g = r["futures"], r["futures_near_campus"]
    print(c, "best wk gen min median", round(f["best_weekly_gen_min"]["median"]), r["timings"])
    for k in ["a_straight_line", "b_walk_to_top_dest", "c_transit_9am_top_dest"]:
        print("  ", k[:10], "differ %.2f" % f[k]["pick_differs"]["p"], "reg h mean %.1f med %.1f p90 %.1f" % (
            f[k]["regret_h_semester"]["mean"], f[k]["regret_h_semester"]["median"], f[k]["regret_h_semester"]["p90"]),
              "tau %.2f" % f[k]["kendall_tau"]["mean"],
              "| near: differ %.2f mean %.1f" % (g[k]["pick_differs"]["p"], g[k]["regret_h_semester"]["mean"]))
    e = r["evpi_cvar"]
    print("   evpi h %.2f (%.1f%%)" % (e["evpi_h_semester"]["mean"], 100 * e["evpi_share_of_expected_cost"]["mean"]),
          "cvar!=mean %.2f" % e["cvar_optimal_differs_from_mean_optimal"]["p"])
    t = r["tau"]
    print("   tau_bar %.1f sd %.1f rigidity %.1f transit-share %.2f ex %s" % (t["tau_bar_min"]["mean"], t["tau_sd_over_day_min"]["mean"],
          t["rigidity_price_min"]["mean"], t["share_pairs_with_transit_journeys"], t["example"] is not None))
    q = r["qmc"]
    print("   qmc slopes cost mc %.2f qmc %.2f | regret mc %.2f qmc %.2f" % (q["mc"]["slope_mean_cost_home0"], q["qmc"]["slope_mean_cost_home0"],
          q["mc"]["slope_mean_regret_a"], q["qmc"]["slope_mean_regret_a"]))
    reg = r["regression"]["a"]
    print("   OLS a r2 %.3f" % reg["r2"], {k: round(v, 2) for k, v in reg["t_hc3"].items()})
    print("   access A30 median", r["accessibility"]["cum_share_30min"]["median"], "opt-naive_a", round(r["accessibility"]["A30_opt_minus_naive_a"]["mean"], 3))
