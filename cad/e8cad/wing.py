"""Wing: foam cores, spar caps/webs, skins, ribs, root fittings, ailerons, tip fairings.

Modelling frame: local airfoil frame (x along the chord from the LE, y span, z normal), placed with
config.WLOC; left-hand items are mirror placements of the right-hand solid.
"""
from __future__ import annotations

import math

import numpy as np
from build123d import Plane

from .config import (SIZING, FEA_FIT, BOOM_OD, BOOM_Y, BOOM_Z, CHUTE, DETAIL, PANEL, WING, WLOC, AIRFOIL_DIR, Part, G, mm, rho,
                     SHOP, global_to_wing)
from .geom import (prism_x, cyl_z, box, clip2d, compound, cyl_x, cyl_y, fuse_all, loft3d, offset2d, prism_y, selig_airfoil,
                   thickness_at, circle)

C = WING["chord"]
# WP F phase 3.1: H45 layer under the upper skin over x/c 0.08-0.73 for |y| <= 2.94 m (skin wrinkling), 15 mm deep
H45_T, H45_XC = 15.0, (0.085, 0.735)
H45_Y = 3260.0 / 4500.0 * WING["half"]          # WP F 3.2: |y| <= 3.26 m on the 9 m wing, kept at the same span fraction
HALF = WING["half"]
FOIL = selig_airfoil(AIRFOIL_DIR / "ls417_coordinates_TND7428.dat", C, 64)
INNER = offset2d(FOIL, -WING["skin_t"])
TIP_FAIR = 80.0                               # tip fairing length (detail)
Y_TIP = HALF - TIP_FAIR                       # end of the structural box
RIB_T = DETAIL["rib_t"]
Y_AIL0, Y_AIL1 = mm(WING["ail"]["y_from"]), mm(WING["ail"]["y_to"])
X_HINGE = (1 - WING["ail"]["chord_fraction"]) * C
GAP = DETAIL["ctrl_gap"]
_FL = WING.get("flaps")
FLAP_BOOM_GAP = 90.0                          # flap split either side of the boom (detail: boom + saddle clearance)
BAYS = [("W-AIL", "Aileron", Y_AIL0, Y_AIL1)]
if _FL:
    _f0, _f1 = mm(_FL["y_from"]), mm(_FL["y_to"])
    if _f0 < BOOM_Y < _f1:
        BAYS += [("W-FLAP-I", "Flap, inboard of the boom", _f0, BOOM_Y - FLAP_BOOM_GAP),
                 ("W-FLAP-O", "Flap, outboard of the boom", BOOM_Y + FLAP_BOOM_GAP, _f1)]
    else:
        BAYS += [("W-FLAP", "Flap", _f0, _f1)]
RIB_Y = {"W-RIB-R": WING["root_y"], "W-RIB-B": BOOM_Y, "W-RIB-A": [Y_AIL0, Y_AIL1]}
if _FL:
    RIB_Y["W-RIB-F"] = [b[2] for b in BAYS[1:]] + [b[3] for b in BAYS[1:]]
L_PLACE = [(WLOC, False), (WLOC, True)]


def lr(y, dy0=0.0):
    """Right/left placements of a solid modelled at local span station dy0, moved to +/-y."""
    from build123d import Pos
    return [(WLOC * Pos(0, y - dy0, 0), False), (WLOC * Pos(0, -(y - dy0), 0), True)]


def _stations(name):
    """[(eta, section)] of a spar: WP F sized stations if available, else the design root/tip sections."""
    for sp in SIZING.get("wing", {}).get("spars", []):
        if sp["name"] == name:
            return [(s["eta"], s["section"]) for s in sp["stations"]]
    sp = [s for s in WING["spars"] if s["name"] == name][0]
    return [(0.0, sp["section_root"]), (1.0, sp["section_tip"])]


def sec_val(name, key, y):
    st = _stations(name)
    return float(np.interp(min(abs(y) / HALF, 1.0), [e for e, _ in st], [s[key] for _, s in st]))


def _lin(sec_root, sec_tip, key, y, name=None):
    return sec_val(name, key, y)


def _zin(x):
    return thickness_at(INNER, x)


def _cap_ring(xs, b, t, upper, y, n=9, grow=0.0):
    xx = np.linspace(xs - b / 2, xs + b / 2, n)
    zz = np.array([_zin(x)[1 if upper else 0] for x in xx])
    inner = zz - t if upper else zz + t
    zz = zz + grow if upper else zz - grow                    # cutting tool: pushed past the core surface
    pts = np.vstack([np.column_stack([xx, zz]), np.column_stack([xx[::-1], inner[::-1]])])
    return np.column_stack([pts[:, 0], np.full(len(pts), y), pts[:, 1]])


