"""Fuselage: OML shell panels, canopy and windows, hatches, cabin sandwich structure (floor, side panels,
bulkheads, aft keel), wing-root fairing. Modelled in aircraft coordinates (mm)."""
from __future__ import annotations

import numpy as np
from build123d import Plane, Pos

from .config import (DETAIL, F, FUS_L, PANEL, Part, oml, oml_ring, oml_section_xz, oml_half_width, oml_z_range, mm,
                     place, rho, IDENT, WLOC, WING, CHUTE, BATS, SEATS, G)
from .geom import cyl_x, cyl_y, box, compound, loft3d, prism_x, prism_y, prism_z, offset2d, cyl_z, rounded_rect, fuse_all, superellipse

T_SH = DETAIL["shell_t"]
T_CAN = DETAIL["canopy_t"]
PT = PANEL["t"]
FLOOR_Z = mm(F["cabin"]["floor_z"])
_door = F["cabin"].get("passenger_door")
SILL_Z = mm(_door["sill_z"]) if _door else FLOOR_Z + 530.0   # canopy / door sill height
X_CAB0 = 600.0                              # front of the canopy / cabin shell split
X_COWL = mm(F["tail_cone_cowl"]["x_from"]) if F.get("tail_cone_cowl") else FUS_L   # pusher cowl (part of the OML)
_seat1 = min(SEATS, key=lambda s: s["x"])
_x_feet = mm(_seat1["x"]) + DETAIL["seat_srp_back"] - 760.0          # P95 heel/toe envelope ahead of the pilot SRP
BH_X = {"BH-0": max(120.0, _x_feet - 330.0), "BH-1": min(750.0, _x_feet - 60.0), "BH-2": None, "BH-3": None, "BH-4": None, "BH-5": None, "BH-6": None, "BH-7": 4230.0}
# stations derived from the design: between the packs, behind the passenger seat back, gear, parachute, chute rear
_bs = sorted(BATS, key=lambda b: b["x"])
for _k, (_bA, _bB) in enumerate(zip(_bs[:-1], _bs[1:])):
    BH_X["BH-2" + ("" if _k == 0 else "ABCDEFGHIJ"[_k])] = (mm(_bA["x"]) + mm(_bA["length"]) / 2 + mm(_bB["x"]) - mm(_bB["length"]) / 2) / 2
BH_X = dict(sorted(BH_X.items(), key=lambda kv: kv[1] if kv[1] is not None else 1e9))
_seat2 = max(SEATS, key=lambda s: s["x"])
_cb = G["cargo_bay"]
from .config import FEA_FIT as _FF
BH_X["BH-4"] = mm(G["landing_gear_oml"]["struts"][1]["p1"][0]) - _FF["P4_gear_saddle"]["pad_w"] / 2 - PT / 2 - 2
_can = CHUTE["canister"]
_cl = mm(_can["length"]) / 2 * abs(_can["fire_direction"][0]) / np.linalg.norm(_can["fire_direction"]) + mm(_can["diameter"]) / 2
BH_X["BH-5"] = mm(_can["x"]) + _cl + 40
BH_X["BH-6"] = mm([a for a in CHUTE["attach"] if a["name"] == "chute_rear"][0]["x"])
DOOR_P = (X_CAB0 + 40, None)                # pilot opening, aft end set by the main-spar post
POST_W = 40.0
Y_SIDE = 330.0                              # inner face of the cabin side panels


def _spar_x_global(i):
    from .config import wing_to_global
    xs = WING["spars"][i]["x_c"] * WING["chord"]
    return float(wing_to_global(xs, 0)[0])


X_POST_M = _spar_x_global(0)
X_POST_R = _spar_x_global(1)
X_CAN1 = X_POST_M - POST_W - 30.0           # aft end of the front canopy: clear of the main-spar root lug
DOOR_PILOT = (X_CAB0 + 40, X_CAN1)
if G.get("pushers"):                                   # no fuselage pusher: tail-cone frame behind the rear riser fitting
    BH_X["BH-7"] = max(BH_X["BH-7"], BH_X["BH-6"] + 200.0)
