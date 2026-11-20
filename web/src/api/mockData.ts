/**
 * Deterministic fixtures for the offline MOCK mode. Every listing here is SYNTHETIC (fictional,
 * labeled provenance:"synthetic"). Building coordinates are approximate and labeled as such.
 * Feed facts in MOCK_METHODS are read from the raw files in data/raw (dates as found in calendar.txt / feed_info.txt).
 */
import type {
  Building,
  DemoProfile,
  Event,
  Listing,
  Manifest,
  MethodsResult,
  Profile,
  ScheduleTemplate,
} from '../types';

const BSRC = 'mock fixture: approximate coordinates (replace with data/campus/buildings.json)';
const b = (id: string, name: string, campus: Building['campus'], lat: number, lon: number, aliases: string[], hours_note?: string): Building => ({
  id, name, campus, lat, lon, aliases, source: BSRC, hours_note: hours_note ?? null,
});

export const MOCK_BUILDINGS: Building[] = [
  b('bbb', 'Bob and Betty Beyster Building', 'north', 42.2929, -83.7163, ['BBB', 'Beyster', 'Bob and Betty', 'CSE building']),
  b('eecs', 'EECS Building', 'north', 42.2925, -83.7142, ['EECS', 'EECS bldg']),
  b('ggbrown', 'G.G. Brown Laboratory', 'north', 42.2934, -83.7137, ['GG Brown', 'GGB', 'G.G. Brown']),
  b('dude', 'Duderstadt Center', 'north', 42.2912, -83.7158, ['Dude', 'Duderstadt', 'Media Union'], 'Open 24 h during the term (verify)'),
  b('pierpont', 'Pierpont Commons', 'north', 42.2915, -83.7178, ['Pierpont']),
  b('frb', 'Ford Motor Company Robotics Building', 'north', 42.2944, -83.7108, ['FRB', 'Robotics', 'Ford Robotics']),
  b('ncrb', 'North Campus Recreation Building', 'north', 42.2950, -83.7208, ['NCRB', 'North gym']),
  b('moore', 'Earl V. Moore Building (Music)', 'north', 42.2908, -83.7226, ['Moore', 'Music school', 'SMTD']),
  b('ugli', 'Shapiro Undergraduate Library', 'central', 42.2756, -83.7372, ['UgLi', 'Ugli', 'Shapiro', 'undergrad library'], 'Open 24/7 during the term; MCard midnight-8am'),
  b('hatcher', 'Hatcher Graduate Library', 'central', 42.2764, -83.7384, ['Hatcher', 'Grad library', 'the grad']),
  b('angell', 'Angell Hall', 'central', 42.2766, -83.7399, ['Angell', 'Angell Hall', 'Fishbowl', 'AH']),
  b('mason', 'Mason Hall', 'central', 42.2772, -83.7391, ['Mason', 'MH']),
  b('union', 'Michigan Union', 'central', 42.2750, -83.7417, ['Union', 'the Union']),
  b('league', 'Michigan League', 'central', 42.2791, -83.7387, ['League']),
  b('chem', 'Chemistry Building', 'central', 42.2785, -83.7362, ['Chem', 'Chemistry']),
  b('bsb', 'Biological Sciences Building', 'central', 42.2794, -83.7354, ['BSB', 'Bio building']),
  b('ross', 'Ross School of Business', 'central', 42.2731, -83.7383, ['Ross', 'B-school', 'Business school']),
  b('law', 'Law Quadrangle', 'central', 42.2737, -83.7398, ['Law Quad', 'Law school']),
  b('ccrb', 'Central Campus Recreation Building', 'central', 42.2762, -83.7313, ['CCRB', 'gym', 'central gym']),
  b('uh', 'University Hospital', 'medical', 42.2838, -83.7288, ['UH', 'hospital', 'Michigan Medicine']),
  b('stadium', 'Michigan Stadium', 'south', 42.2659, -83.7487, ['Big House', 'stadium']),
  b('imsb', 'Intramural Sports Building', 'south', 42.2696, -83.7425, ['IM Building', 'IMSB']),
  b('kerrytown', 'Kerrytown Market & Shops', 'downtown', 42.2847, -83.7462, ['Kerrytown', 'the cafe']),
  b('mainst', 'Main Street (downtown)', 'downtown', 42.2808, -83.7484, ['Main St', 'Main Street', 'downtown']),
];

