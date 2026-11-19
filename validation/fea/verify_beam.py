"""Verification of the beam/frame solver fea/frame.py against closed-form solutions.

    ~/tools/cadenv/bin/python validation/fea/verify_beam.py

B1  cantilever, tip load and uniform load: Euler-Bernoulli and Timoshenko (short composite tube)
B2  tapered cantilever tube (linearly varying diameter): Mohr integral reference, convergence
B3  torsion of thin-walled tubes: round (exact) and rectangular (Bredt); CalculiX shell cross-check in verify_ccx.py
B4  inertia relief: free-free beam, central and end loads (bending-moment distribution), 3-D frame equilibrium
B5  free-free beam modes vs Euler-Bernoulli (consistent and lumped mass), cantilever with tip mass
B6  Euler buckling: pinned-pinned and cantilever columns (geometric stiffness)
B7  3-D L-shaped cantilever (bending + torsion coupling) - checks transformations and assembly
Results -> validation/fea/results/beam.json and validation/fea/img/*.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fea.frame import Frame, Section  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
IMG = Path(__file__).resolve().parent / "img"

# carbon tube (roll-wrapped, quasi-axial): representative values only for verification
E_CF, G_CF, RHO_CF = 70e9, 5e9, 1550.0


def pct(a, b):
    return 100.0 * (a - b) / b


def cantilever(sec, L, n, tip=None, q=None, tip_mass=0.0):
    f = Frame()
    a, b = f.node((0, 0, 0)), f.node((L, 0, 0))
    chain = f.beam(a, b, sec, n=n)
    F = np.zeros(f.ndof)
    if tip is not None:
        F[6 * b + 2] = tip
    if q is not None:   # consistent nodal loads of a uniform load q (N/m) in z
        for e in range(n):
            le = L / n
            i, j = chain[e], chain[e + 1]
            F[6 * i + 2] += q * le / 2
            F[6 * j + 2] += q * le / 2
            F[6 * i + 4] += -q * le**2 / 12
            F[6 * j + 4] += q * le**2 / 12
    if tip_mass:
        f.add_mass(b, tip_mass)
    return f, chain, F


# ----------------------------------------------------------------------------- B1
def b1():
    out = {}
    ro, ri, L, P = 0.040, 0.037, 2.0, 1000.0
    s_eb = Section.pipe(ro, ri, E_CF, G_CF, RHO_CF, shear=False)
    I = s_eb.Iy
    rows = []
    for n in (1, 2, 4, 8, 16):
        f, ch, F = cantilever(s_eb, L, n, tip=-P)
        u, R = f.solve_static(F, list(range(6)))
        st = f.stresses(u)
        rows.append(dict(n=n, tip_m=-u[6 * ch[-1] + 2], root_moment_Nm=abs(st[0]["My"]), sigma_root_Pa=st[0]["sigma"]))
    ref = dict(tip_m=P * L**3 / (3 * E_CF * I), root_moment_Nm=P * L, sigma_root_Pa=P * L * ro / I)
    for r in rows:
        r["err_tip_pct"] = pct(r["tip_m"], ref["tip_m"])
        r["err_sigma_pct"] = pct(r["sigma_root_Pa"], ref["sigma_root_Pa"])
    out["B1a tip load EB"] = dict(case="CF tube 80x3 mm, L=2 m, 1 kN tip", reference=ref, mesh=rows)
    # uniform load
    q = -2000.0
    rows = []
    for n in (1, 2, 4, 8, 16):
        f, ch, F = cantilever(s_eb, L, n, q=q)
        u, _ = f.solve_static(F, list(range(6)))
        st = f.stresses(u)
        mid = ch[len(ch) // 2] if n > 1 else None
        rows.append(dict(n=n, tip_m=-u[6 * ch[-1] + 2], root_moment_Nm=abs(st[0]["My"])))
    ref = dict(tip_m=-q * L**4 / (8 * E_CF * I), root_moment_Nm=-q * L**2 / 2)
    for r in rows:
        r["err_tip_pct"] = pct(r["tip_m"], ref["tip_m"])
        r["err_moment_pct"] = pct(r["root_moment_Nm"], ref["root_moment_Nm"])
    out["B1b uniform load EB"] = dict(case="same tube, 2 kN/m", reference=ref, mesh=rows,
                                      note="element-end moments of consistent loads are exact at nodes")
    # Timoshenko: short thick composite tube with low shear modulus
    ro, ri, L = 0.040, 0.034, 0.4
    s_t = Section.pipe(ro, ri, E_CF, G_CF, RHO_CF, shear=True)
    rows = []
    for n in (1, 4, 16):
        f, ch, F = cantilever(s_t, L, n, tip=-P)
        u, _ = f.solve_static(F, list(range(6)))
        rows.append(dict(n=n, tip_m=-u[6 * ch[-1] + 2]))
    d_b = P * L**3 / (3 * E_CF * s_t.Iy)
    d_s = P * L / (G_CF * s_t.Az)
    for r in rows:
        r["err_tip_pct"] = pct(r["tip_m"], d_b + d_s)
    out["B1c tip load Timoshenko"] = dict(case="CF tube 80x6, L=0.4 m, G=5 GPa, k=0.5", reference=dict(tip_bending_m=d_b, tip_shear_m=d_s,
                                          tip_m=d_b + d_s, shear_share_pct=100 * d_s / (d_b + d_s)), mesh=rows)
    return out


# ----------------------------------------------------------------------------- B2
def b2():
    L, P, t = 3.0, 500.0, 0.0025
    D0, D1 = 0.10, 0.04          # root and tip outer diameter (boom/spar-like taper)

    def I_of(x):
        ro = (D0 + (D1 - D0) * x / L) / 2
        return np.pi / 4 * (ro**4 - (ro - t) ** 4)

    def c_of(x):
        return (D0 + (D1 - D0) * x / L) / 2
    tip_ref = quad(lambda x: P * (L - x) ** 2 / (E_CF * I_of(x)), 0, L, epsabs=1e-14, limit=200)[0]
    slope_ref = quad(lambda x: P * (L - x) / (E_CF * I_of(x)), 0, L, epsabs=1e-14, limit=200)[0]
    # maximum bending stress location (not at the root for strong taper)
    xs = np.linspace(0, L, 3001)
    sig = P * (L - xs) * c_of(xs) / I_of(xs)
    rows = []
    for n in (2, 4, 8, 16, 32, 64):
        f = Frame()
        nodes = [f.node((x, 0, 0)) for x in np.linspace(0, L, n + 1)]
        for e in range(n):
            xm = (e + 0.5) * L / n
            ro = c_of(xm)
            f.beam(nodes[e], nodes[e + 1], Section.pipe(ro, ro - t, E_CF, G_CF, RHO_CF, shear=False))
        F = np.zeros(f.ndof)
        F[6 * nodes[-1] + 2] = -P
        u, _ = f.solve_static(F, list(range(6)))
        st = f.stresses(u)
        rows.append(dict(n=n, tip_m=-u[6 * nodes[-1] + 2], slope=abs(u[6 * nodes[-1] + 4]),
                         sigma_max_Pa=max(s["sigma"] for s in st)))
        rows[-1]["err_tip_pct"] = pct(rows[-1]["tip_m"], tip_ref)
        rows[-1]["err_slope_pct"] = pct(rows[-1]["slope"], slope_ref)
        rows[-1]["err_sigma_pct"] = pct(rows[-1]["sigma_max_Pa"], sig.max())
    return {"B2 tapered cantilever": dict(case="CF tube OD 100->40 mm, t 2.5 mm, L 3 m, 500 N tip; piecewise-constant elements",
                                          reference=dict(tip_m=tip_ref, slope=slope_ref, sigma_max_Pa=float(sig.max()),
                                                         x_sigma_max_m=float(xs[sig.argmax()])), mesh=rows,
                                          note="stress compared at element ends with section of the element mid-point: O(h) in stress, O(h^2) in deflection")}


# ----------------------------------------------------------------------------- B3
def b3():
    out = {}
    L, T = 1.5, 400.0
    ro, ri = 0.030, 0.0285
    s = Section.pipe(ro, ri, E_CF, G_CF, RHO_CF)
    f, ch, _ = cantilever(s, L, 4)
    F = np.zeros(f.ndof)
    F[6 * ch[-1] + 3] = T
    u, _ = f.solve_static(F, list(range(6)))
    st = f.stresses(u)
    J_ex = np.pi / 2 * (ro**4 - ri**4)
    rm, t = (ro + ri) / 2, ro - ri
    J_thin = 2 * np.pi * rm**3 * t
    out["B3a round tube torsion"] = dict(case="CF tube 60x1.5, L 1.5 m, 400 N m", twist_rad=u[6 * ch[-1] + 3], twist_ref=T * L / (G_CF * J_ex),
                                         tau_Pa=st[0]["tau"], tau_ref=T * ro / J_ex,
                                         err_twist_pct=pct(u[6 * ch[-1] + 3], T * L / (G_CF * J_ex)), err_tau_pct=pct(st[0]["tau"], T * ro / J_ex),
                                         J_thin_wall_vs_exact_pct=pct(J_thin, J_ex))
    # rectangular box (wing-box-like), Bredt
    b, h, tw, tf = 0.20, 0.12, 0.002, 0.003
    s = Section.rect_tube(b, h, tw, tf, 50e9, 4e9, 1500.0)
    f, ch, _ = cantilever(s, L, 4)
    F = np.zeros(f.ndof)
    F[6 * ch[-1] + 3] = T * 5
    u, _ = f.solve_static(F, list(range(6)))
    st = f.stresses(u)
    Am = (b - tw) * (h - tf)
    J_b = 4 * Am**2 / (2 * (b - tw) / tf + 2 * (h - tf) / tw)
    out["B3b box torsion (Bredt)"] = dict(case="box 200x120, webs 2 mm, flanges 3 mm, G 4 GPa, 2 kN m", J_m4=s.J, J_bredt=J_b,
                                          twist_rad=u[6 * ch[-1] + 3], twist_ref=T * 5 * L / (4e9 * J_b),
                                          err_twist_pct=pct(u[6 * ch[-1] + 3], T * 5 * L / (4e9 * J_b)),
                                          tau_web_Pa=st[0]["tau"], tau_ref=T * 5 / (2 * Am * tw),
                                          note="CalculiX S8R shell model of the same box: case C7 in verify_ccx.py")
    return out


# ----------------------------------------------------------------------------- B4
def b4():
    out = {}
    L, m, P, n = 2.0, 10.0, 100.0, 40
    s = Section.pipe(0.03, 0.028, E_CF, G_CF, 0.0)
    s.m_per_len = m / L
    for lumped in (False, True):
        f = Frame(lumped=lumped)
        nodes = [f.node((x, 0, 0)) for x in np.linspace(0, L, n + 1)]
        for e in range(n):
            f.beam(nodes[e], nodes[e + 1], s)
        # central load
        F = np.zeros(f.ndof)
        F[6 * nodes[n // 2] + 2] = P
        u, info = f.solve_inertia_relief(F, nodes[0])
        st = f.stresses(u)
        Mc = max(abs(r["My"]) for r in st)
        key = "lumped" if lumped else "consistent"
        out[f"B4a free-free central load ({key} mass)"] = dict(
            case="uniform free-free beam 2 m, 10 kg, 100 N at mid-span", M_center_Nm=Mc, M_ref=P * L / 8,
            err_pct=pct(Mc, P * L / 8), accel=info["accel"].tolist(), accel_ref=[0, 0, P / m],
            support_reaction_N=float(np.linalg.norm(info["reaction"][:3])))
        # end load: M(x) = P x - (P/L)(2 x^2 - x^3/L), x measured from the loaded end
        F = np.zeros(f.ndof)
        F[6 * nodes[-1] + 2] = P
        u, info = f.solve_inertia_relief(F, nodes[0])
        fl = f.element_forces(u)
        xs = np.array([f.nodes[a][0] for (a, b_, *_r) in f.elems])
        M_fe = np.array([abs(e[4]) for e in fl])            # moment at element start node
        xi = L - xs                                         # distance from the loaded end
        M_ref = P * xi - P / L * (2 * xi**2 - xi**3 / L)
        out[f"B4b free-free end load ({key} mass)"] = dict(
            case="same beam, 100 N at one end: a = P/m, alpha = 6P/(mL)", M_max_Nm=float(M_fe.max()), M_max_ref=4 / 27 * P * L,
            err_pct=pct(M_fe.max(), 4 / 27 * P * L), max_abs_err_over_span_pct_of_max=float(100 * np.max(np.abs(M_fe - M_ref)) / M_ref.max()),
            alpha=float(info["alpha"][1]), alpha_ref=-6 * P / (m * L), accel_z=float(info["accel"][2]), accel_ref=P / m,
            support_reaction_N=float(np.linalg.norm(info["reaction"][:3])))
        if not lumped:
            _plot_b4(xi, M_fe, M_ref, P, L)
    # 3-D frame with random loads: equilibrium of applied + inertia loads, gravity-only check
    rng = np.random.default_rng(1)
    f = Frame()
    pts = [(0, 0, 0), (2, 0, 0), (2, 3, 0), (0, 3, 1), (1, 1.5, 2)]
    ids = [f.node(p) for p in pts]
    tube = Section.pipe(0.03, 0.027, 70e9, 5e9, 1550.0)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            f.beam(ids[i], ids[j], tube, n=6)
    for k in ids:
        f.add_mass(k, float(rng.uniform(5, 20)), tuple(rng.uniform(0.1, 0.5, 3)))
    F = rng.normal(0, 200, f.ndof)
    u, info = f.solve_inertia_relief(F, ids[0])
    Fb = info["F_balanced"]
    Phi = f.rigid_modes()
    res = Phi.T @ Fb
    u0, info0 = f.solve_inertia_relief(np.zeros(f.ndof), ids[0], gravity=(0, 0, -9.80665))
    out["B4c 3-D frame random loads"] = dict(
        case="5-node space frame, 10 tubes, random nodal forces/moments and lumped masses",
        resultant_force_of_balanced_loads_N=float(np.linalg.norm(res[:3])), resultant_moment_Nm=float(np.linalg.norm(res[3:])),
        applied_force_norm_N=float(np.linalg.norm((Phi.T @ F)[:3])), support_reaction_N=float(np.linalg.norm(info["reaction"])),
        gravity_only_max_disp_m=float(np.abs(u0).max()), gravity_only_accel=info0["accel"].tolist())
    return out


def _plot_b4(xi, M_fe, M_ref, P, L):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 3.4), dpi=130)
    o = np.argsort(xi)
    x = np.linspace(0, L, 200)
    ax.plot(x, P * x - P / L * (2 * x**2 - x**3 / L), "-", color="#1f5fa8", label="closed form")
    ax.plot(xi[o], M_fe[o], "o", ms=3, color="#d1495b", label="frame, inertia relief")
    ax.set_xlabel("distance from loaded end (m)")
    ax.set_ylabel("bending moment (N m)")
    ax.set_title("B4b free-free beam, end load balanced by inertia", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMG / "b4_inertia_relief.png")
    plt.close(fig)


# ----------------------------------------------------------------------------- B5
def b5():
    out = {}
    L = 3.0
    s = Section.pipe(0.05, 0.047, E_CF, G_CF, RHO_CF, shear=False)
    bl = np.array([4.730041, 7.853205, 10.995608])
    f_ref = bl**2 / (2 * np.pi) * math.sqrt(E_CF * s.Iy / (s.mass_per_length * L**4))
    for lumped in (False, True):
        rows = []
        for n in (4, 8, 16, 32, 64):
            f = Frame(lumped=lumped)
            a, b = f.node((0, 0, 0)), f.node((L, 0, 0))
            f.beam(a, b, s, n=n)
            fr, V = f.modes(14)
            # keep bending modes only (no torsion rx or axial ux content); each appears twice (two planes)
            bend = []
            for k, fk in enumerate(fr):
                v = V[:, k].reshape(-1, 6)
                if fk > 1.0 and np.linalg.norm(v[:, [0, 3]]) < 1e-6 * np.linalg.norm(v):
                    bend.append(fk)
            uniq = np.unique(np.round(bend, 6))[:3]
            rows.append(dict(n=n, f_hz=uniq.tolist(), err_pct=[pct(a_, b_) for a_, b_ in zip(uniq, f_ref)],
                             n_rigid=int(np.sum(fr < 1e-2 * f_ref[0]))))
        out[f"B5a free-free beam modes ({'lumped' if lumped else 'consistent'} mass)"] = dict(
            case="CF tube 100x3, L 3 m, free-free", f_ref_hz=f_ref.tolist(), mesh=rows)
    # cantilever with tip mass (characteristic equation)
    ro, ri, L, m_tip = 0.015, 0.0135, 1.0, 0.3
    s = Section.pipe(ro, ri, E_CF, G_CF, RHO_CF, shear=False)
    mu = s.mass_per_length * L
    ratio = m_tip / mu
    fn = lambda x: 1 + math.cos(x) * math.cosh(x) + ratio * x * (math.cos(x) * math.sinh(x) - math.sin(x) * math.cosh(x))
    x1 = brentq(fn, 0.5, 1.875)
    f_an = x1**2 / (2 * math.pi) * math.sqrt(E_CF * s.Iy / (s.mass_per_length * L**4))
    f, ch, _ = cantilever(s, L, 20, tip_mass=m_tip)
    fr, _ = f.modes(4, fixed_dofs=list(range(6)))
    out["B5b cantilever with tip mass"] = dict(case="CF tube 30x27, 1 m, 0.3 kg tip mass, 20 elements", f1_hz=float(fr[0]), f1_ref_hz=f_an,
                                               err_pct=pct(fr[0], f_an))
    return out


# ----------------------------------------------------------------------------- B6
def b6():
    out = {}
    L = 2.0
    s = Section.pipe(0.025, 0.023, E_CF, G_CF, RHO_CF, shear=False)
    Pe = math.pi**2 * E_CF * s.Iy / L**2
    for name, k_eff, bc in (("pinned-pinned", 1.0, "pp"), ("cantilever", 2.0, "cf")):
        rows = []
        for n in (2, 4, 8, 16):
            f = Frame()
            a, b = f.node((0, 0, 0)), f.node((L, 0, 0))
            f.beam(a, b, s, n=n)
            F = np.zeros(f.ndof)
            F[6 * b] = -1.0
            if bc == "pp":
                fixed = [0, 1, 2, 3, 6 * b + 1, 6 * b + 2]
            else:
                fixed = list(range(6))
            lam = f.buckling(F, fixed, 2)
            ref = Pe / k_eff**2
            rows.append(dict(n=n, Pcr_N=float(lam[0]), err_pct=pct(lam[0], ref)))
        out[f"B6 Euler buckling {name}"] = dict(case=f"CF tube 50x2, L 2 m, {name}", Pcr_ref_N=Pe / k_eff**2, mesh=rows)
    return out


# ----------------------------------------------------------------------------- B7
def b7():
    a, b, P = 1.2, 0.8, 300.0
    s = Section.pipe(0.025, 0.022, E_CF, G_CF, RHO_CF, shear=False)
    f = Frame()
    n0, n1, n2 = f.node((0, 0, 0)), f.node((a, 0, 0)), f.node((a, b, 0))
    f.beam(n0, n1, s, n=3)
    f.beam(n1, n2, s, n=3)
    F = np.zeros(f.ndof)
    F[6 * n2 + 2] = -P
    u, R = f.solve_static(F, list(range(6)))
    EI, GJ = E_CF * s.Iy, G_CF * s.J
    ref = P * a**3 / (3 * EI) + P * b**3 / (3 * EI) + P * a * b**2 / GJ
    tip = -u[6 * n2 + 2]
    root_T = abs(R[3])
    return {"B7 3-D L-frame": dict(case="L-shaped CF tube cantilever 1.2 m + 0.8 m, 300 N tip load normal to the plane",
                                   tip_m=tip, tip_ref_m=ref, err_pct=pct(tip, ref), root_torque_Nm=root_T, root_torque_ref=P * b,
                                   root_moment_Nm=abs(R[4]), root_moment_ref=P * a)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    res = {}
    for fn in (b1, b2, b3, b4, b5, b6, b7):
        r = fn()
        res.update(r)
        for k, v in r.items():
            print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("case",)}, default=float)[:400])
    (OUT / "beam.json").write_text(json.dumps(res, indent=1, default=float))
    _plot_convergence(res)


def _plot_convergence(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3.8), dpi=130)
    series = [("B2 tapered cantilever", "err_tip_pct", "B2 tapered: tip deflection"),
              ("B2 tapered cantilever", "err_sigma_pct", "B2 tapered: max stress"),
              ("B1b uniform load EB", "err_tip_pct", "B1b UDL: tip deflection")]
    for key, col, lab in series:
        rows = res[key]["mesh"]
        ax.loglog([r["n"] for r in rows], [max(abs(r[col]), 1e-10) for r in rows], "o-", label=lab)
    for lumped in ("consistent", "lumped"):
        rows = res[f"B5a free-free beam modes ({lumped} mass)"]["mesh"]
        ax.loglog([r["n"] for r in rows], [max(abs(r["err_pct"][2]), 1e-10) for r in rows], "s--", label=f"B5a mode 3 ({lumped} mass)")
    for name in ("pinned-pinned", "cantilever"):
        rows = res[f"B6 Euler buckling {name}"]["mesh"]
        ax.loglog([r["n"] for r in rows], [max(abs(r["err_pct"]), 1e-10) for r in rows], "^:", label=f"B6 buckling {name}")
    ax.set_xlabel("elements along the member")
    ax.set_ylabel("|error| vs closed form (%)")
    ax.set_title("Frame solver mesh convergence", fontsize=9)
    ax.grid(alpha=0.3, which="both")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(IMG / "beam_convergence.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