def _span_loft(ring_fn):
    st = sorted({min(e * HALF, Y_TIP) for e, _ in _stations("main")} | {Y_TIP})
    ys = sorted({-y for y in st} | set(st))
    return loft3d([ring_fn(y) for y in ys], ruled=True)


def spar_solids():
    out = {}
    for sp in WING["spars"]:
        tag = "M" if sp["name"] == "main" else "R"
        r, t = sp["section_root"], sp["section_tip"]
        xs = sp["x_c"] * C
        for upper, nm in ((True, "U"), (False, "L")):
            out[f"cap{tag}{nm}"] = _span_loft(lambda y, u=upper: _cap_ring(xs, _lin(r, t, "b_cap", y, sp["name"]) * 1000,
                                                                        _lin(r, t, "t_cap", y, sp["name"]) * 1000, u, y))
        bt = min(s["b_cap"] for _, s in _stations(sp["name"])) * 1000
        webs = []
        if r["n_web"] == 2:
            web_x = [(xs - bt / 2, +1), (xs + bt / 2, -1)]
        else:
            web_x = [(xs, 0)]

        def web_ring(y, x0, sgn):
            tw = _lin(r, t, "t_web", y, sp["name"]) * 1000
            tc = _lin(r, t, "t_cap", y, sp["name"]) * 1000
            if sgn == 0:
                xa, xb = x0 - tw / 2, x0 + tw / 2
            elif sgn > 0:
                xa, xb = x0, x0 + tw
            else:
                xa, xb = x0 - tw, x0
            lo, hi = _zin((xa + xb) / 2)
            return np.array([[xa, y, lo + tc], [xb, y, lo + tc], [xb, y, hi - tc], [xa, y, hi - tc]])
        for x0, sgn in web_x:
            webs.append(_span_loft(lambda y, a=x0, s=sgn: web_ring(y, a, s)))
        out[f"web{tag}"] = webs
        if r["n_web"] == 2:
            tw0 = max(s["t_web"] for _, s in _stations(sp["name"])) * 1000

            def foam_ring(y):
                tc = _lin(r, t, "t_cap", y, sp["name"]) * 1000
                xx = np.linspace(xs - bt / 2 + tw0, xs + bt / 2 - tw0, 7)
                lo = np.array([_zin(x)[0] for x in xx]) + tc
                hi = np.array([_zin(x)[1] for x in xx]) - tc
                pts = np.vstack([np.column_stack([xx, lo]), np.column_stack([xx[::-1], hi[::-1]])])
                return np.column_stack([pts[:, 0], np.full(len(pts), y), pts[:, 1]])
            out[f"foam{tag}"] = _span_loft(foam_ring)
    # H45 layer under the upper skin (minus caps, webs and spar-box foam)
    from shapely.geometry import Polygon, box as sbox
    ring = Polygon(INNER).difference(Polygon(offset2d(INNER, -H45_T)))
    band = ring.intersection(sbox(H45_XC[0] * C, 0.0, H45_XC[1] * C, 1e4))
    band = band if band.geom_type == "Polygon" else max(band.geoms, key=lambda g: g.area)
    lay = prism_y(np.array(band.exterior.coords)[:-1], -H45_Y, H45_Y)
    for k in ("capMU", "capRU", "foamM"):
        lay = lay - out[k]
    for w_ in out["webM"] + out["webR"]:
        lay = lay - w_
    out["h45"] = lay
    return out


SP = None


def _sp():
    global SP
    if SP is None:
        SP = spar_solids()
    return SP


def spar_cut(with_h45=True):
    s = _sp()
    tools = []
    for sp in WING["spars"]:
        xs = sp["x_c"] * C
        for upper in (True, False):
            tools.append(_span_loft(lambda y, u=upper, sp=sp, xs=xs: _cap_ring(
                xs, sec_val(sp["name"], "b_cap", y) * 1000 + 0.6, sec_val(sp["name"], "t_cap", y) * 1000 + 0.3, u, y, grow=2.0)))
    parts = tools + [s["foamM"]] + ([s["h45"]] if with_h45 else []) + s["webM"] + s["webR"]
    u = parts[0].fuse(*parts[1:]).clean()
    if u.volume < 0.95 * sum(p.volume for p in parts):      # robust fallback: cut with the loose set of tools
        u = compound(parts)
    return u


def boom_channel_local():
    """Boom envelope + clearance as a solid in the wing frame (right boom)."""
    r = BOOM_OD / 2 + DETAIL["boom_clear"]
    g = cyl_x(r, WING["xle"] - 200, WING["xle"] + C + 200, BOOM_Y, BOOM_Z)
    return g.moved(WLOC.inverse())


def x_cut():
    """Aft face of the fixed wing in a control-surface bay: hinge line, but never into the rear spar caps."""
    st = _stations("rear")
    xs_r = WING["spars"][1]["x_c"] * C
    return max(X_HINGE - GAP - 1.0, xs_r + max(q["b_cap"] for _, q in st) * 1000 / 2 + 1.0)


