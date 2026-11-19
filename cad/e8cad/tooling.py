"""Tooling: spar-cap jigs, hot-wire templates, wing cradles, fuselage / canopy / seat / tip plugs (split to the CNC
bed), nacelle moulds (split to the printer), drill templates, V-blocks, cross-tube bend template.
Tooling parts are not placed in the aircraft assembly; qty = number of identical pieces needed."""
from __future__ import annotations

import math

import numpy as np
from build123d import Plane

from .config import SHOP, WING, DETAIL, Part, mm, rho, IDENT, place, PANEL
from .geom import (cyl_y, box, compound, prism_y, prism_z, offset2d, clip2d, thickness_at, rounded_rect, cyl_x, cyl_z, tube_x,
                   loft3d, naca4)
from shapely.geometry import Polygon, box as sbox


def _qty(n):
    return [IDENT] * n


def split_axes(solid, lim):
    """Split a solid into a grid so each piece fits lim = (lx, ly, lz) along the global axes."""
    bb = solid.bounding_box()
    mins = [bb.min.X, bb.min.Y, bb.min.Z]
    size = [bb.size.X, bb.size.Y, bb.size.Z]
    n = [max(1, math.ceil((s - 1e-6) / l)) for s, l in zip(size, lim)]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                b = box(mins[0] + size[0] * i / n[0] - 0.01, mins[0] + size[0] * (i + 1) / n[0] + 0.01 * (i == n[0] - 1),
                        mins[1] + size[1] * j / n[1] - 0.01, mins[1] + size[1] * (j + 1) / n[1] + 0.01 * (j == n[1] - 1),
                        mins[2] + size[2] * k / n[2] - 0.01, mins[2] + size[2] * (k + 1) / n[2] + 0.01 * (k == n[2] - 1))
                p = solid & b
                if p is not None and getattr(p, "wrapped", None) is not None and p.volume > 1.0:
                    out.append(((i, j, k), p))
    return out, n


def _joint_text(n, axes="xyz"):
    t = [f"{n[i]} pieces along {axes[i]}" for i in range(3) if n[i] > 1]
    return ("split into " + ", ".join(t) + "; pieces dowel-pinned and bonded (plugs) or bolted (moulds) on the split planes") if t else ""


