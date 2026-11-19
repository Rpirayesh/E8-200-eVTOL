"""Vectorised physics for the E8-200 sizing code.  Every function accepts numpy arrays (broadcasting) or scalars.

Equation tags refer to methods/EQUATIONS.md; source ids to resources/README.md.
"""
from __future__ import annotations

import numpy as np

G0 = 9.80665
R_AIR, GAMMA = 287.053, 1.4
LB, FT, KT = 0.45359237, 0.3048, 0.514444


# ---------------------------------------------------------------- atmosphere [A1]-[A3] (ICAO Doc 7488)
def isa(h, dT=0.0):
    Ts = 288.15 - 0.0065 * np.asarray(h, float)
    p = 101325.0 * (Ts / 288.15) ** 5.25588
    T = Ts + dT
    return dict(T=T, p=p, rho=p / (R_AIR * T), a=np.sqrt(GAMMA * R_AIR * T), mu=1.458e-6 * T**1.5 / (T + 110.4))


# ---------------------------------------------------------------- rotors [H1]-[H5] (RA01 Leishman ch. 2-3)
def rotor_power(T, D, rho, vtip, sigma, kappa=1.20, cd0=0.015):
    """Shaft power (W) of one isolated rotor: kappa * T^1.5 / sqrt(2 rho A) + sigma cd0 rho A vtip^3 / 8."""
    A = np.pi * D**2 / 4
    p_i = T**1.5 / np.sqrt(2 * rho * A)
    p_0 = sigma * cd0 * rho * A * vtip**3 / 8
    return kappa * p_i + p_0, p_i


def solidity_for_blade_loading(T, D, rho, vtip, ct_sigma):
    A = np.pi * D**2 / 4
    return T / (rho * A * vtip**2) / ct_sigma


def disc_strip_area(R, xc, x1, x2):
    """Area of a disc (centre xc, radius R) between the lines x = x1 and x = x2 (x1 < x2), all y."""
    def seg_ge(u):          # area of the part with x' >= u (u relative to the centre, clipped to [-R, R])
        u = np.clip(u, -R, R)
        return R**2 * np.arccos(u / R) - u * np.sqrt(np.maximum(R**2 - u**2, 0.0))
    return np.maximum(seg_ge(x1 - xc) - seg_ge(x2 - xc), 0.0)


# ---------------------------------------------------------------- propeller [P1]-[P2] (MCC ch. 6)
def prop_efficiency(T, V, rho, D, profile=0.90, cap=0.86):
    A = np.pi * D**2 / 4
    eta_i = 2 / (1 + np.sqrt(1 + 2 * T / (rho * V**2 * A)))
    return np.minimum(eta_i * profile, cap)


def static_thrust(P_shaft, D, rho, fm=0.70):
    """Static thrust of a propeller from momentum theory with a figure of merit (RA01 ch. 2)."""
    A = np.pi * D**2 / 4
    return (fm * P_shaft) ** (2 / 3) * (2 * rho * A) ** (1 / 3)


# ---------------------------------------------------------------- drag [D1]-[D9] (AE01 Raymer ch. 12, AE04 Hoerner)
def cf_mixed(Re, M, lam):
    cf_l = 1.328 / np.sqrt(Re)
    cf_t = 0.455 / (np.log10(Re) ** 2.58 * (1 + 0.144 * M**2) ** 0.65)
    return lam * cf_l + (1 - lam) * cf_t


def ff_wing(tc, xc, M):
    return (1 + 0.6 / xc * tc + 100 * tc**4) * (1.34 * M**0.18)


def ff_body(f):
    return 1 + 60 / f**3 + f / 400


def oswald_raymer(AR):
    """[I2] Raymer 12.48, straight wing."""
    return 1.78 * (1 - 0.045 * AR**0.68) - 0.64


def helmbold(AR, eta=0.95):
    """[L2] finite-wing lift slope per rad."""
    return 2 * np.pi * AR / (2 + np.sqrt(4 + AR**2 / eta**2))


def superellipse_perimeter(w, h, e=2.5, n=64):
    t = np.linspace(0, 2 * np.pi, n + 1)
    c, s = np.cos(t), np.sin(t)
    y = 0.5 * np.multiply.outer(w, np.sign(c) * np.abs(c) ** (2 / e))
    z = 0.5 * np.multiply.outer(h, np.sign(s) * np.abs(s) ** (2 / e))
    return np.sum(np.hypot(np.diff(y, axis=-1), np.diff(z, axis=-1)), axis=-1)


