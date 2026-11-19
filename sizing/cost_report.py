"""Cost breakdown of the frozen design in two views (iteration 3), and the decomposition of the iteration-2 figure.

    ~/tools/cadenv/bin/python -m sizing.cost_report [--rate 55] [--N 10]

Writes sizing/results/cost_breakdown.json and .md.  View (a): out-of-pocket cash to build ONE prototype in our shop
(labour listed separately in hours); view (b): per aircraft at a batch of N.
"""
from __future__ import annotations

import json
import sys

import numpy as np

from . import data as D
from .cost import (H_COTS_INSTANCE, H_FINAL, H_PER_CELL, H_PER_PACK, H_WIRING, OUTSOURCED, QC_FRAC, airframe_cost,
                   learning_factor, load_rates)
from .model import evaluate
from .run import RESULTS

COTS_KEYS = ["lift_motors", "inverters", "lift_propellers", "pusher_motor", "pusher_propeller", "battery", "parachute",
             "hv_cooling_harness", "systems_avionics_cabin"]


def breakdown(x, cfg, rate=55.0, N=10):
    asm = dict(cfg.get("assumptions", {}), labour_rate=rate, N_units=N)
    cfg = dict(cfg, assumptions=asm)
    o = evaluate({k: np.atleast_1d(v) for k, v in x.items()}, cfg)
    f = lambda v: float(np.asarray(v).ravel()[0])  # noqa: E731
    cost = {k: f(v) for k, v in o["cost"].items()}
    mass = {k: f(v) for k, v in o["mass"].items()}
    n = int(cfg["n_rot"])
    cells, npk = f(o["cells"]), f(o["npk"])
    n_push = 2 if D.PUSHER_MOTORS[int(x["pm"])].get("twin") else 1
    ac = airframe_cost(mass, N, rate, load_rates(), n_cells=cells, n_packs=npk, n_cots_instances=4 * n + 3 * n_push + 10 + 30 + (n if asm.get("hub_fairing_kg", 0) > 0 else 0))
    cots = {k: cost[k] for k in COTS_KEYS + ["hub_fairings"] if cost.get(k)}
    made = {k: v[0] for k, v in ac["by_group"].items()}
    hours = {f"made parts: {k}": v[1] for k, v in ac["by_group"].items()}
    hours.update({"COTS installation": H_COTS_INSTANCE * (4 * n + 3 * n_push + 40 + (n if asm.get("hub_fairing_kg", 0) > 0 else 0)), "battery assembly": H_PER_CELL * cells + H_PER_PACK * npk,
                  "HV and LV wiring": H_WIRING, "final assembly, rigging, systems test": H_FINAL})
    hours["quality control (10 %)"] = QC_FRAC * sum(hours.values())
    h_air = sum(hours.values())
    proto = dict(cots=cots, cots_total=sum(cots.values()), made_parts_materials_consumables=made,
                 made_total=sum(made.values()), tooling_materials=ac["tooling_materials"], outsourced=dict(OUTSOURCED),
                 outsourced_total=sum(OUTSOURCED.values()))
    proto["cash_total"] = proto["cots_total"] + proto["made_total"] + proto["tooling_materials"] + proto["outsourced_total"]
    proto["labour_hours"] = dict(hours, tooling=ac["tooling_hours"])
    proto["labour_hours_total"] = h_air + ac["tooling_hours"]
    proto["labour_value_at_rate"] = proto["labour_hours_total"] * rate
    lf = learning_factor(N)
    batch = dict(cots_total=proto["cots_total"], made_total=proto["made_total"], outsourced_total=proto["outsourced_total"],
                 labour=h_air * lf * rate, labour_hours_per_aircraft=h_air * lf, tooling_amortised=ac["tooling_materials"] / N,
                 learning_factor=lf, N=N, rate=rate)
    batch["per_aircraft"] = (batch["cots_total"] + batch["made_total"] + batch["outsourced_total"] + batch["labour"]
                             + batch["tooling_amortised"])
    return dict(prototype=proto, batch=batch, mtow=f(o["mtow"]), feasible=bool(o["feasible"][0]),
                eastlake_reference=f(o["eastlake_recurring"]))


ITER2_DECOMPOSITION = {
    "COTS bottom-up (catalog)": 270000,
    "  of which lift motors 8 x REB 60 (catalog estimate mid USD 8 k)": 64000,
    "  of which inverters 9 x HBCi 400800 (catalog estimate mid USD 7 k)": 63000,
    "  of which systems, avionics, cabin list": 56632,
    "  of which battery (cells, holders, BMS, contactors, fuses, enclosure, 0.02 h/cell assembly)": 37468,
    "  of which parachute, propellers, pusher motor, HV/cooling": 48754,
    "Eastlake recurring airframe (GA regression, N = 10, F_cert 0.5)": 177911,
    "  of which manufacturing labour 2,705 h/aircraft x USD 55": 148796,
    "  of which materials regression": 15575,
    "  of which quality control (13 % of labour)": 13540,
}
DOUBLE_COUNTS = [
    "seat shells, canopy frame hardware and cabin trim (USD 3,000 estimate) were in the systems list AND in the Eastlake airframe materials",
    "canopy polycarbonate sheet (USD 480) and CONFOR seat foam (USD 176) were in the systems list AND in the Eastlake airframe materials",
    "battery assembly labour (0.02 h/cell x USD 55 = USD 2.6 k) was in the battery cost; it is now only in the labour hours",
    "the Eastlake labour (2,705 h/aircraft) is a certified-GA regression on airframe mass and speed; it is replaced by the "
    "bottom-up hours of the CAD parts (no double count, but a different and lower basis for an in-house experimental build)",
]


