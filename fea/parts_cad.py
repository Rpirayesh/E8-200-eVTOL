"""CalculiX C3D10 analyses of the critical fittings on the WP G CAD parts (cad/parts/<ID>/<ID>.step) -> fea/results/parts_cad.json

    ~/tools/cadenv/bin/python fea/parts_cad.py [ID ...]

Design-change checks before the CAD is revised: FEA_CAD_PARTS=<dir with ID/ID.step> and FEA_RESULTS=<file name> run the
same cases on a modified STEP and write to fea/results/<file name> instead of parts_cad.json.

Same loads, fitting factor, boundary-condition idealisation and margin definitions as fea/parts.py (parametric models);
supports and loaded surfaces are found on the STEP geometry by their cylinder radius and axis (bolt holes, pin eyes, bores,
sockets). Loads are rotated from aircraft axes into the part modelling frame with the CAD instance matrix
(cad/parts.json). Peak stresses are multiplied by the mesh factor of validation D6 in fea/margins.py.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import ccx  # noqa: E402
from fea import parts as PT  # noqa: E402
from fea.geometry import ROOT  # noqa: E402

HERE = Path(__file__).resolve().parent
CAD = ROOT / "cad"
PARTS = Path(__import__("os").environ.get("FEA_CAD_PARTS", str(CAD / "parts")))
RESULTS = __import__("os").environ.get("FEA_RESULTS", "parts_cad.json")
FF = PT.FF


def cyl_features(shape):
    from build123d import GeomType
    out = []
    for f in shape.faces():
        if f.geom_type == GeomType.CYLINDER:
            ax = f.axis_of_rotation
            out.append(dict(r=float(f.radius), axis=np.array([ax.direction.X, ax.direction.Y, ax.direction.Z]),
                            pos=np.array([ax.position.X, ax.position.Y, ax.position.Z])))
    return out


def faces_on(m, faces, feats, r, axis, tol=0.3):
    """Mesh boundary faces lying on any CAD cylinder of radius r and axis direction axis."""
    sel = []
    cen, nrm, area = ccx.face_props(m, faces)
    for ft in feats:
        ax_ = np.abs(np.asarray(axis, float)) / np.linalg.norm(axis)
        if abs(ft["r"] - r) > 0.05 or not np.allclose(np.abs(ft["axis"]) / np.linalg.norm(ft["axis"]), ax_, atol=0.01):
            continue
        a = ft["axis"] / np.linalg.norm(ft["axis"])
        d = cen - ft["pos"]
        rad = np.linalg.norm(d - np.outer(d @ a, a), axis=1)
        sel.append(np.where(np.abs(rad - r) < tol)[0])
    idx = np.unique(np.concatenate(sel)) if sel else np.array([], int)
    return faces[idx], idx


def groups_by_axis(m, faces, feats, r, axis, tol=0.3):
    """One face group per CAD cylinder (e.g. each bolt hole separately)."""
    out = []
    cen, _, _ = ccx.face_props(m, faces)
    seen = []
    for ft in feats:
        ax_ = np.abs(np.asarray(axis, float)) / np.linalg.norm(axis)
        if abs(ft["r"] - r) > 0.05 or not np.allclose(np.abs(ft["axis"]) / np.linalg.norm(ft["axis"]), ax_, atol=0.01):
            continue
        a = ft["axis"] / np.linalg.norm(ft["axis"])
        key = tuple(np.round(ft["pos"] - (ft["pos"] @ a) * a, 1))
        if key in seen:
            continue
        seen.append(key)
        d = cen - ft["pos"]
        rad = np.linalg.norm(d - np.outer(d @ a, a), axis=1)
        idx = np.where(np.abs(rad - r) < tol)[0]
        if len(idx):
            _, _, ar = ccx.face_props(m, faces[idx])
            c = (cen[idx] * ar[:, None]).sum(axis=0) / ar.sum()
            out.append((faces[idx], c, a))
    return out


def bc_faces(m, faces, feats, spec):
    """spec: (r, axis) cylinder; ('plane', k, 'min'|'max'|'largest'|'both') planar faces normal to global axis k of the part."""
    if spec[0] == "pcd":                           # ("pcd", hole r, axis, centre xyz, bolt-circle radius): holes on one circle
        _, r, ax, c0, pcd = spec
        out = [gq[0] for gq in groups_by_axis(m, faces, feats, r, ax)
               if abs(np.linalg.norm((gq[1] - np.asarray(c0)) - ((gq[1] - np.asarray(c0)) @ np.asarray(ax)) * np.asarray(ax)) - pcd) < 3.0]
        return np.concatenate(out)
    if spec[0] != "plane":
        return faces_on(m, faces, feats, spec[0], spec[1])[0]
    _, k, which = spec
    cen, nrm, area = ccx.face_props(m, faces)
    sel = np.abs(np.abs(nrm[:, k]) - 1) < 1e-3
    lv = np.round(cen[sel, k], 1)
    if not sel.any():
        raise ValueError("no planar faces")
    levels = {}
    for v, a in zip(lv, area[sel]):
        levels[v] = levels.get(v, 0) + a
    if which == "min":
        keep = [min(levels)]
    elif which == "max":
        keep = [max(levels)]
    elif which == "both":
        keep = [min(levels), max(levels)]
    else:
        keep = [max(levels, key=levels.get)]
    idx = np.where(sel)[0][np.isin(lv, keep)]
    return faces[idx]


def boom_bore(pid):
    """Inner boom bore radius of a clamp (follows the boom over-wrap OD of the CAD build)."""
    from build123d import import_step
    feats = cyl_features(import_step(str(PARTS / pid / f"{pid}.step")))
    rs = [f["r"] for f in feats if abs(abs(f["axis"][0]) - 1) < 1e-3 and 50 < f["r"] < 66]
    return min(rs)


def instance_R(pid):
    parts = {it["id"]: it for it in json.loads((CAD / "parts.json").read_text())["parts"]}
    T = np.array(parts[pid]["instances"][0], float)
    return T[:3, :3]


def run(pid, mt, hmax, hmin, bc_spec, load_fn, title, excl=None):
    from build123d import import_step
    shape = import_step(str(PARTS / pid / f"{pid}.step"))
    feats = cyl_features(shape)
    try:                                   # the CAD material key governs (e.g. LG-DUP changed to 7075-T6)
        cm = {it["id"]: it for it in json.loads((CAD / "parts.json").read_text())["parts"]}[pid]["material"]
        if cm in PT.MAT and PT.MAT[cm]["kind"] == "isotropic":
            mt = PT.mat(cm)
    except (KeyError, StopIteration):
        pass
    work = PT.WORK / f"cad_{pid}"
    for straight in (False, True):
        m = ccx.mesh_solid(shape, work, hmax, hmin, None, straight=straight)
        faces = ccx.boundary_faces(m)
        fx = np.concatenate([bc_faces(m, faces, feats, b) for b in bc_spec])
        fixed = PT.nodes_of(fx)
        loads, loaded = load_fn(m, faces, feats)
        try:
            res = ccx.solve_solid(m, mt["E"], mt["nu"], fixed, loads, work, "part")
            break
        except RuntimeError as e:
            if straight or "jacobian" not in str(e):
                raise
    out = PT.evaluate(pid, m, res, mt, fixed, loaded, (excl / 1.5) if excl else hmin)
    if excl:
        out["note"] = (f"peak evaluated >= {excl:.0f} mm from the supports and the pin-bearing surface (outside the idealised "
                       f"cosine-pressure bearing zone; bearing checked with Fbru)")
    out.update(applied_N=np.sum(np.array(list(loads.values())), axis=0).tolist(), source=f"cad/parts/{pid}/{pid}.step",
               volume_mm3=float(shape.volume), mass_kg=float(shape.volume) * 1e-9 * mt["rho"])
    PT.render(m, res, PT.IMG / f"CAD_{pid}.png", f"{title} (CAD part)\npeak {out['vm_peak_away_from_bc']:.0f} MPa (Ftu {mt['Ftu']:.0f}), "
              f"MS {out['MS_ultimate']:+.2f}", mt["Ftu"])
    PT.export_glb(m, res, PT.IMG / f"CAD_{pid}.glb", mt["Ftu"])
    print(pid, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k not in ("reaction",)})
    return out


def cradle_beam(L, g, mt):
    """CH-CRADLE: the clamp ring does not touch the posts in the CAD solid (gap, separate bodies), so the beam + posts are
    analysed with the canister loads put on the post tops: 18 g forward x 1.15 on the 28.2 kg canister, its cg taken at the
    ring centre; the forward load is shared by the posts and its overturning moment is a push-pull couple between them."""
    from build123d import import_step, Compound
    shape = import_step(str(PARTS / "CH-CRADLE" / "CH-CRADLE.step"))
    sol = sorted(shape.solids(), key=lambda q: q.volume)
    ring = sol[-1]
    body = sol[0] + sol[1] + sol[2]                       # two posts + beam
    posts = sol[:2]
    rb = ring.bounding_box()
    z_cg = 0.5 * (rb.min.Z + rb.max.Z)
    mc = g["parachute"]["kg"] * 9.80665 * FF
    Fx = -18.0 * mc
    pc = [np.array([p.center().X, p.center().Y, p.center().Z]) for p in posts]
    zt = max(p.bounding_box().max.Z for p in posts)
    dx = abs(pc[0][0] - pc[1][0])
    Fz = Fx * (z_cg - zt) / dx                           # couple between the posts
    work = PT.WORK / "cad_CH-CRADLE-BEAM"
    m = ccx.mesh_solid(body, work, 8.0, 2.5, None, straight=True)
    faces = ccx.boundary_faces(m)
    cen, nrm, area = ccx.face_props(m, faces)
    fx = bc_faces(m, faces, [], ("plane", 0, "both"))
    loads, ln = {}, []
    for k, c in enumerate(sorted(pc, key=lambda q: q[0])):
        sel = (np.abs(cen[:, 2] - zt) < 0.2) & (np.abs(cen[:, 0] - c[0]) < 12.5) & (np.abs(cen[:, 1] - c[1]) < 12.5)
        bf = faces[sel]
        Fp = np.array([Fx / 2, 0.0, (Fz if k == 0 else -Fz)])
        tr = np.outer(np.ones(len(bf)), Fp / area[sel].sum())
        for n, v in ccx.face_loads(m, bf, tr).items():
            loads[n] = loads.get(n, 0) + v
        ln.append(PT.nodes_of(bf))
    res = ccx.solve_solid(m, mt["E"], mt["nu"], PT.nodes_of(fx), loads, work, "part")
    out = PT.evaluate("CH-CRADLE", m, res, mt, PT.nodes_of(fx), np.concatenate(ln), 2.5)
    out.update(applied_N=np.sum(np.array(list(loads.values())), axis=0).tolist(), source="cad/parts/CH-CRADLE/CH-CRADLE.step (beam + posts)",
               volume_mm3=float(shape.volume), mass_kg=float(shape.volume) * 1e-9 * mt["rho"],
               note=f"ring separate from the posts in the CAD (gap); canister cg {z_cg - zt:.0f} mm above the post tops; post couple {Fz:.0f} N")
    PT.render(m, res, PT.IMG / "CAD_CH-CRADLE.png", f"CH-CRADLE beam + posts (CAD part), 18 g forward\npeak {out['vm_peak_away_from_bc']:.0f} MPa "
              f"(Ftu {mt['Ftu']:.0f}), MS {out['MS_ultimate']:+.2f}", mt["Ftu"])
    PT.export_glb(m, res, PT.IMG / "CAD_CH-CRADLE.glb", mt["Ftu"])
    print("CH-CRADLE", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k not in ("reaction",)})
    return out


def main():
    L, g = PT.global_loads()
    sel = sys.argv[1:] or ["MP", "PY-C", "LG-SADDLE", "W-FIT-MS", "W-FIT-RS", "F-CLV-MS", "BC-W", "BC-WR", "CH-ATT-R", "W-CHUTE-FIT",
                            "SEAT-FIT", "LG-LEGEND", "LG-DUP", "LG-SKCL", "TL-CLAMP", "CH-CRADLE-BEAM"]
    al6, al7, st = PT.mat("al6061_t6_extr"), PT.mat("al7075_t6_sheet"), PT.mat("steel_4130_n")
    res = {}

    def bore_load(F_g, M_g, pid, r, axis):
        R = instance_R(pid)
        F, M = R.T @ np.asarray(F_g), R.T @ np.asarray(M_g)

        def ld(m, faces, feats):
            grp = groups_by_axis(m, faces, feats, r, axis)
            bf = np.concatenate([gq[0] for gq in grp])
            c = np.mean([gq[1] for gq in grp], axis=0)
            tr = PT.bearing_traction(m, bf, c, axis, F) + PT.couple_traction(m, bf, c, axis, M)
            return ccx.face_loads(m, bf, tr), PT.nodes_of(bf)
        return ld

    for pid in sel:
        if res:
            save(res)
        if pid == "MP":
            mo = L["motor"]
            k = 1.5 * FF
            T, Q, Mg, H = mo["T_limit"] * k, mo["Q_limit"] * k * 1000, mo["gyro_limit"] * k * 1000, mo["H_limit"] * k

            def ld(m, faces, feats):
                grp = groups_by_axis(m, faces, feats, 4.0, (0, 0, 1))
                ctr = np.mean([gq[1] for gq in grp], axis=0)
                rb = np.mean([np.linalg.norm((gq[1] - ctr)[:2]) for gq in grp])
                loads, ln = {}, []
                for bf, c, a in grp:
                    ang = math.atan2(c[1] - ctr[1], c[0] - ctr[0])
                    ft = Q / (len(grp) * rb) * np.array([-math.sin(ang), math.cos(ang), 0])
                    fz = T / len(grp) + Mg * math.cos(ang) / (len(grp) * rb / 2)
                    fl = np.array([H / len(grp), 0, 0]) + ft + np.array([0, 0, fz])
                    tr = PT.bearing_traction(m, bf, c, (0, 0, 1), fl)
                    for n, v in ccx.face_loads(m, bf, tr).items():
                        loads[n] = loads.get(n, 0) + v
                    ln.append(PT.nodes_of(bf))
                return loads, np.concatenate(ln)
            res[pid] = run(pid, al6, 6.0, 2.0, [(4.2, (0, 0, 1))], ld, "MP motor plate, windows -48 %")
        elif pid == "PY-C":
            rM = L["pylon"][1]
            res[pid] = run(pid, al6, 6.0, 2.0, [(boom_bore(pid), (1, 0, 0))],
                           bore_load(np.array(rM["F"]) * FF, np.array(rM["M"]) * FF * 1000, pid, 50.15, (0, 0, 1)), "PY-C pylon saddle + socket")
        elif pid in ("W-FIT-MS", "W-FIT-RS"):
            rows = [r for r in L["wing_root_all"] if ("front" in r["tag"]) == (pid == "W-FIT-MS")]
            rF = max(rows, key=lambda r: np.linalg.norm(r["F"]))
            res[pid] = run(pid, al7, 6.0, 2.0, [(4.0, (1, 0, 0))], bore_load(np.array(rF["F"]) * FF, np.zeros(3), pid, 9.53, (1, 0, 0)),
                           f"{pid} wing-root lug", excl=6.0)
        elif pid in ("BC-W", "BC-WR"):
            rows = [r for r in L["boom_clamp_all"] if ("main" in r["tag"]) == (pid == "BC-W")]
            rF = max(rows, key=lambda r: np.linalg.norm(r["F"]))
            res[pid] = run(pid, al6, 8.0, 2.0, [(4.75, (0, 0, 1))],
                           bore_load(np.array(rF["F"]) * FF, np.array(rF["M"]) * FF * 1000, pid, boom_bore(pid), (1, 0, 0)), f"{pid} boom-wing saddle")
        elif pid in ("CH-ATT-R", "W-CHUTE-FIT"):
            P = L["chute"]["F_limit"] * 1.5 * FF
            F = np.array([P * math.sin(math.radians(45)), 0.1 * P, P * math.cos(math.radians(45))])
            res[pid] = run(pid, st, 5.0, 2.0, [(4.0, (0, 1, 0))], bore_load(F, np.zeros(3), pid, 8.0, (0, 1, 0)), f"{pid} parachute hard point")
        elif pid in ("F-CLV-MS", "F-CLV-RS"):
            rows = [r for r in L["wing_root_all"] if ("front" in r["tag"]) == (pid == "F-CLV-MS")]
            rF = max(rows, key=lambda r: np.linalg.norm(r["F"]))
            res[pid] = run(pid, al7, 6.0, 2.0, [(4.1, (0, 1, 0))], bore_load(-np.array(rF["F"]) * FF, np.zeros(3), pid, 9.57, (1, 0, 0)),
                           f"{pid} fuselage clevis 7075 (wing root)")
        elif pid == "LG-SADDLE":
            rF = L["gear"][0]
            res[pid] = run(pid, al6, 5.0, 1.5, [(4.75, (0, 0, 1))], bore_load(np.array(rF["F"]) * FF, np.zeros(3), pid, 10.1, (1, 0, 0)),
                           "LG-SADDLE pivot saddle (clevis cheeks)")
        elif pid == "LG-LEGEND":
            rF = L["gear"][0]
            from build123d import import_step
            r_plug = max(f_["r"] for f_ in cyl_features(import_step(str(PARTS / pid / f"{pid}.step"))) if abs(abs(f_["axis"][1]) - 1) < 1e-3)
            res[pid] = run(pid, al6, 5.0, 1.5, [(r_plug, (0, 1, 0))], bore_load(-np.array(rF["F"]) * FF, np.zeros(3), pid, 10.1, (1, 0, 0)),
                           "LG-LEGEND leg-end eye")
        elif pid == "LG-DUP":
            rF = L["damper_hp"][0]
            res[pid] = run(pid, al6, 5.0, 1.5, [("plane", 1, "largest")], bore_load(np.array(rF["F"]) * FF, np.zeros(3), pid, 8.1, (1, 0, 0)),
                           "LG-DUP damper upper fitting")
        elif pid == "LG-SKCL":
            from build123d import import_step
            fts = cyl_features(import_step(str(PARTS / pid / f"{pid}.step")))
            r_sock = max(f_["r"] for f_ in fts if abs(f_["axis"][0]) < 0.1)
            r_skid = max(f_["r"] for f_ in fts if abs(abs(f_["axis"][0]) - 1) < 1e-3)
            ax = np.array([0, 0.725, 0.689])
            rF = L["skid"][0]
            res[pid] = run(pid, al6, 6.0, 2.0, [(r_sock, tuple(ax))],
                           bore_load(np.array(rF["F"]) * FF, np.zeros(3), pid, r_skid, (1, 0, 0)), "LG-SKCL skid clamp")
        elif pid == "TL-CLAMP":
            rT = L["tail_end"]
            res[pid] = run(pid, al6, 6.0, 2.0, [(boom_bore(pid), (1, 0, 0))],
                           bore_load(-np.array(rT["F"]) * FF, -np.array(rT["M"]) * FF * 1000, pid, 25.15, (0, 1, 0)), "TL-CLAMP tail clamp")
        elif pid == "CH-CRADLE-BEAM":
            res["CH-CRADLE"] = cradle_beam(L, g, al6)
        elif pid == "MP-EMX":
            from build123d import import_step
            shp = import_step(str(PARTS / pid / f"{pid}.step"))
            bb = shp.bounding_box()
            c0 = np.array([(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2, 0.0])
            fts = [f_ for f_ in cyl_features(shp) if abs(f_["r"] - 4.2) < 0.05]
            radii = sorted({round(float(np.linalg.norm((f_["pos"] - c0)[:2])), 0) for f_ in fts})
            pcd_mp = min(radii, key=lambda r_: abs(r_ - 90.0))           # P3 motor-plate bolt circle (PCD 180)
            pcd_em = [r_ for r_ in radii if r_ != pcd_mp][0]
            mo = L["motor"]
            k = 1.5 * FF
            T, Q, Mg, H = mo["T_limit"] * k, mo["Q_limit"] * k * 1000, mo["gyro_limit"] * k * 1000, mo["H_limit"] * k

            def ld(m, faces, feats):
                grp = [gq for gq in groups_by_axis(m, faces, feats, 4.2, (0, 0, 1))
                       if abs(np.linalg.norm((gq[1] - c0)[:2]) - pcd_em) < 3.0]
                loads, ln = {}, []
                for bf, c, a in grp:
                    ang = math.atan2(c[1] - c0[1], c[0] - c0[0])
                    ft = Q / (len(grp) * pcd_em) * np.array([-math.sin(ang), math.cos(ang), 0])
                    fz = T / len(grp) + Mg * math.cos(ang) / (len(grp) * pcd_em / 2)
                    fl = np.array([H / len(grp), 0, 0]) + ft + np.array([0, 0, fz])
                    tr = PT.bearing_traction(m, bf, c, (0, 0, 1), fl)
                    for n, v in ccx.face_loads(m, bf, tr).items():
                        loads[n] = loads.get(n, 0) + v
                    ln.append(PT.nodes_of(bf))
                return loads, np.concatenate(ln)
            res[pid] = run(pid, al6, 5.0, 2.0, [("pcd", 4.2, (0, 0, 1), c0, pcd_mp)], ld,
                           f"MP-EMX EMRAX adapter ring (EMRAX bolts r {pcd_em:.0f}, plate bolts r {pcd_mp:.0f})")
        elif pid == "PB-PLUG":
            from fea.geometry import pusher_list
            pu = pusher_list(g)[0]
            k = 1.5 * FF
            Om = 2 * math.pi * pu["rpm_max"] / 60
            T = pu["max_thrust_N"] * k
            Q = pu["max_torque_Nm"] * 1.25 * k * 1000
            Mg = pu.get("rotor_inertia_kgm2", 0.0) * Om * 2.5 * k * 1000         # CS-23.371 yaw 2.5 rad/s
            Fd = 2.5 * pu["mass_kg"] * 9.80665 * k                               # 2.5 g on the unit

            def ld(m, faces, feats):
                grp = groups_by_axis(m, faces, feats, 4.2, (1, 0, 0))
                ctr = np.mean([gq[1] for gq in grp], axis=0)
                rb = np.mean([np.linalg.norm((gq[1] - ctr)[1:]) for gq in grp])
                loads, ln = {}, []
                for bf, c, a in grp:
                    ang = math.atan2(c[2] - ctr[2], c[1] - ctr[1])
                    ft = Q / (len(grp) * rb) * np.array([0, -math.sin(ang), math.cos(ang)])
                    fx = -T / len(grp) + Mg * math.cos(ang) / (len(grp) * rb / 2)
                    fl = np.array([fx, 0, -Fd / len(grp)]) + ft
                    tr = PT.bearing_traction(m, bf, c, (1, 0, 0), fl)
                    for n, v in ccx.face_loads(m, bf, tr).items():
                        loads[n] = loads.get(n, 0) + v
                    ln.append(PT.nodes_of(bf))
                return loads, np.concatenate(ln)
            res[pid] = run(pid, al6, 7.0, 2.5, [(50.6, (1, 0, 0))], ld, "PB-PLUG pusher boom-end plug")
        elif pid == "CH-CRADLE":
            mc = g["parachute"]["kg"] * 9.80665 * FF
            F = np.array([-18.0, 0.0, -1.0]) * mc
            axc = np.array([0.3, 0, 0.95]) / np.linalg.norm([0.3, 0, 0.95])
            res[pid] = run(pid, al6, 9.0, 3.0, [("plane", 0, "both")], bore_load(F, np.zeros(3), pid, 160.5, tuple(np.round(axc, 2))),
                           "CH-CRADLE parachute cradle, 18 g forward")
        elif pid == "SEAT-FIT":
            se = L["seat"]
            Fs = max(9.0 * 1.33, 26.0) * se["m"] * 9.80665
            F = np.array([Fs / 4, 0, Fs * se["h_cg"] * 1000 / 450.0 / 2])
            res[pid] = run(pid, al7, 4.0, 1.5, [(4.0, (0, 0, 1))], bore_load(F, np.zeros(3), pid, 4.75, (0, 1, 0)), "SEAT-FIT seat-leg fitting")
    save(res)


def save(res):
    path = HERE / "results" / RESULTS
    allr = json.loads(path.read_text()) if path.exists() else {}
    allr.update(res)
    path.write_text(json.dumps(allr, indent=1, default=float))


if __name__ == "__main__":
    main()
