"""Component options and fixed assumptions for the E8-200 sizing code (work package D).

Every COTS number is read from bom/catalog.json (work package P) by its catalog id; nothing is typed in here
except where the catalog gives no value - those entries are marked ``basis="estimate: ..."``.
Source ids in comments refer to resources/README.md (SZxx, BTxx, RAxx, AExx, STxx, MFxx) and equation tags to
methods/EQUATIONS.md ([H1], [M1], ...).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "bom" / "catalog.json").read_text())
ITEMS = {it["id"]: it for it in CATALOG["items"]}
REQ_PATH = ROOT / "requirements" / "requirements.yaml"

# Currency: the catalog keeps the published currency (no FX). Conversion used here (estimate, Nov 2026 order of
# magnitude; WP M used EUR 1,304 ~ USD 1,450, i.e. 1.11):
FX_USD = {"USD": 1.0, "EUR": 1.10, "GBP": 1.27}


def item(cid: str) -> dict:
    return ITEMS[cid]


def price_usd(cid: str, which: str = "mid") -> tuple[float | None, str]:
    """Unit price in USD and its basis.  'quote_required' items use the catalog estimate (mid of a range)."""
    p = ITEMS[cid]["price"]
    fx = FX_USD[p.get("currency", "USD")]
    if p.get("value") is not None:
        return p["value"] * fx, f"{cid}: {p['type']} {p['currency']} {p['value']}"
    est = p.get("estimate")
    if est is None:
        return None, f"{cid}: no price in catalog"
    if isinstance(est, (list, tuple)):
        v = {"low": est[0], "high": est[1]}.get(which, 0.5 * (est[0] + est[1]))
    else:
        v = est
    return v * fx, f"{cid}: catalog estimate {p['currency']} {est} ({which})"


# ----------------------------------------------------------------------------------------------------------------
# Lift / pusher motors.  Continuous ratings published as ranges use the LOWER bound.  MGM gives no rpm-dependent
# torque curve: max torque is taken as available over the rpm range (WP P method, validation/parts).
# ----------------------------------------------------------------------------------------------------------------
def _motor(cid, cont_kw, cont_basis, rpm_min, rpm_max, inverter, vclass, torque_cont=None, diameter=None, exposed_h=0.10, lv_winding=0):
    it = ITEMS[cid]
    r = it["ratings"]
    peak = r.get("peak_power_kW")
    peak = float(str(peak).split()[0]) if peak is not None else None
    tq = r.get("max_torque_Nm", r.get("peak_torque_Nm"))
    pr, pb = price_usd(cid)
    return dict(id=cid, name=it["name"], mass_kg=it["mass_kg"], peak_kw=peak, cont_kw=cont_kw, cont_basis=cont_basis,
                torque_nm=float(tq), torque_cont_nm=torque_cont, rpm_min=rpm_min, rpm_max=rpm_max, inverter=inverter,
                vclass=vclass, price_usd=pr, price_basis=pb,
                diameter_m=(diameter or r.get("diameter_mm", 266) / 1000.0), exposed_height_m=exposed_h, lv_winding=lv_winding)


LIFT_MOTORS = [
    _motor("MOT-REB30", 25.0, "catalog 25-30 kW, lower bound", 1500, 4000, "INV-HBCI100400", 400),
    _motor("MOT-REB50", 30.0, "catalog 30-40 kW, lower bound", 1500, 4000, "INV-HBCI400800", 800),
    _motor("MOT-REB60", 36.0, "estimate: 0.60 x 60 kW peak (lowest cont/peak ratio of the REB family: REB 50 30/50)",
           1500, 4000, "INV-HBCI400800", 800, diameter=0.27),
    _motor("MOT-REB90", 60.0, "catalog 60-70 kW, lower bound", 1500, 4000, "INV-HBCI400800", 800),
    # iteration 3 cost option: REB 60 with a low-voltage winding on a <= 400 V bus (93s max) driven by the cheaper, lighter-
    # rated HBCi 400400 (400 A); MGM publishes the REB family as 400-800 V and windings as customer-specified: to be confirmed
    _motor("MOT-REB60", 36.0, "estimate: 0.60 x 60 kW peak", 1500, 4000, "INV-HBCI400400", 400, diameter=0.27, lv_winding=1),
    # motor-rating fallback study: EMRAX axial-flux (SI), liquid cooled, catalog LC continuous torque/power
    _motor("MOT-EMRAX268", 91.0, "catalog 91 kW LC, 205 N m LC continuous torque", 0, 4500, "INV-HBCI400800", 800,
           torque_cont=205.0, diameter=0.268),
    _motor("MOT-EMRAX228", 68.0, "catalog 68 kW LC, 118 N m LC continuous torque", 0, 6500, "INV-HBCI400800", 800,
           torque_cont=118.0, diameter=0.228),
]
for _m in LIFT_MOTORS:
    if _m["id"].startswith("MOT-EMRAX"):
        _m["price_usd"], _m["price_basis"] = ({"MOT-EMRAX268": 12000.0}.get(_m["id"], 9000.0),
                                              "estimate: EMRAX sells by quotation; 228 set equal to the REB 50 class mid, "
                                              "268 scaled to the REB 90 class mid")
# Excluded lift options (kept for the record in the README): MOT-MAD-M90C60 (no torque rating published),
# MOT-U15XXL (fails 1000 m ISA+15 OEI per WP P, 100 V), EMRAX (continuous torque too low, WP P), MOT-HW-P50M.

PUSHER_MOTORS = [
    _motor("MOT-REB50", 30.0, "catalog 30-40 kW, lower bound", 1500, 4000, "INV-HBCI400800", 800),
    _motor("MOT-REB60", 36.0, "estimate: 0.60 x peak", 1500, 4000, "INV-HBCI400800", 800, diameter=0.27),
    _motor("MOT-REB90", 60.0, "catalog 60-70 kW, lower bound", 1500, 4000, "INV-HBCI400800", 800),
    # EMRAX 228 MV liquid cooled: continuous power limited by 118 N m continuous torque at propeller rpm
    _motor("MOT-EMRAX228", 68.0, "catalog 68 kW LC, limited by 118 N m LC continuous torque", 0, 6500,
           "INV-HBCI400800", 800, torque_cont=118.0, diameter=0.228),
    _motor("MOT-EMRAX208", 47.0, "catalog 47 kW LC, limited by 75 N m LC continuous torque", 0, 7000,
           "INV-HBCI400800", 800, torque_cont=75.0, diameter=0.208),
]
# iteration 3.2 option: twin pushers on the boom tails, each the lift unit (REB 60 + HBCi 400800); one motor type
_tw = dict(_motor("MOT-REB60", 36.0, "estimate: 0.60 x 60 kW peak, per motor", 1500, 4000, "INV-HBCI400800", 800, diameter=0.27))
_tw.update(mass_kg=2 * _tw["mass_kg"], peak_kw=2 * _tw["peak_kw"], cont_kw=2 * _tw["cont_kw"], torque_nm=2 * _tw["torque_nm"],
           price_usd=2 * _tw["price_usd"], twin=1, name="2 x MGM REB 60 on the boom tails (twin pusher)")
PUSHER_MOTORS.append(_tw)


def _twin(m, name):
    t = dict(m)
    t.update(mass_kg=2 * m["mass_kg"], peak_kw=2 * m["peak_kw"], cont_kw=2 * m["cont_kw"], torque_nm=2 * m["torque_nm"],
             torque_cont_nm=(2 * m["torque_cont_nm"] if m["torque_cont_nm"] else None), price_usd=2 * m["price_usd"], twin=1, name=name)
    return t


# motor-rating fallback study: twin REB 90, twin EMRAX 228, single EMRAX 268
PUSHER_MOTORS.append(_twin(_motor("MOT-REB90", 60.0, "catalog 60-70 kW, lower bound", 1500, 4000, "INV-HBCI400800", 800),
                           "2 x MGM REB 90 on the boom tails (twin pusher)"))
_e228 = _motor("MOT-EMRAX228", 68.0, "catalog 68 kW LC, limited by 118 N m LC continuous torque", 0, 6500, "INV-HBCI400800", 800,
               torque_cont=118.0, diameter=0.228)
_e228["price_usd"] = 9000.0
PUSHER_MOTORS.append(_twin(_e228, "2 x EMRAX 228 MV LC on the boom tails (twin pusher)"))
_e268 = _motor("MOT-EMRAX268", 91.0, "catalog 91 kW LC, limited by 205 N m LC continuous torque", 0, 4500,
               "INV-HBCI400800", 800, torque_cont=205.0, diameter=0.268)
_e268["price_usd"], _e268["price_basis"] = 12000.0, "estimate: EMRAX sells by quotation; scaled to the REB 90 class mid"
PUSHER_MOTORS.append(_e268)
# REB 60 detailed MGM table "valid for 25 C" (catalog ratings table_25C_*): the motor-rating risk case
REB60_TABLE = dict(peak_kw=33.5, cont_kw=25.0, torque_nm=133.0, torque_cont_nm=95.0)
for _m in PUSHER_MOTORS[:5]:
    if _m["id"].startswith("MOT-EMRAX"):
        _m["price_usd"], _m["price_basis"] = 9000.0, "estimate: no price in catalog; set equal to REB 50 class mid (USD 7-9 k)"

INVERTERS = {
    "INV-HBCI400400": dict(mass_kg=4.0, v_max=400.0, v_min=120.0, i_cont=400.0, i_peak=400.0,   # mass: catalog gives 4 kg
                           price_usd=price_usd("INV-HBCI400400")[0], price_basis=price_usd("INV-HBCI400400")[1]),
    "INV-HBCI400800": dict(mass_kg=ITEMS["INV-HBCI400800"]["mass_kg"], v_max=800.0, v_min=120.0, i_cont=400.0, i_peak=400.0,
                           price_usd=price_usd("INV-HBCI400800")[0], price_basis=price_usd("INV-HBCI400800")[1]),
    # HBCi 100400: 100 A continuous (fluid cooled), 125 A short time = 50 kW / 400 V (WP P estimate)
    "INV-HBCI100400": dict(mass_kg=ITEMS["INV-HBCI100400"]["mass_kg"], v_max=400.0, v_min=120.0, i_cont=100.0, i_peak=125.0,
                           price_usd=price_usd("INV-HBCI100400")[0], price_basis=price_usd("INV-HBCI100400")[1]),
}

# ----------------------------------------------------------------------------------------------------------------
# Cells.  'i_cont_screen' = continuous current used for the normal hover C-rate check (WP M screening value 40 A for
# the P50B = 2/3 of the datasheet 60 A, which is quoted at an 80 C cut-off; BT01); 'i_peak' = datasheet continuous
# rating, used for one-pack-out and rotor-out emergency cases.  DC resistance BT01 (P50B); others estimate.
# ----------------------------------------------------------------------------------------------------------------
CELLS = [
    dict(id="CELL-P50B", energy_wh=18.0, mass_kg=0.071, capacity_ah=5.0, v_nom=3.6, i_cont_screen=40.0, i_peak=60.0,
         dcir_ohm=0.0128, price_usd=price_usd("CELL-P50B")[0]),
    dict(id="CELL-P45B", energy_wh=16.2, mass_kg=0.069, capacity_ah=4.5, v_nom=3.6, i_cont_screen=30.0, i_peak=45.0,
         dcir_ohm=0.0128, price_usd=price_usd("CELL-P45B")[0]),
    dict(id="CELL-SAM50S", energy_wh=18.0, mass_kg=0.072, capacity_ah=5.0, v_nom=3.6, i_cont_screen=25.0, i_peak=45.0,
         dcir_ohm=0.015, price_usd=price_usd("CELL-SAM50S")[0]),
]
ORION_MAX_SERIES = ITEMS["BMS-ORION2"]["ratings"]["cells_series_max"]          # 180 per BMS / pack

# ----------------------------------------------------------------------------------------------------------------
# Parachutes (catalog), smallest one rated >= MTOW is used.
# ----------------------------------------------------------------------------------------------------------------
PARACHUTES = [
    dict(id="CHUTE-MAG601", max_kg=757.0, mass_kg=12.4, price_usd=price_usd("CHUTE-MAG601")[0]),
    dict(id="CHUTE-MAG901", max_kg=950.0, mass_kg=17.6, price_usd=price_usd("CHUTE-MAG901")[0]),
    dict(id="CHUTE-GRS990", max_kg=1050.0, mass_kg=21.7,
         price_usd=14000.0),  # estimate: quote required; Magnum 901 price + ~15 % for the larger canopy
    # Not yet in bom/catalog.json (sourced by WP D in iteration 2, to be added by WP P): Galaxy GRS 6 990-1190 SDS/FF
    # 245 m2, MTOW variants 990 / 1190 kg, total packed weight 28.9 kg, VNE 320 / 280 km/h, opening shock 45.6 kN at
    # 990 kg / 48.8 kN at 1190 kg; https://galaxysky.cz/grs-6-990-1190-sds-ff-245m2-p44-en (checked 2026-11-14).
    dict(id="GRS-6-990-1190-SDS-FF (sourced, not in catalog)", max_kg=1190.0, mass_kg=28.9,
         price_usd=16000.0),  # estimate: quote required; GRS 990 estimate + ~15 % for the 245 m2 canopy
    # iteration 3.3: Galaxy GRS 6 1200-1390 SDS/FF 245 m2, MTOW variants 1200 / 1390 kg, total weight 28.9 kg (soft pack B2),
    # VNE 280 / 260 km/h, max opening shock 48.8 kN at 1200 kg / 57.4 kN at 1390 kg (4.2 g), descent 6.3-6.7 m/s at 1000 m;
    # https://galaxysky.cz/grs-6-1200-1390-sds-ff-245m2-p45-en (checked 2026-11-18). Not yet in bom/catalog.json.
    dict(id="CHUTE-GRS1390", max_kg=1390.0, mass_kg=ITEMS["CHUTE-GRS1390"]["mass_kg"],
         price_usd=price_usd("CHUTE-GRS1390")[0]),  # catalog estimate (quote required)
]

# ----------------------------------------------------------------------------------------------------------------
# Propellers / lift rotors.  No catalog masses for E-PROPS/Sensenich: blade mass scaled from the T-Motor NS62x24
# (0.92 kg per blade at 1.575 m, PROP-TM-NS62) with D^2.5 (estimate), + 1.2 kg ground-adjustable hub and adaptor
# (estimate).  Price per 2-blade rotor from the catalog reference; 3 blades x 1.4 (estimate).
# ----------------------------------------------------------------------------------------------------------------
NS62_BLADE_KG, NS62_D = 0.92, 1.575
PROP_HUB_KG = 1.2
LIFT_PROPS = [
    dict(id="PROP-EPROPS-UAV-ADJ", d_max=1.90, price_usd=price_usd("PROP-EPROPS-UAV-ADJ")[0]),
    dict(id="PROP-SENSENICH-UAV", d_max=2.48, price_usd=price_usd("PROP-SENSENICH-UAV")[0]),
    dict(id="PROP-HELIX", d_max=2.80, price_usd=3500.0),   # estimate: no price published (quote)
]
PUSHER_PROPS = [
    dict(id="PROP-DUC-SWIRL", d_max=1.73, price2=ITEMS["PROP-DUC-SWIRL"]["price"]["value"], price3=3102.0,
         mass2=2.72, mass3=3.63),   # catalog: 2-blade USD 2,226 / 6.0 lb; 3-blade USD 3,102 / 8.0 lb
    dict(id="PROP-EPROPS-UAV-ADJ", d_max=2.09, price2=price_usd("PROP-EPROPS-UAV-ADJ")[0],
         price3=1.4 * price_usd("PROP-EPROPS-UAV-ADJ")[0], mass2=None, mass3=None),
]


def blade_mass_kg(D):
    return NS62_BLADE_KG * (D / NS62_D) ** 2.5


# ----------------------------------------------------------------------------------------------------------------
# Airfoils: section data from NeuralFoil (TL04) computed by sizing/airfoils.py at Re 3e6, ncrit 5 (rough wet lay-up);
# t/c and x_t/c from the coordinates.  Loaded lazily from sizing/results/airfoils.json.
# ----------------------------------------------------------------------------------------------------------------
AIRFOIL_NAMES = ["naca4415", "naca2415", "naca23015", "naca4412", "ls417"]

# ----------------------------------------------------------------------------------------------------------------
# Fixed systems: avionics, cabin, HV/LV parts (catalog prices; masses estimates where the catalog has none)
# ----------------------------------------------------------------------------------------------------------------
def systems_cost() -> list[tuple[str, float, str]]:
    rows = []
    for cid, qty in (("FCC-VERONTE4X", 1), ("EFIS-DYNON-HDX7", 1), ("EFIS-G5", 1), ("XPDR-TAILBEACONX", 1), ("COM-TY91", 1),
                     ("GNSS-HERE4", 2), ("AIRSPEED-MS4525", 2), ("CAB-HARNESS", 2), ("HV-DCDC", 2)):
        v, b = price_usd(cid)
        rows.append((f"{qty} x {cid}", qty * v, b))
    # iteration 3: seat shells, foam, canopy sheet and cabin trim are made parts costed from the CAD (sizing/cost.py);
    # they were counted twice in iterations 1-2 (here and in the Eastlake airframe materials)
    rows.append(("LV system: 24 V LiFePO4 backup battery, breakers, switches, lights, LV harness materials", 2500.0, "estimate"))
    rows.append(("pilot inceptors (side-stick, throttle/collective lever) and 8 control-surface servo-actuators", 6000.0, "estimate"))
    rows.append(("air data / AHRS secondary (Dynon ADAHRS class), intercom, antennas", 2000.0, "estimate"))
    return rows


# Avionics masses (uninstalled, kg; Raymer [M12] install factor applied in the model).  Estimates except FCC.
AVIONICS_UNINSTALLED_KG = 6.0      # Veronte 4x 0.75 (catalog) + EFIS 1.6 + G5 0.5 + transponder 0.45 + radio 0.5 +
                                   # 2 GNSS 0.3 + airdata/AHRS 0.5 + intercom 0.4 + antennas 0.5 + misc 0.5 (estimates)
LV_ELECTRICAL_KG = 10.0            # 2 x 600 W DC-DC (HV-DCDC), 24 V LiFePO4 2 kg, LV harness 4 kg, panel 1.5 kg, lights 1 kg
FLIGHT_CONTROLS_KG = 9.0           # 8 servo-actuators x 0.6 kg + inceptors 3 kg + wiring/brackets 1.2 kg (estimate)
SEAT_KG = 10.0                     # crash-rated composite shell + CONFOR EA foam + 4-point harness + rails, each (estimate)
FURNISHING_KG = 4.0                # cargo net/tie-downs, floor mats, sound/thermal liner, placards (estimate)