def write_report(b, x, rate, N, path_md, path_json, steps=None, ranges=None):
    p, bt = b["prototype"], b["batch"]
    L = ["# E8-200 cost breakdown (iteration 3, generated by sizing/cost_report.py)", "",
         f"Frozen design MTOW {b['mtow']:.0f} kg. Labour rate USD {rate:.0f}/h (parameter), batch N = {N}, learning 85 % "
         f"(cumulative average factor {bt['learning_factor']:.3f}). Prices: bom/catalog.json (quote items at the middle of the "
         "catalog estimate range; EUR x 1.10, GBP x 1.27); made parts from the CAD parts list (sizing/cost.py). Engineering, "
         "certification, flight test, facilities and machines are not included.", "",
         "## (a) One prototype built in our shop: out-of-pocket cash", "", "| Item | USD |", "|---|---|"]
    for k, v in p["cots"].items():
        L.append(f"| COTS: {k.replace('_', ' ')} | {v:,.0f} |")
    L.append(f"| **COTS subtotal** | **{p['cots_total']:,.0f}** |")
    for k, v in p["made_parts_materials_consumables"].items():
        L.append(f"| made-part materials + consumables: {k.replace('_', ' ')} | {v:,.0f} |")
    L.append(f"| **materials + consumables subtotal** | **{p['made_total']:,.0f}** |")
    L.append(f"| tooling materials (MDF/EPS plugs, moulds, jigs, FDM, tooling resin) | {p['tooling_materials']:,.0f} |")
    for k, v in p["outsourced"].items():
        L.append(f"| outsourced: {k} | {v:,.0f} |")
    L += [f"| **cash total (excl. labour)** | **{p['cash_total']:,.0f}** |", "",
          "Labour (own shop), hours:", "", "| Task | hours |", "|---|---|"]
    for k, v in p["labour_hours"].items():
        L.append(f"| {k.replace('_', ' ')} | {v:,.0f} |")
    L += [f"| **total** | **{p['labour_hours_total']:,.0f}** |", "",
          f"At USD {rate:.0f}/h the labour is worth USD {p['labour_value_at_rate']:,.0f}; prototype total incl. labour "
          f"USD {p['cash_total'] + p['labour_value_at_rate']:,.0f}.", "",
          f"## (b) Per aircraft at a batch of {N}", "", "| Item | USD |", "|---|---|",
          f"| COTS | {bt['cots_total']:,.0f} |", f"| made-part materials + consumables | {bt['made_total']:,.0f} |",
          f"| outsourced services | {bt['outsourced_total']:,.0f} |",
          f"| labour {bt['labour_hours_per_aircraft']:,.0f} h x USD {rate:.0f} (learning applied) | {bt['labour']:,.0f} |",
          f"| tooling materials / {N} | {bt['tooling_amortised']:,.0f} |", f"| **per aircraft** | **{bt['per_aircraft']:,.0f}** |", "",
          f"Eastlake recurring airframe for the same airframe mass (reference only): USD {b['eastlake_reference']:,.0f}.", "",
          "## How the iteration-2 USD 448 k was composed", "", "| Item | USD |", "|---|---|"]
    for k, v in ITER2_DECOMPOSITION.items():
        L.append(f"| {k} | {v:,.0f} |")
    L += ["", "Double counts / basis issues fixed in iteration 3:", ""] + [f"- {d}" for d in DOUBLE_COUNTS]
    if steps:
        L += ["", "## Cost-reduction steps (each re-optimised at 20 km with all requirements)", "",
              "| Step | feasible | MTOW kg | per aircraft (N=10) USD | prototype cash USD | prototype hours | violated |", "|---|---|---|---|---|---|---|"]
        for s_ in steps:
            L.append(f"| {s_['label']} | {s_['feasible']} | {s_['mtow']:.0f} | {s_['cost_batch']:,.0f} | {s_['prototype_cash']:,.0f} | "
                     f"{s_['labour_hours']:,.0f} | {', '.join(s_['violated']) or '-'} |")
    if ranges:
        L += ["", "## Range sensitivity", "", "| Design range | feasible | MTOW kg | per aircraft USD | prototype cash USD |", "|---|---|---|---|---|"]
        for r, v in ranges.items():
            L.append(f"| {r} km | {v['feasible']} | {v['mtow']:.0f} | {v['cost']:,.0f} | {v['prototype_cash']:,.0f} |")
    path_md.write_text("\n".join(L) + "\n")
    path_json.write_text(json.dumps(dict(b, steps=steps, ranges=ranges, iteration2_decomposition=ITER2_DECOMPOSITION,
                                         double_counts=DOUBLE_COUNTS), indent=1, default=float))


def main():
    args = sys.argv[1:]
    rate = float(args[args.index("--rate") + 1]) if "--rate" in args else 55.0
    N = int(args[args.index("--N") + 1]) if "--N" in args else 10
    sel = json.loads((RESULTS / "selected.json").read_text())
    b = breakdown(sel["x"], sel["cfg"], rate, N)
    write_report(b, sel["x"], rate, N, RESULTS / "cost_breakdown.md", RESULTS / "cost_breakdown.json",
                 sel.get("cost_steps"), sel.get("range_cost"))
    for r in (0.0, 35.0, 55.0, 75.0):
        bb = breakdown(sel["x"], sel["cfg"], r, N)
        print(f"rate {r:5.0f}: prototype cash {bb['prototype']['cash_total']:9,.0f} + {bb['prototype']['labour_hours_total']:6,.0f} h; "
              f"batch per aircraft {bb['batch']['per_aircraft']:9,.0f}")


if __name__ == "__main__":
    main()
