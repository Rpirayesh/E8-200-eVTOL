"""Battery packs (boxes, cell modules, cold plates, BMS/contactors), pusher installation, ballistic parachute,
seats and occupants, instrument panel and avionics, LV electrical, inceptors, HV harness runs."""
from __future__ import annotations

import math

import numpy as np
from build123d import Compound, Pos, Rot

from .config import (BOOM_Z, mass_item, FEA_FIT, BATS, CAT, CHUTE, DETAIL, PUSH, S, SEATS, G, Part, mm, oml, oml_half_width, oml_z_range, place,
                     rho, IDENT, PANEL, WLOC, WING, BOOM_Y, BOOM_Z, wing_to_global)
from .geom import (box, compound, cyl, cyl_x, cyl_y, cyl_z, naca4, prism_y, prism_z, rounded_rect, sphere, tube_between,
                   tube_x, loft3d, circle, fuse_all)
from .fuselage import BH_X, FLOOR_Z, PT, Y_SIDE

CP = 22.2                                            # cell pitch in the G10 holder (detail)
CD = DETAIL["cell_d"]
CH = DETAIL["cell_h"]
HOLD_T = 5.0
MOD_H = CH + 2 * HOLD_T
COLD_T = 6.0
NP = S["battery"]["parallel_per_pack"]
NS = S["battery"]["series"]
CELL = CAT[S["battery"]["cell"]["name"]]


def _tier(n_cells, rows, across, px, py):
    cells = []
    k = 0
    for r in range(rows):
        for c in range(across):
            if k >= n_cells:
                break
            cells.append(cyl_z(CD / 2, HOLD_T, HOLD_T + CH, px / 2 + r * px, py / 2 + c * py))
            k += 1
    lx, ly = rows * px, across * py
    plates = [box(0, lx, 0, ly, 0, HOLD_T), box(0, lx, 0, ly, HOLD_T + CH, MOD_H)]
    net = (lx * ly - n_cells * math.pi * (CD / 2) ** 2) * HOLD_T * 2
    m = n_cells * CELL["mass_kg"] + net * 1e-9 * rho("g10")
    return Compound(children=cells + plates), (lx, ly), m


def battery_parts() -> list[Part]:
    parts = []
    b = BATS[0]
    L, W, H = mm(b["length"]), mm(b["width"]), mm(b["height"])
    t = DETAIL["bat_wall"]
    pl = [place(mm(p["x"]), mm(p["y"]), mm(p["z"])) for p in BATS]
    npk = b["series"] * b["parallel"]
    tiers = b.get("tiers", 2)
    rows, across = b.get("rows_per_tier", 15), b.get("cells_across", 26)
    px = (L - 2 * t - 8) / rows
    py = (W - 2 * t - 8) / across
    assert min(px, py) >= CD + 0.4, "cells do not fit the pack box"
    per = rows * across
    counts = [min(per, npk - k * per) for k in range(tiers)]
    assert sum(counts) >= npk, "cells do not fit the pack box"
    z_t = [-H / 2 + t + COLD_T + k * (MOD_H + COLD_T) for k in range(tiers)]
    assert z_t[-1] + MOD_H <= H / 2 - 2.0, "tiers do not fit the pack height"
    for k, n in enumerate(counts):
        sol, (lx, ly), m = _tier(n, rows, across, px, py)
        inst = [(p[0] * Pos(-lx / 2, -ly / 2, z_t[k]), False) for p in pl]
        parts.append(Part(f"BAT-TIER{k + 1}", f"Battery cell tier {k + 1} ({n} x P50B in G10 holders)", "Battery", "COTS",
                          f"{S['battery']['cell']['name']} cells in g10 holders", sol, inst, "battery", mass_kg=m,
                          mass_source="cell count x catalog cell mass + G10 holder volume", purchased=True,
                          notes=f"{n} Molicel P50B 21700 cells on a {px:.1f} x {py:.1f} mm grid ({rows} rows x {across}), "
                                f"{b['series']}s{b['parallel']}p per pack over {tiers} tiers; nickel-plated copper bus strips laser-welded; "
                                "waterjet-cut 5 mm G10 holder plates.",
                          settings={"cells": n, "pack": f"{b['series']}s{b['parallel']}p"}))
    slot_w = L
    # box (open top, 5052/6061 sheet), lid, cold plates
    bx = box(-L / 2, L / 2, -W / 2, W / 2, -H / 2, H / 2 - 2.0) - box(-L / 2 + t, L / 2 - t, -W / 2 + t, W / 2 - t, -H / 2 + t, H / 2 + 1)
    parts.append(Part("BAT-BOX", "Battery box (folded aluminium)", "Battery", "outsourced-waterjet", "al6061_t6_sheet", bx, pl,
                      "battery", density=rho("al6061_t6_sheet"),
                      notes=f"{t} mm sheet, flat pattern waterjet-cut by a supplier, folded on a brake, corners riveted "
                            "(CherryMAX) and sealed; mica fire liner inside; vent port to BAT-VENT. Box envelope from design/geometry.json.",
                      settings={"flat_pattern": f"{L + 2*H:.0f} x {W + 2*H:.0f} mm", "bend_radius": "2 t"}))
    lid = box(-L / 2, L / 2, -W / 2, W / 2, H / 2 - 2.0, H / 2)
    for x in np.linspace(-L / 2 + 20, L / 2 - 20, 8):
        for y in (-W / 2 + 10, W / 2 - 10):
            lid = lid - cyl_z(3.2, H / 2 - 5, H / 2 + 5, x, y)
    parts.append(Part("BAT-LID", "Battery box lid (bolts to the floor)", "Battery", "outsourced-waterjet", "al6061_t6_sheet", lid, pl,
                      "battery", density=rho("al6061_t6_sheet"),
                      notes="2 mm lid; the pack hangs from the floor on 16 x AN3 into potted inserts; removed downwards."))
    cp = box(-L / 2 + t, L / 2 - t, -W / 2 + t, W / 2 - t, 0, COLD_T)
    parts.append(Part("BAT-CP", "Battery cold plate (one per tier)", "Battery", "CNC", "al6061_t6_extr", cp,
                      [(p[0] * Pos(0, 0, z), False) for p in pl for z in (z_t[0] - COLD_T, z_t[1] - COLD_T)], "battery",
                      density=rho("al6061_t6_extr") * 0.7, machine="cnc",
                      notes="6 mm 6061 plate with milled coolant channels and a bonded cover (net density 70 %); thermal pad to the modules."))
    # electronics in the spare slot (BMS, 2 contactors, fuse)
    # BMS, contactors and fuse beside each pack (outboard of the box, below the floor, inside the boxy OML)
    bms = box(-L / 2 + 5, -3, W / 2 + 4, W / 2 + 64, -5, H / 2 - 4)
    con = box(3, L / 2 - 5, W / 2 + 4, W / 2 + 64, -5, H / 2 - 4)
    parts.append(Part("BMS", "Orion BMS 2 (placeholder)", "Battery", "COTS", "purchased (BMS-ORION2)", bms, pl, "battery",
                      mass_kg=0.6, mass_source="estimate (catalog has no mass)", purchased=True))
    parts.append(Part("HV-SW", "Pack contactors (2 x EV200) and fuse (placeholder)", "Battery", "COTS", "purchased (HV-EV200, HV-FUSE)",
                      con, pl, "battery", mass_kg=2 * 0.43 + 0.25, mass_source="estimate (catalog has no mass)", purchased=True))
    # mounts (angle brackets at the free box ends) and vent
    ang = box(-4, 0, -40, 40, 0, 100) + box(-64, -4, -40, 40, 96, 100)
    mp = []
    xs = sorted(BATS, key=lambda q: q["x"])
    for q, s in ((xs[0], -1), (xs[-1], 1)):
        for y in (-200, 200):
            x = mm(q["x"]) + s * L / 2
            mp.append((Pos(x, y, mm(q["z"]) + H / 2 - 100) * (Rot(0, 0, 180) if s > 0 else Rot()), False))
    parts.append(Part("BAT-MNT", "Battery end bracket (fore/aft restraint to the floor)", "Battery", "CNC", "al6061_t6_extr", ang, mp,
                      "battery", density=rho("al6061_t6_extr"), machine="cnc_metal",
                      notes="6061 angle 100 x 60 x 4, 80 mm wide; the inner pack ends bolt to the under-floor bulkheads BH-2/BH-2B through inserts."))
    vent = tube_between((0, 0, 0), (0, 0, -150), 22, 20) + tube_between((0, 0, 0), (-60, 0, 0), 22, 20)
    parts.append(Part("BAT-VENT", "Battery vent duct (to the belly)", "Battery", "COTS-cut", "al6061_t6_extr", vent,
                      [(p[0] * Pos(L / 2 - 80, W / 2 - 60, -H / 2), False) for p in pl], "battery", density=rho("al6061_t6_extr"),
                      purchased=True, notes="44 mm aluminium tube with burst disc at the box; exits through the belly panel."))
    return parts


