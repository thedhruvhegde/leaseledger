"""Monthly per-person ledger (USD/month) for one listing.

  rent_pp      = rent                      (rent_basis "bed")
               = rent / max(household_size, bedrooms)  (rent_basis "unit"; all bedrooms assumed filled)
  fees_pp      = sum_f amount_f x period_f / per_f, with period: monthly 1, annual 1/12, once 1/lease_term;
                 per: "unit" => divided by occupants, "person" => as is. Parking fees go to the parking line.
  utilities    = see utilities.py (interval band)
  parking      = needs_parking ? (parking_monthly | parking fee | UM permit/12 proxy) : 0
  insurance    = renters_insurance (unless a fee already covers it)
  transport    = bus fare x bus trips/week x weeks_per_month (= 0: Blue Bus free, TheRide free with MCard)
  food_offset  = -groceries (assumed) when Listing.board_included (co-op charge includes meals)
  time_value   = VOT x G_week/60 x weeks_per_month                 [not cash]
  late_night   = usd_per_outdoor_min x late_night_weight x N_week x weeks_per_month   [not cash]
  member_labor = VOT x labor_hours/week x weeks_per_month   [not cash; co-op work shifts; Listing value or
                 coop_labor_hours_week param for co-ops]
  amenity_gap  = fit_usd_per_importance x sum_k importance_k x (1 - has_k)          [not cash; score only]
  cash_total   = rent + fees + utilities + parking + insurance + transport + food_offset
  all_in_total = cash_total + time_value + late_night + member_labor
  score        = all_in_total + amenity_gap      (the money-metric ranking key; lower is better)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from ledger.schemas import LedgerLine, Listing, Mode, Profile, Provenance

from .params import Params
from .tours import ListingCommute
from .utilities import UtilityEstimate, occupants
from .valuation import VOT, Multipliers


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def amenity_fit(listing: Listing, prefs: dict[str, float]) -> tuple[float, list[str], list[str], float]:
    """Return (fit in [0,1], missing prefs, unknown prefs, importance-weighted missing sum).

    has_k = 1 if the listing provides preference k (boolean field True or amenity string match), else 0;
    unknown (field None) counts as missing (conservative) but is listed separately for the UI.
    """
    if not prefs:
        return 1.0, [], [], 0.0
    amen = {_norm(a) for a in listing.amenities}
    bool_fields = {"in_unit_laundry": listing.in_unit_laundry, "furnished": listing.furnished,
                   "pets_allowed": listing.pets_allowed, "pet_friendly": listing.pets_allowed}
    missing, unknown = [], []
    tot = got = 0.0
    for k, imp in sorted(prefs.items()):
        imp = max(0.0, min(1.0, float(imp)))
        if imp <= 0:
            continue
        nk = _norm(k)
        tot += imp
        if nk in bool_fields and bool_fields[nk] is not None:
            has = bool(bool_fields[nk]) or nk in amen
        elif nk == "parking":
            has = listing.parking_monthly is not None or any("parking" in a for a in amen)
        elif nk in ("heat_included", "utilities_included"):
            has = "heat" in listing.utilities_included
        else:
            has = nk in amen or any(nk in a for a in amen)
            if not has and nk in bool_fields:
                unknown.append(k)
        if has:
            got += imp
        else:
            missing.append(k)
    if tot <= 0:
        return 1.0, [], [], 0.0
    return got / tot, missing, unknown, tot - got


@dataclass
class LedgerCalc:
    lines: list[LedgerLine]
    rent_pp: float
    fees_pp: float
    utilities: float
    parking: float
    insurance: float
    transport: float
    time_usd: float
    time_h_week: float
    late_usd: float
    late_min_week: float
    amenity_gap: float
    fit: float
    cash: float
    cash_low: float
    cash_high: float
    all_in: float
    score: float
    usd_per_gen_hour: float          # weeks_per_month (time_usd = VOT x gen_h x this)
    late_rate: float                 # USD per weekly late-night minute per month
    labor_h_week: float = 0.0        # co-op work shifts, valued at VOT (linear in VOT like travel)
    labor_usd: float = 0.0
    labor_from_param: bool = False   # True => hours sampled in robustness
    food: float = 0.0                # food offset (negative) included in cash
    missing_prefs: list[str] = field(default_factory=list)
    unknown_prefs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_ledger(listing: Listing, profile: Profile, params: Params, vot: VOT, mult: Multipliers,
                 mult_lo: Multipliers, mult_hi: Multipliers, commute: ListingCommute,
                 util: UtilityEstimate, months_label: str) -> LedgerCalc:
    warns: list[str] = []
    occ = occupants(listing, profile.household_size)
    wpm = params.v("calendar.weeks_per_month")
    O, A, C = Provenance.observed, Provenance.assumed, Provenance.computed
    lprov = {"observed": Provenance.observed, "user": Provenance.user}.get(listing.provenance, Provenance.synthetic)
    lines: list[LedgerLine] = []

    # ---- rent
    if listing.rent_basis == "bed":
        div, how = 1, "advertised per bed"
    else:
        div = max(profile.household_size, listing.bedrooms, 1)
        how = "advertised per unit" + (f" / {div} people" if div > 1 else "")
        if listing.bedrooms > profile.household_size:
            how += f" (assumes all {listing.bedrooms} bedrooms are filled; your group is {profile.household_size})"
        cap = max(listing.bedrooms, 1)
        if cap < profile.household_size:
            warns.append(f"{listing.id}: {listing.bedrooms} bedroom(s) for a household of {profile.household_size}.")
    rent = listing.rent / div
    rlo = (listing.rent_low if listing.rent_low is not None else listing.rent) / div
    rhi = (listing.rent_high if listing.rent_high is not None else listing.rent) / div
    lines.append(LedgerLine(key="rent", label="Rent", usd_month=rent, low=min(rlo, rent), high=max(rhi, rent),
                            provenance=lprov, note=how + (" (advertised range)" if listing.rent_is_range else "")))

    # ---- fees
    term = max(1, listing.lease_term_months or 12)
    fee_total = fee_parking = fee_ins = 0.0
    fee_notes = []
    for f in listing.fees:
        per_month = f.amount * {"monthly": 1.0, "annual": 1 / 12, "once": 1 / term}[f.period]
        if f.per == "unit":
            per_month /= occ
        lab = f.label.lower()
        if "parking" in lab:
            fee_parking += per_month
            continue
        if "insurance" in lab:
            fee_ins += per_month
        fee_total += per_month
        fee_notes.append(f"{f.label} ${f.amount:g}/{f.period}{' per unit' if f.per == 'unit' else ''}")
    if listing.fees:
        lines.append(LedgerLine(key="fees", label="Fees (monthly-ized)", usd_month=fee_total, low=fee_total,
                                high=fee_total, provenance=lprov if lprov == Provenance.synthetic else O,
                                note="; ".join(fee_notes) + (f"; one-time fees spread over {term} months" if any(
                                    f.period == "once" for f in listing.fees) else "")))

    # ---- utilities
    unote = (f"{months_label}: " + ", ".join(f"{k} ${v:.0f}" for k, v in util.components.items() if v > 0.005)
             + f"; split {util.occupants} way(s); annual average ${util.annual_avg:.0f}")
    if util.notes:
        unote += "; " + "; ".join(util.notes)
    lines.append(LedgerLine(key="utilities", label="Utilities (estimated)", usd_month=util.value, low=util.low,
                            high=util.high, provenance=Provenance.estimated, note=unote))

    # ---- parking (home spot + UM campus permit)
    parking = plo = phi = 0.0
    if profile.needs_parking:
        pr = params.p("um_parking_permit_usd_year")
        if listing.parking_monthly is not None:
            home, pn = listing.parking_monthly, f"home spot ${listing.parking_monthly:,.0f}/mo (listing)"
        elif fee_parking > 0:
            home, pn = fee_parking, f"home spot ${fee_parking:,.0f}/mo (listing fee)"
        else:
            home, pn = 0.0, "home parking price not stated (counted $0; confirm with landlord)"
        parking, plo, phi = home + pr.value / 12, home + pr.low / 12, home + pr.high / 12
        lines.append(LedgerLine(key="parking", label="Parking", usd_month=parking, low=plo, high=phi,
                                provenance=Provenance.estimated,
                                note=f"{pn} + UM campus permit ${pr.value:,.0f}/yr / 12 ({pr.provenance})"))

    # ---- insurance
    insurance = ilo = ihi = 0.0
    if fee_ins <= 0:
        ip = params.p("renters_insurance_usd_month")
        insurance, ilo, ihi = ip.value, ip.low, ip.high
        lines.append(LedgerLine(key="insurance", label="Renters insurance", usd_month=insurance, low=ilo, high=ihi,
                                provenance=A, note=ip.note))

    # ---- board (co-op meals) offset
    food = flo = fhi = 0.0
    if getattr(listing, "board_included", False):
        fo = params.p("engine.food_offset_usd_person_month")
        food, flo, fhi = -fo.value, -fo.high, -fo.low
        lines.append(LedgerLine(key="food_offset", label="Meals included (groceries offset)", usd_month=food,
                                low=flo, high=fhi, provenance=A,
                                note=(f"charge includes meals; compare against rent + groceries: -${fo.value:,.0f}/mo "
                                      f"assumed grocery spend (${fo.low:,.0f}-${fo.high:,.0f})")))

    # ---- transport cash
    fare = params.p("bus_fare_student")
    bus_trips = sum(1 for t in commute.all_trips() if t.trip.mode == Mode.bus)
    transport = fare.value * bus_trips * wpm
    lines.append(LedgerLine(key="transport_cash", label="Bus fares", usd_month=transport, low=fare.low * bus_trips * wpm,
                            high=fare.high * bus_trips * wpm, provenance=Provenance(fare.provenance) if fare.provenance in Provenance.__members__ else A,
                            note=f"{bus_trips} bus trips/week; {fare.note}"))

    cash = rent + fee_total + util.value + parking + insurance + transport + food
    cash_lo = lines[0].low + fee_total + util.low + plo + ilo + fare.low * bus_trips * wpm + flo
    cash_hi = lines[0].high + fee_total + util.high + phi + ihi + fare.high * bus_trips * wpm + fhi

    # ---- time value (not cash)
    gen_h = commute.weekly_gen_min / 60.0
    gen_lo = float(commute.comp @ mult_lo.vector()) / 60.0
    gen_hi = float(commute.comp @ mult_hi.vector()) / 60.0
    time_usd = vot.value * gen_h * wpm
    lines.append(LedgerLine(key="time_value", label="Travel time (valued)", usd_month=time_usd,
                            low=vot.low * gen_lo * wpm, high=vot.high * gen_hi * wpm, provenance=C, in_cash_total=False,
                            note=(f"{commute.weekly_total_min / 60:.1f} h/wk door-to-door "
                                  f"({commute.comp[1] / 60:.1f} h walking, {commute.comp[2] / 60:.1f} h waiting at stops, "
                                  f"{commute.comp[0] / 60:.1f} h riding, {commute.comp[5]:.0f} min forced early arrival "
                                  f"charged at {mult.early:g}x) = {gen_h:.1f} generalized h/wk x ${vot.value:.2f}/h x "
                                  f"{wpm:g} wk/mo")))

    # ---- late night (not cash)
    lp = params.p("late_night.usd_per_outdoor_min")
    late_rate = lp.value * profile.late_night_weight * wpm
    late_usd = late_rate * commute.weekly_late_min
    lines.append(LedgerLine(key="late_night", label="Late-night outdoor exposure", usd_month=late_usd,
                            low=lp.low * profile.late_night_weight * wpm * commute.weekly_late_min,
                            high=lp.high * profile.late_night_weight * wpm * commute.weekly_late_min,
                            provenance=A, in_cash_total=False,
                            note=(f"{commute.weekly_late_min:.0f} min/wk walking or waiting outdoors after 22:00 x "
                                  f"${lp.value:.2f}/min x weight {profile.late_night_weight:g} x {wpm:g} wk/mo")))

    # ---- amenity gap (score only)
    fit, missing, unknown, miss_imp = amenity_fit(listing, profile.preferences)
    fp = params.p("engine.fit_usd_per_importance")
    gap = fp.value * miss_imp
    if profile.preferences:
        lines.append(LedgerLine(key="amenity_gap", label="Missing preferences", usd_month=gap, low=fp.low * miss_imp,
                                high=fp.high * miss_imp, provenance=A, in_cash_total=False,
                                note=(("missing: " + ", ".join(missing)) if missing else "all preferences met")
                                + f"; ${fp.value:g}/mo per unit of importance (assumed)"))
    # ---- member labor (co-op work shifts; not cash)
    labor_h, labor_usd, from_param = 0.0, 0.0, False
    if listing.member_labor_hours_week is not None or listing.building_type == "coop":
        lp_ = params.p("engine.coop_labor_hours_week")
        if listing.member_labor_hours_week is not None:
            labor_h, hlo, hhi, src = float(listing.member_labor_hours_week), float(listing.member_labor_hours_week), \
                float(listing.member_labor_hours_week), "hours from the listing"
            lprov2 = lprov
        else:
            labor_h, hlo, hhi, src, from_param = lp_.value, lp_.low, lp_.high, lp_.note, True
            lprov2 = A
        labor_usd = vot.value * labor_h * wpm
        if labor_h > 0:
            lines.append(LedgerLine(key="member_labor", label="Co-op work shifts (valued)", usd_month=labor_usd,
                                    low=vot.low * hlo * wpm, high=vot.high * hhi * wpm, provenance=lprov2,
                                    in_cash_total=False,
                                    note=f"{labor_h:g} h/wk x ${vot.value:.2f}/h x {wpm:g} wk/mo; {src}"))
    all_in = cash + time_usd + late_usd + labor_usd
    return LedgerCalc(lines, rent, fee_total, util.value, parking, insurance, transport, time_usd, gen_h, late_usd,
                      commute.weekly_late_min, gap, fit, cash, cash_lo, cash_hi, all_in, all_in + gap,
                      wpm, late_rate, labor_h_week=labor_h, labor_usd=labor_usd, labor_from_param=from_param,
                      food=food, missing_prefs=missing, unknown_prefs=unknown, warnings=warns)
