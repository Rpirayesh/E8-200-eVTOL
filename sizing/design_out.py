"""Detailed layout of one sized design and the interface files.

From the design variables x (sizing.optimise) this module
  * re-runs the closure (sizing.model) for the design,
  * places every mass item in aircraft axes (x aft from the fuselage nose, y right, z up from the skid bottom) and moves
    the fuselage relative to the wing/rotor group so that the MTOW CG lies on the rotor centroid,
  * evaluates three loading cases (pilot + passenger, pilot + cargo, pilot only): CG, static margin, all-rotor hover
    trim and the one-motor-out linear programme [H6] for every failed rotor at 1000 m ISA+15 with the control margin,
  * writes design/selected_design.json (methods/design_schema.md), design/geometry.json (fea/README.md, cfd/README.md and
    the checker keys) and design/geometry_cfd.json (the same geometry with the CFD tool's native key types).
"""
from __future__ import annotations

import json
import math

import numpy as np

from . import data as D
from . import physics as ph
from .airfoils import load as load_airfoils
from .model import A0, SEATING, evaluate, fuselage_stations, fuselage_wetted
from .rotor_out import best_spin_pattern, lp_max_thrust

G0 = ph.G0
R3 = lambda v: round(float(v), 3)  # noqa: E731
R4 = lambda v: round(float(v), 4)  # noqa: E731


def s(o, k):
    v = o[k]
    return float(np.asarray(v).ravel()[0])


def _section_top_for_halfwidth(hw_needed, w, e, z_fit, bot):
    """Smallest fuselage top so that the super-ellipse half-width at height z_fit is >= hw_needed."""
    a = w / 2
    if hw_needed >= a:
        return np.inf
    r = (1 - (hw_needed / a) ** e) ** (1 / e)      # |z - zc| / (h/2) allowed
    # zc = (top + bot)/2, h/2 = (top - bot)/2 ; need z_fit - zc <= r (top - bot)/2
    # z_fit - (top+bot)/2 <= r (top-bot)/2  ->  top (1 + r)/2 >= z_fit - bot/2 + r bot/2 ... solve linear
    return (2 * z_fit - bot * (1 - r)) / (1 + r)


