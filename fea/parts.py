"""Detailed CalculiX (C3D10) analyses of the critical fittings -> fea/results/parts.json, docs/models/fea/*.png / *.glb

    ~/tools/cadenv/bin/python fea/parts.py [P1 ... P6]

The CAD package (cad/parts/<ID>/) did not exist when this was run, so each fitting is modelled here as a parametric
build123d solid with the dimensions written in PARTS (to be adopted / replaced by WP G). Loads come from the global beam
model with the sized sections (fea/results/sizing_update.json): the worst case of every link, ultimate (x 1.5) and
x 1.15 fitting factor (seat fittings: max of 1.33 x CS-23.561 static and the AC 23.562 26 g peak).

P1 wing-root lug (7075-T6), P2 boom-wing saddle clamp (6061-T6), P3 motor plate on the rotor pylon (6061-T6),
P4 gear cross-tube saddle (6061-T6), P5 parachute riser hard point (4130 N), P6 seat-leg fitting (7075-T6).
Boundary conditions: bolt-hole surfaces fixed (stiff structure behind); loads as bearing tractions on pin/tube
surfaces or at the motor bolt holes. Units N, mm, MPa.
Margins: MS_ult = Ftu / sigma_vm - 1 on the peak von Mises away from the fixed/loaded nodes (>= 1.5 h_min), and
MS_yield = Fty / (sigma_vm / 1.5) - 1 at limit load; analytic lug / bolt / bearing checks in addition.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import airframe as AF  # noqa: E402
from fea import ccx  # noqa: E402
from fea.geometry import MAT, ROOT, load  # noqa: E402

HERE = Path(__file__).resolve().parent
WORK = HERE / ".cache" / "parts"
IMG = ROOT / "docs" / "models" / "fea"
FF = 1.15
KSI = 6.894757


def mat(key):
    d = MAT[key]["design"]
    return dict(E=MAT[key]["E"] / 1e6, nu=MAT[key]["nu"], Ftu=d["Ftu"] / 1e6, Fty=d.get("Fty", d["Ftu"]) / 1e6, Fsu=d["Fsu"] / 1e6,
                Fbru=d.get("Fbru_eD2", 1.5 * d["Ftu"]) / 1e6, name=MAT[key]["name"], rho=MAT[key]["rho"])


# ============================================================================= loads from the global model
def global_loads():
    upd = HERE / "results" / "sizing_update.json"
    g = load(ROOT / "design" / "geometry.json", sizing=upd if upd.exists() else None)
    m, ac, allc, U = AF.run_all(g)

    def worst(prefix, at="b"):
        lv = AF.link_vectors(m, U, prefix, at=at)
        rows = [r | dict(tag=t) for t, rr in lv.items() for r in rr]
        rF = max(rows, key=lambda r: np.linalg.norm(r["F"]))
        rM = max(rows, key=lambda r: np.linalg.norm(r["M"]))
        return rF, rM
    out = dict(wing_root=worst("wing root fitting"), boom_clamp=worst("boom saddle", at="a"), gear=worst("gear attach", at="a"))
    for key, pre, at in (("skid", "skid saddle", "a"), ("damper_hp", "gear damper hard point", "a")):
        try:
            out[key] = worst(pre, at=at)
        except ValueError:
            pass
    yb_ = abs(g["booms"][0]["y"])
    tl = [r | dict(tag=t) for t, rr in AF.link_vectors(m, U, "tail spar", at="a").items() for r in rr
          if abs(abs(r["base_xyz"][1]) - yb_) < 1e-6]
    if tl:
        out["tail_end"] = max(tl, key=lambda r: np.linalg.norm(r["M"]))
    out["wing_root_all"] = [r | dict(tag=t) for t, rr in AF.link_vectors(m, U, "wing root fitting").items() for r in rr]
    out["boom_clamp_all"] = [r | dict(tag=t) for t, rr in AF.link_vectors(m, U, "boom saddle", at="a").items() for r in rr]
    lv = AF.link_vectors(m, U, "rotor pylon", at="a")
    zb = g["booms"][0]["z"]
    rows = [r | dict(tag=t) for t, rr in lv.items() for r in rr if abs(r["base_xyz"][2] - zb) < 1e-6]
    out["pylon"] = (max(rows, key=lambda r: np.linalg.norm(r["F"])), max(rows, key=lambda r: np.linalg.norm(r["M"])))
    mounts = [r["mount"] for r in allc["rotor"] if "mount" in r]
    rot = ac["rotors"][0]
    gyro = max(np.linalg.norm(mm[0]["M_Nm"][:2]) for mm in mounts)
    out["motor"] = dict(T_limit=rot["T_max"], Q_limit=rot["kQ"] * rot["T_max"] * ac.get("torque_fault_factor", 1.25), gyro_limit=gyro,
                        H_limit=0.1 * rot["T_max"], down_limit=2.5 * rot.get("mass_kg", 21.1) * 0.75 * 9.80665)
    p = g["parachute"]
    out["chute"] = dict(F_limit=p.get("opening_load_N", 47400.0) * p.get("max_share", 0.5))
    seat_m = g["seats"][0]["occupant_kg"] + g["seats"][0]["seat_kg"]
    out["seat"] = dict(m=seat_m, h_cg=g["seats"][0]["z"] - g["fuselage"]["cabin"]["floor_z"])
    return out, g


# ============================================================================= helpers
def bearing_traction(m, faces, center, axis, F, width_axis=None):
    """Cosine bearing pressure on the half of a cylindrical surface facing the load F (vector, N) about 'axis'."""
    cen, nrm, area = ccx.face_props(m, faces)
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    Fd = np.asarray(F, float)
    Fp = Fd - axis * (Fd @ axis)                          # radial part
    Fa = Fd @ axis                                        # axial part, shared as uniform shear traction
    dirr = Fp / (np.linalg.norm(Fp) + 1e-30)
    r = cen - center
    r = r - np.outer(r @ axis, axis)
    rn = r / np.linalg.norm(r, axis=1)[:, None]
    w = np.clip(rn @ dirr, 0, None)                       # pin presses on the side the load points to
    tr = np.outer(w, dirr)
    s = (tr * area[:, None]).sum(axis=0) @ dirr
    tr = tr * np.linalg.norm(Fp) / s if s > 0 else tr
    tr = tr + np.outer(np.ones(len(faces)), axis * Fa / area.sum())
    return tr


def couple_traction(m, faces, center, axis, M):
    """Traction field on a cylindrical bore that transmits a moment M (about axes normal to the bore axis) as linearly
    varying bearing along the bore, plus torsion about the bore axis as tangential shear."""
    cen, nrm, area = ccx.face_props(m, faces)
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    M = np.asarray(M, float)
    tr = np.zeros((len(faces), 3))
    xi = (cen - center) @ axis
    Mt = M @ axis
    Mb = M - axis * Mt
    if np.linalg.norm(Mb) > 0:
        d = np.cross(axis, Mb / np.linalg.norm(Mb))      # force direction at positive xi for a couple Mb
        r = cen - center - np.outer(xi, axis)
        rn = r / np.linalg.norm(r, axis=1)[:, None]
        w = np.clip(np.sign(xi)[:, None] * rn @ d[:, None], 0, None)[:, 0]
        # balance the two halves so the couple carries no net force (uneven face sizes on CAD meshes)
        Sp, Sn = np.sum((w * area)[xi > 0]), np.sum((w * area)[xi < 0])
        if Sp > 0 and Sn > 0:
            w = np.where(xi > 0, w / Sp, w / Sn)
        tr = np.outer(w * np.sign(xi), d)
        Mnow = np.sum(np.cross(cen - center, tr * area[:, None]), axis=0) @ (Mb / np.linalg.norm(Mb))
        tr *= np.linalg.norm(Mb) / Mnow if Mnow != 0 else 0
    if abs(Mt) > 0:
        r = cen - center - np.outer(xi, axis)
        t_dir = np.cross(axis, r)
        rr = np.linalg.norm(r, axis=1)
        t_dir /= rr[:, None]
        tq = np.outer(np.ones(len(faces)), [1.0])[:, 0]
        Mnow = np.sum(rr * area)
        tr += t_dir * (Mt / Mnow)
    return tr


def select_cyl(m, faces, center, axis, radius, tol=0.3, xlim=None):
    cen, nrm, area = ccx.face_props(m, faces)
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    r = cen - center
    xi = r @ axis
    rad = np.linalg.norm(r - np.outer(xi, axis), axis=1)
    sel = np.abs(rad - radius) < tol
    if xlim is not None:
        sel &= (xi > xlim[0]) & (xi < xlim[1])
    return faces[sel]


def nodes_of(faces):
    return np.unique(faces.ravel())


def evaluate(name, m, res, mt, fixed, loaded, hmin, extra=None):
    P = m.nodes
    bad = np.unique(np.r_[fixed, loaded])
    from scipy.spatial import cKDTree
    tree = cKDTree(P[bad - 1])
    d, _ = tree.query(P[res["ids"] - 1])
    keep = d > 1.5 * hmin
    vm = res["vm"]
    peak = float(vm[keep].max()) if keep.any() else float(vm.max())
    at = P[res["ids"][keep][np.argmax(vm[keep])] - 1].tolist() if keep.any() else None
    out = dict(part=name, material=mt["name"], elems=len(m.elems), vm_max_all=float(vm.max()), vm_peak_away_from_bc=peak, peak_at_mm=at,
               umax_mm=float(np.linalg.norm(res["U"], axis=1).max()), reaction=res["reaction"],
               MS_ultimate=mt["Ftu"] / peak - 1, MS_yield_limit=mt["Fty"] / (peak / 1.5) - 1)
    if extra:
        out.update(extra)
    return out


def render(m, res, path, title, allow, view=(25, -60)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    faces = ccx.boundary_faces(m)
    vm = dict(zip(res["ids"], res["vm"]))
    U = dict(zip(res["ids"], res["U"]))
    size = np.ptp(m.nodes, axis=0).max()
    umax = max(np.linalg.norm(res["U"], axis=1).max(), 1e-9)
    s = 0.04 * size / umax
    tris = [[m.nodes[n - 1] + s * U[n] for n in f[:3]] for f in faces]
    vals = np.array([np.mean([vm[n] for n in f[:3]]) for f in faces])
    fig = plt.figure(figsize=(7, 5.4), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    cmap = plt.get_cmap("turbo")
    norm = plt.Normalize(0, allow)
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cmap(norm(vals)), edgecolor="none"))
    c = m.nodes.mean(axis=0)
    r = size / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(*view)
    ax.set_axis_off()
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), ax=ax, shrink=0.7)
    cb.set_label("von Mises, ultimate x fitting factor (MPa)")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def export_glb(m, res, path, allow):
    import trimesh
    import matplotlib.pyplot as plt
    faces = ccx.boundary_faces(m)
    used = np.unique(faces[:, :3])
    idx = {n: k for k, n in enumerate(used)}
    V = m.nodes[used - 1] / 1000.0
    Fc = np.array([[idx[n] for n in f[:3]] for f in faces])
    vm = dict(zip(res["ids"], res["vm"]))
    col = (plt.get_cmap("turbo")(np.clip(np.array([vm.get(n, 0) for n in used]) / allow, 0, 1)) * 255).astype(np.uint8)
    tm = trimesh.Trimesh(vertices=V, faces=Fc, vertex_colors=col, process=False)
    tm.export(path)


def run_part(name, solid, mt, hmax, hmin, refine, bc_faces_fn, load_fn, title, extra_fn=None, view=(25, -60)):
    work = WORK / name
    for straight in (False, True):      # straight-sided quadratic tets if the curved high-order mesh has bad elements
        m = ccx.mesh_solid(solid, work, hmax, hmin, refine, straight=straight)
        faces = ccx.boundary_faces(m)
        fixed_faces = bc_faces_fn(m, faces)
        fixed = nodes_of(fixed_faces)
        loads, loaded = load_fn(m, faces)
        try:
            res = ccx.solve_solid(m, mt["E"], mt["nu"], fixed, loads, work, "part")
            break
        except RuntimeError as e:
            if straight or "jacobian" not in str(e):
                raise
    extra = extra_fn() if extra_fn else None
    out = evaluate(name, m, res, mt, fixed, loaded, hmin, extra)
    Ftot = np.sum(np.array(list(loads.values())), axis=0)
    out["applied_N"] = Ftot.tolist()
    out["volume_mm3"] = float(solid.volume)
    out["mass_kg"] = float(solid.volume) * 1e-9 * mt["rho"]
    render(m, res, IMG / f"{name}.png", f"{title}\npeak {out['vm_peak_away_from_bc']:.0f} MPa (Ftu {mt['Ftu']:.0f}), MS {out['MS_ultimate']:+.2f}",
           mt["Ftu"], view)
    export_glb(m, res, IMG / f"{name}.glb", mt["Ftu"])
    print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k not in ("reaction",)})
    return out


# ============================================================================= parts
def lug_check(P, W, D, t, e, mt):
    """Simplified lug strength (Bruhn D1 / Melcon-Hoblit style): net tension, shear-out, bearing (N, mm, MPa)."""
    Pnt = 0.9 * (W - D) * t * mt["Ftu"]
    Pso = 2 * (e - D / 2 * math.cos(math.radians(40))) * t * mt["Fsu"]
    Pbr = D * t * mt["Fbru"] * min(1.0, e / D / 2.0)
    return dict(P_design_N=P, net_tension_MS=Pnt / P - 1, shear_out_MS=Pso / P - 1, bearing_MS=Pbr / P - 1)


def P1_wing_root(L):
    from build123d import Box, Cylinder, Pos, Rot
    mt = mat("al7075_t6_sheet")
    t, W, D, zc = 12.0, 60.0, 19.05, -95.0
    body = Box(170, t, 120) + Pos(0, 0, -60) * Box(W, t, 70) + Pos(0, 0, zc) * Rot(90, 0, 0) * Cylinder(W / 2, t)
    body = body - Pos(0, 0, zc) * Rot(90, 0, 0) * Cylinder(D / 2, 3 * t)
    bolts = [(x, z) for x in (-60, -20, 20, 60) for z in (-25, 25)]
    for x, z in bolts:
        body = body - Pos(x, 0, z) * Rot(90, 0, 0) * Cylinder(4.0, 3 * t)          # 5/16 in bolts
    rF, rM = L["wing_root"]
    Fg = np.array(rF["F"]) * FF
    F = np.array([Fg[1], Fg[0], Fg[2]]) * 1.0                                         # part x = global y, part y = global x
    F = F  # N

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, 0, z]), (0, 1, 0), 4.0) for x, z in bolts])

    def ld(m, faces):
        hf = select_cyl(m, faces, np.array([0, 0, zc]), (0, 1, 0), D / 2)
        tr = bearing_traction(m, hf, np.array([0, 0, zc]), (0, 1, 0), F)
        return ccx.face_loads(m, hf, tr), nodes_of(hf)
    e = W / 2
    ex = lambda: dict(load_case=rF["case"], design_load_N=F.tolist(), lug=lug_check(np.linalg.norm(F[[0, 2]]), W, D, t, e, mt),
                      bolts=bolt_check(np.linalg.norm(F), 8, 5 / 16 * 25.4, t, mt), dims=dict(t=t, lug_width=W, pin_D=D, bolts="8 x AN5"))
    return run_part("P1_wing_root_lug", body, mt, 7.0, 2.5, [(0, 0, zc, 30, 2.5)], bc, ld,
                    "P1 wing-root lug, 7075-T6, 12 mm", ex)


def bolt_check(F, n, d, t_plate, mt, Fsu_bolt=75 * KSI):
    A = math.pi / 4 * d**2
    Pshear = n * A * Fsu_bolt
    Pbr = n * d * t_plate * mt["Fbru"]
    return dict(n=n, d_mm=d, shear_MS=Pshear / F - 1, bearing_MS=Pbr / F - 1)


def saddle(ID, wall, width, pad_w, pad_t, bolt_d, bolt_xy):
    from build123d import Box, Cylinder, Pos, Rot
    Ro = ID / 2 + wall
    ring = Rot(0, 90, 0) * Cylinder(Ro, width)                                       # axis along x
    pad = Pos(0, 0, Ro + pad_t / 2 - wall / 2) * Box(width, pad_w, pad_t + wall)
    s = ring + pad - Rot(0, 90, 0) * Cylinder(ID / 2, 3 * width)
    top = Ro + pad_t - wall / 2
    for (x, y) in bolt_xy:
        s = s - Pos(x, y, top - pad_t / 2) * Cylinder(bolt_d / 2, pad_t * 3)
    return s, top


def P2_boom_clamp(L, g):
    mt = mat("al6061_t6_extr")
    upd = json.loads((HERE / "results" / "sizing_update.json").read_text())
    seg = upd["booms"][0]["segments"][1]["section"]
    ID = (0.1016 + 2 * sum(l["t"] for l in seg["layers"])) * 1000
    wall, width, pad_w, pad_t = 12.0, 110.0, 150.0, 16.0
    bxy = [(x, y) for x in (-38, 38) for y in (-58, 58)]
    solid, top = saddle(ID, wall, width, pad_w, pad_t, 9.5, bxy)
    rF, rM = L["boom_clamp"]
    F = np.array(rF["F"]) * FF
    M = np.array(rF["M"]) * FF * 1000.0                                                # N mm
    Fsum, Msum = F, M

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, y, top]), (0, 0, 1), 9.5 / 2) for x, y in bxy])

    def ld(m, faces):
        bore = select_cyl(m, faces, np.zeros(3), (1, 0, 0), ID / 2)
        tr = bearing_traction(m, bore, np.zeros(3), (1, 0, 0), Fsum) + couple_traction(m, bore, np.zeros(3), (1, 0, 0), Msum)
        return ccx.face_loads(m, bore, tr), nodes_of(bore)
    ex = lambda: dict(load_case=rF["case"], design_F_N=F.tolist(), design_M_Nmm=M.tolist(), boom_od_mm=ID,
                      bolts=bolt_check(np.linalg.norm(F) + np.linalg.norm(M[[1, 2]]) / 76.0, 4, 3 / 8 * 25.4, pad_t, mt),
                      boom_bearing_MPa=float(np.linalg.norm(F[1:]) / (ID * width) + 6 * np.linalg.norm(M[1:]) / (ID * width**2)),
                      dims=dict(wall=wall, width=width, pad=f"{pad_w} x {pad_t}", bolts="4 x AN6 per saddle"))
    return run_part("P2_boom_wing_clamp", solid, mt, 8.0, 2.0, None, bc, ld, "P2 boom-wing saddle clamp, 6061-T6", ex)


def P3_motor_plate(L):
    """Pocketed motor plate (iteration 3: -50 % mass): ring r 75-120 mm, 10 mm, motor bolts 8 x M8 on PCD 180, carried by six
    elastomeric isolators on PCD 210 (stud holes fixed: stiff-isolator bound)."""
    from build123d import Cylinder, Pos
    mt = mat("al6061_t6_extr")
    Ro, Ri, t, rb, nb, db, ri_, ni, di_ = 120.0, 75.0, 10.0, 90.0, 8, 8.0, 105.0, 6, 10.0
    s = Cylinder(Ro, t) - Cylinder(Ri, 3 * t)
    holes = [(rb * math.cos(2 * math.pi * k / nb), rb * math.sin(2 * math.pi * k / nb)) for k in range(nb)]
    isos = [(ri_ * math.cos(2 * math.pi * (k + 0.5) / ni), ri_ * math.sin(2 * math.pi * (k + 0.5) / ni)) for k in range(ni)]
    for x, y in holes:
        s = s - Pos(x, y, 0) * Cylinder(db / 2, 3 * t)
    for x, y in isos:
        s = s - Pos(x, y, 0) * Cylinder(di_ / 2, 3 * t)
    mo = L["motor"]
    k = 1.5 * FF
    T, Q, Mg, H = mo["T_limit"] * k, mo["Q_limit"] * k * 1000, mo["gyro_limit"] * k * 1000, mo["H_limit"] * k

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, y, 0]), (0, 0, 1), di_ / 2) for x, y in isos])

    def ld(m, faces):
        loads, ln = {}, []
        for (x, y) in holes:
            hf = select_cyl(m, faces, np.array([x, y, 0]), (0, 0, 1), db / 2)
            ang = math.atan2(y, x)
            ft = Q / (nb * rb) * np.array([-math.sin(ang), math.cos(ang), 0])         # torque reaction
            fz = T / nb + Mg * math.cos(ang) / (nb * rb / 2)                          # thrust + gyroscopic couple about y
            fl = np.array([H / nb, 0, 0]) + ft + np.array([0, 0, fz])
            tr = bearing_traction(m, hf, np.array([x, y, 0]), (0, 0, 1), fl)
            for n, v in ccx.face_loads(m, hf, tr).items():
                loads[n] = loads.get(n, 0) + v
            ln.append(nodes_of(hf))
        return loads, np.concatenate(ln)
    ex = lambda: dict(design=dict(thrust_N=T, torque_Nmm=Q, gyro_Nmm=Mg, inplane_N=H), pocketing="ring 75-120 mm = -54 % of the R140 disc",
                      motor_bolts=bolt_check(T / nb * 3 + Q / rb / nb, 1, db, t, mt),
                      isolator_studs=bolt_check(T / ni * 2 + Q / ri_ / ni + Mg / (ni * ri_ / 2), 1, di_, t, mt))
    return run_part("P3_motor_plate", s, mt, 6.0, 2.0, None, bc, ld, "P3 pocketed motor plate on 6 isolators, 6061-T6, 10 mm", ex, view=(35, -50))


def P7_pylon_saddle(L, g):
    """PY-C: boom saddle with the pylon socket (iteration 3: pocketed -30 %, modelled as a 30 % thinner wall)."""
    from build123d import Cylinder, Pos, Rot
    mt = mat("al6061_t6_extr")
    upd = json.loads((HERE / "results" / "sizing_update.json").read_text())
    seg = upd["booms"][0]["segments"][1]["section"]
    ID = (0.1016 + 2 * sum(l["t"] for l in seg["layers"])) * 1000
    wall, width = 12.0, 110.0                                                         # no pocketing (the -30 % gives MS < 0)
    Ro = ID / 2 + wall
    rp, hs = 50.0, 40.0
    from build123d import Cone
    body = (Rot(0, 90, 0) * Cylinder(Ro, width) + Pos(0, 0, Ro + hs / 2 - wall) * Cylinder(rp + 10, hs + wall)
            + Pos(0, 0, Ro - wall / 2 + 6) * Cone(rp + 22, rp + 10, 12))                      # 45 deg collar at the socket root
    body = body - Rot(0, 90, 0) * Cylinder(ID / 2, 3 * width) - Pos(0, 0, Ro + hs / 2 - wall + 6) * Cylinder(rp, hs + wall)
    top = Ro + hs - wall
    rF, rM = L["pylon"]
    F = np.array(rM["F"]) * FF
    M = np.array(rM["M"]) * FF * 1000.0
    c_s = np.array([0, 0, top - hs / 2])

    def bc(m, faces):
        return select_cyl(m, faces, np.zeros(3), (1, 0, 0), ID / 2)                    # bonded to the boom over the bore

    def ld(m, faces):
        sock = select_cyl(m, faces, c_s, (0, 0, 1), rp, tol=0.3)
        tr = bearing_traction(m, sock, c_s, (0, 0, 1), F) + couple_traction(m, sock, c_s, (0, 0, 1), M)
        return ccx.face_loads(m, sock, tr), nodes_of(sock)
    ex = lambda: dict(load_case=rM["case"], design_F_N=F.tolist(), design_M_Nmm=M.tolist(), pocketing="none: wall 12 mm (-30 % and -15 % give MS < 0 with the mesh factor)",
                      socket_bond_MPa=float(np.linalg.norm(M[:2]) / (math.pi * rp**2 * hs / 2 * 2) + abs(F[2]) / (2 * math.pi * rp * hs)))
    return run_part("P7_pylon_saddle", body, mt, 6.0, 2.0, None, bc, ld, "P7 pylon saddle + socket (PY-C), 6061-T6", ex)


def P4_gear_saddle(L, g):
    mt = mat("al6061_t6_extr")
    upd = json.loads((HERE / "results" / "sizing_update.json").read_text())
    ID = upd["landing_gear_oml"]["cross_tube"]["od"] * 1000
    wall, width, pad_w, pad_t = 18.0 * 0.8, 150.0, 160.0, 20.0 * 0.8              # iteration 3: 20 % thinner (damper load)
    bxy = [(x, y) for x in (-55, 0, 55) for y in (-62, 62)]
    solid, top = saddle(ID, wall, width, pad_w, pad_t, 9.5, bxy)
    rF, rM = L["gear"]
    Fg, Mg = np.array(rF["F"]) * FF, np.array(rF["M"]) * FF * 1000
    # cross tube runs along global y: part x = global y, part y = -global x
    F = np.array([Fg[1], -Fg[0], Fg[2]])
    M = np.array([Mg[1], -Mg[0], Mg[2]])

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, y, top]), (0, 0, 1), 9.5 / 2) for x, y in bxy])

    def ld(m, faces):
        bore = select_cyl(m, faces, np.zeros(3), (1, 0, 0), ID / 2)
        tr = bearing_traction(m, bore, np.zeros(3), (1, 0, 0), F) + couple_traction(m, bore, np.zeros(3), (1, 0, 0), M)
        return ccx.face_loads(m, bore, tr), nodes_of(bore)
    ex = lambda: dict(load_case=rF["case"], design_F_N=F.tolist(), design_M_Nmm=M.tolist(),
                      bolts=bolt_check(np.linalg.norm(F) + np.linalg.norm(M[[1, 2]]) / 110.0, 6, 3 / 8 * 25.4, pad_t, mt),
                      dims=dict(wall=wall, width=width, pad=f"{pad_w} x {pad_t}", bolts="6 x AN6"))
    return run_part("P4_gear_saddle", solid, mt, 7.0, 2.0, None, bc, ld, "P4 gear cross-tube saddle, 6061-T6", ex)


def P5_chute_hardpoint(L):
    from build123d import Box, Cylinder, Pos, Rot
    mt = mat("steel_4130_n")
    t, W, D, zc = 12.0, 64.0, 16.0, 75.0
    s = Box(120, t, 70) + Pos(0, 0, 45) * Box(W, t, 50) + Pos(0, 0, zc) * Rot(90, 0, 0) * Cylinder(W / 2, t)
    s = s - Pos(0, 0, zc) * Rot(90, 0, 0) * Cylinder(D / 2, 3 * t)
    bolts = [(x, z) for x in (-45, -15, 15, 45) for z in (-18, 18)]
    for x, z in bolts:
        s = s - Pos(x, 0, z) * Rot(90, 0, 0) * Cylinder(4.0, 3 * t)
    P = L["chute"]["F_limit"] * 1.5 * FF
    ang = math.radians(45)
    F = np.array([P * math.sin(ang), 0.1 * P, P * math.cos(ang)])                      # 45 deg in plane + 10 % out of plane

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, 0, z]), (0, 1, 0), 4.0) for x, z in bolts])

    def ld(m, faces):
        hf = select_cyl(m, faces, np.array([0, 0, zc]), (0, 1, 0), D / 2)
        tr = bearing_traction(m, hf, np.array([0, 0, zc]), (0, 1, 0), F)
        return ccx.face_loads(m, hf, tr), nodes_of(hf)
    ex = lambda: dict(design_load_N=F.tolist(), lug=lug_check(P, W, D, t, W / 2, mt), bolts=bolt_check(P, 8, 5 / 16 * 25.4, t, mt),
                      note="one riser leg at 50 % of the 47.4 kN opening load (GRS 6/1050 kg), x 1.5 x 1.15")
    return run_part("P5_parachute_hardpoint", s, mt, 5.0, 2.0, [(0, 0, zc, 25, 2.0)], bc, ld, "P5 parachute riser hard point, 4130 N, 12 mm", ex)


def P6_seat_fitting(L):
    from build123d import Box, Cylinder, Pos, Rot
    mt = mat("al7075_t6_sheet")
    t, D = 14.0, 9.5
    s = Box(90, 50, 10) + Pos(0, 0, 5 + 20) * Box(40, t, 40) + Pos(0, 0, 45) * Rot(90, 0, 0) * Cylinder(20, t)
    s = s - Pos(0, 0, 44) * Rot(90, 0, 0) * Cylinder(D / 2, 3 * t)
    bolts = [(-32, 0), (32, 0)]
    for x, y in bolts:
        s = s - Pos(x, y, 0) * Cylinder(4.0, 30)
    se = L["seat"]
    mass, h = se["m"], se["h_cg"]
    legs_dx = 450.0
    Fs = max(9.0 * 1.33, 26.0) * mass * 9.80665                                          # static x 1.33 vs 26 g dynamic peak
    Tleg = Fs * h * 1000 / legs_dx / 2                                                    # rear-leg tension from overturning
    Vleg = Fs / 4
    F = np.array([Vleg, 0, Tleg])

    def bc(m, faces):
        return np.concatenate([select_cyl(m, faces, np.array([x, y, 0]), (0, 0, 1), 4.0) for x, y in bolts])

    def ld(m, faces):
        hf = select_cyl(m, faces, np.array([0, 0, 45]), (0, 1, 0), D / 2)
        tr = bearing_traction(m, hf, np.array([0, 0, 44]), (0, 1, 0), F)
        return ccx.face_loads(m, hf, tr), nodes_of(hf)
    ex = lambda: dict(design_leg_N=F.tolist(), seat_forward_N=Fs, basis="max(9 g x 1.33 static, 26 g AC 23.562 test 2 peak) on occupant + seat",
                      bolts=bolt_check(np.linalg.norm(F), 2, 5 / 16 * 25.4, 8.0, mt), lug=lug_check(np.linalg.norm(F), 40, D, t, 20, mt))
    return run_part("P6_seat_fitting", s, mt, 4.0, 1.5, [(0, 0, 45, 18, 1.5)], bc, ld, "P6 seat-leg fitting, 7075-T6", ex)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    sel = sys.argv[1:] or ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    L, g = global_loads()
    fn = dict(P1=lambda: P1_wing_root(L), P2=lambda: P2_boom_clamp(L, g), P3=lambda: P3_motor_plate(L), P4=lambda: P4_gear_saddle(L, g),
              P5=lambda: P5_chute_hardpoint(L), P6=lambda: P6_seat_fitting(L), P7=lambda: P7_pylon_saddle(L, g))
    path = HERE / "results" / "parts.json"
    allr = json.loads(path.read_text()) if path.exists() else {}
    for k in sel:
        allr[k] = fn[k]()
    path.write_text(json.dumps(allr, indent=1, default=float))


if __name__ == "__main__":
    main()
