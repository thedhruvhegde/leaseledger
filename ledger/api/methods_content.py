"""Curated equations + limitations for GET /api/methods (KaTeX-compatible LaTeX).

Each equation is written to match what the code computes (module named in `source`), not an idealised version.
Symbols with default values are the point values in data/behavior/params.json + data/costs/cost_params.json as
loaded by ledger.engine.load_params(); `meaning` says where they come from. Keep in sync with
ledger/engine/README.md (tests/api/test_methods_equations.py checks shape and KaTeX-safe syntax).
"""
from __future__ import annotations

EQUATIONS: list[dict] = [
    {
        "id": "generalized_trip_cost",
        "title": "Generalized trip cost (component-priced)",
        "source": "ledger/engine/valuation.py: trip_components, Multipliers",
        "latex": r"G = m_{\mathrm{ivt}}\,t_{\mathrm{ivt}} + w(M)\left(m_{\mathrm{walk}}\,t_{\mathrm{walk}}"
                 r" + m_{\mathrm{wait}}\,t_{\mathrm{wait}} + m_{\mathrm{bike}}\,t_{\mathrm{bike}}\right)"
                 r" + \pi_{\mathrm{xfer}}\,n_{\mathrm{xfer}} + m_{\mathrm{sde}}\,t_{\mathrm{early}},"
                 r"\qquad t_{\mathrm{early}} = \max\!\left(0,\ \tau - (a_{\mathrm{last\,bus}} + t_{\mathrm{walk\,after}})\right),"
                 r"\quad t_{\mathrm{wait}} = \max\!\left(0,\ T - t_{\mathrm{walk}} - t_{\mathrm{ivt}} - t_{\mathrm{bike}} - t_{\mathrm{early}}\right)",
        "meaning": "Minutes of one timetable trip turned into in-vehicle-equivalent minutes. m_ivt = 1, m_walk = m_wait = "
                   "1.75 (plausible 1.5-2.0; Wardman 2004, Small & Verhoef 2007), m_bike = 1.0 (assumed), transfer "
                   "penalty pi = 10 min per transfer, schedule-delay-early m_sde = 0.5 (Small 1982). tau = the arrive-by "
                   "deadline (event start - 5 min buffer); early arrival is only computed for arrive-by bus trips "
                   "(depart-at trips home have t_early = 0). T = door-to-door minutes. The headway rule "
                   "(wait = h/2 if headway <= 10 min) applies only when a provider reports headways; the real GTFS "
                   "provider does not, so slack before a bus counts as waiting/early arrival as above.",
    },
    {
        "id": "weather_factor",
        "title": "Weather factor on outdoor minutes",
        "source": "ledger/engine/valuation.py: weather_walk_multiplier",
        "latex": r"w(M) = 1 + \alpha\,(b - 1)\,\frac{1}{|M|}\sum_{m \in M} \frac{\mathrm{SnowDays}_m}{\mathrm{Days}_m}",
        "meaning": "Expected multiplier on walking, waiting and cycling minutes. b = 1.3 on a snow-covered day "
                   "(estimated, 1.1-1.7), alpha = Profile.winter_aversion (default 1), SnowDays from NOAA 1991-2020 "
                   "normals (Ann Arbor, snow depth >= 1 in). M = {Profile.month} if set, else the season's months.",
    },
    {
        "id": "value_of_time",
        "title": "Value of time",
        "source": "ledger/engine/valuation.py: value_of_time",
        "latex": r"v = \begin{cases} v_{\mathrm{user}} & \text{if entered} \\ f \cdot \mathrm{wage} & \text{otherwise} \end{cases}"
                 r"\qquad f = 0.5,\ \ \mathrm{wage} = \mathrm{Profile.hourly\_wage}\ \text{or}\ \$15/\mathrm{h}"
                 r"\ \Rightarrow\ v = \$7.50/\mathrm{h};\qquad v \in [\,0.5v,\ 2v\,]\ \text{unless declared}",
        "meaning": "USDOT (2016) guidance values personal local travel at 50% of hourly income (range 35-60%). The "
                   "$15/h default wage is a student-wage assumption. The interval is used by robustness (log-uniform) "
                   "and the ledger's low/high band.",
    },
    {
        "id": "day_tour",
        "title": "Day-tour rule (home vs direct between events)",
        "source": "ledger/engine/tours.py: day_tour",
        "latex": r"G_{\mathrm{day}} = G(H \to e_1) + \sum_{i:\,p_i \neq p_{i+1}} \min\!\Big\{ G(e_i \to e_{i+1}),\ "
                 r"\underbrace{G(e_i \to H) + G(H \to e_{i+1})}_{\text{only if } s_{i+1}-f_i \ge 30 \text{ and } \ge 30 \text{ min at home}} \Big\}"
                 r" + G(e_n \to H),\qquad G_{\mathrm{week}} = \sum_{d} G_{\mathrm{day}}(d)",
        "meaning": "Events of a day sorted by start s_i (end f_i, place p_i). Inbound legs are arrive-by queries "
                   "(start - 5 min), returns are depart-at queries at the event end. Consecutive events in the same "
                   "place need no trip. Going home is chosen only when cheaper in generalized minutes (home_return "
                   "'auto'; 'never'/'always' override). Time at home or inside a building is not a cost.",
    },
    {
        "id": "monthly_ledger",
        "title": "Monthly ledger and all-in total (per person)",
        "source": "ledger/engine/ledger.py: build_ledger",
        "latex": r"\begin{aligned} \mathrm{cash} &= \mathrm{rent}_{pp} + \mathrm{fees}_{pp} + U + \mathrm{parking} + \mathrm{insurance} + \mathrm{fares} - \mathrm{food}\\"
                 r" \text{all-in} &= \mathrm{cash} + \underbrace{v\,\tfrac{G_{\mathrm{week}}}{60}\,\omega}_{\text{travel time}}"
                 r" + \underbrace{c_{n}\,\lambda\,N_{22}\,\omega}_{\text{late night}} + \underbrace{v\,h_{\mathrm{coop}}\,\omega}_{\text{co-op work}}\\"
                 r" \mathrm{score} &= \text{all-in} + \$40 \textstyle\sum_k \iota_k (1 - \mathrm{has}_k) \end{aligned}",
        "meaning": "omega = 4.348 weeks/month. rent_pp = rent (per-bed) or rent / max(household, bedrooms) (whole unit; "
                   "all bedrooms assumed filled). Fees monthly-ized (once / lease term, annual / 12, per-unit / "
                   "occupants). fares = 0 (Blue Bus free; TheRide free with MCard). food = $250 grocery offset when "
                   "board is included (assumed). N_22 = weekly walking/waiting minutes outdoors 22:00-06:00, "
                   "c_n = $0.10/min (assumed), lambda = Profile.late_night_weight. h_coop = listing's work hours or "
                   "4 h/wk for co-ops (assumed). The ranking key is score (lower is better); no other weights.",
    },
    {
        "id": "utilities_heating",
        "title": "Utilities: seasonal heating model",
        "source": "ledger/engine/utilities.py: coefficients, estimate",
        "latex": r"\begin{aligned} \mathrm{therms} &= \overline{\mathrm{HDD}}(M)\cdot I_{\mathrm{class}}\cdot \tfrac{\mathrm{sqft}}{1000}"
                 r"\qquad \mathrm{heat} = \begin{cases} \mathrm{therms}\cdot p_{\mathrm{gas}} / n & \text{gas / unknown}\\"
                 r" \mathrm{therms}\cdot \eta\cdot 29.307 / \mathrm{COP}\cdot p_{\mathrm{el}} / n & \text{electric}\\"
                 r" 0 & \text{included, steam, tower} \end{cases}\\"
                 r" U &= \mathrm{heat} + k_{\mathrm{base}}\,p_{\mathrm{el}} + \mathrm{internet}/n + \mathrm{water} \end{aligned}",
        "meaning": "Per person per month. HDD = NOAA monthly heating degree days (base 65F) averaged over M; I = "
                   "therms/HDD/1000 sqft by building type and age band (assumed bands; unknown year spans all house "
                   "bands); sqft defaults to 375/bedroom. n = occupants. eta = 0.8 furnace efficiency, COP = 1 "
                   "(resistance) or 2.5 (heat pump). k_base = 180 kWh/person, p_el = $0.22/kWh, p_gas = $1.10/therm, "
                   "internet $55/unit, water/sewer/trash $30/person. Included utilities are 0. The band is exact: "
                   "U is monotone in every input, so all-low and all-high inputs give the interval.",
    },
    {
        "id": "breakeven",
        "title": "Breakevens (closed form)",
        "source": "ledger/engine/breakevens.py",
        "latex": r"\mathrm{score}_i = K_i + v\,T_i,\ \ T_i = \left(\tfrac{G_{\mathrm{week},i}}{60} + h_{\mathrm{coop},i}\right)\omega"
                 r"\ \Rightarrow\ v^{*} = \frac{K_b - K_a}{T_a - T_b};\qquad"
                 r" m^{*} = \frac{K'_b - K'_a}{U_a - U_b};\qquad \mathrm{rent}_b^{*} = \mathrm{rent}_b + \mathrm{score}_a - \mathrm{score}_b",
        "meaning": "Exact because tour choices are fixed at baseline multipliers and do not depend on v or prices. "
                   "m multiplies all utility prices at once (K' = score - U). A tie outside v in [0, $100/h], "
                   "m in [0, 3x], or at rent <= 0 is reported as 'never'.",
    },
    {
        "id": "monte_carlo",
        "title": "Monte Carlo robustness estimator",
        "source": "ledger/engine/robustness.py",
        "latex": r"\hat p_\ell = \frac{1}{S}\sum_{s=1}^{S} \mathbf{1}\!\left[\ell = \arg\min_j \mathrm{score}_j(\theta_s)\right],"
                 r"\qquad \mathrm{SE} = \max_\ell \sqrt{\frac{\hat p_\ell(1-\hat p_\ell)}{S}},"
                 r"\qquad \mathrm{score}_{s\ell} = F_\ell + U_{s\ell} + \tfrac{v_s}{60}\,\omega\, C_{k_s \ell}\cdot \mathbf{m}_s"
                 r" + c_{n,s}\lambda\omega N_{k_s\ell} + v_s\,\omega\, h_{s\ell} - \mathrm{food}_{s\ell}",
        "meaning": "S = 2000 seeded draws theta_s of declared inputs only: v log-uniform on its range; walk/wait/bike/"
                   "transfer/early weights, bad-day multiplier, late-night $/min, utility prices, heating-intensity "
                   "quantile, co-op hours and grocery offset uniform on their bands; month uniform in season; one "
                   "schedule alternative per template slot (k_s). Common random numbers: every home gets the same "
                   "draw. C = weekly (ivt, walk, wait, bike, transfers, early) vector (tours not re-optimised per draw). "
                   "Ranks break ties stably. Drivers = one-factor-at-a-time flip rates over S/4 draws.",
    },
    {
        "id": "envy_free_lp",
        "title": "Envy-free maximin rent split (Gal et al. 2016)",
        "source": "ledger/engine/group.py",
        "latex": r"\begin{aligned} &\sigma = \arg\max_\sigma \textstyle\sum_p W_{p\sigma(p)},\qquad W_{pr} = V_{pr} - c_p\\"
                 r" &\max_{u,\pi}\ u \ \ \text{s.t.}\ \ W_{p\sigma(p)} - \pi_{\sigma(p)} \ge u,\ \ "
                 r"W_{p\sigma(p)} - \pi_{\sigma(p)} \ge W_{p\sigma(q)} - \pi_{\sigma(q)}\ \ \forall p,q,\ \ "
                 r"\textstyle\sum_r \pi_r = R,\ \ \pi_{\sigma(p)} \le \mathrm{cap}_p \end{aligned}",
        "meaning": "c_p = member p's own monthly travel + late-night cost from this home. V_pr = given room values or "
                   "cap_p + $75 private bath + $1/sqft vs the mean room (assumed). Welfare-maximising assignment "
                   "(Hungarian) is required for envy-free prices (Svensson 1983). HiGHS LP; if caps make it "
                   "infeasible, a slack LP finds the minimal total budget increase ('closest-to-fair'). Envy "
                   "verified <= 1e-6. Homes ranked by maximin utility.",
    },
    {
        "id": "csa_backward",
        "title": "Connection Scan, backward (latest departure) recurrence",
        "source": "ledger/pipeline/csa.py: _backward_py, Timetable.backward",
        "latex": r"\begin{aligned} &LA[s] \leftarrow \tau - \mathrm{walk}(s \to D)\ \ \text{(stops near } D),\qquad LV, LA \leftarrow -\infty\ \text{elsewhere}\\"
                 r" &\text{for } c = (u \to x,\ d_c, a_c, \mathrm{trip}_c) \text{ by decreasing } d_c \text{ with } a_c \le \tau:\\"
                 r" &\quad \mathrm{ok}[\mathrm{trip}_c] \mathrel{|}= \left(a_c \le LA[x]\right);\ \ \text{if } \mathrm{ok}[\mathrm{trip}_c]:"
                 r"\ LV[u] \leftarrow \max(LV[u], d_c),\ \ LA[u] \leftarrow \max(LA[u], LV[u] - \mathrm{xfer}_u),\\"
                 r" &\qquad LA[w] \leftarrow \max(LA[w], LV[u] - \mathrm{fp}(w \to u))\ \ \forall w \to u\\"
                 r" &\mathrm{depart}(O) = \max_{s \text{ near } O}\ \left(LV[s] - \mathrm{walk}(O \to s)\right) \end{aligned}",
        "meaning": "LV[s] = latest time one can board at stop s and still reach destination D by deadline tau; "
                   "LA[s] = latest vehicle arrival at s that still works. Footpaths (<= 300 m) are relaxed only from "
                   "vehicle labels (no chained walks); pickup/drop-off flags are respected. One scan per campus "
                   "building x day type x 5-min slot (06:00-26:30) is precomputed, so every listing is answered from "
                   "the same labels. The trip is then compared with walking (and biking if allowed): arrive-by "
                   "returns the latest-leaving option, each transfer counted as 2 min.",
    },
]

