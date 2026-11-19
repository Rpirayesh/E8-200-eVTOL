"""Classical Lamination Theory: ply stiffness, ABD matrices, ply stresses/strains, failure indices.

Plies are dicts with E1, E2, nu12, G12 (Pa) and optional strengths Xt, Xc, Yt, Yc, S (Pa, positive)
and strain limits; a layup is a list of (ply, angle_deg, thickness_m) from the bottom (-z) surface up.
Used by the material database (fea/materials.py) and verified against CalculiX S8R composite shells
(validation/fea, case C4).
"""
from __future__ import annotations

import numpy as np


def Q(p):
    E1, E2, nu12, G12 = p["E1"], p["E2"], p["nu12"], p["G12"]
    nu21 = nu12 * E2 / E1
    d = 1 - nu12 * nu21
    return np.array([[E1 / d, nu12 * E2 / d, 0], [nu12 * E2 / d, E2 / d, 0], [0, 0, G12]])


def T_stress(theta_deg):
    """Global -> material stress transformation (engineering shear kept as tensor shear inside)."""
    c, s = np.cos(np.radians(theta_deg)), np.sin(np.radians(theta_deg))
    return np.array([[c * c, s * s, 2 * c * s], [s * s, c * c, -2 * c * s], [-c * s, c * s, c * c - s * s]])


def T_strain(theta_deg):
    """Global -> material engineering strain transformation."""
    c, s = np.cos(np.radians(theta_deg)), np.sin(np.radians(theta_deg))
    return np.array([[c * c, s * s, c * s], [s * s, c * c, -c * s], [-2 * c * s, 2 * c * s, c * c - s * s]])


def Qbar(p, theta_deg):
    Te = T_strain(theta_deg)
    return Te.T @ Q(p) @ Te


def z_coords(layup):
    t = np.array([l[2] for l in layup])
    z = np.concatenate([[0], np.cumsum(t)])
    return z - z[-1] / 2


def ABD(layup):
    z = z_coords(layup)
    A, B, D = np.zeros((3, 3)), np.zeros((3, 3)), np.zeros((3, 3))
    for k, (p, th, t) in enumerate(layup):
        Qb = Qbar(p, th)
        A += Qb * (z[k + 1] - z[k])
        B += Qb * (z[k + 1] ** 2 - z[k] ** 2) / 2
        D += Qb * (z[k + 1] ** 3 - z[k] ** 3) / 3
    return A, B, D


def abd_matrix(layup):
    A, B, D = ABD(layup)
    return np.block([[A, B], [B, D]])


def engineering_constants(layup):
    """Membrane engineering constants of the laminate (symmetric or not, from the inverse of ABD)."""
    h = sum(l[2] for l in layup)
    a = np.linalg.inv(abd_matrix(layup))
    return dict(Ex=1 / (h * a[0, 0]), Ey=1 / (h * a[1, 1]), Gxy=1 / (h * a[2, 2]), nuxy=-a[0, 1] / a[0, 0], t=h)


def response(layup, N=(0, 0, 0), M=(0, 0, 0)):
    """Mid-plane strains eps0 (ex, ey, gxy), curvatures k, and per-ply stresses/strains (material axes)
    at the bottom, middle and top of every ply."""
    abd = abd_matrix(layup)
    ek = np.linalg.solve(abd, np.r_[N, M])
    e0, kap = ek[:3], ek[3:]
    z = z_coords(layup)
    plies = []
    for k, (p, th, t) in enumerate(layup):
        rows = {}
        for pos, zz in (("bot", z[k]), ("mid", 0.5 * (z[k] + z[k + 1])), ("top", z[k + 1])):
            eg = e0 + zz * kap
            sg = Qbar(p, th) @ eg
            rows[pos] = dict(z=zz, eps_global=eg, sig_global=sg, eps12=T_strain(th) @ eg, sig12=T_stress(th) @ sg)
        plies.append(dict(angle=th, t=t, **rows))
    return e0, kap, plies


def failure_index(p, s12, criterion="max_stress"):
    """Failure index (>= 1 fails) for material-axis stresses s12 = (s1, s2, t12)."""
    s1, s2, t12 = s12
    Xt, Xc, Yt, Yc, S = p["Xt"], p["Xc"], p["Yt"], p["Yc"], p["S"]
    if criterion == "max_stress":
        return max(s1 / Xt if s1 > 0 else -s1 / Xc, s2 / Yt if s2 > 0 else -s2 / Yc, abs(t12) / S)
    if criterion == "tsai_wu":
        F1, F2 = 1 / Xt - 1 / Xc, 1 / Yt - 1 / Yc
        F11, F22, F66 = 1 / (Xt * Xc), 1 / (Yt * Yc), 1 / S**2
        F12 = -0.5 * np.sqrt(F11 * F22)
        a = F11 * s1**2 + F22 * s2**2 + F66 * t12**2 + 2 * F12 * s1 * s2
        b = F1 * s1 + F2 * s2
        # strength ratio R with a R^2 + b R = 1; failure index = 1/R
        R = (-b + np.sqrt(b * b + 4 * a)) / (2 * a) if a > 0 else (1 / b if b > 0 else np.inf)
        return 1 / R
    raise ValueError(criterion)


def max_strain_index(p, e12):
    """Strain-based index against design strain limits eps_t, eps_c, gamma (positive numbers)."""
    e1, e2, g12 = e12
    return max(e1 / p["eps_t"] if e1 > 0 else -e1 / p["eps_c"], e2 / p["eps_t"] if e2 > 0 else -e2 / p["eps_c"],
               abs(g12) / p["gamma"])


def sandwich_beam(Ef, tf, Ec, Gc, tc, b=1.0):
    """Flexural rigidity D and shear stiffness S of a symmetric sandwich beam (Allen / Zenkert)."""
    d = tc + tf
    D = Ef * b * tf**3 / 6 + Ef * b * tf * d**2 / 2 + Ec * b * tc**3 / 12
    S = Gc * b * d**2 / tc
    return D, S
