"""Skid landing gear: skid tubes, pivoting legs, keel pivot saddles, oleo dampers, skid clamps, wear shoes, leg fairings."""
from __future__ import annotations

import math

import numpy as np

from .config import GEAR, G, Part, mm, place, rho, IDENT, SIZING, FEA_FIT
from .geom import box, compound, cyl_x, cyl_y, cyl_z, loft3d, naca4, swept_tube, tube_x, cyl, tube_between

SK = GEAR["skids"][0]
ST = GEAR["struts"]
XT = GEAR["cross_tube"]
# US stock sizes (BOM): skid 2-1/4 x 0.125 in, legs 3 x 0.250 in 6061-T6 tube
R_SK = 2.25 * 25.4 / 2
T_SK = 0.125 * 25.4
_XT = SIZING.get("landing_gear_oml", {}).get("cross_tube", XT)
R_XT, T_XT = 3.0 * 25.4 / 2, max(mm(_XT["t"]), 0.095 * 25.4)   # 3 x 0.095 in US stock (WP F phase 3.3)
P4 = FEA_FIT["P4_gear_saddle"]
Y_PIV = 160.0                           # leg pivot on the keel saddle (|y|, detail)
STROKE = 80.0                            # oleo damper stroke (>= 75 mm, WP F requirement)
BEND_R = 2.0 * mm(XT["od"])


def cross_path():
    s = ST[0]
    p1, p2 = np.array([mm(v) for v in s["p1"]]), np.array([mm(v) for v in s["p2"]])
    return [np.array([0, -p1[1], p1[2]]), np.array([0, -p2[1], p2[2]]), np.array([0, p2[1], p2[2]]), np.array([0, p1[1], p1[2]])]