def build(x: dict, cfg: dict) -> dict:
    """Layout of one design (iteration 2): CG solution, vertical stack from the cabin outward, OML stations, packs,
    gear, canister, tail, item placement with the CAD-calibrated group positions, loading cases."""
    from .calibration import load as load_cal
    from .geometry_checks import (BOOM_R_WRAP, FITTING_DROP, PAD_TOP, SILL_ABOVE_FLOOR, Wing, head_center)
    A = dict(A0, **cfg.get("assumptions", {}))
    CAL = load_cal()
    o = evaluate({k: np.atleast_1d(v) for k, v in x.items()}, cfg)
    mass = {k: float(np.asarray(v).ravel()[0]) for k, v in o["mass"].items()}
    n, coax = int(cfg["n_rot"]), bool(cfg.get("coax", False))
    seating = cfg.get("seating", "tandem")
    fus = dict(SEATING[seating])
    AF = load_airfoils()
    afname = list(AF)[int(x["airfoil"])]
    af = AF[afname]
    lmot = D.LIFT_MOTORS[int(x["lm"])]
    pmot = D.PUSHER_MOTORS[int(x["pm"])]
    cell = D.CELLS[int(x["cell"])]
    inv = D.INVERTERS[lmot["inverter"]]
    Dr, R, vtip, nb = float(x["D"]), float(x["D"]) / 2, float(x["vtip"]), int(x["nb"])
    span, chord, V, Dp = float(x["span"]), float(x["chord"]), float(x["V"]), float(x["Dp"])
    Rp = Dp / 2
    mtow = s(o, "mtow")
    b_y, x_le_l = s(o, "b_y"), s(o, "x_le")
    xr_l = np.asarray(o["xr"])[0]
    x_tle_l, c_h, span_h, S_h = s(o, "x_tle"), s(o, "c_h"), s(o, "span_h"), s(o, "S_h")
    S_v, c_v = s(o, "S_v"), s(o, "c_v")
    bx0_l, bx1_l = s(o, "boom_x0"), s(o, "boom_x1")
    sigma = s(o, "sigma")
    Lf, wf = fus["L"], fus["w"]
    e_f = A["fus_e"]
    inc_deg = A.get("wing_incidence_deg", 4.0)
    x_s1, x_s2 = fus["x_seat"]
    ys1, ys2 = fus["y_seat"]
    n_disk = n // 2 if coax else n

    # ---------------- battery packs: 2 tiers of cells standing in G10 holders, width fitted to the OML (nose frame)
    npk = int(x["npk"])
    cells_pack = int(round(s(o, "Ns") * s(o, "Np_pack")))
    pack_w, tiers = 0.62, 2
    across = int((pack_w - 2 * 0.0016 - 0.020) // 0.0224)
    rows = int(math.ceil(cells_pack / tiers / across))
    pack_len = rows * 0.0224 + 0.080
    pack_h = tiers * 0.0845 + 0.020
    pack_kg = s(o, "battery_kg") / npk
    x_pack0 = 0.95
    packs = [dict(name=f"battery_{chr(65 + i)}", x=x_pack0 + pack_len / 2 + i * (pack_len + 0.04), length=pack_len) for i in range(npk)]
    pack_end = packs[-1]["x"] + pack_len / 2

    # ---------------- items, x frames: 'L' relative to the CG target, 'F' from the fuselage nose; z set later
    items = []

    def add(name, kg, xx, yy, fr, attach, group, zkey, dz=0.0):
        items.append(dict(name=name, kg=float(kg), x=float(xx), y=float(yy), frame=fr, attach=attach, group=group, zkey=zkey, dz=dz))
    cg_off = CAL["cg_offsets_m"]
    st_hw = CAL["fixed_kg"]["rotor_station_hardware_each"]
    m_lprop = mass["lift_rotors"] / n
    unit_kg = lmot["mass_kg"] + m_lprop + inv["mass_kg"] + mass["rotor_pylons_mounts"] / n
    rotor_pos = []
    for side, yy in (("L", -b_y), ("R", b_y)):
        for j, xx in enumerate(xr_l):
            if coax:
                for lvl, dz in (("up", 0.20), ("lo", -0.15)):
                    rotor_pos.append((f"{side}{j + 1}{lvl}", xx, yy, dz))
            else:
                rotor_pos.append((f"{side}{j + 1}", xx, yy, 0.0))
    for name, xx, yy, dz in rotor_pos:
        add("rotor_" + name, unit_kg, xx, yy, "L", "boom_" + name[0], "rotor", "hub", dz - 0.20)   # CAD: station CG 0.20 m below the hub
    add("wing structure", mass["wing"], x_le_l + 0.425 * chord, 0.0, "L", "wing", "structure", "wing", -0.045)
    for side, yy in (("L", -b_y), ("R", b_y)):
        add(f"boom_{side}", mass["booms"] / 2, 0.5 * (bx0_l + bx1_l), yy, "L", f"boom_{side}", "structure", "boom")
    add("tail structure", mass["tail"], x_tle_l + 0.30 * c_h + 0.05, 0.0, "L", "tail", "structure", "boom", -0.11)
    add("fuselage structure", mass["fuselage"], 0.407 * Lf, 0.0, "F", "fuselage", "structure", "abs", 1.17)   # CAD it. 3
    twin = bool(pmot.get("twin", 0))
    x_push = Lf + 0.12
    if twin:      # two pushers on the boom tails (prop plane 0.15 m behind the boom end), inverter in the boom tail
        m_push = mass["pusher_motor"] + mass["pusher_propeller"] + 2 * inv["mass_kg"]
        x_pod_l = x_tle_l - A["pusher_pod_ahead_of_tail"]     # iteration 3.3: inverter pod ahead of the tail clamp / fin spar
        for side, yy in (("L", -b_y), ("R", b_y)):
            add(f"pusher unit {side} (motor, propeller, mount)", m_push / 2 - inv["mass_kg"], bx1_l + 0.05, yy, "L", f"boom_{side}",
                "pusher", "boom")
            add(f"pusher inverter pod {side}", inv["mass_kg"], x_pod_l, yy, "L", f"boom_{side}", "pusher", "boom", -0.10)
    else:
        m_push = mass["pusher_motor"] + mass["pusher_propeller"] + inv["mass_kg"]
        add("pusher unit", m_push, x_push - 0.25, 0.0, "F", "fuselage", "pusher", "pusher")
    seat_kg = (mass["seats"] - D.FURNISHING_KG) / 2
    add("seat_1 (pilot)", seat_kg, x_s1, ys1, "F", "fuselage", "seat", "srp", -0.05)
    add("seat_2 (passenger / removable)", seat_kg, x_s2, ys2, "F", "fuselage", "seat", "srp", -0.05)
    add("occupant_1 (pilot)", A["occupant_kg"], x_s1, ys1, "F", "fuselage", "payload", "srp", 0.28)
    add("occupant_2 (passenger)", A["occupant_kg"], x_s2, ys2, "F", "fuselage", "payload", "srp", 0.28)
    for p in packs:
        add(p["name"], pack_kg, p["x"], 0.0, "F", "fuselage", "battery", "pack")
    add("avionics (FCC, EFIS, radios)", mass["avionics"], 0.41, 0.0, "F", "fuselage", "systems", "abs", 1.04)   # CAD it. 3
    add("LV electrical", mass["lv_electrical"], 0.53, 0.0, "F", "fuselage", "systems", "abs", 0.73)
    fc = mass["flight_controls"] - (4.0 if int(x["flap"]) else 0.0)
    if int(x["flap"]):
        for side, yy in (("L", -1.0), ("R", 1.0)):
            add(f"flap actuators {side} (2)", 2.0, x_le_l + 0.72 * chord, yy, "L", "wing", "systems", "wing", -0.05)
    add("flight controls: inceptors", 3.0 / 9.0 * fc, x_s1 + 0.30, 0.0, "F", "fuselage", "systems", "srp", 0.10)
    add("flight controls: misc wiring/panel", 1.6 / 9.0 * fc, 1.60, 0.0, "F", "fuselage", "systems", "abs", 0.95)
    for side, yy in (("L", -0.66 * span / 2), ("R", 0.66 * span / 2)):
        add(f"aileron actuator {side}", 1.0 / 9.0 * fc, x_le_l + 0.72 * chord, yy, "L", "wing", "systems", "wing", -0.05)
    add("tail actuators", 2.4 / 9.0 * fc, x_tle_l + 0.6 * c_h, 0.0, "L", "tail", "systems", "boom")
    add("furnishings", D.FURNISHING_KG, 1.80, 0.0, "F", "fuselage", "systems", "floor", 0.05)
    add("parachute (canister, cradle, hard points)", mass["parachute"], 0.0, 0.0, "F*", "fuselage", "systems", "chute")
    hv = mass["hv_harness"]
    for side, yy in (("L", -b_y), ("R", b_y)):
        add(f"HV harness in boom_{side}", 0.357 * hv, 0.5 * (xr_l[0] + xr_l[-1]), yy, "L", f"boom_{side}", "systems", "boom")
    add("HV harness in the wing", 0.156 * hv, x_le_l + 0.80 * chord, 0.0, "L", "wing", "systems", "wing")
    add("HV risers and pusher run", 0.130 * hv, 0.0, 0.0, "F#", "fuselage", "systems", "abs", 1.30)
    for side, yy in (("L", -b_y), ("R", b_y)):
        add(f"cooling_{side} (cold plates, pump, radiator)", mass["cooling"] / 2, 0.08, yy, "L", f"boom_{side}", "systems", "boom", -0.11)
    add("growth allowance", mass["growth"], 0.0, 0.0, "L", "fuselage", "systems", "abs", 1.15)
    # gear (nose frame): cross tubes ahead of pack A and behind the last pack
    x_ct1 = x_pack0 - 0.10
    gear_item = dict(name="landing gear", kg=mass["landing_gear"], group="structure", attach="fuselage")

    # CAD-as-built group CG corrections (iteration 3.3, mass_calibration.json cg_dx_iteration33)
    cdx = CAL.get("cg_dx_iteration33", {})
    rules = [("rotor_", "rotor stations"), ("wing structure", "wing"), ("boom_", "booms"), ("tail structure", "tail"),
             ("fuselage structure", "fuselage"), ("seat_", "seats"), ("furnishings", "seats"), ("avionics", "avionics"),
             ("LV electrical", "LV electrical"), ("flap actuators", "flight controls"), ("flight controls", "flight controls"),
             ("aileron actuator", "flight controls"), ("tail actuators", "flight controls"), ("parachute", "parachute"),
             ("HV ", "HV harness"), ("cooling_", "cooling"), ("battery_", "battery")]
    for it in items:
        for pre, key in rules:
            if it["name"].startswith(pre) and key in cdx:
                it["x_cad_dx"] = cdx[key]
                if it["frame"] in ("L", "F"):
                    it["x"] += cdx[key]
                break
    gear_dx = cdx.get("landing gear", 0.0)

    # ---------------- CG solution (x): fuselage group slides along the wing/rotor group
    x_n = -2.3
    for _ in range(40):
        x_te_n = x_le_l + chord - x_n
        x_ct2 = max(pack_end + 0.10, -x_n + 0.70)
        for it in items:
            if it["frame"] == "F*":
                it["x_from_nose"] = x_te_n + 0.25 + it.get("x_cad_dx", 0.0)
            if it["frame"] == "F#":
                it["x_from_nose"] = x_le_l + 0.2 * chord - x_n + it.get("x_cad_dx", 0.0)
        gx = 0.5 * (x_ct1 + x_ct2) + gear_dx
        mL = sum(it["kg"] * it["x"] for it in items if it["frame"] == "L")
        mF = sum(it["kg"] * (it["x"] if it["frame"] == "F" else it["x_from_nose"]) for it in items if it["frame"] != "L") + gear_item["kg"] * gx
        kF = sum(it["kg"] for it in items if it["frame"] != "L") + gear_item["kg"]
        x_n_new = -(mL + mF) / kF
        if abs(x_n_new - x_n) < 1e-7:
            break
        x_n = x_n_new
    shift = -x_n
    X = lambda xl: float(xl + shift)  # noqa: E731
    for it in items:
        it["x"] = it["x"] + shift if it["frame"] == "L" else (it["x"] if it["frame"] == "F" else it["x_from_nose"])
    x_ct2 = max(pack_end + 0.10, shift + 0.70)
    gear_item.update(x=0.5 * (x_ct1 + x_ct2) + gear_dx, y=0.0, zkey="abs", dz=0.31)
    items.append(gear_item)
    x_cg = shift
    x_le = X(x_le_l)

    # ---------------- vertical stack
    bot = 0.40                                          # cabin belly
    a_f = wf / 2
    s_fit = 1 - (1 - ((pack_w / 2 + 0.01) / a_f) ** e_f) ** (1 / e_f)    # fraction of h/2 above the belly for the pack width
    floor = None
    top_cab = 1.85
    for _ in range(4):
        h_half = (top_cab - bot) / 2
        z_pack0 = bot + s_fit * h_half + 0.005
        floor = z_pack0 + pack_h + 0.005
        srp = floor + 0.200                                  # 150 mm seat stroke (WP G C23 reference)
        seat1 = dict(name="seat_1_pilot", x=x_s1, y=ys1, seat_reference_point_z=srp)
        seat2 = dict(name="seat_2_passenger", x=x_s2, y=ys2, seat_reference_point_z=srp)
        hc1 = head_center(seat1)
        top_cab = hc1[2] + 0.110 + 0.050 + 0.0032 + 0.012   # 50 mm head clearance + canopy + 12 mm margin
    hc2 = head_center(seat2)
    head2_top = hc2[2] + 0.110
    # wing: lowest chord-line height giving 50 mm (+10) passenger head clearance under the wing and the 0.66 m door
    wing_geo = dict(x_le_root=x_le, z_root=1.80, root_chord=chord, incidence_deg=inc_deg, airfoil=afname, span=span)
    x_ms = x_le + A["x_spar_f"] * chord * math.cos(math.radians(inc_deg))
    x_rs = x_le + A["x_spar_r"] * chord * math.cos(math.radians(inc_deg))
    sill = floor + SILL_ABOVE_FLOOR
    for zle in np.arange(1.70, 2.40, 0.0025):
        wing_geo["z_root"] = float(zle)
        Wg = Wing(wing_geo)
        xs_h = np.linspace(hc2[0] - 0.11, hc2[0] + 0.11, 23)
        ok_head = all((np.isnan(Wg.z_lo(xx)) or Wg.z_lo(xx) - (hc2[2] + math.sqrt(max(0.11**2 - (xx - hc2[0]) ** 2, 0))) >= 0.060) for xx in xs_h)
        xs_h1 = np.linspace(hc1[0] - 0.11, hc1[0] + 0.11, 23)
        ok_head1 = all((np.isnan(Wg.z_lo(xx)) or Wg.z_lo(xx) - (hc1[2] + math.sqrt(max(0.11**2 - (xx - hc1[0]) ** 2, 0))) >= 0.060) for xx in xs_h1)
        ok_door = Wg.z_lo(0.5 * (x_ms + x_rs)) - sill >= 0.670
        if ok_head and ok_door and ok_head1:
            break
    z_wing = float(zle)
    Wg = Wing(wing_geo)
    xs_m, zs_m = Wg.lower_at_xc(A["x_spar_f"])
    xs_r, zs_r = Wg.lower_at_xc(A["x_spar_r"])
    Xc = np.linspace(x_le + 0.005, x_le + chord * math.cos(math.radians(inc_deg)) - 0.005, 200)
    zl_min = float(np.nanmin([Wg.z_lo(xx) for xx in Xc]))
    z_boom = min(min(zs_m, zs_r) - PAD_TOP - 0.008, zl_min - BOOM_R_WRAP - 0.008)
    # fuselage top in the wing region: wing-root fittings (y = root_fittings_y, 56 mm under the lower surface) inside the OML
    root_y = 0.38
    pz = zs_m - FITTING_DROP
    top_wing = max(_section_top_for_halfwidth(root_y + 0.008, wf, e_f, pz, bot), top_cab)
    z_push = 1.20
    # parachute canister just aft of the wing trailing edge, inside the OML
    can_d, can_L = 0.32, 0.50
    fire = np.array([0.3, 0.0, 0.95])
    fire = fire / np.linalg.norm(fire)
    x_can = x_le + chord * math.cos(math.radians(inc_deg)) + 0.25
    z_can = 1.42
    can_top = z_can + fire[2] * can_L / 2 + can_d / 2 * abs(fire[0])
    x_can_top = x_can + fire[0] * can_L / 2
    # OML stations (nose frame)
    w_cowl = 0.32
    x_w1 = x_le + chord + 0.10
    x_bend = max(pack_end, x_ct2 + 0.08) + 0.15
    st_def = [
        (0.00, 0.0, 0.98, 0.98), (0.06, 0.46 * wf, 1.18, 0.80), (0.30, 0.82 * wf, 1.48, 0.55), (0.75, wf, top_cab, bot),
        (x_le - 0.10, wf, top_cab + 0.6 * (top_wing - top_cab), bot), (x_ms, wf, top_wing, bot), (x_rs, wf, top_wing, bot),
        (x_w1, wf, top_wing - 0.02, bot), (max(x_bend, x_w1 + 0.15), 0.93 * wf, max(can_top + 0.03, top_wing - 0.08), bot + 0.03),
        (max(x_can_top + 0.10, x_bend + 0.25), 0.80 * wf, can_top + 0.02, bot + 0.20),
        (Lf - 0.60, 0.52 * wf, z_push + 0.30, z_push - 0.30),
    ] + ([(Lf - 0.30, 0.26 * wf, z_push + 0.15, z_push - 0.15), (Lf, 0.0, z_push, z_push)] if twin else   # closed tail cone, no cowl
         [(Lf - 0.32, w_cowl, z_push + w_cowl / 2, z_push - w_cowl / 2), (Lf - 0.12, w_cowl, z_push + w_cowl / 2, z_push - w_cowl / 2),
          (Lf - 0.02, 0.30, z_push + 0.15, z_push - 0.15), (Lf, 0.0, z_push, z_push)])
    st_def.sort(key=lambda t: t[0])
    stations = []
    for xx, ww, tt, bb in st_def:
        if stations and xx - stations[-1]["x"] < 0.05:
            continue
        stations.append(dict(x=round(xx, 4), width=round(ww, 4), height=round(max(tt - bb, 0.0), 4), z_center=round(0.5 * (tt + bb), 4)))
    fus_geo = dict(stations=stations, shape_exponent=e_f, cabin=dict(floor_z=floor))
    # rotor plane: lowest pylon (>= 0.50 m) giving 0.15 m over the wing, clear of the cabin top and the 5 deg burst fan
    from .geometry_checks import OML, occupant_points
    oml = OML(dict(stations=stations, shape_exponent=e_f))
    occ = np.vstack([occupant_points(dict(seat1, y=ys1)), occupant_points(dict(seat2, y=ys2))])
    hubs_xy = np.array([[X(xx), yy] for _, xx, yy, _ in rotor_pos])
    fus_top = max(oml.top(xx) for xx in np.linspace(0, Lf, 200))
    pylon = A["pylon_h"]
    for pylon in np.arange(A["pylon_h"], 0.90, 0.01):
        zbl = z_boom + pylon - 0.02
        ok = zbl - fus_top >= 0.10
        wing_gap = min(((zbl - Wg.z_up(hx + R * math.cos(t))) for hx, hy in hubs_xy for t in np.linspace(0, 2 * np.pi, 36)
                       if not np.isnan(Wg.z_up(hx + R * math.cos(t)))), default=9.0)   # no disc over the wing
        ok = ok and wing_gap >= 0.15
        best = 90.0
        for hx, hy in hubs_xy:
            for t in np.linspace(0, 2 * np.pi, 72, endpoint=False):
                tip = np.array([hx + R * math.cos(t), hy + R * math.sin(t), zbl])
                d = occ - tip
                best = min(best, float(np.degrees(np.arctan2(-d[:, 2], np.hypot(d[:, 0], d[:, 1]))).min()))
        if ok and best >= 5.4:
            break
    z_hub = z_boom + float(pylon)
    # skids: aft end for an 11 deg tail-down pusher strike angle (10 deg requirement)
    x_sk0 = x_ct1 - 0.40
    if twin:
        x_push = X(bx1_l + 0.15)
        x_sk1 = max(x_ct2 + 0.40, x_push - (z_boom - Rp) / math.tan(math.radians(11.0)))
    else:
        x_sk1 = max(x_ct2 + 0.40, x_push - (z_push - Rp) / math.tan(math.radians(11.0)))
    # fins: exposed height under the boom
    h_v_exp = S_v / 2 / c_v
    z_fin_root = z_boom - BOOM_R_WRAP - h_v_exp
    zmap = dict(hub=z_hub, wing=z_wing, boom=z_boom, pusher=z_push, srp=srp, pack=z_pack0 + pack_h / 2, floor=floor,
                chute=z_can, abs=0.0)
    for it in items:
        it["z"] = zmap[it.get("zkey", "abs")] + it.get("dz", 0.0)
        if it["name"].startswith("parachute"):
            it["x"] = x_can
    tot = sum(it["kg"] for it in items)
    cg = np.array([sum(it["kg"] * it[k] for it in items) for k in "xyz"]) / tot

    # ---------------- neutral point, incidence, loading cases with the rotor-out LP
    hn = s(o, "hn")
    x_np = x_le + hn * chord
    cases = {}
    rot_xy_abs = hubs_xy
    Qh = s(o, "P_mot_site") * 1e3 / (vtip / R)
    k_qt = Qh / s(o, "T_rotor")
    spin, _ = best_spin_pattern(rot_xy_abs - np.array([cg[0], 0.0]), 1.0, k_qt) if not coax else (None, None)
    if coax:
        spin = np.array([1 if nm.endswith("up") else -1 for nm, *_ in rotor_pos], float)
        spin *= np.array([1 if (i // 2) % 2 == 0 else -1 for i in range(len(rotor_pos))])
    ceil_ = ph.isa(A["ceil_alt"], A["dT"])
    site_ = ph.isa(A["site_alt"], A["dT"])
    f_dl = s(o, "f_dl")
    T_h = s(o, "T_rotor")
    for cname, mods in (("pilot + passenger (MTOW)", {}),
                        ("pilot + cargo (MTOW)", {"occupant_2 (passenger)": None, "seat_2 (passenger / removable)": None,
                                                  "cargo": (A["occupant_kg"] + seat_kg, x_s2 + 0.05, 0.0, floor + 0.25)}),
                        ("pilot only", {"occupant_2 (passenger)": None})):
        its = [dict(i) for i in items if i["name"] not in mods]
        for k, v in mods.items():
            if v is not None:
                its.append(dict(name=k, kg=v[0], x=v[1], y=v[2], z=v[3]))
        mc = sum(i["kg"] for i in its)
        cgc = np.array([sum(i["kg"] * i[k] for i in its) for k in "xyz"]) / mc
        rel = rot_xy_abs - cgc[:2]
        out = dict(mass_kg=R3(mc), cg_m=[R4(c) for c in cgc], static_margin=R4((x_np - cgc[0]) / chord))
        for tag, g_lf, atm, margin in (("1000m", 1.0, ceil_, A["k_ctrl"]), ("flare_500m", A["oei_flare_g"], site_, 0.0)):
            Fz = mc * G0 * (1 + f_dl) * g_lf
            worst = [lp_max_thrust(rel, spin, Fz, k_qt, f)[0] for f in range(len(rel))]
            kf = int(np.argmax(worst))
            T_c = worst[kf] * (1 + margin)
            r_w = math.sqrt(T_c / T_h)
            if coax:
                P = (A["kappa"] * A["coax_kint"] * T_c**1.5 / math.sqrt(2 * atm["rho"] * math.pi * R**2)
                     + sigma * A["cd0_blade"] * atm["rho"] * math.pi * R**2 * (vtip * r_w) ** 3 / 8)
            else:
                P = float(ph.rotor_power(T_c, Dr, atm["rho"], vtip * r_w, sigma, A["kappa"], A["cd0_blade"])[0])
            Q = P / (vtip / R * r_w)
            sfx = "" if tag == "1000m" else "_flare"
            out.update({f"oei{sfx}_worst_failed_rotor": rotor_pos[kf][0], f"oei{sfx}_max_thrust_N": R3(worst[kf]),
                        f"oei{sfx}_thrust_ratio_to_hover": R4(worst[kf] / T_h),
                        f"oei{sfx}_shaft_power_kw{'_1000m' if not sfx else '_500m'}": R3(P / 1e3),
                        f"oei{sfx}_torque_Nm{'_1000m' if not sfx else '_500m'}": R3(Q), f"oei{sfx}_rpm": R3(vtip / R * r_w * 60 / (2 * math.pi)),
                        f"oei{sfx}_power_margin": R4(1 - P / 1e3 / lmot["peak_kw"]), f"oei{sfx}_torque_margin": R4(1 - Q / lmot["torque_nm"])})
            if tag == "1000m":
                out["hover_max_rotor_thrust_all_rotors_N"] = R3(lp_max_thrust(rel, spin, mc * G0 * (1 + f_dl), k_qt, None)[0])
                out["hover_mean_rotor_thrust_N"] = R3(mc * G0 * (1 + f_dl) / len(rel))
        cases[cname] = out
    z = dict(wing=z_wing, boom=z_boom, hub=z_hub, tail=z_boom, pusher=z_push, occ=srp + 0.28, seat=srp, floor=floor, pack=zmap["pack"],
             pylon=float(pylon), canister=z_can, fin_root=z_fin_root, top_cab=top_cab, top_wing=top_wing, bot=bot)
    lay = dict(packs=packs, pack_len=pack_len, pack_w=pack_w, pack_h=pack_h, tiers=tiers, cells_across=across, rows=rows,
               x_ct=(x_ct1, x_ct2), x_skid=(x_sk0, x_sk1), x_can=x_can, can=(can_d, can_L, fire.tolist()), root_y=root_y,
               stations=stations, x_ms=xs_m, x_rs=xs_r, x_push=x_push, h_v_exp=h_v_exp, twin=twin,
               twin_clearance=(dict(prop_plane_x=x_push, axial_gap_htail_te_m=round(bx1_l + 0.15 - (x_tle_l + c_h), 3),
                                    axial_gap_fin_te_m=round(bx1_l + 0.15 - (x_tle_l + c_v), 3),
                                    tip_to_tip_gap_m=round(2 * b_y - Dp, 3), tip_to_boom_axis_of_other_m=round(2 * b_y - Rp, 3),
                                    ground_clearance_static_m=round(z_boom - Rp, 3), skid_aft_x=round(x_sk1, 3),
                                    tip_over_htail_radial_m=round(Rp - BOOM_R_WRAP, 3)) if twin else None), seats=(seat1, seat2), seat_kg=seat_kg)
    return dict(x=x, cfg=cfg, o=o, mass=mass, items=items, cg=cg, cases=cases, spin=spin, rotor_pos=[(nm, xx, yy, z_hub + dz) for nm, xx, yy, dz in rotor_pos],
                shift=shift, X=X, z=z, lay=lay, af=af, afname=afname, lmot=lmot, pmot=pmot, cell=cell, inv=inv, x_le=x_le, x_np=x_np,
                hn=hn, incidence=inc_deg, packs=packs, pack_len=pack_len, unit_kg=unit_kg, m_push=m_push, k_qt=k_qt, A=A, CAL=CAL)


# ================================================================================================================
def _rotor_max(b):
    """Maximum thrust of one lift rotor/motor (sea level ISA, torque or peak power limited), its rpm and inertia."""
    o, A, lmot = b["o"], b["A"], b["lmot"]
    x = b["x"]
    R, vtip = float(x["D"]) / 2, float(x["vtip"])
    T_h, P_h = s(o, "T_rotor"), s(o, "P_mot_site") * 1e3
    Q_h = P_h / (vtip / R)
    T_q = lmot["torque_nm"] * T_h / Q_h                        # fixed pitch: Q/T constant at any rpm
    T_p = T_h * (lmot["peak_kw"] * 1e3 / P_h) ** (2 / 3)          # P ~ T^1.5
    T_max = min(T_q, T_p)
    rpm = vtip / R * 60 / (2 * math.pi) * math.sqrt(T_max / T_h)
    m_blade = D.blade_mass_kg(float(x["D"]))
    I_rot = 2 * m_blade * R**2 / 3 + 0.4 * lmot["mass_kg"] * 0.12**2
    return T_max, rpm, I_rot


def write(b: dict, out_dir, tag="") -> dict:
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    o, x, A, X, z = b["o"], b["x"], b["A"], b["X"], b["z"]
    cfg = b["cfg"]
    mass = b["mass"]
    n = int(cfg["n_rot"])
    coax = bool(cfg.get("coax", False))
    fus = SEATING[cfg.get("seating", "tandem")]
    Dr, R, vtip, nb = float(x["D"]), float(x["D"]) / 2, float(x["vtip"]), int(x["nb"])
    span, chord, V, Dp = float(x["span"]), float(x["chord"]), float(x["V"]), float(x["Dp"])
    S = span * chord
    lmot, pmot, cell, af = b["lmot"], b["pmot"], b["cell"], b["af"]
    mtow = s(o, "mtow")
    W = mtow * G0
    cg = b["cg"]
    cr = ph.isa(A["cruise_alt"], A["dT"])
    sl = ph.isa(0.0)
    site = ph.isa(A["site_alt"], A["dT"])
    eta_d = A["eta_m"] * A["eta_inv"] * A["eta_w"]
    x_le, x_te = b["x_le"], b["x_le"] + chord
    xr_abs = [X(v) for v in np.asarray(o["xr"])[0]]
    x_fs, x_rs = b["lay"]["x_ms"], b["lay"]["x_rs"]
    x_tle = X(s(o, "x_tle"))
    c_h, span_h, S_h = s(o, "c_h"), s(o, "span_h"), s(o, "S_h")
    S_v, h_v, c_v = s(o, "S_v"), s(o, "h_v"), s(o, "c_v")
    bx0, bx1 = X(s(o, "boom_x0")), X(s(o, "boom_x1"))
    b_y = s(o, "b_y")
    T_max, rpm_max, I_rot = _rotor_max(b)
    v_cap = A["mach_tip_flare_max"] * float(ph.isa(0.0)["a"])            # flight-controller rpm cap: tip Mach 0.70, sea level
    fc_rpm = round(v_cap / R * 60 / (2 * math.pi), -1)
    fc_T = round(min(T_max, s(o, "T_rotor") * (v_cap / vtip) ** 2), -1)
    T_h = s(o, "T_rotor")
    Q_h = s(o, "P_mot_site") * 1e3 / (vtip / R)
    rpm_h = s(o, "rpm_hover")
    blade_chord = s(o, "blade_chord")
    rpm_p = s(o, "rpm_pusher")
    om_p = rpm_p * 2 * math.pi / 60
    n_pu = 2 if b["lay"]["twin"] else 1          # values below are per propeller / per motor
    P_push_pk = min(pmot["peak_kw"], pmot["torque_nm"] * om_p / 1e3) / n_pu
    T_push_max = float(ph.static_thrust(P_push_pk * 1e3, Dp, sl["rho"]))
    I_push = 3 * (D.blade_mass_kg(Dp) * 0.8) * (Dp / 2) ** 2 / 3 + 0.4 * pmot["mass_kg"] / n_pu * 0.12**2
    x_push = b["lay"]["x_push"]
    lay = b["lay"]
    case_mtow = b["cases"]["pilot + passenger (MTOW)"]
    ws = W / S
    # wing spar initial sections: ultimate root bending from an elliptic span load minus boom/rotor relief
    n_ult = 1.5 * 3.8
    semispan = span / 2
    y_root = b["lay"]["root_y"]
    side_relief_kg = mass["booms"] / 2 + n / 2 * b["unit_kg"]
    M_root = n_ult * (W - mass["wing"] * G0) / 2 * (4 * semispan / (3 * math.pi) - y_root) \
        - n_ult * side_relief_kg * G0 * (b_y - y_root)
    h_main = 0.92 * b["af"]["t_c"] * chord
    sig_c = 380e6
    b_cap = 0.08
    t_cap_root = max(0.8 * M_root / (h_main * 0.95) / (b_cap * sig_c), 0.002)
    yb = np.array([0.0])  # noqa: F841
    h_rear = 0.60 * b["af"]["t_c"] * chord
    t_rear_root = max(0.2 * M_root / (h_rear * 0.95) / (0.05 * sig_c), 0.0015)
    t_boom = s(o, "t_boom_root")
    t_ct = None
    M_ct = 1.5 * A["n_land"] * W / 4 * 0.45
    t_ct = float(np.clip(M_ct / (math.pi * 0.038**2 * 262e6), 0.002, 0.008))
    stations = b["lay"]["stations"]
    fus_h = max(st_["height"] for st_ in stations)
    swet_geo = fuselage_wetted(None, A["fus_e"], stations)

    # --------------------------------------------------------------- geometry.json
    rotors_fea, rotors_cfd = [], []
    spin = b["spin"]
    for i, (nm, xl, yy, zz) in enumerate(b["rotor_pos"]):
        sp = int(spin[i])
        common = dict(diameter=R3(Dr), blades=nb)
        rotors_fea.append(dict(name="LR_" + nm, boom="boom_" + nm[0], x=R4(X(xl)), y=R4(yy), z=R4(zz), spin=sp,
                               max_thrust_N=R3(T_max), max_torque_Nm=lmot["torque_nm"], rpm_max=R3(rpm_max),
                               rpm_hover=R3(rpm_h), rotor_inertia_kgm2=R4(I_rot), mass_kg=R3(b["unit_kg"]),
                               axis=[0.0, 0.0, 1.0], torque_per_thrust_m=R4(Q_h / T_h), **common))
        rotors_cfd.append(dict(id="LR_" + nm, name="LR_" + nm, hub=[R4(X(xl)), R4(yy), R4(zz)], diameter_m=R3(Dr), spin=sp,
                               spin_sense="ccw" if sp > 0 else "cw", axis=[0.0, 0.0, 1.0], blade_chord=R4(blade_chord),
                               hub_diameter=R3(lmot["diameter_m"] + 0.02), hub_height=0.14, stopped_azimuth_deg=0.0,
                               mast_thickness=A["pylon_fair_t"], mast_chord=A["pylon_fair_c"],
                               pylon=dict(tube_od=0.100, tube_t=0.0016, fairing_thickness=A["pylon_fair_t"], fairing_chord=A["pylon_fair_c"],
                                          from_z=R4(z["boom"]), to_z=R4(zz - 0.07), note="faired 6061 pylon tube (WP F section)"),
                               blade_pitch_deg=10.0, thrust_hover_n=R3(T_h), max_thrust_n=fc_T, fc_rpm_cap=fc_rpm, max_thrust_n_structural=R3(T_max),
                               max_thrust_note="flight-controller rpm cap at tip Mach 0.70; structure sized conservatively at "
                                               f"{T_max:,.0f} N (motor peak torque through the prop)",
                               max_torque_nm=lmot["torque_nm"],
                               rotor_inertia_kgm2=R4(I_rot), **common))
    masses = [dict(name=it["name"], kg=R3(it["kg"]), x=R4(it["x"]), y=R4(it["y"]), z=R4(it["z"]), attach=it["attach"])
              for it in b["items"] if it["group"] in ("battery", "systems")]
    seats = []
    for sdict in lay["seats"]:
        seats.append(dict(name=sdict["name"], x=R4(sdict["x"]), y=R4(sdict["y"]), z=R4(z["occ"]),
                          occupant_kg=A["occupant_kg"], seat_kg=R3(lay["seat_kg"]), attach="fuselage",
                          seat_reference_point_z=R4(z["seat"])))
    x_chute = lay["x_can"]
    from .geometry_checks import BOOM_R_WRAP
    geo = {
        "_about": "E8-200 selected design geometry (work package D). Generated by sizing/design_out.py; do not edit by hand. "
                  "Read by FEA (fea/README.md), CFD (cfd/README.md) and the checker (methods/design_schema.md). "
                  "design/geometry_cfd.json is the same geometry with the CFD tool's native types (spin strings, gear dict).",
        "units": "m, kg, N, N m, rpm, deg", "frame": "x aft from the fuselage nose, y right, z up from the skid bottom (ground)",
        "mtow_kg": R3(mtow),
        "cg_mtow_m": [R4(c) for c in cg], "cg": dict(x=R4(cg[0]), y=R4(cg[1]), z=R4(cg[2])),
        "limits": dict(n_pos=3.8, n_neg=-1.5, n_land=3.0),
        "aero": dict(CLalpha_per_rad=R4(s(o, "a_w")), CLmax=R4(0.9 * af["cl_max"]), CLmin=-0.80, Cm0=R4(af["cm0"]),
                     VC_ms=R3(V * math.sqrt(cr["rho"] / sl["rho"])), VD_ms=R3(1.4 * V * math.sqrt(cr["rho"] / sl["rho"])),
                     VD_tas_ms=R3(1.4 * V), speeds_note="VC_ms and VD_ms are EAS (sea-level density); VD_tas_ms is TAS at 500 m ISA+15",
                     cruise_thrust_N=R3(s(o, "D_cruise")), gust_altitude_m=A["cruise_alt"],
                     cruise_speed_ms=R3(V), cruise_CL=R4(s(o, "CL")), CD0=R4(s(o, "CD0")), oswald=R4(s(o, "oswald")),
                     note="CLalpha: Helmbold finite wing; CLmax clean = 0.9 x NeuralFoil section clmax; Cm0: section value about c/4"),
        "reference": dict(S_ref=R4(S), c_ref=R4(chord), b_ref=R4(span), x_ref=R4(cg[0]), z_ref=R4(cg[2])),
        "wing": dict(span=R4(span), span_m=R4(span), root_chord=R4(chord), root_chord_m=R4(chord), tip_chord=R4(chord),
                     tip_chord_m=R4(chord), area=R4(S), x_le_root=R4(x_le), le_root_x_m=R4(x_le), z_root=R4(z["wing"]),
                     z_m=R4(z["wing"]), y_root=0.0, sweep_le_deg=0.0, dihedral_deg=0.0, incidence_deg=round(b["incidence"], 2),
                     fuselage_angle_in_cruise_deg=round(math.degrees(s(o, "CL") / s(o, "a_w")) + b["af"]["alpha0_deg"] - b["incidence"], 2),
                     twist_tip_deg=0.0, airfoil=b["afname"], t_c=R4(af["t_c"]), max_thickness_x_c=R4(af["x_t_c"]),
                     mass_kg=R3(mass["wing"]), root_fittings_y=R4(lay["root_y"]), spar_x_c=[A["x_spar_f"], A["x_spar_r"]],
                     front_spar_x_c=A["x_spar_f"], rear_spar_x_c=A["x_spar_r"],
                     construction="constant-chord foam core (hot-wire cut, XPS with spanwise lightening voids: 30 mm of foam kept "
                                  "under each skin, solid at ribs, spar box and hinge lines) with wet-laid carbon skins; main-spar box "
                                  "foam H45; one piece, removable",
                     root_fairing="the fuselage OML rises into the wing between x_le-0.10 and the trailing edge (shoulder-wing "
                                  "fairing); the root fittings at y = root_fittings_y lie inside it",
                     spars=[
                         dict(name="main", x_c=A["x_spar_f"],
                              section_root=dict(type="cap_web", h=R4(h_main), b_cap=b_cap, t_cap=R4(t_cap_root), n_web=2, t_web=0.0020,
                                                cap_material="cf_ud_wet", web_material="cf_fabric_wet", web_layup="+-45"),
                              section_tip=dict(type="cap_web", h=R4(h_main), b_cap=0.05, t_cap=0.0015, n_web=2, t_web=0.0010,
                                               cap_material="cf_ud_wet", web_material="cf_fabric_wet", web_layup="+-45")),
                         dict(name="rear", x_c=A["x_spar_r"],
                              section_root=dict(type="cap_web", h=R4(h_rear), b_cap=0.05, t_cap=R4(t_rear_root), n_web=1, t_web=0.0015,
                                                cap_material="cf_ud_wet", web_material="cf_fabric_wet", web_layup="+-45"),
                              section_tip=dict(type="cap_web", h=R4(h_rear), b_cap=0.03, t_cap=0.0010, n_web=1, t_web=0.0010,
                                               cap_material="cf_ud_wet", web_material="cf_fabric_wet", web_layup="+-45"))],
                     torsion_box=dict(skin_t=0.0008, skin_material="cf_fabric_wet", skin_layup="+-45", depth_factor=0.85),
                     control_surfaces=dict(ailerons=dict(y_from=R3(0.62 * span / 2), y_to=R3(0.97 * span / 2), chord_fraction=0.30),
                                           flaps=None if int(x["flap"]) == 0 else dict(y_from=R3(fus["w"] / 2 + 0.05), y_to=R3(0.6 * span / 2),
                                                                                        chord_fraction=0.30)),
                     sizing_note=f"initial spar caps from ultimate root bending {M_root / 1e3:.1f} kN m (n = 5.7, elliptic load, boom/rotor relief), "
                                 "UD wet lay-up design stress 380 MPa, main spar 80 % of the moment; WP F to size"),
        "fuselage": dict(x_nose=0.0, x_tail=R4(fus["L"]), z_axis=R4(0.5 * (z["bot"] + z["top_wing"])), mass_kg=R3(mass["fuselage"]),
                         length_m=fus["L"], max_width_m=fus["w"], max_height_m=R4(fus_h), wetted_area_m2=R3(swet_geo),
                         section=dict(type="rect_tube", b=fus["w"], h=R4(fus_h), t_web=0.0015, t_flange=0.0015, material="cf_fabric_wet_qi"),
                         shape_exponent=A["fus_e"], stations=stations,
                         cabin=dict(seating=cfg.get("seating", "tandem"), floor_z=R4(z["floor"]), belly_z=z["bot"],
                                    canopy="polycarbonate (CAB-PC-SHEET), 2-piece, hinged right",
                                    passenger_door=dict(x_from=R4(lay["x_ms"] + 0.04), x_to=R4(lay["x_rs"] - 0.04), sill_z=R4(z["floor"] + 0.53),
                                                        note="between the main- and rear-spar posts")),
                         tail_cone_cowl=(None if lay["twin"] else dict(x_from=R4(fus["L"] - 0.32), x_to=R4(fus["L"] - 0.02), width=0.32, height=0.32,
                                             note="REB 90 (270 mm) cowl is part of the OML")),
                         construction="wet-laid carbon/foam sandwich shell over CNC-cut tooling-foam plugs, two halves"),
        "booms": [dict(name=f"boom_{sd}", y=R4(yy), z=R4(z["boom"]), x_front=R4(bx0), x_aft=R4(bx1), x_start=R4(bx0), x_end=R4(bx1),
                       diameter=A["boom_od"], mirror=False, mass_kg=R3(mass["booms"] / 2),
                       section=dict(type="tube", od=A["boom_od"], t=R4(t_boom), material="cf_tube_rollwrapped_ud"),
                       construction="COTS 4 in ID roll-wrapped carbon tube (MAT-TUBE-DP-4x96, 1.6 mm wall) spliced with internal sleeves, "
                                    f"in-house UD over-wrap to {t_boom * 1e3:.1f} mm between the inner rotors; wall from the boom bending "
                                    "(1.5 x rotor-out thrust with control margin on both rotors of an arm, 300 MPa)",
                       attach_x=[R4(x_fs), R4(x_rs)])
                  for sd, yy in (("L", -b_y), ("R", b_y))],
        "lift_rotors": rotors_cfd,
        "rotors": rotors_fea,
        "pusher": (dict(name="pusher", hub=[R4(x_push), 0.0, R4(z["pusher"])], x=R4(x_push), y=0.0, z=R4(z["pusher"]), axis=[-1.0, 0.0, 0.0],
                       diameter=R3(Dp), blades=int(x.get("pnb", 3)), spinner_diameter=0.28, blades_in_cfd=False, spin=1,
                       max_thrust_N=R3(T_push_max), max_torque_Nm=pmot["torque_nm"], rpm_max=R3(rpm_p * 1.1), rpm_cruise=R3(rpm_p),
                       rotor_inertia_kgm2=R4(I_push), mass_kg=R3(b["m_push"]), attach="fuselage", motor=pmot["id"], motor_diameter_m=0.2702,
                       propeller=D.PUSHER_PROPS[s(o, "pprop_idx").__int__()]["id"]) if not lay["twin"] else
                   dict(layout="twin_boom_tail", count=2, name="pusher_L",
                        hub=[R4(x_push), R4(-b_y), R4(z["boom"])], x=R4(x_push), y=R4(-b_y), z=R4(z["boom"]), axis=[-1.0, 0.0, 0.0],
                        diameter=R3(Dp), blades=int(x.get("pnb", 3)), spinner_diameter=0.28, blades_in_cfd=False, spin=1,
                        max_thrust_N=R3(T_push_max), max_torque_Nm=pmot["torque_nm"] / 2, rpm_max=R3(rpm_p * 1.1), rpm_cruise=R3(rpm_p),
                        rotor_inertia_kgm2=R4(I_push), mass_kg=R3(b["m_push"] / 2), attach="boom_L", motor=pmot["id"],
                        motor_diameter_m=R4(pmot["diameter_m"]), inverter=lmot["inverter"], propeller=D.PUSHER_PROPS[s(o, "pprop_idx").__int__()]["id"],
                        note="pusher (legacy key) = left unit; both units in 'pushers'. Both props turn the same way (spin +1, "
                             "one blade hand: E-PROPS publishes CCW blades only to 1.90 m); the props run in the H-tail and fin "
                             "wakes (open item)")),
        "pushers": ([dict(name=f"pusher_{sd_}", hub=[R4(x_push), R4(yy), R4(z["boom"])], x=R4(x_push), y=R4(yy), z=R4(z["boom"]),
                          axis=[-1.0, 0.0, 0.0], diameter=R3(Dp), blades=int(x.get("pnb", 3)), spinner_diameter=0.28,
                          spin=1, blades_in_cfd=False, max_thrust_N=R3(T_push_max),
                          blade_pitch_075R_deg=round(math.degrees(math.atan(V / (0.75 * math.pi * rpm_p / 60 * Dp))) + 3.0, 1),
                          pitch_note="ground-adjustable pitch at 0.75 R for the cruise rpm: helix angle + 3 deg (estimate)",
                          max_torque_Nm=pmot["torque_nm"] / 2, rpm_cruise=R3(rpm_p), rpm_max=R3(rpm_p * 1.1),
                          rotor_inertia_kgm2=R4(I_push), mass_kg=R3(b["m_push"] / 2), attach=f"boom_{sd_}",
                          motor=dict(id=pmot["id"], x_face=R4(bx1), diameter=R4(pmot["diameter_m"]), length=0.09,
                                     note="motor plate bolted to a boom-end fitting (bonded aluminium plug in the boom tube)"),
                          mount=dict(type="boom-end fitting", x_from=R4(bx1 - 0.15), x_to=R4(bx1 + 0.06),
                                     note="machined 6061 plug bonded 150 mm into the boom, motor plate on its face; reacts thrust, "
                                          "motor torque and the prop gyroscopic moment into the boom"),
                          inverter=dict(id=lmot["inverter"], pod_x=R4(x_tle - A["pusher_pod_ahead_of_tail"]), pod_z=R4(z["boom"] - 0.10),
                                        note="iteration 3.3: inverter pod under the boom, centred 0.30 m ahead of the H-tail / fin leading edge, "
                                             "clear of TL-CLAMP, VF-SPAR and RUD (3.2 position 0.45 m ahead of the boom end collided); "
                                             "3-phase leads run aft inside the boom to the motor"),
                          spinner=dict(diameter=0.28, x_to=R4(x_push + 0.20)),
                          propeller=D.PUSHER_PROPS[s(o, "pprop_idx").__int__()]["id"])
                     for sd_, yy in (("L", -b_y), ("R", b_y))] if lay["twin"] else None),
        "pusher_clearances": (dict(lay["twin_clearance"], prop_plane_behind_rear_lift_disc_m=R4(x_push - (max(xr_abs) + R)),
                                   note="open items: props run in the H-tail and fin wakes (noise, blade loads); thrust deduction "
                                        "assumed at the CFD tail-cone value 4.5 %") if lay["twin"] else None),
        "tail": dict(type="H", x_ac=R4(x_tle + 0.25 * c_h), x_spar=R4(x_tle + 0.30 * c_h), z=R4(z["tail"]), span=R4(2 * b_y),
                     mass_kg=R3(mass["tail"]), area_h_m2=R4(S_h), chord_h=R4(c_h), area_v_total_m2=R4(S_v),
                     span_exposed_h=R4(span_h), height_exposed_v=R4(lay["h_v_exp"]),
                     area_note="areas are exposed areas (H-tail between the boom surfaces, fins below the boom underside)",
                     volume_h=A["Vh"], volume_v=A["Vv"], arm_h_m=R4(s(o, "l_t")),
                     spar_section=dict(type="tube", od=0.050, t=0.0020, material="cf_tube_rollwrapped_twill"),
                     fins=[dict(boom="boom_L"), dict(boom="boom_R")],
                     horizontal=[dict(airfoil="naca0014", span=R4(2 * b_y), root_chord=R4(c_h), tip_chord=R4(c_h), x_le_root=R4(x_tle),
                                      z_root=R4(z["tail"]), y_root=0.0, incidence_deg=0.0, mirror=True,
                                      elevator_chord_fraction=0.35)],
                     vertical=[dict(airfoil="naca0012", x_le_root=R4(x_tle), y=R4(yy), z_root=R4(z["fin_root"]),
                                    height=R4(lay["h_v_exp"] + BOOM_R_WRAP),
                                    root_chord=R4(c_v), tip_chord=R4(c_v), sweep_le_deg=0.0, mirror=False, rudder_chord_fraction=0.35,
                                    note="ventral fin under the boom (clear of the rear lift-rotor disc)")
                               for yy in (-b_y, b_y)]),
        "landing_gear": [dict(name=f"skid_{'F' if k == 0 else 'A'}{'L' if gy < 0 else 'R'}", x=R4(gx), y=gy, z=0.0, attach="fuselage",
                              mass_kg=R3(mass["landing_gear"] / 4)) for k, gx in enumerate(lay["x_ct"]) for gy in (-0.70, 0.70)],
        "gear_strut_section": dict(type="tube", od=0.0762, t=0.00241, material="al6061_t6_extr",
                                   note="3 in x 0.095 in 6061-T6 tube as in the CAD (LG-LEG); FEA phase 3.3B MS +0.32 at MTOW 1,350 kg"),
        "landing_gear_oml": dict(
            type="skid", material="6061-T6 tube",
            skids=[dict(y=0.70, z=0.03, x_start=R4(lay["x_skid"][0]), x_end=R4(lay["x_skid"][1]), diameter=0.06, mirror=True)],
            struts=[dict(p1=[R4(gx), 0.70, 0.06], p2=[R4(gx), 0.30, R4(z["bot"] + 0.04)], diameter=0.076, mirror=True) for gx in lay["x_ct"]],
            dampers=[dict(p1=[R4(gx), 0.55, 0.22], p2=[R4(gx), 0.42, 0.72], stroke_m=0.080, type="oleo-pneumatic", mirror=True)
                     for gx in lay["x_ct"]],
            cross_tube=dict(od=0.0762, t=0.00241, faired=True, note="WP F section; legs faired (LG-FAIR); dampers in parallel with each leg (>= 75 mm stroke)"),
            faired=True),
        "battery_packs": [dict(name=p["name"], x=R4(p["x"]), y=0.0, z=R4(z["pack"]), length=R4(p["length"]), width=lay["pack_w"],
                               height=R4(lay["pack_h"]), tiers=lay["tiers"], cells_across=lay["cells_across"], rows_per_tier=lay["rows"],
                               series=int(s(o, "Ns")), parallel=int(s(o, "Np_pack")), cell=cell["id"], kg=R3(s(o, "battery_kg") / int(x["npk"])),
                               bms="BMS-ORION2", contactors="2 x HV-EV200", fuse="HV-FUSE")
                          for p in b["packs"]],
        "masses": masses,
        "seats": seats,
        "cargo_bay": dict(x_center=R4(fus["x_seat"][1] + 0.05), y=0.0, z_floor=R4(z["floor"]), length=0.65, width=0.60, height=0.55,
                          note="second seat removed; tie-downs on the seat rails; min 0.6 x 0.5 x 0.5 m required"),
        "parachute": dict(model=D.PARACHUTES[int(s(o, "chute_idx"))]["id"], kg=R3(mass["parachute"]),
                          canister=dict(x=R4(x_chute), y=0.0, z=R4(z["canister"]), diameter=0.32, length=0.50, fire_direction=[0.3, 0.0, 0.95],
                                        note="inside the OML under a frangible hatch"),
                          n_open_limit=round((48.8e3 if mtow > 1050 else 47.4e3) / (mtow * G0), 2),
                          attach=[dict(name="chute_front_L", x=R4(x_fs), y=-0.30, z=R4(z["top_wing"] - 0.05)),
                                  dict(name="chute_front_R", x=R4(x_fs), y=0.30, z=R4(z["top_wing"] - 0.05)),
                                  dict(name="chute_rear", x=R4(min(x_chute + 0.8, fus["L"] - 0.6)), y=0.0, z=R4(z["canister"] + 0.05))],
                          note="n_open_limit = vendor opening shock at VNE and MTOW / weight: GRS 6 800-990/1050 47.4 kN (ST12), "
                               "GRS 6 990-1190 48.8 kN (galaxysky.cz p44)"),
        "mass_items": [dict(name=it["name"], kg=R3(it["kg"]), x=R4(it["x"]), y=R4(it["y"]), z=R4(it["z"]), group=it["group"],
                            attach=it["attach"]) for it in b["items"]],
        "loading_cases": b["cases"],
        "mass": dict(mtow_kg=R3(mtow), x_cg=R4(cg[0]), z_cg=R4(cg[2])),
        "operating": dict(cruise_speed_ms=R3(V), hover_thrust_per_lift_rotor_n=R3(T_h), cruise_thrust_pusher_n=R3(s(o, "D_cruise"))),
        "neutral_point_x_m": R4(b["x_np"]),
    }
    (out_dir / f"geometry{tag}.json").write_text(json.dumps(geo, indent=1))
    # CFD-native view: spin as 'ccw'/'cw' strings, gear as the OML dict
    gc = json.loads(json.dumps(geo))
    for r in gc["lift_rotors"]:
        r["spin"] = r.pop("spin_sense")
    gc["landing_gear"] = gc.pop("landing_gear_oml")
    gc["_about"] = "CFD view of design/geometry.json (generated together with it): lift_rotors[].spin as 'ccw'/'cw', landing_gear as skids/struts."
    (out_dir / f"geometry_cfd{tag}.json").write_text(json.dumps(gc, indent=1))

    # --------------------------------------------------------------- selected_design.json
    hov_site = s(o, "P_hover_site")
    cost = {k: float(np.asarray(v).ravel()[0]) for k, v in o["cost"].items()}
    cost_total = s(o, "cost_total")
    acc_factor = (mass["inverters"] + mass["hv_harness"] + mass["cooling"]) / (mass["lift_motors"] + mass["pusher_motor"])
    rot_arms = sorted({R4(abs(xr_abs[1] - x_fs)), R4(abs(xr_abs[0] - x_fs))})
    stopped_each = (A["cd_motor_bell"] * lmot["diameter_m"] * lmot["exposed_height_m"]
                    + A["cd_pylon"] * A["pylon_fair_t"] * b["z"]["pylon"] + A["cd_nacelle"] * A["nacelle_frontal"]
                    + nb * float(ph.cf_mixed(cr["rho"] * V * blade_chord / cr["mu"], V / cr["a"], 0.1)) * 1.3 * 2 * R * blade_chord * 0.9)
    E_nom = s(o, "E_nom")
    rng = s(o, "range_km")
    sd = {
        "schema_version": "1.0",
        "name": f"E8-200 selected design: {n} x {Dr:.2f} m lift rotors ({lmot['id']}), {cell['id']} "
                f"{int(s(o, 'Ns'))}s{int(s(o, 'Np_pack'))}p x {int(x['npk'])} packs, {span:.1f} m wing, {V * 3.6:.0f} km/h",
        "notes": "Generated by sizing/run.py (work package D). Masses: catalog parts (bom/catalog.json) + Raymer GA structure with "
                 "composite factor 0.85 + physics-based booms/gear/harness; see sizing/README.md.",
        "requirements": dict(range_km=cfg["range_km"], cruise_speed_kmh_min=120, payload_kg=A["payload_kg"],
                             cruise_over_stall_min=A["stall_factor"], footprint_max_m=A["L_max"],
                             note="20 km design range (capability in results.range_km). Iteration 3.2 relaxation "
                                  "(requirements.yaml iteration_3_2_relaxation): one-motor-out flare "
                                  f"{A['oei_flare_g']:.2f} g (was 1.2), cruise >= {A['stall_factor']:.2f} Vs (was 1.3), footprint "
                                  f"{A['L_max']:.1f} m (was 9.0), cruise >= 120 km/h (was 135)"),
        "mass_kg": dict(mtow=R3(mtow), payload=A["payload_kg"], battery=R3(s(o, "battery_kg")), empty=R3(s(o, "empty")),
                        breakdown={k: R3(v) for k, v in mass.items()}),
        "environment": dict(hover_design_altitude_m=A["site_alt"], hover_ceiling_m=A["ceil_alt"], hover_isa_offset_C=A["dT"],
                            cruise_altitude_m=A["cruise_alt"], cruise_isa_offset_C=A["dT"]),
        "lift_rotors": dict(count=n, coaxial=coax, diameter_m=R3(Dr), blades=nb, blade_chord_m=R4(blade_chord), solidity=R4(s(o, "sigma")),
                            tip_speed_hover_ms=vtip, figure_of_merit=R4(s(o, "fm")), download_fraction=R4(s(o, "f_dl")),
                            stopped_drag_area_m2_each=R4(stopped_each),
                            motor_diameter_m=lmot["diameter_m"], motor_exposed_height_m=lmot["exposed_height_m"],
                            pylon_frontal_area_m2=R4(b["z"]["pylon"] * A["pylon_fair_t"]),
                            propeller=D.LIFT_PROPS[int(s(o, "lprop_idx"))]["id"],
                            motor=dict(name=f"{lmot['id']}: {lmot['name']}", mass_kg=lmot["mass_kg"], continuous_power_kw=lmot["cont_kw"],
                                       peak_power_kw=lmot["peak_kw"], max_torque_nm=lmot["torque_nm"]),
                            inverter=lmot["inverter"], spin_pattern=[int(v) for v in spin]),
        "pusher": dict(layout=("twin_boom_tail" if b["lay"]["twin"] else "tail_cone"), count=(2 if b["lay"]["twin"] else 1),
                       diameter_m=R3(Dp), blades=int(x.get("pnb", 3)), blade_chord_m=0.12, rpm_cruise=R3(rpm_p), eta_cruise=R4(s(o, "eta_p")),
                       propeller=D.PUSHER_PROPS[int(s(o, "pprop_idx"))]["id"],
                       motor=dict(name=f"{pmot['id']}: {pmot['name']}", mass_kg=pmot["mass_kg"], continuous_power_kw=pmot["cont_kw"],
                                  peak_power_kw=pmot["peak_kw"], max_torque_nm=pmot["torque_nm"])),
        "wing": dict(span_m=R4(span), area_m2=R4(S), mac_m=R4(chord), thickness_ratio=R4(af["t_c"]), max_thickness_x_c=R4(af["x_t_c"]),
                     sweep_deg=0.0, taper=1.0, cl_max=R4(s(o, "CLmax")), oswald=R4(s(o, "oswald")), airfoil=b["afname"],
                     flaps=bool(int(x["flap"])), removable_for_transport=True),
        "fuselage": dict(length_m=fus["L"], max_width_m=fus["w"], max_height_m=R4(fus_h), wetted_area_m2=R3(swet_geo),
                         tail_arm_m=R4(s(o, "l_t"))),
        "booms": dict(count=2, length_m=R4(s(o, "L_boom")), diameter_m=A["boom_od"], rotor_arms_m=rot_arms),
        "tail": dict(horizontal_area_m2=R4(S_h), vertical_area_m2=R4(S_v), vertical_count=2, mac_m=R4(c_h), thickness_ratio=A["tail_tc"],
                     horizontal_aspect_ratio=R4(s(o, "ARh")), vertical_aspect_ratio=A["ARv"]),
        "landing_gear": dict(type="skid", length_m=0.5, frontal_area_m2=0.101, drag_area_m2=R4(float(np.asarray(o["dq"]["landing_gear"]).ravel()[0]))),
        "drag": dict(cd0=R4(s(o, "CD0")), drag_area_m2=R4(s(o, "dq_total")),
                     extra_items_m2=dict(cooling_inlets=0.01),
                     breakdown_m2={k: R4(float(np.asarray(v).ravel()[0])) for k, v in o["dq"].items()}),
        "battery": dict(energy_nominal_kwh=R3(E_nom), series=int(s(o, "Ns")), parallel=int(s(o, "Np_pack") * int(x["npk"])),
                        parallel_per_pack=int(s(o, "Np_pack")), independent_packs=int(x["npk"]),
                        voltage_nominal_v=R3(s(o, "V_bus")),
                        architecture="each pack: own Orion BMS 2, 2 EV200 contactors and a fuse, on a split HV bus with a normally-closed "
                                     "bus-tie contactor; a failed pack is isolated and the remaining pack(s) feed all motors",
                        cell=dict(name=cell["id"], energy_wh=cell["energy_wh"], mass_kg=cell["mass_kg"], capacity_ah=cell["capacity_ah"],
                                  v_nom=cell["v_nom"], max_continuous_discharge_a=cell["i_cont_screen"], max_peak_discharge_a=cell["i_peak"],
                                  dcir_ohm=cell["dcir_ohm"], price_usd=cell["price_usd"]),
                        pack_overhead_fraction=None, pack_mass_model=dict(per_cell_kg=A["pack_per_cell_kg"], per_pack_kg=A["pack_fixed_kg"])),
        "efficiencies": dict(motor=A["eta_m"], inverter=A["eta_inv"], wiring=A["eta_w"],
                             battery_cruise=R4(s(o, "eta_b_cruise")), battery_hover=R4(s(o, "eta_b_hover"))),
        "aux_power_kw": A["aux_kw"],
        "mission": dict(range_km=cfg["range_km"], cruise_speed_kmh=round(V * 3.6, 1), hover_takeoff_s=A["t_hover_to"],
                        hover_landing_s=A["t_hover_ld"], transition_each_s=A["t_tr"], transitions=2, vertical_climb_m=A["h_vclimb"],
                        transition_altitude_m=A["transition_alt"]),
        "cabin": dict(seats=2, seating=cfg.get("seating", "tandem")),
        "systems": dict(avionics_uninstalled_kg=D.AVIONICS_UNINSTALLED_KG, hv_cable_length_m=R3(n * 2 * (np.mean(np.abs(np.asarray(o["xr"])[0])) + b_y + 1.5) + 6)),
        "structure": dict(limit_load_factor_positive=3.8, limit_load_factor_negative=-1.5, landing_load_factor=3.0,
                          dive_speed_ms=R3(1.4 * V * math.sqrt(cr["rho"] / sl["rho"])),
                          dive_speed_eas_ms=R3(1.4 * V * math.sqrt(cr["rho"] / sl["rho"])), dive_speed_tas_ms=R3(1.4 * V),
                          cruise_speed_eas_ms=R3(V * math.sqrt(cr["rho"] / sl["rho"])),
                          note="V_D = 1.4 V_C. dive_speed_ms is EAS (use with sea-level density for loads), the same value as "
                               "geometry.aero.VD_ms; dive_speed_tas_ms is the true speed at the cruise condition (500 m ISA+15)"),
        "limits": dict(footprint_max_m=A["L_max"]),
        "cost": dict(units_produced_5yr=A["N_units"], composite_fraction=A["f_comp"], f_cert=A["f_cert"],
                     labour_rates_usd_h=dict(engineering=95, tooling=65, manufacturing=55),
                     cots_propulsion_systems_usd=R3(cost_total - cost["airframe_materials_consumables"] - cost["outsourced_services"]
                                                    - cost["labour"] - cost["tooling_amortised"]),
                     method="iteration 3: bottom-up (sizing/cost.py): COTS from the catalog + CAD-part materials, consumables, "
                            "outsourced services, labour hours x rate x 85 % learning (N units) + tooling materials / N; "
                            "Eastlake recurring airframe given for reference only",
                     eastlake_recurring_reference_usd=round(s(o, "eastlake_recurring")),
                     labour_hours_prototype=round(s(o, "labour_hours_prototype")), tooling_hours=round(s(o, "tooling_hours")),
                     labour_rate_usd_h=A["labour_rate"], learning_factor_N=round(s(o, "learning"), 3),
                     prototype_out_of_pocket_usd=round(s(o, "prototype_cash")),
                     breakdown_usd={k: round(v) for k, v in cost.items()},
                     complexity=dict(distinct_part_types=int(s(o, "n_types")), propulsion_lru=int(s(o, "n_lru")),
                                     penalty_usd=round(s(o, "penalty")), objective_usd=round(s(o, "objective")))),
        "results": dict(
            disk_loading_N_m2=R3(s(o, "disk_loading")),
            hover_shaft_power_per_motor_kw=R3(s(o, "P_mot_site")),
            hover_electrical_power_kw=R3(hov_site),
            hover_electrical_power_ceiling_kw=R3(s(o, "P_hover_ceil")),
            rotor_out_max_shaft_power_kw=R3(case_mtow["oei_shaft_power_kw_1000m"]),
            rotor_out_max_torque_nm=R3(case_mtow["oei_torque_Nm_1000m"]),
            cruise_drag_N=R3(s(o, "D_cruise")), cruise_LD=R4(s(o, "LD")), cruise_electrical_power_kw=R3(s(o, "P_cruise")),
            mission_energy_kwh=R3(s(o, "E_cells")), range_km=R3(rng), stall_speed_ms=R3(s(o, "Vs_sl")),
            tip_mach_hover=R4(vtip / site["a"]), c_rate_hover=R4(s(o, "C_hover")), cost_usd=round(cost_total),
            mtow_kg=R3(mtow), static_margin_mtow=case_mtow["static_margin"],
            static_margin_range=[min(c["static_margin"] for c in b["cases"].values()), max(c["static_margin"] for c in b["cases"].values())],
            reserve_energy_kwh=R3(E_nom * A["f_eol"] * A["f_res"]), transition_speed_ms=R3(1.2 * s(o, "Vs_hot")),
            gust_load_factor_vc=R4(s(o, "n_gust")), climb_rate_ms=R4(s(o, "roc")),
            rotor_out_flare_load_factor_g=A["oei_flare_g"],
            rotor_out_flare_load_factor_required_g=A0["oei_flare_g"],
            rotor_out_flare_shaft_power_kw=R3(case_mtow["oei_flare_shaft_power_kw_500m"]),
            rotor_out_flare_torque_nm=R3(case_mtow["oei_flare_torque_Nm_500m"]),
            note="rotor-out values: linear programme, worst failed rotor, 1000 m ISA+15, incl. 10 % control margin (WP M evaluates "
                 "at 500 m); flare: rotor_out_flare_load_factor_g with one motor out at 500 m ISA+15 (required 1.1 g from iteration 3.2, was 1.2 g; see sizing/README.md)"),
        "loading_cases": b["cases"],
        "assumptions_for_checker": dict(
            tech_factor_structure=A["tf_struct"],
            accessory_factor=R4(acc_factor),
            lv_electrical_kg=D.LV_ELECTRICAL_KG,
            _reasons={
                "tech_factor_structure": "foam-core / wet-laid carbon sandwich structure; Raymer table 15.4 composite factor 0.85 "
                                         "(the WP M 'light' scenario uses the same value)",
                "accessory_factor": "inverters from the catalog (MGM HBCi, 1 per motor), HV harness from [M14] physics, cooling "
                                    "build-up; replaces the NASA 1.63 technology factor",
                "lv_electrical_kg": "COTS build-up (2 x 600 W DC-DC, 24 V LiFePO4, LV harness, panel, lights) instead of the "
                                    "Raymer GA electrical-system regression",
            }),
    }
    (out_dir / f"selected_design{tag}.json").write_text(json.dumps(sd, indent=1))
    return dict(geometry=geo, design=sd)