# aft cabin bulkhead: behind the passenger seat back, the cargo bay and the rear-spar wing fittings
BH_X["BH-3"] = max(mm(_seat2["x"]) + DETAIL["seat_srp_back"] + 800 * np.sin(np.radians(15)) + 30,
                   mm(_cb["x_center"]) + mm(_cb["length"]) / 2 + 10, X_POST_R + 80.0)
DOOR_PAX = (mm(_door["x_from"]), mm(_door["x_to"])) if _door else (X_POST_M + POST_W, X_POST_R - POST_W)
if _door:                                    # door aft edge kept clear of the rear-spar clevis (bolt flange aft of the spar)
    DOOR_PAX = (DOOR_PAX[0], min(DOOR_PAX[1], X_POST_R - 50.0))
X_AFT = max(2820.0, DOOR_PAX[1] + 80.0, X_POST_R + 60.0)   # cabin / aft-fuselage shell split: behind the door and rear post


def oml_solid(inset=0.0, x0=0.0, x1=None):
    x1 = FUS_L if x1 is None else x1
    if inset > 0:                                   # keep inner lofts strictly inside closed (zero-width) nose/tail ends
        if oml(x0)[0] < 4 * inset + 4:
            x0 = x0 + 3.0 * inset + 3.0
        if oml(x1)[0] < 4 * inset + 4:
            x1 = x1 - 3.0 * inset - 3.0
    xs = [mm(s["x"]) for s in F["stations"]] + [6.0 + 3.0 * T_SH, FUS_L - 6.0 - 3.0 * T_SH] + list(np.arange(100.0, FUS_L, 250.0))
    xs = sorted(set([x0, x1] + [round(x, 3) for x in xs if x0 + 1 < x < x1 - 1]))   # same station set for every inset
    rings = []
    for x in xs:
        r = oml_ring(x, inset, 48)
        rings.append(np.column_stack([np.full(len(r), x), r]))
    return loft3d(rings, smooth=SMOOTH_OML)


SMOOTH_OML = False
_CACHE = {}


def OML():
    if "oml" not in _CACHE:
        _CACHE["oml"] = oml_solid(0.0)
        _CACHE["in1"] = oml_solid(T_SH, 0.0, FUS_L)
        _CACHE["inc"] = oml_solid(T_CAN, 0.0, FUS_L)
    return _CACHE["oml"], _CACHE["in1"], _CACHE["inc"]


def wing_envelope(grow=1.0):
    from .wing import FOIL, HALF
    return prism_y(offset2d(FOIL, grow), -HALF, HALF).moved(WLOC)


