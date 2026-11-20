# Competitive Analysis: Hack the Lease (Research Agent C: B3, E3, E6, F3)

Accessed: 2026-11-20 (all URLs below). Method: web search (search-engine snippets plus result pages). **Limitation:** direct page fetches of zillow.com, help.zumper.com and offcampushousing.umich.edu were blocked by this session's network allowlist, so most claims rest on press releases, vendor blogs, news coverage and search snippets, not on hands-on use. Treat every row as **advertised** unless it is marked **demonstrated**. Nothing here was tested hands-on in a live product.

Confidence: **H** = primary or official source plus corroboration; **M** = one primary or reputable secondary source; **L** = snippet only, vendor-only, or dated.

---

## 1. Competitor capability matrix

Legend: Y = present (advertised), P = partial, N = not found, ? = unverified/unknown.

| Product | Problem addressed | Commute / routine modeling | Total-cost modeling | Personalization / NL | Explainability | Uncertainty | Multi-person (roommates) | Coverage | Conf. |
|---|---|---|---|---|---|---|---|---|---|
| **Zillow Rentals** | Listing search | P: commute-time filter, 1 destination, 10–60 min, walk/bike/transit/car, rush-hour vs off-peak; mobile app | P: rent and affordability only | Y: NL search (2023; expanded Sep 2024 with commute, POI, affordability); ChatGPT app (Oct 2025) | N (results sorted the same way as the site) | N | N | US | M |
| **Apartments.com (CoStar)** | Listing search | P: "Plan Your Commute" travel-time search (TravelTime-powered), 1 destination, mode, max time, isochrone | P: per-unit "Cost Calculator" (base rent + required fees + add-ons) | Y: AI Smart Search (Jan 2026), Apartments.com Ai conversational advisor (Jun 16 2026), voice, "community comparisons" | ? | N | N | US | M |
| **Zumper / PadMapper** | Listing search | P: Commute Time filter (one work/school address; drive/bike/transit/walk); PadMapper overlays (dated) | N | P: ChatGPT plug-in (2023) | N | N | N | US/Canada | M (Zumper), L (PadMapper) |
| **HotPads** (Zillow Group) | Map-based listing search | ? (no commute feature found) | N | ? | N | N | N | US | L |
| **Rent.com / RentCafe (Yardi)** | Listing search | ? | ? | Y: "Ren" AI search agent; ChatGPT app for search/compare (RentCafe) | ? | N | N | US | L |
| **Redfin** | Mostly for-sale; some rentals | ? | N | Y: conversational chatbot that asks clarifying questions (2025) | ? | N | N | US | M |
| **brightplace** (startup) | AI rental advisor; agentic search through tour booking | ? | ? | Y (vendor claim) | ? | ? | ? | NYC-first | L |
| **UM Beyond the Diag: offcampushousing.umich.edu** | Official U-M listings + roommate finder (uniqname-gated) | ? (likely distance/map; unverified) | N | N | N | N | P: roommate *finder* (matching people, not joint decision) | Ann Arbor | M |
| **Off Campus Partners** (vendor for many campus sites, part of CoStar; *the U-M vendor is unverified*) | Campus-branded listings | ? | ? | ? | N | N | P: "roommates" (no detail) | Many US campuses | L |
| **College Pads (now StarRez)** | Campus off-campus marketplace (Yale, UTSA, etc.) | ? | ? | ? | N | N | ? | US campuses | M |
| **Places4Students** | Campus listing service | P: map with distance to campus | N | Filters: rate, type, lease period, occupancy date | N | N | ? | Mostly Canada, some US | M |
| **offcampus-universe.com** | Student-run U-M listing/guide site (not affiliated with U-M) | ? | N | ? | Guides | N | ? | U-M | L |
| **Facebook groups** (U-M housing/sublets) | Peer sublets, roommates | N | N | N | Human Q&A | N | Informal | Per campus | L (not verified) |
| **Roomi / SpareRoom / Diggz / Roomsurf** | Roommate matching | N | P: rent split by listing only | Y: lifestyle filters (Diggz: 20+ filters, ranking algorithm) | N | N | Y: pairing people (not apartment choice) | US/UK | L–M (vendor) |
| **Rentgrata** | Prospects chat with current residents | N | N | N | Human testimony | N | N | Partner buildings | M (vendor) |
| **HousingAnywhere / Uniplaces / Student.com / Amber** | Verified mid/long-term student rentals, often international | N | P: booking fees shown | Filters | N | N | P: Uniplaces roommate service | EU/global; Ann Arbor coverage thin (L) | L–M |
| **Walk Score API** | Walk/Transit/Bike score 0–100 | P: static accessibility score, not schedule | N | N | P: published methodology | N | N | US/Canada | H |
| **TravelTime API** | Isochrones, time matrices | Y (building block): multi-origin isochrones, union/intersection server-side, transit, ≤4 h, ≤10 per fast request | N | N/A | N/A | N | N/A | Global | M |
| **Mapbox Isochrone API** | Isochrones | Y (building block): ≤60 min, drive/cycle/walk (no transit), ≤4 contours, 1 origin | N | N/A | N/A | N | N/A | Global | M |
| **CNT H+T Index** | Neighborhood housing + transportation cost share | P: modeled average household, not individual | Y (area-level): 45%-of-income benchmark | N | Y (methodology) | N | N | All US (last update Oct 2022) | H |
| **Generic TCO calculators** (Pearson rent calc, lease-comparison calculators, commute-cost-with-time-value calculators) | Manual cost math | P: manual commute input | Y (manual entry) | N | Formula shown | N | N | Any | L–M |
| **Spliddit (rent division)** | Envy-free room assignment + rent split (maximin, Gal et al. 2017) | N | N | Bids per room | Y: fairness properties explained | N (envy-freeness is fragile; see the Peters et al. 2022 "lexislack" paper) | Y (one apartment) | Global | H (algorithm); status L: one source says it ran 2014–2022 |
| **Homesnap search-by-commute** (homebuyers) | Up to 5 commute destinations | P (multi-destination, no time-of-week) | N | N | N | N | N | US | M (2018) |
| **Walk Score apartment search / Somewhere Ideal** (dated) | Two-person commute balancing / unlimited destinations (neighborhood level) | P | N | N | N | N | P (couples) | US | L (2011/2016; may be defunct) |
| **Devpost hackathon projects** (ZotHomes, CribConnect, Slughousing, Bed-a-thon, UMatch Dorms, CityMate, Roomix, Leasybot…) | Mostly roommate swiping, listing aggregation, AI tour scheduling | N (none found) | N | Preference vectors (Bed-a-thon) | N | N | Roommate *matching* | Single campuses | M |

