"""Booms, boom clamps, the eight identical rotor stations (clamp, pylon plates, motor plate, motor, inverter,
nacelle fairing, rotor) and boom-mounted cooling / harness runs.

Station parts are modelled with the origin on the boom axis under the rotor hub (x fwd/aft along the boom).
Boom-length parts are modelled on the right boom in aircraft coordinates; the left boom is a mirror placement.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from .config import (mass_item, SIZING, FEA_FIT, BOOM_OD, BOOM_X0, BOOM_X1, BOOM_Y, BOOM_Z, BOOMS, CAT, DETAIL, ROTORS, S, SHOP, TAIL, G, Part,
                     mm, place, rho, IDENT, global_to_wing, WING)
from .geom import (tube_between, cyl, box, compound, cyl_x, cyl_y, cyl_z, fuse_all, naca4, offset2d, prism_z, prism_y, rounded_rect,
                   tube_x, thickness_at, loft3d, circle)

TUBE_ID = CAT["MAT-TUBE-DP-4x96"]["ratings"]["id_mm"]
R_BASE_I = TUBE_ID / 2
BASE_WALL = 1.6                                           # catalog tube wall (geometry.json construction note)
R_BASE = R_BASE_I + BASE_WALL
# boom over-wrap segments sized by WP F (fea/results/sizing_update.json): UD + outer +/-45 layer on the COTS tube
SEGS = []
for _sg in (SIZING.get("booms") or [{"segments": []}])[0]["segments"]:
    _L = _sg["section"]["layers"]
    SEGS.append(dict(x0=mm(_sg["x_from"]), x1=mm(_sg["x_to"]), t_ud=sum(l["t"] for l in _L if l["material"] == "cf_ud_wet") * 1000,
                     t45=sum(l["t"] for l in _L if l["material"].startswith("cf_fabric")) * 1000))
if not SEGS:
    SEGS = [dict(x0=BOOM_X0, x1=BOOM_X1, t_ud=BOOM_OD / 2 - R_BASE, t45=0.0)]
R_WRAP = max(R_BASE + s_["t_ud"] + s_["t45"] for s_ in SEGS)   # clamp-station radius (largest sized OD)
FIT = FEA_FIT["P2_boom_clamp"]
CW = FIT["wall"]
CL = FIT["width"]                                         # clamp length along the boom (FEA P2 width)
RO = R_WRAP + CW
PAD_TOP = RO + FIT["pad_t"]
SLEEVE = 300.0
HUB_DZ = mm(ROTORS[0]["hub"][2]) - BOOM_Z                 # hub height above the boom axis
HUB_H = mm(ROTORS[0]["hub_height"])
HUB_D = mm(ROTORS[0]["hub_diameter"])
MOT_D = S["lift_rotors"]["motor_diameter_m"] * 1000
MOT_TOP = HUB_DZ - HUB_H / 2
_MID = S["lift_rotors"]["motor"]["name"].split(":")[0].strip()
EMRAX = "EMRAX" in _MID
MOT_LEN = 91.0 if EMRAX else DETAIL["motor_len"]          # EMRAX 268 datasheet axial length 91 mm
ADP_T = 12.0 if EMRAX else 0.0                            # EMRAX face-mount adapter ring between motor and motor plate
MOT_BOT = MOT_TOP - MOT_LEN
P3 = FEA_FIT["P3_motor_plate"]
MP_BOT = MOT_BOT - ADP_T - P3["t"]
ISO_H = 25.0                                              # elastomeric sandwich mount height (COTS class)
HEAD_T = 8.0
HEAD_TOP = MP_BOT - ISO_H
PYL = SIZING.get("rotor_pylon_section", {"od": 0.1, "t": 0.0016, "material": "al6061_t6_extr"})
PYL_R, PYL_T = mm(PYL["od"]) / 2, mm(PYL["t"])
SOCK_H = 60.0                                             # WP F phase 3.3B: pylon socket depth 60 mm
PYL_Z0 = PAD_TOP + 5.0
PYL_Z1 = HEAD_TOP - HEAD_T - P3["stub_len"]
_R0 = ROTORS[0]
NAC_C = mm(_R0.get("mast_chord", 0.4))
NAC_T = mm(_R0.get("mast_thickness", 0.116))
NAC_X0 = -0.3 * NAC_C                                     # pylon tube at the fairing's thickest section
NAC_BOT = None                                            # set below (top of the saddle socket)
NAC_TOP = HEAD_TOP - HEAD_T - 2.0
_nf = naca4(f"00{int(round(100 * NAC_T / NAC_C)):02d}", NAC_C, 40, te_mm=2.0)
NAC_FOIL = np.column_stack([_nf[:, 0] + NAC_X0, _nf[:, 1]])
BOOM_OD = 2 * R_WRAP                                      # used by the audit for the clamp-station envelope

RIGHT_ROT = [r for r in ROTORS if r["hub"][1] > 0]
ROT_X = [mm(r["hub"][0]) for r in RIGHT_ROT]
WING_CLAMP_X = [mm(x) for x in BOOMS[0]["attach_x"]]
TAIL_X = mm(TAIL["x_spar"])


def boom_joints():
    """Choose splice stations: every piece <= stock length, splices >= keep-out from clamp stations,
    pieces packed into the fewest stock tubes (first-fit decreasing), then fewest pieces."""
    stock = SHOP["tube_stock_mm"] - 5.0
    keep = CL / 2 + SLEEVE / 2 + 10.0
    stations = ROT_X + WING_CLAMP_X + [TAIL_X]
    grid = [x for x in np.arange(BOOM_X0 + 300, BOOM_X1 - 300, 50.0) if all(abs(x - s) >= keep for s in stations)]
    best = None
    L = BOOM_X1 - BOOM_X0
    for k in range(math.ceil(L / stock), 7):
        nj = k - 1
        found = []

        def rec(start, chosen):
            if len(chosen) == nj:
                if BOOM_X1 - start <= stock:
                    found.append(list(chosen))
                return
            for x in grid:
                if x <= start or x - start > stock:
                    continue
                if x - start < 300:
                    continue
                rec(x, chosen + [x])
                if len(found) > 4000:
                    return
        rec(BOOM_X0, [])
        for js in found:
            pts = [BOOM_X0] + js + [BOOM_X1]
            pieces = sorted(np.diff(pts), reverse=True)
            bins = []
            for p in pieces:
                for i, b in enumerate(bins):
                    if b + p + 5 <= stock:
                        bins[i] += p + 5
                        break
                else:
                    bins.append(p)
            score = (len(bins), k, -min(abs(j - s) for j in js for s in stations))
            if best is None or score < best[0]:
                best = (score, js, pieces)
        if best is not None and best[0][0] <= math.ceil(L / stock):
            break
    return best[1], best[0][0]


def boom_parts() -> list[Part]:
    joints, n_stock = boom_joints()
    pts = [BOOM_X0] + joints + [BOOM_X1]
    parts = []
    LR = [IDENT, place(mirror=True)]
    # tube pieces (each a distinct length)
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        t = tube_x(R_BASE, R_BASE_I, a, b, BOOM_Y, BOOM_Z)
        parts.append(Part(f"BM-T{i + 1}", f"Boom tube piece {i + 1} ({b - a:.0f} mm)", "Booms", "COTS-cut",
                          "cf_tube_rollwrapped_twill (MAT-TUBE-DP-4x96)", t, LR, "booms",
                          density=rho("cf_tube_rollwrapped_twill"), purchased=True,
                          notes=f"Cut from 96 in DragonPlate stock (ID {TUBE_ID} mm, {BASE_WALL} mm wall); {n_stock} stock tubes per boom. "
                                "Ends squared in the T-VBLOCK fixture.",
                          joints="spliced to the neighbouring piece with BM-SLV (bonded EA 9394, 150 mm each side)"))
    sl = tube_x(R_BASE_I - 0.1, R_BASE_I - 0.1 - 2.5, -SLEEVE / 2, SLEEVE / 2, 0, 0)
    parts.append(Part("BM-SLV", "Boom internal splice sleeve", "Booms", "composite-layup", "cf_fabric_wet", sl,
                      [place(j, BOOM_Y, BOOM_Z) for j in joints] + [place(j, -BOOM_Y, BOOM_Z) for j in joints], "booms",
                      density=rho("cf_fabric_wet"),
                      notes="Roll-wrapped on a waxed 96 mm aluminium mandrel (10 plies twill), sanded to a 0.1 mm slip fit."))
    # WP F over-wrap segments (UD + outer +/-45); the high-moment segment is extended over the L2/L3 clamps
    xs_seg = [BOOM_X0] + [q["x1"] for q in SEGS[:-1]] + [BOOM_X1]
    if len(SEGS) == 3:
        xs_seg[1] = ROT_X[1] - CL / 2 - 40
        xs_seg[2] = ROT_X[2] + CL / 2 + 40
    seg_r = []
    for k, q in enumerate(SEGS):
        a, b = xs_seg[k], xs_seg[k + 1]
        r1 = R_BASE + q["t_ud"]
        r2 = r1 + q["t45"]
        seg_r.append((a, b, r2))
        ud = tube_x(r1, R_BASE, a, b, BOOM_Y, BOOM_Z)
        bd = [(ud, rho("cf_ud_wet"))]
        sol = [ud]
        if q["t45"] > 0:
            o45 = tube_x(r2, r1, a, b, BOOM_Y, BOOM_Z)
            bd.append((o45, rho("cf_fabric_wet")))
            sol.append(o45)
        parts.append(Part(f"BM-WRAP{k + 1}", f"Boom over-wrap segment {k + 1} (x {a:.0f} to {b:.0f} mm)", "Booms", "composite-layup",
                          "cf_ud_wet + cf_fabric_wet (+/-45)", compound(sol), LR, "booms", bodies=bd,
                          notes=f"WP F sizing: UD {q['t_ud']:.2f} mm + +/-45 {q['t45']:.2f} mm over the 1.6 mm COTS tube, OD "
                                f"{2*r2:.1f} mm; wet-wound, shrink-taped, 50 C post-cure. "
                                + ("Extended over the L2/L3 clamp stations so those clamps sit on this OD." if k == 1 else ""),
                          settings={"lay-up": "UD 0 deg tape, then +/-45 carbon sleeve/fabric outside", "cure": "shrink tape"}))
    band_x = [ROT_X[0], ROT_X[3], TAIL_X]
    for x in band_x:
        rr = [r for a, b, r in seg_r if a <= x < b][0]
        assert rr <= R_WRAP + 1e-6
    rr_min = min(r for _, _, r in seg_r)
    bands = {}
    for x in band_x:
        rr = [r for a, b, r in seg_r if a <= x < b][0]
        bands.setdefault(round(rr, 2), []).append(x)
    for k, (rr, xs_b) in enumerate(sorted(bands.items())):
        band = tube_x(R_WRAP, rr, -CL / 2 - 20, CL / 2 + 20, 0, 0)
        parts.append(Part(f"BM-BAND{k + 1}", f"Boom clamp band to the {2*R_WRAP:.1f} mm clamp OD (on {2*rr:.1f} mm)", "Booms",
                          "composite-layup", "cf_ud_wet", band, [place(x, sg * BOOM_Y, BOOM_Z) for x in xs_b for sg in (1, -1)],
                          "booms", density=rho("cf_ud_wet"),
                          notes="Local UD build-up so all pylon, wing and tail clamps share one bore."))
    # end caps
    nose = loft3d([np.column_stack([np.zeros(48), circle(R_BASE, 0, 0, 48)]),
                   np.column_stack([np.full(48, -90.0), circle(R_BASE * 0.65, 0, 0, 48)]),
                   np.column_stack([np.full(48, -150.0), circle(8.0, 0, 0, 48)])])
    nose = nose + tube_x(R_BASE_I - 0.2, R_BASE_I - 3, 0, 30)
    parts.append(Part("BM-CAP-F", "Boom front cap (with nav-light pocket)", "Booms", "FDM", "asa", nose,
                      [place(BOOM_X0, BOOM_Y, BOOM_Z), place(BOOM_X0, -BOOM_Y, BOOM_Z)], "booms", density=rho("asa") * 0.35,
                      notes="ASA, 3 walls, 15 % gyroid; bonded spigot.", machine="fdm",
                      settings={"material": "ASA", "walls": 3, "infill": "15 % gyroid", "layer": "0.2 mm"}))
    tail = loft3d([np.column_stack([np.zeros(48), circle(R_BASE, 0, 0, 48)]),
                   np.column_stack([np.full(48, 60.0), circle(R_BASE * 0.55, 0, 0, 48)])]) + tube_x(R_BASE_I - 0.2, R_BASE_I - 3, -30, 0)
    if not G.get("pushers"):
      parts.append(Part("BM-CAP-A", "Boom aft cap (tail light)", "Booms", "FDM", "asa", tail,
                      [place(BOOM_X1, BOOM_Y, BOOM_Z), place(BOOM_X1, -BOOM_Y, BOOM_Z)], "booms", density=rho("asa") * 0.35,
                      machine="fdm", settings={"material": "ASA", "walls": 3, "infill": "15 % gyroid"}))
    # internal harness and coolant runs (simplified)
    hv = cyl_x(14.0, ROT_X[0], (BOOM_X1 - 300) if G.get("pushers") else ROT_X[3], BOOM_Y, BOOM_Z + 22)
    L_hv = ROT_X[3] - ROT_X[0]
    parts.append(Part("HV-BOOM", "HV harness run inside the boom (simplified conduit)", "Systems", "COTS", "purchased", hv,
                      LR, "hv_harness", mass_kg=mass_item("HV harness in boom_L"), purchased=True,
                      mass_source="design mass item 'HV harness in boom' (aluminium conductors)",
                      notes="4 x 2-core aluminium-conductor HV cables (one per motor station) with bimetal lugs, in a split loom "
                            "inside the boom; exit through grommets at each pylon."))
    cl = tube_x(8.0, 6.0, ROT_X[0], ROT_X[3], BOOM_Y, BOOM_Z - 25)
    parts.append(Part("COOL-LINE", "Coolant line inside the boom (simplified)", "Systems", "COTS", "purchased", cl, LR,
                      "cooling", mass_kg=(0.20 if EMRAX else 0.25) * mass_item("cooling_L", 4.7), mass_source="share of the design cooling side mass item", purchased=True,
                      notes="16 mm supply/return manifold to the inverter cold plates and motor jackets."))
    pk = box(WING_CLAMP_X[0] + CL / 2 + 10, WING_CLAMP_X[1] - CL / 2 - 10, BOOM_Y - 70, BOOM_Y + 70,
             BOOM_Z - R_WRAP - 170, BOOM_Z - R_WRAP - 10)
    parts.append(Part("COOL-PK", "Cooling pack: radiator, pump, reservoir (placeholder)", "Systems", "COTS", "purchased", pk,
                      LR, "cooling", mass_kg=(0.65 if EMRAX else 0.75) * mass_item("cooling_L", 4.7), mass_source="share of the design cooling side mass item",
                      purchased=True, notes="Hung under the boom between the two wing clamps; scoop fairing in COOL-FAIR."))
    fair = (box(pk.bounding_box().min.X - 4, pk.bounding_box().max.X + 4, BOOM_Y - 78, BOOM_Y + 78,
                BOOM_Z - R_WRAP - 178, BOOM_Z) - box(pk.bounding_box().min.X - 3, pk.bounding_box().max.X + 3,
                                                    BOOM_Y - 77, BOOM_Y + 77, BOOM_Z - R_WRAP - 177, BOOM_Z + 1)
            - cyl_x(R_WRAP + 1, 0, 9000, BOOM_Y, BOOM_Z))
    fair = fair - box(pk.bounding_box().min.X - 5, pk.bounding_box().min.X - 2, BOOM_Y - 60, BOOM_Y + 60,
                      BOOM_Z - R_WRAP - 160, BOOM_Z - R_WRAP - 20)   # inlet
    parts.append(Part("COOL-FAIR", "Cooling pack fairing with inlet", "Systems", "composite-layup", "eglass_fabric_wet", fair, LR,
                      "cooling", density=rho("eglass_fabric_wet"), skin=True,
                      notes="Glass over a CNC foam plug; screwed to the clamp ears with rivnuts."))
    # boom-to-wing clamps
    parts += clamp_parts()
    parts += station_parts()
    return parts


def saddle(slotted=False):
    """FEA part P2 (fea/parts.py saddle): one-piece ring + top pad, bolt holes through the pad (slotted fore-aft if asked)."""
    pad_lo = RO - CW
    ring = cyl_x(RO, -CL / 2, CL / 2)
    pad = box(-CL / 2, CL / 2, -FIT["pad_w"] / 2, FIT["pad_w"] / 2, pad_lo, PAD_TOP)
    s = ring + pad - cyl_x(R_WRAP + 0.15, -CL, CL)
    for x, y in FIT["bolts"]:
        r = FIT["bolt_d"] / 2
        if slotted:
            sl = FIT["slot_len"]
            s = s - (box(x - sl / 2, x + sl / 2, y - r, y + r, pad_lo - 1, PAD_TOP + 1) + cyl_z(r, pad_lo - 1, PAD_TOP + 1, x - sl / 2, y)
                     + cyl_z(r, pad_lo - 1, PAD_TOP + 1, x + sl / 2, y))
        else:
            s = s - cyl_z(r, pad_lo - 1, PAD_TOP + 1, x, y)
    return s


def clamp_parts() -> list[Part]:
    note = ("WP F part P2 geometry (ring wall {w:.0f} mm, width {L:.0f} mm, pad {pw:.0f} x {pt:.0f} mm, 4 x AN6 into potted "
            "inserts at the wing spar cap). One-piece 6061-T6 ring slid on from the boom front end, bore abraded, primed and "
            "bonded (EA 9394) at its station. See validation/cad: the pad and boom crown sit above the wing lower surface.").format(
        w=CW, L=CL, pw=FIT["pad_w"], pt=FIT["pad_t"])
    return [Part("BC-W", "Boom-to-wing saddle clamp, front (main spar)", "Booms", "CNC", FIT["material"], saddle(False),
                 [place(WING_CLAMP_X[0], s_ * BOOM_Y, BOOM_Z) for s_ in (1, -1)], "booms", density=rho(FIT["material"]),
                 notes=note, machine="cnc_metal"),
            Part("BC-WR", "Boom-to-wing saddle clamp, rear (rear spar), slotted holes", "Booms", "CNC", FIT["material"], saddle(True),
                 [place(WING_CLAMP_X[1], s_ * BOOM_Y, BOOM_Z) for s_ in (1, -1)], "booms", density=rho(FIT["material"]),
                 notes=note + f" Rear saddle bolt holes slotted {FIT['slot_len']:.0f} mm fore-aft so boom/wing differential "
                              "strain and tolerance are not forced through the joint (WP F requirement).", machine="cnc_metal")]


def station_inverter():
    """Inverter envelope and its under-boom pod fairing, origin on the boom axis."""
    ib = DETAIL["inverter_box"]
    zb = -RO - 6
    inv = box(-110, -110 + ib[0], -ib[1] / 2, ib[1] / 2, zb - ib[2], zb)
    pf = naca4("0032", 460.0, 40, te_mm=2.0)
    pf = np.column_stack([pf[:, 0] - 160.0, pf[:, 1]])
    po = prism_z(pf, zb - ib[2] - 15, 0.0)
    pod = po - prism_z(offset2d(pf, -1.5), zb - ib[2] - 14, 1.0) - cyl_x(RO + 1, -400, 400)
    return inv, pod


def station_parts() -> list[Part]:
    parts = []
    st = [place(mm(r["hub"][0]), mm(r["hub"][1]), BOOM_Z) for r in ROTORS]
    pc = saddle(False) + (cyl_z(PYL_R + 0.15 + 8, PAD_TOP, PAD_TOP + SOCK_H) - cyl_z(PYL_R + 0.15, PAD_TOP + 5, PAD_TOP + SOCK_H + 1))
    pc_full = pc.volume
    # weight reduction (design/mass_calibration.json): pockets in the pad flanks outside the bolt bosses and the socket,
    # lightening windows in the ring flanks below the pad
    for sx in (1, -1):                                    # lower ring scalloped to a 60 mm wide band
        pc = pc - box(sx * 30 if sx > 0 else -CL / 2 - 1, CL / 2 + 1 if sx > 0 else -30, -RO - 1, RO + 1, -RO - 1, -25)
    for sy in (1, -1):                                    # flank windows in the ring
        for sx in (1, -1):
            pc = pc - cyl_y(13, min(sy * (R_WRAP - 2), sy * (RO + 1)), max(sy * (R_WRAP - 2), sy * (RO + 1)), sx * 27, 8)
    PC_FRAC = 1 - pc.volume / pc_full
    note = "Identical at all 8 stations (L/R and fore/aft)."
    parts.append(Part("PY-C", "Pylon boom saddle with pylon socket", "Rotor stations", "CNC", FIT["material"], pc, st, "rotor_pylons_mounts",
                      density=rho(FIT["material"]), machine="cnc_metal", settings={"_reduction": PC_FRAC},
                      notes=note + " Same P2 saddle as the wing clamps (one bore for all), plus a 60 mm deep, 8 mm wall socket for the pylon tube "
                                   f"(bonded, 2 x AN4 cross-bolts). The lower ring is scalloped to a 60 mm band and the ring flanks have windows: they remove {100*PC_FRAC:.0f} % "
                                   "(mass_calibration target 30 %); WP F to re-check."))
    tube = cyl_z(PYL_R, PYL_Z0, PYL_Z1) - cyl_z(PYL_R - PYL_T, PYL_Z0 - 1, PYL_Z1 + 1)
    parts.append(Part("PY-TUBE", f"Rotor pylon tube {2*PYL_R:.0f} x {PYL_T:.1f} mm", "Rotor stations", "COTS-cut", PYL["material"], tube, st,
                      "rotor_pylons_mounts", density=rho(PYL["material"]), purchased=True,
                      notes=f"6061-T6 drawn tube (WP F rotor_pylon_section); pylon = boom axis to hub {HUB_DZ:.0f} mm; "
                            "internal bonded sleeves at both ends."))
    head = cyl_z(P3["stub_r"], PYL_Z1, PYL_Z1 + P3["stub_len"]) - cyl_z(P3["stub_r"] - P3["stub_wall"], PYL_Z1 - 1, PYL_Z1 + P3["stub_len"] + 1)
    head = head + (cyl_z(P3["R"] - 20, HEAD_TOP - HEAD_T, HEAD_TOP) - cyl_z(P3["stub_r"] - P3["stub_wall"], HEAD_TOP - HEAD_T - 1, HEAD_TOP + 1))
    iso_r = 105.0
    iso_xy = [(iso_r * math.cos(math.radians(30 + 60 * k)), iso_r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    for x, y in iso_xy:
        head = head - cyl_z(4.2, HEAD_TOP - HEAD_T - 1, HEAD_TOP + 1, x, y)
    from .geom import sector_z
    h_full = head.volume
    for k in range(6):
        a = 60 * k
        head = head - sector_z(P3["stub_r"] + 8, P3["R"] - 20 + 1, a + 20, a + 40, HEAD_TOP - HEAD_T - 1, HEAD_TOP + 1)
    PH_FRAC = 1 - head.volume / h_full
    parts.append(Part("PY-HEAD", "Pylon head (P3 stub + isolator flange)", "Rotor stations", "CNC", P3["material"], head, st, "rotor_pylons_mounts",
                      density=rho(P3["material"]), machine="cnc_metal", settings={"_reduction": PH_FRAC},
                      notes=f"Carries the WP F P3 pylon stub (OD {2*P3['stub_r']:.0f}, wall {P3['stub_wall']:.0f}, {P3['stub_len']:.0f} mm) "
                            f"with an 8 mm flange for the six isolators; stub bonded over an internal sleeve in the pylon tube; flange windows between the "
                            f"isolator bosses remove {100*PH_FRAC:.0f} % (target 25 %)."))
    iso = compound([cyl_z(19, HEAD_TOP, MP_BOT, x, y) for x, y in iso_xy])
    parts.append(Part("MP-ISO", "Motor-plate elastomeric isolators (6 per station)", "Rotor stations", "COTS", "purchased (elastomer sandwich mount)",
                      iso, st, "rotor_pylons_mounts", mass_kg=6 * 0.06, mass_source="estimate (6 x 60 g sandwich mounts, M8 studs)", purchased=True,
                      notes=f"Cylindrical rubber-metal sandwich mounts d 38 x {ISO_H:.0f} mm under the motor plate; tune the "
                            "vertical/torsional rates to place the mount modes below 0.7 x 1P at hover rpm; snubbing washers "
                            "limit travel if an isolator fails (WP F to verify)."))
    MP_TOP = MOT_BOT - ADP_T
    mp = cyl_z(P3["R"], MP_BOT, MP_TOP) - cyl_z(P3["centre_d"] / 2, MP_BOT - 1, MP_TOP + 1)
    for k in range(P3["n_bolts"]):
        a = 2 * math.pi * k / P3["n_bolts"]
        mp = mp - cyl_z(P3["bolt_d"] / 2, MP_BOT - 1, MP_TOP + 1, P3["bolt_pcd_r"] * math.cos(a), P3["bolt_pcd_r"] * math.sin(a))
    for x, y in iso_xy:
        mp = mp - cyl_z(4.2, MP_BOT - 1, MP_TOP + 1, x, y)
    m_full = mp.volume
    nb = P3["n_bolts"]
    for k in range(nb):                                   # through windows inside the bolt circle
        a = 360 / nb * k
        mp = mp - sector_z(P3["centre_d"] / 2 + 6, P3["bolt_pcd_r"] - 10, a + 5, a + 360 / nb - 5, MP_BOT - 1, MP_TOP + 1)
    for k in range(6):                                    # rim scallops between the isolator studs
        a = 30 + 60 * k
        mp = mp - sector_z(iso_r + 14, P3["R"] + 1, a + 14, a + 46, MP_BOT - 1, MP_TOP + 1)
    for k in range(6):                                    # half-depth pockets between the bolt circle and the studs
        a = 30 + 60 * k
        mp = mp - sector_z(P3["bolt_pcd_r"] + 9, iso_r + 14, a + 12, a + 48, MP_BOT + 0.3 * P3["t"], MP_TOP + 1)
    MP_FRAC = 1 - mp.volume / m_full
    parts.append(Part("MP", "Motor plate (FEA part P3)", "Rotor stations", "CNC", P3["material"], mp, st, "rotor_pylons_mounts",
                      density=rho(P3["material"]), machine="cnc_metal", settings={"_reduction": MP_FRAC},
                      notes=f"WP F P3: R {P3['R']:.0f} mm, {P3['t']:.0f} mm 6061-T6, {P3['n_bolts']} x M8 motor bolts on PCD "
                            f"{2*P3['bolt_pcd_r']:.0f} (confirm on the REB 50 drawing); six isolator studs at PCD {2*iso_r:.0f}. The P3 "
                            "pylon stub is on PY-HEAD below the isolators; the FEA load path now runs through the isolators. Windows and pockets "
                            f"between the bolt circles remove {100*MP_FRAC:.0f} % (target 50 %, FEA MS +2.8)."))
    if EMRAX:                                             # axial-flux disc: stator housing, rotor flange on top, coolant ports
        mot = cyl_z(MOT_D / 2, MOT_BOT, MOT_TOP - 15) + cyl_z(60, MOT_TOP - 15, MOT_TOP)
        for a in (0.0, 180.0):
            mot = mot + cyl(8, (MOT_D / 2 * math.cos(math.radians(a)) * 0.95, MOT_D / 2 * math.sin(math.radians(a)) * 0.95, MOT_BOT + 30),
                            (math.cos(math.radians(a)), math.sin(math.radians(a)), 0), 25)
        adp = cyl_z(110, MOT_BOT - ADP_T, MOT_BOT) - cyl_z(78, MOT_BOT - ADP_T - 1, MOT_BOT + 1)
        for k in range(8):
            a = math.radians(22.5 + 45 * k)
            adp = adp - cyl_z(4.2, MOT_BOT - ADP_T - 1, MOT_BOT + 1, 95 * math.cos(a), 95 * math.sin(a))
        for k in range(P3["n_bolts"]):
            a = 2 * math.pi * k / P3["n_bolts"]
            adp = adp - cyl_z(4.2, MOT_BOT - ADP_T - 1, MOT_BOT + 1, P3["bolt_pcd_r"] * math.cos(a), P3["bolt_pcd_r"] * math.sin(a))
        parts.append(Part("MP-EMX", "EMRAX face-mount adapter ring", "Rotor stations", "CNC", "al6061_t6_extr", adp, st,
                          "rotor_pylons_mounts", density=rho("al6061_t6_extr"), machine="cnc_metal",
                          notes="12 mm 6061-T6 ring: EMRAX stator bolt circle (confirm on the EMRAX 268 drawing) to the P3 motor-plate "
                                "bolt circle; the motor plate keeps the WP F P3 dimensions."))
        hoses = compound([tube_between((s_ * 60.0, -PYL_R - 12, PYL_Z0 + 20), (s_ * 60.0, -MOT_D / 2 * 0.95 - 20, MOT_BOT + 30), 8, 6)
                          for s_ in (-1, 1)])
        parts.append(Part("COOL-MOT", "Motor coolant hoses (supply/return, per station)", "Rotor stations", "COTS", "purchased", hoses, st,
                          "cooling", mass_kg=0.15 * mass_item("cooling_L", 4.7) / 4, mass_source="15 % of the cooling side mass item / 4 stations",
                          purchased=True, notes="16 mm hoses from the boom manifold up the pylon to the EMRAX coolant ports (liquid-cooled)."))
    else:
        mot = cyl_z(MOT_D / 2, MOT_BOT, MOT_TOP) - cyl_z(MOT_D / 2 - 15, MOT_TOP - 20, MOT_TOP + 1)
        mot = mot + cyl_z(40, MOT_TOP - 20, MOT_TOP)
    mid = _MID
    parts.append(Part("MOT-L", f"Lift motor {S['lift_rotors']['motor']['name'].split(': ')[-1].split(' - ')[0]} (placeholder)", "Rotor stations", "COTS",
                      f"purchased ({mid})", mot, st, "lift_motors", mass_kg=CAT[mid]["mass_kg"], mass_source=f"bom/catalog.json {mid}", purchased=True,
                      notes=f"Diameter {MOT_D:.1f} mm from the catalog; axial length {MOT_LEN:.0f} mm."))
    inv, pod = station_inverter()
    parts.append(Part("INV-L", "Lift inverter MGM HBCi 400800 (placeholder)", "Rotor stations", "COTS", "purchased (INV-HBCI400800)",
                      inv, st, "inverters", mass_kg=CAT["INV-HBCI400800"]["mass_kg"], mass_source="bom/catalog.json INV-HBCI400800",
                      purchased=True, notes="Envelope assumed (catalog gives no dimensions). It does not fit the 116 mm pylon fairing, so it "
                                            "hangs under the boom below the pylon in INV-POD, on a cold plate strapped to the saddle."))
    parts.append(Part("INV-POD", "Inverter pod fairing (under the boom)", "Rotor stations", "composite-layup", "eglass_fabric_wet", pod, st,
                      "rotor_pylons_mounts", density=rho("eglass_fabric_wet"), skin=True,
                      notes="2 plies glass in FDM-printed half moulds; NACA inlet at the front, outlet at the tail; screwed to the saddle."))
    z0 = PAD_TOP + SOCK_H + 1.0
    outer = prism_z(NAC_FOIL, z0, NAC_TOP)
    inner = prism_z(offset2d(NAC_FOIL, -1.5), z0 - 1, NAC_TOP + 1)
    nac = outer - inner
    parts.append(Part("NAC", f"Pylon fairing ({NAC_T:.0f} x {NAC_C:.0f} mm)", "Rotor stations", "composite-layup", "eglass_fabric_wet", nac,
                      st, "rotor_pylons_mounts", density=rho("eglass_fabric_wet"), skin=True,
                      notes="Faired pylon per design/geometry.json (mast thickness/chord): 2 plies glass laid in FDM-printed half moulds "
                            "(T-NAC-M*), split on the x-z plane, joined with a 15 mm joggle.",
                      joints="two halves (left/right) bonded on the centre plane"))
    # rotors
    nb = ROTORS[0]["blades"]
    R = mm(ROTORS[0]["diameter_m"]) / 2
    ch = mm(ROTORS[0]["blade_chord"])
    pitch = ROTORS[0]["blade_pitch_deg"]
    mass_rotor = S["mass_kg"]["breakdown"]["lift_rotors"] / S["lift_rotors"]["count"]
    for spin, nm in ((1, "CCW"), (-1, "CW")):
        sec = naca4("0012", ch, 30)
        sec = np.column_stack([sec[:, 0] - ch * 0.3, sec[:, 1]])
        blades = []
        for k in range(nb):
            bl = prism_y(sec, HUB_D / 2 - 20, R)
            from build123d import Pos, Rot
            bl = bl.moved(Rot(0, -spin * pitch, 0) if True else None)
            bl = bl.moved(Rot(0, 0, 360 * k / nb))
            blades.append(bl.moved(Pos(0, 0, HUB_DZ)))
        hub = cyl_z(HUB_D / 2, HUB_DZ - HUB_H / 2, HUB_DZ + HUB_H / 2)
        rot = compound([hub] + blades)
        sel = [place(mm(r["hub"][0]), mm(r["hub"][1]), BOOM_Z) for r in ROTORS if (r["spin"] == spin)]
        parts.append(Part(f"ROT-{nm}", f"Lift rotor {nm} (E-PROPS ground-adjustable, placeholder)", "Rotor stations", "COTS",
                          "purchased (PROP-EPROPS-UAV-ADJ)", rot, sel, "lift_rotors", mass_kg=mass_rotor,
                          mass_source="selected_design lift_rotors / 8", purchased=True,
                          notes=f"D {2*R:.0f} mm, {nb} blades, chord {ch:.0f} mm, shown stopped at 0 deg azimuth, pitch {pitch} deg; "
                                f"spin {'counter-clockwise' if spin > 0 else 'clockwise'} seen from above."))
    return parts