def fuselage_parts() -> list[Part]:
    oml_s, in1, inc = OML()
    shell = oml_s - in1
    can_shell = oml_s - inc
    wing = wing_envelope(2.0)
    big = 3000
    parts = []
    eg = rho("eglass_fabric_wet")
    sh_notes = ("Moldless: 3 plies 300 g/m2 glass wet-laid over the CNC-machined foam plug sections T-PLUG-*, cut on the "
                "centre line, bonded to the cabin structure with flox; joggled lap joints at the station splits.")

    def region(x0, x1, z0=-big, z1=big, y0=-big, y1=big):
        return box(x0, x1, y0, y1, z0, z1)
    # hatches / openings
    h_av = region(150, 550, z0=1200, y0=-170, y1=170)
    h_bat = [region(mm(b["x"]) - mm(b["length"]) / 2 + 10, mm(b["x"]) + mm(b["length"]) / 2 - 10, z1=FLOOR_Z - 80,
                    y0=-280, y1=280) for b in BATS]
    h_ch = region(mm(_can["x"]) - 200, mm(_can["x"]) + 230, z0=mm(_can["z"]) + 20, y0=-210, y1=210)
    _bay = max(((BH_X["BH-5"], BH_X["BH-6"]), (BH_X["BH-4"], BH_X["BH-5"])), key=lambda ab: ab[1] - ab[0])
    h_svc = region(_bay[0] + 80, _bay[1] - 80, z0=900, z1=1350, y0=-big, y1=0)
    win = region(DOOR_PAX[0], DOOR_PAX[1], z0=SILL_Z, z1=big, y0=0, y1=big)
    win_l = win.mirror(Plane.XZ)

    regs = [
        ("SH-NOSE", "Fuselage nose shell", region(-10, X_CAB0) - h_av, "x 0 to front of canopy; avionics hatch cut-out"),
        ("SH-CAB", "Cabin lower shell", region(X_CAB0, X_AFT, z1=SILL_Z) - fuse_all(h_bat), "below the canopy sill; battery access panels cut out"),
        ("SH-MID", "Cabin upper shell / window frames under the wing", region(X_CAN1, X_AFT, z0=SILL_Z) - win - win_l - h_ch, "between the canopy and the aft fuselage, trimmed to the wing"),
        ("SH-AFT", "Aft fuselage shell", region(X_AFT, BH_X["BH-7"]) - h_ch - h_svc - fuse_all(h_bat), "parachute hatch and service door cut out"),
        ("SH-TAIL", "Tail cone shell", region(BH_X["BH-7"], X_COWL), "ahead of the pusher cowl"),
    ]
    from .gear import ST as _ST, R_XT as _RXT
    xslots = [box(mm(s_["p1"][0]) - _RXT - 5, mm(s_["p1"][0]) + _RXT + 5, -mm(s_["p2"][1]) - 120, mm(s_["p2"][1]) + 120, 0,
                  mm(s_["p2"][2]) + _RXT + 5) for s_ in _ST]
    # local notch in the aft shell around the rear parachute hard point (CH-ATT-R eye plate)
    from .config import FEA_FIT as _F5
    _P5 = _F5["P5_parachute_hardpoint"]
    _ra = [a for a in CHUTE["attach"] if a["name"] == "chute_rear"][0]
    _xr = BH_X["BH-6"] + PT / 2 + 6 + _P5["plate_w"] / 2
    _zr = mm(_ra["z"]) - _P5["eye_zc"]
    ch_notch = box(_xr - _P5["plate_w"] / 2 - 5, _xr + _P5["plate_w"] / 2 + 5, -_P5["neck_w"] / 2 - 5, _P5["neck_w"] / 2 + 5,
                   _zr - _P5["plate_h"] / 2 - 5, _zr + _P5["eye_zc"] + _P5["neck_w"] / 2 + 5)
    regs = [(a, b, (r - ch_notch) if a == "SH-AFT" else r, n) for a, b, r, n in regs]
    for pid, nm, reg, note in regs:
        s = (shell & reg) - wing
        for xs_ in xslots:
            s = s - xs_
        parts.append(Part(pid, nm, "Fuselage", "composite-layup", "eglass_fabric_wet", s, [IDENT], "fuselage", density=eg,
                          skin=True, notes=f"{note}. {sh_notes}", joints="left/right halves bonded on the keel and crown lines"))
    for pid, nm, reg in (("HATCH-AV", "Avionics bay hatch (nose top)", h_av), ("HATCH-CH", "Parachute frangible hatch", h_ch),
                         ("HATCH-SVC", "Aft fuselage service door (left)", h_svc)):
        s = shell & reg
        parts.append(Part(pid, nm, "Fuselage", "composite-layup", "eglass_fabric_wet", s, [IDENT], "fuselage", density=eg,
                          skin=True, notes="Cut from the shell after cure, 15 mm joggle flange bonded on; camlock fasteners"
                                           + (" (hatch is a frangible tear-away panel the rocket fires through)" if pid == "HATCH-CH" else "")))
    for i, hb in enumerate(h_bat):
        s = shell & hb
        for xs_ in xslots:
            s = s - xs_
        parts.append(Part(f"HATCH-BAT{'ABCDEFGHIJ'[i]}", f"Battery access panel {'ABCDEFGHIJ'[i]} (belly)", "Fuselage", "composite-layup",
                          "eglass_fabric_wet", s, [IDENT], "fuselage", density=eg, skin=True,
                          notes="Removable belly panel, 10 x camlock; opening for pack removal downwards."))
    # canopy, door glazing, fixed left window
    cf = (can_shell & region(X_CAB0, X_CAN1, z0=SILL_Z)) - wing
    parts.append(Part("CAN-F", "Front canopy (pilot), hinged right", "Fuselage", "outsourced-thermoform", "polycarbonate",
                      cf, [IDENT], "fuselage", density=rho("polycarbonate"), skin=True,
                      notes=f"{T_CAN} mm PC drape-formed by a plastics shop over the CNC MDF plug T-CAN-PLUG*; trimmed in-house "
                            "with printed trim templates; edges drilled oversize, rubber grommets; bonded into CAN-FRM.",
                      settings={"sheet": "CAB-PC-SHEET 0.125 x 48 x 96 in, one sheet per canopy",
                                "forming": "outsourced drape/blow forming, PC dried 120 C 12 h"}))
    from .wing import fitting_geometry as _fg
    _c = _fg()["R"]["clv"]
    notch = []
    for m_ in (False, True):
        cc = (_c.mirror(Plane.XZ) if m_ else _c).moved(WLOC * Pos(0, -WING["root_y"] if m_ else WING["root_y"], 0))
        bb_ = cc.bounding_box()
        notch.append(box(bb_.min.X - 8, bb_.max.X + 8, bb_.min.Y - 8, bb_.max.Y + 8, bb_.min.Z - 8, bb_.max.Z + 8))
    win = win - notch[0] - notch[1]
    win_l = win_l - notch[0] - notch[1]
    cr = (can_shell & win) - wing
    parts.append(Part("CAN-R", "Passenger door glazing (right), hinged right", "Fuselage", "outsourced-thermoform", "polycarbonate",
                      cr, [IDENT], "fuselage", density=rho("polycarbonate"), skin=True,
                      notes="Single-curvature PC cold-curved into the door frame; the door is the second canopy piece."))
    cl = (can_shell & win_l) - wing
    parts.append(Part("WIN-L", "Passenger window (left, fixed)", "Fuselage", "outsourced-waterjet", "polycarbonate", cl, [IDENT],
                      "fuselage", density=rho("polycarbonate"), skin=True, notes="Flat-cut PC cold-curved into the frame."))
    # canopy frame: 40 mm band of the shell around the front canopy opening
    band = region(X_CAB0 - 40, X_CAB0, z0=SILL_Z - 40) + region(X_CAN1 - 40, X_CAN1, z0=SILL_Z - 40) + \
        region(X_CAB0, X_CAN1, z0=SILL_Z - 40, z1=SILL_Z)
    frm = ((oml_solid(T_CAN, X_CAB0 - 60, X_POST_M + 20) - oml_solid(T_CAN + 8, X_CAB0 - 61, X_POST_M + 21)) & band) - wing
    parts.append(Part("CAN-FRM", "Front canopy frame", "Fuselage", "composite-layup", "cf_fabric_wet", frm, [IDENT], "fuselage",
                      density=rho("cf_fabric_wet"),
                      notes="8 mm carbon/foam hat-section frame laid up on the canopy plug edge; carries the hinges and latch."))
    # canopy hinges and latches
    zh = SILL_Z
    yh = oml_half_width((X_CAB0 + X_POST_M) / 2, zh)
    hg = box(-40, 40, -10, 10, -25, 25) - cyl_x(4.1, -50, 50, 0, 0)
    hpl = [place(x, yh, zh) for x in (X_CAB0 + 150, X_POST_M - 200)] + [place(x, yh, zh) for x in (DOOR_PAX[0] + 80, DOOR_PAX[1] - 80)]
    parts.append(Part("CAN-HINGE", "Canopy / door hinge", "Fuselage", "CNC", "al6061_t6_sheet", hg, hpl, "fuselage",
                      density=rho("al6061_t6_sheet"), machine="cnc_metal", notes="6061-T6, AN4 pin, jettison pin pull."))
    lt = box(-30, 30, -12, 12, -20, 20)
    parts.append(Part("CAN-LATCH", "Canopy / door latch (COTS)", "Fuselage", "COTS", "purchased", lt,
                      [place((X_CAB0 + X_POST_M) / 2, -yh, zh), place((DOOR_PAX[0] + DOOR_PAX[1]) / 2, yh, zh + 300)], "fuselage",
                      mass_kg=0.25, mass_source="estimate", purchased=True))
    # pusher cowl: the aft end of the OML (iteration 3 puts the cowl inside the fuselage stations)
    if F.get("tail_cone_cowl"):
        cow = shell & region(X_COWL, FUS_L + 10)
        parts.append(Part("PM-COWL", "Pusher motor cowl (aft end of the fuselage OML)", "Pusher", "composite-layup", "eglass_fabric_wet", cow,
                          [IDENT], "fuselage", density=eg, skin=True,
                          notes="Glass over the last plug section; open aft end around the motor, cooling exit slots; quick-release "
                                "fasteners for motor access."))
    parts += structure_parts(wing)
    return parts