def aileron_cut(y0, y1):
    """Region removed from cores/skin in a control-surface bay (aft of the false spar)."""
    lo, hi = thickness_at(FOIL, X_HINGE)
    return box(x_cut(), C + 10, y0, y1, lo - 50, hi + 50)


def in_bay(y0, y1):
    for b in BAYS:
        if y0 >= b[2] - 1 and y1 <= b[3] + 1:
            return b
    return None


def void_profiles():
    """Hot-wire spanwise lightening voids: 30 mm of foam kept under each skin, solid around the spars."""
    from shapely.geometry import Polygon, box as sbox
    keep = 30.0
    io = Polygon(offset2d(INNER, -keep))
    xs_m, xs_r = WING["spars"][0]["x_c"] * C, WING["spars"][1]["x_c"] * C
    bm = max(q["b_cap"] for _, q in _stations("main")) * 1000
    br = max(q["b_cap"] for _, q in _stations("rear")) * 1000
    out = []
    for xa, xb in ((40.0, xs_m - bm / 2 - 20), (xs_m + bm / 2 + 20, xs_r - br / 2 - 20)):
        if xb - xa < 40:
            continue
        g = io.intersection(sbox(xa, -1e4, xb, 1e4))
        for q in ([g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))):
            if q.area > 500:
                out.append(np.array(q.exterior.coords)[:-1])
    return out


def core_segments():
    """Span stations of the foam cores (right half) between ribs, split to the hot-wire bow length."""
    stops = [0.0]
    edges = []
    ribs = sorted({WING["root_y"], BOOM_Y, Y_AIL0, Y_AIL1} | set(RIB_Y.get("W-RIB-F", [])))
    a = -WING["root_y"] + RIB_T / 2
    segs = [(a, WING["root_y"] - RIB_T / 2)]          # centre core spans the fuselage
    prev = WING["root_y"] + RIB_T / 2
    for yr in ribs[1:] + [Y_TIP]:
        end = yr - RIB_T / 2 if yr != Y_TIP else Y_TIP
        L = end - prev
        n = max(1, math.ceil(L / (SHOP["hotwire_bow_mm"] - 100)))
        for k in range(n):
            segs.append((prev + k * L / n, prev + (k + 1) * L / n))
        prev = yr + RIB_T / 2
    return segs


