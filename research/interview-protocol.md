# Interview Protocol — Student Housing Decisions (Hack the Lease, UMich, 2026-11-20)

Owner: Division A4 (interview research design). Status: **protocol only. No interviews have been run.** Record results in `interview-results.md` and `interview-results-template.csv`.

> Integrity rule: do not invent, paraphrase into stronger claims, or "round up" any interview result. If a field was not discussed, write `ND`. A count of 0 is a real finding. If the team mentions synthetic personas anywhere, label them `SYNTHETIC` and keep them out of these files.

Method note: the questioning style follows **The Mom Test** (Rob Fitzpatrick), applied from memory and not re-checked against the book today. The rules we use from it: ask about their life and not your idea, ask about specific past events and not about hypothetical futures, skip compliments, and dig for what they actually did and paid.

---

## 1. Goals and provisional hypotheses

**Research goal.** Learn how UMich students *actually* made their most recent housing decision: which alternatives they weighed, what information they lacked, which trade-offs they made, and what surprised them. Use that to choose which product concept to build and demo (rubric: Student value 30%, Decision quality & evidence 20%).

**Secondary goal.** Collect real, quantified anchors (commute minutes, January utilities, months signed before move-in) that the team can cite as observed, small-n field data. Never present them as representative.

The hypotheses are provisional and neutral. Each one is a claim we are trying to *break*, not to confirm.