LIMITATIONS: list[str] = [
    "Transit times come from a representative service week of the fall-2026 GTFS feeds (UM Blue Bus + AAATA TheRide), "
    "not real-time data; holidays, detours and special schedules are not modelled.",
    "No bus delays or ride-time variability (no AVL data): a fixed 5-minute arrival buffer stands in for reliability.",
    "Observed listing prices come from search-result text (verification 'search_extract'), not verified listing pages; "
    "prices, fees and availability can differ from the landlord's current offer.",
    "Utility amounts are model estimates (heating intensity bands, default square footage, typical prices), shown as "
    "bands; they are not bills.",
    "Value of time (50% of wage, $15/h default wage) and the late-night cost ($0.10 per outdoor minute) are assumptions; "
    "the breakeven panel shows where they would change the answer.",
    "Co-op work hours are assumed (4 h/wk, range 3-6) when a listing does not state them, and meals are offset with an "
    "assumed $250/mo grocery spend.",
    "Synthetic listings (ids starting with syn-) are fictional examples, labeled 'synthetic' everywhere they appear.",
    "The roommate split is envy-free for the stated room values but not strategy-proof: members could misreport "
    "values (Dufton & Larson 2011).",
    "The AI schedule/listing parsers were evaluated on a small synthetic set (18 + 6 held-out schedules, 8 + 3 listing "
    "texts; ledger/ai/EVAL.md), so scores are noisy; every parsed event is shown with its source quote to confirm.",
    "The weekly routine is assumed to hold every week of the month (4.348 weeks); breaks and exam weeks are not "
    "discounted, and Monte Carlo does not re-optimise day tours per draw.",
]