def pusher_parts() -> list[Part]:
    """Twin boom-tail pushers (design/geometry.json pushers[]): boom-end plug with motor plate, REB motor, propeller
    (counter-rotating pair), spinner, inverter in an under-boom pod. Modelled on the right unit; the left one is the
    mirror placement except the propellers, which are separate CW/CCW parts."""
    PUS = G.get("pushers") or [dict(G["pusher"], motor={"x_face": G["pusher"]["x"] - 0.21, "length": 0.15,
                                                        "id": "MOT-REB90", "diameter": 0.2702},
                                    mount={"x_from": G["pusher"]["x"] - 0.36, "x_to": G["pusher"]["x"] - 0.15})]
    from .booms import R_BASE_I, R_WRAP, CW, NAC_T
    parts = []
    u = max(PUS, key=lambda p: p["y"])
    xp, yp, zp = mm(u["x"]), mm(u["y"]), mm(u["z"])
    D, sd = mm(u["diameter"]), mm(u.get("spinner_diameter", 0.28))
    mo, mt = u["motor"], u["mount"]
    x_face, x0, x1 = mm(mo["x_face"]), mm(mt["x_from"]), mm(mt["x_to"])
    m_len, m_d = mm(mo["length"]), mm(mo["diameter"])
    LRp = [IDENT, place(mirror=True)]
    # boom-end plug + motor plate (one 6061 part)
    plug = cyl_x(R_BASE_I - 0.2, x0, x_face, yp, zp) - cyl_x(R_BASE_I - 8.2, x0 - 1, x_face - 12, yp, zp)
    boss = cyl_x(R_WRAP + 6, x_face, x1 - 15, yp, zp) - cyl_x(R_WRAP - 6, x_face - 1, x1 - 20, yp, zp)
    plate = cyl_x(m_d / 2 + 5, x1 - 15, x1, yp, zp) - cyl_x(25, x1 - 16, x1 + 1, yp, zp)
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        plate = plate - cyl_x(4.2, x1 - 16, x1 + 1, yp + 90 * math.cos(a), zp + 90 * math.sin(a))
    for k in range(6):
        a = math.radians(60 * k)
        plate = plate - cyl_x(18, x1 - 16, x1 + 1, yp + 118 * math.cos(a), zp + 118 * math.sin(a))
    fit = plug + boss + plate
    for k in range(4):
        fit = fit - cyl(4.1, (x0 + 40 + 30 * k, yp, zp - R_BASE_I - 30), (0, 0, 1), 2 * R_BASE_I + 60)
    parts.append(Part("PB-PLUG", "Pusher boom-end fitting (plug + motor plate)", "Pusher", "CNC", "al6061_t6_extr", fit, LRp,
                      "pusher_motor", density=rho("al6061_t6_extr"), machine="cnc_metal",
                      joints="210 mm long, more than the 150 mm mill Z: turned/milled in two set-ups (plug end, then plate end)",
                      notes=f"Machined 6061-T6: plug bonded {x_face - x0:.0f} mm into the boom end (EA 9394, 4 x AN5 cross-bolts), "
                            "boss and motor plate with the 8-bolt motor pattern and lightening windows; reacts thrust, motor torque "
                            "and the propeller gyroscopic moment into the boom."))
    mid = mo.get("id", "MOT-REB60")
    mot = cyl_x(m_d / 2, x1, x1 + m_len, yp, zp)
    parts.append(Part("MOT-PB", f"Pusher motor {mid.replace('MOT-', '')} (placeholder)", "Pusher", "COTS", f"purchased ({mid})", mot, LRp,
                      "pusher_motor", mass_kg=CAT[mid]["mass_kg"], mass_source=f"bom/catalog.json {mid}", purchased=True,
                      notes=f"Diameter {m_d:.0f} mm, length {m_len:.0f} mm from design/geometry.json; "
                            + ("same motor type as the lift units." if mid in S["lift_rotors"]["motor"]["name"] else
                               f"{mid.replace('MOT-', '')} pusher motor (the lift units use {S['lift_rotors']['motor']['name'].split(':')[0].replace('MOT-', '')}).")))
    nb = u["blades"]
    ch = mm(S["pusher"].get("blade_chord_m", 0.12))
    sec = naca4("0012", ch, 30)
    sec = np.column_stack([sec[:, 0] - 0.3 * ch, sec[:, 1]])
    m_prop = S["mass_kg"]["breakdown"]["pusher_propeller"] / len(PUS)
    spins = sorted({q.get("spin", 1) for q in PUS})
    pitch = u.get("blade_pitch_075R_deg", u.get("blade_pitch_deg", 25.0))
    for spin, nm in ((1, "CCW"), (-1, "CW")):
        if len(spins) == 1:                               # co-rotating units: one propeller part for both
            if spin != spins[0]:
                continue
            nm = "CW"
        blades = []
        for k in range(nb):
            bl = prism_y(sec, max(sd / 2 - 20, m_d / 2 + 8), D / 2)
            bl = bl.moved(Rot(0, spin * (90 - pitch), 0)).moved(Rot(360 * k / nb + 90, 0, 0))
            blades.append(bl.moved(Pos(xp, 0, zp)))
        hub = cyl_x(100, xp, xp + 100, 0, zp)            # hub flange on the motor face (prop plane at the motor end)
        sel = [place(0, mm(q["y"]), 0) for q in PUS if q.get("spin", 1) == spin]
        if not sel:
            continue
        parts.append(Part(f"PROP-P{nm}", f"Pusher propeller {nm}, {nb} blades, D {D:.0f} mm (placeholder)", "Pusher", "COTS",
                          f"purchased ({u.get('propeller', 'PROP-EPROPS-UAV-ADJ')})", compound([hub] + blades), sel, "pusher_propeller",
                          mass_kg=m_prop, mass_source="selected_design pusher_propeller / units", purchased=True,
                          notes=f"Shown stopped (blades vertical); ground-adjustable pitch set to {pitch:.0f} deg; "
                                + ("both units turn the same way (one part)." if len(spins) == 1 else "the two units counter-rotate.")))
    x_sp = mm(u.get("spinner", {}).get("x_to", u["x"] + 0.2))
    sp_o = loft3d([np.column_stack([np.full(48, xp + 0.5), circle(sd / 2, yp, zp, 48)]),
                   np.column_stack([np.full(48, xp + 0.4 * (x_sp - xp)), circle(sd / 2 * 0.8, yp, zp, 48)]),
                   np.column_stack([np.full(48, x_sp), circle(5, yp, zp, 48)])])
    sp_i = loft3d([np.column_stack([np.full(48, xp - 0.5), circle(sd / 2 - 1.5, yp, zp, 48)]),
                   np.column_stack([np.full(48, xp + 0.4 * (x_sp - xp) - 1), circle(sd / 2 * 0.8 - 1.5, yp, zp, 48)]),
                   np.column_stack([np.full(48, x_sp - 5), circle(2, yp, zp, 48)])])
    parts.append(Part("SPIN-P", "Pusher spinner", "Pusher", "composite-layup", "eglass_fabric_wet", sp_o - sp_i, LRp,
                      "pusher_propeller", density=rho("eglass_fabric_wet"), skin=True,
                      notes="Glass in an FDM-printed female mould (split for the printer), blade cut-outs trimmed to the hub."))
    # pusher inverters in the same under-boom pod as the lift stations
    from .booms import station_inverter
    inv, pod = station_inverter()
    ip = [place(mm(q["inverter"]["pod_x"]) if q.get("inverter") else xp - 600, mm(q["y"]), BOOM_Z) for q in PUS]
    parts.append(Part("INV-PB", "Pusher inverter MGM HBCi 400800 (placeholder)", "Pusher", "COTS", "purchased (INV-HBCI400800)",
                      inv, ip, "inverters", mass_kg=CAT["INV-HBCI400800"]["mass_kg"], mass_source="bom/catalog.json INV-HBCI400800",
                      purchased=True, notes="Same pod installation as the lift inverters, ahead of the boom end."))
    parts.append(Part("INV-POD-P", "Pusher inverter pod fairing", "Pusher", "composite-layup", "eglass_fabric_wet", pod, ip,
                      "pusher_motor", density=rho("eglass_fabric_wet"), skin=True,
                      notes="Same moulds as INV-POD."))
    return parts


