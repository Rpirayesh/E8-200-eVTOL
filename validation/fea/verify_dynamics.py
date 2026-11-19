"""Verification of the phase-2 tools: flutter, divergence, whirl, gear energy, part mesh convergence.

    ~/tools/cadenv/bin/python validation/fea/verify_dynamics.py

D1  typical-section flutter (Hodges & Pierce case: mu 20, a -0.2, x_a 0.1, r^2 0.24, sigma 0.4): modal k-method
    implementation vs the 2-DOF determinant (same theory, independent code paths)
D2  Goland wing flutter (strip theory, sea-level-like rho 1.02 kg/m^3): frame modes + modal k-method vs published
    137 m/s / 70.7 rad/s; mesh 10 / 20 / 40 elements
D3  divergence of a uniform cantilever wing: beam-model eigenproblem vs q_D = pi^2 GJ / (4 e c a0 L^2)
D4  pivoted-rotor gyroscopic whirl frequencies without aerodynamics vs I w^2 -+ Ip Omega w - K = 0
D5  skid-gear frame vertical stiffness vs inclined-cantilever formula
D6  mesh convergence of the C3D10 fitting model (P1 wing-root lug, peak von Mises away from the supports)
Results -> validation/fea/results/dynamics_checks.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import scipy.linalg as sla

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fea.dynamics import flutter_k_method, modal_flutter, whirl  # noqa: E402
from fea.frame import Frame, Section  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"


def d1():
    rho, b, mu, xa, r2, sig, a = 1.0, 1.0, 20.0, 0.1, 0.24, 0.4, -0.2
    _, fl2 = flutter_k_method(mu, a, xa, r2, sig, 0.0)
    m = mu * math.pi * rho * b * b
    M = np.array([[m, m * b * xa], [m * b * xa, m * b * b * r2]])
    K = np.diag([m * sig**2, m * b * b * r2])
    w2, V = sla.eigh(K, M)
    flm, _ = modal_flutter(np.sqrt(w2), np.array([V[0, :]]), np.array([V[1, :]]), [dict(b=b, a=a, w=1.0)], b, rho=rho, g_s=0.0)
    return dict(V_det=fl2["V_over_bwa"], V_modal=flm["V"], diff_pct=100 * (flm["V"] - fl2["V_over_bwa"]) / fl2["V_over_bwa"],
                w_det=fl2["w_over_wa"], w_modal=flm["omega"], textbook_note="Hodges & Pierce (2011) sec. 5.x example, U_F/(b w_theta) ~ 2.17")


def goland(n):
    L, c, mpl, Icg, EI, GJ = 6.096, 1.8288, 35.71, 8.64, 9.77e6, 0.987e6
    b, a, xcg = c / 2, (0.33 - 0.5) / 0.5, 0.10 * c
    f = Frame()
    ys = np.linspace(0, L, n + 1)
    nodes = [f.node((0, y, 0)) for y in ys]
    E, G = 70e9, 27e9
    s = Section(A=1.0, Iy=EI / E, Iz=EI / E * 100, J=GJ / G, E=E, G=G, rho=0.0)
    for i in range(n):
        f.beam(nodes[i], nodes[i + 1], s, vref=(0, 0, 1))
    w = np.full(n + 1, L / n)
    w[0] = w[-1] = L / n / 2
    for i, nd in enumerate(nodes):
        mn = f.node((xcg, ys[i], 0))
        f.beam(nd, mn, Section.rigid(), vref=(0, 0, 1))
        f.add_mass(mn, mpl * w[i], (0, Icg * w[i], 0))
    fr, V = f.modes(12, fixed_dofs=list(range(6)))
    keep = list(range(6))
    H = np.array([-V[6 * nd + 2, keep] for nd in nodes])
    A = np.array([V[6 * nd + 4, keep] for nd in nodes])
    fl, _ = modal_flutter(2 * math.pi * fr[keep], H, A, [dict(b=b, a=a, w=w[i]) for i in range(n + 1)], b, rho=1.02, g_s=0.0)
    return dict(n=n, f_hz=fr[:3].tolist(), V=fl["V"], omega=fl["omega"], err_V_pct=100 * (fl["V"] - 137.2) / 137.2,
                err_omega_pct=100 * (fl["omega"] - 70.7) / 70.7)


def d3():
    L, c, GJ, e, a0 = 4.0, 1.2, 2.0e5, 0.15, 2 * math.pi
    rows = []
    q_ref = math.pi**2 * GJ / (4 * e * c * a0 * L**2)
    for n in (5, 10, 20, 40):
        f = Frame()
        ys = np.linspace(0, L, n + 1)
        nodes = [f.node((0, y, 0)) for y in ys]
        s = Section(A=1.0, Iy=1e-3, Iz=1e-3, J=GJ / 27e9, E=70e9, G=27e9, rho=0.0)
        for i in range(n):
            f.beam(nodes[i], nodes[i + 1], s, vref=(0, 0, 1))
        K, _ = f.assemble(with_mass=False)
        Ka = np.zeros((f.ndof, f.ndof))
        w = np.full(n + 1, L / n)
        w[0] = w[-1] = L / n / 2
        for i, nd in enumerate(nodes):
            Ka[6 * nd + 2, 6 * nd + 4] += a0 * c * w[i]
            Ka[6 * nd + 4, 6 * nd + 4] += a0 * c * w[i] * e
        free = np.arange(6, f.ndof)
        lam = sla.eigvals(Ka[np.ix_(free, free)], K[free][:, free].toarray())
        lam = lam[np.isfinite(lam) & (np.abs(lam.imag) < 1e-9 * np.abs(lam).max()) & (lam.real > 0)]
        q = 1 / lam.real.max()
        rows.append(dict(n=n, q=q, err_pct=100 * (q - q_ref) / q_ref))
    return dict(q_ref=q_ref, mesh=rows)


def d4():
    K, I, Ip, Om = 2.0e5, 5.0, 1.0, 2 * math.pi * 2000 / 60
    ev = whirl(K, I, Ip, Om, 1e-6, dict(R=0.9, Rh=0.14, B=3, chord=1e-9, a=0.3, V_design=40.0, alpha_design_deg=4.0), damping=0.0)
    f_num = np.sort(np.unique(np.round(np.abs(ev.imag), 6)))
    roots = np.sort([(Ip * Om + math.sqrt((Ip * Om) ** 2 + 4 * I * K)) / (2 * I), (-Ip * Om + math.sqrt((Ip * Om) ** 2 + 4 * I * K)) / (2 * I)])
    return dict(numeric_rad_s=f_num.tolist(), analytic_rad_s=roots.tolist(), err_pct=(100 * (f_num - roots) / roots).tolist())


def d5():
    from fea.gear import gear_frame
    oml = {"cross_tube": {"od": 0.076, "t": 0.006}, "skids": [{"y": 0.7, "z": 0.03, "x_start": 0.0, "x_end": 2.0, "diameter": 0.2, "t": 0.02}],
           "struts": [{"p1": [1.0, 0.7, 0.06], "p2": [1.0, 0.28, 0.45]}]}
    f, fixed, contact, cts = gear_frame(oml)
    F = np.zeros(f.ndof)
    for n in contact:
        F[6 * n + 2] = -1000.0
    u, _ = f.solve_static(F, [6 * n + k for n in fixed for k in range(6)])
    d = -np.mean([u[6 * n + 2] for n in contact])
    L = math.hypot(0.42, 0.39)
    c, s_ = 0.42 / L, 0.39 / L
    EI, EA = cts.E * cts.Iy, cts.E * cts.A
    GA = cts.G * cts.Az
    d_ref = 1000 * (L**3 / (3 * EI) * c**2 + L / EA * s_**2 + L / GA * c**2)
    return dict(frame_mm=d * 1000, formula_mm=d_ref * 1000, err_pct=100 * (d - d_ref) / d_ref,
                note="stiff skid tube; inclined cantilever arm: bending + axial + shear; skid-tube flexibility makes the frame softer")


def d6():
    import fea.parts as PT
    from fea import ccx
    L, g = PT.global_loads()
    rows = []
    orig = PT.run_part
    res = {}

    def capture(name, solid, mt, hmax, hmin, refine, bc, ld, title, extra_fn=None, view=(25, -60)):
        for hm, hr in ((10.0, 4.0), (7.0, 2.5), (5.0, 1.6), (4.0, 1.2)):
            work = PT.WORK / f"conv_{hm}"
            m = ccx.mesh_solid(solid, work, hm, hr, [(0, 0, -95.0, 30, hr)])
            faces = ccx.boundary_faces(m)
            fixed = PT.nodes_of(bc(m, faces))
            loads, loaded = ld(m, faces)
            r = ccx.solve_solid(m, mt["E"], mt["nu"], fixed, loads, work, "part")
            ev = PT.evaluate(name, m, r, mt, fixed, loaded, 2.5)
            rows.append(dict(hmax=hm, h_hole=hr, elems=len(m.elems), peak_MPa=ev["vm_peak_away_from_bc"], umax_mm=ev["umax_mm"]))
            print("D6", rows[-1])
        return {}
    PT.run_part = capture
    try:
        PT.P1_wing_root(L)
    finally:
        PT.run_part = orig
    ref = rows[-1]
    for r in rows:
        r["peak_diff_pct"] = 100 * (r["peak_MPa"] - ref["peak_MPa"]) / ref["peak_MPa"]
        r["umax_diff_pct"] = 100 * (r["umax_mm"] - ref["umax_mm"]) / ref["umax_mm"]
    return dict(part="P1 wing-root lug (12 mm, 7075-T6), loads of the sized design", mesh=rows,
                note="peak measured away (>= 3.75 mm) from the bolt-hole supports and the pin bearing surface")


def main():
    OUT.mkdir(exist_ok=True)
    res = dict(D1=d1(), D2=[goland(n) for n in (10, 20, 40)], D3=d3(), D4=d4(), D5=d5())
    print(json.dumps(res, indent=1, default=float))
    res["D6"] = d6()
    (OUT / "dynamics_checks.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
