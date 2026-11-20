"""Concept scoring against official rubric + robustness of the winner under weight uncertainty.
Scores 1-10 are team judgments informed by research files (see concepts/concept-inventory.md); NOT measurements.
unc = +/- half-width of judgment uncertainty applied uniformly to each subscore."""
import numpy as np, csv, pathlib
rng=np.random.default_rng(7)
# id, name, tech(35), value(30), evidence(20), ux(15), unc, feasible_hours, screen_note
C=[
("C01","Routine commute ledger (schedule x multimodal GTFS)",8,8,8,7,1.0,10,""),
("C02","True cost of occupancy (fees+seasonal utilities+transport)",6,8,8,6,1.0,6,""),
("C03","Week-in-the-life engine: C01+C02+robust ranking",9,9,8,8,1.5,16,""),
("C04","Roommate joint choice + envy-free room/rent split",9,7,6,8,1.5,12,"local evidence weak"),
("C05","Bayesian pairwise preference elicitation",7,6,6,7,1.5,8,""),
("C06","Robustness layer (SMAA rank acceptability)",7,5,8,5,1.0,5,"layer, not product"),
("C07","Lease/listing auditor w/ cited extraction + A2 fee-law flags",6,7,7,7,1.5,10,"LLM-dependent"),
("C08","Personal lease-timing planner (A2 ordinance)",3,6,5,6,1.0,5,"thin computation"),
("C09","Optimal stopping: sign now vs wait",7,5,2,5,2.0,10,"no market curve data"),
("C10","Late-entrant / transfer finder",4,6,5,5,1.5,8,"needs live inventory"),
("C11","Multi-year housing trajectory (major/year shifts)",6,6,4,6,2.0,12,""),
("C12","Schedule isochrone 'where can I live' map",6,7,7,9,1.0,8,"subset of C01"),
("C13","Roommate group-formation matcher",5,5,4,6,1.5,10,"saturated (Diggz,BtD)"),
("C14","Winter reliability Monte Carlo",6,5,6,5,1.5,6,"layer of C01"),
("C15","Study/noise fit from OSM POIs",4,5,3,5,1.5,6,"weak proxy validity"),
("C16","Per-bed vs per-unit normalizer + joint-liability risk",4,6,5,5,1.0,4,""),
("C17","Sublet/summer cost risk calculator",4,5,4,4,1.0,4,""),
("C18","Bayesian landlord reputation aggregator",6,6,2,5,2.0,10,"no legit review data"),
("C19","Conversational AI housing advisor",4,4,3,6,1.5,6,"saturated; hallucination risk"),
("C20","Minimax-regret 'regret check' advisor",7,5,6,5,1.5,6,"layer"),
("C21","New-construction move-in risk tracker",3,5,4,4,2.0,8,"no data"),
("C22","Mobility-aware route fit",5,6,4,5,1.5,6,"sensitive; feature of C01"),
("C23","Group constraint negotiator (minimal concessions / IIS)",8,7,5,7,1.5,8,"pairs with C04"),
("C24","Group mode on Week-in-the-life engine (C03+C04+C23)",9,9,7,9,2.0,22,"over-scope risk"),
]
W=np.array([.35,.30,.20,.15])
S=np.array([c[2:6] for c in C],float); U=np.array([c[6] for c in C])
base=S@W
# Round 6 sensitivity: Dirichlet weights centered on rubric + judgment noise on scores
N=20000; wins=np.zeros(len(C)); top3=np.zeros(len(C))
for _ in range(N):
    w=rng.dirichlet(W*40)
    s=S+rng.uniform(-1,1,S.shape)*U[:,None]
    t=s@w; o=np.argsort(-t); wins[o[0]]+=1; top3[o[:3]]+=1
out=pathlib.Path(__file__).resolve().parents[1]/'concept-evaluation.csv'
with open(out,'w',newline='') as f:
    wr=csv.writer(f); wr.writerow(["id","name","technical_35","value_30","evidence_20","ux_15","judgment_unc","est_build_hours","rubric_score","p_rank1","p_top3","screen_note"])
    for i,c in sorted(enumerate(C),key=lambda x:-base[x[0]]):
        wr.writerow([c[0],c[1],*c[2:6],c[6],c[7],round(base[i],2),round(wins[i]/N,3),round(top3[i]/N,3),c[8]])
for i in np.argsort(-base)[:8]:
    print(f"{C[i][0]} {base[i]:.2f} P(#1)={wins[i]/N:.2f} P(top3)={top3[i]/N:.2f} h={C[i][7]} {C[i][1][:55]}")
# feasibility-constrained: exclude >18h
m=np.array([c[7]<=18 for c in C]); i=np.argmax(np.where(m,base,-1)); print("Best with build<=18h:",C[i][0])