# ---------------------------------------------------------------- masses (AE01 Raymer ch. 15, GA equations, lb/ft)
def raymer_wing_kg(S, AR, q, taper, tc, Nz, W_kg, tf=1.0):
    """[M1] Raymer 15.46, W_fw = 1 lb (electric)."""
    S_ft2, q_psf, Wdg = S / FT**2, q * 0.020885, W_kg / LB
    return tf * 0.036 * S_ft2**0.758 * AR**0.6 * q_psf**0.006 * taper**0.04 * (100 * tc) ** -0.3 * (Nz * Wdg) ** 0.49 * LB


def raymer_htail_kg(S, AR, q, tc, Nz, W_kg, tf=1.0):
    return tf * 0.016 * (Nz * W_kg / LB) ** 0.414 * (q * 0.020885) ** 0.168 * (S / FT**2) ** 0.896 * (100 * tc) ** -0.12 * AR**0.043 * LB


def raymer_vtail_kg(S, AR, q, tc, Nz, W_kg, tf=1.0):
    return tf * 0.073 * (Nz * W_kg / LB) ** 0.376 * (q * 0.020885) ** 0.122 * (S / FT**2) ** 0.873 * (100 * tc) ** -0.49 * AR**0.357 * LB


def raymer_fuselage_kg(Swet, Nz, W_kg, Lt, L_over_D, q, tf=1.0):
    return tf * 0.052 * (Swet / FT**2) ** 1.086 * (Nz * W_kg / LB) ** 0.177 * (Lt / FT) ** -0.051 * L_over_D**-0.072 * \
        (q * 0.020885) ** 0.241 * LB


def avionics_installed_kg(w_uninst):
    """[M12] Raymer 15.57."""
    return 2.117 * (w_uninst / LB) ** 0.933 * LB


# ---------------------------------------------------------------- loads [L3] (CS-23.341, ST09)
def gust_load_factor(WS, rho0, rho, mac, a, V_eas, Ude=15.24):
    mu_g = 2 * WS / (rho * mac * a * G0)
    Kg = 0.88 * mu_g / (5.3 + mu_g)
    return 1 + Kg * rho0 * Ude * V_eas * a / (2 * WS)


# ---------------------------------------------------------------- cost: Eastlake as given by Gudmundsson (AE02 ch. 2)
def eastlake_recurring_per_unit(W_airframe_kg, VH_kt, N=10, f_comp=0.8, f_cert=0.5, cpi=1.40, rate_mfg=55.0):
    """Recurring airframe cost per aircraft (manufacturing labour + materials + QC) [C1]-[C8], WP M adaptation:
    hours x 2026 burdened rate, regression cost terms escalated from 2012 USD by CPI 1.40 (estimate)."""
    W = W_airframe_kg / LB
    h_mfg = 9.6613 * W**0.74 * VH_kt**0.543 * N**0.524 * f_cert * (1 + 0.25 * f_comp)
    c_mfg = h_mfg * rate_mfg
    c_mat = 24.896 * W**0.689 * VH_kt**0.624 * N**0.792 * cpi * f_cert
    c_qc = 0.13 * c_mfg * f_cert * (1 + 0.5 * f_comp)
    return (c_mfg + c_mat + c_qc) / N, h_mfg / N


def eastlake_nonrecurring(W_airframe_kg, VH_kt, N=10, f_comp=0.8, f_cert=0.5, cpi=1.40, rates=(95.0, 65.0)):
    W = W_airframe_kg / LB
    Q = max(N / 60.0, 1.0)
    h_eng = 0.0396 * W**0.791 * VH_kt**1.526 * N**0.183 * f_cert * (1 + f_comp)
    h_tool = 1.0032 * W**0.764 * VH_kt**0.899 * N**0.178 * Q**0.066 * (1 + f_comp)
    dev = 0.06458 * W**0.873 * VH_kt**1.89 * 2**0.346 * cpi * f_cert * (1 + 0.5 * f_comp)
    ft = 0.009646 * W**1.16 * VH_kt**1.3718 * 2**1.281 * cpi * f_cert
    return h_eng * rates[0] + h_tool * rates[1] + dev + ft