def _chute_kg():
    if CHUTE["model"] in CAT and CAT[CHUTE["model"]].get("mass_kg"):
        return CAT[CHUTE["model"]]["mass_kg"]
    import json as _j
    from .config import ROOT as _R
    cal = _j.loads((_R / "design" / "mass_calibration.json").read_text())
    return CHUTE["kg"] - cal["fixed_kg"]["parachute_installation"]


def _chute_src():
    if CHUTE["model"] in CAT and CAT[CHUTE["model"]].get("mass_kg"):
        return f"bom/catalog.json {CHUTE['model']} (the design item adds cradle and hard points)"
    return "design parachute mass minus the parachute installation of design/mass_calibration.json (model not in the catalog)"


def chute_parts() -> list[Part]:
    parts = []
    c = CHUTE["canister"]
    d = np.array(c["fire_direction"], float)
    d /= np.linalg.norm(d)
    ctr = np.array([mm(c["x"]), mm(c["y"]), mm(c["z"])])
    Lc, Dc = mm(c["length"]), mm(c["diameter"])
    p0 = ctr - d * Lc / 2
    can = cyl(Dc / 2, p0, d, Lc)
    parts.append(Part("CHUTE", f"Ballistic parachute {CHUTE['model']} canister (placeholder)", "Systems", "COTS",
                      f"purchased ({CHUTE['model']})", can, [IDENT], "parachute", mass_kg=_chute_kg(),
                      mass_source=_chute_src(), purchased=True,
                      notes="Rocket-extracted canopy; axis along the design fire direction; risers stowed in a tear-strip channel."))
    BEAM_T = 9.0                                           # WP F phase 3.2: beam 100 x 9 mm
    Z_REQ = 1687.0                                         # WP F phase 3.2: post section modulus >= 1,687 mm3
    POST_A = 24.0
    while POST_A ** 3 / 6 < Z_REQ:
        POST_A += 1.0
    Z_POST = POST_A ** 3 / 6

    def cradle(rt, bw, holes):
        ring = cyl(Dc / 2 + rt, p0 - d * 60, d, 130) - cyl(Dc / 2 + 0.5, p0 - d * 100, d, 300)
        beam_z = p0[2] - 60
        beam = box(BH_X["BH-4"] + PT / 2, BH_X["BH-5"] - PT / 2, -bw / 2, bw / 2, beam_z - BEAM_T, beam_z)
        FL_D, FL_T = 40.0, 8.0                            # WP F phase 3.3B: two 40 x 8 mm down-standing flanges
        for sy in (-1, 1):
            beam = beam + box(BH_X["BH-4"] + PT / 2, BH_X["BH-5"] - PT / 2, sy * bw / 2 - (FL_T if sy > 0 else 0),
                              sy * bw / 2 + (0 if sy > 0 else FL_T), beam_z - BEAM_T - FL_D, beam_z - BEAM_T)
        if holes:
            for xh in np.arange(BH_X["BH-4"] + 60, BH_X["BH-5"] - 40, 70):
                if min(abs(xh - (p0[0] + s * 120)) for s in (-1, 1)) < 70:    # solid beam under/around the posts (WP F 3.1)
                    continue
                beam = beam - cyl_z(bw / 2 - 12, beam_z - 9, beam_z + 1, xh, 0)
        bore = cyl(Dc / 2 + 0.5, p0 - d * 300, d, 1200)
        above = cyl(Dc, p0 + d * 70, d, 800)
        posts = [box(p0[0] + s * 120 - POST_A / 2, p0[0] + s * 120 + POST_A / 2, -POST_A / 2, POST_A / 2, beam_z, p0[2] + 200)
                 - bore - above for s in (-1, 1)]                  # posts run up into the clamp ring: one fused body
        return fuse_all([ring, beam] + posts)
    full = cradle(12, 120, False).volume
    cr = cradle(8, 100, True)
    # WP F phase 3.3C: forward post 28 x 56 mm (part frame x 112-140, y 140-196) from the beam web into the front of the ring
    bb0 = cr.bounding_box()
    beam_z = p0[2] - 60
    fp = box(bb0.min.X + 112, bb0.min.X + 140, bb0.min.Y + 140, bb0.min.Y + 196, bb0.min.Z + 49.0, bb0.min.Z + 114.0)
    fp = fp - cyl(Dc / 2 + 0.5, p0 - d * 60, d, 1000) - cyl(Dc, p0 + d * 70, d, 800)   # flush with the ring bore only
    cr = fuse_all([cr, fp])
    _h = cr.bounding_box().size.Z
    CR_JOINT = (f"one fused body; {_h:.0f} mm tall: " + ("within the 150 mm mill Z, one block, two set-ups (top and bottom)"
                if _h <= 150 else "more than the 150 mm mill Z: machined from one block in two set-ups (flip on dowels)"))
    CR_FRAC = 1 - cr.volume / full
    parts.append(Part("CH-CRADLE", "Parachute canister cradle", "Systems", "CNC", "al6061_t6_extr", cr, [IDENT], "parachute",
                      density=rho("al6061_t6_extr"), machine="cnc_metal", settings={"_reduction": CR_FRAC, "post_section": f"{POST_A:.0f} x {POST_A:.0f} mm solid", "post_Z_mm3": round(Z_POST)},
                      notes=f"Machined clamp ring fused to two posts and a {BEAM_T:.0f} x 100 mm beam with two 40 x 8 mm flanges (lightening holes only away from the posts) bolted between BH-4 and BH-5 (angle tabs, "
                            f"inserts) and a 28 x 56 mm forward post into the front of the ring (WP F phase 3.3C); {100*CR_FRAC:.0f} % lighter than the iteration-1 cradle. Posts {POST_A:.0f} x {POST_A:.0f} mm "
                            f"solid 6061: section modulus Z = {Z_POST:.0f} mm3 about either axis (required >= {Z_REQ:.0f} mm3).",
                      joints=CR_JOINT))
    ra = [a for a in CHUTE["attach"] if a["name"] == "chute_rear"][0]
    P5 = FEA_FIT["P5_parachute_hardpoint"]
    from .geom import p5_hardpoint, p5_angle
    face = BH_X["BH-6"] + PT / 2
    xr = face + 6 + P5["plate_w"] / 2
    zr = mm(ra["z"]) - P5["eye_zc"]
    fit = p5_hardpoint(P5).moved(Pos(xr, 0, zr))
    ang = p5_angle(P5, face - xr).moved(Pos(xr, 0, zr))
    parts.append(Part("CH-ATT-R", "Parachute rear riser hard point (FEA part P5)", "Systems", "CNC", P5["material"], fit, [IDENT],
                      "parachute", density=rho(P5["material"]), machine="cnc_metal",
                      notes="WP F P5 geometry, 4130 N; plate in the x-z plane (riser pull in the lug plane), eye at the design "
                            "attach height; bolted to CH-ANG-R."))
    parts.append(Part("CH-ANG-R", "Parachute rear hard-point angle (to BH-6)", "Systems", "CNC", "al6061_t6_extr", ang, [IDENT],
                      "parachute", density=rho("al6061_t6_extr"), machine="cnc_metal",
                      notes="6 mm 6061 angle bolted through BH-6 with a doubler on the forward face."))
    xr_eye, zr_eye = xr, mm(ra["z"])
    top = ctr + d * Lc / 2
    ris = []
    from .wing import FOIL, C
    from . import wing as W_
    xs = WING["spars"][0]["x_c"] * C
    from .geom import thickness_at
    hi = thickness_at(FOIL, xs)[1]
    for a in CHUTE["attach"]:
        if a["name"].startswith("chute_front"):
            P5f = FEA_FIT["P5_parachute_hardpoint"]
            st0 = W_._stations("main")
            xc = xs + st0[0][1]["b_cap"] * 1000 / 2 + 2 + P5f["plate_w"] / 2
            p = wing_to_global(xc, thickness_at(FOIL, xc)[1] + 25, mm(a["y"]))
        else:
            p = np.array([xr_eye, 0, zr_eye])
        ris.append(tube_between(top, p, 6))
    parts.append(Part("CH-RISER", "Parachute risers (3, simplified)", "Systems", "COTS", "nylon_strap", compound(ris), [IDENT],
                      "parachute", mass_kg=0.0, mass_source="included in the parachute mass", purchased=True,
                      notes="Kevlar/nylon risers from the canister bridle to the three hard points; routed under tear strips."))
    return parts


