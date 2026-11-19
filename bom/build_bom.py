#!/usr/bin/env python3
"""E8-200 bill of materials for ONE prototype (WP P, pass 2).

Inputs (read-only):  bom/catalog.json (prices, sources), cad/parts.json (every made and bought part with material,
mass, envelope, qty), design/selected_design.json (frozen design), fea/materials.json (laminate Vf and densities),
sizing/results/cost_breakdown.json (for the reconciliation).
Outputs: bom/BOM.csv, bom/BOM.md, docs/data/bom.json.

Rules: every unit price comes from bom/catalog.json (source link) or is typed 'estimate' with the basis in the row.
Currency: catalog prices are kept in the published currency; converted here with the same FX as WP D (sizing/data.py:
EUR x 1.10, GBP x 1.27 - an estimate, to be replaced by the rate on the order date).
Raw-material quantities are derived from the CAD part masses and envelopes with the rules in RULES below.

    python3 bom/build_bom.py
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = {i["id"]: i for i in json.loads((ROOT / "bom/catalog.json").read_text())["items"]}
CADJ = json.loads((ROOT / "cad/parts.json").read_text())
PARTS = CADJ["parts"]
PID = {p["id"]: p for p in PARTS}
DES = json.loads((ROOT / "design/selected_design.json").read_text())
FX = {"USD": 1.0, "EUR": 1.10, "GBP": 1.27}
_cad_des = CADJ.get("design", {}) or {}
CAD_STALE = abs((_cad_des.get("mtow_kg") or 0) - DES["mass_kg"]["mtow"]) > 1.0
CAD_NOTE = (f"WARNING: cad/parts.json was generated for '{_cad_des.get('name')}' (MTOW {_cad_des.get('mtow_kg')} kg), not for the frozen "
            f"design '{DES['name']}' (MTOW {DES['mass_kg']['mtow']:.1f} kg). Purchased-item counts follow the design; made-part "
            "material quantities, the cut list and the per-part tables follow the CAD and must be regenerated after the CAD rebuild.") if CAD_STALE else ""
CHECKED = "2026-11-15"

RULES = {
    "fibre_density": {"carbon": 1780.0, "eglass": 2550.0},          # kg/m3, standard fibre values (estimate)
    "laminate": {"cf_fabric_wet": (0.45, 1450.0), "cf_ud_wet": (0.50, 1500.0), "eglass_fabric_wet": (0.40, 1800.0)},  # Vf, rho (fea/materials.json)
    "areal_kg_m2": {"cf_fabric_wet": 0.193, "cf_ud_wet": 0.300, "eglass_fabric_wet": 0.303},   # MAT-CF-FABRIC, MAT-UD-CF, MAT-GLASS-7781
    "fabric_scrap": {"cf_fabric_wet": 0.25, "cf_ud_wet": 0.15, "eglass_fabric_wet": 0.25},      # cost.py basis (estimate)
    "resin_waste": 0.30,               # mixing, squeegee, bagging absorption (estimate)
    "resin_bonding_allowance": 0.25,   # flox fillets, tapes, inserts, bonding of cores (estimate, fraction of laminating resin)
    "sandwich": {"t_face": 0.0005, "faces": 2, "t_core": 0.010, "rho_core": 80.0},  # CAD material string "2 x 0.5 mm on pvc_h80 10 mm"
    "skin_on_xps_laminate_fraction": 0.60,   # cost.py split for 'skin on xps' parts (estimate)
    "core_nest_efficiency": 0.75,      # CNC nesting of flat sandwich parts on 2440 x 1220 sheets (estimate)
    "foam_block_buy_factor": 1.15,     # hot-wire / block buy volume over the envelope volume (estimate)
    "metal_plate_nest_efficiency": 0.65,
    "metal_bar_buy_factor": 1.15,      # bar/block stock volume over the part envelope (upper bound)
    "buy_to_fly_bar": 3.0,             # stock mass / finished mass for machined bar parts (sizing/cost.py basis, estimate)
    "al_usd_per_kg": 149.99 / 6.37,    # MAT-AL-PLATE (Zoro 1/2 x 12 x 24 6061 plate)
    "al7075_usd_per_kg": 269.97 / 9.895,  # MAT-AL7075-PLATE (21.816 lb)
    "mgs_kit_kg": 3.785 * 1.16 * 1.40,  # 1 gal L285 (density ~1.16, estimate) + 40 phr hardener -> ~6.1 kg mixed
    "bag_area_factor": 1.3,            # bag/breather/peel-ply area over laminate area incl. overlaps (estimate)
    "yd2_per_m2_50in": 1 / (1.27 * 0.9144),
    "yd2_per_m2_60in": 1 / (1.524 * 0.9144),
}


def cat_price(cid: str, which: str = "mid"):
    """(USD unit price, type, source, basis) from the catalog."""
    it = CAT[cid]
    p = it["price"]
    fx = FX[p.get("currency", "USD")]
    src = p.get("source") or (it.get("sources") or [""])[0]
    if p.get("value") is not None:
        cur = p.get("currency", "USD")
        basis = f"{cid}: {p['type']} {cur} {p['value']}" + (f" ({p['note']})" if p.get("note") else "")
        return p["value"] * fx, p["type"], src, basis
    est = p.get("estimate")
    if est is None:
        return None, "quote_required", src, f"{cid}: quote required, no published figure"
    v = 0.5 * (est[0] + est[1]) if isinstance(est, list) else est
    return v * fx, "estimate (quote required)", src, f"{cid}: quote required; catalog estimate {p.get('currency','USD')} {est}" + (" (mid)" if isinstance(est, list) else "")


ROWS: list[dict] = []
LEAD_QUOTE = "made to order - lead time to be confirmed in the quote (QUOTES_TO_REQUEST.md)"
EXP_EU = "EU origin: ask vendor for EU dual-use / ECCN classification and export documentation to the US"
EXP_CN = "China origin: export licence required from 18 Nov 2026 for heavy-lift motors/ESCs/large blades (catalog note)"
EXP_US = "US domestic purchase"


def row(category, item, qty, unit, price_usd, ptype, source, *, cid="", cad="", lead="stock item per vendor page - confirm",
        export=EXP_US, note="", group="purchased"):
    ROWS.append(dict(group=group, category=category, item=item, catalog_id=cid, cad_ids=cad, qty=round(qty, 3), unit=unit,
                     unit_price_usd=round(price_usd, 2) if price_usd is not None else None,
                     total_usd=round(qty * price_usd, 2) if price_usd is not None else None,
                     price_type=ptype, source=source, lead_time=lead, export_control=export, note=note))


def crow(category, cid, qty, unit="each", cad="", lead="stock item per vendor page - confirm", export=EXP_US, note="", item=None, group="purchased"):
    v, t, s, b = cat_price(cid)
    row(category, item or CAT[cid]["name"], qty, unit, v, t, s, cid=cid, cad=cad, lead=lead, export=export,
        note=(note + "; " if note else "") + b, group=group)


def est(category, item, qty, unit, usd, basis, source="", cad="", lead="stock item - confirm", export=EXP_US, group="purchased"):
    row(category, item, qty, unit, usd, "estimate", source, cad=cad, lead=lead, export=export, note="estimate: " + basis, group=group)


def qty_cad(*ids):
    return sum(PID[i]["qty"] for i in ids if i in PID)


# =================================================================================================== purchased items
nb = DES["battery"]
n_cells = nb["series"] * nb["parallel"]
n_packs = nb["independent_packs"]
n_lift = DES["lift_rotors"]["count"]

# --- propulsion (counts, motor types and sizes from design/selected_design.json)
LR, PU = DES["lift_rotors"], DES["pusher"]
n_push = PU.get("count", 1)
LIFT_MOT = LR["motor"]["name"].split(":")[0].strip()
PUSH_MOT = PU["motor"]["name"].split(":")[0].strip()
ns_ = DES["battery"]["series"]
GEO = json.loads((ROOT / "design/geometry.json").read_text())
_spins = [q.get("spin") for q in GEO.get("pushers", [])]
counter_rot = len(set(_spins)) > 1
if LIFT_MOT == PUSH_MOT:
    crow("Propulsion", LIFT_MOT, n_lift + n_push, cad="MOT-L, MOT-PB", lead=LEAD_QUOTE, export=EXP_EU,
         note=f"{n_lift} lift + {n_push} pusher; winding for the {ns_}s bus to be confirmed (QUOTES_TO_REQUEST.md)")
else:
    crow("Propulsion", LIFT_MOT, n_lift, cad="MOT-L", lead=LEAD_QUOTE, export=EXP_EU,
         note=f"lift; winding for the {ns_}s bus (525-756 V) and duty points to be confirmed (QUOTES_TO_REQUEST.md item 1)")
    crow("Propulsion", PUSH_MOT, n_push, cad="MOT-PB", lead=LEAD_QUOTE, export=EXP_EU,
         note=f"boom-tail pushers at {PU['rpm_cruise']:.0f} rpm cruise; continuous torque at 2,000-2,100 rpm to be confirmed (QUOTES_TO_REQUEST.md item 2)")
crow("Propulsion", "INV-HBCI400800", n_lift + n_push, cad="INV-L, INV-PB", lead=LEAD_QUOTE, export=EXP_EU,
     note=f"{n_lift} lift + {n_push} pusher; a smaller 800 V unit is requested from MGM")
crow("Propulsion", "PROP-EPROPS-UAV-ADJ", n_lift, cad="ROT-CW, ROT-CCW", lead=LEAD_QUOTE, export="EU (FR) origin: ask vendor",
     item=f"E-PROPS ground-adjustable carbon lift rotor {LR['diameter_m']:.2f} m, {LR['blades']}-blade, with hub ({n_lift//2} CW + {n_lift//2} CCW)",
     note=f"{LR['diameter_m']:.2f} m = {LR['diameter_m']/0.0254:.1f} in, within the 74.8 in matched CW/CCW range (E-PROPS UAV page); price reference = manned Durandal-2 two-blade list; UAV/VTOL quote required")
pd_in = PU["diameter_m"] / 0.0254
PROP_ISSUE = (f"NOT AVAILABLE AS PUBLISHED: counter-rotating pair at {PU['diameter_m']:.2f} m ({pd_in:.1f} in) needs a CCW blade beyond the 75 in published CCW range") \
    if (pd_in > 75.0 and counter_rot) else ""
crow("Propulsion", "PROP-EPROPS-UAV-ADJ", n_push, cad="PROP-PCW", lead=LEAD_QUOTE, export="EU (FR) origin: ask vendor",
     item=f"E-PROPS ground-adjustable carbon pusher propeller {PU['diameter_m']:.2f} m, {PU['blades']}-blade, " + ("counter-rotating pair" if counter_rot else "both units the same rotation (one part)"),
     note=(PROP_ISSUE + "; " if PROP_ISSUE else "") + f"{pd_in:.1f} in, within the published E-PROPS range for this rotation; same price reference as the lift rotors")
row("Propulsion", "Rubber-metal sandwich isolator, cylindrical M8 (6 per lift-motor station)", 6 * n_lift, "each", 9.77, "retail",
    "https://www.123bearing.com/accessories/anti-vibration/ff/ff2540-8", cad="MP-ISO",
    note="FF2540-8 (25 x 40 mm, M8) as the priced reference; CAD calls for d38 x 25 mm - final rate/size from WP F modal tuning")

# --- battery and HV
crow("Battery and HV", "CELL-P50B", n_cells, cad="BAT-TIER1, BAT-TIER2", lead="1000+ tier, check stock",
     note=f"{n_packs} packs x {nb['series']}s{nb['parallel_per_pack']}p")
g10_area = n_cells * 0.0270 * 0.0234 * 2 * 1.15   # 27.0 x 23.4 mm cell grid (CAD BAT-TIER note), top + bottom plate, +15 % border
g10_sheets = math.ceil(g10_area / (0.3048 * 0.6096) / 0.80)
crow("Battery and HV", "MAT-G10", g10_sheets, unit="sheet", cad="BAT-TIER1, BAT-TIER2",
     note=f"cell holder plates top+bottom: {n_cells} cells on the 27.0 x 23.4 mm grid = {g10_area:.2f} m2 / 80 % nesting")
strip_m = n_packs * nb["series"] * 0.30
row("Battery and HV", "Nickel-plated copper bus strip 0.2 x ~30 mm", strip_m, "m", 8.99, "estimate", "https://www.ebay.com/itm/305567325562",
    cad="BAT-TIER1, BAT-TIER2", note="estimate: 0.30 m of strip per series link (layout to be drawn); price = copper 0.2 x 31 mm single-metre listing "
    "(MAT-CU-STRIP); bulk plated stock by quote")
crow("Battery and HV", "BMS-ORION2", n_packs, cad="BMS")
crow("Battery and HV", "HV-EV200", 2 * n_packs + 1, cad="HV-SW", note="2 per pack + 1 normally-closed bus-tie contactor")
crow("Battery and HV", "HV-FUSE", n_packs + n_lift + n_push, cad="HV-SW", note="1 main fuse per pack + 1 branch fuse per inverter")
est("Battery and HV", "Precharge relay + resistor set (per pack)", n_packs, "set", 150.0,
    "no source captured; small HV relay and power resistor per pack - quote with the contactors")
surlok_pair = cat_price("HV-CONN")[0] + 21.96 * FX["GBP"]
row("Battery and HV", "Amphenol SurLok Plus 8 mm HV connector pair (receptacle + plug)", 2 * (n_lift + n_push) + 4 * n_packs, "pair",
    surlok_pair, "retail", CAT["HV-CONN"]["price"]["source"], cid="HV-CONN",
    note="receptacle USD 13.13 + plug GBP 21.96 (DigiKey); 2 per inverter + 4 per pack")
hv_len = DES["systems"]["hv_cable_length_m"]
crow("Battery and HV", "HV-AL-CABLE", round(hv_len * 1.1), unit="m", cad="HV-BOOM, HV-WING, HV-RISER, HV-PUSH", lead=LEAD_QUOTE,
     export="ask vendor", note=f"{hv_len:.0f} m (design) + 10 % for routing/terminations")
est("Battery and HV", "Bimetal (Al-Cu) crimp lugs, contact grease, heat-shrink, fire sleeve, HV loom clips", 1, "set", 600.0,
    "no source captured; ~80 terminations - quote with the cable", cad="HV-BOOM, HV-WING, HV-RISER, HV-PUSH")
crow("Battery and HV", "HV-DCDC-MW", 4, cad="LV-DCDC", note="2 per HV bus side, 1.2 kW total, diode-ORed")
row("Battery and HV", "Mica sheet fire liner for battery boxes", n_packs, "box set", None, "quote_required", "",
    cad="BAT-BOX", note="no published price found; quote from an insulation supplier (QUOTES_TO_REQUEST.md)")

# --- thermal
row("Thermal", "Liquid cooling: 24 V electric coolant pump (Davies Craig EWP115 24 V class)", 2, "each", 339.0, "retail",
    "https://autopro.com.au/ap/Autopro-Category/Brands/Davies-Craig/Davies-Craig-EWP115-Nylon-Kit-24V---8026/p/SP139340", cad="COOL-PK",
    note="listing currency AUD shown as '$339.00' - converted 1:1 (conservative); one loop per boom")
row("Thermal", "Liquid-to-air cooler (CSF drive-motor inverter cooler class)", 2, "each", 122.99, "retail",
    "https://autoparts.com/product/573518", cad="COOL-PK", note="CSF #3678 listing; heat rejection to be checked by WP D/C for 4 inverters + motor jackets per boom")
if "EMRAX" in LIFT_MOT:
    est("Thermal", "Motor coolant loop per lift station: 16 mm hose up the pylon, fittings to the EMRAX ports, clamps", n_lift, "station", 120.0,
        "no source captured; COOL-MOT in the CAD - check pump/cooler capacity for the added motor heat (WP D/C)", cad="COOL-MOT")
est("Thermal", "Coolant hose 16 mm, manifolds, quick disconnects, clamps, coolant", 2, "boom set", 450.0,
    "no source captured; 2 x 7.5 m supply/return + 6 branches per boom (4 lift + 1 pusher inverter, motor jackets)", cad="COOL-LINE")

# --- safety
CHUTE_ID = (PID["CHUTE"]["material"].split("(")[-1].rstrip(")").strip() if "CHUTE" in PID and "CHUTE-" in PID["CHUTE"]["material"] else
            ("CHUTE-GRS1390" if DES["mass_kg"]["mtow"] > 1190 else "CHUTE-GRS1190" if DES["mass_kg"]["mtow"] > 1050 else "CHUTE-GRS990"))
crow("Safety", CHUTE_ID, 1, cad="CHUTE", lead=LEAD_QUOTE, export="EU (CZ) origin: rocket motor is an explosive (hazmat shipping, storage permit)",
     note=f"MTOW {DES['mass_kg']['mtow']:.0f} kg; Galaxy to confirm the variant (990 or 1190 kg) and opening load at this mass")
est("Safety", "Parachute risers / bridle to 3 hard points (Kevlar/nylon), tear-strip channel", 1, "set", 500.0,
    "no source captured; normally supplied by Galaxy with the installation - include in the quote", cad="CH-RISER", export="EU (CZ)")

# --- avionics and flight control
crow("Avionics and flight control", "FCC-VERONTE4X", 1, cad="AV-FCC", lead=LEAD_QUOTE, export="EU (ES) origin: autopilots may be dual-use controlled - ask Embention")
crow("Avionics and flight control", "FCC-CUBE-ORANGEP", 1, cad="AV-FCC", lead="in stock (IRLock page: 205 units)",
     note="uncrewed test phase and HIL bench")
crow("Avionics and flight control", "EFIS-DYNON-HDX7", 1, cad="AV-EFIS")
crow("Avionics and flight control", "EFIS-G5", 1, cad="AV-G5")
crow("Avionics and flight control", "XPDR-TAILBEACONX", 1, cad="AV-MISC")
crow("Avionics and flight control", "COM-TY91", 1, cad="AV-RADIO", export="UK origin: ask dealer", note="+ VAT where applicable")
crow("Avionics and flight control", "GNSS-HERE4", 2, cad="AV-GNSS", lead="in stock (IRLock page: 147 units)")
crow("Avionics and flight control", "AIRSPEED-MS4525", 2, cad="AV-MISC")
_nact = sum(PID[i]["qty"] for i in PID if i.endswith("-ACT"))
est("Avionics and flight control", f"Pilot inceptors (2 side-sticks, collective/throttle lever) and {_nact} control-surface servo-actuators",
    1, "set", 6000.0, f"WP D allowance (sizing/data.py systems_cost); CAD actuators: {', '.join(i for i in PID if i.endswith('-ACT'))}",
    cad="FC-STICK, FC-MISC, " + ", ".join(i for i in PID if i.endswith("-ACT")))
est("Avionics and flight control", "Secondary air data / AHRS (Dynon ADAHRS class), intercom, antennas", 1, "set", 2000.0,
    "WP D allowance (sizing/data.py systems_cost)", cad="AV-MISC")
row("Avionics and flight control", "24 V 20 Ah LiFePO4 backup battery (Bioenno BLF-2420A)", 1, "each", 369.99, "retail",
    "https://www.bioennopower.com/products/24v-20ah-lfp-battery-black-pvc-pack-charger", cad="LV-BATT", note="battery only")
row("Avionics and flight control", "Push-pull circuit breakers (TE/P&B W23 class)", 20, "each", 44.50, "retail",
    "https://www.aircraftspruce.com/catalog/pnpages/11-03928.php", cad="LV-PANEL", note="count estimate 20")
est("Avionics and flight control", "LV harness wire (Tefzel), connectors, switches, nav/strobe lights, panel hardware", 1, "set", 1300.0,
    "remainder of the WP D LV allowance USD 2,500 after battery and breakers (sizing/data.py)", cad="LV-PANEL, AV-MISC")

# --- cabin and gear (COTS)
crow("Cabin and landing gear", "CAB-HARNESS", 2, cad="HARN", export="ask dealer")
seat_track_in = qty_cad("SR") * PID["SR"]["envelope_mm"][0] / 25.4
v, t, s, b = cat_price("MAT-SEAT-TRACK")
row("Cabin and landing gear", "Seat track extrusion (Brownline style) cut to 4 x 600 mm", seat_track_in, "inch", v, t, s, cid="MAT-SEAT-TRACK",
    cad="SR", note="+ USD 30 cut fee (added as separate row)")
row("Cabin and landing gear", "Seat-track cut fee", 1, "order", 30.0, "retail", s, cid="MAT-SEAT-TRACK", cad="SR")
v, t, s, b = cat_price("CAB-CONFOR")
row("Cabin and landing gear", "CONFOR CF-45 foam 1 x 18 x 40 in (seat + back, 2 layers per seat)", 4, "piece", 90.0, "retail",
    "https://cumulus-soaring.com/store/confor-foam-blue-1x18x40", cid="CAB-CONFOR", cad="SEAT-CUSH")
pc = cat_price("CAB-PC-SHEET")
row("Cabin and landing gear", "Polycarbonate sheet 0.125 x 48 x 96 in (canopy CAN-F; rear window CAN-R and WIN-L)", 2, "sheet",
    pc[0] + 80.0, pc[1], pc[2], cid="CAB-PC-SHEET", cad="CAN-F, CAN-R, WIN-L", note="incl. USD 80 special-delivery surcharge per sheet")
crow("Cabin and landing gear", "LG-OLEO", qty_cad("LG-DAMP"), cad="LG-DAMP", lead=LEAD_QUOTE,
     note="short-stroke (80 mm) custom valving; spherical bearings at both eyes")
est("Cabin and landing gear", "Gear pivot pins 20 mm 4130 with bronze bushes, spherical rod ends for dampers", 4, "set", 60.0,
    "no source captured; machined/bought pins and bushes", cad="LG-PIN, LG-LEGEND")
est("Cabin and landing gear", "Canopy latches with jettison pull, gas strut", 1, "set", 250.0, "no source captured", cad="CAN-LATCH")
est("Cabin and landing gear", "Furnishing: cargo net, tie-downs, floor mats, liner, placards", 1, "set", 400.0, "no source captured", cad="FURN")
est("Cabin and landing gear", "Ground-handling wheels (clip-on, 2)", 1, "set", 150.0, "no source captured", cad="LG-SKID")
est("Cabin and landing gear", "AN wing pins (W-PIN-M, W-PIN-R) and quick-release pins", 4, "each", 25.0, "no source captured; AN7/AN8 bolt class",
    cad="W-PIN-M, W-PIN-R")

# =================================================================================================== raw materials from CAD
lam = defaultdict(float)        # laminate kg by laminate type
lam_area = defaultdict(float)   # laminate surface m2 (one side) for bagging consumables
core = defaultdict(float)       # kg by core type (net)
xps_buy_m3 = 0.0
sandwich_area = 0.0
metal = []                      # (id, qty, material, envelope)
fdm_kg = 0.0
comp_parts = []
for p in PARTS:
    if p.get("tooling") or p.get("purchased") or not p.get("qty"):
        continue
    m, q, mat = p["mass_kg_each"], p["qty"], p["material"]
    tot = m * q
    if mat.startswith("sandwich"):
        sw = RULES["sandwich"]
        areal = sw["faces"] * sw["t_face"] * 1450.0 + sw["t_core"] * sw["rho_core"]
        a = tot / areal
        sandwich_area += a
        lam["cf_fabric_wet"] += a * sw["faces"] * sw["t_face"] * 1450.0
        lam_area["cf_fabric_wet"] += a * 2
        core["pvc_h80_10mm_m2"] += a
        comp_parts.append(p["id"])
    elif "skin on xps" in mat:
        f = RULES["skin_on_xps_laminate_fraction"]
        lam["cf_fabric_wet"] += f * tot
        lam_area["cf_fabric_wet"] += f * tot / (0.6e-3 * 1450.0)
        e = p["envelope_mm"]
        xps_buy_m3 += e[0] * e[1] * e[2] * 1e-9 * q * RULES["foam_block_buy_factor"]
        comp_parts.append(p["id"])
    elif mat.startswith("cf_ud_wet + cf_fabric_wet"):
        ratio = {"BM-WRAP1": 0.69 / 1.19, "BM-WRAP2": 3.63 / 4.13, "BM-WRAP3": 1.80 / 2.30}.get(p["id"], 0.75)   # UD share by thickness (fea)
        lam["cf_ud_wet"] += ratio * tot
        lam["cf_fabric_wet"] += (1 - ratio) * tot
        lam_area["cf_fabric_wet"] += (1 - ratio) * tot / (0.5e-3 * 1450.0)
        comp_parts.append(p["id"])
    elif mat.startswith("cf_ud_wet"):
        lam["cf_ud_wet"] += tot
        lam_area["cf_ud_wet"] += tot / (3e-3 * 1500.0)
        comp_parts.append(p["id"])
    elif mat.startswith("cf_fabric_wet"):
        lam["cf_fabric_wet"] += tot
        lam_area["cf_fabric_wet"] += tot / (0.6e-3 * 1450.0)
        comp_parts.append(p["id"])
    elif mat.startswith("eglass"):
        lam["eglass_fabric_wet"] += tot
        lam_area["eglass_fabric_wet"] += tot / (0.75e-3 * 1800.0)
        comp_parts.append(p["id"])
    elif mat.startswith("xps_foam"):
        e = p["envelope_mm"]
        xps_buy_m3 += e[0] * e[1] * e[2] * 1e-9 * q * RULES["foam_block_buy_factor"]
    elif mat.startswith("pvc_h45"):
        core["pvc_h45_kg"] += tot
    elif mat.startswith("pvc_h100"):
        core["pvc_h100_kg"] += tot
    elif mat.startswith("pvc_h80"):
        core["pvc_h80_block_kg"] += tot
    elif mat.startswith(("al6061", "al7075", "steel_4130")) and p["process"] in ("CNC",):
        metal.append((p["id"], q, mat, p["envelope_mm"], m))
    elif mat in ("asa", "petg", "pa_cf"):
        fdm_kg += tot

# fabrics
fab = {}
for k, kg in lam.items():
    vf, rho = RULES["laminate"][k]
    fib_rho = RULES["fibre_density"]["eglass" if k.startswith("eglass") else "carbon"]
    fmf = vf * fib_rho / rho
    fibre = kg * fmf
    m2 = fibre / RULES["areal_kg_m2"][k] * (1 + RULES["fabric_scrap"][k])
    fab[k] = dict(laminate_kg=kg, fibre_kg=fibre, fmf=fmf, m2=m2, resin_kg=kg * (1 - fmf))
yd_cf = fab["cf_fabric_wet"]["m2"] * RULES["yd2_per_m2_50in"]
yd_ud = fab["cf_ud_wet"]["m2"] * RULES["yd2_per_m2_50in"]
yd_gl = fab["eglass_fabric_wet"]["m2"] * RULES["yd2_per_m2_50in"]
LAM_NOTE = "quantity from CAD laminate mass x fibre mass fraction / areal weight + scrap (bom/build_bom.py RULES)"
crow("Raw material: composite", "MAT-CF-FABRIC", math.ceil(yd_cf), unit="yard",
     item="Carbon 3K 2x2 twill 193 g/m2, 50 in", note=f"{fab['cf_fabric_wet']['laminate_kg']:.1f} kg laminate -> {fab['cf_fabric_wet']['m2']:.0f} m2; {LAM_NOTE}; 20+ yd tier USD 28.50 would apply", group="material")
crow("Raw material: composite", "MAT-UD-CF", math.ceil(yd_ud), unit="yard", lead="~303 yd in stock (vendor page)",
     note=f"{fab['cf_ud_wet']['laminate_kg']:.1f} kg laminate -> {fab['cf_ud_wet']['m2']:.0f} m2; {LAM_NOTE}", group="material")
crow("Raw material: composite", "MAT-GLASS-7781", math.ceil(yd_gl), unit="yard",
     note=f"{fab['eglass_fabric_wet']['laminate_kg']:.1f} kg laminate -> {fab['eglass_fabric_wet']['m2']:.0f} m2 + glass tapes; {LAM_NOTE}", group="material")
glass_tape_extra = 30
crow("Raw material: composite", "MAT-GLASS-7781", glass_tape_extra, unit="yard", item="E-glass 7781 for 45 deg joint tapes (cut on bias)",
     note="estimate: 2 tapes x ~120 m of bonded panel joints", group="material")

resin_lam = sum(v["resin_kg"] for v in fab.values())
resin_buy = resin_lam * (1 + RULES["resin_waste"]) * (1 + RULES["resin_bonding_allowance"])
kits = math.ceil(resin_buy / RULES["mgs_kit_kg"])
v, t, s, b = cat_price("MAT-RESIN-MGS")
row("Raw material: composite", "MGS L285 laminating resin, 1 gal", kits, "gallon", v, t, s, cid="MAT-RESIN-MGS",
    note=f"laminate resin {resin_lam:.1f} kg x {1+RULES['resin_waste']:.2f} waste x {1+RULES['resin_bonding_allowance']:.2f} bonding/fillets = {resin_buy:.1f} kg mixed -> {kits} kits of ~6.1 kg", group="material")
hq = math.ceil(kits * 1.6)
row("Raw material: composite", "MGS H285F fast hardener, 1 qt (small parts, fillets)", hq - hq // 2, "quart", 97.75, "retail",
    "https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php", cid="MAT-RESIN-MGS", note="~1.6 qt per gallon of resin (100:40)", group="material")
row("Raw material: composite", "MGS H287S slow hardener, 1 qt (skins, spar caps, boom wraps)", hq // 2, "quart", 123.75, "retail",
    "https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php", cid="MAT-RESIN-MGS", note="ships UPS ground only", group="material")
row("Raw material: composite", "MGS H287S hazmat and box fees", hq // 2, "quart", 70.0, "retail",
    "https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php", cid="MAT-RESIN-MGS", note="per Aircraft Spruce page: USD 25 hazmat + 45 box per quart", group="material")
crow("Raw material: composite", "MAT-ADH-EA9394", 4, unit="quart kit", note="metal-to-composite bonds (clamps, sleeves, lugs, inserts); estimate 4 kits", group="material")
est("Raw material: composite", "Fillers: cotton flock, glass microballoons, fumed silica, milled fibre", 1, "set", 350.0,
    "no source captured", group="material")

# cores and foams
h80_sheet_m2 = 2.44 * 1.22
h80_sheets = math.ceil(core["pvc_h80_10mm_m2"] / h80_sheet_m2 / RULES["core_nest_efficiency"])
row("Raw material: composite", "Divinycell H80 10 mm, 2440 x 1220 mm", h80_sheets, "sheet", 109.0 * FX["EUR"], "retail",
    CAT["MAT-FOAM-H80"]["price"]["source"], cid="MAT-FOAM-H80",
    note=f"sandwich panels {sandwich_area:.1f} m2 / {RULES['core_nest_efficiency']:.0%} nesting; priced GPC2 grooved/perforated, plain sheet by quote", group="material")
h80_block_m3 = core["pvc_h80_block_kg"] / 80.0
crow("Raw material: composite", "MAT-FOAM-H80-12", max(1, math.ceil(h80_block_m3 * 1.3 / (1.219 * 2.438 * 0.0127))), unit="sheet",
     note=f"NOSE-EA stacked slabs ({h80_block_m3*1000:.0f} L net)", group="material")
crow("Raw material: composite", "MAT-FOAM-H45", 2, unit="2 in 48x96 sheet",
     note="W-SPM-F box foam 49 x 176 mm x 7.94 m cut as 2438 mm strips (6 strips of 176 mm per sheet, 2 layers)", group="material")
h45s_m2 = PID["W-SPM-S"]["mass_kg_each"] * PID["W-SPM-S"]["qty"] / 48.0 / 0.015 if "W-SPM-S" in PID else 0.0
row("Raw material: composite", "Divinycell H45 5/8 in 32 x 48 in (W-SPM-S 15 mm strips, WP F change 2)", max(1, math.ceil(h45s_m2 / 0.991 / 0.6)), "sheet", 75.85,
    "retail", "https://aircraftspruce.com/catalog/cmpages/divinycellfoam.php", cid="MAT-FOAM-H45",
    note=f"{h45s_m2:.2f} m2 of 15 mm strip from the CAD mass / 60 % strip yield", group="material")
h100_m3 = core["pvc_h100_kg"] / 100.0
crow("Raw material: composite", "MAT-FOAM-H100", max(1, math.ceil(h100_m3 * 1.3 / (1.0668 * 2.159 * 0.0254))), unit="sheet",
     note=f"SEAT-EA crush blocks ({h100_m3*1000:.0f} L net), bonded layers", group="material")
xps_boards = math.ceil(xps_buy_m3 / (1.219 * 2.438 * 0.0508))
crow("Raw material: composite", "MAT-XPS", xps_boards, unit="board",
     note=f"wing/tail/surface cores from envelope volume {xps_buy_m3:.2f} m3 x buy factor; boards laminated to block height", group="material")

# consumables
bag_m2 = sum(lam_area.values()) * RULES["bag_area_factor"]
yd60 = bag_m2 * RULES["yd2_per_m2_60in"]
for item, unitp in (("Peel ply 60 in", 5.55), ("Breather 4 oz 60 in", 4.30), ("Perforated release film 60 in", 6.50)):
    row("Raw material: consumables", item, math.ceil(yd60), "yard", unitp, "retail", "https://uscomposites.com/vacuum.html", cid="MAT-BAGGING",
        note=f"bagged area {bag_m2:.0f} m2 (laminate area x {RULES['bag_area_factor']})", group="material")
row("Raw material: consumables", "Nylon bagging film 110 in (unfolded)", math.ceil(yd60 * 60 / 110 * 1.2), "yard", 4.95, "retail",
    "https://uscomposites.com/vacuum.html", cid="MAT-BAGGING", group="material")
row("Raw material: consumables", "Sealant tape 1/2 in x 25 ft", 20, "roll", 7.15, "retail", "https://uscomposites.com/vacuum.html", cid="MAT-BAGGING",
    note="estimate 20 rolls", group="material")
est("Raw material: consumables", "Gloves, mixing cups, brushes, rollers, squeegees, solvent, release wax/PVA, abrasives", 1, "set", 1200.0,
    "no source captured; 35 % consumable rule of sizing/cost.py covers this line together with the bagging rows", group="material")

# carbon tubes (cut list)
CUT = []
boom_pieces = sorted([(p["id"], round(max(p["envelope_mm"]))) for p in PARTS if p["id"].startswith("BM-T") and p["id"][4:].isdigit()])
n_boom_tubes = 0
for side in ("L", "R"):
    for pid, L in boom_pieces:
        n_boom_tubes += 1
        CUT.append(dict(stock="DragonPlate 4 in ID x 96 in (2438 mm), MAT-TUBE-DP-4x96", part=pid, name=f"boom {side} segment",
                        length_mm=L, offcut_mm=2438 - L - 3 if L <= 2435 else None))
long_pieces = [pid for pid, L in boom_pieces if L > 2435]
crow("Raw material: tubes", "MAT-TUBE-DP-4x96", n_boom_tubes, cad=", ".join(pid for pid, _ in boom_pieces), lead="DragonPlate options 10-15 days (catalog)",
     note=f"one stock tube per boom segment, {n_boom_tubes} total (cut list in BOM.md)" + (f"; segments longer than stock: {long_pieces}" if long_pieces else ""), group="material")
row("Raw material: tubes", "Carbon roll-wrapped tube 50 mm OD x 2.14 mm, >= 2960 mm (HT-SPAR)", 1, "each", 386.50 * 1.3, "estimate",
    "https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-3-id-x-72-gloss-finish", cad="HT-SPAR",
    note="estimate: DragonPlate 3 in x 72 in price x 1.3 for the longer length; stock longer than 96 in by quote (or centre splice with sleeve)",
    lead=LEAD_QUOTE, group="material")
CUT.append(dict(stock="50 mm OD carbon tube >= 120 in (quote)", part="HT-SPAR", name="tail spar", length_mm=round(max(PID["HT-SPAR"]["envelope_mm"])) if "HT-SPAR" in PID else None, offcut_mm=None))
row("Raw material: tubes", "Carbon roll-wrapped tube 40 x 2 mm, 1 m (VF-SPAR x2)", 2, "each", 41.30 * FX["EUR"], "estimate",
    "https://www.easycomposites.eu/35mm-roll-wrapped-carbon-fibre-tube-metric", cad="VF-SPAR",
    note="estimate: Easy Composites 35 mm tube price as reference for 40 mm", group="material")
for i in range(2):
    _L = round(max(PID["VF-SPAR"]["envelope_mm"])) if "VF-SPAR" in PID else 690
    CUT.append(dict(stock="40 mm carbon tube 1 m", part="VF-SPAR", name="fin spar", length_mm=_L, offcut_mm=1000 - _L - 3))
row("Raw material: tubes", "Pultruded carbon tube 30 x 2 mm, 1 m (PM-STRUT)", 2, "each", 41.30 * FX["EUR"], "estimate",
    "https://www.easycomposites.eu/35mm-roll-wrapped-carbon-fibre-tube-metric", cad="PM-STRUT", note="estimate: same reference", group="material")

# aluminium / steel stock
al_kg_plate = defaultdict(float)
bar_kg = defaultdict(float)
plates_m2 = defaultdict(float)
for pid, q, mat, e, m in metal:
    t = min(e)
    dims = sorted(e)
    alloy = "7075" if "7075" in mat else ("4130" if "4130" in mat else "6061")
    if t <= 25.4:
        tin = math.ceil((t + 0.3) / 3.175) * 3.175          # next 1/8 in
        area = (dims[1] + 10) * (dims[2] + 10) * 1e-6 * q / RULES["metal_plate_nest_efficiency"]
        plates_m2[(alloy, round(tin / 25.4, 3))] += area
    else:
        rho_ = 7850 if alloy == "4130" else 2800 if alloy == "7075" else 2700
        env_kg = dims[0] * dims[1] * dims[2] * 1e-9 * q * RULES["metal_bar_buy_factor"] * rho_
        bar_kg[alloy] += min(env_kg, m * q * RULES["buy_to_fly_bar"])
for (alloy, tin), a in sorted(plates_m2.items()):
    rho = 7850 if alloy == "4130" else 2800 if alloy == "7075" else 2700
    kg = a * tin * 0.0254 * rho
    if alloy == "4130":
        crow("Raw material: metals", "MAT-4130-PLATE", 1, unit="plate", item=f"4130 plate {tin:.3f} in, {a:.3f} m2 nested (W-CHUTE-FIT x2, CH-ATT-R)",
             note="plate size to be confirmed (listing size not captured)", group="material")
        continue
    upk = RULES["al7075_usd_per_kg"] if alloy == "7075" else RULES["al_usd_per_kg"]
    row("Raw material: metals", f"{alloy} plate {tin:.3f} in thick, {a:.3f} m2 nested ({kg:.1f} kg)", kg, "kg", upk, "estimate",
        CAT["MAT-AL7075-PLATE" if alloy == "7075" else "MAT-AL-PLATE"]["price"]["source"], cid="MAT-AL7075-PLATE" if alloy == "7075" else "MAT-AL-PLATE",
        note=f"USD/kg from the catalog plate listing applied to this thickness; nesting {RULES['metal_plate_nest_efficiency']:.0%} + 10 mm margin", group="material")
for alloy, kg in sorted(bar_kg.items()):
    upk = RULES["al7075_usd_per_kg"] if alloy == "7075" else RULES["al_usd_per_kg"]
    row("Raw material: metals", f"{alloy} bar / thick plate blocks for machined fittings ({kg:.0f} kg)", kg, "kg", upk, "estimate",
        CAT["MAT-AL-PLATE"]["price"]["source"], cid="MAT-AL-PLATE",
        note="min(finished mass x 3 buy-to-fly, envelope volume x 1.15) for parts thicker than 25 mm (rings BC-W/BC-WR/PY-C, TL-CLAMP, LG blocks, CH-CRADLE); thick-wall tube for the rings by quote", group="material")
skid_L = max(PID["LG-SKID"]["envelope_mm"]) if "LG-SKID" in PID else 2900
skid_ft = 2 * math.ceil(skid_L / 304.8 + 0.5)
row("Raw material: metals", f"6061-T6 tube 2-1/4 x 0.125 in (57.2 x 3.18 mm) for LG-SKID, 2 x {skid_L:.0f} mm", skid_ft, "ft", 21.70, "retail",
    "https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php", cid="MAT-AL-TUBE", cad="LG-SKID",
    note=(("skid longer than the 12 ft stock length: buy 16 ft lengths from a metals supplier or splice with an internal sleeve; " if skid_L > 3657 else "") +
         ("CAD already uses the 2-1/4 x 0.125 in stock tube (P/N 03-38310)" if min(PID["LG-SKID"]["envelope_mm"]) < 58 else
          "SKID SIZE FIX: the CAD 60 x 3.2 mm is not a listed US stock size; build to 2-1/4 x 0.125 in (P/N 03-38310)")), group="material")
gs = GEO.get("gear_strut_section", {})
leg_note = (PID.get("LG-LEG", {}).get("notes") or "")
if "0.095" in leg_note:
    row("Raw material: metals", "6061-T6 tube 3 x 0.095 in (76.2 x 2.41 mm) for LG-LEG", 16, "ft", 23.75 * 1.4, "estimate",
        "https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php", cid="MAT-AL-TUBE", cad="LG-LEG",
        note=f"estimate: 3 x 0.065 price USD 23.75/ft x 1.4 for the 0.095 wall; 4 legs x 1.2 m incl. bending grip. CAD uses 3 x 0.095 but "
             f"design/geometry.json gear_strut_section still says t = {gs.get('t', 0)*1000:.2f} mm - WP D/G to align", group="material")
else:
    row("Raw material: metals", "6061-T6 tube 3 x 0.250 in for LG-LEG", 3, "length (72 in)", 177.83, "retail",
        "https://www.speedymetals.com/p-4619-3-od-x-025-wall-tube-6061-t6-aluminum.aspx", cid="MAT-AL-TUBE", cad="LG-LEG", group="material")
row("Raw material: metals", "6061-T6 tube 100 x 1.6 mm (PY-TUBE x8) and 44 mm vent tube", 8, "ft", 23.75 * 1.4, "estimate",
    "https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php", cid="MAT-AL-TUBE", cad="PY-TUBE, BAT-VENT",
    note="estimate: 3 x 0.065 price x 1.4 for 100 mm OD; 8 x 0.21 m + vents", group="material")
_bb = PID.get("BAT-BOX", {}).get("envelope_mm", [237, 620, 187])
_flat = (_bb[0] + 2 * _bb[2]) * (_bb[1] + 2 * _bb[2]) * 1e-6
row("Raw material: metals", f"6061-T6 sheet 0.063 in 4 x 8 ft (BAT-BOX flat patterns, {n_packs} boxes)", math.ceil(n_packs * _flat / 2.97 / 0.7), "sheet", 325.00, "retail",
    "https://www.aircraftspruce.com/catalog/mepages/alumsheet_6061t6.php", cid="MAT-AL-6061-SHEET", cad="BAT-BOX", group="material")
row("Raw material: metals", "6061-T6 sheet 0.090 in 4 x 6 ft (BAT-LID x3, CAD 2 mm)", 1, "sheet", 337.00, "retail",
    "https://www.aircraftspruce.com/catalog/mepages/alumsheet_6061t6.php", cid="MAT-AL-6061-SHEET", cad="BAT-LID", group="material")
row("Raw material: metals", "6061-T6 sheet 0.125 in 2 x 4 ft (IP panel, CAD 3 mm)", 1, "sheet", 112.75, "retail",
    "https://www.aircraftspruce.com/catalog/mepages/alumsheet_6061t6.php", cid="MAT-AL-6061-SHEET", cad="IP", group="material")
crow("Raw material: metals", "MAT-UHMW", 1, unit="sheet", cad="LG-SHOE", group="material")
row("Raw material: plastics", "3-D printer filament ASA / PA-CF / PETG (parts)", max(1, math.ceil(fdm_kg * 1.5)), "kg", 30.0, "estimate", "",
    cad="BM-CAP-F, BM-CAP-A", note="estimate: USD 30/kg (sizing/cost.py FDM basis); x1.5 for supports/failed prints", group="material")

# fasteners and inserts (counts from cad/parts.json notes; unit prices from the catalog hardware row)
FAST = [  # (item, count, unit price USD, basis)
    ("AN5 bolts (W-FIT-MS/RS 8 each x4, W-CHUTE-FIT 8 x2, CH-ATT-R 8, W-CHUTE-ANG 4 x2, SEAT-FIT 2 x8, HA-FIT 8)", 32 + 16 + 8 + 8 + 16 + 8, 1.50, "AN4-5 USD 1.06 (Air Power) scaled x1.4 for AN5 (estimate)"),
    ("AN4 bolts (F-CLV 6 x4, PY-C 2 x8, TL-CLAMP 8 x2, LG-SKCL 2 x4, CAN-HINGE 4, misc 40)", 24 + 16 + 16 + 8 + 4 + 40, 1.06, "AN4-5 Air Power listing"),
    ("AN6 bolts (BC-W/BC-WR 4 x4, LG-SADDLE 4 x4)", 32, 2.50, "estimate: AN6 ~2.4 x AN4 price"),
    ("AN3 bolts and clevis pins (BAT-LID 16 x3, hinges 18+8+4, misc 40)", 48 + 30 + 40, 0.90, "estimate: below AN4 price"),
    ("MS21042 / AN365 nuts, AN960 washers (all bolts above, x1.3 spares)", 400, 0.60, "MS21042-3 USD 0.32 / -4 USD 0.48 (Van's) + washers"),
    ("M8 class 12.9 motor bolts (8 per motor) and isolator studs/nuts (6 per lift station)", 8 * (n_lift + n_push) + 6 * n_lift, 1.20, "estimate"),
    ("CherryMAX blind rivets (battery boxes, brackets)", 400, 0.81, "CR3212-4-3 USD 0.81 (Van's)"),
    ("Potted aluminium inserts / bushings for sandwich panels", 220, 2.50, "estimate: in-house turned from 6061 bar or bought"),
    ("Camlock / quick-release fasteners for hatches and cowls", 60, 4.00, "estimate"),
]
for item, n, up, basis in FAST:
    row("Raw material: hardware", item, n, "each", up, "retail" if "Van's" in basis or "Air Power" in basis else "estimate",
        "https://www.airpowerinc.com/an4-5" if "Air Power" in basis else ("https://store.vansaircraft.com/kits-components/rv-12-kit/fuselage-11/rv-12-12is-fuselage/hardware-259.html?p=3" if "Van's" in basis else ""),
        cid="MAT-FASTENERS", note=basis, group="material")

# =================================================================================================== tooling materials
tool = defaultdict(float)
tool_ids = defaultdict(list)
for p in PARTS:
    if not p.get("tooling"):
        continue
    mat = p["material"]
    q = p["qty"]
    e = p["envelope_mm"]
    if mat == "mdf":
        tool["mdf_m3"] += p["mass_kg_each"] * q / 750.0
        tool_ids["mdf"].append(p["id"])
    elif mat.startswith("eps"):
        tool["foam_m3"] += e[0] * e[1] * e[2] * 1e-9 * q * 1.1
        tool_ids["foam"].append(p["id"])
    elif mat == "birch_plywood":
        tool["ply_kg"] += p["mass_kg_each"] * q
        tool_ids["ply"].append(p["id"])
    elif mat in ("asa", "petg", "pa_cf"):
        tool["fdm_kg"] += p["mass_kg_each"] * q
        tool_ids["fdm"].append(p["id"])
    elif mat.startswith("al6061"):
        tool["al_kg"] += p["mass_kg_each"] * q
        tool_ids["al"].append(p["id"])
mdf_sheets = math.ceil(tool["mdf_m3"] * 1.3 / (1.245 * 2.464 * 0.01905))
crow("Tooling materials", "MAT-MDF", mdf_sheets, unit="sheet", cad=", ".join(sorted(set(tool_ids["mdf"])))[:120] + " ...",
     note=f"{tool['mdf_m3']:.2f} m3 net (CAD tooling mass / 750 kg/m3, estimate) x 1.3 waste", group="tooling")
crow("Tooling materials", "MAT-XPS", math.ceil(tool["foam_m3"] / (1.219 * 2.438 * 0.0508)), unit="board",
     item="XPS boards laminated into plug blocks (T-PLUG-*, T-SEAT-PLUG*, T-PLUG-TIP)", note=f"{tool['foam_m3']:.2f} m3 block envelope x 1.1", group="tooling")
est("Tooling materials", "Birch plywood 18 mm 4 x 8 ft (T-XT-TEMPL)", 1, "sheet", 90.0, "no source captured", cad="T-XT-TEMPL", group="tooling")
row("Tooling materials", "FDM filament for tools (ASA, PETG, PA-CF)", math.ceil(tool["fdm_kg"] * 1.3), "kg", 30.0, "estimate", "",
    cad="T-NAC-M*, T-VBLOCK, T-DRILL-BC", note="estimate: USD 30/kg (sizing/cost.py); PA-CF costs more", group="tooling")
row("Tooling materials", "6061 sheet for drill templates (T-DRILL-RF)", 1, "sheet", 82.75, "retail",
    "https://www.aircraftspruce.com/catalog/mepages/alumsheet_6061t6.php", cid="MAT-AL-6061-SHEET", note="0.063 2x4 ft as listed; CAD 6 mm plate - use offcut of the 1/4 in plate", group="tooling")
crow("Tooling materials", "MAT-RESIN-WEST", 3, unit="1.2 gal kit", note="plug/mould sealing and tooling (sizing/cost.py)", group="tooling")
est("Tooling materials", "Lightweight fairing filler, primer, mould release (plugs and moulds)", 1, "set", 500.0, "no source captured", group="tooling")
est("Tooling materials", "Hot-wire cutter supply, nichrome wire, bow (if not owned)", 1, "set", 300.0, "no source captured", group="tooling")

# =================================================================================================== outsourced services
OUTS = [("Waterjet / laser-cut flat parts (battery boxes, lids, IP, G10 holder plates)", 600.0),
        ("Canopy and window thermoforming over our MDF plug", 2500.0),
        ("Gear-leg bending (4 legs, T-XT-TEMPL)", 400.0),
        ("Aluminium surface treatment (alodine / anodize)", 1500.0),
        ("Primer and paint materials", 1500.0)]
for item, usd in OUTS:
    est("Outsourced services", item, 1, "lot", usd, "WP D allowance (sizing/cost.py OUTSOURCED) - quote required", group="outsourced")

# =================================================================================================== totals and outputs
for r in ROWS:
    if r["total_usd"] is None:
        r["total_usd"] = 0.0
TOTAL = sum(r["total_usd"] for r in ROWS)
by_cat = defaultdict(float)
for r in ROWS:
    by_cat[r["category"]] += r["total_usd"]

COLS = ["group", "category", "item", "catalog_id", "cad_ids", "qty", "unit", "unit_price_usd", "total_usd", "price_type", "source",
        "lead_time", "export_control", "note"]
with open(ROOT / "bom/BOM.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for r in ROWS:
        w.writerow(r)

# ---- reconciliation with sizing/results/cost_breakdown.md (prototype cash)
cb = DES["cost"]["breakdown_usd"]
def s_(cats=None, items=None, ids=None):
    t = 0.0
    for r in ROWS:
        if cats and r["category"] in cats:
            t += r["total_usd"]
        elif items and any(k in r["item"] for k in items):
            t += r["total_usd"]
        elif ids and r["catalog_id"] in ids:
            t += r["total_usd"]
    return t
mine = {
    "lift_motors": 0.0,     # set below
    "inverters": s_(ids={"INV-HBCI400800"}),
    "lift_propellers": s_(ids={"PROP-EPROPS-UAV-ADJ"}),
    "pusher_motor": 0.0,
    "pusher_propeller": 0.0,
    "battery": sum(r["total_usd"] for r in ROWS if r["category"] == "Battery and HV"
                   and r["catalog_id"] not in ("HV-AL-CABLE", "HV-DCDC-MW") and "lugs" not in r["item"]),
    "parachute": s_(cats={"Safety"}),
    "hv_cooling_harness": s_(cats={"Thermal"}) + s_(ids={"HV-AL-CABLE"}) + s_(items=["Bimetal"]),
    "systems_avionics_cabin": s_(cats={"Avionics and flight control", "Cabin and landing gear"}) + s_(ids={"HV-DCDC-MW"}),
    "isolators (in airframe materials in WP D)": s_(items=["sandwich isolator"]),
    "airframe_materials_consumables": sum(r["total_usd"] for r in ROWS if r["group"] == "material"),
    "tooling_materials": sum(r["total_usd"] for r in ROWS if r["group"] == "tooling"),
    "outsourced_services (incl. fasteners in WP D)": sum(r["total_usd"] for r in ROWS if r["group"] == "outsourced"),
}
cbj = json.loads((ROOT / "sizing/results/cost_breakdown.json").read_text()) if (ROOT / "sizing/results/cost_breakdown.json").exists() else {}
wpd = {"lift_motors": cb["lift_motors"], "inverters": cb["inverters"], "lift_propellers": cb["lift_propellers"],
       "pusher_motor": cb["pusher_motor"], "pusher_propeller": cb["pusher_propeller"], "battery": cb["battery"],
       "parachute": cb["parachute"], "hv_cooling_harness": cb["hv_cooling_harness"], "systems_avionics_cabin": cb["systems_avionics_cabin"],
       "isolators (in airframe materials in WP D)": 0.0,
       "airframe_materials_consumables": cb["airframe_materials_consumables"], "tooling_materials": 2792.0,
       "outsourced_services (incl. fasteners in WP D)": cb["outsourced_services"]}
mine["lift_motors"] = sum(r["total_usd"] for r in ROWS if r["catalog_id"] == LIFT_MOT and r["category"] == "Propulsion") * (1 if LIFT_MOT != PUSH_MOT else n_lift / (n_lift + n_push))
mine["pusher_motor"] = sum(r["total_usd"] for r in ROWS if r["catalog_id"] == PUSH_MOT and r["category"] == "Propulsion") * (1 if LIFT_MOT != PUSH_MOT else n_push / (n_lift + n_push))
_pr = [r for r in ROWS if r["catalog_id"] == "PROP-EPROPS-UAV-ADJ" and r["category"] == "Propulsion"]
mine["lift_propellers"] = _pr[0]["total_usd"]
mine["pusher_propeller"] = sum(r["total_usd"] for r in _pr[1:])
import re as _re
_cbmd = (ROOT / "sizing/results/cost_breakdown.md").read_text()
_mt = _re.search(r"tooling materials[^|]*\|\s*([\d,]+)", _cbmd)
wpd["tooling_materials"] = float(_mt.group(1).replace(",", "")) if _mt else 2792.0
REC = [dict(item=k, wp_d_usd=round(wpd[k]), bom_usd=round(mine[k]), delta_usd=round(mine[k] - wpd[k])) for k in wpd]
REC_TOTAL = dict(wp_d=round(sum(wpd.values())), bom=round(sum(mine.values())))

lam_summary = {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in fab.items()}
made = [dict(id=p["id"], name=p["name"], group=p["group"], process=p["process"], material=p["material"], qty=p["qty"],
             mass_kg_each=round(p["mass_kg_each"], 3), size_mm=[round(x) for x in p["envelope_mm"]], files=p.get("files", {}))
        for p in PARTS if not p.get("purchased") and not p.get("tooling") and p["process"] != "COTS"]
docs = dict(_about="E8-200 prototype bill of materials, generated by bom/build_bom.py from bom/catalog.json and cad/parts.json",
            checked=CHECKED, fx=FX, cad_warning=CAD_NOTE, design=DES["name"], design_mtow_kg=DES["mass_kg"]["mtow"],
            wp_d_prototype_cash_usd=DES["cost"]["prototype_out_of_pocket_usd"], total_usd=round(TOTAL, 2), by_category={k: round(v, 2) for k, v in by_cat.items()},
            rows=ROWS, cut_list=CUT, made=made, reconciliation=REC, reconciliation_total=REC_TOTAL, laminate=lam_summary,
            cad_parts_file_date=CADJ.get("_about", ""))
(ROOT / "docs/data").mkdir(parents=True, exist_ok=True)
(ROOT / "docs/data/bom.json").write_text(json.dumps(docs, indent=1) + "\n")


def money(x):
    return f"{x:,.0f}"


L = ["# E8-200 prototype bill of materials", "",
     f"Generated by [build_bom.py](build_bom.py) on the frozen design ({DES["name"].split(": ",1)[-1]}, MTOW {DES['mass_kg']['mtow']:.0f} kg) from "
     "[catalog.json](catalog.json) and [cad/parts.json](../cad/parts.json). Machine-readable: [BOM.csv](BOM.csv), "
     "[docs/data/bom.json](../docs/data/bom.json); web page: [docs/bom.html](../docs/bom.html).", "",
     "One prototype, cash only (labour is in [manufacturing/MANUFACTURING.md](../manufacturing/MANUFACTURING.md)). Prices: catalog "
     f"listings checked 2026-11-12/15; quote items at the middle of the catalog estimate range; EUR x {FX['EUR']}, GBP x {FX['GBP']} "
     "(estimate, same as WP D). `price_type` in the CSV says which numbers are listings and which are estimates; every "
     "estimate carries its basis. Vendor questions: [QUOTES_TO_REQUEST.md](../manufacturing/QUOTES_TO_REQUEST.md).", "",
     (f"> {CAD_NOTE}" if CAD_NOTE else ""), "",
     f"## Total: USD {money(TOTAL)}", "", "| Category | USD | share |", "|---|---|---|"]
for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
    L.append(f"| {k} | {money(v)} | {v / TOTAL:.1%} |")
L.append(f"| **total** | **{money(TOTAL)}** | |")
est_total = sum(r["total_usd"] for r in ROWS if r["price_type"] != "retail" and r["price_type"] != "list" and r["price_type"] != "dealer" and r["price_type"] != "reseller")
L += ["", f"Of the total, USD {money(est_total)} ({est_total / TOTAL:.0%}) rests on estimates or quote-required items (mostly the MGM "
      "motors and inverters and the parachute); the rest are published listings.", "",
      f"## Reconciliation with WP D (sizing/results/cost_breakdown.md, prototype cash USD {DES['cost']['prototype_out_of_pocket_usd']:,.0f})", "",
      "| Item | WP D USD | BOM USD | delta |", "|---|---|---|---|"]
for r in REC:
    L.append(f"| {r['item']} | {money(r['wp_d_usd'])} | {money(r['bom_usd'])} | {r['delta_usd']:+,} |")
L.append(f"| **total** | **{money(REC_TOTAL['wp_d'])}** | **{money(REC_TOTAL['bom'])}** | **{REC_TOTAL['bom'] - REC_TOTAL['wp_d']:+,}** |")
R = {r["item"].split(" ")[0]: r for r in REC}
mat_rows = defaultdict(float)
for r in ROWS:
    if r["group"] == "material":
        mat_rows[r["category"]] += r["total_usd"]
recon = [
    f"The BOM total for the reconciled scope is USD {money(REC_TOTAL['bom'])} against WP D's USD {money(REC_TOTAL['wp_d'])} "
    f"({(REC_TOTAL['bom'] - REC_TOTAL['wp_d']) / REC_TOTAL['wp_d']:+.1%}). The COTS propulsion lines are identical because both use the "
    "same catalog estimates (the MGM quotes will move them most). The differences:",
    "",
    f"- **Airframe materials and consumables {R['airframe_materials_consumables']['delta_usd']:+,}:** WP D prices finished CAD mass at USD/kg "
    "with 15-25 % scrap; the BOM buys whole stock units: Divinycell H45 in two 2 in sheets for 3.5 kg of spar foam, MGS hardener "
    "hazmat/box fees (USD 70 per slow-hardener quart), four EA 9394 kits, carbon tubes as full DragonPlate lengths, and the "
    f"fasteners and bagging consumables as their own rows (composite USD {money(mat_rows['Raw material: composite'])}, metals "
    f"{money(mat_rows['Raw material: metals'])}, tubes {money(mat_rows['Raw material: tubes'])}, consumables "
    f"{money(mat_rows['Raw material: consumables'])}, hardware {money(mat_rows['Raw material: hardware'])}).",
    f"- **Tooling materials {R['tooling_materials']['delta_usd']:+,}:** WP D prices the EPS plugs by finished mass; the plugs are machined "
    "from laminated blocks, so the BOM buys the block envelope volume (about 7.3 m3 of XPS boards) and MDF by sheet.",
    f"- **Battery {R['battery']['delta_usd']:+,}:** WP D used a USD 2,500 per-pack allowance for enclosure, cold plate and bus bars and "
    "USD 1/cell for holders and nickel; the BOM itemises G10 holders, copper strip, contactors, fuses, connectors and precharge, and "
    "carries the box sheet and cold-plate stock under metals. The mica liner is quote-only and not yet priced.",
    f"- **HV, cooling and harness {R['hv_cooling_harness']['delta_usd']:+,}:** itemised pumps, coolers and an aluminium-cable estimate "
    "replace the WP D formula (USD 400 per motor + 1,000 + 30/m).",
    f"- **Systems, avionics, cabin {R['systems_avionics_cabin']['delta_usd']:+,}:** Vicor DC-DC converters (250-425 V input, which do not cover the "
    "bus) are replaced by four Mean Well RSDH-300-24; oleo dampers, seat track, foam, polycarbonate, latches and "
    "pins are added as purchased rows.",
    f"- **Outsourced {R['outsourced_services']['delta_usd']:+,}:** the USD 1,500 AN/MS hardware allowance moved to the hardware rows.",
    f"- **Parachute {R['parachute']['delta_usd']:+,}:** risers/bridle listed separately (normally part of the Galaxy installation).",
    "",
    "Labour is not in either cash figure: WP D's labour hours (incl. tooling and QC, sizing/results/cost_breakdown.md) are broken down by part family in "
    "manufacturing/MANUFACTURING.md.",
]
L += [""] + recon + [""]
L += ["## Purchased items", "", "| Category | Item | Qty | Unit USD | Total USD | Price type | Lead time | Export control | Source |",
      "|---|---|---|---|---|---|---|---|---|"]
for r in ROWS:
    if r["group"] != "purchased":
        continue
    src = f"[link]({r['source']})" if r["source"] else "-"
    up = "quote" if r["unit_price_usd"] is None else money(r["unit_price_usd"]) if r["unit_price_usd"] >= 100 else f"{r['unit_price_usd']:.2f}"
    L.append(f"| {r['category']} | {r['item']} ({r['cad_ids']}) | {r['qty']:g} {r['unit']} | {up} | {money(r['total_usd'])} | {r['price_type']} | {r['lead_time']} | {r['export_control']} | {src} |")
L += ["", "## Raw materials (quantities derived from the CAD)", "",
      "Laminates (CAD mass -> fibre and resin):", "", "| Laminate | laminate kg | fibre mass fraction | fibre kg | fabric to buy m2 (incl. scrap) | resin in laminate kg |",
      "|---|---|---|---|---|---|"]
for k, v in fab.items():
    L.append(f"| {k} | {v['laminate_kg']:.1f} | {v['fmf']:.2f} | {v['fibre_kg']:.1f} | {v['m2']:.0f} | {v['resin_kg']:.1f} |")
L += ["", f"Flat sandwich panels: {sandwich_area:.1f} m2 (carbon 2 x 0.5 mm on H80 10 mm). Foam blocks for hot-wire cores: {xps_buy_m3:.2f} m3. "
      f"Bagged area for consumables: {bag_m2:.0f} m2.", "",
      "| Category | Item | Qty | Unit USD | Total USD | Price type | Basis / note | Source |", "|---|---|---|---|---|---|---|---|"]
for r in ROWS:
    if r["group"] not in ("material", "tooling", "outsourced"):
        continue
    src = f"[link]({r['source']})" if r["source"] else "-"
    up = money(r["unit_price_usd"]) if r["unit_price_usd"] >= 100 else f"{r['unit_price_usd']:.2f}"
    L.append(f"| {r['category']} | {r['item']} | {r['qty']:g} {r['unit']} | {up} | {money(r['total_usd'])} | {r['price_type']} | {r['note'][:220]} | {src} |")
L += ["", "## Carbon tube cut list", "", "| Stock | Part | Use | Cut length mm | Offcut mm |", "|---|---|---|---|---|"]
for c in CUT:
    L.append(f"| {c['stock']} | {c['part']} | {c['name']} | {c['length_mm']} | {c['offcut_mm'] if c['offcut_mm'] is not None else '-'} |")
L += ["", "## Metal stock nesting estimate", "", "| Alloy | Plate thickness in | Nested area m2 (incl. 65 % nesting) |", "|---|---|---|"]
for (alloy, tin), a in sorted(plates_m2.items()):
    L.append(f"| {alloy} | {tin:.3f} | {a:.3f} |")
for alloy, kg in sorted(bar_kg.items()):
    L.append(f"| {alloy} | bar/block | {kg:.1f} kg |")
L += ["", "Machined parts with all envelope dimensions above 25 mm (clamp rings, saddles, sockets) are bought as bar/block; "
      "their envelope volume x 1.15 is the stock mass. The plate rows nest each part's two largest envelope dimensions + 10 mm "
      "on plate of the next 1/8 in thickness at 65 % efficiency.", ""]
(ROOT / "bom/BOM.md").write_text("\n".join(L) + "\n")
print(f"BOM total USD {TOTAL:,.0f} ({len(ROWS)} rows)")
for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
    print(f"  {k:32s} {v:12,.0f}")
print("reconciliation:", REC_TOTAL)
for r in REC:
    print("  ", r)
print("laminate:", lam_summary)
print("xps m3", round(xps_buy_m3, 2), "sandwich m2", round(sandwich_area, 1), "bag m2", round(bag_m2))
print("plates", dict(plates_m2), "bars", dict(bar_kg))
print("tooling", dict(tool))
