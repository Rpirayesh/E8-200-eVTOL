"""Verification of the CalculiX pipeline (fea/ccx.py) against standard benchmarks and closed-form solutions.

    ~/tools/cadenv/bin/python validation/fea/verify_ccx.py [case ...]      (cases: C1 ... C8, default all)

C1  NAFEMS LE1 elliptic membrane (plane stress): CPS8 mapped mesh and gmsh CPS6 free mesh
C2  NAFEMS LE10 thick elliptic plate: C3D20R and C3D20 structured hexahedra
C3  NAFEMS FV52 simply supported thick square plate, free vibration: C3D20R
C4  composite laminate, S8R composite shell vs Classical Lamination Theory (ply stresses, B-coupling curvature)
C5  linear buckling, S8R: isotropic and cross-ply square plates (closed form), thin cylinder under axial load
C6  sandwich beam in 3-point bending vs sandwich beam theory: CPS8 layered and S8R composite shell
C7  thin-walled box beam torsion, S8R vs Bredt-Batho (cross-check of the frame torsion constant)
C8  gmsh C3D10 solid cantilever vs Timoshenko (the part-analysis pipeline used for fittings)

Units: N, mm, MPa, t/mm^3 except C3D (FV52: N, m, Pa, kg/m^3).  Scratch: fea/.cache/verify/.
Results -> validation/fea/results/ccx_<case>.json, plots validation/fea/img/.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fea import ccx, clt  # noqa: E402

WORK = ROOT / "fea" / ".cache" / "verify"
OUT = Path(__file__).resolve().parent / "results"
IMG = Path(__file__).resolve().parent / "img"


def pct(a, b):
    return 100.0 * (a - b) / b


def ellipse_map(u, v):
    th = v * np.pi / 2
    return ((1 - u) * 2000 * np.cos(th) + u * 3250 * np.cos(th), (1 - u) * 1000 * np.sin(th) + u * 2750 * np.sin(th))


# ============================================================================= C1 LE1
def c1():
    ref = 92.7
    rows = []
    for nx, ny in ((2, 3), (4, 6), (8, 12), (16, 24), (32, 48)):
        m = ccx.quad8_block(lambda u, v: (*ellipse_map(u, v), 0.0), nx, ny, "CPS8")
        loads = {}
        for e in range(ny):
            ids = [m.nid(2 * nx, 2 * e + k) for k in range(3)]
            F = ccx.edge_load_quadratic(np.array([m.xyz(n) for n in ids]), lambda x, n: 10.0 * 100 * n)
            for n, fv in zip(ids, F):
                loads[n] = loads.get(n, 0) + fv
        deck = (ccx.deck_mesh([(m, "E")]) + ccx.nset("XF", [m.nid(k, 2 * ny) for k in range(2 * nx + 1)]) +
                ccx.nset("YF", [m.nid(k, 0) for k in range(2 * nx + 1)]) + ccx.iso_material("M", 210000, 0.3) +
                "*SOLID SECTION, ELSET=E, MATERIAL=M\n100.\n*STEP\n*STATIC\n*BOUNDARY\nXF,1\nYF,2\n" + ccx.cload(loads) +
                "*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n")
        p = ccx.run(deck, WORK / "C1", f"le1_{nx}x{ny}")
        S = ccx.frd_field(ccx.read_frd(p.with_suffix(".frd")), "STRESS")
        s = S[m.nid(0, 0)][1]
        rows.append(dict(mesh=f"CPS8 {nx}x{ny}", elems=nx * ny, h_mm=1250 / nx, syy_D=s, err_pct=pct(s, ref)))
        print("C1", rows[-1])
    # gmsh free mesh, second-order triangles (CPS6)
    rows_g = []
    for h in (250.0, 125.0, 62.5, 31.25):
        geo = f"""SetFactory("OpenCASCADE");