def gear_parts() -> list[Part]:
    parts = []
    xs = [mm(s["p1"][0]) for s in ST]
    y_sk, z_sk = mm(SK["y"]), mm(SK["z"])
    x0, x1 = mm(SK["x_start"]), mm(SK["x_end"])
    sk = tube_x(R_SK, R_SK - T_SK, x0, x1, 0, 0)
    parts.append(Part("LG-SKID", "Skid tube", "Landing gear", "COTS-cut", "al6061_t6_extr", sk,
                      [place(0, y_sk, z_sk), place(0, -y_sk, z_sk)], "landing_gear", density=rho("al6061_t6_extr"), purchased=True,
                      notes=f"6061-T6 tube 2-1/4 x 0.125 in ({2*R_SK:.1f} x {T_SK:.2f} mm, US stock), {x1-x0:.0f} mm, ends closed with UHMW plugs; ground-handling "
                            "wheel sockets at the skid clamps.", joints="one piece (stock 12 ft)"))
    path = cross_path()
    y_piv = Y_PIV
    zp = path[2][2]
    leg_pts = [np.array([0.0, y_piv + 25.0, zp]), path[2], path[3]]
    leg = swept_tube(leg_pts, BEND_R, R_XT, R_XT - T_XT)
    LR4 = [place(x, 0, 0) for x in xs] + [(place(x, 0, 0)[0], True) for x in xs]
    parts.append(Part("LG-LEG", "Gear leg (bent tube, pivoting on the keel)", "Landing gear", "outsourced-bend",
                      G["gear_strut_section"]["material"], leg, LR4, "landing_gear", density=rho(G["gear_strut_section"]["material"]),
                      notes=f"3 x 0.095 in ({2*R_XT:.1f} x {T_XT:.2f} mm) 6061-T6 US stock tube (WP F minimum gauge 2.0 mm), one bend (radius {BEND_R:.0f} mm) by a tube "
                            "shop to T-XT-TEMPL. The leg pivots on the keel saddle and the oleo damper strokes (WP F phase 3: no "
                            "continuous clamped cross tube). Four identical legs (left = mirror placement).",
                      settings={"bends": 1, "bend_radius_mm": BEND_R}))
    end = (cyl_y(R_XT - T_XT - 0.2, y_piv + 25, y_piv + 70, 0, zp) + box(-12, 12, y_piv - 18, y_piv + 25, zp - 22, zp + 22)
           - cyl_x(10.1, -20, 20, y_piv, zp))
    parts.append(Part("LG-LEGEND", "Leg pivot end fitting", "Landing gear", "CNC", "al6061_t6_extr", end, LR4, "landing_gear",
                      density=rho("al6061_t6_extr"), machine="cnc_metal",
                      notes="6061 plug bonded and cross-bolted into the leg end; 24 mm eye with a bronze bush on the 20 mm pivot pin."))
    pad_w, pad_t = P4["pad_w"], 0.8 * P4["pad_t"]
    ztop = zp + 60
    brk = box(-pad_w / 2, pad_w / 2, y_piv - 45, y_piv + 45, ztop - pad_t, ztop)
    for sx in (-1, 1):
        brk = brk + box(sx * 13 if sx > 0 else -25, 25 if sx > 0 else -13, y_piv - 30, y_piv + 30, zp - 30, ztop - pad_t)
    brk = brk - cyl_x(10.1, -40, 40, y_piv, zp)
    for by, bx in P4["bolts"]:
        if abs(by) < 45:
            pass
    for bx in (-55, 0, 55):
        for dy in (-30, 30):
            if abs(bx) > 30:
                brk = brk - cyl_z(P4["bolt_d"] / 2, ztop - pad_t - 1, ztop + 1, bx, y_piv + dy)
    parts.append(Part("LG-SADDLE", "Keel pivot saddle (P4 pad, clevis for the leg pivot)", "Landing gear", "CNC", P4["material"], brk, LR4,
                      "landing_gear", density=rho(P4["material"]), machine="cnc_metal",
                      notes=f"Bolted to the belly hard points with the WP F P4 pad ({pad_w:.0f} mm, {pad_t:.0f} mm thick, AN6); clevis "
                            "cheeks carry the 20 mm leg pivot pin; the vertical load goes through the oleo damper."))
    pin = cyl_x(10.0, -40, 40, y_piv, zp)
    parts.append(Part("LG-PIN", "Leg pivot pin (20 mm, 4130)", "Landing gear", "COTS", "steel_4130_n", pin, LR4, "landing_gear",
                      density=rho("steel_4130_n"), purchased=True, notes="Shouldered pin, castellated nut, grease nipple."))
    # oleo dampers between each pivoting leg and the fuselage (energy absorption, WP F requirement)
    p_hor, p_skid = path[2], path[3]
    u = (p_skid - p_hor) / np.linalg.norm(p_skid - p_hor)
    dmp = GEAR.get("dampers")
    if dmp:                                                # damper end points from design/geometry.json
        lo = np.array([0.0, mm(dmp[0]["p1"][1]), mm(dmp[0]["p1"][2])])
        up = np.array([0.0, mm(dmp[0]["p2"][1]), mm(dmp[0]["p2"][2])])
        STROKE_ = mm(dmp[0].get("stroke_m", STROKE / 1000))
    else:
        y_l = 430.0
        lo = p_hor + u * ((y_l - p_hor[1]) / u[1])
        up = np.array([0.0, 385.0, lo[2] + 435.0])
    d = (up - lo) / np.linalg.norm(up - lo)
    L = float(np.linalg.norm(up - lo))
    body = tube_between(lo + d * 25, lo + d * (25 + 0.6 * L), 25)
    rod = tube_between(lo + d * (25 + 0.6 * L), up - d * 25, 11)
    eyes = [cyl(16, q - np.array([20.0, 0, 0]), (1, 0, 0), 40) for q in (lo, up)]
    damp = compound([body, rod] + eyes)
    dpl = [place(x, 0, 0) for x in xs] + [(place(x, 0, 0)[0], True) for x in xs]
    parts.append(Part("LG-DAMP", f"Skid oleo damper ({STROKE:.0f} mm stroke)", "Landing gear", "COTS", "purchased (oleo-pneumatic damper)",
                      damp, dpl, "landing_gear", mass_kg=1.2, mass_source="estimate (light-helicopter skid damper class)", purchased=True,
                      notes=f"Oleo-pneumatic damper, eye-to-eye {L:.0f} mm extended, {STROKE:.0f} mm stroke, acting in parallel "
                            "with the pivoting leg: the leg pivots on the keel and the damper carries and absorbs the landing load "
                            "(WP F estimated +6 kg for the damped gear). Spherical bearings at both eyes."))
    col = tube_between(lo - u * 35, lo + u * 35, R_XT + 10, R_XT + 0.3) + box(-20, 20, -12, 12, -12, 12).moved(
        __import__("build123d").Pos(*(lo + d * 22)))
    parts.append(Part("LG-DCL", "Damper lower collar on the gear leg", "Landing gear", "CNC", "al6061_t6_extr", col, dpl,
                      "landing_gear", density=rho("al6061_t6_extr"), machine="cnc_metal",
                      notes="Split 6061 collar, bonded and pinned to the leg; lug for the damper lower eye."))
    from .fuselage import Y_SIDE
    from build123d import Pos as _Pos
    y_in = Y_SIDE + 11.0 - up[1]                           # outer face of the cabin side panel, relative to the eye
    upf = (box(-40, 40, y_in, y_in + 10, -60, 60) + box(-32, -20, y_in, 18, -25, 25) + box(20, 32, y_in, 18, -25, 25)
           - cyl_x(8.1, -40, 40, 0, 0)).moved(_Pos(*up))     # base plate on the side panel + clevis cheeks for the damper eye
    parts.append(Part("LG-DUP", "Damper upper fitting (fuselage side hard point)", "Landing gear", "CNC", "al7075_t6_sheet", upf, dpl,
                      "landing_gear", density=rho("al7075_t6_sheet"), machine="cnc_metal",
                      notes="6061 fitting through the shell onto the cabin side panel (potted inserts, doubler inside); "
                            "upper damper eye clevis with 12 mm cheeks, 7075-T6 (WP F phases 3.1/3.3)."))
    # skid clamps where the cross tube meets the skid
    cl = box(-55, 55, -45, 45, -R_SK - 8, R_SK + 70) - cyl_x(R_SK + 0.3, -70, 70, 0, 0)
    pe = path[3] - np.array([0, mm(SK["y"]), z_sk])
    d = (path[3] - path[2]) / np.linalg.norm(path[3] - path[2])
    cl = cl - cyl(R_XT + 0.3, pe - d * 200, d, 260)
    v_full = cl.volume
    for sx in (-1, 1):                                    # side pockets outside the bore and socket
        cl = cl - box(sx * 26 if sx > 0 else -56, 56 if sx > 0 else -26, -46, 46, -R_SK - 9, R_SK + 12)
    SK_FRAC = 1 - cl.volume / v_full
    parts.append(Part("LG-SKCL", "Skid-to-leg clamp", "Landing gear", "CNC", "al6061_t6_extr", cl,
                      [place(x, y_sk, z_sk) for x in xs] + [(place(x, -y_sk, z_sk)[0], True) for x in xs], "landing_gear",
                      density=rho("al6061_t6_extr"), machine="cnc_metal", settings={"_reduction": SK_FRAC},
                      notes="Machined 6061 block, socket for the cross tube (bonded + 2 x AN4), split bore on the skid; end pockets "
                            f"remove {100*SK_FRAC:.0f} % (mass_calibration target 30 %)."))
    shoe = (tube_x(R_SK + 5, R_SK, -125, 125) & box(-300, 300, -100, 100, -100, -R_SK * 0.5))
    parts.append(Part("LG-SHOE", "Skid wear shoe", "Landing gear", "CNC", "uhmw_pe", shoe,
                      [place(x, s * y_sk, z_sk) for x in (x0 + 150, x1 - 150) for s in (1, -1)], "landing_gear",
                      density=rho("uhmw_pe"), machine="cnc",
                      notes="Replaceable UHMW-PE half-shell, screwed; raises the static ground line by 5 mm (neglected)."))
    # leg fairings
    fo = naca4("0048", 200.0, 30, te_mm=2)
    fo = np.column_stack([fo[:, 0] - 70.0, fo[:, 1]])
    a, b = path[2], path[3]
    u = (b - a) / np.linalg.norm(b - a)
    ang = math.acos(float(np.dot(u, (path[2] - path[1]) / np.linalg.norm(path[2] - path[1]))))
    tlen = BEND_R * math.tan(ang / 2) + 20
    pa, pb = a + u * tlen, b - u * 140
    en = np.cross(np.array([1.0, 0, 0]), u)
    rings = []
    for p in (pa, pb):
        rings.append(np.array([p + np.array([q[0], 0, 0]) + en * q[1] for q in fo]))
    fo_o = loft3d(rings, ruled=True)
    fo_i = loft3d([np.array([p + np.array([q[0], 0, 0]) + en * q[1] for q in
                            np.column_stack([fo[:, 0] * 0.985, fo[:, 1] * 0.93])]) for p in (pa - u * 1, pb + u * 1)], ruled=True)
    fair = fo_o - fo_i
    parts.append(Part("LG-FAIR", "Cross-tube leg fairing", "Landing gear", "composite-layup", "eglass_fabric_wet", fair,
                      [place(x, 0, 0) for x in xs] + [(place(x, 0, 0)[0], True) for x in xs], "landing_gear",
                      density=rho("eglass_fabric_wet"), skin=True,
                      notes="Glass in an FDM-printed female mould (split to the printer), clamped round the leg with a "
                            "trailing-edge zip strip."))
    return parts
