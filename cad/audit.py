"""Mass / CG audit, clearance checks and interference scan of the E8-200 CAD (called by cad/build.py).

Writes validation/cad/mass_cg_audit.{md,json}, clearance_checks.{md,json}, interference.{md,json}.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import trimesh

from e8cad import booms as B, fuselage as FU, gear as GR, tail as T, wing as W
from e8cad.config import (BATS, BOOM_OD, BOOM_Y, BOOM_Z, CHUTE, DETAIL, G, PUSH, ROOT, ROTORS, S, SEATS, WING, mm, oml,
                          oml_half_width, oml_z_range, wing_to_global)

OUT = ROOT / "validation" / "cad"

DESIGN_CAT = [  # (category, predicate on the geometry.json mass_items name)
    ("wing", lambda n: n == "wing structure"),
    ("boom tubes (+ wing saddles)", lambda n: n.startswith("boom_")),
    ("rotor stations (motors, rotors, inverters, pylons, clamps)", lambda n: n.startswith("rotor_")),
    ("tail", lambda n: n == "tail structure"),
    ("landing gear", lambda n: n.startswith("skid_") or n == "landing gear"),
    ("fuselage", lambda n: n == "fuselage structure"),
    ("pusher unit (motor, propeller, inverter, mount)", lambda n: n.startswith("pusher unit") or n.startswith("pusher inverter")),
    ("seats + furnishings", lambda n: n.startswith("seat_") or n == "furnishings"),
    ("avionics", lambda n: n.startswith("avionics")),
    ("LV electrical", lambda n: n == "LV electrical"),
    ("flight controls", lambda n: n.startswith("flight controls") or n.startswith("aileron actuator") or n.startswith("flap actuators") or n == "tail actuators"),
    ("parachute", lambda n: n.startswith("parachute")),
    ("HV harness", lambda n: n.startswith("HV")),
    ("cooling", lambda n: n.startswith("cooling")),
    ("growth allowance", lambda n: n == "growth allowance"),
    ("battery", lambda n: n.startswith("battery_")),
    ("payload (occupants)", lambda n: n.startswith("occupant_")),
]
STATION_IDS = {"PY-C", "PY-TUBE", "PY-HEAD", "MP", "MP-ISO", "NAC", "INV-L", "INV-POD"}


def cad_category(pid, group):
    if group in ("lift_motors", "lift_rotors") or pid in STATION_IDS:
        return DESIGN_CAT[2][0]
    if pid.startswith("BM-") or pid in ("BC-W", "BC-WR"):
        return DESIGN_CAT[1][0]
    if group in ("pusher_motor", "pusher_propeller") or pid in ("INV-P", "INV-PB"):
        return DESIGN_CAT[6][0]
    m = {"wing": "wing", "tail": "tail", "landing_gear": "landing gear", "fuselage": "fuselage", "seats": "seats + furnishings",
         "avionics": "avionics", "lv_electrical": "LV electrical", "flight_controls": "flight controls", "parachute": "parachute",
         "hv_harness": "HV harness", "cooling": "cooling", "battery": "battery", "payload": "payload (occupants)",
         "booms": DESIGN_CAT[1][0], "inverters": DESIGN_CAT[2][0], "rotor_pylons_mounts": DESIGN_CAT[2][0]}
    return m[group]


def _wing_curves():
    i0 = int(np.argmin(W.FOIL[:, 0]))
    up = np.array([wing_to_global(x, z)[[0, 2]] for x, z in W.FOIL[: i0 + 1][::-1]])
    lo = np.array([wing_to_global(x, z)[[0, 2]] for x, z in W.FOIL[i0:]])
    up = up[np.argsort(up[:, 0])]
    lo = lo[np.argsort(lo[:, 0])]
    return up, lo


UP, LO = _wing_curves()


def z_up(x):
    return float(np.interp(x, UP[:, 0], UP[:, 1], left=np.nan, right=np.nan))


def z_lo(x):
    return float(np.interp(x, LO[:, 0], LO[:, 1], left=np.nan, right=np.nan))


def status(ok, warn=False):
    return "PASS" if ok else ("WARN" if warn else "FAIL")


# ============================================================================ mass / CG
def mass_audit(parts, mp, inst_all):
    pmap = {p.pid: p for p in parts}
    from build import mass_props
    cad = {}
    for pid, k, M in inst_all:
        p = pmap[pid]
        m, c = mass_props(p)
        cg = (M @ np.append(c, 1))[:3] / 1000.0
        cat = cad_category(pid, p.mass_group)
        d = cad.setdefault(cat, {"kg": 0.0, "mx": np.zeros(3)})
        d["kg"] += m
        d["mx"] += m * cg
    des = {}
    for it in G["mass_items"]:
        for cat, f in DESIGN_CAT:
            if f(it["name"]):
                d = des.setdefault(cat, {"kg": 0.0, "mx": np.zeros(3)})
                d["kg"] += it["kg"]
                d["mx"] += it["kg"] * np.array([it["x"], it["y"], it["z"]])
                break
        else:
            raise KeyError(it["name"])
    # growth allowance is not modelled: carried at the design point in the CAD total
    cad["growth allowance"] = {"kg": des["growth allowance"]["kg"], "mx": des["growth allowance"]["mx"].copy(), "allowance": True}
    rows = []
    for cat, _ in DESIGN_CAT:
        d, c = des.get(cat), cad.get(cat, {"kg": 0.0, "mx": np.zeros(3)})
        dcg = d["mx"] / d["kg"]
        ccg = c["mx"] / c["kg"] if c["kg"] > 0 else np.full(3, np.nan)
        rows.append(dict(category=cat, design_kg=round(d["kg"], 3), cad_kg=round(c["kg"], 3), diff_kg=round(c["kg"] - d["kg"], 3),
                         diff_pct=round(100 * (c["kg"] - d["kg"]) / d["kg"], 1),
                         design_cg_m=np.round(dcg, 4).tolist(), cad_cg_m=np.round(ccg, 4).tolist(),
                         dx_m=round(float(ccg[0] - dcg[0]), 4), dz_m=round(float(ccg[2] - dcg[2]), 4),
                         note="not modelled: design allowance carried at the design point" if c.get("allowance") else ""))

    def tot(src, cats):
        m = sum(src[c]["kg"] for c in cats if c in src)
        mx = sum(src[c]["mx"] for c in cats if c in src)
        return m, mx / m
    allc = [c for c, _ in DESIGN_CAT]
    empty_c = [c for c in allc if c not in ("battery", "payload (occupants)")]
    res = {}
    for name, cats in (("empty (incl. growth)", empty_c), ("MTOW (pilot + passenger)", allc)):
        dm, dcg = tot(des, cats)
        cm, ccg = tot(cad, cats)
        res[name] = dict(design_kg=round(dm, 2), cad_kg=round(cm, 2), diff_kg=round(cm - dm, 2), diff_pct=round(100 * (cm - dm) / dm, 2),
                         design_cg_m=np.round(dcg, 4).tolist(), cad_cg_m=np.round(ccg, 4).tolist(),
                         dx_m=round(float(ccg[0] - dcg[0]), 4), dz_m=round(float(ccg[2] - dcg[2]), 4))
    # pilot-only case (passenger removed)
    occ2 = max(SEATS, key=lambda s: s["x"])
    cm, ccg = tot(cad, allc)
    m2 = cm - occ2["occupant_kg"]
    cg2 = (ccg * cm - occ2["occupant_kg"] * np.array([occ2["x"], occ2["y"], occ2["z"]])) / m2
    d2 = S["loading_cases"]["pilot only"]
    res["pilot only"] = dict(design_kg=d2["mass_kg"], cad_kg=round(m2, 2), diff_kg=round(m2 - d2["mass_kg"], 2),
                             diff_pct=round(100 * (m2 - d2["mass_kg"]) / d2["mass_kg"], 2),
                             design_cg_m=d2["cg_m"], cad_cg_m=np.round(cg2, 4).tolist(),
                             dx_m=round(float(cg2[0] - d2["cg_m"][0]), 4), dz_m=round(float(cg2[2] - d2["cg_m"][2]), 4))
    mac = WING["chord"] / 1000
    sm_shift = -res["MTOW (pilot + passenger)"]["dx_m"] / mac
    # breakdown comparison (selected_design keys)
    bd = []
    by = mp["by_group"]
    for k, v in S["mass_kg"]["breakdown"].items():
        if k == "growth":
            continue
        cv = by.get(k, {}).get("kg", 0.0)
        bd.append(dict(key=k, design_kg=v, cad_kg=round(cv, 3), diff_kg=round(cv - v, 3), diff_pct=round(100 * (cv - v) / v, 1)))
    # WP F assumption checks: machined fittings and cabin primary members
    fit, cab = {}, {}
    for pid, k, M in inst_all:
        p = pmap[pid]
        m, _ = mass_props(p)
        if p.process == "CNC" and p.mass_group != "battery" and any(t in p.material for t in ("al6061", "al7075", "steel")):
            fit[pid] = fit.get(pid, 0.0) + m
        if p.group == "Cabin structure":
            cab[pid] = cab.get(pid, 0.0) + m
    wpf = dict(machined_fittings=dict(cad_kg=round(sum(fit.values()), 2), fea_assumed_kg=48.0,
                                      parts={k: round(v, 2) for k, v in sorted(fit.items(), key=lambda t: -t[1])},
                                      note="all machined aluminium/steel parts outside the battery packs (pack cold plates and brackets are in the pack mass)"),
               cabin_primary_members=dict(cad_kg=round(sum(cab.values()), 2), fea_assumed_kg=43.0,
                                          parts={k: round(v, 2) for k, v in sorted(cab.items(), key=lambda t: -t[1])},
                                          note="sandwich floor, side panels, bulkheads BH-0..BH-7, aft keel, nose crush block; shell, canopy and fittings excluded"))
    # weight reductions requested by design/mass_calibration.json, as built
    cal = json.loads((ROOT / "design" / "mass_calibration.json").read_text()) if (ROOT / "design" / "mass_calibration.json").exists() else {}
    targ = {}
    for k, v in cal.get("reductions", {}).items():
        key = "W-CORE (all)" if k.startswith("W-CORE") else k
        t = targ.setdefault(key, {"target_kg": 0.0, "target_fraction": v.get("fraction")})
        t["target_kg"] += v["kg_removed"]
    built = {}
    for p in parts:
        red = p.settings.get("_reduction")
        if red is None or p.tooling:
            continue
        m, _ = mass_props(p)
        key = "W-CORE (all)" if p.pid.startswith("W-CORE") else p.pid
        b = built.setdefault(key, {"cad_kg": 0.0, "removed_kg": 0.0})
        b["cad_kg"] += m * len(p.placements)
        b["removed_kg"] += m * len(p.placements) * red / max(1 - red, 1e-6)
    red_rows = []
    for key in sorted(set(targ) | set(built)):
        t, b = targ.get(key, {}), built.get(key, {})
        frac = b["removed_kg"] / (b["removed_kg"] + b["cad_kg"]) if b else None
        red_rows.append(dict(part=key, target_fraction=t.get("target_fraction"), target_kg_iteration1=round(t.get("target_kg", 0.0), 2),
                             built_fraction=None if frac is None else round(frac, 3),
                             removed_kg_as_built=None if not b else round(b["removed_kg"], 2), cad_kg_as_built=None if not b else round(b["cad_kg"], 2)))
    after = cal.get("group_mass_after_reductions_kg", {})
    by = mp["by_group"]
    cal_rows = [dict(key=k, calibration_kg=v, cad_kg=round(by.get(k, {}).get("kg", 0.0), 2)) for k, v in after.items()]
    return dict(reductions=red_rows, calibration_groups=cal_rows, wpf_checks=wpf, categories=rows, totals=res, static_margin_shift=round(sm_shift, 4),
                static_margin_design=S["results"]["static_margin_mtow"],
                static_margin_cad=round(S["results"]["static_margin_mtow"] + sm_shift, 4), breakdown=bd)


# ============================================================================ clearances
def clearances(parts, mp, meshes, inst_all):
    chk = []

    def add(cid, name, value, ref, unit, ok, note="", warn=False):
        chk.append(dict(id=cid, check=name, value=None if value is None else round(float(value), 4), reference=ref, unit=unit,
                        status=status(ok, warn), note=note))
    R = mm(ROTORS[0]["diameter_m"]) / 2
    hubs = np.array([[mm(v) for v in r["hub"]] for r in ROTORS])
    ch = mm(ROTORS[0]["blade_chord"])
    z_blade = hubs[0, 2] - 0.5 * ch * math.sin(math.radians(ROTORS[0]["blade_pitch_deg"])) - 0.06 * ch
    # rotor-rotor
    gaps = []
    for i in range(len(hubs)):
        for j in range(i + 1, len(hubs)):
            gaps.append((np.linalg.norm(hubs[i, :2] - hubs[j, :2]) - 2 * R, ROTORS[i]["id"], ROTORS[j]["id"]))
    g = min(gaps)
    add("C1", f"rotor tip-to-tip plan clearance, minimum ({g[1]}-{g[2]})", g[0], 100.0, "mm", g[0] >= 100.0 - 0.5,
        "same reference as validation/sizing A6a (0.1 m)")
    # rotors vs wing (plan overlap -> vertical gap above the upper surface)
    worst = None
    for r, h in zip(ROTORS, hubs):
        for rr in np.linspace(0, R, 30):
            for th in np.linspace(0, 2 * np.pi, 72, endpoint=False):
                x, y = h[0] + rr * math.cos(th), h[1] + rr * math.sin(th)
                if abs(y) <= W.HALF and UP[0, 0] <= x <= UP[-1, 0]:
                    gap = z_blade - z_up(x)
                    if worst is None or gap < worst[0]:
                        worst = (gap, r["id"], x, y)
    add("C2", f"rotor blade plane above the wing upper surface where the disc overlaps the wing ({worst[1]})", worst[0], 150.0, "mm",
        worst[0] >= 150.0, "reference as validation/sizing A6c (0.15 m)")
    front = [h for h in hubs if h[0] < WING["xle"]]
    pg = min(WING["xle"] - (h[0] + R) for h in front)
    add("C3", "front rotor tips to the wing leading edge, plan gap", pg, 0.0, "mm", pg > 0, "no plan overlap ahead of the wing")
    # rotors vs fuselage
    pf = min(abs(h[1]) - R - max(oml(x)[0] / 2 for x in np.linspace(0, FU.FUS_L if hasattr(FU, 'FUS_L') else 4700, 100)) for h in hubs)
    add("C4", "rotor tip to fuselage side, plan gap", pf, 150.0, "mm", pf >= 150.0 - 0.5, "reference as validation/sizing A6b")
    top = max(oml(x)[2] + oml(x)[1] / 2 for x in np.linspace(0, 4700, 200))
    add("C5", "rotor blade plane above the fuselage / canopy top", z_blade - top, 0.0, "mm", z_blade > top)
    # rotors vs tail
    ht_le = T.HX
    rear = [h for h in hubs if h[0] > 4000]
    ptail = min(ht_le - (h[0] + R) for h in rear)
    ht_top = T.HZ + 0.06 * T.HC
    add("C6", "rear rotor tips to the H-tail leading edge, plan gap", ptail, 0.0, "mm", ptail > 0, warn=True,
        note=f"rear tip path {'overlaps the H-tail by ' + format(-ptail, '.0f') + ' mm' if ptail < 0 else 'is ' + format(ptail, '.0f') + ' mm ahead of the H-tail'} "
             f"in plan; blade plane {z_blade - ht_top:.0f} mm above the H-tail, so no contact, but the rear-rotor wake impinges on the tail")
    hw_top = BOOM_Z + max(B.NAC_TOP, B.MOT_BOT) if B.P3["R"] > mm(ROTORS[0]["hub_diameter"]) / 2 else BOOM_Z + B.NAC_TOP
    add("C7", "blade plane above the station hardware outside the hub radius (nacelle / motor plate)", z_blade - hw_top, 50.0, "mm",
        z_blade - hw_top >= 50, note=f"motor (r {B.MOT_D/2:.0f} mm) and motor plate (r {B.P3['R']:.0f} mm) lie inside the hub radius "
                                     f"{mm(ROTORS[0]['hub_diameter'])/2:.0f} mm")
    # rotor plane vs occupants
    occ_top = max(mm(s["z"]) + 689.0 for s in SEATS)
    occ_meshes = []
    pmap = {p.pid: p for p in parts}
    for pid, k, M in inst_all:
        if pid == "OCC":
            m = meshes[pid].copy()
            m.apply_transform(M)
            occ_meshes.append(m)
    occ_pts = np.vstack([m.vertices for m in occ_meshes])
    occ_top = occ_pts[:, 2].max()
    hub_bot = hubs[0, 2] - mm(ROTORS[0]["hub_height"]) / 2
    add("C8", "rotor plane (blade) above the highest occupant point (no blade in the occupant plane)", z_blade - occ_top, 0.0, "mm",
        z_blade > occ_top, "requirements.yaml safety.occupant")
    # blade-release fan: smallest depression angle from any blade-tip point to any occupant point
    best = 90.0
    for h in hubs:
        for th in np.linspace(0, 2 * np.pi, 180, endpoint=False):
            tip = np.array([h[0] + R * math.cos(th), h[1] + R * math.sin(th), z_blade])
            d = occ_pts - tip
            hor = np.hypot(d[:, 0], d[:, 1])
            ang = np.degrees(np.arctan2(-d[:, 2], hor))
            best = min(best, float(ang.min()))
    add("C9", "blade-release fan: minimum depression angle from the tip path to an occupant", best, 5.0, "deg", best >= 5.0,
        "reference: +/-5 deg rotor-burst fan (FAA AC 20-128A practice for rotating parts); occupants outside the fan")
    # pushers (twin boom-tail units, or the legacy single fuselage pusher)
    PUS = G.get("pushers") or [PUSH]
    x_piv = mm(GR.SK["x_end"])
    fin_te = T.VX + T.VC
    ht_te = T.HX + T.HC
    u = PUS[0]
    xp, zp, Rp = mm(u["x"]), mm(u["z"]), mm(u["diameter"]) / 2
    add("C10", "pusher tip ground clearance (level, on skids)", zp - Rp, 200.0, "mm", zp - Rp >= 200.0, "reference as validation/sizing A6e")
    th_p = math.degrees(math.atan2(zp - Rp, xp - x_piv))
    th_f = math.degrees(math.atan2(T.VZ0, fin_te - x_piv))
    th_b = math.degrees(math.atan2(BOOM_Z - BOOM_OD / 2, mm(G["booms"][0]["x_end"]) - x_piv))
    first = min((th_p, "pusher tip"), (th_f, "fin trailing edge"), (th_b, "boom end"))
    add("C11", "tail-down rotation about the skid aft end to the first ground strike", first[0], 10.0, "deg", first[0] >= 10.0,
        f"first strike: {first[1]} (pusher tip {th_p:.1f} deg, fin {th_f:.1f} deg, boom end {th_b:.1f} deg); reference 10 deg tail-low touchdown")
    if xp > ht_te:                                   # props behind the tail
        add("C12", "pusher disc behind the H-tail trailing edge (axial gap)", xp - ht_te, 200.0, "mm", xp - ht_te >= 200.0,
            note="props run in the H-tail wake (noise, blade loads): open item in the design")
        add("C12b", "pusher disc behind the fin trailing edge (axial gap)", xp - fin_te, 200.0, "mm", xp - fin_te >= 200.0)
    else:
        add("C12", "pusher disc to H-tail leading edge", T.HX - xp, 300.0, "mm", T.HX - xp >= 300.0, "reference as validation/sizing A6h")
    if len(PUS) > 1:
        ys = sorted(mm(q["y"]) for q in PUS)
        gap = (ys[-1] - ys[0]) - 2 * Rp
        add("C13", "pusher tip-to-tip gap (twin props)", gap, 300.0, "mm", gap >= 300.0)
    else:
        add("C13", "pusher tip to boom surface (radial)", BOOM_Y - BOOM_OD / 2 - Rp, 100.0, "mm", BOOM_Y - BOOM_OD / 2 - Rp >= 100.0)
    # pusher discs vs lift-rotor blade plane where they overlap in plan
    best = None
    for q in PUS:
        xq, yq, zq = mm(q["x"]), mm(q["y"]), mm(q["z"])
        for h in hubs:
            dx = xq - h[0]
            if abs(dx) < R:
                half = math.sqrt(R ** 2 - dx ** 2)
                ylo, yhi = h[1] - half, h[1] + half
                if ylo < yq + Rp and yhi > yq - Rp:
                    best = (z_blade - (zq + Rp)) if best is None else min(best, z_blade - (zq + Rp))
    if best is None:
        dmin = min(abs(mm(q["x"]) - h[0]) - R for q in PUS for h in hubs if abs(h[1] - mm(q["y"])) < Rp + R)
        add("C14", "pusher disc to the nearest lift-rotor tip path (axial, no plan overlap)", dmin, 100.0, "mm", dmin >= 100.0)
    else:
        add("C14", "pusher disc to lift-rotor blade plane where they overlap in plan", best, 100.0, "mm", best >= 100)
    if G.get("pushers"):
        eng = mm(u["motor"]["x_face"]) - mm(u["mount"]["x_from"])
        add("C15", "boom-end fitting engagement in the boom", eng, 150.0, "mm", eng >= 150.0 - 0.5)
    else:
        w_t = oml(min(xp - 60 - DETAIL["pusher_motor_len"], FU.FUS_L - 1))
        mr = 270.2 / 2
        add("C15", "pusher motor radius vs tail-cone OML half-width at the motor face", w_t[0] / 2 - mr, 0.0, "mm", w_t[0] / 2 - mr >= 0)
    # canopy and egress
    p_open = (FU.DOOR_PILOT[1] - FU.DOOR_PILOT[0])
    add("C16", "pilot canopy opening length (x)", p_open, 660.0, "mm", p_open >= 660.0, "14 CFR 23.807 exit 19 x 26 in (483 x 660 mm)")
    door_w = FU.DOOR_PAX[1] - FU.DOOR_PAX[0]
    xm = (FU.DOOR_PAX[0] + FU.DOOR_PAX[1]) / 2
    door_h = z_lo(xm) - FU.SILL_Z
    add("C17", "passenger door clear width between the wing-spar posts", door_w, 483.0, "mm", door_w >= 483.0,
        "posts at the main and rear spar stations carry the wing fittings")
    add("C18", "passenger door clear height (sill to wing lower surface)", door_h, 660.0, "mm", door_h >= 660.0)
    # canopy swing: farthest canopy point from the right-sill hinge line vs boom and rotor disc edge
    yh = oml_half_width((FU.X_CAB0 + FU.X_POST_M) / 2, FU.SILL_Z)
    cv = meshes["CAN-F"].vertices
    rc = float(np.max(np.hypot(cv[:, 1] - yh, cv[:, 2] - FU.SILL_Z)))
    d_boom = math.hypot(BOOM_Y - yh, BOOM_Z - FU.SILL_Z) - BOOM_OD / 2
    d_disc = math.hypot(BOOM_Y - R - yh, z_blade - FU.SILL_Z)
    add("C19", "front canopy swing radius vs boom (canopy fully open)", d_boom - rc, 50.0, "mm", d_boom - rc >= 50.0,
        f"canopy radius {rc:.0f} mm about the right sill hinge")
    add("C20", "front canopy swing radius vs lift-rotor disc edge", d_disc - rc, 0.0, "mm", d_disc - rc >= 0.0,
        "opening the canopy with rotors turning is prohibited regardless")
    add("C21", "boom underside height above ground on the egress path", BOOM_Z - BOOM_OD / 2, 1900.0, "mm",
        BOOM_Z - BOOM_OD / 2 >= 1900.0, warn=True,
        note=f"occupants leave sideways under the booms (y = +/-{BOOM_Y/1000:.3f} m); P95 standing height ~1.85 m -> head-strike hazard, pad/mark the boom")
    # head clearance
    for s in SEATS:
        srp = np.array([mm(s["x"]) + DETAIL["seat_srp_back"], 0, mm(s["seat_reference_point_z"])])
        rec = math.radians(15)
        ub = np.array([math.sin(rec), 0, math.cos(rec)])
        fn = np.array([-math.cos(rec), 0, math.sin(rec)])
        hc = srp + ub * (DETAIL["sitting_height_p95"] - 110) + fn * 110
        xs = np.linspace(hc[0] - 110, hc[0] + 110, 23)
        ceil = []
        for x in xs:
            zt = oml(x)[2] + oml(x)[1] / 2 - DETAIL["canopy_t"]
            zl = z_lo(x)
            ceil.append(min(zt, zl) if not np.isnan(zl) else zt)
        head_z = np.array([hc[2] + math.sqrt(max(110 ** 2 - (x - hc[0]) ** 2, 0)) for x in xs])
        cl = float(np.min(np.array(ceil) - head_z))
        what = "wing lower surface" if not np.isnan(z_lo(hc[0])) and z_lo(hc[0]) < oml(hc[0])[2] + oml(hc[0])[1] / 2 else "canopy"
        add(f"C22{'ab'[SEATS.index(s)]}", f"head clearance, {s['name']} (P95 sitting height {DETAIL['sitting_height_p95']:.0f} mm) to the {what}",
            cl, 50.0, "mm", cl >= 50.0)
    # seat stroke
    stroke = mm(SEATS[0]["seat_reference_point_z"]) - 4 - (FU.FLOOR_Z + FU.PT + 25)
    add("C23", "seat energy-absorber stroke available under the pan", stroke, 150.0, "mm", stroke >= 150.0, warn=True,
        note="vertical crash stroke under the seat is limited by the SRP height above the floor; the packs under the floor give no belly crush zone")
    # tip-over
    cg = np.array(mp["cg_mm"])
    ysk = mm(GR.SK["y"])
    lat = math.degrees(math.atan2(ysk, cg[2]))
    fwd = math.degrees(math.atan2(cg[0] - mm(GR.SK["x_start"]), cg[2]))
    aft = math.degrees(math.atan2(mm(GR.SK["x_end"]) - cg[0], cg[2]))
    add("C24", "static lateral tip-over angle (CAD CG, MTOW)", lat, 25.0, "deg", lat >= 25.0, "reference 25 deg")
    add("C25", "static forward tip-over angle (CAD CG, MTOW)", fwd, 25.0, "deg", fwd >= 25.0)
    add("C26", "static aft tip-over angle (CAD CG, MTOW)", aft, 25.0, "deg", aft >= 25.0)
    # boom vs wing lower surface
    pen = []
    for x in np.linspace(WING["xle"] + 5, WING["xle"] + WING["chord"] - 5, 200):
        pen.append((BOOM_Z + BOOM_OD / 2) - z_lo(x))
    xs_m = wing_to_global(W.WING["spars"][0]["x_c"] * W.C, 0)[0]
    xs_r = wing_to_global(W.WING["spars"][1]["x_c"] * W.C, 0)[0]
    add("C27", "boom crown above the wing lower surface (penetration, max over the chord)", max(pen), 0.0, "mm", max(pen) <= 0,
        note=f"at the main spar {BOOM_Z + BOOM_OD/2 - z_lo(xs_m):.0f} mm, at the rear spar {BOOM_Z + BOOM_OD/2 - z_lo(xs_r):.0f} mm"
             + (": the boom passes through the lower spar caps" if max(pen) > 0 else " (negative = below the wing)"))
    for nm, xg in (("main", xs_m), ("rear", xs_r)):
        pp = BOOM_Z + B.PAD_TOP - z_lo(xg)
        add(f"C27{'ab'[nm == 'rear']}", f"boom-wing saddle pad top (FEA P2) above the wing lower surface, {nm} spar", pp, 0.0, "mm", pp <= 0,
            note="pad sits inside the wing" if pp > 0 else f"gap {-pp:.0f} mm to the lower skin, filled by a bonded hard-point shim")
    # battery fit
    b = BATS[0]
    worst = 0.0
    for bb in BATS:
        for sx in (-1, 1):
            x = mm(bb["x"]) + sx * mm(bb["length"]) / 2
            for z in (mm(bb["z"]) - mm(bb["height"]) / 2, mm(bb["z"]) + mm(bb["height"]) / 2):
                worst = max(worst, mm(bb["width"]) / 2 - oml_half_width(x, z))
    add("C28", "battery box corner outside the fuselage OML (max lateral protrusion)", worst, 0.0, "mm", worst <= 0)
    # chute canister
    c = CHUTE["canister"]
    d = np.array(c["fire_direction"]) / np.linalg.norm(c["fire_direction"])
    topc = np.array([mm(c["x"]), 0, mm(c["z"])]) + d * mm(c["length"]) / 2
    ztop = topc[2] + mm(c["diameter"]) / 2 * abs(d[0])
    w_, h_, zc_ = oml(topc[0])
    add("C29", "parachute canister top above the fuselage OML", ztop - (zc_ + h_ / 2), 0.0, "mm", ztop <= zc_ + h_ / 2,
        "canister protrudes through the frangible hatch" if ztop > zc_ + h_ / 2 else "inside the OML under the frangible hatch")
    # root fittings vs OML
    xs = W.WING["spars"][0]["x_c"] * W.C
    lo = W.thickness_at(W.FOIL, xs)[0]
    pz = wing_to_global(xs, lo - 14 - 42)[2]
    hw = oml_half_width(wing_to_global(xs, lo)[0], pz)
    add("C30", "wing root fitting (y = root_fittings_y) outside the fuselage OML at its height", WING["root_y"] - hw, 0.0, "mm",
        WING["root_y"] - hw <= 0, note="must be inside the shoulder fairing of the OML")
    # tail areas
    ht_area = (T.HC) * 2 * T.Y_PANEL / 1e6
    add("C31", "H-tail exposed planform area (between the booms) vs design", ht_area, G["tail"]["area_h_m2"], "m2",
        ht_area >= 0.97 * G["tail"]["area_h_m2"], note="design value = exposed area between the boom surfaces")
    fin_area = T.VC * ((BOOM_Z - BOOM_OD / 2) - T.VZ0) / 1e6
    add("C32", "ventral fin exposed area (each) vs design", fin_area, G["tail"]["area_v_total_m2"] / 2, "m2",
        fin_area >= 0.97 * G["tail"]["area_v_total_m2"] / 2, note="design value = exposed area below the boom underside")
    lo_, hi_ = W.thickness_at(T.naca4(T.H_FOIL[4:], T.HC, 80), T.XSP - T.HX)
    room = (hi_ - lo_) - 2 * T.SKT - 2 * T.SP_R
    add("C33", f"H-tail spar ({2*T.SP_R:.0f} mm) inside the {T.H_FOIL.upper()} section at the spar", room, 0.0, "mm", room >= 0,
        note="clearance left for the core between the spar tube and the skins")
    return chk


# ============================================================================ interference scan
EXPECTED_CONTACT = [  # pairs that share a bonded / bolted / enveloping interface by design
    ("W-CORE", "W-SP"), ("W-RIB", "W-SP"), ("W-SKIN", "W-SP"), ("W-SKIN", "W-CORE"), ("W-SKIN", "W-RIB"),
    ("BAT-MOD", "BAT-CP"), ("BM-", "BM-"), ("ROT-", "MOT-L"), ("F-WRF", "W-FIT"), ("F-WRF", "F-CLV"), ("F-WRF", "W-PIN"),
    ("F-WRF", "CAN-"), ("F-WRF", "SH-"), ("CHUTE", "CH-RISER"), ("CH-ATT-R", "CH-RISER"), ("W-CHUTE-FIT", "CH-RISER"),
    ("INV-P", "HV-PUSH"), ("CAN-FRM", "SH-"), ("BH-", "SH-"), ("BH-", "HATCH"), ("FLOOR", "HV-"), ("CAN-HINGE", "CAN-"),
    ("CAN-LATCH", "CAN-"), ("PROP-P", "SPIN-P"), ("HARN", "SEAT-CUSH"), ("HA-FIT", "SEAT-CUSH"), ("SEAT-FIT", "SEAT-CUSH"),
    ("F-CLV", "CAN-FRM"), ("W-FIT", "W-PIN"), ("F-CLV", "W-PIN"), ("W-FIT-MS", "W-FIT-MP"), ("W-FIT-RS", "W-FIT-RP"),
    ("W-CHUTE-FIT", "W-CHUTE-ANG"), ("CH-ATT-R", "CH-ANG-R"), ("LG-DAMP", "LG-D"), ("PY-", "MP"), ("PY-TUBE", "PY-"),
    ("MP-ISO", "PY-HEAD"), ("MP-ISO", "MP"), ("W-FIT", "W-SP"), ("W-FIT", "W-RIB"), ("W-FIT", "W-SKIN"), ("W-CHUTE", "W-SKIN"),
    ("W-CHUTE", "W-SP"), ("LG-XT", "LG-SKCL"), ("LG-XT", "LG-DCL"), ("LG-XT", "LG-SADDLE"), ("LG-SKID", "LG-SKCL"),
    ("LG-SKID", "LG-SHOE"), ("BM-", "PY-C"), ("BM-", "BC-W"), ("BM-", "TL-CLAMP"), ("HT-SPAR", "TL-CLAMP"),
    ("VF-SPAR", "TL-CLAMP"), ("LG-DUP", "SH-"), ("LG-DUP", "SIDE"), ("HV-BOOM", "BM-"), ("COOL-LINE", "BM-"),
    ("BM-CAP", "BM-"), ("TL-HINGE", "HT"), ("TL-HINGE", "VF"), ("TL-HINGE", "ELEV"), ("TL-HINGE", "RUD"),
    ("W-HINGE", "W-AIL"), ("W-HINGE", "W-FLAP"), ("W-HINGE", "W-CORE"), ("W-HINGE", "W-FSPAR"), ("LG-SKID", "LG-XT"), ("HV-WING", "W-"),
    ("W-AIL-ACT", "W-CORE"), ("TL-ACT", "VF"), ("TL-ACT", "HT"), ("OCC", "SEAT"), ("OCC", "HARN"), ("OCC", "FURN"),
    ("LG-DAMP", "LG-XT"), ("BAT-VENT", "BAT-"), ("CAN-FRM", "SIDE"), ("F-CLV", "SH-"), ("FLOOR-DBL", "FLOOR"), ("SIDE-DBL", "SIDE"), ("CH-RISER", "W-"), ("LG-LEG", "LG-SKCL"), ("LG-LEG", "LG-DCL"), ("LG-LEG", "LG-LEGEND"), ("LG-LEGEND", "LG-SADDLE"),
    ("LG-PIN", "LG-"), ("LG-DAMP", "LG-LEG"), ("LG-SKID", "LG-LEG"), ("LG-FAIR", "LG-LEG"), ("W-SPM-S", "W-"), ("LG-DAMP", "LG-DUP"), ("SH-", "SIDE"), ("SH-", "AF-KEEL"), ("SH-", "FLOOR"), ("HV-BOOM", "NAC"), ("LG-FAIR", "LG-D"), ("F-CLV", "CAN-F"), ("PM-END", "PM-STRUT"), ("PM-END", "BH-7"), ("PM-END", "PM-PLATE"), ("MOT-P", "PM-PLATE"),
]


def interference(meshes, inst_all, parts, placed=None):
    pmap = {p.pid: p for p in parts}
    items = []
    for pid, k, M in inst_all:
        m = meshes[pid].copy()
        m.apply_transform(M)
        m.merge_vertices()
        if m.is_volume and m.volume < 0:
            m.invert()
        items.append((f"{pid}#{k}", pid, m, m.bounds))
    res, failed = [], 0
    n = len(items)
    import time as _t
    t0 = _t.time()
    for i in range(n):
        if i % 40 == 0:
            print(f"  interference {i}/{n} ({_t.time() - t0:.0f} s)", flush=True)
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            if a[1] == b[1] and a[1].startswith(("BAT-MOD", "BAT-TIER")):
                continue
            if np.any(np.minimum(a[3][1], b[3][1]) - np.maximum(a[3][0], b[3][0]) < 0.5):
                continue                                     # disjoint or face-touching boxes only
            v = None
            if a[2].is_volume and b[2].is_volume:
                try:
                    inter = trimesh.boolean.intersection([a[2], b[2]], engine="manifold")
                    v = float(inter.volume) if inter is not None and len(inter.faces) else 0.0
                except Exception:
                    v = None
            if v is not None and v > min(abs(a[2].volume), abs(b[2].volume)) + 1.0:
                v = None                                     # inconsistent mesh result -> exact check
            if v is None and placed is not None and _t.time() - t0 < 600 and max(a[2].bounds[1] - a[2].bounds[0]) < 1500 and max(b[2].bounds[1] - b[2].bounds[0]) < 1500 \
                    and len(a[2].faces) + len(b[2].faces) < 60000:
                try:
                    v = float((placed[i][1] & placed[j][1]).volume)
                except Exception:
                    v = None
            if v is None:
                failed += 1
                continue
            if v > 2000.0:
                exp = any((a[1].startswith(p) and b[1].startswith(q)) or (a[1].startswith(q) and b[1].startswith(p))
                          for p, q in EXPECTED_CONTACT)
                res.append(dict(a=a[0], b=b[0], volume_cm3=round(v / 1000, 1), expected_contact=exp))
    res.sort(key=lambda r: -r["volume_cm3"])
    return res, failed


# ============================================================================ writers
def run(parts, placed, mp, meshes, inst_all, disp=None):
    OUT.mkdir(parents=True, exist_ok=True)
    ma = mass_audit(parts, mp, inst_all)
    (OUT / "mass_cg_audit.json").write_text(json.dumps(ma, indent=1))
    L = ["# CAD mass and CG audit (generated by cad/audit.py)", "",
         "CAD masses: made parts = CAD volume x density (fea/materials.json, cad/e8cad/config.py); COTS placeholders = catalog "
         "or design masses at their CAD positions; occupants at the design points; the growth allowance is not modelled and is "
         "carried at its design point. Design values: design/geometry.json mass_items (same totals as selected_design.json).", "",
         "## Totals", "", "| case | design kg | CAD kg | diff kg | diff % | design CG x, z (m) | CAD CG x, z (m) | dx (m) | dz (m) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in ma["totals"].items():
        L.append(f"| {k} | {v['design_kg']:.1f} | {v['cad_kg']:.1f} | {v['diff_kg']:+.1f} | {v.get('diff_pct', float('nan')):+.1f} | "
                 f"{v['design_cg_m'][0]:.3f}, {v['design_cg_m'][2]:.3f} | {v['cad_cg_m'][0]:.3f}, {v['cad_cg_m'][2]:.3f} | "
                 f"{v['dx_m']:+.3f} | {v['dz_m']:+.3f} |")
    L += ["", f"Static margin at MTOW: design {ma['static_margin_design']:.3f}, with the CAD CG {ma['static_margin_cad']:.3f} "
              f"(shift {ma['static_margin_shift']:+.3f} of MAC, neutral point unchanged).", "",
          "## By category", "", "| category | design kg | CAD kg | diff kg | diff % | design CG x, z | CAD CG x, z | dx (m) | dz (m) | note |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in ma["categories"]:
        L.append(f"| {r['category']} | {r['design_kg']:.2f} | {r['cad_kg']:.2f} | {r['diff_kg']:+.2f} | {r['diff_pct']:+.1f} | "
                 f"{r['design_cg_m'][0]:.3f}, {r['design_cg_m'][2]:.3f} | {r['cad_cg_m'][0]:.3f}, {r['cad_cg_m'][2]:.3f} | "
                 f"{r['dx_m']:+.3f} | {r['dz_m']:+.3f} | {r['note']} |")
    L += ["", "## Weight reductions from design/mass_calibration.json, as built", "",
          "Target fractions/kg are the iteration-2 calibration values on the iteration-1 parts; the iteration-3 parts are smaller, "
          "so the removed kg differ; the fraction is the comparable figure.", "",
          "| part | target fraction | target kg (iteration-1 parts) | built fraction | kg removed as built | CAD kg as built |", "|---|---|---|---|---|---|"]
    for r in ma["reductions"]:
        f = lambda v, d=3: "-" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))
        L.append(f"| {r['part']} | {f(r['target_fraction'], 2)} | {r['target_kg_iteration1']:.2f} | {f(r['built_fraction'], 2)} | "
                 f"{f(r['removed_kg_as_built'], 2)} | {f(r['cad_kg_as_built'], 2)} |")
    L += ["", "## Group masses vs design/mass_calibration.json (iteration-2 calibration, after reductions)", "",
          "| key | calibration kg | CAD kg |", "|---|---|---|"]
    for r in ma["calibration_groups"]:
        L.append(f"| {r['key']} | {r['calibration_kg']:.2f} | {r['cad_kg']:.2f} |")
    L += ["", "## WP F mass assumptions", "", "| item | FEA assumed kg | CAD kg | parts (kg, all instances) |", "|---|---|---|---|"]
    for k, v in ma["wpf_checks"].items():
        L.append(f"| {k.replace('_', ' ')} | {v['fea_assumed_kg']:.0f} | {v['cad_kg']:.1f} | "
                 + ", ".join(f"{a} {b:.2f}" for a, b in v["parts"].items()) + f" ({v['note']}) |")
    L += ["", "## selected_design.json breakdown keys vs CAD mass groups", "", "| key | design kg | CAD kg | diff kg | diff % |", "|---|---|---|---|---|"]
    for r in ma["breakdown"]:
        L.append(f"| {r['key']} | {r['design_kg']:.2f} | {r['cad_kg']:.2f} | {r['diff_kg']:+.2f} | {r['diff_pct']:+.1f} |")
    (OUT / "mass_cg_audit.md").write_text("\n".join(L) + "\n")
    ck = clearances(parts, mp, disp or meshes, inst_all)
    (OUT / "clearance_checks.json").write_text(json.dumps(ck, indent=1))
    npass = sum(c["status"] == "PASS" for c in ck)
    nf = sum(c["status"] == "FAIL" for c in ck)
    nw = sum(c["status"] == "WARN" for c in ck)
    L = ["# CAD clearance and installation checks (generated by cad/audit.py)", "",
         f"**{npass} PASS, {nw} WARN, {nf} FAIL** of {len(ck)} checks. Geometry from design/geometry.json as modelled in cad/.", "",
         "| id | check | value | reference | unit | status | note |", "|---|---|---|---|---|---|---|"]
    for c in ck:
        v = "n/a" if c["value"] is None else f"{c['value']:.3f}" if abs(c["value"]) < 10 else f"{c['value']:.0f}"
        L.append(f"| {c['id']} | {c['check']} | {v} | {c['reference']} | {c['unit']} | {c['status']} | {c['note']} |")
    (OUT / "clearance_checks.md").write_text("\n".join(L) + "\n")
    print("clearances:", npass, "PASS", nw, "WARN", nf, "FAIL", flush=True)
    import os
    if os.environ.get("E8_INTERFERENCE") == "1":
        write_interference(*interference(meshes, inst_all, parts, placed))
    else:
        print("interference: skipped in the build (run: python cad/audit.py, memory-capped)", flush=True)


def write_interference(inter, failed):
    (OUT / "interference.json").write_text(json.dumps(dict(threshold_cm3=2.0, failed_pairs=failed, overlaps=inter), indent=1))
    L = ["# Interference scan (generated by cad/audit.py)", "",
         "Every pair of placed aircraft parts whose bounding boxes overlap is intersected as meshes (manifold3d, watertight bodies of the exported GLB meshes); overlaps above "
         f"2 cm3 are listed. 'expected' marks bonded interfaces where the overlap is tessellation noise. {failed} pairs could not "
         "be evaluated (meshes that are not watertight).", "", "| part A | part B | overlap cm3 | expected contact |", "|---|---|---|---|"]
    for r in inter:
        L.append(f"| {r['a']} | {r['b']} | {r['volume_cm3']} | {'yes' if r['expected_contact'] else '**no**'} |")
    (OUT / "interference.md").write_text("\n".join(L) + "\n")
    print("interference: ", sum(not r["expected_contact"] for r in inter), "unexpected overlaps", flush=True)


def _volume_parts(m):
    """Watertight bodies of a display mesh (merged vertices, split into connected components)."""
    m = m.copy()
    m.merge_vertices()
    if m.is_volume:
        return [m]
    comps = trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(m.faces)), min_len=1, engine="scipy")
    return [c for c in m.submesh(comps, append=False) if c.is_volume]


def standalone():
    """Interference scan from the exported GLBs and parts.json only (no OCC shapes in memory)."""
    import gc
    data = json.loads((ROOT / "cad" / "parts.json").read_text())
    meshes, inst_all = {}, []
    for p in data["parts"]:
        if p["tooling"]:
            continue
        g = trimesh.load(ROOT / "docs" / p["glb"], force="mesh")
        meshes[p["id"]] = g
        for k, M in enumerate(p["instances"]):
            inst_all.append((p["id"], k, np.array(M)))
    items = []
    for pid, k, M in inst_all:
        m = meshes[pid].copy()
        m.apply_transform(M)
        items.append((f"{pid}#{k}", pid, _volume_parts(m), m.bounds))
    del meshes
    gc.collect()
    res, failed, n = [], 0, len(items)
    for i in range(n):
        if i % 50 == 0:
            print(f"  interference {i}/{n}", flush=True)
            gc.collect()
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            if a[1] == b[1] and a[1].startswith(("BAT-MOD", "BAT-TIER")):
                continue
            if np.any(np.minimum(a[3][1], b[3][1]) - np.maximum(a[3][0], b[3][0]) < 0.5):
                continue
            if not a[2] or not b[2]:
                failed += 1
                continue
            v = 0.0
            ok = True
            for ma_ in a[2]:
                for mb_ in b[2]:
                    if np.any(np.minimum(ma_.bounds[1], mb_.bounds[1]) - np.maximum(ma_.bounds[0], mb_.bounds[0]) < 0.5):
                        continue
                    try:
                        r = trimesh.boolean.intersection([ma_, mb_], engine="manifold")
                        v += float(r.volume) if r is not None and len(r.faces) else 0.0
                    except Exception:
                        ok = False
            if not ok:
                failed += 1
                continue
            if v > 2000.0:
                exp = any((a[1].startswith(p) and b[1].startswith(q)) or (a[1].startswith(q) and b[1].startswith(p))
                          for p, q in EXPECTED_CONTACT)
                res.append(dict(a=a[0], b=b[0], volume_cm3=round(v / 1000, 1), expected_contact=exp))
    res.sort(key=lambda r: -r["volume_cm3"])
    write_interference(res, failed)


if __name__ == "__main__":
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    standalone()