Sources for the matrix are listed in section 6.

### Demonstrated vs advertised
- **Demonstrated / documented by primary sources:** Zillow commute filter (Zillow newsroom); Apartments.com "Plan Your Commute" and AI launch (Apartments.com blog/press); Walk Score API (official docs); TravelTime and Mapbox limits (official docs); Spliddit algorithm (peer-reviewed papers); CNT H+T (official).
- **Vendor-claim only (L–M):** brightplace agentic search, Diggz/Roomi algorithm quality, Rentgrata's "92% alleviated a concern", Amber listing counts (sources conflict), Apartments.com Ai "rental advisor" depth.
- **Unverified:** current U-M listing vendor/platform (the site exists; vendor not confirmed), whether U-M site shows commute times, HotPads commute filter, Rent.com AI features, Spliddit live status, Facebook group norms.

---

## 2. Do these capabilities already exist?

| Capability | Exists? | Where / form | Gap | Conf. |
|---|---|---|---|---|
| **(a) Schedule-aware weekly commute cost** (several destinations at different times/days, mixed modes, weather) | **Largely no.** Single-destination commute filters are commodity (Zillow, Apartments.com, Zumper, Realtor.com). Multi-destination exists for homebuyers (Homesnap, ≤5) and in dated neighborhood tools (Somewhere Ideal). | No consumer tool found that takes a *weekly timetable* (e.g., MWF 9am North Campus, TTh 2pm Ross, gym 7pm, Kroger Sat), weights trip frequency, or switches modes for weather/winter. TravelTime supports departure times and transit, so it can serve as a building block. | **Genuine whitespace** | M |
| **(b) Total cost of occupancy** (rent + utilities + fees + transport + time value) | **Partially.** Apartments.com Cost Calculator covers rent + fees + add-ons for one unit; generic calculators let you enter numbers by hand; CNT H+T works at area level; commute-time-value calculators exist separately. | Nobody combines listing fees, utility estimates, *routine-derived* transport cost (bus pass vs parking permit vs gas) and the value of time per unit, then ranks listings by it. | **Whitespace in the integration**, not in the arithmetic | M |
| **(c) Group/roommate joint apartment choice + room assignment + fair rent** | **Exists in theory, barely in product.** Spliddit (single apartment, envy-free maximin). Multi-apartment rent division (Procaccia, Schiffer, Zhang, AAAI 2025) formalizes choosing the apartment *and* rooms/rents ("rearrangeable envy-freeness"). Roommate apps match *people*, not group decisions. | No listing platform found that lets a group of 3–5 compare candidate apartments and get a fair room/rent split per candidate. | **Strong whitespace; algorithm available off the shelf** | H (research), M (no product) |
| **(d) Robust / uncertainty-aware ranking** (rent ranges, unknown utilities, commute variance, stale listings) | **No consumer product found.** Accuracy of listings is a known complaint. | Ranking under ranges (e.g., worst case / percentile, rank stability under weight perturbation) is absent. | **Whitespace** | M |
| **(e) Preference elicitation via pairwise comparisons** | Academic only: AHP for apartment choice (Gawlik; Obeidat); Wallenius et al. found a linear value function predicts student apartment choice (size, rent, travel time to university and to a hobby location). Consumer apps use filters, swipes (roommate apps) or NL chat. | No rental tool found that learns trade-off weights from "A or B?" pairs. | **Whitespace; research supports the model** | M |
| **(f) Lease-timing / signing-deadline support** | **Information only.** Ann Arbor's ordinance 8:530 (merged ELO + Right-to-Renew, ORD-24-03, Mar 2024) bars showing/leasing until **210 days** into the current lease (city flyer). Older reports say 70 days, later 150; one petition asks for 240. U-M Law guide: continuing students secure housing Oct–Dec. Guides exist (Michigan Daily, offcampus-universe). | No tool found that turns "when must I sign / when can landlords legally show / sublet timing / renewal deadline" into a personal decision timeline or a sign-now vs wait recommendation. | **Whitespace (Ann Arbor-specific)**. Check the current threshold with the city. | M |