const SYN_NOTE = 'SYNTHETIC listing for demonstration — not a real property, price, or availability.';

const L = (p: Partial<Listing> & Pick<Listing, 'id' | 'name' | 'lat' | 'lon' | 'rent' | 'rent_basis' | 'bedrooms' | 'building_type'>): Listing => ({
  address: null,
  neighborhood: null,
  provenance: 'synthetic',
  source_url: null,
  observed_on: null,
  rent_is_range: false,
  rent_low: null,
  rent_high: null,
  baths: null,
  sqft: null,
  rooms: [],
  fees: [],
  utilities_included: [],
  year_built: null,
  heating: 'unknown',
  furnished: null,
  in_unit_laundry: null,
  parking_monthly: null,
  pets_allowed: null,
  lease_term_months: 12,
  lease_start: '2027-08-25',
  amenities: [],
  notes: SYN_NOTE,
  board_included: false,
  verification: null,
  ...p,
});

export const MOCK_LISTINGS: Listing[] = [
  L({ id: 'syn-oxford-tower', name: 'Hill St high-rise (per bed)', neighborhood: 'South Central', lat: 42.2733, lon: -83.7334,
    rent: 1395, rent_basis: 'bed', bedrooms: 4, baths: 4, sqft: 1380, building_type: 'tower', year_built: 2016, heating: 'electric_resistance',
    furnished: true, in_unit_laundry: true, parking_monthly: 95, pets_allowed: false, utilities_included: ['internet', 'water', 'trash'],
    amenities: ['gym', 'study rooms', 'rooftop'],
    fees: [{ label: 'Amenity fee', amount: 45, period: 'monthly', per: 'person', provenance: 'synthetic', quote: null },
      { label: 'Admin fee', amount: 150, period: 'once', per: 'person', provenance: 'synthetic', quote: null }],
    rooms: [{ id: 'A', sqft: 150, private_bath: true }, { id: 'B', sqft: 140, private_bath: true }, { id: 'C', sqft: 140, private_bath: true }, { id: 'D', sqft: 125, private_bath: true }] }),
  L({ id: 'syn-kerrytown-room', name: 'Kerrytown room in 1912 house', neighborhood: 'Kerrytown', lat: 42.2858, lon: -83.7440,
    rent: 925, rent_basis: 'bed', bedrooms: 5, baths: 2, sqft: 2100, building_type: 'house', year_built: 1912, heating: 'gas',
    furnished: false, in_unit_laundry: false, parking_monthly: 50, pets_allowed: true, amenities: ['porch'],
    rooms: [{ id: '1', sqft: 160 }, { id: '2', sqft: 145 }, { id: '3', sqft: 120 }, { id: '4', sqft: 110 }, { id: '5', sqft: 95 }] }),
  L({ id: 'syn-plymouth-1br', name: 'Plymouth Rd 1BR near North Campus', neighborhood: 'North Campus / Plymouth', lat: 42.3009, lon: -83.7066,
    rent: 1240, rent_basis: 'unit', bedrooms: 1, baths: 1, sqft: 640, building_type: 'apartment', year_built: 1998, heating: 'heat_pump',
    furnished: false, in_unit_laundry: true, parking_monthly: 0, pets_allowed: true, utilities_included: ['water', 'trash'], amenities: ['gym'],
    fees: [{ label: 'Trash/valet fee', amount: 25, period: 'monthly', per: 'unit', provenance: 'synthetic', quote: null }] }),
  L({ id: 'syn-southu-tower', name: 'South U tower (per bed)', neighborhood: 'South University', lat: 42.2747, lon: -83.7325,
    rent: 1650, rent_basis: 'bed', bedrooms: 4, baths: 4, sqft: 1450, building_type: 'tower', year_built: 2019, heating: 'electric_resistance',
    furnished: true, in_unit_laundry: true, parking_monthly: 150, pets_allowed: false, utilities_included: ['internet', 'water', 'trash', 'heat'],
    amenities: ['gym', 'rooftop', 'study rooms', 'quiet floors'],
    fees: [{ label: 'Amenity fee', amount: 60, period: 'monthly', per: 'person', provenance: 'synthetic', quote: null }] }),
  L({ id: 'syn-burnspark-duplex', name: 'Burns Park duplex room', neighborhood: 'Burns Park', lat: 42.2668, lon: -83.7287,
    rent: 980, rent_basis: 'bed', bedrooms: 3, baths: 1.5, sqft: 1300, building_type: 'duplex', year_built: 1925, heating: 'gas',
    furnished: false, in_unit_laundry: true, parking_monthly: 0, pets_allowed: false, amenities: ['quiet', 'yard'],
    rooms: [{ id: 'up-front', sqft: 150 }, { id: 'up-back', sqft: 125 }, { id: 'down', sqft: 170, private_bath: true }] }),
  L({ id: 'syn-lowertown-studio', name: 'Lower Town studio', neighborhood: 'Lower Town', lat: 42.2893, lon: -83.7398,
    rent: 1120, rent_basis: 'unit', bedrooms: 0, baths: 1, sqft: 430, building_type: 'apartment', year_built: 1972, heating: 'gas',
    furnished: false, in_unit_laundry: false, parking_monthly: 40, pets_allowed: false, utilities_included: ['heat', 'water'] }),
  L({ id: 'syn-packard-room', name: 'Packard St room (lowest rent)', neighborhood: 'Packard / Stadium', lat: 42.2622, lon: -83.7322,
    rent: 845, rent_basis: 'bed', bedrooms: 4, baths: 1, sqft: 1500, building_type: 'house', year_built: 1908, heating: 'gas',
    furnished: false, in_unit_laundry: false, parking_monthly: 0, pets_allowed: true,
    rooms: [{ id: 'a', sqft: 140 }, { id: 'b', sqft: 130 }, { id: 'c', sqft: 115 }, { id: 'd', sqft: 100 }] }),
  L({ id: 'syn-huronpkwy-share', name: 'Huron Pkwy 2BR share', neighborhood: 'Northeast', lat: 42.2858, lon: -83.7012,
    rent: 890, rent_basis: 'bed', bedrooms: 2, baths: 2, sqft: 980, building_type: 'apartment', year_built: 1985, heating: 'gas',
    furnished: false, in_unit_laundry: true, parking_monthly: 0, pets_allowed: true, utilities_included: ['water'], amenities: ['pool'],
    rooms: [{ id: 'primary', sqft: 160, private_bath: true }, { id: 'second', sqft: 130, private_bath: true }] }),
  L({ id: 'syn-oldwest-room', name: 'Old West Side room', neighborhood: 'Old West Side', lat: 42.2797, lon: -83.7585,
    rent: 900, rent_basis: 'bed', bedrooms: 3, baths: 1, sqft: 1250, building_type: 'house', year_built: 1920, heating: 'gas',
    furnished: false, in_unit_laundry: true, parking_monthly: 0, pets_allowed: true, amenities: ['quiet'],
    rooms: [{ id: 'front', sqft: 150 }, { id: 'middle', sqft: 120 }, { id: 'attic', sqft: 105 }] }),
  L({ id: 'syn-fuller-room', name: 'Fuller Rd apartment room', neighborhood: 'Medical / Fuller', lat: 42.2873, lon: -83.7238,
    rent: 1080, rent_basis: 'bed', bedrooms: 3, baths: 2, sqft: 1150, building_type: 'apartment', year_built: 2004, heating: 'heat_pump',
    furnished: true, in_unit_laundry: true, parking_monthly: 60, pets_allowed: false, utilities_included: ['water', 'trash'],
    fees: [{ label: 'Admin fee', amount: 100, period: 'once', per: 'person', provenance: 'synthetic', quote: null }],
    rooms: [{ id: 'A', sqft: 155, private_bath: true }, { id: 'B', sqft: 135 }, { id: 'C', sqft: 125 }] }),
  L({ id: 'syn-state-loft', name: 'State St loft 1BR', neighborhood: 'State Street', lat: 42.2774, lon: -83.7408,
    rent: 1780, rent_basis: 'unit', bedrooms: 1, baths: 1, sqft: 700, building_type: 'apartment', year_built: 2012, heating: 'heat_pump',
    furnished: true, in_unit_laundry: true, parking_monthly: 175, pets_allowed: true, utilities_included: ['water', 'internet'], amenities: ['gym'] }),
  L({ id: 'syn-briarwood-1br', name: 'Briarwood-area 1BR', neighborhood: 'South / Briarwood', lat: 42.2448, lon: -83.7432,
    rent: 1010, rent_basis: 'unit', bedrooms: 1, baths: 1, sqft: 720, building_type: 'apartment', year_built: 1979, heating: 'electric_resistance',
    furnished: false, in_unit_laundry: false, parking_monthly: 0, pets_allowed: true, amenities: ['pool'] }),
  L({ id: 'syn-coop-room', name: 'Student co-op room (meals included)', neighborhood: 'North Burns Park', lat: 42.2712, lon: -83.7262,
    rent: 1050, rent_basis: 'bed', bedrooms: 20, baths: 6, building_type: 'coop', year_built: 1915, heating: 'gas',
    furnished: true, in_unit_laundry: true, parking_monthly: 0, pets_allowed: false, board_included: true,
    utilities_included: ['heat', 'electric', 'water', 'gas', 'internet', 'trash'], amenities: ['shared kitchen', 'meals'],
    notes: `${SYN_NOTE} Charge includes board (food) — compare against rent + groceries.` }),
];