Ellipse(1) = {{0,0,0, 3250,2750, 0, Pi/2}};
Ellipse(2) = {{0,0,0, 2000,1000, 0, Pi/2}};
Line(3) = {{2,4}};
Line(4) = {{3,1}};
Curve Loop(1) = {{4, 1, 3, -2}};
Plane Surface(1) = {{1}};
Physical Surface("PART") = {{1}};
Physical Curve("OUTER") = {{1}};
Mesh.CharacteristicLengthMax = {h};
Mesh.ElementOrder = 2;
Mesh.HighOrderOptimize = 1;
Mesh 2;
Save "mesh.inp";
"""
        g = ccx.gmsh_mesh(geo, WORK / "C1" / f"g{h}")
        part = ccx.mesh_from_gmsh(g, "PART")
        P = g["nodes"]
        loads = {}
        for typ, conn in g["groups"]["OUTER"]:
            for e in conn:
                ids = [e[0], e[1], e[2]]                       # gmsh writes T3D3 as end, mid, end (Abaqus order)
                pts = np.array([P[i - 1] for i in ids])
                F = ccx.edge_load_quadratic(pts, lambda x, n: 1000.0 * n * np.sign(np.dot(n, x)))
                for n, fv in zip(ids, F):
                    loads[n] = loads.get(n, 0) + fv
        used = np.unique(part.elems)
        xs = used[np.abs(P[used - 1, 0]) < 1e-6]
        ys = used[np.abs(P[used - 1, 1]) < 1e-6]
        deck = (ccx.deck_mesh([(ccx.Mesh(P, part.elems, "CPS6"), "E")]) + ccx.nset("XF", xs) + ccx.nset("YF", ys) +
                ccx.iso_material("M", 210000, 0.3) + "*SOLID SECTION, ELSET=E, MATERIAL=M\n100.\n*STEP\n*STATIC\n*BOUNDARY\nXF,1\nYF,2\n" +
                ccx.cload(loads) + "*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n")
        p = ccx.run(deck, WORK / "C1", f"le1_gmsh_{int(h)}")
        S = ccx.frd_field(ccx.read_frd(p.with_suffix(".frd")), "STRESS")
        D = int(np.argmin(np.linalg.norm(P - [2000, 0, 0], axis=1))) + 1
        s = S[D][1]
        rows_g.append(dict(mesh=f"gmsh CPS6 h={h}", elems=len(part.elems), h_mm=h, syy_D=s, err_pct=pct(s, ref)))
        print("C1", rows_g[-1])
    return dict(case="NAFEMS LE1 elliptic membrane, plane stress, t=0.1 m, E=210 GPa, nu=0.3, p=10 MPa outward",
                quantity="sigma_yy at D (2.0, 0) [MPa]", reference=ref, source="NAFEMS, The Standard NAFEMS Benchmarks, TNSB Rev. 3 (1990), LE1",
                mesh=rows, mesh_gmsh=rows_g)


# ============================================================================= C2 LE10
def c2():
    ref = -5.38
    rows = []
    for et in ("C3D20R", "C3D20"):
        for nx, ny, nz in ((2, 3, 2), (4, 6, 2), (8, 12, 4), (16, 24, 4), (32, 48, 8)):
            m = ccx.hex20_block(lambda u, v, w: (*ellipse_map(u, v), -300 + 600 * w), nx, ny, nz, et)
            top = np.arange(len(m.elems) - nx * ny + 1, len(m.elems) + 1)
            L = m.lattice
            deck = (ccx.deck_mesh([(m, "E")]) + ccx.nset("XF", [n for (i, j, k), n in L.items() if j == 2 * ny]) +
                    ccx.nset("YF", [n for (i, j, k), n in L.items() if j == 0]) +
                    ccx.nset("OF", [n for (i, j, k), n in L.items() if i == 2 * nx]) +
                    ccx.nset("ZF", [n for (i, j, k), n in L.items() if i == 2 * nx and k == nz]) +
                    ccx.iso_material("M", 210000, 0.3) + "*SOLID SECTION, ELSET=E, MATERIAL=M\n*STEP\n*STATIC\n*BOUNDARY\n"
                    "XF,1\nYF,2\nOF,1,2\nZF,3\n*DLOAD\n" + "".join(f"{e},P2,1.0\n" for e in top) + "*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n")
            t0 = time.time()
            p = ccx.run(deck, WORK / "C2", f"le10_{et}_{nx}")
            S = ccx.frd_field(ccx.read_frd(p.with_suffix(".frd")), "STRESS")
            s = S[m.nid(0, 0, 2 * nz)][1]
            rows.append(dict(element=et, mesh=f"{nx}x{ny}x{nz}", elems=nx * ny * nz, nodes=len(m.nodes), syy_D=s,
                             err_pct=pct(s, ref), cpu_s=round(time.time() - t0, 1)))
            print("C2", rows[-1])
    return dict(case="NAFEMS LE10 thick elliptic plate, t=0.6 m, E=210 GPa, nu=0.3, 1 MPa on the top face",
                quantity="sigma_yy at D (2.0, 0, 0.3) [MPa]", reference=ref, source="NAFEMS TNSB Rev. 3 (1990), LE10", mesh=rows)


# ============================================================================= C3 FV52
def mindlin_ss(m, n, a=10.0, h=1.0, E=200e9, nu=0.3, rho=8000.0):
    """Lowest (flexural) Mindlin frequency of a hard simply supported plate, mode (m, n), shear factor pi^2/12."""
    G = E / (2 * (1 + nu))
    D = E * h**3 / (12 * (1 - nu**2))
    A = math.pi**2 / 12 * G * h
    k2 = (math.pi / a) ** 2 * (m * m + n * n)
    # det [[A k2 - rho h w2, A k], [A k, D k2 + A - rho h^3/12 w2]] = 0
    c2 = rho * h * rho * h**3 / 12
    c1 = -(A * k2 * rho * h**3 / 12 + rho * h * (D * k2 + A))
    c0 = A * k2 * (D * k2 + A) - A * A * k2
    w2 = (-c1 - math.sqrt(c1 * c1 - 4 * c2 * c0)) / (2 * c2)
    return math.sqrt(w2) / (2 * math.pi)


def c3():
    nafems = [45.897, 109.44, 109.44, 167.89, 193.59, 206.19, 206.19]
    flex_modes = [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1)]
    flex_ref = [45.897, 109.44, 109.44, 167.89, 206.19, 206.19]
    mind = [mindlin_ss(*mn) for mn in flex_modes]
    rows = []
    for bc in ("hard SS faces", "uz=0 bottom-face edges", "uz=0 mid-plane edges"):
        for n, nz in ((4, 2), (8, 2), (16, 4), (24, 4)):
            m = ccx.hex20_block(lambda u, v, w: (10 * u, 10 * v, -0.5 + w), n, n, nz, "C3D20R")
            L = m.lattice
            if bc == "hard SS faces":
                bnd = (ccx.nset("XF", [nd for (i, j, k), nd in L.items() if i in (0, 2 * n)]) +
                       ccx.nset("YF", [nd for (i, j, k), nd in L.items() if j in (0, 2 * n)]))
                bcl = "XF,2,3\nYF,1\nYF,3\n"
            else:
                kk = 0 if bc.startswith("uz=0 bottom") else nz
                bnd = ccx.nset("SS", [nd for (i, j, k), nd in L.items() if k == kk and (i in (0, 2 * n) or j in (0, 2 * n))])
                bcl = "SS,3\n"
            deck = (ccx.deck_mesh([(m, "E")]) + bnd + ccx.iso_material("M", 200e9, 0.3, 8000.0) +
                    "*SOLID SECTION, ELSET=E, MATERIAL=M\n*STEP\n*FREQUENCY\n14\n*BOUNDARY\n" + bcl + "*END STEP\n")
            p = ccx.run(deck, WORK / "C3", f"fv52_{bc.split()[0].replace('=', '')}{bc.split()[1][:3]}_{n}")
            f = np.array([x for x in ccx.read_eigen(p.with_suffix(".dat")) if x > 1.0])
            row = dict(bc=bc, mesh=f"{n}x{n}x{nz}", elems=n * n * nz, f_hz=f[:8].round(3).tolist())
            if bc == "hard SS faces":
                # match each flexural reference mode to the nearest computed frequency
                used, fm = set(), []
                for r in flex_ref:
                    k = min((k for k in range(len(f)) if k not in used), key=lambda k: abs(f[k] - r))
                    used.add(k)
                    fm.append(float(f[k]))
                row.update(f_flex=fm, err_vs_nafems_pct=[pct(x, r) for x, r in zip(fm, flex_ref)],
                           err_vs_mindlin_pct=[pct(x, r) for x, r in zip(fm, mind)])
            else:
                row.update(err_vs_nafems_pct=[pct(x, r) for x, r in zip(f[:7], nafems)])
            rows.append(row)
            print("C3", bc, row["mesh"], np.round(row["err_vs_nafems_pct"], 2))
    return dict(case="NAFEMS FV52 simply supported thick square plate 10 x 10 x 1 m, E 200 GPa, nu 0.3, rho 8000 kg/m^3",
                reference_hz=nafems, flexural_modes=flex_modes, flexural_reference_hz=flex_ref, mindlin_hz=mind,
                source="NAFEMS R0015 (1987) FV52; values as tabulated in the Altair OptiStruct verification manual (test 0455); "
                       "Mindlin closed form computed here",
                note="The reference flexural frequencies are reproduced by 'hard' simple supports (uz and tangential displacement zero "
                     "over the edge faces, the condition of the 3-D exact and Mindlin solutions). Supporting only a line of nodes "
                     "(bottom or mid-plane edges, as the benchmark text is variously quoted) is a softer support and gives 2-7 % lower "
                     "values that keep falling with refinement; those runs are kept to document the sensitivity.",
                mesh=rows)


# ============================================================================= C4 laminate vs CLT
PLY = dict(E1=120000., E2=8000., nu12=0.30, G12=4000., E3=8000., nu13=0.30, nu23=0.40, G13=4000., G23=3000.)


def _laminate_run(angles, t_ply, nx, ny, Lx, Ly, name, free_bending):
    m = ccx.quad8_block(lambda u, v: (Lx * (u - 0.5), Ly * (v - 0.5), 0.0), nx, ny, "S8R")
    deck = ccx.deck_mesh([(m, "E")]) + ccx.ortho_material("PLY", *(PLY[k] for k in ("E1", "E2", "E3", "nu12", "nu13", "nu23", "G12", "G13", "G23")))
    for a in sorted(set(angles)):
        deck += ccx.orientation(f"OR{a + 90}", a)
    deck += "*SHELL SECTION, ELSET=E, COMPOSITE\n" + "".join(f"{t_ply},,PLY,OR{a + 90}\n" for a in angles)
    Nx = 100.0                                               # N/mm
    loads = {}
    for side, sg in ((2 * nx, 1.0), (0, -1.0)):
        for e in range(ny):
            ids = [m.nid(side, 2 * e + k) for k in range(3)]
            for nd, w in zip(ids, (1 / 6, 4 / 6, 1 / 6)):
                loads[nd] = loads.get(nd, 0) + np.array([sg * Nx * Ly / ny * w, 0, 0])
    c = m.nid(nx, ny)
    ex = m.nid(2 * nx, ny)
    ey = m.nid(nx, 2 * ny)
    bnd = f"{c},1,3\n{ex},2,3\n{ey},3\n"
    if not free_bending:
        deck += ccx.nset("ALL", m.ids)
        bnd = f"{c},1,2\n{ex},2\nALL,3\n"
    mid_el = (ny // 2) * nx + nx // 2 + 1                     # an element next to the plate centre
    deck += ("*STEP\n*STATIC\n*BOUNDARY\n" + bnd + ccx.cload(loads) +
             f"*NODE PRINT, NSET=NALL\nU\n*ELSET, ELSET=EMID\n{mid_el}\n*EL PRINT, ELSET=EMID\nS\n*END STEP\n")
    p = ccx.run(deck, WORK / "C4", name)
    txt = p.with_suffix(".dat").read_text()
    blk = txt.split("displacements (vx,vy,vz)")[1].split("stresses")[0]
    U = {}
    for line in blk.splitlines()[1:]:
        q = line.split()
        if len(q) == 4:
            U[int(q[0])] = np.array([float(v) for v in q[1:]])
    S = ccx.read_el_print(p.with_suffix(".dat"))[0]
    return m, U, S, Nx


def c4():
    out = {}
    # (a) symmetric quasi-isotropic laminate in tension: ply stresses in material axes
    angles, tp = [0, 45, -45, 90, 90, -45, 45, 0], 0.25
    ply = dict(E1=PLY["E1"], E2=PLY["E2"], nu12=PLY["nu12"], G12=PLY["G12"])
    layup = [(ply, a, tp) for a in angles]
    e0, kap, plies = clt.response(layup, N=(100.0, 0, 0))
    rows = []
    for nx in (2, 4, 8, 16):
        m, U, S, Nx = _laminate_run(angles, tp, nx, nx, 100.0, 100.0, f"qi_{nx}", free_bending=False)
        # strain gauges over the central half of the plate (away from loaded and free edges)
        exx = (U[m.nid(3 * nx // 2, nx)][0] - U[m.nid(nx // 2, nx)][0]) / 50.0
        eyy = (U[m.nid(nx, 3 * nx // 2)][1] - U[m.nid(nx, nx // 2)][1]) / 50.0
        errs, table = [], []
        for k, a in enumerate(angles):
            sg = S[8 * k:8 * k + 8, 2:8].mean(axis=0)                 # sxx syy szz sxy sxz syz
            s12 = np.array([sg[0], sg[1], sg[3]])          # CalculiX prints stresses in the ply (orientation) axes
            r12 = plies[k]["mid"]["sig12"]
            table.append(dict(ply=k + 1, angle=a, fe=s12.round(3).tolist(), clt=r12.round(3).tolist()))
            errs.append(np.max(np.abs(s12 - r12)) / np.max(np.abs(r12)) * 100)
        rows.append(dict(mesh=f"{nx}x{nx}", eps_x=exx, eps_x_clt=e0[0], err_eps_x_pct=pct(exx, e0[0]),
                         eps_y=eyy, eps_y_clt=e0[1], err_eps_y_pct=pct(eyy, e0[1]), max_ply_stress_err_pct=float(max(errs)), plies=table))
        print("C4a", nx, rows[-1]["err_eps_x_pct"], rows[-1]["err_eps_y_pct"], rows[-1]["max_ply_stress_err_pct"])
    out["C4a quasi-isotropic [0/45/-45/90]s, Nx = 100 N/mm"] = dict(
        ply="E1 120, E2 8, G12 4 GPa, nu12 0.3, t 0.25 mm", mesh=rows,
        note="ply stresses = mean of the 8 integration points of each layer of an element at the plate centre; CalculiX *EL PRINT gives them already in the ply (orientation) axes")
    # (b) unsymmetric cross-ply [0/90]: extension-bending coupling
    angles = [0, 90]
    tp = 0.5
    layup = [(ply, a, tp) for a in angles]
    e0, kap, _ = clt.response(layup, N=(100.0, 0, 0))
    rows = []
    for nx in (4, 8, 16):
        m, U, S, Nx = _laminate_run(angles, tp, nx, nx, 100.0, 100.0, f"cp_{nx}", free_bending=True)
        P = np.array([m.xyz(n) for n in U])
        W = np.array([U[n][2] for n in U])
        sel = (np.abs(P[:, 0]) < 25.01) & (np.abs(P[:, 1]) < 25.01)          # central region, away from free edges
        x, y = P[sel, 0], P[sel, 1]
        Amat = np.c_[np.ones_like(x), x, y, x * x / 2, y * y / 2, x * y]
        coef = np.linalg.lstsq(Amat, W[sel], rcond=None)[0]
        kx, ky = -coef[3], -coef[4]                                        # kappa = -d2w/dx2
        exx = (U[m.nid(3 * nx // 2, nx)][0] - U[m.nid(nx // 2, nx)][0]) / 50.0
        rows.append(dict(mesh=f"{nx}x{nx}", kappa_x=kx, kappa_x_clt=kap[0], err_kx_pct=pct(kx, kap[0]),
                         kappa_y=ky, kappa_y_clt=kap[1], eps_x_mid=exx, eps_x_clt=e0[0], err_eps_x_pct=pct(exx, e0[0])))
        print("C4b", rows[-1])
    out["C4b unsymmetric [0/90]T, Nx = 100 N/mm (B-matrix coupling)"] = dict(
        mesh=rows, note="curvatures from a quadratic fit of w over the central 50 x 50 mm of a free 100 x 100 mm plate; "
                        "first layer = bottom (CalculiX and CLT use the same convention)")
    return out


# ============================================================================= C5 buckling
def _plate_buckle(n, a, b, section, name, nmodes=3):
    m = ccx.quad8_block(lambda u, v: (a * u, b * v, 0.0), n, max(1, round(n * b / a)), "S8R")
    nx, ny = m.shape
    L = m.lattice
    edges = [nd for (i, j), nd in L.items() if i in (0, 2 * nx) or j in (0, 2 * ny)]
    x0 = [nd for (i, j), nd in L.items() if i == 0]
    loads = {}
    for e in range(ny):
        ids = [m.nid(2 * nx, 2 * e + k) for k in range(3)]
        for nd, w in zip(ids, (1 / 6, 4 / 6, 1 / 6)):
            loads[nd] = loads.get(nd, 0) + np.array([-1.0 * b / ny * w, 0, 0])      # Nx = -1 N/mm
    deck = (ccx.deck_mesh([(m, "E")]) + ccx.nset("SS", edges) + ccx.nset("X0", x0) + section +
            f"*STEP\n*BUCKLE\n{nmodes}\n*BOUNDARY\nSS,3\nX0,1\n{m.nid(0, 0)},2\n" + ccx.cload(loads) + "*END STEP\n")
    p = ccx.run(deck, WORK / "C5", name)
    return ccx.read_eigen(p.with_suffix(".dat"))


def c5():
    out = {}
    a = b = 500.0
    t, E, nu = 2.0, 70000.0, 0.3
    D = E * t**3 / (12 * (1 - nu**2))
    ref = 4 * math.pi**2 * D / b**2
    sec = ccx.iso_material("AL", E, nu) + f"*SHELL SECTION, ELSET=E, MATERIAL=AL\n{t}\n"
    rows = []
    for n in (2, 4, 8, 16):
        lam = _plate_buckle(n, a, b, sec, f"iso_{n}")
        rows.append(dict(mesh=f"{n}x{n}", Ncr=float(lam[0]), err_pct=pct(lam[0], ref)))
        print("C5a", rows[-1])
    out["C5a SS square plate, uniaxial compression"] = dict(case="aluminium 500x500x2 mm, all edges w=0, unloaded edges free in-plane",
                                                           Ncr_ref_N_per_mm=ref, formula="Ncr = 4 pi^2 D / b^2", mesh=rows)
    # specially orthotropic cross-ply [0/90]s
    ply = dict(E1=PLY["E1"], E2=PLY["E2"], nu12=PLY["nu12"], G12=PLY["G12"])
    angles, tp = [0, 90, 90, 0], 0.5
    _, _, Dm = clt.ABD([(ply, ang, tp) for ang in angles])
    refs = []
    for mm in range(1, 5):
        refs.append(math.pi**2 / b**2 * (Dm[0, 0] * (mm * b / a) ** 2 + 2 * (Dm[0, 1] + 2 * Dm[2, 2]) + Dm[1, 1] * (a / (mm * b)) ** 2))
    ref2 = min(refs)
    sec = (ccx.ortho_material("PLY", *(PLY[k] for k in ("E1", "E2", "E3", "nu12", "nu13", "nu23", "G12", "G13", "G23"))) +
           ccx.orientation("OR90", 0) + ccx.orientation("OR180", 90) +
           "*SHELL SECTION, ELSET=E, COMPOSITE\n" + "".join(f"{tp},,PLY,OR{ang + 90}\n" for ang in angles))
    rows = []
    for n in (4, 8, 16):
        lam = _plate_buckle(n, a, b, sec, f"cp_{n}")
        rows.append(dict(mesh=f"{n}x{n}", Ncr=float(lam[0]), err_pct=pct(lam[0], ref2)))
        print("C5b", rows[-1])
    out["C5b SS cross-ply [0/90]s plate"] = dict(case="500x500 mm, 4 x 0.5 mm plies (E1 120, E2 8, G12 4 GPa)", Ncr_ref_N_per_mm=ref2,
                                                formula="Ncr = pi^2/b^2 [D11 (mb/a)^2 + 2(D12+2D66) + D22 (a/mb)^2], min over m", mesh=rows)
    # thin cylinder under axial compression
    R, tc, Lc = 100.0, 1.0, 200.0
    ref3 = E * tc**2 / (R * math.sqrt(3 * (1 - nu**2)))          # N/mm
    rows = []
    for nc, nl in ((64, 20), (128, 40), (192, 60)):
        m = ccx.quad8_block(lambda u, v: (R * math.cos(2 * math.pi * u), R * math.sin(2 * math.pi * u), Lc * v), nc, nl, "S8R")
        m, _ = ccx.merge([m], tol=1e-5)
        z = m.nodes[:, 2]
        bot, top = m.ids[np.abs(z) < 1e-6], m.ids[np.abs(z - Lc) < 1e-6]
        # axial edge load: consistent loads on the top circle (equal arc elements)
        loads = {}
        arc = 2 * math.pi * R / nc
        for nd in top:
            loads[int(nd)] = np.zeros(3)
        Ptop = m.nodes[top - 1]
        ang = np.mod(np.arctan2(Ptop[:, 1], Ptop[:, 0]), 2 * math.pi)
        corner = np.isclose(np.mod(ang / (2 * math.pi / nc), 1.0), 0, atol=1e-6) | np.isclose(np.mod(ang / (2 * math.pi / nc), 1.0), 1, atol=1e-6)
        for nd, cn in zip(top, corner):
            loads[int(nd)] = np.array([0, 0, -arc * (2 / 6 if cn else 4 / 6)])
        deck = (ccx.deck_mesh([(m, "E")]) + ccx.nset("BOT", bot) + ccx.nset("TOP", top) + ccx.iso_material("AL", E, nu) +
                f"*SHELL SECTION, ELSET=E, MATERIAL=AL\n{tc}\n*STEP\n*BUCKLE\n4\n*BOUNDARY\nBOT,1,3\nTOP,1,2\n" + ccx.cload(loads) + "*END STEP\n")
        t0 = time.time()
        p = ccx.run(deck, WORK / "C5", f"cyl_{nc}")
        lam = ccx.read_eigen(p.with_suffix(".dat"))
        rows.append(dict(mesh=f"{nc}x{nl}", elem_mm=round(arc, 2), Ncr=float(lam[0]), err_pct=pct(lam[0], ref3), cpu_s=round(time.time() - t0, 1)))
        print("C5c", rows[-1])
    out["C5c thin cylinder, axial compression"] = dict(
        case="aluminium R=100, t=1, L=200 mm; ends: w=v=0 (radial and circumferential), bottom also axially fixed",
        Ncr_ref_N_per_mm=ref3, formula="classical Ncr = E t^2 / (R sqrt(3(1-nu^2)))",
        note="linear bifurcation of the perfect shell; design knock-down (NASA SP-8007) is applied in sizing, not here", mesh=rows)
    return out


# ============================================================================= C6 sandwich
def c6():
    Lspan, over, b = 300.0, 10.0, 50.0
    tf, tcore = 1.0, 20.0
    Ef, nuf, Ec, nuc = 50000.0, 0.10, 70.0, 0.30
    Gc = Ec / (2 * (1 + nuc))
    P, cpatch = 500.0, 20.0
    D, S = clt.sandwich_beam(Ef, tf, Ec, Gc, tcore, b)
    d_b = P / (384 * D) * (8 * Lspan**3 - 4 * Lspan * cpatch**2 + cpatch**3)
    d_s = P / (4 * S) * (Lspan - cpatch / 2)
    ref = d_b + d_s
    ref_line = P * Lspan**3 / (48 * D) + P * Lspan / (4 * S)          # same beam, line load (shell model)
    Ltot = Lspan + 2 * over
    h = 2 * tf + tcore
    rows = []
    for nxe, nfe, nce in ((32, 1, 4), (64, 1, 8), (128, 2, 12), (256, 2, 16)):
        nyt = 2 * nfe + nce
        br = np.array([0, nfe, nfe + nce, nyt]) / nyt
        yb = np.array([0, tf, tf + tcore, h])
        m = ccx.quad8_block(lambda u, v: (Ltot * u, float(np.interp(v, br, yb)), 0.0), nxe, nyt, "CPS8")
        cent = m.nodes[m.elems[:, :4] - 1].mean(axis=1)
        core = np.where((cent[:, 1] > tf) & (cent[:, 1] < tf + tcore))[0] + 1
        face = np.setdiff1d(np.arange(1, len(m.elems) + 1), core)
        x = m.nodes[:, 0]
        bottom = [nd for (i, j), nd in m.lattice.items() if j == 0]
        supA = [nd for nd in bottom if abs(x[nd - 1] - over) < 1e-6]
        supB = [nd for nd in bottom if abs(x[nd - 1] - (over + Lspan)) < 1e-6]
        if not supA or not supB:
            raise ValueError("support stations must coincide with nodes")
        # patch load on the top surface, consistent quadratic edge loads (pressure * b)
        loads = {}
        q = P / cpatch                                                         # N/mm (already integrated over b)
        for e in range(nxe):
            ids = [m.nid(2 * e + k, 2 * nyt) for k in range(3)]
            xm = x[ids[1] - 1]
            if abs(xm - Ltot / 2) < cpatch / 2:
                le = Ltot / nxe
                for nd, w in zip(ids, (1 / 6, 4 / 6, 1 / 6)):
                    loads[nd] = loads.get(nd, 0) + np.array([0, -q * le * w, 0])
        deck = (ccx.deck_mesh([(m, "E")]) + ccx.elset("FACE", face) + ccx.elset("CORE", core) +
                ccx.iso_material("F", Ef, nuf) + ccx.iso_material("C", Ec, nuc) +
                f"*SOLID SECTION, ELSET=FACE, MATERIAL=F\n{b}\n*SOLID SECTION, ELSET=CORE, MATERIAL=C\n{b}\n"
                f"*STEP\n*STATIC\n*BOUNDARY\n{supA[0]},1,2\n{supB[0]},2\n" + ccx.cload(loads) + "*NODE FILE\nU\n*END STEP\n")
        p = ccx.run(deck, WORK / "C6", f"sw2d_{nxe}")
        U = ccx.frd_field(ccx.read_frd(p.with_suffix(".frd")), "DISP")
        mid = [nd for nd in bottom if abs(x[nd - 1] - Ltot / 2) < 1e-6][0]
        d = -U[mid][1]
        rows.append(dict(model="CPS8 layered", mesh=f"{nxe} x ({nfe}+{nce}+{nfe})", deflection_mm=d, err_pct=pct(d, ref)))
        print("C6", rows[-1])
    # composite S8R shell representation (face/core/face layers)
    for nxe in (16, 32, 64):
        ny = 4
        m = ccx.quad8_block(lambda u, v: (Ltot * u, b * v, 0.0), nxe, ny, "S8R")
        x = m.nodes[:, 0]
        sec = (ccx.iso_material("F", Ef, nuf) + ccx.iso_material("C", Ec, nuc) + ccx.orientation("OR0", 0) +
               f"*SHELL SECTION, ELSET=E, COMPOSITE\n{tf},,F,OR0\n{tcore},,C,OR0\n{tf},,F,OR0\n")
        supA = [nd for (i, j), nd in m.lattice.items() if abs(x[nd - 1] - over) < 1e-6]
        supB = [nd for (i, j), nd in m.lattice.items() if abs(x[nd - 1] - (over + Lspan)) < 1e-6]
        # line load across the width at mid-span (consistent quadratic edge weights)
        loads = {}
        for jj in range(ny):
            for k, w in enumerate((1 / 6, 4 / 6, 1 / 6)):
                nd = m.nid(nxe, 2 * jj + k)
                loads[nd] = loads.get(nd, 0) + np.array([0, 0, -P / ny * w])
        deck = (ccx.deck_mesh([(m, "E")]) + sec + ccx.nset("SA", supA) + ccx.nset("SB", supB) +
                f"*STEP\n*STATIC\n*BOUNDARY\nSA,3\nSB,3\n{supA[0]},1,2\n{supB[0]},2\n" + ccx.cload(loads) + "*NODE PRINT, NSET=NALL\nU\n*END STEP\n")
        p = ccx.run(deck, WORK / "C6", f"sws_{nxe}")
        txt = p.with_suffix(".dat").read_text().split("displacements (vx,vy,vz)")[1]
        U = {int(l.split()[0]): float(l.split()[3]) for l in txt.splitlines()[1:] if len(l.split()) == 4}
        mids = [nd for nd in m.ids if abs(x[nd - 1] - Ltot / 2) < 1e-6]
        d = -np.mean([U[nd] for nd in mids])
        rows.append(dict(model="S8R composite shell (3 layers), line load", mesh=f"{nxe}x{ny}", deflection_mm=d, err_pct=pct(d, ref_line)))
        print("C6", rows[-1])
    # layered solid (C3D20R) plate strip: face / core / face element layers, patch pressure as in the 2-D model
    for nxe, nce in ((32, 2), (64, 4)):
        wz = np.r_[0, tf / h, np.linspace(tf, tf + tcore, nce + 1)[1:] / h, 1.0]
        m = ccx.hex20_block(lambda u, v, w: (Ltot * u, b * v, h * w), nxe, 2, list(wz), "C3D20R")
        nz = len(wz) - 1
        cent = m.nodes[m.elems[:, :8] - 1].mean(axis=1)
        core = np.where((cent[:, 2] > tf) & (cent[:, 2] < tf + tcore))[0] + 1
        face = np.setdiff1d(np.arange(1, len(m.elems) + 1), core)
        x, z = m.nodes[:, 0], m.nodes[:, 2]
        supA = m.ids[(np.abs(x - over) < 1e-6) & (np.abs(z) < 1e-6)]
        supB = m.ids[(np.abs(x - over - Lspan) < 1e-6) & (np.abs(z) < 1e-6)]
        topel = np.where((np.abs(cent[:, 2] - (h - tf / 2)) < 1e-6) & (np.abs(cent[:, 0] - Ltot / 2) < cpatch / 2))[0] + 1
        deck = (ccx.deck_mesh([(m, "E")]) + ccx.elset("FACE", face) + ccx.elset("CORE", core) + ccx.nset("SA", supA) + ccx.nset("SB", supB) +
                ccx.iso_material("F", Ef, nuf) + ccx.iso_material("C", Ec, nuc) +
                "*SOLID SECTION, ELSET=FACE, MATERIAL=F\n*SOLID SECTION, ELSET=CORE, MATERIAL=C\n"
                f"*STEP\n*STATIC\n*BOUNDARY\nSA,3\nSB,3\n{supA[0]},1,2\n{supB[0]},2\n*DLOAD\n" +
                "".join(f"{e},P2,{P / (cpatch * b):.8g}\n" for e in topel) + "*NODE FILE\nU\n*END STEP\n")
        p = ccx.run(deck, WORK / "C6", f"sw3d_{nxe}")
        U = ccx.frd_field(ccx.read_frd(p.with_suffix(".frd")), "DISP")
        mids = m.ids[(np.abs(x - Ltot / 2) < 1e-6) & (np.abs(z) < 1e-6)]
        d = -np.mean([U[nd][2] for nd in mids])
        rows.append(dict(model="C3D20R layered solid strip", mesh=f"{nxe}x2x(1+{nce}+1)", deflection_mm=d, err_pct=pct(d, ref)))
        print("C6", rows[-1])
    return dict(case="sandwich beam 3-point bending: span 300 mm, b 50 mm, faces 1 mm (E 50 GPa), core 20 mm (E 70, G 26.9 MPa), "
                     "P 500 N over 20 mm", reference_mm=ref, reference_line_load_mm=ref_line, bending_mm=d_b, shear_mm=d_s, shear_share_pct=100 * d_s / ref,
                formula="delta = P(8L^3-4Lc^2+c^3)/(384 D) + P(L-c/2)/(4S); D = Ef b tf^3/6 + Ef b tf d^2/2 + Ec b tc^3/12; S = Gc b d^2/tc",
                source="H.G. Allen, Analysis and Design of Structural Sandwich Panels (1969); D. Zenkert, An Introduction to Sandwich Construction (1995)",
                mesh=rows)


# ============================================================================= C7 box torsion
def c7():
    b, h, tw, tf, L = 200.0, 120.0, 2.0, 3.0, 1500.0
    E, nu = 70000.0, 0.33
    G = E / (2 * (1 + nu))
    bm, hm = b - tw, h - tf
    Am = bm * hm
    J = 4 * Am**2 / (2 * bm / tf + 2 * hm / tw)
    T = 2.0e6                                                               # N mm
    rows = []
    for nl, nwb, nwh in ((15, 2, 2), (30, 4, 3), (60, 8, 6)):
        y0, z0 = -bm / 2, -hm / 2
        walls = [((y0, z0), (y0 + bm, z0), nwb, "FL"), ((y0 + bm, z0), (y0 + bm, z0 + hm), nwh, "WEB"),
                 ((y0 + bm, z0 + hm), (y0, z0 + hm), nwb, "FL"), ((y0, z0 + hm), (y0, z0), nwh, "WEB")]
        ms = [ccx.quad8_block(lambda u, v, p0=p0, p1=p1: (L * v, p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u), nw, nl, "S8R")
              for (p0, p1, nw, _) in walls]
        m, ranges = ccx.merge(ms)
        fl = np.concatenate([ranges[0], ranges[2]])
        wb = np.concatenate([ranges[1], ranges[3]])
        x = m.nodes[:, 0]
        root = m.ids[np.abs(x) < 1e-6]
        # end torque: shear flow q = T/(2 Am) along the mid-line of the end section
        q = T / (2 * Am)
        loads = {}
        for (p0, p1, nw, _), mm in zip(walls, ms):
            p0, p1 = np.array(p0), np.array(p1)
            tvec = (p1 - p0) / np.linalg.norm(p1 - p0)
            le = np.linalg.norm(p1 - p0) / nw
            for e in range(nw):
                for k, w in enumerate((1 / 6, 4 / 6, 1 / 6)):
                    pt = np.r_[L, p0 + (p1 - p0) * (2 * e + k) / (2 * nw)]
                    nd = m.near(pt, 1e-6)
                    loads[nd] = loads.get(nd, 0) + np.r_[0, tvec] * q * le * w
        Mx = sum(np.cross(m.xyz(nd), f)[0] for nd, f in loads.items())
        el_web = int(ranges[1][(nl // 2) * nwh + nwh // 2])                 # web element near mid-length, mid-height
        el_fl = int(ranges[0][(nl // 2) * nwb + nwb // 2])
        deck = (ccx.deck_mesh([(m, "E")]) + ccx.elset("FL", fl) + ccx.elset("WEB", wb) + ccx.nset("ROOT", root) +
                ccx.iso_material("AL", E, nu) + f"*SHELL SECTION, ELSET=FL, MATERIAL=AL\n{tf}\n*SHELL SECTION, ELSET=WEB, MATERIAL=AL\n{tw}\n"
                f"*ELSET, ELSET=EW\n{el_web}\n*ELSET, ELSET=EF\n{el_fl}\n"
                "*STEP\n*STATIC\n*BOUNDARY\nROOT,1,3\n" + ccx.cload(loads) +
                "*NODE PRINT, NSET=NALL\nU\n*EL PRINT, ELSET=EW\nS\n*EL PRINT, ELSET=EF\nS\n*END STEP\n")
        p = ccx.run(deck, WORK / "C7", f"box_{nl}")
        txt = p.with_suffix(".dat").read_text().split("displacements (vx,vy,vz)")[1].split("stresses")[0]
        U = {int(l.split()[0]): np.array([float(v) for v in l.split()[1:]]) for l in txt.splitlines()[1:] if len(l.split()) == 4}

        def twist(xs):
            nds = [nd for nd in m.ids if abs(x[nd - 1] - xs) < 1e-6]
            r = np.array([m.xyz(nd)[1:] for nd in nds])
            u = np.array([U[nd][1:] for nd in nds])
            return float(np.mean((r[:, 0] * u[:, 1] - r[:, 1] * u[:, 0]) / (r[:, 0] ** 2 + r[:, 1] ** 2)))
        xa, xb = L * round(0.4 * nl) / nl, L * round(0.8 * nl) / nl
        rate = (twist(xb) - twist(xa)) / (xb - xa)
        Sw, Sf = ccx.read_el_print(p.with_suffix(".dat"))
        # shell *EL PRINT stresses are given in the element's local in-plane axes: use the shear magnitude
        tau_w = float(np.mean(np.linalg.norm(Sw[:, 5:8], axis=1)))
        tau_f = float(np.mean(np.linalg.norm(Sf[:, 5:8], axis=1)))
        rows.append(dict(mesh=f"{nl} x ({nwb},{nwh})", twist_rate=rate, err_twist_rate_pct=pct(rate, T / (G * J)),
                         tau_web=tau_w, err_tau_web_pct=pct(tau_w, q / tw), tau_flange=tau_f, err_tau_flange_pct=pct(tau_f, q / tf),
                         applied_torque_check=Mx / T))
        print("C7", rows[-1])
    return dict(case="aluminium box 200x120 mm (outer), webs 2 mm, flanges 3 mm, L 1.5 m, end torque 2 kN m, root clamped",
                twist_rate_ref=T / (G * J), J_bredt_mm4=J, tau_web_ref=q / tw, tau_flange_ref=q / tf,
                formula="Bredt-Batho: q = T/(2 Am), J = 4 Am^2 / sum(s/t); twist rate measured between 0.4 L and 0.8 L (away from root warping restraint)",
                mesh=rows)


# ============================================================================= C8 C3D10 cantilever
def c8():
    L, b, hgt, P = 200.0, 20.0, 10.0, 100.0
    E, nu = 68900.0, 0.33
    G = E / (2 * (1 + nu))
    I = b * hgt**3 / 12
    d_eb = P * L**3 / (3 * E * I)
    d_tim = d_eb + P * L / (5 / 6 * G * b * hgt)
    sig_mid = P * (L / 2) * (hgt / 2) / I
    rows = []
    for hmax in (5.0, 3.0, 2.0, 1.25):
        geo = f"""SetFactory("OpenCASCADE");
