"""H-tail between the booms and the two ventral fins: cores/skins, control surfaces, spars, boom fittings."""
from __future__ import annotations

import numpy as np

from .config import BOOM_Y, BOOM_Z, DETAIL, TAIL, Part, mm, place, rho, IDENT
from .geom import box, compound, cyl_y, cyl_z, naca4, offset2d, prism_y, prism_z, clip2d, thickness_at, tube_y, tube_z
from .booms import R_WRAP, CW, CL
from .config import mass_item

H = TAIL["horizontal"][0]
V = TAIL["vertical"][0]
HC = mm(H["root_chord"])
HX = mm(H["x_le_root"])
HZ = mm(H["z_root"])
VC = mm(V["root_chord"])
VX = mm(V["x_le_root"])
VZ0 = mm(V["z_root"])
XSP = mm(TAIL["x_spar"])
from .config import SIZING
from .config import FEA_31
_TSP = dict(SIZING.get("tail", {}).get("spar_section", TAIL["spar_section"]))
_TSP["t"] = max(_TSP["t"], FEA_31["ht_spar_t"])          # WP F phase 3.1: 50 x 2.48 mm
SP_R = mm(_TSP["od"]) / 2
SP_T = mm(_TSP["t"])
H_FOIL = H["airfoil"] if H["airfoil"] == FEA_31["ht_airfoil"] or "14" in H["airfoil"] else FEA_31["ht_airfoil"]
FIN_SP_R = 20.0
SKT = DETAIL["ctrl_skin_t"]
GAP = DETAIL["ctrl_gap"]
RING = R_WRAP + CW
Y_PANEL = BOOM_Y - R_WRAP - GAP                 # panel tips run to the boom surface outside the clamp
SOCK_L = 110.0                                  # WP F phase 3.3: spar sockets 110 mm long (bearing)
Y_NOTCH = BOOM_Y - R_WRAP - 1.0 - SOCK_L        # panel end where the clamp boss sits
XC0, XC1 = XSP - CL / 2, XSP + CL / 2


def _surface(foil_xz, span0, span1, hinge_x, axis="y"):
    """Fixed surface (skin + core) and moving surface for a prism along y (HT)."""
    fixed = clip2d(foil_xz, xmax=hinge_x - GAP)
    return fixed


