# Lease Ledger: what a home really costs your week

*A project for Hack the Lease (University of Michigan, Nov 19–20, 2026). I'd love your honest feedback; questions are at the end.*

## The problem

When you look for housing in Ann Arbor, every site shows you roughly the same things: rent, bedrooms, a few photos, and maybe "12 minutes to campus." Then you sign a lease and live a completely different week from the one the listing assumed. You have an 8:30 lecture on North Campus, a lab in GG Brown, a shift in Kerrytown on Saturdays, and you study at the UgLi until midnight. The apartment that looked cheapest can quietly cost you hours every week on buses and walking, plus utilities and fees nobody mentioned.

Research backs this up. People with long commutes report lower life satisfaction and don't get compensated for it (the "commuting paradox"), and a 2024 study found commute time hurts first-year GPA. Locally, the most-documented renter complaints in Ann Arbor are hidden fees and winter utility bills in old houses.

So the question Lease Ledger answers is simple: **which home is cheapest for the week you actually live, not just by rent?**

## What it does

You describe your week in plain English ("MWF 9–10:30 EECS, TTh 2:30 Ross, UgLi till 1am, work Kerrytown Sat 10–4"), or drag blocks onto a weekly calendar. You set a budget, how many people you're living with, and how you get around (walk, bus, bike).

Lease Ledger then does this for every candidate home:

1. **Routes every trip in your week** using this fall's real University of Michigan and AAATA (TheRide) bus timetables and the actual street network, at the actual time of day you travel. It chains a day's events together the way you'd really move (class to class, home only when there's a real gap).
2. **Prices your time.** Walking and waiting count more than sitting on a bus (that's what transportation research finds), winter walking counts extra based on Ann Arbor's snow-cover days, and you choose what an hour of your time is worth (the default is half a typical student wage).
3. **Builds a monthly receipt:** rent per person, fees, estimated utilities (with a low–high range), parking, the value of your travel time, late-night walking, and for co-ops, meals included and required work shifts. Each line shows where it came from (observed, estimated, assumed).
4. **Ranks the homes by all-in cost** and shows them on a map, with your real bus routes drawn in.

Example: for a North Campus engineering student, the listing with the **lowest rent ($666/mo)** comes out at **$1,634/mo all-in** once their week is counted. The top pick costs **$1,166/mo all-in**. Lowest rent isn't the cheapest week.

## The parts that make it trustworthy

- **Change one thing, watch the answer move.** Move a class, switch to winter, or change what your time is worth, and the ranking updates instantly, with an explanation of exactly which trips changed and why.
- **Breakevens.** "Home B beats Home A if your time is worth less than $15.28/hour." No guessing what drives the decision.
- **"How sure are we?"** You don't know next semester's schedule, your utility bills, or exactly what your time is worth. It replays your choice across 2,000 plausible semesters and tells you how often each home comes out on top (e.g., "1,325 of 2,000").
- **Roommates (Group Week).** Each roommate enters their own week and budget. It picks the apartment that's best for the worst-off roommate and splits rent so nobody would rather swap their room-and-rent with anyone else (an "envy-free" split, from published fair-division research).
- **Add a listing.** Paste a listing's text; it pulls out rent, fees, utilities and deposit, quoting the exact words it used, and flags things worth checking (like an application fee above Ann Arbor's $50 cap).

## What I tested

- The bus routing matches an independent algorithm exactly on every test case, and every bus trip I spot-checked matches the official timetable to the minute.
- On 2,400 simulated student semesters with real Ann Arbor listings: if your week has **one** main place you go, a simple "distance to campus" filter usually picks the same home. If your week has **two** anchors (say classes plus a job across town), the simple filter picks the wrong home **about 60% of the time**.
- I ran 28,000 simulated semesters across seven cities' real transit systems (Ann Arbor, Austin, UIUC, Princeton, Boston, NYC, San Francisco); "closest to campus" picks a different home than the full-week model 29–51% of the time.

## Honest limitations

- Listing prices come from public listing text collected on Nov 20 and may be out of date; some listings are clearly marked "synthetic" examples. Availability isn't checked.
- Bus times use one representative week; real-time delays aren't modeled.
- Value of time, late-night cost and co-op hours are assumptions you can adjust.
- The simulations use generated schedules, not real ones.

## How to try it

[link to the live site]. Takes about a minute: type your real (or a typical) week, set a budget, and look at the top three homes and their receipts.

---

## Feedback questions

**Your situation**
1. When did you last choose housing, and how did you decide? What did you compare?
2. What surprised you after moving in (cost, commute, noise, roommates, utilities)?
3. Roughly how many minutes a day do you spend getting to and from places? Did you think about that when you signed?

**First impressions**
4. In one sentence, what do you think this tool does?
5. What was the first thing you looked at on the results screen? Was anything confusing?
6. Did typing your week work? Did it get anything wrong?

**Trust and usefulness**
7. Did the ranking match your intuition about those places? Where did it disagree, and who do you think is right?
8. Does "all-in cost including the value of your time" make sense to you, or does it feel artificial? Would you rather see hours and dollars separately?
9. Which feature would actually change a decision for you: the receipt, the map routes, "how sure are we", breakevens, or the roommate split?
10. What information is missing that you'd need before trusting it (photos, reviews, availability, safety, noise, landlord quality)?

**Roommates**
11. Have you and roommates ever argued about rent splits or rooms? Would an envy-free split help, or would people just argue about the inputs?

**Would you use it**
12. Would you use this for your next lease? At what point in your search (early browsing, final 3, before signing)?
13. Would you send it to a friend? What would you tell them it's for?
14. If you could change one thing, what would it be?

*Optional: rate 1–5 — easy to use / trustworthy / would change my decision.*