---

## 3. Design patterns for communicating trade-offs to nontechnical users

| Pattern | Evidence / example | Use in our tool |
|---|---|---|
| **Weighted ranking with live sliders + stacked bars** | LineUp (Gratzl et al., IEEE InfoVis 2013 Best Paper): users weight attributes and see stacked-bar scores; slope graphs compare rankings; the paper also notes users can see which attribute changes would move an item's rank. Users solved complex ranking tasks quickly in a qualitative study. | Primary results view: each apartment's score as a stacked bar (cost, commute, space, quiet…), re-ranking live as sliders move. |
| **"Why not this one?" counterfactuals** | Counterfactual explanations are valued for being intuitive and low in cognitive load (arXiv 2409.06916). Counterfactual evaluation of explanations correlated with human judgment in an N=400 study (arXiv 2203.01310). | "Apt B would beat Apt A if rent dropped $80 or if you cared 20% less about walking time." |
| **Pareto frontier / dominated-option pruning** | Standard in multi-criteria decision analysis; no consumer rental example found (unverified). | Show a 2-axis scatter (monthly true cost vs weekly commute hours) and grey out dominated options: "nothing cheaper is also closer." |
| **Scenario toggles** | Common in finance/planning UIs (no specific citation verified). | "Winter mode" (bike→bus), "I get a car", "roommate drops out", "parking permit". |
| **Parallel coordinates** | Powerful, but generally considered hard for novices (unverified for this audience). | Optional "advanced" view only. |
| **Pairwise "this or that" elicitation** | AHP/linear value function literature above. | Onboarding: 6–10 synthetic pairs, then infer weights, show them, and let the user edit. |
| **Transparency vs satisfaction tension** | Visual Why/How explanation study (N=12) found a trade-off between transparency/trust and satisfaction when Why and How explanations are shown together (arXiv 2305.17034). | Keep explanations progressive: one-line reason first, detail on click. |

---

## 4. Defensibility: geographic-specific vs portable

