"""Global beam model of the E8-200 airframe built from design/geometry.json: load cases, margins, modes.

    ~/tools/cadenv/bin/python fea/airframe.py [geometry.json] [selected_design.json] [--tag NAME]

Without arguments the model is built from design/geometry.json, or from the placeholder design
(fea/placeholder/geometry_placeholder.json) while the design is not frozen.

Model (fea/frame.py, 6 DOF beams, free-free with inertia relief and gravity):
  wing      front/rear spar lines (sections interpolated root -> tip), a torsion-box line (skin, Bredt GJ),
            stiff ribs at every station; continuous carry-through between the root fittings
  fuselage  equivalent beam on the fuselage axis, stiff frames to the four wing-root fittings
  booms     beams at (y_b, z_b), stiff saddles to both spars at the boom station
  rotors    hub nodes on stiff pylons; thrust along the rotor axis, motor reaction torque, gyroscopic moments
  tail      H-tail spar between the booms (stiff fins if the spar is above the booms)
  gear      struts from the contact points to the fuselage beam
  masses    every item on its own node, linked stiffly to the nearest node of its 'attach' component;
            structural component masses distributed over the component nodes (member self-mass is not added
            again; the section-based member mass is reported for comparison with the mass budget)
All results are ULTIMATE (limit x 1.5) unless marked 'limit'.  Results -> fea/results/airframe_<tag>.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import loads as LD  # noqa: E402
from fea.frame import Frame, Section  # noqa: E402
from fea.geometry import MAT, Wing, load, mass_summary, section, spar_spec  # noqa: E402

HERE = Path(__file__).resolve().parent
G0 = 9.80665
ULT = 1.5
RIGID = Section.rigid()
PIN = Section.pin()
SLIDE_X = Section.pin(name="pinned link, sliding along the boom")
SLIDE_X.meta = {"release": [8, 9, 10, 11]}
FITTING_FACTOR = 1.15


# ============================================================================= build
def build(g: dict, n_half=20, n_boom=40, n_fus=30):
    f = Frame()
    W = Wing(g["wing"])
    s = W.s
    tags = {}
    yr = g["wing"]["root_fittings_y"]
    yb = sorted({abs(b["y"]) for b in g["booms"]})
    ys = np.r_[np.linspace(-s, s, 2 * n_half + 1), [-yr, yr, 0.0], [-y for y in yb], yb]
    ys = np.unique(np.round(ys, 5))
    spars = g["wing"]["spars"]
    lines = {}
    member_mass = {}
    for sp in spars:
        nodes = [f.node((float(W.x_at(y, sp["x_c"])), y, float(W.z(y)))) for y in ys]
        lines[sp["name"]] = nodes
        mm = 0.0
        for i in range(len(ys) - 1):
            ym = 0.5 * (ys[i] + ys[i + 1])
            spec = spar_spec(sp, abs(ym) / s)
            sec = section(spec, name=f"spar {sp['name']}")
            mm += sec.mass_per_length * (ys[i + 1] - ys[i])
            sec.m_per_len, sec.rho = 0.0, 0.0
            f.beam(nodes[i], nodes[i + 1], sec, vref=(0, 0, 1), tag=f"spar {sp['name']}")
        member_mass[f"spar {sp['name']}"] = mm
    front, rear = lines[spars[0]["name"]], lines[spars[-1]["name"]]
    tb = g["wing"]["torsion_box"]
    from fea.geometry import laminate_moduli
    _, Gs = laminate_moduli(tb["skin_material"], tb.get("skin_layup", "+-45"))
    box = []
    for i, y in enumerate(ys):
        xf, xr = f.nodes[front[i]][0], f.nodes[rear[i]][0]
        box.append(f.node((0.5 * (xf + xr), y, float(W.z(y)))))
    for i in range(len(ys) - 1):
        ym = 0.5 * (ys[i] + ys[i + 1])
        c = float(W.chord(ym))
        width = (spars[-1]["x_c"] - spars[0]["x_c"]) * c
        depth = g["wing"]["t_c"] * c * tb.get("depth_factor", 0.85)
        Am = width * depth
        J = 4 * Am**2 / (2 * (width + depth) / tb["skin_t"])
        sec = Section(A=1e-6, Iy=1e-10, Iz=1e-10, J=J, E=1e9, G=Gs, rho=0.0, cy=width / 2, cz=depth / 2,
                      tau_per_T=1 / (2 * Am * tb["skin_t"]), name="wing skin box", material=tb["skin_material"], kind="skin_box")
        f.beam(box[i], box[i + 1], sec, tag="wing skin box")
    for i in range(len(ys)):
        f.beam(front[i], box[i], RIGID, vref=(0, 1, 0), tag="rib")
        f.beam(box[i], rear[i], RIGID, vref=(0, 1, 0), tag="rib")
        for sp in spars[1:-1]:
            f.beam(box[i], lines[sp["name"]][i], RIGID, vref=(0, 1, 0), tag="rib")
    wing_nodes = [n for L in lines.values() for n in L] + box

    # fuselage
    fu = g["fuselage"]
    xs_special = [f.nodes[front[list(ys).index(yr)]][0], f.nodes[rear[list(ys).index(yr)]][0]]
    xs_special += [lg["x"] for lg in g.get("landing_gear", [])]
    fx = np.unique(np.round(np.r_[np.linspace(fu["x_nose"], fu["x_tail"], n_fus + 1), xs_special], 5))
    fus = [f.node((x, 0.0, fu["z_axis"])) for x in fx]
    member_mass["fuselage shell (equivalent beam)"] = 0.0
    stn = fu.get("stations")
    for i in range(len(fx) - 1):
        spec = dict(fu["section"])
        if stn and spec["type"] == "rect_tube":
            # tapered equivalent box from the OML stations (super-ellipse ~ 0.85 x the bounding box), min 0.15 m
            xm = 0.5 * (fx[i] + fx[i + 1])
            xs_ = [q["x"] for q in stn]
            spec["b"] = max(0.15, 0.85 * float(np.interp(xm, xs_, [q["width"] for q in stn])))
            spec["h"] = max(0.15, 0.85 * float(np.interp(xm, xs_, [q["height"] for q in stn])))
        sec = section(spec, name="fuselage")
        member_mass["fuselage shell (equivalent beam)"] += sec.mass_per_length * (fx[i + 1] - fx[i])
        sec.m_per_len, sec.rho = 0.0, 0.0
        f.beam(fus[i], fus[i + 1], sec, vref=(0, 0, 1), tag="fuselage")
    for side in (-yr, yr):
        k = list(ys).index(round(side, 5))
        for line, nm in ((front, "front"), (rear, "rear")):
            nf = fus[int(np.argmin(np.abs(fx - f.nodes[line[k]][0])))]
            # wing-root frame (stiff) from the fuselage axis out to the fitting station, then a vertical lug link pinned at
            # the wing (spherical): the lug carries the true fitting force (no lateral component from an inclined link)
            pf = f.nodes[line[k]].copy()
            pf[2] = f.nodes[nf][2]
            nfr = f.node(pf)
            f.beam(nf, nfr, RIGID, vref=(0, 0, 1), tag="wing-root frame")
            f.beam(nfr, line[k], PIN, vref=(1, 0, 0), tag=f"wing root fitting {nm} {'L' if side < 0 else 'R'}")

    # booms
    booms = {}
    for b in g["booms"]:
        k = list(ys).index(round(b["y"], 5))
        xsp = [f.nodes[L[k]][0] for L in lines.values()]
        xr = [r["x"] for r in g["rotors"] if r.get("boom") == b["name"]]
        xt = [g["tail"]["x_spar"]] if g.get("tail") else []
        xx = np.unique(np.round(np.r_[np.linspace(b["x_front"], b["x_aft"], n_boom + 1), xsp, xr, xt], 5))
        segs = b.get("segments")                       # [{x_from, x_to, section}] along the boom, else one section
        if segs:
            xx = np.unique(np.round(np.r_[xx, [sg["x_from"] for sg in segs], [segs[-1]["x_to"]]], 5))
        nodes = [f.node((x, b["y"], b["z"])) for x in xx]
        member_mass[b["name"]] = 0.0
        for i in range(len(xx) - 1):
            xm = 0.5 * (xx[i] + xx[i + 1])
            spec = b["section"]
            if segs:
                spec = next((sg["section"] for sg in segs if sg["x_from"] <= xm <= sg["x_to"]), segs[0]["section"])
            sec = section(spec, name=b["name"])
            member_mass[b["name"]] += sec.mass_per_length * (xx[i + 1] - xx[i])
            sec.m_per_len, sec.rho = 0.0, 0.0
            f.beam(nodes[i], nodes[i + 1], sec, vref=(0, 0, 1), tag=b["name"])
        for nm, L in lines.items():
            nb = nodes[int(np.argmin(np.abs(xx - f.nodes[L[k]][0])))]
            # bolted saddle clamps at both spars: each transmits forces only (spherical at the spar); the boom moment
            # enters the wing as a force couple between the two spars
            # the rear saddle has slotted (fore-aft sliding) holes so that the boom-spar-saddle portal is not
            # redundant in x (link local z = global x with vref (1, 0, 0))
            last = nm == list(lines)[-1]
            f.beam(nb, L[k], SLIDE_X if last else PIN, vref=(1, 0, 0), tag=f"boom saddle {b['name']} {nm} spar")
        booms[b["name"]] = dict(nodes=nodes, x=xx, spec=b)

    # rotors: hub node on a pylon (section 'rotor_pylon_section', stiff if absent); the unit mass is split between
    # the hub (motor + rotor, fraction 'rotor_hub_mass_fraction') and the boom (inverter, mount)
    hubs = {}
    pspec = g.get("rotor_pylon_section")
    hub_frac = g.get("rotor_hub_mass_fraction", 1.0)
    for r in g["rotors"]:
        bm = booms[r["boom"]]
        nb = bm["nodes"][int(np.argmin(np.abs(bm["x"] - r["x"])))]
        if abs(r["z"] - f.nodes[nb][2]) < 1e-6 and abs(r["y"] - f.nodes[nb][1]) < 1e-6:
            hubs[r["name"]] = nb
        else:
            h = f.node((r["x"], r["y"], r["z"]))
            if pspec:
                ps = section(pspec, name="rotor pylon")
                member_mass["rotor pylons"] = member_mass.get("rotor pylons", 0.0) + ps.mass_per_length * float(np.linalg.norm(f.nodes[h] - f.nodes[nb]))
                ps.m_per_len, ps.rho = 0.0, 0.0
                f.beam(nb, h, ps, n=4, vref=(1, 0, 0), tag="rotor pylon")
                # stiff motor-mount / pylon-root fittings are represented by the pylon ends
            else:
                f.beam(nb, h, RIGID, vref=(1, 0, 0), tag=f"rotor mount {r['name']}")
            hubs[r["name"]] = h
        f.add_mass(hubs[r["name"]], r["mass_kg"] * hub_frac, (0.0, 0.0, r.get("rotor_inertia_kgm2", 0.0)))
        if hub_frac < 1.0:
            f.add_mass(nb, r["mass_kg"] * (1 - hub_frac))
    rotor_base = {r["name"]: booms[r["boom"]]["nodes"][int(np.argmin(np.abs(booms[r["boom"]]["x"] - r["x"])))] for r in g["rotors"]}

    # tail
    tail = []
    if g.get("tail"):
        t = g["tail"]
        bl = sorted(booms.values(), key=lambda b: b["spec"]["y"])
        ends = [b["nodes"][int(np.argmin(np.abs(b["x"] - t["x_spar"])))] for b in (bl[0], bl[-1])]
        yl, yrr = bl[0]["spec"]["y"], bl[-1]["spec"]["y"]
        tn = [f.node((t["x_spar"], y, t["z"])) for y in np.linspace(yl, yrr, 13)[1:-1]]
        # spar end nodes: the boom nodes themselves when the tail spar is at boom height, else stiff fins
        for k, (e, y) in enumerate(((ends[0], yl), (ends[1], yrr))):
            p_end = np.array([t["x_spar"], y, t["z"]])
            if np.linalg.norm(f.nodes[e] - p_end) < 1e-6:
                nt = e
            else:
                nt = f.node(p_end)
                f.beam(e, nt, RIGID, vref=(1, 0, 0), tag="fin / tail joint")
            tn.insert(0 if k == 0 else len(tn), nt)
        sec = section(t["spar_section"], name="tail spar")
        member_mass["tail spar"] = sec.mass_per_length * abs(yrr - yl)
        sec.m_per_len, sec.rho = 0.0, 0.0
        for i in range(len(tn) - 1):
            f.beam(tn[i], tn[i + 1], sec, tag="tail spar")
        tail = tn
        for n in tn:
            f.add_mass(n, t.get("mass_kg", 0.0) / len(tn))

    # gear
    gear = {}
    oml = g.get("landing_gear_oml")
    if g.get("gear_model") == "damped" and oml and oml.get("dampers"):
        # damped skid gear: each leg pivots on its keel saddle (rotation about x released) and is held by an oleo damper
        # (axial-only member, rigid at the peak-load instant) from a point on the leg to a cabin-side hard point
        ct = oml["cross_tube"]
        cts = section(dict(type="tube", od=ct["od"], t=ct["t"], material=ct.get("material", "al6061_t6_extr")), name="gear cross tube")
        pivot = Section(A=cts.A, Iy=cts.Iy, Iz=cts.Iz, J=cts.J, E=cts.E, G=cts.G, rho=0.0, cy=cts.cy, cz=cts.cz, Ay=cts.Ay, Az=cts.Az,
                        tau_per_T=cts.tau_per_T, round=True, name="gear cross tube", material=cts.material, kind="tube",
                        meta=dict(cts.meta, release=[11]))
        damper = Section.rigid(name="oleo damper")
        damper.meta = {"release": [4, 5, 9, 10, 11]}
        member_mass["gear cross tubes"] = 0.0
        sk = oml["skids"][0]
        sks = section(dict(type="tube", od=sk["diameter"], t=sk.get("t", 0.003), material=sk.get("material", "al6061_t6_extr")), name="skid tube")
        xs_st = sorted({st["p1"][0] for st in oml["struts"]})
        skid_nodes = {}
        for sgn in (-1, 1):
            xx = np.unique(np.round(np.r_[np.linspace(sk["x_start"], sk["x_end"], 14), xs_st], 5))
            nodes = [f.node((x, sgn * sk["y"], sk["z"])) for x in xx]
            for i in range(len(xx) - 1):
                f.beam(nodes[i], nodes[i + 1], sks, vref=(0, 0, 1), tag="skid tube")
            skid_nodes[sgn] = (xx, nodes)
        for st in oml["struts"]:
            x, y1, z1 = st["p1"]
            _, y2, z2 = st["p2"]
            dmp = min(oml["dampers"], key=lambda d_: abs(d_["p1"][0] - x))
            _, yd1, zd1 = dmp["p1"]
            _, yd2, zd2 = dmp["p2"]
            for sgn in (-1, 1):
                p1 = f.node((x, sgn * y1, z1))
                pd = f.node((x, sgn * yd1, zd1))       # damper attachment on the leg (assumed on the leg line)
                p2 = f.node((x, sgn * y2, z2))
                L1 = float(np.linalg.norm(f.nodes[pd] - f.nodes[p1]))
                L2 = float(np.linalg.norm(f.nodes[p2] - f.nodes[pd]))
                member_mass["gear cross tubes"] += cts.mass_per_length * (L1 + L2)
                f.beam(p1, pd, cts, n=4, vref=(1, 0, 0), tag="gear cross tube")
                f.beam(pd, p2, pivot, n=1, vref=(1, 0, 0), tag="gear cross tube")
                ph = f.node((x, sgn * yd2, zd2))
                f.beam(pd, ph, damper, vref=(1, 0, 0), tag="gear damper")
                nf = fus[int(np.argmin(np.abs(fx - x)))]
                f.beam(ph, nf, RIGID, vref=(1, 0, 0), tag="gear damper hard point")
                f.beam(p2, nf, RIGID, vref=(1, 0, 0), tag="gear attach (keel saddle)")
                xx, nodes = skid_nodes[sgn]
                f.beam(nodes[int(np.argmin(np.abs(xx - x)))], p1, RIGID, vref=(1, 0, 0), tag="skid saddle")
        cts.m_per_len = sks.m_per_len = 0.0
        cts.rho = sks.rho = 0.0
        for lg in g.get("landing_gear", []):
            sgn = 1 if lg["y"] > 0 else -1
            xx, nodes = skid_nodes[sgn]
            nc = nodes[int(np.argmin(np.abs(xx - lg["x"])))]
            f.add_mass(nc, lg.get("mass_kg", 0.0))
            gear[lg["name"]] = nc
    elif g.get("gear_model") == "frame" and oml:
        # skid gear as a frame: two bent cross tubes (skid -> saddle on the keel -> across -> other skid), skid tubes
        ct = oml["cross_tube"]
        cts = section(dict(type="tube", od=ct["od"], t=ct["t"], material=ct.get("material", "al6061_t6_extr")), name="gear cross tube")
        member_mass["gear cross tubes"] = 0.0
        sk = oml["skids"][0]
        sks = section(dict(type="tube", od=sk["diameter"], t=sk.get("t", 0.003), material=sk.get("material", "al6061_t6_extr")), name="skid tube")
        xs_st = sorted({st["p1"][0] for st in oml["struts"]})
        skid_nodes = {}
        for sgn in (-1, 1):
            xx = np.unique(np.round(np.r_[np.linspace(sk["x_start"], sk["x_end"], 14), xs_st], 5))
            nodes = [f.node((x, sgn * sk["y"], sk["z"])) for x in xx]
            for i in range(len(xx) - 1):
                f.beam(nodes[i], nodes[i + 1], sks, vref=(0, 0, 1), tag="skid tube")
            skid_nodes[sgn] = (xx, nodes)
        for st in oml["struts"]:
            x, y1, z1 = st["p1"]
            _, y2, z2 = st["p2"]
            pL1, pL2 = f.node((x, -y1, z1)), f.node((x, -y2, z2))
            pR2, pR1 = f.node((x, y2, z2)), f.node((x, y1, z1))
            for a_, b_ in ((pL1, pL2), (pL2, pR2), (pR2, pR1)):
                L_ = float(np.linalg.norm(f.nodes[b_] - f.nodes[a_]))
                member_mass["gear cross tubes"] += cts.mass_per_length * L_
                f.beam(a_, b_, cts, n=6, vref=(1, 0, 0), tag="gear cross tube")
            for sgn, pc in ((-1, pL1), (1, pR1)):
                xx, nodes = skid_nodes[sgn]
                f.beam(nodes[int(np.argmin(np.abs(xx - x)))], pc, RIGID, vref=(1, 0, 0), tag="skid saddle")
            for pc in (pL2, pR2):
                nf = fus[int(np.argmin(np.abs(fx - x)))]
                f.beam(pc, nf, RIGID, vref=(1, 0, 0), tag="gear attach (keel saddle)")  # long clamped saddle (moment-carrying)
        cts.m_per_len = sks.m_per_len = 0.0
        cts.rho = sks.rho = 0.0
        for lg in g.get("landing_gear", []):
            sgn = 1 if lg["y"] > 0 else -1
            xx, nodes = skid_nodes[sgn]
            nc = nodes[int(np.argmin(np.abs(xx - lg["x"])))]
            f.add_mass(nc, lg.get("mass_kg", 0.0))
            gear[lg["name"]] = nc
    else:
        gs = g.get("gear_strut_section")
        for lg in g.get("landing_gear", []):
            nc = f.node((lg["x"], lg["y"], lg["z"]))
            nf = fus[int(np.argmin(np.abs(fx - lg["x"])))]
            sec = section(gs, name="gear strut") if gs else RIGID
            if gs:
                sec.m_per_len, sec.rho = 0.0, 0.0
            f.beam(nc, nf, sec, vref=(1, 0, 0), tag="gear strut")
            f.add_mass(nc, lg.get("mass_kg", 0.0))
            gear[lg["name"]] = nc

    groups = dict(fuselage=fus, wing=wing_nodes, tail=tail, **{k: v["nodes"] for k, v in booms.items()})
    groups["fuselage+wing"] = fus + [n for L in lines.values() for n in L]

    def attach(name, xyz, kg, grp, I=(0, 0, 0), tag=None):
        tgt = f.nearest(xyz, groups.get(grp, fus))
        if np.linalg.norm(f.nodes[tgt] - np.asarray(xyz, float)) < 1e-6:     # item sits on a structural node
            if kg:
                f.add_mass(tgt, kg, I)
            return tgt
        n = f.node(xyz)
        f.beam(tgt, n, RIGID, vref=(1, 0, 0) if abs(xyz[0] - f.nodes[tgt][0]) < 1e-3 else (0, 0, 1), tag=tag or f"mount {name}")
        if kg:
            f.add_mass(n, kg, I)
        return n
    items = {}
    for m in g.get("masses", []):
        items[m["name"]] = attach(m["name"], (m["x"], m["y"], m["z"]), m["kg"], m.get("attach", "fuselage"))
    for st in g.get("seats", []):
        items[st["name"]] = attach(st["name"], (st["x"], st["y"], st["z"]), st["occupant_kg"] + st.get("seat_kg", 0.0),
                                   st.get("attach", "fuselage"), tag=f"seat attachment {st['name']}")
    from fea.geometry import pusher_list
    pushers = [attach(p.get("name", "pusher"), (p["x"], p["y"], p["z"]), p["mass_kg"], p.get("attach", "fuselage"),
                      I=(p.get("rotor_inertia_kgm2", 0.0), 0.0, 0.0), tag=f"pusher mount {p.get('name', '')}".strip())
               for p in pusher_list(g)]
    pusher = pushers[0] if pushers else None
    chute = {}
    for a in (g.get("parachute") or {}).get("attach", []):
        chute[a["name"]] = attach(a["name"], (a["x"], a["y"], a["z"]), 0.0, "fuselage+wing", tag=f"parachute fitting {a['name']}")

    # distributed structural masses
    wn = g["wing"]["mass_kg"]
    cw = np.array([float(W.chord(y)) for y in ys]) * trap_weights(ys)
    for i, nb in enumerate(box):
        f.add_mass(nb, wn * cw[i] / cw.sum())
    for n in fus:
        f.add_mass(n, fu["mass_kg"] / len(fus))
    for b in booms.values():
        for n in b["nodes"]:
            f.add_mass(n, b["spec"]["mass_kg"] / len(b["nodes"]))
    ms = mass_summary(g)
    if ms["unallocated_kg"] > 1e-6:
        f.add_mass(f.nearest(ms["cg"], fus), ms["unallocated_kg"])
    return dict(f=f, g=g, W=W, ys=ys, lines=lines, front=front, rear=rear, box=box, fus=fus, fx=fx, booms=booms, hubs=hubs,
                tail=tail, gear=gear, items=items, pusher=pusher, pushers=pushers, chute=chute, member_mass=member_mass, mass=ms, rotor_base=rotor_base)


# ============================================================================= loads -> nodal vectors
def trap_weights(y):
    """Trapezoidal tributary widths of stations y (end stations get half an interval)."""
    y = np.asarray(y, float)
    w = np.zeros_like(y)
    d = np.diff(y)
    w[:-1] += d / 2
    w[1:] += d / 2
    return w


def _add(F, n, force=(0, 0, 0), moment=(0, 0, 0)):
    F[6 * n:6 * n + 3] += force
    F[6 * n + 3:6 * n + 6] += moment


def wing_air_loads(m, F, line, tail_load=0.0):
    ys = m["ys"]
    y = np.array(line["y"])
    l = np.interp(ys, y, np.array(line["lift_per_m"]))
    cm = np.interp(ys, y, np.array(line["cm_per_m"]))
    w = trap_weights(ys)
    W = m["W"]
    f = m["f"]
    for i, yy in enumerate(ys):
        L, M = l[i] * w[i], cm[i] * w[i]
        xf, xr = f.nodes[m["front"][i]][0], f.nodes[m["rear"][i]][0]
        xcp = float(W.x_at(yy, 0.25))
        d = xr - xf
        _add(F, m["front"][i], (0, 0, L * (xr - xcp) / d + M / d))
        _add(F, m["rear"][i], (0, 0, L * (xcp - xf) / d - M / d))
    if m["tail"]:
        for n in m["tail"]:
            _add(F, n, (0, 0, tail_load / len(m["tail"])))


def rotor_loads(m, F, case, ac):
    for r, T, Q, gy in zip(ac["rotors"], case["thrust_N"], case["torque_Nm"], case["gyro_Nm"]):
        n = m["hubs"][r["name"]]
        ax = np.array(r.get("axis", (0, 0, 1.0)), float)
        _add(F, n, T * ax, -Q * ax + np.array(gy))


def build_cases(m, ac, allc):
    f = m["f"]
    nd = f.ndof
    out = {}
    cruise_T = m["g"].get("aero", {}).get("cruise_thrust_N", 0.0)
    for fc in allc["flight"]:
        F = np.zeros(nd)
        wing_air_loads(m, F, fc["line"], fc["line"]["L_tail"])
        for pn in m["pushers"]:
            _add(F, pn, (-cruise_T / len(m["pushers"]), 0, 0))
        out[fc["name"]] = F
    for rc in allc["rotor"]:
        if rc["category"] != "rotor":
            continue
        F = np.zeros(nd)
        rotor_loads(m, F, rc, ac)
        out[rc["name"]] = F
    for pc in allc["pusher"]:
        F = np.zeros(nd)
        line = LD.wing_line_loads(ac, 1.0, ac["speeds"]["VC"])
        wing_air_loads(m, F, line, line["L_tail"])
        from fea.geometry import pusher_list
        for pn, p, T, Q, gy in zip(m["pushers"], pusher_list(m["g"]), pc["thrust_N"], pc["torque_Nm"], pc["gyro_Nm"]):
            ax = np.array(p.get("axis", (-1, 0, 0)), float)
            _add(F, pn, T * ax, -Q * ax + np.array(gy))
        out[pc["name"]] = F
    for lc in allc["landing"]:
        F = np.zeros(nd)
        for rr in lc["reactions"]:
            _add(F, m["gear"][rr["point"]], rr["F"])
        if lc.get("rotor_lift_N"):
            for n in m["hubs"].values():
                _add(F, n, (0, 0, lc["rotor_lift_N"] / len(m["hubs"])))
        out[lc["name"]] = F
    for cc in allc["parachute"]:
        F = np.zeros(nd)
        u = np.array(cc["direction"])
        for a in cc["attach"]:
            _add(F, m["chute"][a["name"]], u * cc["total_N"] / len(cc["attach"]))
        out[cc["name"]] = F
    return out


# ============================================================================= margins
def allowables(sec: Section):
    """(Ft, Fc, Fs) design allowables for a beam section, Pa."""
    if sec.kind == "tube_layers":
        return sec.meta["eps_t"] * sec.E, sec.meta["eps_c"] * sec.E, sec.meta["gamma"] * sec.G
    key = sec.material
    if key.endswith("_qi") or key.endswith("_45"):
        key = key.rsplit("_", 1)[0]
    m = MAT.get(key)
    if m is None:
        return None
    d = m["design"]
    if m["kind"] == "tube":
        return d["Ft"], d["Fc"], d["Fs"]
    if m["kind"] == "lamina":
        if sec.kind == "cap_web":
            return d["Xt"], d["Xc"], None
        # quasi-isotropic / +-45 laminate of fabric: strain cut-off on the laminate modulus
        cut = MAT[key]["knockdowns"]["strain_cutoff"]
        return cut["tension"] * sec.E, cut["compression"] * sec.E, cut["shear"] * sec.G
    if m["kind"] == "isotropic":
        return d["Ftu"], d.get("Fty", d["Ftu"]), d["Fsu"]
    return None


def web_shear_allowable(sec: Section):
    if sec.kind != "cap_web":
        return None
    d = MAT[sec.meta["web_material"]]["design"]
    return 0.5 * min(d["Xt"], d["Xc"])      # +-45 web: shear carried as +-45 fibre tension / compression


def member_check(f, u, scale=ULT):
    rows = []
    for st, (a, b, sec, vref, tag) in zip(f.stresses(u), f.elems):
        if sec is RIGID or sec is PIN or sec is SLIDE_X or tag in ("rib", "gear damper"):
            continue
        N, My, Mz = st["N"] * scale, st["My"] * scale, st["Mz"] * scale
        if sec.round:
            bend = math.hypot(My, Mz) * sec.cy / sec.Iy
        else:
            bend = abs(My) * sec.cz / sec.Iy + abs(Mz) * sec.cy / sec.Iz
        smax, smin = N / sec.A + bend, N / sec.A - bend
        tau = st["tau"] * scale
        if sec.kind in ("tube", "tube_layers"):
            tau += math.hypot(st["Vy"], st["Vz"]) * scale / (sec.A / 2)
        al = allowables(sec)
        r = dict(tag=tag, elem=(a, b), sigma_t=smax, sigma_c=smin, tau=tau, tau_web=st["tau_v"] * scale + (tau if sec.kind == "cap_web" else 0),
                 N=N, M=math.hypot(My, Mz), T=st["T"] * scale)
        if sec.kind == "skin_box":
            r.update(sigma_t=0.0, sigma_c=0.0)
            al = (None, None, MAT[sec.material]["knockdowns"]["strain_cutoff"]["shear"] * sec.G)
        if al:
            Ft, Fc, Fs = al
            ms = []
            if Ft and smax > 0:
                ms.append(("tension", Ft / smax - 1))
            if Fc and smin < 0:
                ms.append(("compression", Fc / -smin - 1))
            if Fs and tau > 0 and sec.kind != "cap_web":
                ms.append(("shear", Fs / tau - 1))
            wa = web_shear_allowable(sec)
            if wa and r["tau_web"] > 0:
                ms.append(("web shear", wa / r["tau_web"] - 1))
            if sec.kind in ("tube", "tube_layers") and smin < 0:   # local (shell) buckling of the tube wall
                t = sec.meta["t"]
                R = sec.meta["od"] / 2 - t / 2
                scr = 0.3 * sec.E * t / R
                ms.append(("tube local buckling (0.3 E t/R)", scr / -smin - 1))
            if ms:
                worst = min(ms, key=lambda x: x[1])
                r.update(MS=worst[1], mode=worst[0], ratios={k: 1.0 / (1.0 + v) for k, v in ms})
        rows.append(r)
    return rows


def fitting_loads(f, u, scale=ULT):
    """Resultants carried by the stiff links (fittings): ultimate, before the fitting factor."""
    out = {}
    for fl, (a, b, sec, vref, tag) in zip(f.element_forces(u), f.elems):
        if ((sec is not RIGID and sec is not PIN and sec is not SLIDE_X) and tag != "gear damper") or tag in ("rib",):
            continue
        Fv = np.array(fl[0:3]) * scale
        Mv = np.array(fl[3:6]) * scale
        rec = out.setdefault(tag, dict(F=0.0, M=0.0))
        rec["F"] = max(rec["F"], float(np.linalg.norm(Fv)))
        rec["M"] = max(rec["M"], float(np.linalg.norm(Mv)))
    return out


# ============================================================================= analysis
def analyse(m, ac, allc, verbose=True):
    f = m["f"]
    support = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    cases = build_cases(m, ac, allc)
    res = {}
    gvec = (0, 0, -G0)
    for name, F in cases.items():
        u, info = f.solve_inertia_relief(F, support, gravity=gvec)
        rows = member_check(f, u)
        groups = {}
        for r in rows:
            gname = r["tag"]
            gr = groups.setdefault(gname, dict(sigma_t=0.0, sigma_c=0.0, tau=0.0, tau_web=0.0, M=0.0, T=0.0, N=0.0, MS=np.inf, mode=""))
            gr["sigma_t"] = max(gr["sigma_t"], r["sigma_t"])
            gr["sigma_c"] = min(gr["sigma_c"], r["sigma_c"])
            for k in ("tau", "tau_web", "M", "T"):
                gr[k] = max(gr[k], abs(r[k]))
            gr["N"] = max(gr["N"], abs(r["N"]), key=abs)
            if r.get("MS", np.inf) < gr["MS"]:
                gr["MS"], gr["mode"] = r["MS"], r["mode"]
        disp = u.reshape(-1, 6)[:, :3]
        rel = disp - disp[support]
        tip = [m["front"][0], m["front"][-1]]
        boom_ends = [b["nodes"][0] for b in m["booms"].values()] + [b["nodes"][-1] for b in m["booms"].values()]
        res[name] = dict(groups=groups, fittings=fitting_loads(f, u),
                         limit_wing_tip_dz_mm=float(max(abs(rel[n, 2]) for n in tip) * 1000),
                         limit_boom_end_dz_mm=float(max(abs(rel[n, 2]) for n in boom_ends) * 1000),
                         limit_max_disp_mm=float(np.linalg.norm(rel, axis=1).max() * 1000),
                         accel_g=(info["accel"] / G0).tolist(), alpha=info["alpha"].tolist(),
                         support_residual_N=float(np.linalg.norm(info["reaction"][:3])))
        if verbose:
            worst = min(groups.items(), key=lambda kv: kv[1]["MS"])
            print(f"{name[:66]:66s} a_z {info['accel'][2] / G0:+5.2f} g  tip {res[name]['limit_wing_tip_dz_mm']:6.1f} mm  "
                  f"min MS {worst[1]['MS']:+.2f} ({worst[0]}, {worst[1]['mode']})")
    return res


def envelope(res):
    env = {}
    for case, r in res.items():
        for gname, gr in r["groups"].items():
            e = env.setdefault(gname, dict(MS=np.inf))
            if gr["MS"] < e["MS"]:
                e.update(MS=gr["MS"], mode=gr["mode"], case=case, sigma_t=gr["sigma_t"], sigma_c=gr["sigma_c"], tau=gr["tau"])
    fit = {}
    for case, r in res.items():
        for tag, v in r["fittings"].items():
            k = tag
            e = fit.setdefault(k, dict(F=0.0, M=0.0, case_F="", case_M=""))
            if v["F"] > e["F"]:
                e.update(F=v["F"], case_F=case)
            if v["M"] > e["M"]:
                e.update(M=v["M"], case_M=case)
    for v in fit.values():
        v["F_design"] = v["F"] * FITTING_FACTOR
        v["M_design"] = v["M"] * FITTING_FACTOR
    return env, fit


def modal(m, ac, n=20):
    f = m["f"]
    fr, V = f.modes(n)
    _, M = f.assemble()
    Md = M.diagonal()
    grp = {}
    for k, nodes in (("wing", m["front"] + m["rear"] + m["box"]), ("fuselage", m["fus"]), ("tail", m["tail"])):
        for nn in nodes:
            grp[nn] = k
    for bname, b in m["booms"].items():
        for nn in b["nodes"]:
            grp[nn] = "booms"
    for nn in m["hubs"].values():
        grp[nn] = "rotors"
    modes = []
    for k, fk in enumerate(fr):
        if fk < 0.5:
            continue
        ke = {}
        for node in range(len(f.nodes)):
            e = float(np.sum(Md[6 * node:6 * node + 3] * V[6 * node:6 * node + 3, k] ** 2))
            gk = grp.get(node, "items")
            ke[gk] = ke.get(gk, 0.0) + e
        tot = sum(ke.values()) or 1.0
        modes.append(dict(f_hz=float(fk), energy={kk: round(v / tot, 3) for kk, v in sorted(ke.items(), key=lambda kv: -kv[1]) if v / tot > 0.02}))
    rot = []
    T_h = LD.allocate(ac["rotors"], ac["mtow_kg"] * G0, ac["x_cg"], 0.0)["T"]
    for r, gr, th in zip(ac["rotors"], m["g"]["rotors"], T_h):
        rpm_h = gr.get("rpm_hover") or r["rpm_max"] * math.sqrt(th / r["T_max"])
        rot.append(dict(rotor=r["name"], rpm_hover=rpm_h, f1P_hover=rpm_h / 60, f1P_max=r["rpm_max"] / 60,
                        fNP_hover=gr.get("blades", 2) * rpm_h / 60, fNP_max=gr.get("blades", 2) * r["rpm_max"] / 60))
    return dict(modes=modes, rotor_excitation=rot, note="free-free modes; energy = kinetic-energy share by component")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("geometry", nargs="?")
    ap.add_argument("selected", nargs="?")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--sizing", default=None, help="sizing update (e.g. fea/results/sizing_update.json); 'none' for the raw geometry")
    a = ap.parse_args()
    upd = HERE / "results" / "sizing_update.json"
    sz = None if a.sizing == "none" else (a.sizing or (str(upd) if upd.exists() and a.geometry and "design" in a.geometry else None))
    g = load(a.geometry, sizing=sz)
    sel = json.loads(Path(a.selected).read_text()) if a.selected else None
    tag = a.tag or ("placeholder" if "placeholder" in g["_path"] else "design")
    ac = LD.aircraft_from_geometry(g, sel)
    m = build(g)
    f = m["f"]
    mt, cg, I = f.mass_properties()
    if not g.get("cg"):
        ac["x_cg"] = float(cg[0])          # trim (tail load, thrust allocation) about the cg of the distributed model
    allc = LD.all_cases(ac)
    print(f"model: {len(f.nodes)} nodes, {len(f.elems)} elements; mass {mt:.1f} kg (budget {m['mass']['mtow_kg']:.1f}), "
          f"cg {np.round(cg, 3).tolist()}")
    res = analyse(m, ac, allc)
    env, fit = envelope(res)
    md = modal(m, ac)
    print("\nmember envelope (ultimate):")
    for k, v in sorted(env.items(), key=lambda kv: kv[1]["MS"]):
        print(f"  {k:28s} MS {v['MS']:+7.2f}  {v['mode']:32s} {v['case'][:60]}")
    print("\nfitting design loads (ultimate x 1.15):")
    for k, v in sorted(fit.items()):
        print(f"  {k:44s} F {v['F_design'] / 1e3:7.2f} kN  M {v['M_design'] / 1e3:6.2f} kN m")
    print("\nmodes (Hz):", [round(x["f_hz"], 1) for x in md["modes"][:10]])
    print("rotor 1P hover/max (Hz):", sorted({(round(r["f1P_hover"], 1), round(r["f1P_max"], 1)) for r in md["rotor_excitation"]}))
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    crash = allc["crash"]
    (out / f"airframe_{tag}.json").write_text(json.dumps(dict(
        geometry=g["_path"], ultimate_factor=ULT, fitting_factor=FITTING_FACTOR, model=dict(nodes=len(f.nodes), elems=len(f.elems)),
        mass=dict(model_kg=mt, cg=cg.tolist(), inertia=I.tolist(), budget=m["mass"], member_section_mass_kg=m["member_mass"]),
        vn={k: v for k, v in allc["vn"].items() if k != "curves"}, envelope=env, fittings=fit, cases=res, modes=md,
        crash_attachment_loads=crash, one_motor_out=[r for r in allc["rotor"] if r["category"] == "info"][0]["table"],
        motor_mount_checks={r["name"]: r["mount"] for r in allc["rotor"] if "mount" in r}), indent=1, default=float))


if __name__ == "__main__":
    main()


# ============================================================================= helpers for detailed analyses
def run_all(g, sel=None):
    """Build the model, run every case; returns (model, ac, cases dict, {case: u})."""
    ac = LD.aircraft_from_geometry(g, sel)
    m = build(g)
    f = m["f"]
    if not g.get("cg"):
        ac["x_cg"] = float(f.mass_properties()[1][0])
    allc = LD.all_cases(ac)
    cases = build_cases(m, ac, allc)
    support = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    U = {}
    for name, F in cases.items():
        U[name], _ = f.solve_inertia_relief(F, support, gravity=(0, 0, -G0))
    return m, ac, allc, U


def link_vectors(m, U, prefix, scale=ULT, at="b"):
    """Ultimate force/moment vectors (global axes) transmitted by the stiff links whose tag starts with prefix, applied
    BY the link TO its second node (the attached part), per case: {tag: [{case, F, M, node_xyz}]}."""
    f = m["f"]
    out = {}
    for e, (a, b, sec, vref, tag) in enumerate(f.elems):
        if not tag.startswith(prefix):
            continue
        p1, p2 = f.nodes[a], f.nodes[b]
        T, _ = f._T(p1, p2, vref)
        L = np.linalg.norm(p2 - p1)
        for case, u in U.items():
            ue = u[np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]]
            fg = T.T @ (f._k_local(L, sec) @ (T @ ue))
            if at == "b":   # end force at node b acts ON the element; the element acts on node b with the opposite sign
                F_, M_, pt = -fg[6:9], -fg[9:12], p2
            else:           # load put INTO the link by node a (e.g. boom -> clamp), moments about node a
                F_, M_, pt = fg[0:3], fg[3:6], p1
            out.setdefault(tag, []).append(dict(case=case, F=(F_ * scale).tolist(), M=(M_ * scale).tolist(),
                                                node_xyz=pt.tolist(), base_xyz=p1.tolist()))
    return out


def member_resultants(m, U, tag, scale=ULT):
    """Envelope of internal forces along a member group: rows (x, y, z, max|N|, max|Vy|, max|Vz|, max|T|, max|My|, max|Mz|)."""
    f = m["f"]
    rows = {}
    for case, u in U.items():
        for fl, (a, b, sec, vref, tg) in zip(f.element_forces(u), f.elems):
            if tg != tag:
                continue
            key = (a, b)
            r = rows.setdefault(key, np.zeros(6))
            vals = np.maximum(np.abs(fl[:6]), np.abs(fl[6:])) * scale
            rows[key] = np.maximum(r, vals)
    out = []
    for (a, b), v in rows.items():
        p = 0.5 * (f.nodes[a] + f.nodes[b])
        out.append([*p.tolist(), *v.tolist()])
    return np.array(sorted(out))