def _bulkhead(x, inset=T_SH + 0.5):
    r = oml_ring(x, inset, 64)
    return prism_x(r, x - PT / 2, x + PT / 2)


def structure_parts(wing) -> list[Part]:
    parts = []
    big = 3000
    dens = PANEL["rho"]
    lbl = PANEL["label"]
    note = ("Flat sandwich panel laminated as a full sheet on the vacuum table, CNC-routed with tabs/slots, "
            "bonded with flox fillets and 2 x 45 deg glass tapes; potted aluminium inserts at every bolt.")
    y_side = Y_SIDE
    # ---- floor
    x_pack_end = max(mm(b_["x"]) + mm(b_["length"]) / 2 for b_ in BATS)
    xf0, xf1 = BH_X["BH-1"] + PT / 2, max(BH_X["BH-3"] - PT / 2, x_pack_end + 20)
    xs = np.linspace(xf0, xf1, 60)
    hw = [min(y_side, oml_half_width(x, FLOOR_Z + PT) - T_SH - 2) for x in xs]
    poly = np.vstack([np.column_stack([xs, hw]), np.column_stack([xs[::-1], -np.array(hw)[::-1]])])
    floor = prism_z(poly, FLOOR_Z, FLOOR_Z + PT)
    tab_x = np.linspace(xf0 + 200, xf1 - 200, 4)
    for x in tab_x:
        for s in (1, -1):
            floor = floor + box(x - 30, x + 30, min(s * y_side, s * (y_side + PT)), max(s * y_side, s * (y_side + PT)), FLOOR_Z, FLOOR_Z + PT)
    for k_, xb2 in BH_X.items():
        if not k_.startswith("BH-2"):
            continue
        for y0, y1 in ((-200, -140), (140, 200)):
            floor = floor - box(xb2 - PT / 2 - 0.2, xb2 + PT / 2 + 0.2, y0 - 0.2, y1 + 0.2, FLOOR_Z - 1, FLOOR_Z + PT + 1)
    parts.append(Part("FLOOR", "Cabin floor", "Cabin structure", "CNC", lbl, floor, [IDENT], "fuselage", density=dens,
                      notes=note + " Seat rails and battery lids bolt through it.", machine="cnc"))
    # ---- side panels (right; left is the mirror)
    sec = oml_section_xz(y_side + PT, BH_X["BH-1"] - 100, 3200, inset=T_SH + 4)
    from shapely.geometry import Polygon, box as sbox
    pg = Polygon(sec).intersection(sbox(BH_X["BH-1"], FLOOR_Z, 3200, 3000))
    for d in (DOOR_PILOT, DOOR_PAX):
        pg = pg.difference(sbox(d[0], SILL_Z, d[1], 3000))
    pg = pg.difference(sbox(-1000, -1000, BH_X["BH-1"] + 200, SILL_Z - 380))   # pilot leg room ahead of the floor tabs
    pg = pg.union(Polygon(sec).intersection(sbox(BH_X["BH-1"], FLOOR_Z, BH_X["BH-1"] + 200, SILL_Z)))
    if pg.geom_type != "Polygon":
        pg = max(pg.geoms, key=lambda g: g.area)
    pts = np.array(pg.exterior.coords)[:-1]
    side = prism_y(pts, y_side, y_side + PT) - wing
    for x in tab_x:
        side = side - box(x - 30.2, x + 30.2, y_side - 1, y_side + PT + 1, FLOOR_Z - 0.2, FLOOR_Z + PT + 0.2)
    parts.append(Part("SIDE", "Cabin side panel (wing-post panel)", "Cabin structure", "CNC", lbl, side, [IDENT, place(mirror=True)],
                      "fuselage", density=dens, machine="cnc",
                      notes=note + " Carries the wing-attach clevises F-CLV-* on the posts at the spar stations, the canopy "
                                   "sill and the floor tabs; the passenger-door opening sits between the two posts.",
                      joints=("length > CNC bed: routed in two pieces joined with a 100 mm scarf + 2-ply doubler at x = "
                              f"{(DOOR_PILOT[1] + X_POST_M) / 2:.0f} mm (inside the main-spar post)")))
    # ---- bulkheads
    for pid, x in BH_X.items():
        b = _bulkhead(x)
        nm = ""
        if pid == "BH-0":
            b = b - prism_x(rounded_rect(120, 80, 20, 0, oml(x)[2]), x - 10, x + 10)
            nm = "Nose bulkhead (avionics bay front, crush-zone back-up)"
        elif pid == "BH-1":
            b = b & box(x - 10, x + 10, -big, big, -big, 1000)
            b = b - box(x - 10, x + 10, -180, 180, FLOOR_Z + PT + 1, 950)
            nm = "Forward cabin bulkhead (rudder-pedal / footwell bulkhead)"
        elif pid.startswith("BH-2"):
            b = b & box(x - 10, x + 10, -big, big, -big, FLOOR_Z)
            b = b + box(x - PT / 2, x + PT / 2, -200, -140, FLOOR_Z, FLOOR_Z + PT) + box(x - PT / 2, x + PT / 2, 140, 200, FLOOR_Z, FLOOR_Z + PT)
            nm = "Under-floor bulkhead between the battery packs"
        elif pid == "BH-3":
            b = b - prism_x(rounded_rect(440, 520, 60, 0, FLOOR_Z + 330), x - 10, x + 10)
            nm = "Aft cabin bulkhead (behind the passenger seat; harness and cargo tie-down back-up)"
        elif pid in ("BH-4", "BH-5", "BH-6"):
            r_in = oml_ring(x, T_SH + 0.5 + 60, 64)
            b = b - prism_x(r_in, x - 10, x + 10)
            nm = {"BH-4": "Gear / parachute forward frame", "BH-5": "Parachute aft frame",
                  "BH-6": "Parachute rear riser frame"}[pid]
        elif pid == "BH-7":
            b = b - prism_x(rounded_rect(110, 110, 30, 0, oml(x)[2]), x - 10, x + 10)
            nm = "Pusher mount bulkhead" if not G.get("pushers") else "Tail-cone frame"
        b = b - wing
        over_pack = any(abs(x - mm(b_["x"])) < mm(b_["length"]) / 2 + PT / 2 + 1 for b_ in BATS)
        if over_pack and not pid.startswith("BH-2"):
            b = b & box(x - 10, x + 10, -3000, 3000, FLOOR_Z + PT, 4000)      # a pack below: frame above the floor only
            nm += " (above the floor; a battery pack runs under it)"
        if xf0 < x < xf1:
            b = b - box(x - 10, x + 10, -y_side, y_side, FLOOR_Z - 0.2, FLOOR_Z + PT + 0.2) - floor
        parts.append(Part(pid, f"{nm} at x = {x:.0f} mm", "Cabin structure", "CNC", lbl, b, [IDENT], "fuselage", density=dens,
                          notes=note, machine="cnc"))
    # ---- half-lap notches where the side panels cross the full bulkheads
    for q in parts:
        if q.pid in ("BH-1", "BH-3", "BH-4"):
            x = BH_X[q.pid]
            zl = SILL_Z - 200.0
            for s_ in parts:
                if s_.pid == "SIDE":
                    s_.solid = s_.solid - box(x - PT / 2 - 0.2, x + PT / 2 + 0.2, Y_SIDE - 0.2, Y_SIDE + PT + 0.2, -1000, zl)
            for sg in (1, -1):
                q.solid = q.solid - box(x - PT / 2 - 1, x + PT / 2 + 1, min(sg * (Y_SIDE - 0.2), sg * (Y_SIDE + PT + 0.2)),
                                        max(sg * (Y_SIDE - 0.2), sg * (Y_SIDE + PT + 0.2)), zl, 3000)
    # ---- aft keel (vertical centre panel from the aft cabin bulkhead to the pusher bulkhead)
    xk0 = max(BH_X["BH-3"] + PT / 2, x_pack_end + 20)
    sec = oml_section_xz(PT / 2, xk0, BH_X["BH-7"], inset=T_SH + 5)
    pg = Polygon(sec).intersection(sbox(xk0, -1000, BH_X["BH-7"] - PT / 2, 950))
    keel = prism_y(np.array(pg.exterior.coords)[:-1], -PT / 2, PT / 2)
    for pid in ("BH-4", "BH-5", "BH-6"):
        x = BH_X[pid]
        if x > xk0:
            keel = keel - box(x - PT / 2 - 0.2, x + PT / 2 + 0.2, -10, 10, -1000, 3000)
    from .gear import ST as _ST, R_XT as _RXT
    keel = keel - cyl_y(_RXT + 5, -20, 20, mm(_ST[1]["p1"][0]), mm(_ST[1]["p2"][2]))
    from .config import sandwich as _sw
    kp = _sw(face_t=0.75)                                  # WP F phase 3.3: keel webs 6 plies (3 per face)
    parts.append(Part("AF-KEEL", "Aft fuselage keel panel", "Cabin structure", "CNC", kp["label"], keel, [IDENT], "fuselage",
                      density=kp["rho"], notes=note + " Half-lap slots into BH-4..BH-6; 3 plies each face (WP F phase 3.3).", machine="cnc"))
    ring_ = pg.difference(pg.buffer(-4.5)).intersection(sbox(xk0 + 15, -1000, BH_X["BH-7"] - PT / 2 - 15, 3000))
    caps = [np.array(g_.exterior.coords)[:-1] for g_ in (getattr(ring_, "geoms", None) or [ring_]) if g_.area > 100]
    cap_s = compound([prism_y(c_, -20, 20) for c_ in caps])
    for pid_ in ("BH-4", "BH-5", "BH-6"):
        if BH_X[pid_] > xk0:
            cap_s = cap_s - box(BH_X[pid_] - PT / 2 - 0.2, BH_X[pid_] + PT / 2 + 0.2, -30, 30, -1000, 3000)
    for q in parts:
        if q.pid == "AF-KEEL":
            q.solid = q.solid - prism_y(np.array(pg.buffer(0).exterior.coords)[:-1], -25, 25) + \
                (q.solid & prism_y(np.array(pg.buffer(-4.5).exterior.coords)[:-1], -25, 25))
    parts.append(Part("AF-KEEL-CAP", "Aft keel caps (UD carbon, top and bottom edges)", "Cabin structure", "composite-layup", "cf_ud_wet",
                      cap_s, [IDENT], "fuselage", density=rho("cf_ud_wet"),
                      notes="40 x 4.5 mm UD carbon caps wet-laid over the keel edges (WP F phase 3.3), wrapped onto the faces 20 mm."))
    # ---- split the floor and the side panels to the router bed / sheet length (WP F phase 3.2 shop check)
    from .config import SHOP as _SHOP
    lim = _SHOP["cnc_bed_mm"][0]
    out = []
    for q in parts:
        bb = q.solid.bounding_box()
        if q.pid in ("FLOOR", "SIDE") and bb.size.X > lim:
            if q.pid == "FLOOR":
                cands = [v for k, v in BH_X.items() if k.startswith("BH-2")]
                xs_ = min(cands, key=lambda v: abs(v - (bb.min.X + bb.max.X) / 2))
                where = "over the under-floor bulkhead at x = %.0f mm" % xs_
            else:
                xs_ = X_POST_M
                where = "at the main-spar post, x = %.0f mm" % xs_
            for tag, (a, b) in (("F", (bb.min.X - 1, xs_)), ("A", (xs_, bb.max.X + 1))):
                piece = q.solid & box(a, b, -3000, 3000, -3000, 4000)
                out.append(Part(f"{q.pid}-{tag}", f"{q.name}, {'front' if tag == 'F' else 'aft'} piece", q.group, q.process, q.material,
                                piece, q.placements, q.mass_group, notes=q.notes, density=q.density, machine=q.machine,
                                joints=f"butt splice {where}: 100 mm 4:1 scarf in the faces + 2-ply carbon doubler ({q.pid}-DBL)"))
            if q.pid == "FLOOR":
                dbl = box(xs_ - 60, xs_ + 60, -Y_SIDE, Y_SIDE, FLOOR_Z - 1.0, FLOOR_Z) - box(xs_ - PT / 2 - 0.2, xs_ + PT / 2 + 0.2,
                                                                                             -Y_SIDE - 1, Y_SIDE + 1, FLOOR_Z - 2, FLOOR_Z + 1)
            else:
                z0_, z1_ = bb.min.Z, bb.max.Z
                dbl = box(xs_ - 60, xs_ + 60, Y_SIDE - 1.0, Y_SIDE, z0_, z1_) & q.solid.moved(Pos(0, -1.0, 0))
            out.append(Part(f"{q.pid}-DBL", f"{q.name} splice doubler", q.group, "composite-layup", "cf_fabric_wet", dbl, q.placements,
                            q.mass_group, density=rho("cf_fabric_wet"),
                            notes="2 plies 200 g/m2 carbon, 120 mm wide, wet-laid over the scarfed splice on the inner face."))
        else:
            out.append(q)
    parts[:] = out
    # ---- wing-root fairing (fills between the OML and the root fittings outside it)
    oml_s = OML()[0]
    reg = box(WING["xle"] - 30, WING["xle"] + WING["chord"] + 60, 150, WING["root_y"] + 60, SILL_Z + 180, 1900)
    from .wing import FOIL
    from .config import wing_to_global
    i0 = int(np.argmin(FOIL[:, 0]))
    low = np.array([wing_to_global(x, z)[[0, 2]] for x, z in FOIL[i0:]])
    above = np.vstack([[[low[0, 0] - 200, low[0, 1]]], low, [[low[-1, 0] + 200, low[-1, 1]], [low[-1, 0] + 200, 2600],
                                                           [low[0, 0] - 200, 2600]]])
    wrf = reg - oml_s - wing - prism_y(above, -big, big)
    from .config import wing_to_global as _w2g
    from .wing import FOIL as _F
    from .geom import thickness_at as _ta
    _xs = WING["spars"][0]["x_c"] * WING["chord"]
    _zf = _w2g(_xs, _ta(_F, _xs)[0])[2] - 60.0
    if wrf.volume < 2.0e5 or oml_half_width(_w2g(_xs, 0)[0], _zf) >= WING["root_y"] - 5:
        return parts                             # the OML shoulder fairing already covers the root fittings
    area = wrf.area
    parts.append(Part("F-WRF", "Wing-root fairing (covers the root fittings)", "Fuselage", "composite-layup", "eglass_fabric_wet",
                      wrf, [IDENT, place(mirror=True)], "fuselage", mass_kg=area / 2 * 1.0e-9 * 1.0 * rho("eglass_fabric_wet"),
                      mass_source="shell: half the envelope area x 1.0 mm glass", skin=True,
                      notes="Glass over a CNC foam plug, screwed to the wing lower skin and the fuselage shell; removed to de-rig."))
    return parts