const ev = (label: string, building_id: string, days: Event['days'], start_min: number, end_min: number, fixed = true): Event => ({
  label, building_id, point: null, days, start_min, end_min, fixed, source_quote: null, provenance: fixed ? 'user' : 'assumed',
});

export const DEFAULT_PROFILE: Profile = {
  events: [],
  template_id: null,
  modes: ['walk', 'bus'],
  rent_cap: 1500,
  all_in_cap: null,
  bedrooms_min: 0,
  household_size: 1,
  max_single_trip_min: null,
  needs_parking: false,
  pet: false,
  hourly_wage: 15,
  value_of_time: null,
  value_of_time_range: null,
  winter_aversion: 1,
  late_night_weight: 1,
  weights: { cash: 0.45, time: 0.35, late_night: 0.1, fit: 0.1 },
  preferences: {},
  season: 'fall',
  month: null,
};

export const MOCK_TEMPLATES: ScheduleTemplate[] = [
  {
    id: 'eecs-junior', name: 'EECS junior (typical)', provenance: 'assumed',
    source: 'Illustrative template — not drawn from registrar data',
    description: 'Two upper-level EECS courses on North, one humanities requirement on Central, discussion sections that vary.',
    slots: [
      [ev('EECS core lecture', 'bbb', ['M', 'W'], 630, 720, false), ev('EECS core lecture', 'eecs', ['T', 'R'], 540, 630, false)],
      [ev('EECS elective', 'eecs', ['T', 'R'], 750, 840, false), ev('EECS elective', 'frb', ['M', 'W'], 810, 900, false)],
      [ev('Humanities requirement', 'angell', ['T', 'R'], 600, 690, false), ev('Humanities requirement', 'mason', ['M', 'W', 'F'], 720, 780, false), ev('Humanities requirement', 'angell', ['M', 'W'], 960, 1050, false)],
      [ev('Discussion', 'ggbrown', ['F'], 570, 630, false), ev('Discussion', 'dude', ['R'], 1020, 1080, false)],
    ],
  },
  {
    id: 'lsa-sophomore', name: 'LSA sophomore (typical)', provenance: 'assumed',
    source: 'Illustrative template — not drawn from registrar data',
    description: 'Mostly Central Campus; one science lab that can land on North or Central.',
    slots: [
      [ev('Intro econ', 'angell', ['M', 'W'], 600, 690, false), ev('Intro econ', 'mason', ['T', 'R'], 690, 780, false)],
      [ev('Science lab', 'chem', ['T'], 780, 960, false), ev('Science lab', 'ggbrown', ['R'], 780, 960, false)],
      [ev('Writing seminar', 'angell', ['M', 'W', 'F'], 540, 600, false), ev('Writing seminar', 'hatcher', ['T', 'R'], 870, 960, false)],
    ],
  },
  {
    id: 'ross-bba', name: 'Ross BBA junior (typical)', provenance: 'assumed',
    source: 'Illustrative template — not drawn from registrar data',
    description: 'Core at Ross, one elective that may be on North.',
    slots: [
      [ev('BBA core', 'ross', ['M', 'W'], 510, 600, false), ev('BBA core', 'ross', ['T', 'R'], 600, 690, false)],
      [ev('Elective', 'ross', ['T', 'R'], 840, 930, false), ev('Elective', 'dude', ['M', 'W'], 900, 990, false)],
    ],
  },
];