def wing_parts() -> list[Part]:
    sp = _sp()
    cut = spar_cut()
    cut_r = spar_cut(with_h45=False)
    chan = boom_channel_local()
    ych = (BOOM_Y - BOOM_OD / 2 - 10, BOOM_Y + BOOM_OD / 2 + 10)
    parts = []
    xps = rho("xps_foam")
    global VOIDS
    VOIDS = void_profiles()
    fg = fitting_geometry()
    from build123d import Pos as _P
    fenv = []
    for f in fg.values():
        e = f["env"].moved(_P(0, WING["root_y"], 0))
        fenv += [e, e.mirror(Plane.XZ)]
    # ---- foam cores
    for i, (y0, y1) in enumerate(core_segments()):
        s = prism_y(INNER, y0, y1) - cut
        for e in fenv:
            eb = e.bounding_box()
            if eb.min.Y < y1 and eb.max.Y > y0:
                s = s - e
        bay = in_bay(y0, y1)
        in_ail = bay is not None
        if in_ail:
            s = s - aileron_cut(y0 - 1, y1 + 1)
        v_before = s.volume
        for vp in VOIDS:
            s = s - prism_y(vp, y0 - 1, y1 + 1)
        red = 1 - s.volume / v_before
        if y0 < ych[1] and y1 > ych[0]:
            s = s - chan
        centre = y0 < 0
        pid = f"W-CORE-{i + 1}"
        parts.append(Part(pid, f"Wing foam core set, span {y0:.0f} to {y1:.0f} mm" + (f" ({bay[1].lower()} bay)" if in_ail else ""),
                          "Wing", "CNC", "xps_foam (hot-wire cut)", s, [(WLOC, False)] if centre else L_PLACE, "wing",
                          notes=("Three pieces (LE, spar-box-to-rear-spar, aft) hot-wire cut on the constant-chord templates "
                                 "T-HW-*; spar-cap troughs routed with a router sled to the cap taper"
                                 + ("; boom channel routed in the lower surface" if y0 < ych[1] and y1 > ych[0] else "")
                                 + "; spanwise lightening voids hot-wire cut with inner templates (30 mm of foam kept under each "
                                   "skin, solid around the spars and aft of the rear spar). Left/right cores are a mirror pair."),
                          density=xps, machine="hotwire",
                          settings={"process": "hot-wire on templates (or 3-axis CNC router in two halves)",
                                    "foam": "XPS 32 kg/m3 (epoxy only)", "kerf_comp_mm": 0.8, "_reduction": red}))
    # ---- spar caps, webs, shear-web foam
    for tag, nm in (("M", "main"), ("R", "rear")):
        for u, un in (("U", "upper"), ("L", "lower")):
            sec = WING["spars"][0 if tag == "M" else 1]
            parts.append(Part(f"W-SP{tag}-C{u}", f"Wing {nm} spar {un} cap (UD carbon, continuous tip to tip)", "Wing",
                              "composite-layup", sec["section_root"]["cap_material"], sp[f"cap{tag}{u}"], [(WLOC, False)],
                              "wing", density=rho(sec["section_root"]["cap_material"]),
                              notes=f"Wet-laid UD tape in the segmented MDF cap jig T-CAPJIG-{tag}*, ply drops to the stations "
                                    + ", ".join(f"{e:.2f}: {s['t_cap']*1000:.1f} x {s['b_cap']*1000:.0f}" for e, s in _stations(sec["name"]))
                                    + " (eta: t x b mm, WP F sizing). Cured, then bonded into the core troughs.",
                              joints=f"one continuous lay-up {2*Y_TIP:.0f} mm long; the jig is split into 2.2 m MDF segments dowel-pinned on a strongback",
                              settings={"lay-up": "UD 300 g/m2, ply drops every ~150 mm span", "resin": "MGS L285/H287",
                                        "cure": "vacuum bag, 24 h RT + 15 h 50 C post-cure", "coupon": "1 per batch"}))
        sec = WING["spars"][0 if tag == "M" else 1]
        webs = compound(sp[f"web{tag}"])
        parts.append(Part(f"W-SP{tag}-W", f"Wing {nm} spar shear web{'s (2, box spar)' if len(sp[f'web{tag}'])>1 else ''}", "Wing",
                          "composite-layup", sec["section_root"]["web_material"], webs, [(WLOC, False)], "wing",
                          density=rho(sec["section_root"]["web_material"]),
                          notes="+/-45 carbon fabric, thickness by station (WP F): "
                                + ", ".join(f"{e:.2f}: {s['t_web']*1000:.2f} mm" for e, s in _stations(sec["name"]))
                                + "; wrapped onto the caps 25 mm.",
                          joints="laid on the assembled core faces in 2 m lengths with 100 mm ply overlaps",
                          settings={"lay-up": "+/-45 carbon twill", "cure": "vacuum bag"}))
        if f"foam{tag}" in sp:
            parts.append(Part(f"W-SP{tag}-F", f"Wing {nm} spar box foam (between the webs)", "Wing", "CNC", "pvc_h45",
                              sp[f"foam{tag}"], [(WLOC, False)], "wing", density=rho("pvc_h45"),
                              notes="Divinycell H45 strips CNC-routed to the cap taper (stabilises the webs only); joints staggered every 1.2 m.",
                              settings={"_reduction": 1 - rho("pvc_h45") / rho("pvc_h80")},
                              joints="strips of <= 2.4 m (sheet length), scarfed 4:1"))
    lay = sp["h45"]
    for ys_ in RIB_Y.values():
        for y_ in (ys_ if isinstance(ys_, list) else [ys_]):
            for sg in (1, -1):
                lay = lay - box(-10, C + 10, sg * y_ - RIB_T / 2 - 0.1, sg * y_ + RIB_T / 2 + 0.1, -500, 500)
    for b in BAYS:
        for sg in (1, -1):
            ya, yb = sorted((sg * b[2], sg * b[3]))
            lay = lay - aileron_cut(ya, yb)
    for e in fenv:
        lay = lay - e
    parts.append(Part("W-H45-U", f"H45 layer under the upper skin (x/c {H45_XC[0]}-{H45_XC[1]}, |y| <= {H45_Y/1000:.2f} m)", "Wing", "CNC", "pvc_h45", lay,
                      [(WLOC, False)], "wing", density=rho("pvc_h45"),
                      notes=f"{H45_T:.0f} mm Divinycell H45 CNC-routed to the airfoil, laid in the upper-core trough between the ribs; "
                            "replaces the XPS under the upper skin over the box and the mid bay (WP F phases 3.1/3.2, skin wrinkling).",
                      joints="pieces between ribs, sheet-length (<= 2.4 m) strips scarfed 4:1"))
    # ---- skins
    skin = prism_y(FOIL, -Y_TIP, Y_TIP) - prism_y(INNER, -Y_TIP - 1, Y_TIP + 1)
    for sgn in (1, -1):
        for b in BAYS:
            ya, yb = sorted((sgn * (b[2] + RIB_T / 2), sgn * (b[3] - RIB_T / 2)))
            skin = skin - aileron_cut(ya, yb)
        ch = chan if sgn > 0 else chan.mirror(Plane.XZ)
        skin = skin - ch
    parts.append(Part("W-SKIN", "Wing skins (upper and lower, continuous tip to tip)", "Wing", "composite-layup",
                      G["wing"]["torsion_box"]["skin_material"], skin, [(WLOC, False)], "wing",
                      density=rho(G["wing"]["torsion_box"]["skin_material"]), skin=True,
                      notes=f"{WING['skin_t']:.1f} mm ({WING['skin_source']}) +/-45 carbon wet-laid on the cores (lower skin in the lower cradles, "
                            "flip, upper skin); 50 mm overlap at the LE; boom channels and aileron bays trimmed after cure.",
                      joints="fabric widths 1.27 m laid spanwise-overlapped 50 mm; one cure per surface",
                      settings={"lay-up": "2 x 200 g/m2 carbon twill +/-45", "bag": "peel ply, perforated film, breather"}))
    # ---- ribs
    for pid, ys in RIB_Y.items():
        ys = ys if isinstance(ys, list) else [ys]
        r = prism_y(INNER, ys[0] - RIB_T / 2, ys[0] + RIB_T / 2) - cut_r
        nm = {"W-RIB-R": "root-fitting rib", "W-RIB-B": "boom-clamp rib", "W-RIB-A": "aileron bay end rib",
              "W-RIB-F": "flap bay end rib"}[pid]
        if pid == "W-RIB-B":
            r = r - chan
        if pid == "W-RIB-R":
            for e in fenv[::2]:
                r = r - e
        # lightening holes in the larger bays
        loc = []
        for y in ys:
            loc += lr(y, ys[0])
        parts.append(Part(pid, f"Wing {nm}", "Wing", "CNC", PANEL["label"], r, loc, "wing", density=PANEL["rho"],
                          notes="Flat sandwich panel CNC-routed in three pieces between the spars; bonded with flox "
                                "fillets and 2 x 45 deg glass tapes; potted inserts where fittings bolt through.",
                          machine="cnc"))
    # ---- control surfaces (aileron, flaps split at the boom), false spars, hinges, actuators
    xc0 = x_cut()
    lo, hi = thickness_at(FOIL, xc0 + GAP + 0.5)
    from shapely.geometry import Polygon
    xh0 = xc0 + GAP
    aft = Polygon(clip2d(FOIL, xmin=xh0))
    nose = Polygon(circle((hi - lo) / 2 - GAP, xh0 + (hi - lo) / 2, (hi + lo) / 2, 32))
    prof = np.array(aft.union(nose).intersection(Polygon(FOIL).buffer(0)).exterior.coords)[:-1]
    prof = clip2d(prof, xmin=xh0 + GAP - (hi - lo) / 2 + 2)
    a_in = offset2d(prof, -DETAIL["ctrl_skin_t"])
    xh = xh0 + (hi - lo) / 2   # hinge axis at the surface nose centre
    zh = (hi + lo) / 2
    hb = box(xc0 - 40, xh + 12, -3, 3, zh - 20, zh + 20) & prism_y(offset2d(FOIL, -1.5), -10, 10)
    hb = hb - cyl_y(3.2, -10, 10, xh, zh)
    hinge_pl, xa = [], (WING["spars"][0]["x_c"] + WING["spars"][1]["x_c"]) / 2 * C + 60
    za = sum(thickness_at(INNER, xa)) / 2
    act = box(xa - 40, xa + 40, -100, 100, za - 25, za + 25)
    fact = [m for m in G["mass_items"] if m["name"].startswith("aileron actuator")]
    _fl = [m for m in G["mass_items"] if m["name"].startswith("flap actuators")]
    flap_kg = _fl[0]["kg"] / 2 if _fl else None
    for pid, nm, b0, b1 in BAYS:
        ya, yb = b0 + RIB_T / 2 + GAP, b1 - RIB_T / 2 - GAP
        fs = box(xc0, xc0 + 1.0, b0 + RIB_T / 2, b1 - RIB_T / 2, lo - 50, hi + 50) & prism_y(INNER, b0, b1)
        parts.append(Part(pid.replace("W-", "W-FS-"), f"{nm} bay false spar (closing web)", "Wing", "composite-layup", "cf_fabric_wet",
                          fs, L_PLACE, "wing", density=rho("cf_fabric_wet"),
                          notes="1 mm carbon closing ply bonded over the core aft face behind the rear-spar caps; carries the hinge brackets."))
        a_skin = prism_y(prof, ya, yb) - prism_y(a_in, ya - 1, yb + 1)
        a_core = prism_y(a_in, ya, yb)
        parts.append(Part(pid, f"{nm} (foam core, carbon skin)", "Wing", "composite-layup", "cf_fabric_wet skin on xps_foam core",
                          compound([a_skin, a_core]), L_PLACE, "wing",
                          bodies=[(a_skin, rho("cf_fabric_wet")), (a_core, rho("xps_foam"))],
                          notes=f"Hot-wire core on template T-HW-AIL (same section for flaps and ailerons), {DETAIL['ctrl_skin_t']} mm "
                                f"carbon skin; span {yb-ya:.0f} mm; hinge line {xh/C:.3f} c (behind the rear-spar caps)."
                                + (" The flap is split at the boom so the deflected flap clears the boom and its saddle." if "FLAP" in pid else ""),
                          settings={"hinges": "3 x W-HINGE, AN clevis pins", "gap": f"{GAP} mm"}))
        yhs = np.linspace(ya + 100, yb - 100, 3)
        hinge_pl += [p for y in yhs for p in lr(y)]
        ymid = (yhs[0] + yhs[1]) / 2
        is_ail = pid == "W-AIL"
        parts.append(Part(pid + "-ACT", f"{nm} actuator (EMA placeholder)", "Wing", "COTS", "purchased", act, lr(ymid), "flight_controls",
                          mass_kg=fact[0]["kg"] if (is_ail and fact) else (flap_kg if flap_kg else 1.0),
                          mass_source="design mass item 'aileron actuator'" if (is_ail and fact) else
                          ("design mass item 'flap actuators' / 2" if flap_kg else "estimate (no flap-actuator mass item in the design)"),
                          purchased=True, notes="Envelope 200 x 80 x 50 mm, spanwise between the spars; bell-crank and push-rod "
                                                "through the rear-spar web and false spar."))
    parts.append(Part("W-HINGE", "Control-surface hinge bracket", "Wing", "CNC", "al6061_t6_sheet", hb, hinge_pl, "wing",
                      density=rho("al6061_t6_sheet"), machine="cnc_metal",
                      notes="6 mm 6061-T6 plate, 2.5-D; bolted to the false spar through potted inserts, AN3 clevis pin."))
    # ---- tip fairing
    tf_out = loft3d([np.column_stack([FOIL[:, 0], np.full(len(FOIL), Y_TIP), FOIL[:, 1]]),
                     np.column_stack([FOIL[:, 0] * 0.96 + 0.02 * C, np.full(len(FOIL), HALF), FOIL[:, 1] * 0.35])])
    tf_in = loft3d([np.column_stack([INNER[:, 0], np.full(len(INNER), Y_TIP - 1), INNER[:, 1]]),
                    np.column_stack([INNER[:, 0] * 0.96 + 0.02 * C, np.full(len(INNER), HALF - 1.0), INNER[:, 1] * 0.33])])
    tip = tf_out - tf_in
    parts.append(Part("W-TIP", "Wing tip fairing", "Wing", "composite-layup", "eglass_fabric_wet", tip, L_PLACE, "wing",
                      density=rho("eglass_fabric_wet"), skin=True,
                      notes="2 plies glass over a CNC-machined foam plug (T-PLUG-TIP), bonded to the last core with a 25 mm joggle."))
    # ---- wing root fittings (wing side) + fuselage clevises + pins
    parts += root_fittings()
    # ---- parachute front riser hard points (WP F part P5) on an angle at the aft face of the main spar box
    from .geom import p5_hardpoint, p5_angle
    from build123d import Pos as _P
    P5 = FEA_FIT["P5_parachute_hardpoint"]
    xs = WING["spars"][0]["x_c"] * C
    st = _stations("main")
    b0, bt = st[0][1]["b_cap"] * 1000, min(q["b_cap"] for _, q in st) * 1000
    xc = xs + b0 / 2 + 2 + P5["plate_w"] / 2
    hi = thickness_at(FOIL, xc)[1]
    zc = hi + 25 - P5["eye_zc"]
    ycf = [mm(a["y"]) for a in CHUTE["attach"] if a["name"] == "chute_front_R"][0]
    hp = p5_hardpoint(P5).moved(_P(xc, 0, zc))
    ang = p5_angle(P5, (xs + bt / 2) - xc).moved(_P(xc, 0, zc))
    parts.append(Part("W-CHUTE-FIT", "Parachute front riser hard point (FEA part P5)", "Systems", "CNC", P5["material"], hp, lr(ycf),
                      "parachute", density=rho(P5["material"]), machine="cnc_metal",
                      notes=f"WP F P5 geometry, plate {P5['t']:.0f} mm (phase 3.3B) ({P5['t']:.0f} mm 4130 N, eye pin {P5['pin_d']:.0f} mm, 8 x AN5); plate in the x-z plane so "
                            "the forward riser pull is in the lug plane; the eye exits the upper skin through a sealed slot."))
    parts.append(Part("W-CHUTE-ANG", "Parachute front hard-point angle (to the main spar aft web)", "Systems", "CNC", "al6061_t6_extr",
                      ang, lr(ycf), "parachute", density=rho("al6061_t6_extr"), machine="cnc_metal",
                      notes="6 mm 6061 angle machined from bar, bonded and bolted (4 x AN5) through the aft box web with a backing plate."))
    for p in parts:
        if p.pid == "W-H45-U":
            for sg in (1, -1):
                p.solid = p.solid - box(xs + bt / 2 - 1, xc + P5["plate_w"] / 2 + 1, sg * ycf - 46, sg * ycf + 46,
                                        zc - P5["plate_h"] / 2 - 1, hi + 5)
        if p.pid == "W-CORE-1":
            for sg in (1, -1):
                p.solid = p.solid - box(xs + bt / 2 - 1, xc + P5["plate_w"] / 2 + 1, sg * ycf - 46, sg * ycf + 46,
                                        zc - P5["plate_h"] / 2 - 1, hi + 5)
    return parts


