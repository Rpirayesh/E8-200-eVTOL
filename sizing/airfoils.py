"""Wing section data for the airfoil trade (NeuralFoil, resources TL04; coordinates AE06 / NASA TN D-7428 for LS(1)-0417).

Writes sizing/results/airfoils.json: t/c, x of max thickness, cl_max, alpha at cl_max, cm0, cl_alpha, cd at cl 0.4-0.9
at Re = 3e6, M = 0.12, ncrit = 5 (lowered from 9 for a wet lay-up / painted foam-core surface).

    ~/tools/cadenv/bin/python -m sizing.airfoils
"""
from __future__ import annotations

import json

import numpy as np

from .data import AIRFOIL_NAMES, ROOT

OUT = ROOT / "sizing" / "results" / "airfoils.json"


def _airfoil(name):
    import aerosandbox as asb
    if name == "ls417":
        pts = np.loadtxt(ROOT / "validation" / "cfd" / "reference" / "ls417_coordinates_TND7428.dat", skiprows=1)
        return asb.Airfoil(name="ls417", coordinates=pts)
    return asb.Airfoil(name)


def compute(re=3.0e6, mach=0.12, ncrit=5.0) -> dict:
    out = {}
    for name in AIRFOIL_NAMES:
        af = _airfoil(name)
        a = np.linspace(-6, 22, 113)
        r = af.get_aero_from_neuralfoil(alpha=a, Re=re, mach=mach, n_crit=ncrit, model_size="xlarge")
        cl, cd, cm = (np.asarray(r[k]) for k in ("CL", "CD", "CM"))
        i = int(np.argmax(cl))
        lin = (a > -2) & (a < 6)
        cla = np.polyfit(np.radians(a[lin]), cl[lin], 1)[0]
        xs = np.linspace(0.01, 0.99, 197)
        th = np.asarray(af.local_thickness(x_over_c=xs))
        k = slice(0, i)
        out[name] = dict(t_c=float(th.max()), x_t_c=float(xs[np.argmax(th)]), cl_max=float(cl[i]), alpha_clmax_deg=float(a[i]),
                         cm0=float(np.interp(0.0, a, cm)), cl_alpha_per_rad=float(cla),
                         cl0=float(np.interp(0.0, a, cl)), alpha0_deg=float(-np.interp(0.0, a, cl) / cla * 57.2958),
                         cd_at_cl={f"{c:.1f}": float(np.interp(c, cl[k], cd[k])) for c in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9)},
                         re=re, mach=mach, ncrit=ncrit, source="NeuralFoil xlarge (TL04)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    return out


def load() -> dict:
    if not OUT.exists():
        return compute()
    return json.loads(OUT.read_text())


if __name__ == "__main__":
    for k, v in compute().items():
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})