def _srp(seat):
    return np.array([mm(seat["x"]) + DETAIL["seat_srp_back"], 0.0, mm(seat["seat_reference_point_z"])])


def cabin_parts() -> list[Part]:
    parts = []
    from shapely.geometry import LineString
    rec = math.radians(15)
    back = 800.0
    pan = 450.0
    # seat shell in SRP-relative coordinates (x, z)
    line = LineString([(-pan, 45), (0, 0), (back * math.sin(rec), back * math.cos(rec))])
    shell2d = np.array(line.buffer(2.0, cap_style=2, join_style=2).exterior.coords)[:-1]
    shell2d[:, 1] -= 2.0
    seat = prism_y(shell2d, -230, 230)
    for y in (-232, 228):      # side bolsters
        seat = seat + prism_y(np.array([[-pan, 40], [0, -4], [150 * math.sin(rec), 150], [-pan, 140]]), y, y + 4)
    spl = [place(*_srp(s)) for s in SEATS]
    parts.append(Part("SEAT-SHELL", "Seat shell (pan, back, side bolsters)", "Cabin", "composite-layup", "cf_fabric_wet", seat, spl,
                      "seats", density=rho("cf_fabric_wet"),
                      notes="4 mm carbon (6 plies twill) wet-laid over the CNC foam plug T-SEAT-PLUG; hard points for the "
                            "harness anchors and seat brackets potted in."))
    cush = np.array(LineString([(-pan + 10, 47), (2, 2), (back * math.sin(rec) - 5, back * math.cos(rec))]).buffer(20, cap_style=2).exterior.coords)[:-1]
    from .geom import offset2d
    from shapely.geometry import Polygon
    behind = Polygon([(-pan - 50, 45), (0, 0), (back * math.sin(rec), back * math.cos(rec)), (2000, back * math.cos(rec)),
                      (2000, -2000), (-pan - 50, -2000)])
    cpoly = Polygon(cush).difference(Polygon(shell2d).buffer(0.5)).difference(behind.buffer(2.0))
    cpoly = cpoly if cpoly.geom_type == "Polygon" else max(cpoly.geoms, key=lambda g: g.area)
    cus = prism_y(np.array(cpoly.exterior.coords)[:-1], -200, 200)
    parts.append(Part("SEAT-CUSH", "Seat cushions (CONFOR CF-45)", "Cabin", "COTS-cut", "confor_cf45", cus, spl, "seats",
                      density=rho("confor_cf45"), purchased=True, notes="Layered CONFOR CF-45/CF-47 cut to template, fabric covered."))
    rail_top = FLOOR_Z + PT + 25.0
    srp_z = _srp(SEATS[0])[2]
    ea = box(-pan + 30, -30, -160, 160, rail_top - srp_z, -4)
    parts.append(Part("SEAT-EA", "Seat energy-absorbing stroke block", "Cabin", "CNC", "pvc_h100", ea, spl, "seats",
                      density=rho("pvc_h100"), machine="cnc",
                      notes=f"Crushable Divinycell H100 block under the pan ({srp_z - 4 - rail_top:.0f} mm stroke) with "
                            "glass tear-strips; WP F to size crush stress for 3 g landing (elastic) and the crash pulse. See "
                            "validation/cad for the available stroke."))
    P6 = FEA_FIT["P6_seat_fitting"]
    bx_, by_, bz_ = P6["base"]
    wx, wy, wz = P6["web"]
    brk = box(-bx_ / 2, bx_ / 2, -by_ / 2, by_ / 2, 0, bz_) + box(-wx / 2, wx / 2, -wy / 2, wy / 2, 5, 5 + wz)
    brk = brk + cyl_y(P6["eye_r"], -wy / 2, wy / 2, 0, P6["eye_z"])
    brk = brk - cyl_y(P6["pin_d"] / 2, -wy, wy, 0, P6["eye_z"] - 1)
    for x, y in P6["bolts"]:
        brk = brk - cyl_z(P6["bolt_d"] / 2, -1, bz_ + 1, x, y)
    bpl = []
    for p in spl:
        for x in (-pan + 50, -50):
            bpl += [(p[0] * Pos(x, 195, rail_top - srp_z), False), (p[0] * Pos(x, -195, rail_top - srp_z), False)]
    parts.append(Part("SEAT-FIT", "Seat leg fitting (FEA part P6)", "Cabin", "CNC", P6["material"], brk, bpl, "seats",
                      density=rho(P6["material"]), machine="cnc_metal",
                      notes="WP F P6 geometry (7075-T6, 14 mm lug, 9.5 mm pin, 2 x AN5 into the seat-track studs); the seat "
                            "pan lugs pin to the eye; sized for max(9 g x 1.33, 26 g dynamic) forward."))
    rail = box(-pan - 50, 100, -12, 12, rail_top - srp_z - 25, rail_top - srp_z) - box(-pan - 51, 101, -4, 4, rail_top - srp_z - 12, rail_top - srp_z + 1)
    rpl = []
    for p in spl:
        for y in (195, -195):
            rpl.append((p[0] * Pos(0, y, 0), False))
    parts.append(Part("SR", "Seat rail (aluminium seat track)", "Cabin", "COTS-cut", "al6061_t6_extr", rail, rpl, "seats",
                      density=rho("al6061_t6_extr"), purchased=True,
                      notes="Aircraft seat-track extrusion cut to length, bolted through the floor into BH-backed inserts; "
                            "cargo tie-downs use the same rails when seat 2 is removed."))
    # harness anchors (lap x2 to the rails, shoulder x2 at the seat back top)
    ha = box(-20, 20, -6, 6, 0, 40) - cyl_y(5, -10, 10, 0, 25)
    hpl = []
    for p in spl:
        hpl += [(p[0] * Pos(-160, 215, rail_top - srp_z), False), (p[0] * Pos(-160, -215, rail_top - srp_z), False),
                (p[0] * Pos(back * math.sin(rec) + 10, 90, back * math.cos(rec) - 40), False),
                (p[0] * Pos(back * math.sin(rec) + 10, -90, back * math.cos(rec) - 40), False)]
    parts.append(Part("HA-FIT", "Harness anchor fitting", "Cabin", "CNC", "al6061_t6_extr", ha, hpl, "seats",
                      density=rho("al6061_t6_extr"), machine="cnc_metal", notes="6061 eye fitting, AN5 bolt, 4 per seat."))
    harn = compound([box(-60, 0, -200, 200, 60, 110)] +
                    [tube_between((back * math.sin(rec) - 60, y, back * math.cos(rec) - 60), (-120, y * 0.2, 100), 4)
                     for y in (-90, 90)])
    parts.append(Part("HARN", "4-point harness (Hooker, COTS)", "Cabin", "COTS", "purchased (CAB-HARNESS)", harn, spl, "seats",
                      mass_kg=1.0, mass_source="estimate", purchased=True))
    # occupants: simplified 95th percentile seated male, origin at the design occupant CG
    for s in SEATS:
        pass
    srp_rel = np.array([DETAIL["seat_srp_back"], 0.0, mm(SEATS[0]["seat_reference_point_z"]) - mm(SEATS[0]["z"])])
    sh = DETAIL["sitting_height_p95"]
    ub = np.array([math.sin(rec), 0, math.cos(rec)])
    fn = np.array([-math.cos(rec), 0, math.sin(rec)])
    head_c = srp_rel + ub * (sh - 110) + fn * 110
    torso = box(0, 260, -200, 200, 120, 640).moved(Rot(0, -15, 0)).moved(Pos(*srp_rel))
    # torso box is in (normal-forward, width, along-back) -> build directly
    tz = []
    for a, n_ in ((100, 20), (100, 250), (640, 250), (640, 20)):
        tz.append(srp_rel + ub * a + fn * n_)
    tz = np.array(tz)
    torso = prism_y(tz[:, [0, 2]], -200, 200)
    thigh = box(srp_rel[0] - 600, srp_rel[0] - 20, -190, 190, srp_rel[2] + 10, srp_rel[2] + 160)
    shin = box(srp_rel[0] - 650, srp_rel[0] - 540, -170, 170, FLOOR_Z + PT + 10 - mm(SEATS[0]["z"]), srp_rel[2] + 80)
    feet = box(srp_rel[0] - 760, srp_rel[0] - 560, -170, 170, FLOOR_Z + PT + 5 - mm(SEATS[0]["z"]), FLOOR_Z + PT + 90 - mm(SEATS[0]["z"]))
    head = sphere(110, head_c)
    neck = cyl(55, srp_rel + ub * 620 + fn * 110, ub, 160)
    occ = compound([torso, thigh, shin, feet, head, neck])
    parts.append(Part("OCC", "Occupant (95th percentile seated male envelope, 100 kg)", "Cabin", "COTS", "payload", occ,
                      [place(mm(s["x"]), mm(s["y"]), mm(s["z"])) for s in SEATS], "payload", mass_kg=SEATS[0]["occupant_kg"],
                      mass_source="design/geometry.json seats.occupant_kg, CG at the design occupant point", purchased=True,
                      notes=f"Clearance envelope only: sitting height {sh:.0f} mm, seat back 15 deg; mass applied at the design CG."))
    # instrument panel and avionics
    xi = BH_X["BH-1"] + 50
    ip = box(xi, xi + 3, -300, 300, 950, 1250)
    from shapely.geometry import Polygon as P2
    yh = oml_half_width(xi, 1100) - 20
    ip = ip & box(xi - 1, xi + 4, -yh, yh, 900, 1300)
    ip = ip - box(xi - 1, xi + 5, -190, 10, 1030, 1170) - box(xi - 1, xi + 5, 60, 150, 1060, 1150) - box(xi - 1, xi + 5, 180, 240, 1000, 1200)
    parts.append(Part("IP", "Instrument panel", "Cabin", "outsourced-waterjet", "al6061_t6_sheet", ip, [IDENT], "avionics",
                      density=rho("al6061_t6_sheet"), notes="3 mm 6061 waterjet-cut with EFIS, standby and radio cut-outs; "
                                                             "rubber-isolated to the BH-1 glare-shield brackets."))
    av_tot = S["mass_kg"]["breakdown"]["avionics"]
    av = [("AV-EFIS", "EFIS Dynon SkyView HDX 7 (placeholder)", box(xi + 3, xi + 93, -190, 10, 1030, 1170), 2.0),
          ("AV-G5", "Standby instrument Garmin G5 (placeholder)", box(xi + 3, xi + 103, 60, 150, 1060, 1150), 0.6),
          ("AV-RADIO", "COM radio + transponder (Trig TY91 / TT21) (placeholder)", box(xi + 3, xi + 163, 180, 240, 1000, 1200), 1.2),
          ("AV-FCC", "Flight control computer Veronte 4x (placeholder)", box(BH_X["BH-0"] + 20, BH_X["BH-0"] + 140, -100, 100, 930, 990), CAT["FCC-VERONTE4X"]["mass_kg"]),
          ("AV-GNSS", "GNSS receivers Here4 x 2 (placeholder)", compound([cyl_z(40, 0, 25, 0, y) for y in (-120, 120)]).moved(Pos((BH_X["BH-0"] + BH_X["BH-1"]) / 2, 0, 0)), 0.4)]
    rest = av_tot - sum(a[3] for a in av)
    av.append(("AV-MISC", "Avionics bay: ADAHRS, air-data, intercom, LV harness (lumped)", box(BH_X["BH-0"] + 150, BH_X["BH-1"] - 15, -150, 150, 930, 1050), rest))
    for pid, nm, sol, m in av:
        pl = [IDENT]
        if pid == "AV-GNSS":
            _, h0, z0 = oml((BH_X["BH-0"] + BH_X["BH-1"]) / 2)
            pl = [place(0, 0, z0 + h0 / 2 - 100)]
        parts.append(Part(pid, nm, "Avionics", "COTS", "purchased", sol, pl, "avionics", mass_kg=m,
                          mass_source="catalog / estimate, remainder of the avionics budget" if pid == "AV-MISC" else "catalog or estimate",
                          purchased=True))
    tray_w = oml_half_width((BH_X["BH-0"] + BH_X["BH-1"]) / 2, 920) - 10
    tray = box(BH_X["BH-0"] + PT / 2, BH_X["BH-1"] - PT / 2, -tray_w, tray_w, 918, 930)
    from .fuselage import oml_solid as _os
    tray = tray & _os(4.0, BH_X["BH-0"], BH_X["BH-1"])
    parts.append(Part("AV-TRAY", "Avionics bay shelf", "Avionics", "CNC", PANEL["label"], tray, [IDENT], "avionics",
                      density=PANEL["rho"], machine="cnc", notes="Sandwich shelf between BH-0 and BH-1 on angle tabs; access through HATCH-AV."))
    # crash zone in the nose under the avionics bay
    nz = []
    from shapely.geometry import box as sbox
    from .config import oml_section_xz
    sec = oml_section_xz(0.0, BH_X["BH-0"] + PT / 2, BH_X["BH-1"] - PT / 2, inset=2.0)
    pg = P2(sec).intersection(sbox(BH_X["BH-0"] + PT / 2, -1000, BH_X["BH-1"] - PT / 2, FLOOR_Z - 5))
    from .fuselage import oml_solid
    ez = prism_y(np.array(pg.exterior.coords)[:-1], -150, 150) & oml_solid(10.0, BH_X["BH-0"], BH_X["BH-1"])
    parts.append(Part("NOSE-EA", "Nose crush block (energy absorber)", "Cabin structure", "CNC", "pvc_h80", ez, [IDENT], "fuselage",
                      density=rho("pvc_h80"), machine="cnc",
                      notes="Stacked H80 slabs bonded, CNC-trimmed to the nose OML, glass-wrapped; crushes against BH-1 "
                            "in a forward impact before the footwell is loaded.",
                      joints="10 stacked 44 mm H80 slabs bonded, then CNC-trimmed in two set-ups"))
    # LV electrical (under the floor between BH-1 and battery A)
    lv_tot = S["mass_kg"]["breakdown"]["lv_electrical"]
    lv = [("LV-BATT", "24 V LiFePO4 backup battery (placeholder)", box(BH_X["BH-1"] + 20, min(BH_X["BH-1"] + 200, mm(min(BATS, key=lambda q: q["x"])["x"]) - mm(BATS[0]["length"]) / 2 - 70), -230, -40, FLOOR_Z - 125, FLOOR_Z - 5), 4.0),
          ("LV-DCDC", "HV-to-28 V DC-DC converters x 2 (placeholder)", box(BH_X["BH-1"] + 20, min(BH_X["BH-1"] + 200, mm(min(BATS, key=lambda q: q["x"])["x"]) - mm(BATS[0]["length"]) / 2 - 70), 40, 230, FLOOR_Z - 125, FLOOR_Z - 5), 3.0),
          ("LV-PANEL", "LV fuse / relay panel and harness (lumped)", box(xi + 3, xi + 60, -300, -200, 950, 1200), lv_tot - 7.0)]
    for pid, nm, sol, m in lv:
        parts.append(Part(pid, nm, "Avionics", "COTS", "purchased", sol, [IDENT], "lv_electrical", mass_kg=m,
                          mass_source="estimate within the lv_electrical budget", purchased=True))
    # inceptors
    p1 = _srp(SEATS[0])
    stick = compound([box(-40, 40, -28, 28, 0, 120), cyl_z(12, 120, 330)])
    parts.append(Part("FC-STICK", "Pilot inceptors: side-stick (right) and lift/thrust lever (left)", "Cabin", "COTS", "purchased",
                      stick, [place(p1[0] - 300, 285, FLOOR_Z + PT + 250), place(p1[0] - 300, -285, FLOOR_Z + PT + 250)],
                      "flight_controls", mass_kg=mass_item("flight controls: inceptors", 3.0) / 2,
                      mass_source="design mass item 'inceptors' / 2", purchased=True,
                      notes="Triplex-sensor inceptors on the side consoles, wired to the FCC."))
    fcrest = mass_item("flight controls: misc", 1.6)
    parts.append(Part("FC-MISC", "Flight-control wiring, trim and mode panel (lumped)", "Cabin", "COTS", "purchased",
                      box(BH_X["BH-0"] + 150, BH_X["BH-1"] - 15, -150, 150, 1052, 1090), [IDENT],
                      "flight_controls", mass_kg=max(fcrest, 0.0), mass_source="design mass item 'flight controls: misc'", purchased=True))
    # furnishings (trim, floor mat, placards) lumped at the design point
    fu = [m for m in G["masses"] if m["name"] == "furnishings"][0]
    parts.append(Part("FURN", "Cabin trim, floor mat, placards (lumped)", "Cabin", "COTS", "purchased",
                      box(-200, 200, -150, 150, 0, 6), [place(mm(fu["x"]), 0, FLOOR_Z + PT + 1.5)], "seats", mass_kg=fu["kg"],
                      mass_source="design furnishings mass item", purchased=True))
    return parts