Box(1) = {{0,{-b / 2},{-hgt / 2}, {L},{b},{hgt}}};
Mesh.CharacteristicLengthMax = {hmax};
Mesh.CharacteristicLengthMin = {hmax / 3};
Mesh.ElementOrder = 2;
Mesh.HighOrderOptimize = 1;
Physical Volume("PART") = {{1}};
Physical Surface("TIP") = Surface In BoundingBox{{{L - 0.1},-100,-100, {L + 0.1},100,100}};
Mesh 3;
Save "mesh.inp";
"""
        g = ccx.gmsh_mesh(geo, WORK / "C8" / f"h{hmax}")
        part = ccx.mesh_from_gmsh(g, "PART")
        P_ = g["nodes"]
        loads = {}
        tris = np.vstack([c for _, c in g["groups"]["TIP"]])
        areas = []
        for t in tris:
            c = P_[t[:3] - 1]
            areas.append(0.5 * np.linalg.norm(np.cross(c[1] - c[0], c[2] - c[0])))
        tr = np.array([0, 0, -P]) / sum(areas)
        for t, a in zip(tris, areas):
            for nd in t[3:]:
                loads[int(nd)] = loads.get(int(nd), 0) + tr * a / 3
        used = np.unique(part.elems)
        fix = used[np.abs(P_[used - 1, 0]) < 1e-6]
        deck = (ccx.deck_mesh([(ccx.Mesh(P_, part.elems, "C3D10"), "E")]) + ccx.nset("FIX", fix) + ccx.iso_material("AL", E, nu) +
                "*SOLID SECTION, ELSET=E, MATERIAL=AL\n*STEP\n*STATIC\n*BOUNDARY\nFIX,1,3\n" + ccx.cload(loads) +
                "*NODE FILE\nU\n*EL FILE\nS\n*NODE PRINT, NSET=FIX, TOTALS=ONLY\nRF\n*END STEP\n")
        p = ccx.run(deck, WORK / "C8", f"cant_{int(hmax * 100)}")
        bl = ccx.read_frd(p.with_suffix(".frd"))
        U, S = ccx.frd_field(bl, "DISP"), ccx.frd_field(bl, "STRESS")
        tipn = [nd for nd in U if abs(P_[nd - 1, 0] - L) < 1e-6]
        d = -np.mean([U[nd][2] for nd in tipn])
        top_mid = [nd for nd in S if abs(P_[nd - 1, 0] - L / 2) < hmax and abs(P_[nd - 1, 2] - hgt / 2) < 1e-6]
        s_mid = float(np.mean([S[nd][0] for nd in top_mid]))
        R = ccx.read_reaction_totals(p.with_suffix(".dat"))
        rows.append(dict(hmax_mm=hmax, elems=len(part.elems), tip_mm=d, err_tip_pct=pct(d, d_tim), sigma_xx_mid=s_mid,
                         err_sigma_pct=pct(abs(s_mid), sig_mid), reaction_z=float(R[0][2]) if R else None))
        print("C8", rows[-1])
    return dict(case="6061 bar 200x20x10 mm, clamped root face, 100 N tip shear traction", tip_euler_mm=d_eb, tip_timoshenko_mm=d_tim,
                sigma_mid_ref=sig_mid, mesh=rows,
                note="the clamped face also restrains Poisson contraction and warping, which stiffens the solid by a fraction of a percent")


CASES = dict(C1=c1, C2=c2, C3=c3, C4=c4, C5=c5, C6=c6, C7=c7, C8=c8)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sel = sys.argv[1:] or list(CASES)
    for k in sel:
        t0 = time.time()
        r = CASES[k]()
        r["_wall_s"] = round(time.time() - t0, 1)
        (OUT / f"ccx_{k}.json").write_text(json.dumps(r, indent=1, default=float))
        print(f"{k} done in {r['_wall_s']} s")


if __name__ == "__main__":
    main()