**Ann Arbor / U-M-specific (a moat for a demo, extra data work for scaling):**
- Campus destination graph (Central, North, Medical, Ross, CCRB/IM, Kroger/Meijer) and the U-M bus system (free with Mcard; UM Magic Bus / TheRide AAATA GTFS). Free bus fares change transport-cost math versus most cities. *(Fare detail not verified in this pass.)*
- Ordinance 8:530 leasing timeline (210-day rule per 2024 city flyer) and the Oct–Dec signing culture.
- Winter weather mode-switching (walk/bike penalty Dec–Mar).
- Parking-permit costs, landlord-specific fee patterns, utility norms (DTE).
- Integration with Beyond the Diag listings and the uniqname-gated roommate finder (partnership angle).

**Portable (the product core):**
- Weekly-routine → commute-cost engine (any GTFS + routing API: TravelTime, OSRM/OpenTripPlanner, Mapbox for non-transit).
- Total-cost-of-occupancy model with ranges.
- Pairwise preference elicitation, robust ranking, counterfactual explanations.
- Group decision: multi-apartment envy-free rent division (published polynomial-time algorithms).
- Lease-timeline engine parameterized by city ordinance (East Lansing uses 150 days, so the same engine applies with different parameters).

**Defensibility honestly assessed:** big portals (Zillow, CoStar, Yardi) have the listings and are adding conversational AI fast (2025–2026), so a "chat to find apartments" pitch is **not** differentiated. Their incentive is lead generation, not ranking by true cost or group fairness. The defensible angle is decision support: routine-derived costs, robustness, roommate fairness, and local timing rules, which portals have no clear incentive to build.

---

## 5. Differentiation assessment (summary)

