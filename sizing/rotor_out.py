"""One-lift-motor-out trim [H6]: minimise the largest rotor thrust with one rotor failed, trimming vertical force,
roll, pitch and yaw (yaw from reaction torque Q = k_QT T of fixed-pitch rotors).  Also: choice of the spin pattern
(mirror-antisymmetric patterns) that minimises the worst case, and a lookup of the worst-case thrust factor for the
vectorised sizing model.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import linprog


def lp_max_thrust(pos_xy, spin, Fz, k_qt, failed=None):
    """pos_xy (n x 2) relative to the CG; spin +1 CCW from above.  Returns (T_max, thrusts) or (inf, None)."""
    n = len(pos_xy)
    idx = [i for i in range(n) if i != failed]
    m = len(idx)
    c = np.zeros(m + 1)
    c[-1] = 1.0
    Aeq = np.zeros((4, m + 1))
    for j, i in enumerate(idx):
        # Fz, roll (y T), pitch (x T), yaw (rotor reaction torque on the airframe -spin k T)
        Aeq[:, j] = [1.0, pos_xy[i, 1], pos_xy[i, 0], -spin[i] * k_qt]
    Aub = np.hstack([np.eye(m), -np.ones((m, 1))])
    sol = linprog(c, A_ub=Aub, b_ub=np.zeros(m), A_eq=Aeq, b_eq=[Fz, 0, 0, 0], bounds=[(0, None)] * (m + 1), method="highs")
    if not sol.success:
        return np.inf, None
    T = np.zeros(n)
    T[idx] = sol.x[:-1]
    return float(sol.x[-1]), T


def worst_case(pos_xy, spin, Fz, k_qt):
    res = [lp_max_thrust(pos_xy, spin, Fz, k_qt, f) for f in range(len(pos_xy))]
    tm = [r[0] for r in res]
    k = int(np.argmax(tm))
    return tm[k], k, res


def best_spin_pattern(pos_xy, Fz, k_qt):
    """Search spin patterns for the starboard rotors (y > 0); port rotors are the mirror image with opposite spin,
    so the hover yaw moment is zero by construction.  Returns (spin array, worst T_max)."""
    n = len(pos_xy)
    stbd = [i for i in range(n) if pos_xy[i, 1] > 0]
    best = (None, np.inf, None)
    for pat in itertools.product((1, -1), repeat=len(stbd)):
        if pat[0] != 1:
            continue
        spin = np.zeros(n)
        for s, i in zip(pat, stbd):
            spin[i] = s
            j = int(np.argmin(np.hypot(pos_xy[:, 0] - pos_xy[i, 0], pos_xy[:, 1] + pos_xy[i, 1])))
            spin[j] = -s
        t, _, _ = worst_case(pos_xy, spin, Fz, k_qt)
        # ties (within 0.1 %) are broken in favour of more spin alternation along each boom (yaw authority without
        # large roll/pitch coupling)
        alt = sum(spin[i] != spin[i + 1] for i in range(n - 1) if abs(pos_xy[i, 1] - pos_xy[i + 1, 1]) < 1e-9)
        key = (round(t, 4), -alt)
        if best[0] is None or key < best[2]:
            best = (spin, t, key)
    return best[0], best[1]


def layout_xy(xr_row, b_y):
    """Rotor positions (x relative to the CG) on two booms at y = +-b_y, port first then starboard."""
    xs = list(xr_row)
    return np.array([[x, -b_y] for x in xs] + [[x, b_y] for x in xs])


def oei_factor_table(a_ratios, p_ratios, k_ratios, n_per_boom=4):
    """Worst-case (over failures) T_max / (W/n) for rotor layouts normalised by b_y:  a = inner arm, p = pitch,
    k = k_QT / b_y; best spin pattern for each point.  Used to build sizing/results/oei_table.json."""
    out = np.zeros((len(a_ratios), len(p_ratios), len(k_ratios)))
    for i, a in enumerate(a_ratios):
        for j, p in enumerate(p_ratios):
            row = [-(a + p), -a, a, a + p] if n_per_boom == 4 else ([-a, 0.0, a] if n_per_boom == 3 else [-a, a])
            pos = layout_xy(row, 1.0)
            n = len(pos)
            for k, kq in enumerate(k_ratios):
                _, t = best_spin_pattern(pos, 1.0, kq)
                out[i, j, k] = t * n
    return out