| ID | Hypothesis (provisional) | Supporting signals (what we would hear/see) | Disconfirming signals |
|---|---|---|---|
| H1 | Students underestimate commute/schedule costs when choosing. | Reported actual commute is clearly longer than they expected (≥10 min/day or ≥30%). They changed routines, bought a bus pass/bike/parking, or skip classes or events because of distance. They name this as a regret. | Their commute matches what they expected. They chose distance on purpose and are satisfied. They say commute "doesn't matter" and can show it (e.g., they live far and never mention it as a cost). |
| H2 | Total cost (utilities, fees, transport) surprises students. | They remember a specific bill (e.g., January gas/electric, an admin or amenity fee, parking) that was higher than expected. They changed behavior (thermostat, roommate dispute, budget cut). They cannot state their all-in monthly cost. | They state their all-in cost accurately and say it matched expectations. Utilities are included or flat-rate and known upfront. No fee surprises. |
| H3 | Roommate group decisions involve unresolved budget/room conflicts and unfair rent splits. | A specific story of disagreement over budget, room size, or split. Someone paid "too much" or took a worse room without compensation. A group broke up or someone dropped out. | The split was settled quickly and everyone felt it was fair. Solo living by choice. Conflicts happened but resolved easily with no lingering cost. |
| H4 | Early-signing pressure forces decisions before preferences are known. | They signed many months before move-in (e.g., Oct–Dec for the next fall). They describe urgency ("everything was going"). They signed before knowing their schedule, roommates, or job/internship location. They regret it. | They signed late without penalty. They felt no pressure. Their preferences didn't change between signing and moving in. |
| H5 | Students cannot articulate their decision weights upfront. | When asked "what mattered most when you were choosing," the answer conflicts with what they actually chose or now regret. Priorities shifted after touring or moving in. | They state clear priorities that match the choice they made and the trade-offs they accepted, consistently across questions. |
| H6 | Listing information is untrustworthy or incomplete. | Specific mismatches (photos, square footage, "furnished," noise, condition, distance). They used workarounds (asked current tenants, Reddit, a friend's tour). They spent time verifying. | Listings were accurate. They didn't need extra sources. The gaps that did exist didn't matter to the outcome. |

**Exploratory (no hypothesis, code only if it comes up unprompted):** noise and study environment, safety, landlord responsiveness, winter (heating, snow, walking), deposits and move-out, accessibility needs (record only what the student volunteers about their own needs. Never ask about health or disability).

**Kill criteria (honest).** If after ≥8 interviews a hypothesis has net-zero or negative evidence (see §7), deprioritize concepts that depend on it, even if the team likes them.

---

## 2. Consent script and minimal-PII rules

### Verbal consent (read close to verbatim, ~20 seconds)

> "Hi! We're a student team at the Hack the Lease hackathon building a tool to help students compare housing. Could I ask you about how you picked your current place? It takes 2, 5, or 10 minutes, whichever you have time for. It's anonymous: we won't write down your name, your address, or anything that identifies you, and we won't record audio. We might quote you anonymously in our presentation. You can skip any question or stop at any time. Is that okay?"

- Only start if they give a clear **yes**. Record `consent_given = Y`. If they hesitate, thank them and let them go.
- If they ask, say what happens to the notes: they stay in the team repo, nothing is shared outside the hackathon judging, and they get deleted after the event if they ask (we can't find "their" row without a name, so tell them that honestly).
- If they agree to be quoted, check the quote at the end: "Can I quote you saying '…'?" Then set `quote_ok = Y/N`.

### Minimal-PII rules (non-negotiable)

1. **No names, emails, phone numbers, social handles, student IDs, or photos of people.** If someone offers contact info for follow-up, don't put it in the results files. Say: "Thanks, just check our demo at the showcase."
2. **Location only at neighborhood level**, e.g. Central Campus, North Campus, Kerrytown, Old West Side, South U, Burns Park, Lower Burns Park, Packard, Ypsilanti, or "other Ann Arbor". Never record a street, a building name, or a unit. (Building names together with other details can identify someone.)
3. **No demographics.** Don't ask about or record age, gender, race/ethnicity, nationality, international status, income, family situation, religion, health, or disability. Don't infer any of them. (The challenge puts demographic profiling out of scope.) If a student *volunteers* a circumstance that drove the decision, record only the decision-relevant need in their words, generalized. Example: "needed to be near a grocery store without a car", not why.
4. **Housing stage is allowed** because it's decision context, not demographics: `first_offcampus`, `repeat_offcampus`, `dorm_now_searching`, `searching_first_time`, `other`. Don't ask for class year.
5. **Money stays as approximate ranges or rounded numbers** of the student's own share (e.g., "~$1,100/mo"). Never record lease documents or photos of bills.
6. **No audio or video recording.** Handwritten or typed notes only.
7. Store notes only in `research/interview-results*.{md,csv}`. Don't paste them into external tools or LLM prompts with any identifying detail. (There shouldn't be any.)

---

## 3. Interview formats

**General rules for every format**
- Anchor on **their most recent actual decision** ("the place you live now" or "the lease you just signed"). If they're still searching, use their *current* search and code `stage = searching`.
- Ask "tell me about the last time…" and not "would you…". Ask "how much / how many minutes / when exactly" and not "is X important?"
- **Never pitch, describe, or name our concept before the closing artifact test.** Don't say "would an app that…".
- Don't fill silences. Count to 3 before you ask the next question.
- If they give you an opinion ("cost is the most important thing"), steer back to behavior: "When did that actually come up for you?"
- Write down **numbers and verbatim phrases**, not your interpretation.

### Universal pain-vs-politeness probes (use after any complaint or enthusiasm)

| They say… | Probe | What it distinguishes |
|---|---|---|
| "Yeah, that was annoying." | "What did you do about it?" / "Did you spend any money or time on it?" | Action means **Strong**. No action means **Moderate** at most. |
| "Utilities were crazy." | "Roughly how much was the highest month? Which month?" | A specific number means real. "I don't remember" lowers the evidence strength. |
| "Commute is kind of long." | "How many minutes, door to class, on a normal day? What did you expect before you signed?" | Gives the expected-vs-actual gap for H1. |
| "I'd totally use something like that." | "What do you use for this today? When did you last do it?" / "Would you have changed your decision?" | Hypothetical means **Weak**. A current workaround means real demand. |
| "Everyone has that problem." | "Has it happened to you? Tell me about the last time." | Moves from a general claim to their own instance. |
| "It's fine." | "If you were picking again tomorrow, what would you do differently?" | Surfaces hidden regret, or confirms no pain (a disconfirming signal). |

### 3A. 2-minute intercept (5 questions): hallway, line, between sessions

Goal: breadth. One quantified fact and one pain or no-pain signal per person.

1. "Where do you live now, roughly, as in which neighborhood, and is it a house, apartment, or dorm?" *(stage + neighborhood)*
2. "When you picked it, what were the other options you seriously looked at? Why did this one win?" *(alternatives, decision driver)*
3. "Since moving in, what surprised you, good or bad?" → probe: "What did you do about it?" *(surprises, evidence strength)*
4. "About how many minutes is your trip to your most frequent class, and what was your highest monthly utilities bill?" *(H1/H2 quantification; ND is fine)*
5. "If you were picking again, what would you do differently?" *(regret / H5)*

Close: "Thanks! That's really helpful." (No artifact test in the 2-minute format unless they offer to stay.)

### 3B. 5-minute structured (8 questions + short artifact test)

1. **Context:** "Tell me about your current place: neighborhood, type, how many people, and when you signed the lease compared with when you moved in." *(H4: months_before)*
2. **Alternatives:** "What other places did you seriously consider? How many did you tour or contact?" *(n alternatives)*
3. **Decisive moment:** "What made you finally decide? Was there a specific moment or piece of information that changed your mind?" *(decision changer, H5)*
4. **Info struggle:** "What was hardest to find out before you signed? What did you do to find it out?" → "Who or what did you trust most?" *(H6, trusted sources)*
5. **Trade-off:** "What did you give up to get this place?" → "Was that worth it, looking back?" *(H5)*
6. **Quantify:** "How many minutes is your commute *actually*, and what did you expect before you signed?" / "What was your share of utilities last January, or your highest month so far?" / "Any fees you didn't expect?" *(H1, H2)*
7. **Roommates (if any):** "How did your group decide who gets which room and how rent is split? Was everyone happy with it?" → "Did anything change because of it?" *(H3)*
8. **Regret:** "What would you do differently next time?"

**Artifact test** (≈1 min, see §3D).

### 3C. 10-minute in-depth (timeline walk-through + artifact test)

Use when someone is willing and relaxed. Walk through the decision chronologically. Use these prompts as needed and follow their story; don't read every one.

**Trigger and timing (H4)**
- "When did you start looking? What made you start then?"
- "When did you sign, and when did you move in? Did you feel any pressure to sign at that point? Where did that pressure come from?"
- "Did anything you didn't know yet at signing (schedule, roommates, internship, budget) turn out to matter?"

**Search process (H6, time spent)**
- "Walk me through how you searched. What sites, people, or groups did you use?"
- "Roughly how many hours total did you spend searching, touring, and messaging?"
- "Did any listing turn out different from reality? What exactly? How did you find out?"
- "Which source did you trust most? Why?"

**Choosing (H5)**
- "Before you started, what did you think mattered most?" *(write their answer)*
- "Which places made the final shortlist? What was the deciding difference?"
- Later, compare: "You said X mattered most. Did the final choice match that?" *(Note a mismatch neutrally. Don't tell them they're inconsistent.)*

**Group dynamics (H3, if applicable)**
- "How did your group form? Did anyone join or drop out?"
- "Did people want different budgets or different things? How was that resolved?"
- "How did you split rent and rooms? Did anyone feel it was unfair? What happened?"

**Living there (H1, H2, exploratory)**
- "What does a normal weekday trip to campus look like: mode and minutes? What about in winter?"
- "What's your all-in monthly cost: rent, utilities, internet, transport, fees? Which part surprised you most?"
- "What was the worst month for bills? Roughly how much?"
- "Anything about noise, studying, safety, the landlord, or winter that you didn't anticipate?" *(Ask open first: "Anything else you didn't anticipate?" Offer the list only if they're stuck, and code as `prompted`.)*

**Reflection**
- "What would you do differently next time?"
- "What would you tell a friend starting their search this month?"
- "Is there anything you'd have paid for, or spent more time on, to get right?" → "What, specifically? How much?" *(Only count it as Strong if they already did something similar.)*

**Artifact test** (≈2 min, see §3D).

### 3D. Closing artifact test (only AFTER all behavioral questions)

Purpose: check comprehension and relevance. This is *not* validation, and enthusiasm here counts as **Weak** evidence at most.

1. Show the concept sketch or demo screen **without explaining it**: "This is a rough idea. What do you think it does?" *(record comprehension: `understood` / `partial` / `misread`)*
2. "If you'd had this when you chose your current place, would anything have gone differently? What, specifically?" *(It counts only if their answer ties back to a problem they described earlier.)*
3. "What's missing or wrong?"
4. Commitment check (no PII): "Would you be willing to try it at our table today / give it 2 minutes of your real numbers?" → record `artifact_commitment = tried_now / agreed_later / declined / ND`. **A commitment is worth more than praise.**

Neutral framing rules: show 1–2 concepts in random order; don't say which one you built; don't react to their reactions.

---

## 4. Recording template (one row per interview)

Fill it in **immediately** after each interview (within 2 minutes) while memory is fresh. Use `ND` = not discussed, `DK` = student didn't know, `NA` = not applicable.

| Field | Description / allowed values |
|---|---|
| `interview_id` | `I01`, `I02`, … (sequential, no other identifier) |
| `date` | YYYY-MM-DD |
| `time_block` | `AM` / `PM` / `EVE` |
| `interviewer` | team initials or role (not the interviewee) |
| `format` | `2min` / `5min` / `10min` |
| `consent_given` | `Y` (if not Y, don't record anything else) |
| `quote_ok` | `Y` / `N` |
| `location_of_intercept` | generic, e.g. `hackathon_venue`, `union`, `library` |
| `housing_stage` | `first_offcampus` / `repeat_offcampus` / `dorm_now_searching` / `searching_first_time` / `other` |
| `housing_type` | `dorm` / `apartment` / `house` / `co-op` / `other` |
| `neighborhood` | neighborhood-level only (see §2) |
| `group_size` | number of people on the lease/household (1 = solo) |
| `signed_month` | month/year signed, e.g. `2025-11` |
| `movein_month` | e.g. `2026-08` |
| `months_signed_before_movein` | integer (compute) |
| `alternatives_considered_n` | integer or DK |
| `search_hours_est` | student's estimate, hours |
| `commute_mode` | `walk` / `bus` / `bike` / `car` / `mixed` |
| `commute_min_expected` | minutes, what they expected pre-signing |
| `commute_min_actual` | minutes, typical door-to-class |
| `rent_share_usd_mo` | rounded own share |
| `utilities_peak_usd_mo` | own share, peak month (note month in notes) |
| `utilities_included` | `Y` / `N` / `partial` |
| `unexpected_fees` | short text or `none` |
| `trusted_sources` | semicolon list, e.g. `friend;reddit;landlord site` |
| `decision_changer` | what tipped the decision (short) |
| `stated_top_priority` | their stated priority |
| `priority_matches_choice` | `Y` / `N` / `partial` / ND |
| `surprises` | short, semicolon list |
| `would_do_differently` | short |
| `pain_codes` | semicolon list of codes from §5 (e.g. `P-COST;P-WINTER`) |
| `H1_ev` … `H6_ev` | one of `S+`, `M+`, `W+`, `C`, `0`, `ND` (see §5.3) |
| `artifact_comprehension` | `understood` / `partial` / `misread` / ND |
| `artifact_commitment` | `tried_now` / `agreed_later` / `declined` / ND |
| `artifact_feedback` | short |
| `key_quote` | verbatim, only if quote_ok = Y |
| `notes` | anything else (no PII) |

**Markdown row template** (copy into `interview-results.md`):

| interview_id | date | format | housing_stage | neighborhood | group_size | months_signed_before_movein | alternatives_considered_n | commute_min_expected | commute_min_actual | rent_share_usd_mo | utilities_peak_usd_mo | pain_codes | H1_ev | H2_ev | H3_ev | H4_ev | H5_ev | H6_ev | artifact_commitment | key_quote |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I01 | | | | | | | | | | | | | | | | | | | | |

**CSV header** (full field set, also saved as `research/interview-results-template.csv`):

```
interview_id,date,time_block,interviewer,format,consent_given,quote_ok,location_of_intercept,housing_stage,housing_type,neighborhood,group_size,signed_month,movein_month,months_signed_before_movein,alternatives_considered_n,search_hours_est,commute_mode,commute_min_expected,commute_min_actual,rent_share_usd_mo,utilities_peak_usd_mo,utilities_included,unexpected_fees,trusted_sources,decision_changer,stated_top_priority,priority_matches_choice,surprises,would_do_differently,pain_codes,H1_ev,H2_ev,H3_ev,H4_ev,H5_ev,H6_ev,artifact_comprehension,artifact_commitment,artifact_feedback,key_quote,notes
```

Put any free text containing commas in double quotes. Use `;` inside list fields.

---

## 5. Coding taxonomy

### 5.1 Decision stage (`stage` code: when the pain occurred)

| Code | Stage |
|---|---|
| D-TRIGGER | Deciding to look / starting the search |
| D-SEARCH | Finding and filtering listings |
| D-VERIFY | Touring, checking listing accuracy, asking others |
| D-GROUP | Forming the roommate group, negotiating budget/rooms/split |
| D-COMMIT | Signing (timing, pressure, lease terms) |
| D-LIVE | Living there (surprises after move-in) |
| D-REFLECT | Regret / what they'd change next time |

### 5.2 Pain categories (`pain_codes`)

| Code | Category | Example evidence |
|---|---|---|
| P-COMMUTE | Commute / schedule fit | actual minutes > expected; bus timing; early class |
| P-COST | Rent and all-in cost | can't state all-in cost; budget overrun |
| P-UTIL | Utilities specifically | high January bill; split disputes over bills |
| P-FEES | Fees / deposits | admin, amenity, parking, move-out deductions |
| P-ROOMMATE | Roommate group dynamics | budget mismatch, unfair split, dropout |
| P-TIMING | Signing timing / pressure | signed 9+ months early, "everything was gone" |
| P-INFO | Listing info quality / trust | photos vs reality, missing info, scams |
| P-PRIORITY | Unclear or shifting priorities | stated vs actual mismatch |
| P-NOISE | Noise / study environment | neighbors, street, thin walls |
| P-SAFETY | Safety / walking at night | route concerns (their perception only) |
| P-LANDLORD | Landlord / management | responsiveness, repairs, disputes |
| P-WINTER | Winter-specific | heating, snow on route, drafts |
| P-ACCESS | Access to essentials | groceries, transit, parking |
| P-OTHER | Other (describe in notes) | |
| P-NONE | Explicitly no pain in this area | (use with the hypothesis column as a disconfirming signal) |

Add the suffix `-prompted` if it came up only after the interviewer offered the category list (e.g. `P-NOISE-prompted`). Prompted codes count at half weight.

### 5.3 Evidence strength (per hypothesis per interview)

| Code | Name | Rule | Example |
|---|---|---|---|
| `S+` | Strong behavioral | Specific past instance **and** they acted: paid money, spent measurable time, changed behavior, switched housing, or used a workaround. | "January was $190 for my share. We started a spreadsheet and fought about the thermostat." |
| `M+` | Moderate qualitative | A specific personal story or number, but no action or cost incurred. | "The walk is 25 minutes, I thought it'd be 15. Whatever, I deal." |
| `W+` | Weak speculative | Generic opinion, hypothetical, or "I would use…", including enthusiasm during the artifact test. | "Yeah, people definitely underestimate commute." |
| `C` | Contradictory | Specific evidence *against* the hypothesis (a disconfirming signal from §1). | "Utilities were included, and I knew my all-in cost to the dollar." |
| `0` | Discussed, neutral | Topic came up, nothing for or against. | |
| `ND` | Not discussed | Not asked or skipped. Excluded from the denominator. | |

Tie-breaks: if one interview has both supporting and contradicting evidence for the same hypothesis, record the **stronger** one and note both. If you're unsure between two levels, record the **lower**.

### 5.4 Tallying rules

1. One vote per interview per hypothesis (the code in `Hx_ev`). Don't count multiple mentions from the same person twice.
2. Two interviewers code each interview independently when possible (each takes the other's notes for 10 interviews). Agreement is the share of `Hx_ev` cells that match exactly. Report it. If it's below ~70%, tighten the definitions and recode.
3. Keep **2-minute intercepts separate** from 5/10-minute interviews in the summary. Intercepts mostly produce M/W evidence by design.
4. Track **n_discussed** per hypothesis (`Hx_ev ≠ ND`), not just n_interviews.
5. Save quotes only verbatim, with `quote_ok = Y`.

### 5.5 Honest sample-size rules

These are judgment heuristics for a one-day hackathon, **not statistical tests**. Our sample is a convenience sample (people at or near a hackathon venue), likely skewed toward tech-oriented students and toward whoever is free to chat. Nothing here generalizes to "UMich students".

| n_discussed for a hypothesis | What we're allowed to say |
|---|---|
| 0–2 | Nothing. "Not yet tested." |
| 3–4 | "Early anecdotes." Quote individual stories. Don't change concept rankings. |
| 5–9 | "Provisional signal." Rankings may be updated (§7). Report raw counts (e.g., "4 of 6 described…"), never percentages. |
| ≥10 | "Consistent pattern in our sample" (or "mixed"). Still small-n and still a convenience sample. Say so in the presentation. |

Always present as "k of n_discussed (S/M/W/C breakdown)". Example format, not data: "H2: 3 of 7 Strong, 2 Moderate, 1 Weak, 1 Contradictory".

---

## 6. Field card (hold on phone)

```
HACK THE LEASE: FIELD CARD   (no names, no addresses, no demographics)

CONSENT (say it): "Student team at Hack the Lease. Can I ask how you
picked your current place? 2/5/10 min, anonymous, no recording,
skip anything, stop anytime, maybe quoted anonymously. OK?"  → need YES

RULES: past behavior > opinions | numbers > adjectives | no pitching
       until the end | don't fill silence | write verbatim

2-MIN
 1 Which neighborhood + type (house/apt/dorm)?
 2 What else did you seriously consider? Why did this one win?
 3 What surprised you after moving in? → What did you DO about it?
 4 Commute minutes? Highest utilities month ($)?
 5 Picking again: what would you do differently?

5-MIN adds
 - When did you sign vs move in? Any pressure?
 - Hardest thing to find out before signing? How did you find out?
   Who did you trust?
 - What did you give up? Worth it?
 - Expected vs actual commute? January utilities? Surprise fees?
 - Roommates: how were rooms/rent split? Everyone happy? What changed?

10-MIN adds
 - Hours spent searching? Any listing ≠ reality?
 - What did you THINK mattered most? Did the final choice match?
 - Group: anyone drop out? budget mismatch?
 - All-in monthly cost? Winter commute?

PAIN vs POLITE
 "annoying" → What did you do? Spend $/time?
 "I'd use it" → What do you use today? When last?
 "everyone"  → Has it happened to YOU? Last time?
 "it's fine" → What would you do differently?

ARTIFACT TEST (LAST, only after the behavioral questions)
 Show sketch silently → "What do you think it does?"
 "Would it have changed your decision? How?"
 "What's missing?" → "Try it now for 2 min?" (record tried/declined)

CODE IT (right after): S+ acted/paid/spent time | M+ specific story,
 no action | W+ hypothetical | C contradicts | ND not discussed
 If unsure → pick the LOWER level.  Neighborhood only.  ND is fine.
```

---

## 7. Analysis procedure: from interviews to concept rankings

**Step 1: Evidence index per hypothesis.** Assign weights:

| Code | Weight |
|---|---|
| S+ | +3 |
| M+ | +1 |
| W+ | +0.25 |
| 0 | 0 |
| C (with a specific behavioral instance) | −3 |
| C (opinion only) | −1 |
| ND | excluded |

Prompted codes (`-prompted`) get half weight.

`EI(Hx) = sum(weights) / n_discussed(Hx)`, which ranges from −3 to +3.

Example of the arithmetic only (**illustrative, not data**): codes S+, M+, M+, C, W+ give (3+1+1−3+0.25)/5 = 0.45.

**Step 2: Confidence gate.** Use EI(Hx) only if n_discussed ≥ 5 (§5.5). Otherwise set the effective `EI'(Hx) = 0` (prior unchanged). If n_discussed ≥ 5, use `EI'(Hx) = EI(Hx) × min(1, n_discussed/10)`. This shrinks small samples toward zero.

**Step 3: Concept–hypothesis relevance matrix.** For each candidate concept (from `concepts/`), the team assigns a relevance `r(C, Hx)` ∈ {0, 1, 2}, where 2 means the concept's core value depends on Hx being true. Fix this matrix **before** looking at interview results, and commit it to `decisions/` with a timestamp so it can't be tuned after the fact.

**Step 4: Updated concept score.**

`Score(C) = Prior(C) + λ × Σx r(C,Hx) × EI'(Hx)`

- `Prior(C)` is the team's pre-interview score from the concept evaluation (whatever scale `concepts/` uses, normalized to 0–10).
- Use λ = 0.5 by default, so interviews can move a concept by a few points without overriding feasibility and demo-ability (the rubric weights technical execution at 35%).
- **Sensitivity check (mirrors R3):** recompute with λ = 0.25 and λ = 1. If the top-ranked concept changes across λ, report the ranking as *not robust* and decide on feasibility.

**Step 5: Report.** For each hypothesis give n_discussed, the S/M/W/C counts, EI, the gate status, and 1–2 verbatim quotes. For concepts give the ranking before and after, plus the λ-sensitivity result. State the limitations explicitly: convenience sample, single day, interviewer effects, self-report recall bias (especially remembered utility amounts), and no demographic balancing (by design).

**Step 6: Product inputs (optional).** Quantified fields (commute expected vs actual, peak utilities, months signed early) may be shown in the demo only as "observed in N = k informal interviews on 2026-11-20". Show medians and ranges, not means, and never mix them with synthetic data in the same unlabeled chart.