**Done well already (don't compete head-on):** listing inventory and photos/3D tours; single-destination commute filter; natural-language/conversational search (Zillow, Apartments.com Ai, RentCafe Ren, Redfin, ChatGPT apps); verified listings (HousingAnywhere, Amber); roommate *people* matching (Diggz, Roomi, U-M finder); walkability scores (Walk Score); per-unit fee calculator (Apartments.com).

**Genuine whitespace:**
1. Weekly-schedule-aware commute *cost* (time × frequency × mode × weather) turned into dollars and hours per week.
2. True monthly cost per listing that combines fees, utilities, routine-derived transport and time value, shown as ranges.
3. Group decision for 3–5 roommates: which apartment and which room, at what fair rent (multi-apartment envy-free).
4. Robust ranking: "#1 in 87% of plausible scenarios" and rank stability under weight changes.
5. Pairwise elicitation → explicit, editable weights + "why not" counterfactuals.
6. Ann Arbor lease-timing assistant (ordinance-aware signing window, renewal/sublet deadlines).

Prior hackathon projects (Devpost) cluster on roommate swiping and listing aggregation; none found did schedule-aware cost modeling or fair rent division. That makes the whitespace items differentiating for judges too.

---

## 6. Sources (all accessed 2026-11-20)

- Zillow commute filter: https://www.zillow.com/news/zillows-commute-time-filter ; https://www.zillowgroup.com/news/zillows-commute-time-filter ; Inman 2024-06-13 https://inman.com/2024/06/13/time-is-of-the-essence-with-zillows-latest-search-filter
- Zillow NL search Sep 2024: https://www.geekwire.com/2024/zillow-expands-ai-home-search-capabilities-in-tech-race-among-major-real-estate-portals/ ; https://inman.com/2024/09/04/zillow-unfiltered-portal-giant-adds-ai-fueled-natural-language-feature
- Zillow ChatGPT: https://zillow.mediaroom.com/2023-05-02-Zillow-builds-ChatGPT-plugin-for-real-estate-searches ; https://www.housingwire.com/articles/zillow-chatgpt-launch-app-integration/ ; https://www.brickunderground.com/rent/zillow-zumper-redfin-launch-chatgpt-plug-ins-ai-artificial-intelligence-real-estate-searches
- Apartments.com commute: https://apartments.com/blog/how-to-find-an-apartment-with-a-great-commute ; https://traveltime.com/case-study/costar-property-portals
- Apartments.com Ai: https://www.apartments.com/grow/news/apartments-ai-conversational-search-launch ; https://www.businesswire.com/news/home/20260616473542/en/ ; https://www.pymnts.com/news/artificial-intelligence/2026/apartments-com-offers-renters-ai-powered-search-options/
- Zumper commute filter: https://help.zumper.com/hc/en-us/articles/219060588 ; PadMapper (dated): https://news.ycombinator.com/item?id=3060748
- Redfin chatbot: https://www.geekwire.com/2025/redfin-launches-chatbot-providing-conversations-with-home-shoppers-moxiworks-releases-new-platform/
- RentCafe Ren / brightplace: https://commercialobserver.com/2026/04/brightplace-ai-rental-advisor/ ; https://www.multihousingnews.com/ai-and-renter-choice-are-reshaping-the-leasing-agents-job/
- U-M: https://offcampus.umich.edu/article/housing-and-roommate-search ; https://offcampus.umich.edu/ ; https://basicneeds.studentlife.umich.edu/department/ums-beyond-the-diag-off-campus-housing ; https://www.offcampus-universe.com/university/umich
- Off Campus Partners / College Pads / Places4Students: https://offcampuspartners.com/grow/ocp ; https://your.yale.edu/campus-essentials/off-campus-living/yale-university-partners-with-college-pads ; https://brocku.ca/off-campus-living/listing-service/landlords/
- Roommate apps: https://medium.com/diggz/the-new-and-improved-matching-algorithm-279c7ebe1f89 ; https://join.diggz.co/list-a-room-for-rent ; https://www.rentcafe.com/blog/daily-living/10-best-apps-for-finding-a-roommate/
- Rentgrata: https://rentgrata.com/how-it-works
- Student platforms: https://www.uni2study.com/articles/housinganywhere-uniplaces-student-housing-europe ; https://amberstudent.com/how-it-works ; https://beyondthestates.com/best-student-housing-websites/
- Walk Score: https://www.walkscore.com/professional/api.php ; https://www.walkscore.com/methodology.shtml ; https://www.walkscore.com/transit-score-methodology.shtml
- TravelTime: https://docs.traveltime.com/api/reference/isochrones ; https://docs.traveltime.com/api/reference/time-map ; Mapbox: https://docs.mapbox.com/api/navigation/isochrone
- Multi-destination commute (dated): https://www.inman.com/2018/09/13/homesnap-launches-search-by-commute-tool-for-homebuyers/ ; https://www.brickunderground.com/blog/search_for_apartments_by_commute_time ; https://humantransit.org/?p=22027
- TCO calculators: https://www.pearson.com/channels/calculators/rent-calculator ; https://www.redfin.com/blog/how-to-compare-apartments/ ; https://findskill.ai/skills/housing/commute-cost-calculator ; CNT H+T: https://htaindex.cnt.org/about/ ; https://cnt.org/node/1121
- Rent division: https://arxiv.org/pdf/1807.04163.pdf ; https://people.cs.umass.edu/~yzick/papers/rent.ec16.pdf ; https://papers.neurips.cc/paper_files/paper/2022/file/5a1a10c2c2c9b9af1514687bc24b8f3d-Paper-Conference.pdf ; Multi-apartment: https://ojs.aaai.org/index.php/AAAI/article/view/33538 ; https://arxiv.org/abs/2403.08051v1
- Pairwise / AHP: https://ideas.repec.org/a/eee/ejores/v259y2017i1p229-235.html ; https://doaj.org/article/0e5035b996614ffdb81ca2f4924739df ; https://econpapers.repec.org/RePEc:taf:jpropr:v:35:y:2018:i:1:p:53-71
- Leasing timeline: https://a2gov.org/media/lpijxcs2/elo-rtr.pdf ; https://a2gov.org/media/yp5mecxm/ord-24-03-approval-notice.pdf ; https://www.wemu.org/wemu-news/2024-03-06/ann-arbor-city-council-closes-loophole-left-in-rental-ordinances ; https://michigan.law.umich.edu/admitted-students/housing/ann-arbor-housing-market-timeline ; https://www.michigandaily.com/news/ann-arbor/whats-the-deal-with-pre-lease-agreements/
- Trade-off UI: LineUp https://sci.utah.edu/~vdl/papers/2013_infovis_lineup.pdf ; counterfactual https://arxiv.org/pdf/2409.06916 ; https://arxiv.org/pdf/2203.01310v2.pdf ; https://ar5iv.labs.arxiv.org/html/2305.17034
- Devpost: https://devpost.com/software/zothomes ; https://devpost.com/software/cribconnect ; https://devpost.com/software/umatch-dorms ; https://devpost.com/software/citymate-82zugd ; https://devpost.com/software/roomix ; https://devpost.com/software/leasybot
