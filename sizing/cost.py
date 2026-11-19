"""Bottom-up cost model of the E8-200 (design iteration 3).

Replaces the Eastlake airframe regression (a certified-GA labour-hour model) by a build-up from the WP G CAD parts list
(cad/parts.json: material, process, mass and instance count of every made part and tooling item):

  materials      = sum(part mass x material price x scrap/buy-to-fly factor)       (catalog prices, see MATERIAL)
  consumables    = 35 % of composite material + 10 % of tooling material            (estimate)
  tooling        = tooling-part mass x tooling-material price (MDF, EPS, plywood, FDM)
  outsourced     = waterjet, thermoforming, tube bending, surface treatment, paint (estimates per service)
  labour hours   = per-process hours: composite h/kg, CNC programming per unique part + run time per instance,
                   COTS installation per instance, battery assembly per cell and per pack, wiring, final assembly
                   and systems test, QC (estimates; labour rate is a parameter)

Two views:
  prototype  - out-of-pocket cash for ONE aircraft built in our shop: COTS + materials + consumables + tooling
               materials + outsourced services; labour shown separately as hours (x rate if wanted)
  batch      - per aircraft at N units: COTS + materials + consumables + outsourced + labour hours x rate x learning
               factor (85 % curve, cumulative average) + tooling materials / N

Per-group USD/kg and h/kg rates are derived here from the CAD parts so that the sizing model can scale them with the
group masses.  Engineering, certification, flight test and facilities are non-recurring and not in either view.

    ~/tools/cadenv/bin/python -m sizing.cost        # prints the rates and the prototype breakdown of the frozen design
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

from .data import FX_USD, ROOT, price_usd

# ------------------------------------------------------------------------------------------------ prices
# USD per kg of finished part, incl. scrap / buy-to-fly; basis given per entry
_yd_m2 = 0.9144 * 1.27
CF_FABRIC = 28.5 / (_yd_m2 * 0.193)                    # MAT-CF-FABRIC 20+ yd tier: USD 28.50/yd, 193 g/m2, 50 in -> 127 USD/kg
EPOXY = (439.0 + 1.6 * 97.75) / (3.78 * 1.16 * 1.4)     # MAT-RESIN-MGS gallon + ~1.6 qt H285F per gallon (100:40) -> ~99 USD/kg
LAMINATE_CF = 0.55 * CF_FABRIC * 1.25 + 0.45 * EPOXY * 1.15   # fibre mass fraction 0.55; 25 % fabric / 15 % resin waste
LAMINATE_GL = 0.50 * 15.0 * 1.25 + 0.50 * EPOXY * 1.15      # E-glass fabric ~USD 15/kg (estimate)
PVC_CORE = (109.0 * FX_USD["EUR"]) / (2.44 * 1.22 * 0.010 * 80.0) * 1.2   # MAT-FOAM-H80 sheet -> ~57 USD/kg with 20 % scrap
XPS = 13.0 * 1.3                                        # XPS board ~USD 40 per 4x8x2 in (estimate), 30 % hot-wire scrap
TUBE_CF = 645.0 / (math.pi * 0.103 * 0.0016 * 1550 * 2.438)   # MAT-TUBE-DP-4x96 per kg of tube (~330 USD/kg)
AL_PLATE = 15.0 * 3.0                                   # 6061 plate/bar ~USD 15/kg (estimate) x buy-to-fly 3 for machined parts
AL_SHEET = 62.75 / (0.0016 * 0.6096 * 0.9144 * 2700) * 1.3    # MAT-AL-6061-SHEET -> ~34 USD/kg with 30 % scrap
AL7075 = 25.0 * 3.0
STEEL = 15.0 * 3.0
PC = (239.99 + 80.0) / (1.219 * 2.438 * 0.0032 * 1200) * 1.5  # CAB-PC-SHEET + surcharge, 50 % thermoform trim
FDM = 30.0
MATERIAL = [   # (substring of the CAD material string, USD/kg, class)
    ("sandwich", 0.6 * LAMINATE_CF + 0.4 * PVC_CORE, "composite"),
    ("cf_fabric_wet skin on xps", 0.6 * LAMINATE_CF + 0.4 * XPS, "composite"),
    ("cf_ud_wet", LAMINATE_CF, "composite"), ("cf_fabric_wet", LAMINATE_CF, "composite"),
    ("eglass", LAMINATE_GL, "composite"), ("xps_foam", XPS, "composite"), ("pvc_h", PVC_CORE, "composite"),
    ("cf_tube", TUBE_CF, "tube"), ("al6061_t6_extr", AL_PLATE, "metal"), ("al6061_t6_sheet", AL_SHEET, "metal"),
    ("al7075", AL7075, "metal"), ("steel", STEEL, "metal"), ("polycarbonate", PC, "other"), ("confor", 60.0, "other"),
    ("uhmw", 20.0, "other"), ("asa", FDM, "other"), ("petg", FDM, "other"), ("pa_cf", 80.0, "other"),
    ("g10", 30.0, "other"),
    # tooling
    ("mdf", 1.2, "tooling"), ("eps_tooling", 6.0, "tooling"), ("birch_plywood", 3.0, "tooling"), ("pu_tooling", 25.0, "tooling"),
]
CONSUMABLE_FRAC = dict(composite=0.35, tooling=0.10)     # peel ply, bagging, release, brushes, gloves / sealer, wax (estimate)

# labour (estimates; rate is a parameter)
H_PER_KG_COMPOSITE = 9.0       # hand lay-up incl. trimming, bonding, fairing (moldless/foam-core home-built practice, MF10)
H_CNC_UNIQUE, H_CNC_INSTANCE = 4.0, 1.5
H_COTS_INSTANCE = 2.0
H_PER_CELL, H_PER_PACK = 0.02, 30.0
H_WIRING = 160.0               # HV + LV harnesses
H_FINAL = 300.0                # final assembly, rigging, systems integration and ground test
QC_FRAC = 0.10
H_TOOLING_UNIQUE, H_TOOLING_INSTANCE, H_FDM = 6.0, 1.0, 0.5
LEARNING = 0.85                # 85 % learning curve (cumulative average over N units)

OUTSOURCED = {                 # USD per aircraft (estimates)
    "waterjet / laser-cut flat parts": 600.0,
    "canopy and window thermoforming": 2500.0,
    "cross-tube bending": 400.0,
    "aluminium surface treatment (alodine/anodize)": 1500.0,
    "primer and paint materials": 1500.0,
    "fasteners and hardware (AN/MS)": 1500.0,
}


def _price(material: str):
    for key, usd, cls in MATERIAL:
        if key in material:
            return usd, cls
    return None, "cots"


def learning_factor(N: int, lc: float = LEARNING) -> float:
    b = math.log(lc, 2)
    return sum((k) ** b for k in range(1, N + 1)) / N


def parts_rates(reductions: dict | None = None) -> dict:
    """USD/kg and h/kg per mass group from the CAD parts (after the calibration reductions), plus tooling totals."""
    parts = json.loads((ROOT / "cad" / "parts.json").read_text())["parts"]
    red = reductions or {}
    g = defaultdict(lambda: dict(kg=0.0, usd=0.0, hours=0.0, cons=0.0))
    tooling = dict(kg=0.0, usd=0.0, hours=0.0, cons=0.0)
    uniq_cnc = defaultdict(int)
    for p in parts:
        q, m = p.get("qty") or 0, p.get("mass_kg_each") or 0.0
        if not q:
            continue
        grp = p.get("mass_group")
        frac = 1.0 - red.get(p["id"], {}).get("fraction", 0.0)
        kg = m * q * frac
        usd_kg, cls = _price(p["material"])
        if grp == "tooling":
            tooling["kg"] += kg
            tooling["usd"] += kg * (usd_kg or 1.2)
            tooling["hours"] += H_TOOLING_UNIQUE + H_TOOLING_INSTANCE * q if p["process"] == "CNC" else H_FDM * q
            continue
        if p["process"].startswith("COTS") and p["process"] != "COTS-cut" or grp in ("payload", "battery"):
            continue            # purchased items are costed from the catalog in the model
        d = g[grp]
        d["kg"] += kg
        if usd_kg:
            d["usd"] += kg * usd_kg
            d["cons"] += kg * usd_kg * CONSUMABLE_FRAC.get(cls, 0.0)
        if p["process"] == "composite-layup":
            d["hours"] += kg * H_PER_KG_COMPOSITE
        elif p["process"] == "CNC":
            d["hours"] += H_CNC_UNIQUE + H_CNC_INSTANCE * q
        elif p["process"] in ("COTS-cut", "FDM"):
            d["hours"] += 0.5 * q
        elif p["process"].startswith("outsourced"):
            d["hours"] += 1.0 * q
    rates = {k: dict(kg=round(v["kg"], 2), usd_per_kg=round((v["usd"] + v["cons"]) / v["kg"], 2) if v["kg"] else 0.0,
                     h_per_kg=round(v["hours"] / v["kg"], 3) if v["kg"] else 0.0, usd=round(v["usd"], 1), cons=round(v["cons"], 1),
                     hours=round(v["hours"], 1)) for k, v in g.items()}
    tooling["cons"] = tooling["usd"] * CONSUMABLE_FRAC["tooling"] + 3 * price_usd("MAT-RESIN-WEST")[0]
    return dict(groups=rates, tooling={k: round(v, 1) for k, v in tooling.items()},
                basis=dict(CF_FABRIC=round(CF_FABRIC, 1), EPOXY=round(EPOXY, 1), LAMINATE_CF=round(LAMINATE_CF, 1),
                           LAMINATE_GL=round(LAMINATE_GL, 1), PVC_CORE=round(PVC_CORE, 1), XPS=XPS, TUBE_CF=round(TUBE_CF, 1),
                           AL_PLATE=AL_PLATE, AL_SHEET=round(AL_SHEET, 1), PC=round(PC, 1)))


# model mass keys -> CAD mass groups whose rates they use
GROUP_MAP = dict(wing="wing", tail="tail", fuselage="fuselage", booms="booms", rotor_pylons_mounts="booms", landing_gear="landing_gear",
                 cooling="cooling", seats="seats", avionics="avionics", parachute="parachute", pusher_motor="pusher_motor",
                 pusher_propeller="pusher_propeller", flight_controls="flight_controls", hv_harness="hv_harness")
MADE_FRACTION = dict(parachute=6.53 / 35.43, pusher_motor=3.52 / 27.32, pusher_propeller=0.66 / 3.63, avionics=1.85 / 12.53,
                     cooling=0.96 / 10.36, seats=(22.67 - 4.0 - 2.0) / 22.67)   # made-part share of groups with COTS content


def load_rates():
    p = ROOT / "design" / "cost_rates.json"
    if p.exists():
        return json.loads(p.read_text())
    r = parts_rates({})        # iteration 3.1: cad/parts.json is the iteration-3 build with the reductions already applied
    p.write_text(json.dumps(r, indent=1))
    return r


def airframe_cost(mass: dict, N: int = 10, rate: float = 55.0, rates: dict | None = None, n_cells: float = 0.0, n_packs: float = 0.0,
                  n_cots_instances: float = 120.0):
    """Made-part materials, consumables, labour hours and tooling for the given model masses (arrays or floats)."""
    R = rates or load_rates()
    G = R["groups"]
    mat, hours = 0.0, 0.0
    by = {}
    for key, grp in GROUP_MAP.items():
        if key == "rotor_pylons_mounts" and "rotor_pylons_mounts" in G:
            grp = "rotor_pylons_mounts"
        if key not in mass or grp not in G:
            continue
        kg = mass[key] * MADE_FRACTION.get(key, 1.0)
        m_ = kg * G[grp]["usd_per_kg"]
        h_ = kg * G[grp]["h_per_kg"]
        by[key] = (m_, h_)
        mat = mat + m_
        hours = hours + h_
    hours = hours + H_COTS_INSTANCE * n_cots_instances + H_PER_CELL * n_cells + H_PER_PACK * n_packs + H_WIRING + H_FINAL
    hours = hours * (1 + QC_FRAC)
    outs = sum(OUTSOURCED.values())
    tool = R["tooling"]["usd"] + R["tooling"]["cons"]
    tool_h = R["tooling"]["hours"]
    lf = learning_factor(N)
    return dict(materials=mat, hours_prototype=hours, outsourced=outs, tooling_materials=tool, tooling_hours=tool_h,
                labour_batch=hours * lf * rate, tooling_per_unit=tool / N, learning=lf, by_group=by)


if __name__ == "__main__":
    r = parts_rates({})
    (ROOT / "design" / "cost_rates.json").write_text(json.dumps(r, indent=1))
    print(json.dumps(r, indent=1))
    print("learning factor N=10:", round(learning_factor(10), 3))
