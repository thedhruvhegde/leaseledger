# Behavioral parameters (`params.json`): how each number was chosen

Every number below is a **default with a range**. The engine uses `value` for the headline result and samples
`[low, high]` in the Monte Carlo robustness check. Each entry has a `provenance` tag:

- **observed**: copied from a published source (government guidance, a statute, NOAA data, or plain arithmetic).
- **estimated**: our judgement built from published studies. The studies are named, but no single one gives this exact number.
- **assumed**: no usable evidence was found. We chose a reasonable value, gave it a wide range and expose it as a slider.

Full citations and the reasoning behind each value are in `research/literature-review.md`.

## Turning time into money

**Share of wage (0.50, range 0.35–0.60, observed).** The U.S. Department of Transportation tells agencies to value
personal local travel time at 50% of hourly income, with 35–60% as the plausible range. This is the standard U.S.
convention for valuing travel time, not a measurement of students.

**Student wage ($15/h, range $13.73–$18.75, observed).** Since August 2022 the University of Michigan has paid at least
$15/h for on-campus student and temporary jobs. Michigan's minimum wage is $13.73 in 2026 and rises to $15 on
1 Jan 2027. The high end comes from student job postings we saw, which is a weak source.

**Default value of time ($7.50/h, range $4.80–$15, estimated).** This is 50% × $15. The low end is 35% of the
minimum wage. The high end assumes every hour of travel replaces an hour of paid work. Studies of students' value of
time disagree widely, from about €1.4/h to $23/h depending on method. That is why the app shows **hours first**,
lets you type your own value, and runs the robustness check across the whole range.

## Not all minutes feel the same

Everything is measured in "bus-seat minutes" (in-vehicle = 1.0).

- **Walking (×1.75, range 1.5–2.0, estimated)** and **waiting at a stop (×1.75, range 1.5–2.0, estimated).** For
  decades, transport agencies counted a walking or waiting minute as two riding minutes; USDOT's guidance amounts to
  ×2.0. The largest worldwide meta-analysis (Wardman and co-authors: 2,872 multipliers from 606 studies) finds ×1.5–1.75
  is closer to how people actually behave. We use 1.75 and keep 2.0 as the upper bound.
- **Cycling (×1.0, range 0.8–1.5, assumed).** We found no reliable figure. Riding a bike is treated like riding a bus.
- **Transfer (+10 bus-minutes per transfer, range 5–18, estimated).** Changing buses has a cost of its own, beyond the
  extra walking and waiting. A Madrid commuter study puts this "pure" penalty at 15–18 minutes. Campus trips are short
  and transfers here are usually at the same stop, so we scale it down. The scaling is our own judgement.
- **Arriving early because of the bus timetable (×0.5 per minute beyond the buffer, range 0.3–0.8, estimated).** If the
  only bus that gets you to a 9:00 class arrives at 8:35, those 25 minutes are not wasted, since you can study, but
  they are not free either. Scheduling research (Small 1982) finds people value a minute of being early at roughly half
  a minute of travel, and a minute of being late at about twice. Unit: a multiplier on your value of time per minute.

## Michigan winter

- **Snow-cover days and freezing days per month (observed).** These are NOAA 1991–2020 climate normals for the Ann
  Arbor U of M station. Snow-cover days are days with at least 1 inch of snow on the ground: Jan 20.9, Feb 17.0,
  Mar 7.2, Dec 11.7, about 59 a year. Freezing days are days with a minimum temperature at or below the NOAA 32 °F
  threshold, about 130 a year.
- **Bad-day walk multiplier (×1.3, range 1.1–1.7, estimated).** On a snow-cover day, each walking or outdoor waiting
  minute counts 1.3 times as much. Studies of winter walking find people move about 8–17% slower on snow or ice.
  Studies of bad weather find each minute also feels worse. One study measured about 1.7× in rain, though it is
  preliminary and about rain, not snow. For a given month the engine applies the multiplier in proportion to that
  month's share of snow-cover days, scaled by your own "winter aversion" setting.

## Late night

**Extra cost per outdoor minute after 10 pm ($0.10/min, range $0–$0.30, assumed).** Many people dislike walking
alone at night. In Gallup's 2023 poll, 40% of U.S. adults said they would be afraid to walk alone at night near
their home (53% of women, 26% of men). We found no study that puts a dollar or minute value on this, so the number is
our assumption. It adds about 45% to a walking minute at the default value of time. You can turn it up or down.

## Schedule rules

- **Go home between events only if the gap leaves at least 30 minutes at home** (range 15–60, assumed).
- **Arrive 5 minutes before an event** (range 2–10, assumed). Scheduling theory suggests aiming to be on time about
  80% of the time when lateness costs about four times as much as earliness. A fixed 5 minutes is a simple stand-in
  until ride-time variability is modeled.

## Calendar

- **4.348 weeks per month (observed):** 365.25 ÷ 12 ÷ 7.
- **30 academic weeks per year (range 28–32, estimated).** The University's 2026–27 Ann Arbor calendar has 69 class
  days in each of fall and winter, about 14 weeks of classes per term, plus about a week of exams and study days. Fall
  2026 classes begin 31 Aug. We could not open the Registrar's PDF, so the exam dates are unverified.