export const MOCK_DEMO_PROFILES: DemoProfile[] = [
  {
    id: 'maya-eecs',
    name: 'Maya — EECS junior, late-night UgLi studier',
    description: 'Classes on North, a Ross minor course on Central, a weekend café shift in Kerrytown, and late nights at the UgLi.',
    narrative: [
      'Notice the cheapest-rent room is not the cheapest week.',
      'Turn on Bike, or drop the late-night UgLi blocks, and watch #1 change (mock engine).',
      'Set value of time to $0 for a cash-only ranking: the lowest-rent room takes #1.',
      'Switch Fall to Winter: walking gets more expensive and heating bands widen.',
    ],
    profile: {
      ...DEFAULT_PROFILE,
      template_id: 'eecs-junior',
      hourly_wage: 15,
      value_of_time_range: [4, 20],
      events: [
        { ...ev('EECS 281 lecture', 'bbb', ['M', 'W', 'F'], 540, 630), source_quote: 'EECS 281 MWF 9-10:30 in BBB', provenance: 'user' },
        { ...ev('Lab', 'ggbrown', ['T'], 540, 720), source_quote: 'lab Tuesday 9 to noon in GG Brown' },
        { ...ev('Ross minor course', 'ross', ['T', 'R'], 780, 870), source_quote: 'Ross class TTh 1-2:30' },
        { ...ev('Gym', 'ccrb', ['M', 'W'], 1050, 1110), source_quote: 'gym at CCRB Mon/Wed 5:30' },
        { ...ev('Study at the UgLi', 'ugli', ['M', 'T', 'W', 'R'], 1230, 1500), source_quote: 'UgLi most weeknights until 1am' },
        { ...ev('Café shift', 'kerrytown', ['S'], 600, 900), source_quote: 'café job in Kerrytown Saturdays 10-3' },
      ],
    },
  },
  {
    id: 'jordan-lsa',
    name: 'Jordan — LSA sophomore, Central Campus only',
    description: 'All classes on Central; works at University Hospital twice a week; cash matters most.',
    narrative: ['Set value of time to $0 to see a cash-only ranking.'],
    profile: {
      ...DEFAULT_PROFILE,
      template_id: 'lsa-sophomore',
      rent_cap: 1100,
      hourly_wage: 13,
      events: [
        ev('Intro econ', 'angell', ['M', 'W'], 600, 690),
        ev('Writing seminar', 'angell', ['M', 'W', 'F'], 540, 600),
        ev('Hospital job', 'uh', ['T', 'R'], 960, 1200),
        ev('Hatcher study', 'hatcher', ['S', 'U'], 780, 1020),
      ],
    },
  },
];