def fitting_geometry():
    """P1 wing-root lug (fea/parts.py dimensions) on a spacer at the fore face of each spar, plus the fuselage clevis
    and pin. Modelled at y = 0 in the wing frame (placed at +/- root_fittings_y)."""
    P = FEA_FIT["P1_wing_root_lug"]
    from .fuselage import Y_SIDE
    yr = WING["root_y"]
    ys_out = Y_SIDE + PANEL["t"]
    out = {}
    for sp, tag in ((WING["spars"][0], "M"), (WING["spars"][1], "R")):
        st = _stations(sp["name"])
        xs = sp["x_c"] * C
        b0, tw0, tc0 = st[0][1]["b_cap"] * 1000, max(s["t_web"] for _, s in st) * 1000, st[0][1]["t_cap"] * 1000
        bt = min(s["b_cap"] for _, s in st) * 1000
        x_web = xs - bt / 2 if sp["section_root"]["n_web"] == 2 else xs - tw0 / 2
        x_pl = xs - b0 / 2 - 0.5                       # plate aft face: clear of the lower cap
        lo_in = min(_zin(x)[0] for x in (x_pl - P["t"], x_pl))
        lo_out = min(thickness_at(FOIL, x)[0] for x in (x_pl - P["t"] - 25, x_pl + 25))
        zc = lo_in + 1.0 + P["plate_h"] / 2
        ze = zc + P["lug_zc"]
        t_pl = P.get("t_main33", P["t"]) if tag == "M" else P["t"]     # WP F phase 3.3C: uniform 18 mm main lug
        x0 = x_pl - t_pl
        e_r = P.get("edge_main32", P["lug_w"] / 2) if tag == "M" else P["lug_w"] / 2
        if tag == "M":
            from shapely.geometry import box as _sb, Point as _Pt
            prof = _sb(-P["plate_w"] / 2, zc - P["plate_h"] / 2, P["plate_w"] / 2, zc + P["plate_h"] / 2).union(
                _sb(-P["lug_w"] / 2, ze, P["lug_w"] / 2, zc - P["plate_h"] / 2 + 1)).union(_Pt(0, ze).buffer(e_r, quad_segs=24))
            prof = prof.buffer(10.0, join_style=1, quad_segs=8).buffer(-10.0, join_style=1, quad_segs=8)   # R10 fillets
            plate = prism_x(np.array(prof.exterior.coords)[:-1], x0, x_pl)
            neck = plate
        else:
            plate = box(x0, x_pl, -P["plate_w"] / 2, P["plate_w"] / 2, zc - P["plate_h"] / 2, zc + P["plate_h"] / 2)
            neck = box(x0, x_pl, -P["lug_w"] / 2, P["lug_w"] / 2, ze, zc - P["plate_h"] / 2 + 1)
        eye_t = P.get("eye_t_main", P["t"])                # WP F phase 3/3.1: 14 mm eye boss on both root lugs
        eye_r = P["lug_w"] / 2
        if tag == "M":                                    # WP F phase 3.3C: eye = plate thickness (18 mm), edge distance 34 mm
            eye_t, eye_r = t_pl, P.get("edge_main32", eye_r)
        x0e = x_pl - eye_t
        eye = cyl_x(eye_r, x0e, x_pl, 0, ze)
        fit = (plate + neck + eye) - cyl_x(P["pin_d"] / 2, x0e - 1, x_pl + 1, 0, ze)
        spacer = box(x_pl, x_web, -P["plate_w"] / 2, P["plate_w"] / 2, zc - P["plate_h"] / 2 + tc0 + 1, zc + P["plate_h"] / 2)
        for by, bz in P["bolts"]:
            fit = fit - cyl_x(P["bolt_d"] / 2, x0 - 1, x_pl + 1, by, zc + bz)
            spacer = spacer - cyl_x(P["bolt_d"] / 2, x_pl - 1, x_web + 1, by, zc + bz)
        g = 1.0
        ztop = lo_out - 3.0
        # WP F phase 3.2 redesign: the cheeks stand directly on the bolted plate and run its full height (U-channel),
        # 40 mm flange between the cheeks, gusset under it; bolted plate 24 mm with 6 bolts outside the cheeks
        yp = -(yr - ys_out) + 0.5
        ct, pt_, fl = 12.0, 24.0, 40.0
        xa, xb = x0e - g - ct, x_pl + g + ct
        cheeks = (box(xa, x0e - g, yp, eye_r + 2, ze - 230, ztop) + box(x_pl + g, xb, yp, eye_r + 2, ze - 230, ztop))
        fx0, fx1 = (xa - 40, xb + 40) if tag == "M" else (xa, xb + 80)   # rear clevis: bolt flange aft only (door edge)
        plate_c = box(fx0, fx1, yp, yp + pt_, ze - 230, ze - 45)
        base = box(xa, xb, yp, eye_r + 2, ze - 45 - fl, ze - 45)
        gus = prism_x(np.array([[yp + pt_, ze - 45 - fl], [eye_r + 2, ze - 45 - fl], [yp + pt_, ze - 225]]), x0e - g, x_pl + g)
        clv = cheeks + plate_c + base + gus - cyl_x(P["pin_d"] / 2 + 0.05, x0e - 40, x_pl + 40, 0, ze)
        for bx in ((xa - 20, xb + 20) if tag == "M" else (xb + 20, xb + 60)):
            for bz in (ze - 70, ze - 135, ze - 200):
                clv = clv - cyl_y(4.1, yp - 1, yp + pt_ + 1, bx, bz)
        pin = cyl_x(P["pin_d"] / 2, xa - 8, xb + 8, 0, ze)
        out[tag] = dict(fit=fit, spacer=spacer, clv=clv, pin=pin, eye_t=eye_t, env=box(x0e - 1, x_web, -P["plate_w"] / 2 - 1, P["plate_w"] / 2 + 1,
                                                                           ze - 40, zc + P["plate_h"] / 2 + 1), ze=ze, eye_r=eye_r)
    return out


