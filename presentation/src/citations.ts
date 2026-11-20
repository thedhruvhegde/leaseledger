// Bibliography used on slides. Only `year` and `where` may contain digits (bibliographic metadata);
// `finding` is prose with NO numbers (scripts/check-copy.mjs enforces this).
// Sources: research/literature-review.md, research/student-behavior.md, research/housing-feedback.md.
export type Cite = { id: string; who: string; year: string; where: string; finding: string; kind: 'peer-reviewed' | 'government' | 'local reporting' | 'working paper' };

export const CITES: Record<string, Cite> = {
  stutzer: { id: 'stutzer', who: 'Stutzer & Frey', year: '2008', where: 'Scand. J. Econ. 110(2)', kind: 'peer-reviewed',
    finding: 'People with longer commutes report lower life satisfaction and are not compensated for it: the “commuting paradox”.' },
  burzacchi: { id: 'burzacchi', who: 'Burzacchi et al.', year: '2024', where: 'Studies in Higher Education', kind: 'peer-reviewed',
    finding: 'GPS-measured commute time has a significant negative effect on first-year engineering GPA.' },
  kobus: { id: 'kobus', who: 'Kobus, Van Ommeren & Rietveld', year: '2015', where: 'Reg. Sci. Urban Econ. 52', kind: 'peer-reviewed',
    finding: 'Students with long commutes come to campus on fewer days but stay longer: they chain trips — which is why we model day tours.' },
  usdot: { id: 'usdot', who: 'U.S. DOT', year: '2016', where: 'Valuation of Travel Time, Rev. 2', kind: 'government',
    finding: 'Personal local travel time is valued at half the traveller’s wage — our default, and a slider.' },
  fees: { id: 'fees', who: 'Michigan Daily; Ann Arbor Tenants Union', year: '2024', where: 'local reporting', kind: 'local reporting',
    finding: 'Waitlist, application and admin fees in Ann Arbor are renamed and hidden, and hit students before they sign.' },
  winter: { id: 'winter', who: 'r/AnnArbor; Michigan Daily', year: '2025', where: 'tenant reports', kind: 'local reporting',
    finding: 'Winter heating bills in older, drafty student houses arrive as a budget shock after signing.' },
  csa: { id: 'csa', who: 'Dibbelt, Pajor, Strasser & Wagner', year: '2018', where: 'ACM J. Exp. Algorithmics', kind: 'peer-reviewed',
    finding: 'Connection Scan: one pass over time-sorted connections gives exact earliest arrivals.' },
  small: { id: 'small', who: 'Small', year: '1982', where: 'Am. Econ. Rev. 72(3)', kind: 'peer-reviewed',
    finding: 'Arriving early because of the timetable is a real cost, smaller than travel time.' },
  wardman: { id: 'wardman', who: 'Wardman, Chintakayala & de Jong', year: '2016', where: 'Transp. Res. A 94', kind: 'peer-reviewed',
    finding: 'Walking and waiting minutes feel heavier than riding minutes.' },
  abrantes: { id: 'abrantes', who: 'Abrantes & Wardman', year: '2011', where: 'Transp. Res. A 45(1)', kind: 'peer-reviewed',
    finding: 'A UK meta-analysis finds the walk and wait multiplier substantially lower than the conventional two.' },
  wardmanMeta: { id: 'wardmanMeta', who: 'Wardman et al.', year: '2026', where: 'worldwide meta-analysis of time multipliers (TRID)', kind: 'peer-reviewed',
    finding: 'Across hundreds of studies, a walking or waiting minute weighs less than the conventional double of a riding minute.' },
  garcia: { id: 'garcia', who: 'García-Martínez et al.', year: '2018', where: 'Transp. Res. A 114', kind: 'peer-reviewed',
    finding: 'A transfer costs riders extra minutes on top of the walk and the wait it causes.' },
  noaa: { id: 'noaa', who: 'NOAA NCEI', year: '2021', where: 'U.S. Climate Normals 1991–2020, Ann Arbor', kind: 'government',
    finding: 'Monthly snow-cover days and heating degree days for Ann Arbor.' },
  eia: { id: 'eia', who: 'EIA RECS', year: '2020', where: 'Residential Energy Consumption Survey', kind: 'government',
    finding: 'Heating use per degree day by home type and age.' },
  gigerenzer: { id: 'gigerenzer', who: 'Gigerenzer & Hoffrage', year: '1995', where: 'Psych. Review 102(4)', kind: 'peer-reviewed',
    finding: 'People reason about uncertainty far better with natural frequencies than with percentages.' },
  gal: { id: 'gal', who: 'Gal, Mash, Procaccia & Zick', year: '2017', where: 'J. ACM 64(6)', kind: 'peer-reviewed',
    finding: 'Among all envy-free rent splits, pick the one that leaves the worst-off roommate best off; it is a linear program.' },
  dufton: { id: 'dufton', who: 'Dufton & Larson', year: '2011', where: 'IJCAI-11 workshop (COMSOC)', kind: 'peer-reviewed',
    finding: 'No deterministic room-and-rent mechanism is both envy-free and manipulation-proof.' },
};

export const citeTag = (id: string) => {
  const c = CITES[id];
  return `<cite class="cite" data-cite="${c.id}" data-src="cite:${c.id}">${c.who} <span class="yr">${c.year}</span></cite>`;
};
