# Real decision-sensitivity flips (computed)

Computed 2026-11-20 02:33 UTC with the real provider (live fall-2026 GTFS), 69 observed (search-extract) listings, params as loaded. Regenerate: `python3 analysis/tools/find_demo_flips.py`.

## north-engineer — baseline #1 `icc-escher-double` ($1,166/mo all-in), #2 `university-towers-2br` ($1,231)

| Change | New #1 | Top-5 changed | Causes (engine diff) |
|---|---|---|---|
| January (winter) | same | False | ICC Escher House - double room (co-op) stays #1; its lead over University Towers - 2BR shared (up to 4 people) is now $65/mo (was $65/mo). |
| value of time $0 (cash only) | same | True | Changed value of time: unset -> $0.00/h.; Value of time used: $8.00/h -> $0.00/h; each listing's travel cost scales with its own hours. |
| value of time $20/h | **`university-towers-2br`** | True | Changed value of time: unset -> $20.00/h.; Value of time used: $8.00/h -> $20.00/h; each listing's travel cost scales with its own hours. |
| exclude co-ops | **`university-towers-2br`** | True | University Towers - 2BR shared (up to 4 people) becomes #1 because ICC Escher House - double room (co-op) is now excluded.; ICC Escher House - single room (co-op) is now excluded: excluded type: coop. |

## ross-kerrytown-job — baseline #1 `university-towers-2br` ($887/mo all-in), #2 `hillcrest-2br` ($918)

| Change | New #1 | Top-5 changed | Causes (engine diff) |
|---|---|---|---|
| January (winter) | same | True | Changed month: unset -> 1.; Outdoor minutes now count x1.202 for weather (was x1.006). |
| value of time $0 (cash only) | **`icc-escher-double`** | True | Changed value of time: unset -> $0.00/h.; Value of time used: $7.50/h -> $0.00/h; each listing's travel cost scales with its own hours. |

## late-night-studio — baseline #1 `icc-escher-double` ($1,271/mo all-in), #2 `university-towers-2br` ($1,319)

| Change | New #1 | Top-5 changed | Causes (engine diff) |
|---|---|---|---|
| add TR 7:00-12:00 hospital shift | **`university-towers-2br`** | True | Added 'add TR 7:00-12:00 hospital shift' (T/R 07:00-12:00): ICC Escher House - double room (co-op) +120 generalized min/wk (+$65/mo); University Towers - 2BR shared (up to 4 people) +47 generalized min/wk (+$26/mo); Hillcrest Manor - 2BR +294 generalized min/wk (+$160/mo).; At ICC Escher House - dou |
| January (winter) | same | False | Changed month: 2 -> 1.; Outdoor minutes now count x1.303 for weather (was x1.271). |
| value of time $0 (cash only) | same | True | Changed value of time: unset -> $0.00/h.; Value of time used: $7.50/h -> $0.00/h; each listing's travel cost scales with its own hours. |
| value of time $20/h | **`university-towers-2br`** | True | Changed value of time: unset -> $20.00/h.; Value of time used: $7.50/h -> $20.00/h; each listing's travel cost scales with its own hours. |
| exclude co-ops | **`university-towers-2br`** | True | University Towers - 2BR shared (up to 4 people) becomes #1 because ICC Escher House - double room (co-op) is now excluded.; ICC Escher House - single room (co-op) is now excluded: excluded type: coop. |

## premed-hospital — baseline #1 `university-towers-2br` ($996/mo all-in), #2 `icc-escher-double` ($1,172)

| Change | New #1 | Top-5 changed | Causes (engine diff) |
|---|---|---|---|
| January (winter) | same | True | Changed month: unset -> 1.; Outdoor minutes now count x1.202 for weather (was x1.006). |
| value of time $0 (cash only) | **`icc-escher-double`** | True | Changed value of time: unset -> $0.00/h.; Value of time used: $7.50/h -> $0.00/h; each listing's travel cost scales with its own hours. |
