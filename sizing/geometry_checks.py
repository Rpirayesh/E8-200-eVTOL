"""Geometric integration checks of design/geometry.json, using the same definitions as WP G's CAD audit
(cad/audit.py): wing section rotated by the incidence about the leading edge, fuselage OML from PCHIP-interpolated
super-ellipse stations, P95 seated occupant (sitting height 970 mm, 15 deg recline, head radius 110 mm, SRP 100 mm aft
of the occupant point), boom saddle pad 84 mm above the boom axis, cabin sill 530 mm above the floor, spar posts
40 mm, canopy 3.2 mm.

Used by sizing/design_out.py to place the wing, booms, rotors, packs, seats, canister and gear, and by
validation/sizing/verify_sizing.py (G-checks).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.interpolate import PchipInterpolator

from .data import ROOT

# CAD detail constants (cad/e8cad/config.py DETAIL, fuselage.py, booms.py with the WP F P2 saddle)
SITTING_P95 = 0.970
SRP_BACK = 0.100
HEAD_R = 0.110
RECLINE = math.radians(15.0)
CANOPY_T = 0.0032
SILL_ABOVE_FLOOR = 0.530
POST_W = 0.040
PANEL_T = 0.011
BOOM_R_WRAP = 0.0560          # boom outer radius at the WP F over-wrap (OD 112 mm)
PAD_TOP = 0.0840              # P2 saddle pad top above the boom axis (R_wrap 56 + wall 12 + pad 16 mm)
FITTING_DROP = 0.056          # wing-root fitting P1 below the wing lower surface (14 + 42 mm)
MOTOR_P_LEN = 0.150           # REB 90 axial length placeholder; motor face 60 mm ahead of the propeller plane
FAN_DEG = 5.0                 # rotor-burst fan half angle (AC 20-128A practice)


def ls417():
    pts = np.loadtxt(ROOT / "validation" / "cfd" / "reference" / "ls417_coordinates_TND7428.dat", skiprows=1)
    i = int(np.argmin(pts[:, 0]))
    up, lo = pts[: i + 1][::-1], pts[i:]
    return up, lo


def naca4_surfaces(code, n=200):
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    x = (1 - np.cos(np.linspace(0, np.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.126 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)
    yc = np.where(x < p, m / max(p, 1e-9) ** 2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2)) if m else 0 * x
    return np.column_stack([x, yc + yt]), np.column_stack([x, yc - yt])


class Wing:
    def __init__(self, w: dict):
        self.xle, self.zle, self.c = w["x_le_root"], w["z_root"], w["root_chord"]
        self.inc = math.radians(w["incidence_deg"])
        af = w.get("airfoil", "ls417")
        up, lo = ls417() if af == "ls417" else naca4_surfaces(af[4:])
        self.up, self.lo = up, lo
        self.span = w["span"]

    def to_global(self, x, z):
        a = self.inc
        return self.xle + x * math.cos(a) + z * math.sin(a), self.zle - x * math.sin(a) + z * math.cos(a)

    def _surf(self, pts):
        X, Z = self.to_global(pts[:, 0] * self.c, pts[:, 1] * self.c)
        o = np.argsort(X)
        return X[o], Z[o]

    def z_lo(self, x):
        X, Z = self._surf(self.lo)
        return float(np.interp(x, X, Z, left=np.nan, right=np.nan))

    def z_up(self, x):
        X, Z = self._surf(self.up)
        return float(np.interp(x, X, Z, left=np.nan, right=np.nan))

    def x_at(self, xc):
        return self.to_global(xc * self.c, 0.0)[0]

    def lower_at_xc(self, xc):
        """Global (x, z) of the lower surface at chord fraction xc (wing frame)."""
        zl = float(np.interp(xc, self.lo[:, 0], self.lo[:, 1])) * self.c
        return self.to_global(xc * self.c, zl)

    def lower_min(self):
        X, Z = self._surf(self.lo)
        return float(Z.min())


class OML:
    def __init__(self, f: dict):
        st = f["stations"]
        x = np.array([s["x"] for s in st])
        self.w = PchipInterpolator(x, [s["width"] for s in st])
        self.h = PchipInterpolator(x, [s["height"] for s in st])
        self.zc = PchipInterpolator(x, [s["z_center"] for s in st])
        self.e = f.get("shape_exponent", 2.5)
        self.L = x[-1]

    def sec(self, x):
        return max(float(self.w(x)), 0.0), max(float(self.h(x)), 0.0), float(self.zc(x))

    def top(self, x):
        w, h, zc = self.sec(x)
        return zc + h / 2

    def half_width(self, x, z):
        w, h, zc = self.sec(x)
        if h <= 0 or abs(z - zc) >= h / 2:
            return 0.0
        return w / 2 * (1 - (abs(z - zc) / (h / 2)) ** self.e) ** (1 / self.e)


def head_center(seat):
    srp = np.array([seat["x"] + SRP_BACK, 0.0, seat["seat_reference_point_z"]])
    ub = np.array([math.sin(RECLINE), 0, math.cos(RECLINE)])
    fn = np.array([-math.cos(RECLINE), 0, math.sin(RECLINE)])
    return srp + ub * (SITTING_P95 - HEAD_R) + fn * HEAD_R


def occupant_points(seat):
    """Approximate P95 occupant envelope: head sphere and shoulders (the highest points of the CAD occupant)."""
    hc = head_center(seat)
    pts = []
    for th in np.linspace(0, 2 * np.pi, 24, endpoint=False):
        for ph_ in np.linspace(0, np.pi / 2, 6):
            pts.append(hc + HEAD_R * np.array([math.cos(th) * math.cos(ph_), math.sin(th) * math.cos(ph_), math.sin(ph_)]))
    srp_z = seat["seat_reference_point_z"]
    for sy in (-0.23, 0.23):
        pts.append(np.array([seat["x"] + 0.05, seat.get("y", 0.0) + sy, srp_z + 0.62]))
    return np.array(pts)


def head_clearance(seat, wing: Wing, oml: OML):
    hc = head_center(seat)
    xs = np.linspace(hc[0] - HEAD_R, hc[0] + HEAD_R, 23)
    best = np.inf
    for x in xs:
        zt = oml.top(x) - CANOPY_T
        zl = wing.z_lo(x)
        ceil_ = min(zt, zl) if not np.isnan(zl) else zt
        hz = hc[2] + math.sqrt(max(HEAD_R**2 - (x - hc[0]) ** 2, 0))
        best = min(best, ceil_ - hz)
    return best


def checks(geo: dict) -> list[dict]:
    """All integration checks; each row: id, check, value, reference, unit, sense ('ge'/'le'), status."""
    rows = []

    def add(cid, name, v, ref, unit, sense="ge", note=""):
        ok = v >= ref - 1e-9 if sense == "ge" else v <= ref + 1e-9
        rows.append(dict(id=cid, check=name, value=float(v), reference=float(ref), unit=unit, sense=sense,
                         status="PASS" if ok else "FAIL", note=note))
    w = Wing(geo["wing"])
    oml = OML(geo["fuselage"])
    b0 = geo["booms"][0]
    zb = b0["z"]
    seats = geo["seats"]
    floor = geo["fuselage"]["cabin"]["floor_z"]
    # G1 boom vs wing (crown under the lower surface over the chord; saddle pads under the lower skin at both spars)
    X = np.linspace(w.xle + 0.005, w.xle + w.c * math.cos(w.inc) - 0.005, 200)
    zl = np.array([w.z_lo(x) for x in X])
    add("G1a", "boom crown below the wing lower surface (min gap over the chord)", float(np.nanmin(zl - (zb + BOOM_R_WRAP))), 0.0, "m")
    for i, nm in enumerate(("main", "rear")):
        xs, zs = w.lower_at_xc(geo["wing"]["spars"][i]["x_c"])
        add(f"G1{'bc'[i]}", f"boom saddle pad top below the wing lower surface at the {nm} spar", zs - (zb + PAD_TOP), 0.0, "m")
    # G2 head clearance (P95) under canopy / wing, 50 mm
    for s in seats:
        add("G2", f"head clearance, {s['name']} (P95)", head_clearance(s, w, oml), 0.050, "m")
    # G3 passenger door between the spar posts, 14 CFR 23.807 exit 0.483 x 0.660 m
    xm = w.x_at(geo["wing"]["spars"][0]["x_c"])
    xr = w.x_at(geo["wing"]["spars"][1]["x_c"])
    dw = (xr - POST_W) - (xm + POST_W)
    add("G3a", "passenger door clear width between the spar posts", dw, 0.483, "m")
    sill = floor + SILL_ABOVE_FLOOR
    add("G3b", "passenger door clear height (sill to wing lower surface)", w.z_lo(0.5 * (xm + xr)) - sill, 0.660, "m")
    # G4 seat stroke (150 mm reference, WP G C23)
    srp = min(s["seat_reference_point_z"] for s in seats)
    add("G4", "seat energy-absorber stroke under the pan", srp - 0.004 - (floor + PANEL_T + 0.025), 0.150, "m")
    # G5 battery packs inside the OML (all 8 box corners) and gear cross tubes clear of the packs
    worst = -np.inf
    for p in geo["battery_packs"]:
        for sx in (-1, 1):
            x = p["x"] + sx * p["length"] / 2
            for z in (p["z"] - p["height"] / 2, p["z"] + p["height"] / 2):
                worst = max(worst, p["width"] / 2 - oml.half_width(x, z))
    add("G5a", "battery box corner outside the fuselage OML (max lateral protrusion)", worst, 0.0, "m", "le")
    pk = [(p["x"] - p["length"] / 2, p["x"] + p["length"] / 2) for p in geo["battery_packs"]]
    gaps = []
    for st in geo["landing_gear_oml"]["struts"]:
        x = st["p1"][0]
        gaps.append(min(abs(x - a) if x < a else (abs(x - b) if x > b else -min(x - a, b - x)) for a, b in pk) - 0.080)
    add("G5b", "gear cross-tube saddle (+-80 mm pad) clear of the battery packs", min(gaps), 0.0, "m")
    add("G5c", "battery pack top below the cabin floor", floor - max(p["z"] + p["height"] / 2 for p in geo["battery_packs"]), 0.0, "m")
    # G6 pusher tail-down strike angle about the skid aft end (>= 10 deg) and ground clearance
    p = geo["pusher"]
    sk = geo["landing_gear_oml"]["skids"][0]
    Rp = p["diameter"] / 2
    add("G6a", "tail-down rotation about the skid aft end to pusher-tip strike", math.degrees(math.atan2(p["z"] - Rp, p["x"] - sk["x_end"])), 10.0, "deg")
    add("G6b", "pusher tip ground clearance (level)", p["z"] - Rp, 0.20, "m")
    vf = geo["tail"]["vertical"][0]
    add("G6c", "tail-down rotation to ventral-fin strike", math.degrees(math.atan2(vf["z_root"], vf["x_le_root"] + vf["root_chord"] - sk["x_end"])), 10.0, "deg")
    twin = p.get("layout") == "twin_boom_tail"
    if twin:      # G7 twin: each motor on its boom end, behind the boom (no tail-cone cowl)
        add("G7", "twin pusher: motor face at or behind the boom end (boom-end fitting)",
            min(pp["motor"]["x_face"] - bm["x_aft"] for pp, bm in zip(geo["pushers"], geo["booms"])) + 1e-9, 0.0, "m")
    else:         # G7 pusher motor inside the tail-cone OML (cowl part of the OML)
        xm_face = p["x"] - 0.060 - MOTOR_P_LEN
        wd, hd, zc = oml.sec(xm_face)
        md = geo["pusher"].get("motor_diameter_m", 0.2702)
        add("G7", "pusher motor radius inside the tail-cone OML (half-width and half-height minus radius)",
            min(wd, hd) / 2 - md / 2 - abs(zc - p["z"]), 0.0, "m")
    # G8 parachute canister inside the OML
    c = geo["parachute"]["canister"]
    d = np.array(c["fire_direction"], float)
    d /= np.linalg.norm(d)
    topc = np.array([c["x"], 0, c["z"]]) + d * c["length"] / 2
    ztop = topc[2] + c["diameter"] / 2 * abs(d[0])
    add("G8a", "parachute canister top below the fuselage OML", oml.top(topc[0]) - ztop, 0.0, "m")
    add("G8b", "parachute canister width inside the OML at its mid height", oml.half_width(c["x"], c["z"]) - c["diameter"] / 2, 0.0, "m")
    # G9 wing-root fittings inside the fuselage OML (root fairing part of the OML)
    xs, zs = w.lower_at_xc(geo["wing"]["spars"][0]["x_c"])
    pz = zs - FITTING_DROP
    add("G9", "wing-root fitting inside the fuselage OML at its height (half-width - root_fittings_y)",
        oml.half_width(xs, pz) - geo["wing"]["root_fittings_y"], 0.0, "m")
    # G10 exposed tail areas
    t = geo["tail"]
    h = t["horizontal"][0]
    by = abs(geo["booms"][0]["y"])
    exp_h = h["root_chord"] * 2 * (by - BOOM_R_WRAP)
    add("G10a", "H-tail exposed area between the booms / sized area (>= 0.99; WP G uses 0.97)", exp_h / t["area_h_m2"], 0.99, "-")
    fin_exp = vf["root_chord"] * ((zb - BOOM_R_WRAP) - vf["z_root"])
    add("G10b", "ventral fin exposed area (each) / sized area (>= 0.99)", fin_exp / (t["area_v_total_m2"] / 2), 0.99, "-")
    # G11 lift rotors: blade plane above wing upper surface where they overlap, above the cabin top, burst fan
    R = geo["lift_rotors"][0]["diameter"] / 2
    hubs = np.array([r["hub"] for r in geo["lift_rotors"]])
    zbl = hubs[:, 2].min() - 0.02
    worst = np.inf
    for hb in hubs:
        for rr in np.linspace(0, R, 20):
            for th in np.linspace(0, 2 * np.pi, 48, endpoint=False):
                x, y = hb[0] + rr * math.cos(th), hb[1] + rr * math.sin(th)
                if abs(y) <= w.span / 2:
                    zu = w.z_up(x)
                    if not np.isnan(zu):
                        worst = min(worst, zbl - zu)
    add("G11a", "rotor blade plane above the wing upper surface where the discs overlap it", worst if np.isfinite(worst) else 9.9, 0.15, "m")
    top = max(oml.top(x) for x in np.linspace(0, oml.L, 200))
    add("G11b", "rotor blade plane above the fuselage top", zbl - top, 0.0, "m")
    occ = np.vstack([occupant_points(s) for s in seats])
    best = 90.0
    for hb in hubs:
        for th in np.linspace(0, 2 * np.pi, 120, endpoint=False):
            tip = np.array([hb[0] + R * math.cos(th), hb[1] + R * math.sin(th), zbl])
            dd = occ - tip
            ang = np.degrees(np.arctan2(-dd[:, 2], np.hypot(dd[:, 0], dd[:, 1])))
            best = min(best, float(ang.min()))
    add("G11c", "rotor-burst fan: min depression angle from the tip path to an occupant (approx. envelope)", best, FAN_DEG + 0.3, "deg",
        note="WP G's mesh-based occupant is used in cad/audit.py C9; 0.3 deg margin for the envelope approximation")
    # G12 pusher clearances
    if twin:
        te = max(h["x_le_root"] + h["root_chord"], vf["x_le_root"] + vf["root_chord"])
        add("G12a", "twin pusher: prop plane behind the H-tail and fin trailing edges (axial gap)", p["x"] - te, 0.25, "m",
            note="the props run in the tail wake: acoustic / blade-load check open")
        add("G12b", "twin pusher: tip to the other boom surface", 2 * by - BOOM_R_WRAP - Rp, 0.10, "m")
    else:
        add("G12a", "pusher disc ahead of the H-tail leading edge", h["x_le_root"] - p["x"], 0.30, "m")
        add("G12b", "pusher tip to boom surface", by - BOOM_R_WRAP - Rp, 0.10, "m")
    gmin = 9.9
    for pp in (geo["pushers"] if twin else [p]):
        for hb in hubs:
            dx = pp["x"] - hb[0]
            if abs(dx) < R:
                half = math.sqrt(R**2 - dx**2)
                lo, hi = max(hb[1] - half, pp["y"] - Rp), min(hb[1] + half, pp["y"] + Rp)
                if lo < hi:     # the lift disc and the pusher disc overlap in plan: worst lateral station
                    dy = 0.0 if lo <= pp["y"] <= hi else min(abs(lo - pp["y"]), abs(hi - pp["y"]))
                    gmin = min(gmin, zbl - (pp["z"] + math.sqrt(max(Rp**2 - dy**2, 0))))
    add("G12c", "pusher disc to lift-rotor blade plane where they overlap in plan", gmin, 0.10, "m")
    # G13 tip-over angles (25 deg) and boom height on the egress path (warn reference 1.9 m)
    cg = geo["cg_mtow_m"]
    add("G13a", "static lateral tip-over angle", math.degrees(math.atan2(sk["y"], cg[2])), 25.0, "deg")
    add("G13b", "static forward tip-over angle", math.degrees(math.atan2(cg[0] - sk["x_start"], cg[2])), 25.0, "deg")
    add("G13c", "static aft tip-over angle", math.degrees(math.atan2(sk["x_end"] - cg[0], cg[2])), 25.0, "deg")
    rows.append(dict(id="G13d", check="boom underside height above ground on the egress path (information, 1.9 m reference)",
                     value=float(zb - BOOM_R_WRAP), reference=1.9, unit="m", sense="ge",
                     status="PASS" if zb - BOOM_R_WRAP >= 1.9 else "WARN", note="pad and mark the boom underside"))
    return rows