def harness_parts() -> list[Part]:
    """HV harness runs (simplified conduits); masses share the hv_harness budget by length (set in build)."""
    parts = []
    from .wing import FOIL, C
    from .geom import thickness_at
    xs = WING["spars"][1]["x_c"] * C + 30
    lo, hi = thickness_at(FOIL, xs)
    w = cyl_y(14, -BOOM_Y, BOOM_Y, xs, (lo + hi) / 2)
    parts.append(Part("HV-WING", "HV harness run in the wing (behind the rear spar)", "Systems", "COTS", "purchased", w, [(WLOC, False)],
                      "hv_harness", purchased=True, mass_kg=mass_item("HV harness in the wing"),
                      mass_source="design mass item 'HV harness in the wing' (aluminium conductors)",
                      notes="Aluminium-conductor cables in a split loom clipped to the rear-spar web; drop to each boom in the boom rib bay."))
    bB = max(BATS, key=lambda b: b["x"])
    xr = mm(bB["x"]) + mm(bB["length"]) / 2 + 30
    from .fuselage import X_POST_R, POST_W
    xs_r = WING["spars"][1]["x_c"] * C
    z_wl = wing_to_global(xs_r, thickness_at(FOIL, xs_r)[0])[2] - 10
    pts = [(xr, Y_SIDE - 30, FLOOR_Z - 20), (X_POST_R + POST_W / 2, Y_SIDE - 30, FLOOR_Z + 40), (X_POST_R + POST_W / 2, Y_SIDE - 30, z_wl)]
    r = compound([tube_between(a, b, 12) for a, b in zip(pts[:-1], pts[1:])])
    parts.append(Part("HV-RISER", "HV riser, battery bay to wing root (one per pack bus)", "Systems", "COTS", "purchased", r,
                      [IDENT, place(mirror=True)], "hv_harness", purchased=True, mass_source="share of the hv_harness budget by length",
                      notes="Aluminium-conductor HV cable in a fire-sleeved conduit up the rear wing post."))
    if not G.get("pushers"):
        x7 = BH_X["BH-7"]
        pts = [(xr, -150, FLOOR_Z - 20), (BH_X["BH-3"] + 30, -150, 850), ((BH_X["BH-5"] + BH_X["BH-6"]) / 2, -60, 850)]
        p = compound([tube_between(a, b, 12) for a, b in zip(pts[:-1], pts[1:])])
        parts.append(Part("HV-PUSH", "HV run to the pusher inverter", "Systems", "COTS", "purchased", p, [IDENT], "hv_harness",
                          purchased=True, mass_source="share of the hv_harness budget by length"))
    return parts