def tooling_parts() -> list[Part]:
    from . import wing as W
    from . import fuselage as FU
    from . import booms as B
    from . import tail as T
    from . import gear as GR
    parts = []
    bed = SHOP["cnc_bed_mm"]
    fdm = SHOP["fdm_mm"]
    mdf = rho("mdf")
    # ---------------- spar-cap jigs (half span in segments, mirror pair)
    sp = W._sp()
    seg_L = min(bed[0] - 40, W.Y_TIP / math.ceil(W.Y_TIP / (bed[0] - 40)))
    nseg = math.ceil(W.Y_TIP / seg_L)
    for tag in ("M", "R"):
        for u in ("U", "L"):
            cap = sp[f"cap{tag}{u}"]
            bb = cap.bounding_box()
            for k in range(nseg):
                y0, y1 = k * W.Y_TIP / nseg, (k + 1) * W.Y_TIP / nseg
                seg = cap & box(bb.min.X - 1, bb.max.X + 1, y0, y1, bb.min.Z - 1, bb.max.Z + 1)
                if u == "U":
                    blk = box(bb.min.X - 40, bb.max.X + 40, y0, y1, bb.min.Z - 0.0 + 0.0, bb.max.Z + 40)
                else:
                    blk = box(bb.min.X - 40, bb.max.X + 40, y0, y1, bb.min.Z - 40, bb.max.Z)
                jig = blk - seg
                parts.append(Part(f"T-CAPJIG-{tag}{u}{k + 1}", f"Spar-cap jig, {'main' if tag == 'M' else 'rear'} spar "
                                  f"{'upper' if u == 'U' else 'lower'} cap, segment {k + 1} (span {y0:.0f}-{y1:.0f} mm)",
                                  "Tooling", "CNC", "mdf", jig, _qty(2), "tooling", density=mdf, tooling=True, machine="cnc",
                                  notes="3-axis CNC MDF trough = the cap's skin-side surface with the ply-drop taper; sealed with "
                                        "epoxy, waxed + PVA. Shown in aircraft orientation (the upper-cap jig is flipped for lay-up). "
                                        "Qty 2: left and right halves of the span (mirror programs).",
                                  joints=f"{nseg} segments per half-span, butted on a steel-box strongback with 2 dowels per joint"))
    # ---------------- hot-wire templates (12 mm MDF, kerf-compensated)
    C = W.C
    xs_m = WING["spars"][0]["x_c"] * C
    xs_r = WING["spars"][1]["x_c"] * C
    btm = WING["spars"][0]["section_tip"]["b_cap"] * 1000
    inner = Polygon(W.INNER)
    pieces = {
        "T-HW-LE": inner.intersection(sbox(-10, -500, xs_m - btm / 2, 500)),
        "T-HW-MID": inner.intersection(sbox(xs_m + btm / 2, -500, xs_r - 1, 500)),
        "T-HW-AFT": inner.intersection(sbox(xs_r + 1, -500, C + 10, 500)),
        "T-HW-AFTA": inner.intersection(sbox(xs_r + 1, -500, W.x_cut(), 500)),
    }
    def tmpl(poly, name, pid):
        poly = poly.buffer(DETAIL["ctrl_gap"] * 0 + 0.8, join_style=2)
        b = poly.bounds
        tab = sbox(b[0] + (b[2] - b[0]) * 0.3, poly.centroid.y, b[0] + (b[2] - b[0]) * 0.7, b[3] + 40)
        poly = poly.union(tab)
        pts = np.array(poly.exterior.coords)[:-1]
        s = prism_y(pts, 0, 12)
        for hx in np.linspace(b[0] + (b[2] - b[0]) * 0.38, b[0] + (b[2] - b[0]) * 0.62, 2):
            s = s - cyl_y(3.2, -1, 13, hx, b[3] + 20)
        return Part(pid, f"Hot-wire template: {name}", "Tooling", "CNC", "mdf", s, _qty(2), "tooling", density=mdf, tooling=True,
                    machine="cnc", notes="12 mm MDF (or 3 mm aluminium for repeated use), outline offset 0.8 mm for the wire "
                                         "kerf; one template at each end of the block (constant chord), station marks every 50 mm.")
    for pid, pg in pieces.items():
        nm = {"T-HW-LE": "wing LE core", "T-HW-MID": "wing core between the spars", "T-HW-AFT": "wing aft core",
              "T-HW-AFTA": "wing aft core in the flap and aileron bays"}[pid]
        parts.append(tmpl(pg, nm, pid))
    # control surfaces and tail
    xh0 = W.x_cut() + W.GAP
    lo, hi = thickness_at(W.FOIL, xh0 + 0.5)
    from .geom import circle
    aft = Polygon(clip2d(W.FOIL, xmin=xh0))
    nose = Polygon(circle((hi - lo) / 2 - W.GAP, xh0 + (hi - lo) / 2, (hi + lo) / 2, 32))
    prof = aft.union(nose).intersection(Polygon(W.FOIL).buffer(0))
    parts.append(tmpl(Polygon(offset2d(np.array(prof.exterior.coords)[:-1], -DETAIL["ctrl_skin_t"])), "aileron core", "T-HW-AIL"))
    hf = naca4(T.H_FOIL[4:], T.HC, 50)
    xh = (1 - T.H["elevator_chord_fraction"]) * T.HC
    parts.append(tmpl(Polygon(offset2d(clip2d(hf, xmax=xh - T.GAP), -T.SKT)), "horizontal-tail core", "T-HW-HT"))
    parts.append(tmpl(Polygon(offset2d(clip2d(hf, xmin=xh + T.GAP), -T.SKT)), "elevator core", "T-HW-ELV"))
    vf = naca4("0012", T.VC, 50)
    xr = (1 - T.V["rudder_chord_fraction"]) * T.VC
    parts.append(tmpl(Polygon(offset2d(clip2d(vf, xmax=xr - T.GAP), -T.SKT)), "fin core", "T-HW-VF"))
    parts.append(tmpl(Polygon(offset2d(clip2d(vf, xmin=xr + T.GAP), -T.SKT)), "rudder core", "T-HW-RUD"))
    # ---------------- wing cradles (18 mm MDF boards, lower and upper)
    fo = Polygon(offset2d(W.FOIL, 3.0))
    n_cr = int(math.ceil(2 * W.HALF / 600.0)) + 1
    for u, (z0, z1) in (("L", (-260, 0)), ("U", (0, 260))):
        pg = sbox(-100, z0, C + 100, z1).difference(fo)
        pg = max(pg.geoms, key=lambda g: g.area) if pg.geom_type != "Polygon" else pg
        s = prism_y(np.array(pg.exterior.coords)[:-1], 0, 18)
        parts.append(Part(f"T-CRADLE-{u}", f"Wing {'lower' if u == 'L' else 'upper'} cradle board", "Tooling", "CNC", "mdf", s,
                          _qty(n_cr), "tooling", density=mdf, tooling=True, machine="cnc",
                          notes=f"18 mm MDF, CNC-cut negative of the airfoil + 3 mm bagging allowance; {n_cr} boards at 600 mm "
                                "on a levelled table, set to the design incidence with a digital level (twist check)."))
    # ---------------- fuselage plug sections (CNC tooling foam, split to the bed)
    oml_s, in1, inc = FU.OML()
    plug = in1 & box(-10, FU.FUS_L + 10, 0, 3000, -1000, 3000)
    lim = (bed[0] - 40, bed[2], bed[1] - 20)       # x along the bed X, y (depth) along the machine Z, z along the bed Y
    pcs, n = split_axes(plug, lim)
    for (i, j, k), p in pcs:
        parts.append(Part(f"T-PLUG-F{i + 1}{k + 1}{j + 1}", f"Fuselage plug section x{i + 1} z{k + 1} layer {j + 1}", "Tooling",
                          "CNC", "eps_tooling_foam", p, [IDENT, place(mirror=True)], "tooling", density=rho("eps_tooling_foam"),
                          tooling=True, machine="cnc_plug",
                          notes="Laminated EPS/XPS block machined 3-axis (two set-ups), sealed with lightweight filler and "
                                "epoxy; male plug for the moldless glass shell (surface = OML - shell thickness). Qty 2 = left/right.",
                          joints=_joint_text(n, "xyz")))
    # canopy plug (stacked MDF)
    can = inc & box(FU.X_CAB0, FU.X_CAN1, -3000, 3000, FU.SILL_Z - 30, 3000)
    can = can - FU.wing_envelope(4.0)
    pcs, n = split_axes(can, (bed[0] - 40, bed[1] - 20, bed[2]))
    for (i, j, k), p in pcs:
        parts.append(Part(f"T-CAN-PLUG{k + 1}", f"Canopy plug, lift {k + 1}", "Tooling", "CNC", "mdf", p, _qty(1), "tooling",
                          density=mdf, tooling=True, machine="cnc",
                          notes="Stacked MDF lifts machined 3-axis, sealed and polished; supplied to the plastics shop for "
                                "drape forming the PC canopy.", joints=_joint_text(n)))
    # seat plug
    rec = math.radians(15)
    sp2 = np.array([[-450, 45], [0, 0], [800 * math.sin(rec), 800 * math.cos(rec)], [-450, 800 * math.cos(rec)]])
    seat = prism_y(sp2, -230, 230)
    pcs, n = split_axes(seat, (bed[0], bed[2], bed[1]))
    for (i, j, k), p in pcs:
        parts.append(Part(f"T-SEAT-PLUG{j + 1}", f"Seat shell plug, layer {j + 1}", "Tooling", "CNC", "eps_tooling_foam", p, _qty(1),
                          "tooling", density=rho("eps_tooling_foam"), tooling=True, machine="cnc_plug",
                          notes="Foam plug, sealed; seat shell laid on the occupant-side surface.", joints=_joint_text(n)))
    # wing tip plug
    tf = loft3d([np.column_stack([W.INNER[:, 0], np.full(len(W.INNER), 0.0), W.INNER[:, 1]]),
                 np.column_stack([W.INNER[:, 0] * 0.96 + 0.02 * C, np.full(len(W.INNER), W.TIP_FAIR - 1), W.INNER[:, 1] * 0.33])])
    parts.append(Part("T-PLUG-TIP", "Wing tip fairing plug", "Tooling", "CNC", "eps_tooling_foam", tf, _qty(1), "tooling",
                      density=rho("eps_tooling_foam"), tooling=True, machine="cnc_plug",
                      notes="Machined in two halves (upper/lower) on the chord plane; one plug serves both tips (mirror lay-up "
                            "uses the flipped plug)."))
    # ---------------- nacelle moulds (FDM, split to the printer)
    nac_o = prism_z(B.NAC_FOIL, 0.0, B.NAC_TOP)
    mould = box(B.NAC_X0 - 15, B.NAC_X0 + B.NAC_C + 15, 0, 105, -10, B.NAC_TOP + 15) - nac_o - cyl_x(B.RO + 1, -400, 800)
    pcs, n = split_axes(mould, fdm)
    for idx, ((i, j, k), p) in enumerate(pcs):
        parts.append(Part(f"T-NAC-M{idx + 1}", f"Nacelle half-mould segment {idx + 1}", "Tooling", "FDM", "asa", p, _qty(2), "tooling",
                          density=rho("asa") * 0.35, tooling=True, machine="fdm",
                          notes="ASA, 4 walls, 15 % infill, flanged split faces bolted (M5) and sealed; surface sanded, epoxy "
                                "coated, waxed + PVA. Qty 2: left and right mould halves (mirror print).",
                          joints=_joint_text(n), settings={"material": "ASA", "walls": 4, "infill": "15 % gyroid", "layer": "0.2 mm"}))
    # ---------------- drill templates, V-blocks, bend template
    rf = box(-80, 80, -50, 50, 0, 6)
    for bx in (-45, 45):
        for by in (-22, 22):
            rf = rf - cyl_z(3.3, -1, 7, bx, by)
    rf = rf - cyl_z(4.0, -1, 7, 0, 0)
    parts.append(Part("T-DRILL-RF", "Root-fitting drill template", "Tooling", "CNC", "al6061_t6_sheet", rf, _qty(4), "tooling",
                      density=rho("al6061_t6_sheet"), tooling=True, machine="cnc_metal",
                      notes="6 mm 6061 with pressed drill bushes; indexed on the spar-cap edge and the pin hole."))
    dt = (tube_x(B.R_WRAP + 6, B.R_WRAP + 0.3, -90, 90) & box(-100, 100, -100, 100, 0, 100))
    for x in (-45, 45):
        dt = dt - cyl_z(3.3, 0, 200, x, 0)
    parts.append(Part("T-DRILL-BC", "Boom clamp crown drill template", "Tooling", "FDM", "pa_cf", dt, _qty(1), "tooling",
                      density=rho("pa_cf") * 0.6, tooling=True, machine="fdm",
                      notes="PA-CF half-shell clipped on the boom, indexed on a scribed datum line; steel drill bushes pressed in."))
    vb = box(-80, 80, -90, 90, 0, 110) - cyl_x(B.R_WRAP + 0.5, -100, 100, 0, 110)
    parts.append(Part("T-VBLOCK", "Boom alignment cradle (strongback)", "Tooling", "FDM", "petg", vb, _qty(12), "tooling",
                      density=rho("petg") * 0.3, tooling=True, machine="fdm",
                      notes="PETG cradles bolted to an aluminium strongback at the clamp stations; rotor stations set with a laser line."))
    path = GR.cross_path()
    pts = np.array([[p[1], p[2]] for p in path])
    from shapely.geometry import LineString
    tl = LineString(pts).buffer(GR.R_XT, cap_style=2, join_style=1)
    tpl = sbox(pts[:, 0].min() - 80, -20, pts[:, 0].max() + 80, pts[:, 1].max() + GR.R_XT + 60).difference(tl)
    tpl = max(tpl.geoms, key=lambda g: g.area) if tpl.geom_type != "Polygon" else tpl
    s = prism_z(np.array(tpl.exterior.coords)[:-1], 0, 18)
    parts.append(Part("T-XT-TEMPL", "Gear leg bend template (both legs of a station)", "Tooling", "CNC", "birch_plywood", s, _qty(1), "tooling",
                      density=rho("birch_plywood"), tooling=True, machine="cnc",
                      notes="18 mm plywood negative of the cross-tube centreline + tube radius, sent to the tube-bending shop "
                            "and used for the receiving inspection (lay the bent tube in it)."))
    return parts