export const MOCK_MANIFEST: Manifest = {
  provider: 'mock',
  warning: 'MOCK mode — travel times use a simplified walk + 10/20/30-min-headway bus model, not real timetables.',
  engine_version: 'web-mock-0.1',
  feeds: [
    { name: 'TheRide (AAATA) GTFS — data/raw/aaata_gtfs/gtfs.zip', valid_from: '2026-01-25', valid_to: '2026-08-22', used_service_date: 'n/a in mock' },
    { name: 'U-M Transit GTFS (MobilityDatabase mdb-2072, S1000095)', valid_from: '2026-05-03', valid_to: '2026-08-22', used_service_date: 'n/a in mock' },
    { name: 'U-M Transit GTFS (mdb-416, 2021–22 term, S1000060)', valid_from: '2021-12-19', valid_to: '2022-04-30', used_service_date: 'n/a in mock' },
  ],
  assumptions: {
    walk_speed_mps: 1.34, walk_detour: 1.3, bus_speed_kmh: 22, headway_day_min: 10, headway_evening_min: 20, headway_late_min: 30,
    no_service: '02:30–06:30', vot_share_of_wage: 0.5, late_night_usd_per_min: 0.1,
  },
};

export const MOCK_METHODS: MethodsResult = {
  sources: [
    { name: 'TheRide (AAATA) GTFS', kind: 'Bus timetables', valid: '2026-01-25 → 2026-08-22 (calendar.txt)', note: 'data/raw/aaata_gtfs/gtfs.zip; routes include 4 Washtenaw, 5 Packard, 6 Ellsworth–State, 23 Plymouth, 62 U-M–State.' },
    { name: 'U-M Transit (Blue Bus) GTFS', kind: 'Bus timetables', valid: '2026-05-03 → 2026-08-22 (feed_info.txt, S1000095)', note: 'Summer feed: some term routes (e.g. BB/CN frequency) differ in fall. The engine must use a term-time feed for fall claims.' },
    { name: 'U-M Transit GTFS 2021–22 term', kind: 'Bus timetables (historical)', valid: '2021-12-19 → 2022-04-30 (S1000060)', note: 'Used only to sanity-check late-night term service (e.g. Bursley-Baits).' },
    { name: 'Overture Maps transportation', kind: 'Street & footway network', date: 'release 2026-11-07', license: 'ODbL-1.0 (OSM-derived)', note: 'Basemap on this page and the walk graph.' },
    { name: 'NOAA GHCN-Daily USC00200230 & 1991–2020 Normals', kind: 'Weather', note: 'Ann Arbor station; drives seasonal walk penalty and heating-degree utility bands.' },
    { name: 'Listings', kind: 'Housing', note: 'All listings in mock mode are SYNTHETIC. Live mode shows observed listings with source URL and observation date.' },
  ],
  assumptions: [
    { key: 'vot_share', label: 'Value of time as share of wage', value: 0.5, unit: '× wage', range: [0.25, 1.0], provenance: 'assumed', source: 'Transport-appraisal rule of thumb; adjustable' },
    { key: 'walk_weight', label: 'Walking minute weight', value: 1.5, unit: '× in-vehicle', range: [1.2, 2.0], provenance: 'assumed' },
    { key: 'wait_weight', label: 'Waiting minute weight', value: 2.0, unit: '× in-vehicle', range: [1.5, 2.5], provenance: 'assumed' },
    { key: 'winter_walk', label: 'Winter walking penalty', value: 0.3, unit: '+ share per aversion unit', range: [0.1, 0.5], provenance: 'assumed' },
    { key: 'late_night', label: 'Late-night outdoor minute cost', value: 0.1, unit: 'USD/min', range: [0, 0.3], provenance: 'assumed' },
    { key: 'buffer', label: 'Arrival buffer', value: 5, unit: 'min', range: [0, 10], provenance: 'assumed' },
    { key: 'weeks', label: 'Weeks per month', value: 4.33, unit: 'wk/mo', provenance: 'computed' },
  ],
  equations: [
    { name: 'All-in monthly cost', latex: 'C_{\\text{all-in}} = \\underbrace{R + F + U + P}_{\\text{cash}} + \\underbrace{v\\cdot \\tfrac{52}{12}\\cdot \\tfrac{T_{\\text{gen}}}{60}}_{\\text{time value}} + \\underbrace{\\lambda\\, N_{22}}_{\\text{late night}}', explanation: 'Rent R, fees F, utilities U, parking P, value of time v ($/h), weekly generalized minutes T_gen, late-night outdoor minutes N_22.' },
    { name: 'Generalized minutes', latex: 'T_{\\text{gen}} = \\sum_{\\text{trips}} \\big( w_{\\text{walk}}\\,s\\,t_{\\text{walk}} + w_{\\text{wait}}\\,t_{\\text{wait}} + t_{\\text{ride}} + 5\\,n_{\\text{xfer}} \\big)', explanation: 's is the seasonal walk penalty (1 + 0.3·winter aversion in winter).' },
    { name: 'Value-of-time breakeven', latex: 'v^{*} = \\frac{\\text{cash}_B - \\text{cash}_A + \\lambda (N_B - N_A)}{(T_A - T_B)\\cdot \\tfrac{52}{12\\cdot 60}}', explanation: 'A and B tie at v*. Below v* the cheaper-cash home wins.' },
    { name: 'Envy-free rent split', latex: 'v_i(r_i) - p_{r_i} \\ge v_i(r_j) - p_{r_j}\\ \\ \\forall i,j, \\quad \\sum_r p_r = R_{\\text{total}}', explanation: 'Welfare-maximizing room assignment plus prices from the difference-constraint system; we pick the split that maximizes the worst-off roommate.' },
    { name: 'Monte Carlo standard error', latex: '\\mathrm{SE} = \\sqrt{\\hat p(1-\\hat p)/N}', explanation: 'Reported for the share of plausible semesters in which the top home is #1.' },
  ],
  limitations: [
    'Mock mode: travel times are a simplified model, not real timetables. Start the API for timetable-based results.',
    'Utility bands are estimates from building type, heating fuel and season — not bills.',
    'Listings are curated or synthetic; no availability claims.',
    'Schedule templates are illustrative, not registrar data.',
    'Legal flags are prompts to verify with Student Legal Services — not legal advice.',
  ],
};
