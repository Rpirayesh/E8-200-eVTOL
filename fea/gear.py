"""Skid-gear landing-energy check (drop test equivalent) -> fea/results/gear.json.

    ~/tools/cadenv/bin/python fea/gear.py

Gear frame (cross tubes + skid tubes, landing_gear_oml of geometry.json with the sized cross tube from
fea/results/sizing_update.json) clamped at the keel saddles; vertical load shared by the four skid/cross-tube
junctions.  Energy balance of a limit drop (CS-27.725 style, design_inputs.landing):
    (W - L) (h + d) = 1/2 k d^2 ,  n_gear = k d / W ,  limit inertia factor n = n_gear + L/W  (requirement n <= 3.0)
with rotor lift L = 2/3 W.  Elastic stress at the drop deflection is compared with Fty (no permanent set at limit).
If the elastic gear is too stiff, the stroke needed by an energy absorber (efficiency eta) is reported:
    s = (W - L) h / (eta n_gear,max W - (W - L)).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea.frame import Frame, Section  # noqa: E402
from fea.geometry import MAT, ROOT, load, section  # noqa: E402

HERE = Path(__file__).resolve().parent
G0 = 9.80665


def gear_frame(oml, od=None, t=None):
    f = Frame()
    ct = dict(oml["cross_tube"])
    if od:
        ct["od"] = od
    if t:
        ct["t"] = t
    cts = section(dict(type="tube", od=ct["od"], t=ct["t"], material="al6061_t6_extr"))
    sk = oml["skids"][0]
    sks = section(dict(type="tube", od=sk["diameter"], t=sk.get("t", 0.003), material="al6061_t6_extr"))
    fixed, contact = [], []
    xs = sorted({st["p1"][0] for st in oml["struts"]})
    for sgn in (-1, 1):
        xx = np.unique(np.r_[np.linspace(sk["x_start"], sk["x_end"], 14), xs])
        nodes = [f.node((x, sgn * sk["y"], sk["z"])) for x in xx]
        for i in range(len(nodes) - 1):
            f.beam(nodes[i], nodes[i + 1], sks, tag="skid")
        for st in oml["struts"]:
            x, y1, z1 = st["p1"]
            _, y2, z2 = st["p2"]
            p1 = f.node((x, sgn * y1, z1))
            p2 = f.node((x, sgn * y2, z2))
            f.beam(p1, p2, cts, n=10, vref=(1, 0, 0), tag="cross tube arm")
            ns = nodes[int(np.argmin(np.abs(xx - x)))]
            f.beam(ns, p1, Section.rigid(), vref=(1, 0, 0), tag="saddle")
            fixed.append(p2)
            contact.append(ns)
    return f, fixed, contact, cts


def analyse(g, od=None, t=None):
    oml = g["landing_gear_oml"]
    W = g["mtow_kg"] * G0
    di = g.get("_fea_inputs", {}).get("landing", {})
    h, lf = di.get("drop_height_m", 0.33), di.get("rotor_lift_fraction", 0.667)
    f, fixed, contact, cts = gear_frame(oml, od, t)
    F = np.zeros(f.ndof)
    for n in contact:
        F[6 * n + 2] = -W / len(contact)
    fd = [6 * n + k for n in fixed for k in range(6)]
    u, _ = f.solve_static(F, fd)
    d1 = -np.mean([u[6 * n + 2] for n in contact])            # deflection under 1 W
    k = W / d1
    st = f.stresses(u)
    s1 = max(r["sigma"] for r in st if r["tag"] == "cross tube arm")   # stress under 1 W
    Wn = (1 - lf) * W
    # (W - L)(h + d) = k d^2 / 2
    d = (Wn + np.sqrt(Wn**2 + 2 * k * Wn * h)) / k
    n_gear = k * d / W
    n_inertia = n_gear + lf
    Fty, Ftu = MAT["al6061_t6_extr"]["design"]["Fty"], MAT["al6061_t6_extr"]["design"]["Ftu"]
    sig_lim = s1 * n_gear
    out = dict(od=cts.meta["od"], t=cts.meta["t"], k_N_per_m=k, deflection_1g_mm=d1 * 1000, drop_height_m=h, rotor_lift_fraction=lf,
               drop_deflection_mm=d * 1000, n_gear=n_gear, n_inertia=n_inertia, sigma_limit_MPa=sig_lim / 1e6, Fty_MPa=Fty / 1e6,
               MS_yield_at_limit_drop=Fty / sig_lim - 1, MS_ultimate=Ftu / (1.5 * sig_lim) - 1)
    for eta, nm in ((0.8, "oleo-pneumatic damper (eta 0.8)"), (0.5, "linear spring (eta 0.5)")):
        n_g_max = 3.0 - lf
        out[f"stroke_needed_mm, {nm}"] = 1000 * Wn * h / (eta * n_g_max * W - Wn)
    return out


def analyse_damped(g, eta=0.8):
    """Pivoted leg + oleo damper (geometry.json landing_gear_oml.dampers): lever ratio from a 2-D leg model, energy
    balance (W - L)(h + d_skid) = eta * F_d,peak * stroke (all four dampers), gear reaction and inertia factor."""
    oml = g["landing_gear_oml"]
    W = g["mtow_kg"] * G0
    di = g.get("_fea_inputs", {}).get("landing", {})
    h, lf = di.get("drop_height_m", 0.33), di.get("rotor_lift_fraction", 0.667)
    st = oml["struts"][0]
    dm = min(oml["dampers"], key=lambda d_: abs(d_["p1"][0] - st["p1"][0]))
    P1, P2 = np.array(st["p1"][1:]), np.array(st["p2"][1:])          # (y, z): skid end, pivot
    D1, D2 = np.array(dm["p1"][1:]), np.array(dm["p2"][1:])          # damper on the leg, hard point
    u = (D2 - D1) / np.linalg.norm(D2 - D1)
    r_d = D1 - P2
    arm_d = r_d[0] * u[1] - r_d[1] * u[0]                             # moment arm of the damper about the pivot
    arm_R = P1[0] - P2[0]                                             # vertical skid reaction about the pivot
    ratio = abs(arm_R / arm_d)                                        # damper force per unit skid reaction
    s = dm["stroke_m"]
    d_skid = s * ratio                                                # skid travel at full stroke (small-angle)
    n_legs = 2 * len(oml["struts"])
    Fd = (1 - lf) * W * (h + d_skid) / (eta * s * n_legs)             # peak force per damper
    R = n_legs * Fd / ratio
    out = dict(lever_ratio_Fdamper_per_R=ratio, skid_travel_at_full_stroke_mm=d_skid * 1000, stroke_mm=s * 1000, eta=eta,
               damper_peak_force_N=Fd, gear_reaction_over_W=R / W, n_inertia=R / W + lf, drop_height_m=h, rotor_lift_fraction=lf,
               MS_inertia_factor=3.0 / (R / W + lf) - 1,
               note="leg modelled as a lever on its keel pivot; damper efficiency 0.8 (oleo-pneumatic); the leg's own bending "
                    "flexibility adds travel (conservative to ignore)")
    # reserve energy (CS-27.727 style: 1.22 x h, no lift credit beyond 1 g) - damper must not bottom
    h_r = 1.5 * h
    s_needed = None
    for s_try in np.linspace(0.04, 0.25, 400):
        F_lim = Fd * 1.5                                              # assume the oleo can develop 1.5 x the limit force
        if eta * F_lim * s_try * n_legs >= (1 - lf) * W * (h_r + s_try * ratio):
            s_needed = s_try
            break
    out["reserve_drop_1p5h_stroke_needed_mm"] = None if s_needed is None else s_needed * 1000
    return out


def main():
    upd = HERE / "results" / "sizing_update.json"
    g = load(ROOT / "design" / "geometry.json", sizing=upd if upd.exists() else None)
    if g["landing_gear_oml"].get("dampers"):
        dmp = analyse_damped(g)
        res = dict(damped_gear=dmp, verdict="PASS" if dmp["n_inertia"] <= 3.0 else "FAIL: n > 3",
                   note="drop height 0.33 m (13 in) and rotor lift 2/3 W per CS-27.725; strength of legs, saddles and damper "
                        "hard points from the global landing cases (gear reaction 2.33 W)")
        (HERE / "results" / "gear.json").write_text(json.dumps(res, indent=1, default=float))
        print(json.dumps(res, indent=1, default=float))
        return
    base = analyse(g)
    print(json.dumps(base, indent=1))
    # elastic alternative study: what arm length would an elastic 6061 cross tube need for n <= 3 without yield
    E, Fty = MAT["al6061_t6_extr"]["design"]["E"], MAT["al6061_t6_extr"]["design"]["Fty"]
    W = g["mtow_kg"] * G0
    lf = base["rotor_lift_fraction"]
    h = base["drop_height_m"]
    n_g = 3.0 - lf
    d_req = (1 - lf) * h / (0.5 * n_g - (1 - lf))               # elastic: (W-L)(h+d) = 0.5 n_g W d
    alt = []
    for od in (0.05, 0.064, 0.076):
        c = od / 2
        L_req = np.sqrt(3 * E * c * d_req / Fty)                # cantilever arm: sigma/delta = 3 E c / L^2
        alt.append(dict(od=od, elastic_stroke_needed_mm=d_req * 1000, cantilever_arm_needed_m=float(L_req)))
    res = dict(current_gear=base, elastic_aluminium_alternatives=alt,
               verdict=("PASS" if base["n_inertia"] <= 3.0 and base["MS_yield_at_limit_drop"] >= 0 else "FAIL: gear too stiff for the "
                        "limit drop; add an energy absorber (stroke as listed) or a long flexible composite bow"),
               note="drop height 0.33 m (13 in) and rotor lift 2/3 W per CS-27.725; skid contact assumed under the cross tubes")
    (HERE / "results" / "gear.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(alt, indent=1), res["verdict"])


if __name__ == "__main__":
    main()
