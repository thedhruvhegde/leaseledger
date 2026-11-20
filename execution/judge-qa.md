# Judge Q&A prep (final)

Short answers first; the detail is for follow-ups. Numbers are from the live engine (North Campus engineer, 69 observed listings).

## Problem and value
1. **Why not just use Zillow's commute filter?**
   It prices one trip to one place at one time. A student's week is 20–40 trips at different times, to different places, on buses whose frequency changes through the day. For two-anchor weeks (classes plus a job), a single-destination filter picks a different home than the full-week model 60% of the time (95% CI 55–66%).
2. **Who is this for?**
   Any student choosing between a few places, especially students whose week spans North and Central, or classes plus a job. That's also where it changes decisions most.
3. **When does it not matter?**
   If your week has one anchor, a commute filter is usually fine: the pick differs only 8% of the time. We say so on the evidence slide.
4. **What did students tell you?**
   16 interviews. 10 of 16 said it would change their decision. The receipt (10) and map routes (8) were the most useful features. The skeptics are budget-first and car-first students who don't want time priced in dollars. That's why value of time is a slider and $0 is allowed.

## Method
5. **How do you compute travel times?**
   Real UM and AAATA GTFS timetables for this fall, plus the Overture street network. We use the Connection Scan Algorithm: one backward scan per building and 5-minute slot gives the latest departure from every stop, so any home becomes a lookup. A scan takes 0.10 ms.
6. **How do you know routing is correct?**
   Three checks:
   - it matches an independent time-expanded Dijkstra on every test query;
   - 11 of 11 sampled bus legs match the published timetable exactly;
   - trip invariants hold (walk + wait + ride = total; a bus trip is never slower than walking).
7. **Why multiply walking and waiting by 1.75?**
   Transport meta-analyses (e.g. Abrantes & Wardman 2011) find a minute spent walking or waiting feels worse than one on the bus, at somewhat less than the conventional 2×. The range 1.5–2.0 is in the uncertainty analysis, and changing it moves #1 in under 1% of sampled semesters.
8. **Isn't value of time arbitrary?**
   It's the student's choice: a slider, with $0 allowed. The default is half of a $15 wage, the US DOT convention. We show the exact breakeven ("B wins below $15.28/h"), so students see whether their answer depends on it. It is the biggest lever, and we say so.
9. **What does "80 in 100" mean?**
   It's how often this home stays #1 when we redraw everything you're unsure about: next semester's schedule, utility prices, value of time and the weights. It's a stability measure, not the probability that you'll be happy.
10. **Why Monte Carlo and not a single score?**
    The inputs really are uncertain. One number hides whether the ranking is fragile. With 2,000 samples and common random numbers, the standard error is under 1 point.
11. **How are utilities estimated?**
    Heating degree days × heating intensity by building type and age × floor area × the gas price, plus electricity per person. Every input has a low/high range, so the receipt shows a band, not a fake exact number.
12. **How does the roommate split work?**
    We assign rooms to maximise total value, then a linear program sets rents to make the worst-off roommate as well off as possible, subject to nobody preferring someone else's room at its price (Gal, Mash, Procaccia & Zick 2017). We check the envy matrix numerically. It's not strategy-proof, and the app says so.
13. **What's the hardest technical part?**
    Making time-dependent routing fast enough to re-rank a whole week in milliseconds. The answer was precomputing backward scans per building and time slot, so a slider move is just lookups plus arithmetic.

## Data and honesty
14. **Are the listings real?**
    69 come from public listing text captured on Nov 20 and are labelled "observed · search text". Prices may be stale and availability isn't verified. 30 synthetic listings are labelled everywhere. A scraper for property-manager sites (robots.txt-respecting, never Zillow or Apartments.com) is built.
15. **Why not scrape Zillow?**
    Their terms forbid it, and the photos are copyrighted. We use first-party property pages and public timetables.
16. **Where does AI come in?**
    Only to parse your typed week and pasted listing text into structured data. Every extracted item must quote the source text exactly, a rule-based parser cross-checks it, and the app works with AI off. AI never ranks homes or invents numbers.
17. **Privacy?**
    No accounts and no stored profiles. Only schedule or listing text is sent for parsing, with personal details scrubbed. We collect no demographics.
18. **What are the biggest limitations?**
    - Listing data freshness.
    - One representative bus week with no real-time delays.
    - Assumed values (late-night cost, co-op hours) shown with ranges.
    - The other cities are a travel-only simulation.
    - The interviews are a small convenience sample.

## Scale and business
19. **Does this work beyond Ann Arbor?**
    The engine is campus-agnostic: give it GTFS, OpenStreetMap streets and a building list. We ran 28,000 simulated semesters on seven real networks (Austin, UIUC, Princeton, Boston, NYC, San Francisco, Ann Arbor). Closest-to-campus picks a different home 29–51% of the time.
20. **How would you make money?**
    This is a plan, not traction. Options: university off-campus housing offices license it for students, or property managers pay for verified, all-in-priced listings.
21. **What's your moat?**
    Honestly, little today. It would come from per-campus calibrated cost and commute data, verified listings, and the decision engine.
22. **What would you build next?**
    - A "cash + hours" view, the top interview request.
    - Calendar import.
    - Verified availability.
    - Real-time bus reliability.
    - Saved scenarios (semester vs summer).

## Demo
23. **Why did #1 change when you moved the slider?**
    Escher is cheaper in cash but costs more hours a week. Above $15.28/h, the time difference outweighs the rent difference. That's the closed-form breakeven.
24. **The hospital-shift flip wins by only $2. Is that meaningful?**
    It's a near-tie, and we call it that. The point is that the tool shows the student it's a coin flip between two homes, instead of pretending one is clearly better.
25. **What if the site is slow?**
    The demo profiles are pre-computed at startup and answer in under 0.3 s. The deck also has an offline snapshot of every API response.
