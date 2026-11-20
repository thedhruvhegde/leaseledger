"""Coding of 16 SIMULATED persona feedback responses (source: simulated_feedback_round1.pdf, which states
'Each response below is from a distinct simulated persona'). Codes transcribed by hand from the PDF.
NOT real user research; used to stress-test product decisions. Run: python3 coded_responses.py"""
import json, math, collections
R = [  # id, profile tag, ratings(easy,trust,change), time_value stance, valued features (q9), missing info (q10), request (q14), use stage (q12)
 (1,"north-campus house, 4 roommates",(4,4,4),"accept_wants_toggle",["receipt","breakevens"],["photos","reviews","availability"],"calendar_import","early+final"),
 (2,"kerrytown studio, lifestyle-first",(3,3,2),"separate",["map_routes","receipt"],["noise","landlord","photos"],"lifestyle_score","final"),
 (3,"high time value, irregular labs",(5,5,5),"accept",["breakevens","how_sure"],["realtime_bus","availability"],"saved_schedules","early+final"),
 (4,"time-value skeptic, lowest rent",(4,2,2),"separate",["receipt","map_routes"],["photos","reviews","landlord"],"time_value_optional","final_only"),
 (5,"first lease, dorm, safety",(4,4,4),"accept_wants_both",["map_routes","how_sure"],["safety","photos","landlord","availability"],"night_safety_overlay","early+final"),
 (6,"late-night studier",(4,4,5),"accept",["receipt","map_routes"],["safety"],"night_constraint","final"),
 (7,"out-of-state, winter",(4,4,5),"accept",["receipt","map_routes"],["photos","heating_type"],"season_toggle","early+final"),
 (8,"athlete, 6am practice",(4,4,4),"accept",["map_routes","breakevens"],["realtime_bus","parking"],"default_anchors_sports","early+final"),
 (9,"extremely budget-tight",(3,3,2),"separate",["receipt"],["fees","utilities_included"],"time_value_optional","final_only"),
 (10,"drives, parking-focused",(3,3,2),"separate",["receipt"],["parking"],"car_mode","final_only"),
 (11,"international, bus-reliant",(4,5,5),"accept",["map_routes","receipt"],["photos","transit_explainer"],"beginner_transit_mode","early+final"),
 (12,"signed last month",(4,4,3),"accept",["breakevens"],["photos"],"compare_current_home","final"),
 (13,"lease organizer, roommate mediator",(4,4,5),"accept",["group_split","receipt"],["room_locks"],"export_split","early+final"),
 (14,"social-location first",(4,3,2),"useful_not_decider",["map_routes"],["custom_anchors"],"custom_anchors","final"),
 (15,"knows resident complaints",(5,5,4),"accept",["receipt","fee_flags","how_sure"],["landlord"],"pitfalls_callout","early+final"),
 (16,"north+central+job, time-scarce",(5,5,5),"accept",["breakevens","instant_rerank"],["availability","photos"],"saved_schedules","early+final"),
]
n=len(R)
def ci(k,n,z=1.96):  # Wilson
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d; return [round(c-h,3),round(c+h,3)]
mean=lambda xs: round(sum(xs)/len(xs),2)
easy=[r[2][0] for r in R]; trust=[r[2][1] for r in R]; chg=[r[2][2] for r in R]
sep=[r for r in R if r[3] in ("separate","accept_wants_toggle","accept_wants_both")]
cnt=lambda key: collections.Counter(x for r in R for x in r[key]).most_common()
# simple segmentation: does 'would change decision' differ between time-value acceptors and skeptics?
acc=[r[2][2] for r in R if r[3].startswith("accept")]; skp=[r[2][2] for r in R if not r[3].startswith("accept")]
out={
 "simulated": True, "n": n, "source": "simulated_feedback_round1.pdf (16 simulated personas, provided by team 2026-11-20)",
 "ratings_mean": {"easy": mean(easy), "trust": mean(trust), "would_change_decision": mean(chg)},
 "share_change_decision_ge4": {"k": sum(c>=4 for c in chg), "n": n, "ci95": ci(sum(c>=4 for c in chg), n)},
 "wants_hours_and_dollars_separate": {"k": len(sep), "n": n, "ci95": ci(len(sep), n), "ids": [r[0] for r in sep]},
 "would_change_decision_mean_by_stance": {"accepts_time_value": mean(acc), "n_accept": len(acc), "skeptic_or_separate": mean(skp), "n_skeptic": len(skp)},
 "valued_features": cnt(4), "missing_info": cnt(5),
 "requests": collections.Counter(r[6] for r in R).most_common(),
 "use_stage": collections.Counter(r[7] for r in R).most_common(),
 "caveat": "Simulated personas, n=16, not a sample of real students; directional only.",
}
json.dump(out, open("feedback_summary.json","w"), indent=1); print(json.dumps(out, indent=1))