def tail_parts() -> list[Part]:
    parts = []
    LR = [IDENT, place(mirror=True)]
    # ---------------- horizontal stabiliser (fixed part, one piece between the clamps)
    foil = naca4(H_FOIL[4:], HC, 50)
    foil_g = np.column_stack([foil[:, 0] + HX, foil[:, 1] + HZ])
    xh = HX + (1 - H["elevator_chord_fraction"]) * HC
    fixed = clip2d(foil_g, xmax=xh - GAP)
    fin_ = offset2d(fixed, -SKT)
    outer = prism_y(fixed, -Y_PANEL, Y_PANEL)
    inner = prism_y(fin_, -Y_PANEL + SKT, Y_PANEL - SKT)
    notch = box(XC0 - 10, XC1 + 10, Y_NOTCH, Y_PANEL + 5, HZ - 100, HZ + 100)
    notch = notch + notch.mirror(__import__("build123d").Plane.XZ)
    skin = outer - inner - notch
    core = inner - notch - cyl_y(SP_R + 0.3, -2000, 2000, XSP, HZ)
    parts.append(Part("HT", "Horizontal stabiliser (foam core, carbon skin)", "Tail", "composite-layup",
                      "cf_fabric_wet skin on xps_foam core", compound([skin, core]), [IDENT], "tail",
                      bodies=[(skin, rho("cf_fabric_wet")), (core, rho("xps_foam"))], skin=False,
                      notes=f"Hot-wire cores on T-HW-HT (constant chord {HC:.0f} mm) in 3 lengths of <= 1.2 m, spar tunnel cut with a "
                            f"hot tube; 0.6 mm carbon skin; notched at the tail clamps. Section {H_FOIL.upper()} (WP F phase 3.1 / sizing; "
                            f"design/geometry.json still lists {H['airfoil']}).",
                      joints="cores butt-bonded at 2 span stations; skin continuous"))
    ef = clip2d(foil_g, xmin=xh + GAP)
    lo, hi = thickness_at(foil_g, xh + GAP + 1)
    e_in = offset2d(ef, -SKT)
    el_skin = prism_y(ef, -Y_PANEL, Y_PANEL) - prism_y(e_in, -Y_PANEL + SKT, Y_PANEL - SKT)
    el_core = prism_y(e_in, -Y_PANEL + SKT, Y_PANEL - SKT)
    parts.append(Part("ELEV", "Elevator (one piece)", "Tail", "composite-layup", "cf_fabric_wet skin on xps_foam core",
                      compound([el_skin, el_core]), [IDENT], "tail",
                      bodies=[(el_skin, rho("cf_fabric_wet")), (el_core, rho("xps_foam"))],
                      notes=f"{H['elevator_chord_fraction']*100:.0f} % chord, full span between the booms; 4 hinges."))
    spar = tube_y(SP_R, SP_R - SP_T, -(BOOM_Y - R_WRAP - 2), BOOM_Y - R_WRAP - 2, XSP, HZ)
    parts.append(Part("HT-SPAR", "Horizontal-tail spar tube", "Tail", "COTS-cut", TAIL["spar_section"]["material"], spar, [IDENT],
                      "tail", density=rho(TAIL["spar_section"]["material"]), purchased=True,
                      notes=f"Roll-wrapped twill tube {2*SP_R:.0f} x {SP_T:.2f} mm (WP F sizing) cut to length; bonded into the TL-CLAMP sockets.",
                      joints="one piece, 2.4 m stock + bonded internal sleeve at the centre if 96 in stock is used"))
    # ---------------- tail clamp with HT-spar and fin-spar sockets (right; left is the mirror)
    from .geom import cyl_x
    xf = VX + 0.3 * VC
    ring = cyl_x(RING, XC0, XC1, BOOM_Y, BOOM_Z)
    SOCK_W = 10.0                                         # WP F phase 3.2: socket wall 10 mm
    boss_h = cyl_y(SP_R + 0.15 + SOCK_W, Y_NOTCH + 2, BOOM_Y - 20, XSP, HZ)
    boss_v = cyl_z(FIN_SP_R + 0.15 + SOCK_W, BOOM_Z - R_WRAP - 1 - SOCK_L, BOOM_Z - 20, xf, BOOM_Y)
    tc = ring + boss_h + boss_v
    tc = tc - cyl_x(R_WRAP + 0.15, XC0 - 10, XC1 + 10, BOOM_Y, BOOM_Z)
    tc = tc - cyl_y(SP_R + 0.15, Y_NOTCH, BOOM_Y - R_WRAP - 1, XSP, HZ)
    tc = tc - cyl_z(FIN_SP_R + 0.15, BOOM_Z - R_WRAP - 2 - SOCK_L, BOOM_Z - R_WRAP - 1, xf, BOOM_Y)
    v_full = tc.volume
    for sx in (-1, 1):                                    # ring flank windows outside the spar sockets
        for zz in (1, -1):
            tc = tc - cyl_y(19, BOOM_Y + R_WRAP - 2, BOOM_Y + RING + 1, XSP + sx * 33, BOOM_Z + zz * 28)
    # (phase 3.2: no stepped crown; the only windows are on the outboard flank, > 20 mm from both sockets)
    TC_FRAC = 1 - tc.volume / v_full
    parts.append(Part("TL-CLAMP", "Tail clamp (boom, HT-spar socket, fin-spar socket)", "Tail", "CNC", "al6061_t6_extr", tc, LR,
                      "tail", density=rho("al6061_t6_extr"), machine="cnc_metal", settings={"_reduction": TC_FRAC},
                      notes="Machined from 6061-T6 block, split on the vertical plane through the boom axis (4 x AN4 above and "
                            "below the boom); bonded to the boom band BM-BAND; sockets (10 mm wall) bonded and cross-bolted to the spars. "
                            f"Outboard flank windows only (> 20 mm from the sockets) remove {100*TC_FRAC:.0f} %."))
    # ---------------- ventral fins + rudders
    vf = naca4(V["airfoil"][4:], VC, 50)
    vf_g = np.column_stack([vf[:, 0] + VX, vf[:, 1]])          # (x, y-offset)
    xr = VX + (1 - V["rudder_chord_fraction"]) * VC
    z_top = BOOM_Z - R_WRAP - GAP
    ffix = clip2d(vf_g, xmax=xr - GAP)
    f_in = offset2d(ffix, -SKT)
    fo = prism_z(ffix, VZ0, z_top) - prism_z(f_in, VZ0 + SKT, z_top - SKT)
    fcore = prism_z(f_in, VZ0 + SKT, z_top - SKT)
    fn = box(XC0 - 10, XC1 + 10, -100, 100, BOOM_Z - R_WRAP - SOCK_L - 3, z_top + 10)
    fo, fcore = fo - fn, fcore - fn - cyl_z(FIN_SP_R + 0.3, 0, 3000, xf, 0)
    from build123d import Pos
    fin_pl = [place(0, BOOM_Y, 0), place(0, -BOOM_Y, 0)]
    parts.append(Part("VF", "Ventral fin (fixed part)", "Tail", "composite-layup", "cf_fabric_wet skin on xps_foam core",
                      compound([fo, fcore]), fin_pl, "tail", bodies=[(fo, rho("cf_fabric_wet")), (fcore, rho("xps_foam"))],
                      notes=f"Under each boom; chord {VC:.0f} mm; symmetric section so one part serves both sides; "
                            "foam core on T-HW-VF, bottom tip with a replaceable UHMW skid strip."))
    rf = clip2d(vf_g, xmin=xr + GAP)
    r_in = offset2d(rf, -SKT)
    rs = prism_z(rf, VZ0 + GAP, z_top) - prism_z(r_in, VZ0 + GAP + SKT, z_top - SKT)
    rc = prism_z(r_in, VZ0 + GAP + SKT, z_top - SKT)
    parts.append(Part("RUD", "Rudder", "Tail", "composite-layup", "cf_fabric_wet skin on xps_foam core", compound([rs, rc]), fin_pl,
                      "tail", bodies=[(rs, rho("cf_fabric_wet")), (rc, rho("xps_foam"))],
                      notes=f"{V['rudder_chord_fraction']*100:.0f} % chord; 2 hinges; actuator inside the fin."))
    fs = tube_z(FIN_SP_R, FIN_SP_R - 2.0, VZ0 + 20, BOOM_Z - R_WRAP - 2, xf, 0)
    parts.append(Part("VF-SPAR", "Fin spar tube", "Tail", "COTS-cut", "cf_tube_rollwrapped_twill", fs, fin_pl, "tail",
                      density=rho("cf_tube_rollwrapped_twill"), purchased=True,
                      notes="40 x 2 mm roll-wrapped tube, bonded into the TL-CLAMP socket and the fin core."))
    # hinges (shared design for elevator and rudders)
    hg = box(-35, 15, -3, 3, -18, 18) - cyl_y(3.2, -5, 5, 8, 0)
    hp = [place(xh - GAP - 15, y, HZ) for y in np.linspace(-Y_PANEL + 150, Y_PANEL - 150, 4)]
    hp += [place(xr - GAP - 15, s * BOOM_Y, z, rx=90) for s in (1, -1) for z in (VZ0 + 150, z_top - 200)]
    parts.append(Part("TL-HINGE", "Tail hinge bracket", "Tail", "CNC", "al6061_t6_sheet", hg, hp, "tail",
                      density=rho("al6061_t6_sheet"), machine="cnc_metal", notes="6 mm 6061-T6, potted inserts, AN3 pin."))
    act = box(-110, 110, -22, 22, -18, 18)
    ap = [place(xh - GAP - 60, 300, HZ, rz=90)] + [place(xr - GAP - 60, s * BOOM_Y, VZ0 + 330, ry=90) for s in (1, -1)]
    parts.append(Part("TL-ACT", "Tail surface actuator (EMA placeholder)", "Tail", "COTS", "purchased", act, ap, "flight_controls",
                      mass_kg=mass_item("tail actuators", 2.4) / 3, mass_source="design mass item 'tail actuators' / 3", purchased=True,
                      notes="Elevator x 1, rudder x 2; envelope 220 x 44 x 36 mm."))
    return parts
