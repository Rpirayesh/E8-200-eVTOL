"""Size and optimise the E8-200 and write the interface files (design iteration 2).

    ~/tools/cadenv/bin/python -m sizing.calibration     # CAD/FEA mass calibration -> design/mass_calibration.json
    ~/tools/cadenv/bin/python -m sizing.run             # range study, selected design -> design/*.json, sizing/results/selected.json
    ~/tools/cadenv/bin/python -m sizing.trades          # trade studies, Pareto fronts, sensitivity, plots

Iteration 2: with the CAD-calibrated masses and the 1.2 g one-motor-out flare the 50 km mission no longer closes.
Following the coordinator's instruction the design is not forced: run.py finds the largest design range that closes,
freezes the design at that range (rounded down to 1 km) and reports the best designs at 40 / 45 / 50 km with their
violated constraints.  The design layout (sizing/design_out.py) is closed twice: the second pass uses the wetted area
and height of the actual OML stations.
"""
from __future__ import annotations

import json
import math

import numpy as np

from .data import ROOT
from .design_out import build, write
from .geometry_checks import checks
from .optimise import optimise

BASELINE_CFG = dict(n_rot=8, coax=False, seating="tandem", range_km=50.0)
RESULTS = ROOT / "sizing" / "results"
DISCRETE = ("nb", "flap", "lm", "pm", "cell", "npk", "airfoil", "pnb")


def jsonable(v):
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        return jsonable(v.tolist())
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v


def clean(x):
    return {k: (int(v) if k in DISCRETE else float(v)) for k, v in x.items()}


def size_at(range_km, seeds=(1, 2, 3), extra_asm=None, fixed=None):
    """Optimise at a range, lay out, re-close with the actual OML, re-optimise once; returns (x, cfg, b, feasible)."""
    cfg = dict(BASELINE_CFG, range_km=float(range_km), assumptions=dict(extra_asm or {}))
    x, f = optimise(cfg, fixed=fixed, seeds=seeds)
    x = clean(x)
    for _ in range(2):
        b = build(x, cfg)
        st = b["lay"]["stations"]
        from .model import fuselage_wetted
        cfg = dict(cfg, assumptions=dict(cfg["assumptions"], swet_f=fuselage_wetted(None, b["A"]["fus_e"], st),
                                         fus_h=max(s_["height"] for s_ in st)))
        x, f = optimise(cfg, fixed=fixed, seeds=seeds)
        x = clean(x)
    b = build(x, cfg)
    feas = bool(b["o"]["feasible"][0])
    return x, cfg, b, feas, f


def max_closing_range(lo=10.0, hi=50.0, tol=0.5):
    best = None
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        x, cfg, b, feas, _ = size_at(mid, seeds=(1, 2))
        if feas:
            lo, best = mid, (x, cfg, b)
        else:
            hi = mid
    return lo, hi, best


def summarise(b):
    o = b["o"]
    g = {k: round(float(v[0]), 4) for k, v in o["g"].items() if v[0] > 1e-9}
    return dict(range_km=b["cfg"]["range_km"], feasible=bool(o["feasible"][0]), mtow=float(o["mtow"][0]), empty=float(o["empty"][0]),
                battery_kg=float(o["battery_kg"][0]), E_nom=float(o["E_nom"][0]), cost=float(o["cost_total"][0]),
                objective=float(o["objective"][0]), x=b["x"], violated=g, P_oei=float(o["P_oei"][0]), Q_oei=float(o["Q_oei"][0]),
                P_flare=float(o["P_flare"][0]), Q_flare=float(o["Q_flare"][0]), LD=float(o["LD"][0]))


COST_STEPS = [
    # (label, assumptions, fixed) applied cumulatively; iteration-2 choices first (REB 60 on HBCi 400800, copper HV, 3-blade pusher)
    ("A: iteration-2 parts, bottom-up cost (double counts removed)", dict(hv_conductor="cu"), dict(lm=2, pnb=3)),
    ("B: + aluminium HV conductors (closes the 1.2 g flare)", dict(hv_conductor="al"), dict(lm=2, pnb=3)),
    ("C: + 2-blade DUC pusher propeller", dict(hv_conductor="al"), dict(lm=2, pnb=2)),
    ("D: + 400 V bus, REB LV windings on HBCi 400400 inverters", dict(hv_conductor="al"), dict(lm=4, pnb=2)),
    ("E: free optimum over all options", dict(hv_conductor="al"), None),
]


def main(r_sel=20.0):
    """Iteration 3 (cost-down): full 1.2 g flare, 20 km design range; sequential cost-reduction steps, each re-optimised
    and checked; cheapest compliant design frozen; cost at 15 and 25 km."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    steps, best = [], None
    for label, asm, fixed in COST_STEPS:
        x, cfg, b, feas, f = size_at(r_sel, seeds=(1, 2), extra_asm=asm, fixed=fixed)
        o = b["o"]
        row = dict(label=label, feasible=feas, x=x, mtow=float(o["mtow"][0]), cost_batch=float(o["cost_total"][0]),
                   prototype_cash=float(o["prototype_cash"][0]), labour_hours=float(o["labour_hours_prototype"][0]),
                   objective=float(o["objective"][0]), cost={k: float(np.asarray(v).ravel()[0]) for k, v in o["cost"].items()},
                   flare_power_kw=float(o["P_flare"][0]), violated={k: round(float(v[0]), 4) for k, v in o["g"].items() if v[0] > 1e-9})
        steps.append(row)
        print(label, feas, round(row["mtow"]), round(row["cost_batch"]), round(row["prototype_cash"]), row["violated"])
        if feas and (best is None or row["objective"] < best[0]):
            best = (row["objective"], x, cfg, b, f)
    _, x, cfg, b, f = best
    files = write(b, ROOT / "design")
    gchk = checks(files["geometry"])
    ranges = {}
    for r in (15.0, 25.0):
        _, _, bb, _, _ = size_at(r, seeds=(1, 2), extra_asm=dict(hv_conductor="al"))
        ranges[f"{r:.0f}"] = dict(summarise(bb), prototype_cash=float(bb["o"]["prototype_cash"][0]))
    summary = dict(iteration=3, x=x, cfg=cfg, objective=f, feasible=bool(b["o"]["feasible"][0]), selected_range_km=r_sel,
                   capability_range_km=files["design"]["results"]["range_km"], cost_steps=steps, range_cost=ranges,
                   results=files["design"]["results"], mass=files["design"]["mass_kg"], cost=files["design"]["cost"],
                   loading_cases=b["cases"], geometry_checks=gchk)
    (RESULTS / "selected.json").write_text(json.dumps(jsonable(summary), indent=1))
    return x, b


if __name__ == "__main__":
    main()
