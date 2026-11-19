"""Mission closure of the frozen design with the CFD aerodynamics (no design/ file is modified).

The sizing model (sizing/model.py, `evaluate`) is evaluated once for the selected design variables
(sizing/results/selected.json) to obtain its mission energy terms.  The frozen design (mass, battery energy and
propulsion fixed) is then re-flown with the CFD values: cruise power scaled with the CFD drag (CD0, Oswald factor),
hover energy with (1 + download)^1.5, transition energy with the mean of hover and cruise power.  The model's own
range formula (energy available after hover/transition/climb and reserve, divided by cruise power) gives the range.
Results for the nominal CFD values and for the ends of the CFD uncertainty bands go to cfd/results/mission_check.json.

    python cfd/tools/mission_check.py --cd0 0.055 --e 0.80 --download 0.05 [--cd0-band 0.1 --e-band 0.05 --dl-band 0.4]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def baseline(x: dict, cfg: dict) -> dict:
    from sizing import model
    o = model.evaluate({k: np.atleast_1d(v) for k, v in x.items()}, cfg)
    A = dict(model.A0, **cfg.get("assumptions", {}))
    f = lambda k: float(np.ravel(o[k])[0])
    return dict(o={k: f(k) for k in ("CD0", "CDi", "CL", "oswald", "D_cruise", "P_cruise", "E_hover", "E_tr", "E_climb",
                                     "eta_b_cruise", "eta_b_hover", "E_nom", "range_km", "S", "AR", "mtow")},
                f_eol=A["f_eol"], f_res=A["f_res"], aux_kw=A["aux_kw"], f_dl0=A["f_dl0"])


def run_case(B: dict, cd0: float, e: float, dl: float, dl_sizing: float, V: float) -> dict:
    """Frozen design (mass, battery, propulsion fixed): cruise power scales with drag, hover energy with
    (thrust incl. download)^1.5, transition energy with the mean of hover and cruise power."""
    o = B["o"]
    CL = o["CL"]
    CDi = CL**2 / (np.pi * o["AR"] * e)
    D = o["D_cruise"] * (cd0 + CDi) / (o["CD0"] + o["CDi"])
    P_cr = (o["P_cruise"] - B["aux_kw"]) * D / o["D_cruise"] + B["aux_kw"]
    k_h = ((1 + dl) / (1 + dl_sizing)) ** 1.5
    E_h = o["E_hover"] * k_h
    # E_tr = 2 * 0.5 * (P_h + P_cr) * t: split it with the hover/cruise power ratio of the baseline
    E_tr = o["E_tr"] * 0.5 * (k_h + P_cr / o["P_cruise"])
    E_fixed_cells = E_h / o["eta_b_hover"] + E_tr / (0.5 * (o["eta_b_hover"] + o["eta_b_cruise"])) + o["E_climb"] / o["eta_b_cruise"]
    E_avail = o["E_nom"] * B["f_eol"] * (1 - B["f_res"])
    rng = (E_avail - E_fixed_cells) * o["eta_b_cruise"] / P_cr * V * 3.6
    return dict(CD0=cd0, oswald=e, CL_cruise=CL, CDi=CDi, LD=CL / (cd0 + CDi), D_cruise_N=D, P_cruise_kW=P_cr, download=dl,
                E_hover_kWh=E_h, E_transitions_kWh=E_tr, range_km=rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd0", type=float, required=True)
    ap.add_argument("--e", type=float, required=True)
    ap.add_argument("--download", type=float, required=True)
    ap.add_argument("--cd0-band", type=float, default=0.10)
    ap.add_argument("--e-band", type=float, default=0.05)
    ap.add_argument("--dl-band", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=ROOT / "cfd" / "results" / "mission_check.json")
    a = ap.parse_args()
    sel = json.loads((ROOT / "sizing" / "results" / "selected.json").read_text())
    x, cfg = sel["x"], sel["cfg"]
    B = baseline(x, cfg)
    o = B["o"]
    V = float(x["V"])
    sd = json.loads((ROOT / "design" / "selected_design.json").read_text())
    dl_s = next((v["download_fraction"] for v in sd.values() if isinstance(v, dict) and "download_fraction" in v), B["f_dl0"])
    res = dict(sizing_model=dict(CD0=o["CD0"], oswald=o["oswald"], CL_cruise=o["CL"], LD=o["CL"] / (o["CD0"] + o["CDi"]),
                                 D_cruise_N=o["D_cruise"], P_cruise_kW=o["P_cruise"], range_km=o["range_km"], E_nom_kWh=o["E_nom"]),
               check_same_inputs=run_case(B, o["CD0"], o["oswald"], dl_s, dl_s, V),
               cfd_nominal=run_case(B, a.cd0, a.e, a.download, dl_s, V))
    worst = dict(cd0=a.cd0 * (1 + a.cd0_band), e=a.e * (1 - a.e_band), dl=a.download * (1 + a.dl_band))
    best = dict(cd0=a.cd0 * (1 - a.cd0_band), e=a.e * (1 + a.e_band), dl=a.download * (1 - a.dl_band))
    res["cfd_worst_band"] = run_case(B, worst["cd0"], worst["e"], worst["dl"], dl_s, V) | dict(inputs=worst)
    res["cfd_best_band"] = run_case(B, best["cd0"], best["e"], best["dl"], dl_s, V) | dict(inputs=best)
    # the sizing model may have been recalibrated after the design was frozen: report the CFD ranges also as the
    # frozen design's published range scaled by the model's range ratio (CFD case / same-inputs case)
    pub = sd.get("results", {}).get("range_km")
    base = res["check_same_inputs"]["range_km"]
    for k in ("check_same_inputs", "cfd_nominal", "cfd_worst_band", "cfd_best_band"):
        res[k]["range_km_scaled_to_published"] = pub * res[k]["range_km"] / base if pub else None
    res["published_range_km"] = pub
    res["required_range_km"] = cfg["range_km"]
    res["inputs"] = dict(cd0=a.cd0, e=a.e, download=a.download, bands=dict(cd0=a.cd0_band, e=a.e_band, download=a.dl_band))
    res["note"] = ("range_km is the still-air range the battery supports with the full mission energy rules of the sizing model "
                   "(hover, transitions, climb, 20 % reserve, end-of-life capacity); it must be >= required_range_km")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