def root_fittings() -> list[Part]:
    out = []
    yr = WING["root_y"]
    P = FEA_FIT["P1_wing_root_lug"]
    pl = lr(yr)
    for tag, nm in (("M", "main"), ("R", "rear")):
        f = fitting_geometry()[tag]
        out.append(Part(f"W-FIT-{tag}S", f"Wing root lug, {nm} spar (FEA part P1)", "Wing", "CNC", P["material"], f["fit"], pl, "wing",
                        density=rho(P["material"]), machine="cnc_metal",
                        notes=f"Dimensions of WP F part P1 (fea/parts.py): {P['t']:.0f} mm 7075-T6 plate (eye boss {f['eye_t']:.0f} mm) {P['plate_w']:.0f} x "
                              f"{P['plate_h']:.0f} mm, lug {P['lug_w']:.0f} mm wide, pin {P['pin_d']} mm, 8 x AN5 through the spacer "
                              "and the spar web; holes drilled through T-DRILL-RF and reamed; lug exits the lower skin through a slot."))
        out.append(Part(f"W-FIT-{tag}P", f"Root lug spacer, {nm} spar (web to cap edge)", "Wing", "CNC", "al6061_t6_extr", f["spacer"],
                        pl, "wing", density=rho("al6061_t6_extr"), machine="cnc_metal",
                        notes="6061 packer that brings the P1 plate forward of the lower cap so the lug clears the cap; bonded "
                              "to the web with EA 9394 and clamped by the lug bolts."))
        mat_c = "al7075_t6_sheet"                                             # WP F phase 3.1/3.2: clevises in 7075-T6
        out.append(Part(f"F-CLV-{tag}S", f"Fuselage wing-attach clevis, {nm} spar", "Fuselage", "CNC", mat_c, f["clv"], pl,
                        "fuselage", density=rho(mat_c), machine="cnc_metal",
                        notes="Machined 7075-T6 (WP F phase 3.2 redesign): cheeks stand directly on the 24 mm bolted plate as a U-channel with a 40 mm flange and a gusset, 6 x AN5 outside the cheeks; the leg bolts (6 x AN4 through potted inserts) to the outer face of the cabin "
                              "side panel; the clevis sits outside the fuselage OML and is covered by the wing-root fairing F-WRF."))
        out.append(Part(f"W-PIN-{tag}", f"Wing attach pin, {nm} spar (3/4 in close-tolerance bolt)", "Wing", "COTS", "steel_an_bolt",
                        f["pin"], pl, "wing", density=rho("steel_an_bolt"), purchased=True,
                        notes="Close-tolerance bolt with castellated nut and safety pin; removed to de-rig the wing."))
    return out
