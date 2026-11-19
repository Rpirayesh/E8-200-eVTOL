#!/usr/bin/env python3
"""E8-200 independent design checker (work package M).

Recomputes the main conceptual-design quantities of a lift + cruise eVTOL with the equations of
methods/EQUATIONS.md (equation tags such as [A1], [H3] refer to that file) and compares them with
the values reported by the sizing work package in design/selected_design.json.

This is deliberately an independent implementation: it does not import anything from sizing/.

    ~/tools/cadenv/bin/python methods/check_design.py                       # design/selected_design.json
    ~/tools/cadenv/bin/python methods/check_design.py path/to/design.json [--geometry geometry.json]
                                                     [--out validation/methods] [--tag name]

Writes <out>/check_report<_tag>.json and .md and prints a PASS/WARN/FAIL table.
Input schema: methods/design_schema.md.  Dependencies: python 3.9+, numpy (scipy optional, for the
rotor-out thrust allocation; a closed-form fallback is used without it).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G0 = 9.80665
LB = 0.45359237           # kg per lb
FT = 0.3048               # m per ft
HP = 745.699872           # W per hp
KT = 0.514444             # m/s per knot
R_AIR = 287.053
GAMMA = 1.4

# --------------------------------------------------------------------------------------------
# Defaults (assumptions; every one is listed in EQUATIONS.md section 0 and can be overridden by
# an "assumptions" block in the input file).
# --------------------------------------------------------------------------------------------
DEFAULTS = dict(
    kappa_induced=1.20,          # [H2] induced-power factor (tip loss, non-uniform inflow, fixed-pitch rotor)
    cd0_blade=0.015,             # [H2] mean blade profile drag coefficient (low-Re composite blade at CT/sigma ~0.11)
    coax_factor=1.0,             # [H4] coaxial pair induced power vs one disk at pair thrust (upper bound)
    download_fraction=0.03,      # [H1] wing/boom download in hover, fraction of weight
    control_thrust_margin=0.10,  # [H6] thrust margin for control on the most loaded rotor in rotor-out
    eta_motor=0.93, eta_inverter=0.97, eta_wiring=0.98,
    eta_battery=0.95,            # [E6] discharge (I^2 R) efficiency, terminal / chemical
    aux_power_kw=1.5,
    battery_eol_fraction=0.80,   # requirement: cells at end-of-life capacity
    reserve_fraction=0.20,       # requirement: 20 % energy remaining at landing
    c_rate_margin=0.3,           # requirement "0.3 C margin": demanded C-rate <= cell rating - 0.3 C
    pack_overhead_fraction=0.30, # [B2] non-cell mass fraction of the pack (NASA 2018 uses 0.30)
    laminar_fraction_wing=0.10, laminar_fraction_body=0.05,
    excrescence_factor=1.10,     # [D9] leakage, protuberance, interference not otherwise counted
    cl_max_default=1.4,
    prop_profile_factor=0.90,    # [P2] propeller efficiency / ideal (actuator-disc) efficiency
    eta_prop_cap=0.86,
    climb_rate_ms=2.5, cruise_alt_m=500.0, takeoff_alt_m=0.0,
    gust_ude_ms=15.24,           # [L3] CS-23/14 CFR 23.333 derived gust velocity at VC (50 ft/s)
    transition_power_rule="mean", # [T1] mean of hover and cruise electrical power
    tech_factor_structure=1.0,   # Raymer GA regressions, wet lay-up composite: no reduction applied
    tech_factor_rotor=1.0,
    flap_frequency=1.10,         # [M9] hingeless rotor flap frequency per rev for AFDD00
    # [M15] ballistic parachute systems (rated MTOW kg, system kg): Galaxy GRS 6 600 SD, 750 SDS, 800-990/1050 SDS;
    # Magnum 601 SP, 901 SP (manufacturer/dealer data, see EQUATIONS.md M15 and bom/catalog.json)
    parachute_points=[[600.0, 12.3], [750.0, 14.8], [1050.0, 21.7], [757.0, 12.4], [950.0, 17.6]],
    cfrp_allowable_mpa=300.0, cfrp_density=1550.0, boom_fitting_factor=1.6,
    copper_density=8960.0, hv_current_density_a_mm2=5.0, harness_overhead=1.4,
    seat_mass_kg=8.0,            # per seat incl. 4-point harness (estimated, replace with catalog)
    accessory_factor=0.63,       # [M16] NASA motor technology factor 1.63 (inverter, cooling, connectors, wiring)
    lv_electrical_kg=None,       # [M13] override of the Raymer GA electrical-system estimate (kg)
)

# Tolerances: (warn, fail) as relative difference |M - D| / |D|, or absolute where noted.
TOL = dict(
    mass=(0.10, 0.20), mass_component=(0.25, 0.50), power=(0.10, 0.20), drag=(0.15, 0.30),
    energy=(0.10, 0.20), range=(0.10, 0.20), speed=(0.03, 0.08), mach=(0.03, 0.08),
    c_rate=(0.10, 0.20), geometry=(0.01, 0.05), cost=(0.30, 0.60),
)


# ============================================================================================
# Atmosphere [A1]-[A3]
# ============================================================================================
def isa(h_m: float, dT: float = 0.0) -> dict:
    """ISA troposphere with a temperature offset (pressure from the standard day, ICAO Doc 7488)."""
    T_std = 288.15 - 0.0065 * h_m
    p = 101325.0 * (T_std / 288.15) ** 5.25588
    T = T_std + dT
    rho = p / (R_AIR * T)
    return dict(T=T, p=p, rho=rho, a=math.sqrt(GAMMA * R_AIR * T), mu=1.458e-6 * T**1.5 / (T + 110.4))


# ============================================================================================
# Rotor / hover [H1]-[H7]
# ============================================================================================
def hover_rotor(T_N: float, D: float, rho: float, vtip: float | None, sigma: float | None,
                kappa: float, cd0: float, fm_given: float | None = None, area_factor: float = 1.0,
                coax_factor: float = 1.0) -> dict:
    """Shaft power of one rotor (or one coaxial pair if area_factor=1 and T is the pair thrust)."""
    A = math.pi * D**2 / 4 * area_factor
    vh = math.sqrt(T_N / (2 * rho * A))
    p_ideal = T_N * vh * coax_factor                                   # [H1]
    if vtip and sigma:
        p_prof = sigma * cd0 * rho * A * vtip**3 / 8                    # [H2]
        p_bemt = kappa * p_ideal + p_prof
        fm_est = p_ideal / p_bemt
    else:
        p_bemt, fm_est = None, None
    fm_used = fm_est if fm_est is not None else (fm_given or 0.70)
    p = p_ideal / fm_used
    out = dict(T_N=T_N, area_m2=A, vh_ms=vh, p_ideal_kw=p_ideal / 1e3, fm_estimate=fm_est,
               fm_used=fm_used, p_shaft_kw=p / 1e3)
    if fm_given:
        out["p_shaft_with_D_fm_kw"] = p_ideal / fm_given / 1e3
    if vtip and sigma:
        out["ct_sigma"] = T_N / (rho * A * vtip**2) / sigma            # [H5]
    return out


def rotor_out_allocation(pos_xy: np.ndarray, spin: np.ndarray, W: float, k_qt: float, failed: int):
    """Minimise the largest rotor thrust with one rotor failed; trim Fz, roll, pitch, yaw [H6].

    pos_xy relative to the CG (x aft, y right).  Returns (max thrust, thrusts) or None if infeasible.
    """
    n = len(pos_xy)
    idx = [i for i in range(n) if i != failed]
    try:
        from scipy.optimize import linprog
    except ImportError:  # pragma: no cover - closed-form fallback (shut down the opposite rotor)
        return None
    m = len(idx)
    c = np.zeros(m + 1)
    c[-1] = 1.0
    Aeq = np.zeros((4, m + 1))
    for j, i in enumerate(idx):
        Aeq[:, j] = [1.0, pos_xy[i, 1], pos_xy[i, 0], spin[i] * k_qt]
    Aub = np.hstack([np.eye(m), -np.ones((m, 1))])
    sol = linprog(c, A_ub=Aub, b_ub=np.zeros(m), A_eq=Aeq, b_eq=[W, 0, 0, 0],
                  bounds=[(0, None)] * (m + 1), method="highs")
    if not sol.success:
        return None
    return float(sol.x[-1]), sol.x[:-1]


# ============================================================================================
# Drag [D1]-[D10], induced drag [I1]-[I2], propeller [P1]-[P2]
# ============================================================================================
def cf_mixed(Re: float, M: float, lam: float) -> float:
    cf_lam = 1.328 / math.sqrt(Re)                                            # [D1]
    cf_turb = 0.455 / (math.log10(Re) ** 2.58 * (1 + 0.144 * M**2) ** 0.65)   # [D2]
    return lam * cf_lam + (1 - lam) * cf_turb


def ff_wing(tc: float, xc_m: float, M: float, sweep_deg: float) -> float:
    return (1 + 0.6 / xc_m * tc + 100 * tc**4) * (1.34 * M**0.18 * math.cos(math.radians(sweep_deg)) ** 0.28)  # [D3]


def ff_body(fineness: float) -> float:
    return 1 + 60 / fineness**3 + fineness / 400                                # [D4]


def oswald_raymer(AR: float) -> float:
    return 1.78 * (1 - 0.045 * AR**0.68) - 0.64                               # [I2]


def prop_efficiency(T: float, V: float, rho: float, D: float, profile: float, cap: float) -> float:
    A = math.pi * D**2 / 4
    eta_i = 2 / (1 + math.sqrt(1 + 2 * T / (rho * V**2 * A)))                  # [P1]
    return min(eta_i * profile, cap)                                          # [P2]


def drag_buildup(d: dict, V: float, atm: dict, a: dict) -> dict:
    """Zero-lift drag area D/q (m^2) by components [D5]-[D9]."""
    rho, mu = atm["rho"], atm["mu"]
    M = V / atm["a"]
    w = d["wing"]
    comp = {}
    S, b = w["area_m2"], w["span_m"]
    mac = w.get("mac_m", S / b)
    tc = w.get("thickness_ratio", 0.15)
    s_exp = S - w.get("fuselage_width_at_wing_m", d["fuselage"].get("max_width_m", 1.0)) * mac
    swet_w = s_exp * (1.977 + 0.52 * tc)                                      # [D5]
    comp["wing"] = cf_mixed(rho * V * mac / mu, M, a["laminar_fraction_wing"]) * \
        ff_wing(tc, w.get("max_thickness_x_c", 0.30), M, w.get("sweep_deg", 0.0)) * w.get("interference_Q", 1.0) * swet_w
    f = d["fuselage"]
    L = f["length_m"]
    deq = math.sqrt(f["max_width_m"] * f["max_height_m"])
    swet_f = f.get("wetted_area_m2") or 0.80 * math.pi * deq * L              # [D6] fallback
    comp["fuselage"] = cf_mixed(rho * V * L / mu, M, a["laminar_fraction_body"]) * ff_body(L / deq) * \
        f.get("interference_Q", 1.0) * swet_f
    bo = d.get("booms") or {}
    if bo:
        Lb, db = bo["length_m"], bo["diameter_m"]
        swet_b = math.pi * db * Lb * 0.95
        comp["booms"] = bo.get("count", 2) * cf_mixed(rho * V * Lb / mu, M, a["laminar_fraction_body"]) * \
            ff_body(Lb / db) * bo.get("interference_Q", 1.1) * swet_b
    t = d.get("tail") or {}
    for key, name in (("horizontal_area_m2", "tail_h"), ("vertical_area_m2", "tail_v")):
        if t.get(key):
            ct = t.get("mac_m", 0.6)
            comp[name] = cf_mixed(rho * V * ct / mu, M, a["laminar_fraction_wing"]) * \
                ff_wing(t.get("thickness_ratio", 0.10), 0.30, M, 0.0) * 1.04 * t[key] * (1.977 + 0.52 * 0.10)
    lr = d["lift_rotors"]
    n_rot = lr["count"]
    per_rotor = lr.get("stopped_drag_area_m2_each")
    if per_rotor is None:                                                     # [D7]
        md, mh = lr.get("motor_diameter_m", 0.25), lr.get("motor_exposed_height_m", 0.08)
        pylon = lr.get("pylon_frontal_area_m2", 0.012)
        Rr = lr["diameter_m"] / 2
        c_bl = lr.get("blade_chord_m", 0.08 * Rr)
        blades = lr.get("blades", 2) * cf_mixed(rho * V * c_bl / mu, M, 0.1) * 1.3 * 2 * Rr * c_bl * 0.9
        per_rotor = 0.80 * md * mh + 0.30 * pylon + blades + lr.get("parked_misalignment_cd_area_m2", 0.0)
    comp["stopped_lift_rotors"] = n_rot * per_rotor
    lg = d.get("landing_gear") or {}
    comp["landing_gear"] = lg.get("drag_area_m2", 1.0 * lg.get("frontal_area_m2", 0.04))     # [D8]
    comp["other_listed"] = sum((d.get("drag") or {}).get("extra_items_m2", {}).values())
    base = sum(comp.values())
    comp["excrescence_interference"] = base * (a["excrescence_factor"] - 1)  # [D9]
    comp["total"] = base * a["excrescence_factor"]
    comp["swet_wing_m2"] = swet_w
    comp["swet_fuselage_m2"] = swet_f
    return comp


# ============================================================================================
# Masses [M1]-[M20]  (Raymer GA equations in lb/ft units, wrapped to SI)
# ============================================================================================
def raymer_wing_lb(S_ft2, Wfw_lb, AR, sweep_deg, q_psf, taper, tc, Nz, Wdg_lb):
    cl = math.cos(math.radians(sweep_deg))
    return 0.036 * S_ft2**0.758 * max(Wfw_lb, 1.0) ** 0.0035 * (AR / cl**2) ** 0.6 * q_psf**0.006 * \
        taper**0.04 * (100 * tc / cl) ** -0.3 * (Nz * Wdg_lb) ** 0.49                   # [M1]


def afdd93_wing_lb(S_ft2, AR, sweep_deg, taper, tc, Nz, Wsd_lb):
    return 5.66411 * (Wsd_lb / (1000 * math.cos(math.radians(sweep_deg)))) ** 0.847 * Nz**0.39579 * \
        S_ft2**0.21754 * AR**0.50016 * ((1 + taper) / tc) ** 0.09359                   # [M2]


def raymer_htail_lb(Nz, Wdg, q, S, tc, AR, taper=1.0, sweep=0.0):
    cl = math.cos(math.radians(sweep))
    return 0.016 * (Nz * Wdg) ** 0.414 * q**0.168 * S**0.896 * (100 * tc / cl) ** -0.12 * \
        (AR / cl**2) ** 0.043 * taper**-0.02                                             # [M3]


def raymer_vtail_lb(Nz, Wdg, q, S, tc, AR, taper=1.0, sweep=0.0, Ht_Hv=0.0):
    cl = math.cos(math.radians(sweep))
    return 0.073 * (1 + 0.2 * Ht_Hv) * (Nz * Wdg) ** 0.376 * q**0.122 * S**0.873 * \
        (100 * tc / cl) ** -0.49 * (AR / cl**2) ** 0.357 * taper**0.039                 # [M4]


def raymer_fuselage_lb(Swet_ft2, Nz, Wdg, Lt_ft, L_over_D, q):
    return 0.052 * Swet_ft2**1.086 * (Nz * Wdg) ** 0.177 * Lt_ft**-0.051 * L_over_D**-0.072 * q**0.241  # [M5]


def raymer_main_gear_lb(Nl, Wl, Lm_in):
    return 0.095 * (Nl * Wl) ** 0.768 * (Lm_in / 12) ** 0.409                          # [M6]


def raymer_flight_controls_lb(L_ft, b_ft, Nz, Wdg):
    return 0.053 * L_ft**1.536 * b_ft**0.371 * (Nz * Wdg * 1e-4) ** 0.80                # [M7]


def motor_mass_kg(torque_nm: float) -> float:
    """Johnson & Silva / NDARC motor regression W = 0.3928 Q^0.8587 (lb, ft-lb) [M8]."""
    return 0.3928 * (torque_nm / 1.3558179) ** 0.8587 * LB


def afdd00_rotor_kg(R_m, c_m, vtip, n_blades, nu, chi=1.0):
    """AFDD00 blade + hub (hub from blade-weight equation), one rotor, NDARC TP-2009-215402 ch. 19 [M9]."""
    R, c, V = R_m / FT, c_m / FT, vtip / FT
    wb = 0.0024419 * 1.0 * n_blades**0.53479 * R**1.74231 * c**0.77291 * V**0.87562 * nu**2.51048
    wh = 0.0061182 * n_blades**0.20373 * R**0.60406 * V**0.52803 * nu**1.00218 * wb**0.87127
    return chi * wb * LB, chi * wh * LB


def boom_mass_kg(d: dict, T_rotor_max: float, a: dict) -> dict:
    """Physics-based boom estimate [M10]: CFRP tube sized for ultimate bending from rotor thrust."""
    bo = d.get("booms") or {}
    if not bo:
        return dict(kg=0.0)
    D = bo["diameter_m"]
    arms = bo.get("rotor_arms_m") or [bo["length_m"] / 4] * 2
    M_ult = 1.5 * T_rotor_max * max(arms) * (2 if len(arms) > 2 else 1)  # two rotors on the longest arm side
    sigma = a["cfrp_allowable_mpa"] * 1e6
    t = max(M_ult / (math.pi * (D / 2) ** 2 * sigma), bo.get("min_wall_m", 0.0015))
    m_tube = a["cfrp_density"] * math.pi * D * t * bo["length_m"]
    m = bo.get("count", 2) * m_tube * a["boom_fitting_factor"]
    return dict(kg=m, wall_m=t, M_ult_Nm=M_ult)


def parachute_kg(mtow: float, pts) -> float:
    x, y = np.array(pts, float).T
    k1, k0 = np.polyfit(x, y, 1)                                                      # [M15] least-squares line
    return float(k0 + k1 * mtow)


def harness_kg(P_peak_w: float, V_bus: float, length_m: float, a: dict) -> float:
    I = P_peak_w / V_bus
    area_m2 = I / a["hv_current_density_a_mm2"] * 1e-6
    return 2 * length_m * area_m2 * a["copper_density"] * a["harness_overhead"]       # [M14]


# ============================================================================================
# Loads [L1]-[L3] and cost [C1]-[C9]
# ============================================================================================
def lift_slope(AR: float, sweep_deg: float = 0.0, eta: float = 0.95) -> float:
    t = math.tan(math.radians(sweep_deg))
    return 2 * math.pi * AR / (2 + math.sqrt(4 + AR**2 / eta**2 * (1 + t**2)))       # [L2]


def gust_load_factor(WS: float, rho0: float, rho: float, mac: float, a: float, V_eas: float, Ude: float) -> float:
    mu_g = 2 * WS / (rho * mac * a * G0)
    Kg = 0.88 * mu_g / (5.3 + mu_g)
    return 1 + Kg * rho0 * Ude * V_eas * a / (2 * WS)                                  # [L3]


def eastlake_cost(W_airframe_kg: float, VH_kts: float, N: int, cpi: float, f_comp: float, rates: dict,
                  f_cert: float = 1.0) -> dict:
    """Eastlake labour-hour model as given by Gudmundsson (2014) sec. 2.2 [C1]-[C8], adapted:
    hours from the Eastlake regressions; labour cost = hours x our 2026 burdened rates (no extra
    rate-escalation factor); materials, development support and flight test from the Eastlake
    cost regressions escalated by `cpi` (2012 -> 2026)."""
    W = W_airframe_kg / LB
    Q = max(N / 60.0, 1.0)  # production rate per month over a 5-year run
    h_eng = 0.0396 * W**0.791 * VH_kts**1.526 * N**0.183 * f_cert * (1 + f_comp)
    h_tool = 1.0032 * W**0.764 * VH_kts**0.899 * N**0.178 * Q**0.066 * (1 + f_comp)
    h_mfg = 9.6613 * W**0.74 * VH_kts**0.543 * N**0.524 * f_cert * (1 + 0.25 * f_comp)
    c = dict(
        engineering=h_eng * rates["engineering"],
        development_support=0.06458 * W**0.873 * VH_kts**1.89 * 2**0.346 * cpi * f_cert * (1 + 0.5 * f_comp),
        flight_test=0.009646 * W**1.16 * VH_kts**1.3718 * 2**1.281 * cpi * f_cert,
        tooling=h_tool * rates["tooling"],
        manufacturing=h_mfg * rates["manufacturing"],
        materials=24.896 * W**0.689 * VH_kts**0.624 * N**0.792 * cpi * f_cert,
    )
    c["quality_control"] = 0.13 * c["manufacturing"] * f_cert * (1 + 0.5 * f_comp)
    total = sum(c.values())
    recurring = c["manufacturing"] + c["materials"] + c["quality_control"]
    return dict(items=c, total=total, per_unit_total=total / N, per_unit_recurring=recurring / N,
                hours=dict(eng=h_eng, tool=h_tool, mfg=h_mfg, mfg_per_unit=h_mfg / N))


# ============================================================================================
# The checker
# ============================================================================================
def _get(d, path, default=None):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


class Checker:
    def __init__(self, design: dict, geometry: dict | None = None):
        self.d = design
        self.g = geometry or {}
        self.a = dict(DEFAULTS)
        self.a.update(design.get("assumptions_for_checker", {}))
        self.rows: list[dict] = []
        self.calc: dict = {}
        self.notes: list[str] = []

    # ------------------------------------------------------------------ comparison helper
    def cmp(self, name, m_val, d_val, kind, unit="", eq="", lower_is_ok=False, note=""):
        warn, fail = TOL[kind]
        row = dict(quantity=name, unit=unit, M=m_val, D=d_val, eq=eq, tol=f"±{warn:.0%} warn / ±{fail:.0%} fail", note=note)
        if d_val is None or m_val is None:
            row.update(diff=None, status="INFO" if d_val is None else "MISSING")
        else:
            diff = (m_val - d_val) / abs(d_val) if d_val else float("inf")
            row["diff"] = diff
            mag = abs(diff)
            if lower_is_ok and diff < 0:
                mag = 0.0
            row["status"] = "PASS" if mag <= warn else ("WARN" if mag <= fail else "FAIL")
        self.rows.append(row)
        return row

    def limit(self, name, value, limit, unit="", sense="<=", warn_band=0.0, eq="", note=""):
        ok = value <= limit if sense == "<=" else value >= limit
        near = (value <= limit * (1 + warn_band) if sense == "<=" else value >= limit * (1 - warn_band))
        status = "PASS" if ok else ("WARN" if near else "FAIL")
        self.rows.append(dict(quantity=name, unit=unit, M=value, D=None, eq=eq, tol=f"{sense} {limit:g}",
                              diff=None, status=status, note=note))

    # ------------------------------------------------------------------ main
    def run(self) -> dict:
        d, a = self.d, self.a
        rep = d.get("results", {})
        m = d["mass_kg"]
        mtow = m["mtow"]
        W = mtow * G0
        env = d.get("environment", {})
        dT = env.get("hover_isa_offset_C", 15.0)
        h_site = env.get("hover_design_altitude_m", 500.0)
        h_ceiling = env.get("hover_ceiling_m", 1000.0)
        h_cr = env.get("cruise_altitude_m", a["cruise_alt_m"])
        atm_h = isa(h_site, dT)
        atm_c = isa(h_ceiling, dT)
        atm_cr = isa(h_cr, env.get("cruise_isa_offset_C", dT))
        atm_sl = isa(0.0, 0.0)
        eta_drive = a["eta_motor"] * a["eta_inverter"] * a["eta_wiring"]
        eff = d.get("efficiencies", {})
        eta_drive_D = eff.get("motor", a["eta_motor"]) * eff.get("inverter", a["eta_inverter"]) * eff.get("wiring", a["eta_wiring"])
        self.calc["eta_drive_M"] = eta_drive
        self.calc["eta_drive_D"] = eta_drive_D
        if abs(eta_drive_D - eta_drive) > 0.03:
            self.notes.append(f"Drive-train efficiency differs: D {eta_drive_D:.3f} vs M default {eta_drive:.3f}; M uses its own value.")
        aux = d.get("aux_power_kw", a["aux_power_kw"])

        # ---------------- geometry consistency
        w = d["wing"]
        AR = w["span_m"] ** 2 / w["area_m2"]
        self.calc["aspect_ratio"] = AR
        gw = self.g.get("wing") or {}
        if gw.get("span_m"):
            self.cmp("wing span: geometry.json vs selected_design", gw["span_m"], w["span_m"], "geometry", "m", "-")
        if gw.get("root_chord_m") and gw.get("tip_chord_m"):
            S_g = gw["span_m"] * (gw["root_chord_m"] + gw["tip_chord_m"]) / 2
            self.cmp("wing area from geometry.json chords", S_g, w["area_m2"], "geometry", "m^2", "trapezoid")
        mass_sum = m.get("empty", 0) + m.get("payload", 0) + m.get("battery", 0)
        self.cmp("MTOW = empty (excl. battery) + battery + payload", mass_sum, mtow, "geometry", "kg", "[M0]",
                 note="bookkeeping closure of D's own numbers")
        lim = d.get("limits", {})
        span_max = lim.get("footprint_max_m", 9.0)
        length = d["fuselage"]["length_m"]
        if d.get("booms"):
            length = max(length, d["booms"]["length_m"])
        xs = [r["hub"][0] for r in (self.g.get("lift_rotors") or []) if isinstance(r, dict)]
        if xs:
            length = max(length, max(xs) - min(xs) + d["lift_rotors"]["diameter_m"])
        self.calc["overall_length_m"] = length
        self.limit("wing span <= footprint limit", w["span_m"], span_max, "m", eq="req.")
        self.limit("overall length incl. booms and rotor discs <= footprint limit", length, span_max, "m", eq="req.")

        # ---------------- hover
        lr = d["lift_rotors"]
        n = lr["count"]
        coax = bool(lr.get("coaxial", False))
        Dr = lr["diameter_m"]
        vtip = lr.get("tip_speed_hover_ms")
        nb = lr.get("blades", 2)
        sigma = lr.get("solidity") or (nb * lr["blade_chord_m"] / (math.pi * Dr / 2) if lr.get("blade_chord_m") else None)
        dl_frac = lr.get("download_fraction", a["download_fraction"])
        n_disks = n // 2 if coax else n
        T_disk = W * (1 + dl_frac) / n_disks
        A_total = n_disks * math.pi * Dr**2 / 4
        DL = W / A_total
        self.calc["disk_loading_N_m2"] = DL
        self.cmp("disk loading", DL, rep.get("disk_loading_N_m2"), "geometry", "N/m^2", "[H0]")
        hov = {}
        for tag, atm in (("site", atm_h), ("ceiling", atm_c), ("sea_level_isa", atm_sl)):
            if coax:
                # each blade row carries half of the pair thrust; solidity per row
                r = hover_rotor(T_disk, Dr, atm["rho"], vtip, 2 * sigma if sigma else None, a["kappa_induced"],
                                a["cd0_blade"], lr.get("figure_of_merit"), coax_factor=a["coax_factor"])
            else:
                r = hover_rotor(T_disk, Dr, atm["rho"], vtip, sigma, a["kappa_induced"], a["cd0_blade"],
                                lr.get("figure_of_merit"))
            r["p_shaft_total_kw"] = r["p_shaft_kw"] * n_disks
            r["p_elec_total_kw"] = r["p_shaft_total_kw"] / eta_drive + aux
            r["p_shaft_per_motor_kw"] = r["p_shaft_total_kw"] / n
            hov[tag] = r
        self.calc["hover"] = hov
        hs = hov["site"]
        self.cmp("figure of merit (M: blade-element estimate)", hs["fm_used"], lr.get("figure_of_merit"), "power", "-", "[H2]-[H3]")
        self.cmp("hover shaft power per motor, site (500 m ISA+15)", hs["p_shaft_per_motor_kw"],
                 rep.get("hover_shaft_power_per_motor_kw"), "power", "kW", "[H1]-[H3]")
        self.cmp("hover electrical power total, site", hs["p_elec_total_kw"], rep.get("hover_electrical_power_kw"),
                 "power", "kW", "[H1]-[H3],[E1]")
        self.cmp("hover electrical power total, 1000 m ISA+15 ceiling", hov["ceiling"]["p_elec_total_kw"],
                 rep.get("hover_electrical_power_ceiling_kw"), "power", "kW", "[H1]-[H3],[E1]")
        mot = lr.get("motor", {})
        if mot.get("continuous_power_kw"):
            self.limit("hover shaft power per motor at 1000 m ISA+15 <= motor continuous", hov["ceiling"]["p_shaft_per_motor_kw"],
                       mot["continuous_power_kw"], "kW", warn_band=0.10, eq="[H1]")
        if vtip:
            mt = vtip / atm_h["a"]
            self.calc["tip_mach_hover"] = mt
            self.cmp("lift-rotor hover tip Mach (ISA+15)", mt, rep.get("tip_mach_hover"), "mach", "-", "[H7]")
            self.limit("lift-rotor tip Mach (noise screen)", mt, 0.55, "-", warn_band=0.10, eq="[H7]",
                       note="NASA UAM concepts use 550-600 ft/s (Mtip ~0.49-0.54)")
            if "ct_sigma" in hs:
                self.limit("hover blade loading CT/sigma (stall margin for transition)", hs["ct_sigma"], 0.14, "-",
                           warn_band=0.10, eq="[H5]")

        # ---------------- rotor out
        omega = vtip / (Dr / 2) if vtip else None
        k_qt = (hs["p_shaft_kw"] * 1e3 / omega) / T_disk if omega else 0.05
        rotors = self.g.get("lift_rotors") or lr.get("positions")
        cg = self.g.get("cg_mtow_m") or d.get("cg_mtow_m")
        ro = None
        if rotors and cg and not coax and len(rotors) == n:
            pos = np.array([[r["hub"][0] - cg[0], r["hub"][1] - cg[1]] if isinstance(r, dict) else
                            [r[0] - cg[0], r[1] - cg[1]] for r in rotors])
            spin = np.array([r.get("spin", 1) if isinstance(r, dict) else 1 for r in rotors], float)
            res = []
            for f in range(n):
                sol = rotor_out_allocation(pos, spin, W * (1 + dl_frac), k_qt, f)
                res.append(sol[0] if sol else float("nan"))
            Tmax = float(np.nanmax(res))
            if all(math.isnan(x) for x in res):
                Tmax = None
            ro = dict(method="LP min-max thrust, 4 trim equations", T_max_N=Tmax, per_case_T_N=res)
        if not ro or ro.get("T_max_N") is None:
            # closed form [H6]: the opposite rotor (row) is shut down, n/(n-2) thrust on the rest.
            # For coaxial pairs the count n is the number of rows; the failed pair keeps one row.
            Tmax = W * (1 + dl_frac) / (n - 2) if n > 4 else None
            ro = dict(method="opposite-rotor/row shutdown (n/(n-2))", T_max_N=Tmax)
        if ro["T_max_N"] is None:
            self.rows.append(dict(quantity="rotor-out: 4 lift rotors cannot trim with one rotor failed", unit="", M=None, D=None,
                                  eq="[H6]", tol="n>=6 rows", diff=None, status="FAIL", note="use >= 6 rotors or coaxial pairs"))
        else:
            T_ctrl = ro["T_max_N"] * (1 + a["control_thrust_margin"])
            atm = atm_h
            T_row_hover = T_disk / 2 if coax else T_disk
            if coax:
                # row power taken as half the pair power at twice the row thrust (pair solidity, coaxial factor)
                rp = hover_rotor(2 * T_ctrl, Dr, atm["rho"], vtip, 2 * sigma if sigma else None, a["kappa_induced"],
                                 a["cd0_blade"], coax_factor=a["coax_factor"])
                p_ro = rp["p_shaft_kw"] / 2
            else:
                p_ro = hover_rotor(T_ctrl, Dr, atm["rho"], vtip, sigma, a["kappa_induced"], a["cd0_blade"])["p_shaft_kw"]
            ro["p_shaft_most_loaded_kw"] = p_ro
            ro["thrust_ratio_to_hover"] = ro["T_max_N"] / T_row_hover
            self.calc["rotor_out"] = ro
            self.cmp("rotor-out shaft power, most loaded motor (incl. 10 % thrust control margin)", p_ro,
                     rep.get("rotor_out_max_shaft_power_kw"), "power", "kW", "[H6]")
            if mot.get("peak_power_kw"):
                self.limit("rotor-out power <= motor peak power", p_ro, mot["peak_power_kw"], "kW",
                           warn_band=0.05, eq="[H6] req.")
            if omega:
                # fixed pitch: thrust ~ rpm^2, so rpm rises with sqrt(T/T_hover)
                Q = p_ro * 1e3 / (omega * math.sqrt(T_ctrl / T_row_hover))
                ro["torque_most_loaded_nm"] = Q
            if mot.get("max_torque_nm") and omega:
                self.limit("rotor-out torque <= motor max torque", Q, mot["max_torque_nm"], "N m", warn_band=0.05, eq="[H6]")

        # ---------------- cruise
        mis = d["mission"]
        V = mis["cruise_speed_kmh"] / 3.6
        q = 0.5 * atm_cr["rho"] * V**2
        CL = W / (q * w["area_m2"])
        db = drag_buildup(d, V, atm_cr, a)
        e = w.get("oswald") or oswald_raymer(AR)
        e_M = oswald_raymer(AR)
        self.calc["oswald_M"] = e_M
        if w.get("oswald"):
            self.cmp("Oswald efficiency", e_M, w.get("oswald"), "drag", "-", "[I2]")
        CD0 = db["total"] / w["area_m2"]
        CDi = CL**2 / (math.pi * e_M * AR)
        D_N = q * w["area_m2"] * (CD0 + CDi)
        self.calc["cruise"] = dict(V_ms=V, q_Pa=q, CL=CL, CD0=CD0, CDi=CDi, drag_N=D_N, LD=W / D_N,
                                   drag_area_breakdown_m2=db)
        self.cmp("zero-lift drag area D/q", db["total"], _get(d, "drag.drag_area_m2"), "drag", "m^2", "[D1]-[D9]")
        self.cmp("cruise drag", D_N, rep.get("cruise_drag_N"), "drag", "N", "[I1]")
        self.cmp("cruise L/D", W / D_N, rep.get("cruise_LD"), "drag", "-", "[I1]")
        pu = d.get("pusher", {})
        eta_p = prop_efficiency(D_N, V, atm_cr["rho"], pu.get("diameter_m", 1.6), a["prop_profile_factor"], a["eta_prop_cap"])
        self.calc["cruise"]["eta_prop_M"] = eta_p
        self.cmp("pusher propulsive efficiency", eta_p, pu.get("eta_cruise"), "power", "-", "[P1]-[P2]")
        p_shaft_cr = D_N * V / eta_p
        p_el_cr = p_shaft_cr / eta_drive / 1e3 + aux
        self.calc["cruise"]["p_shaft_kw"] = p_shaft_cr / 1e3
        self.calc["cruise"]["p_elec_kw"] = p_el_cr
        self.cmp("cruise electrical power", p_el_cr, rep.get("cruise_electrical_power_kw"), "power", "kW", "[E1]")
        if pu.get("motor", {}).get("continuous_power_kw"):
            self.limit("cruise shaft power <= pusher motor continuous", p_shaft_cr / 1e3, pu["motor"]["continuous_power_kw"],
                       "kW", warn_band=0.05, eq="[E1]")
        if pu.get("diameter_m") and pu.get("rpm_cruise"):
            vt = math.pi * pu["diameter_m"] * pu["rpm_cruise"] / 60
            mh = math.sqrt(vt**2 + V**2) / atm_cr["a"]
            self.calc["pusher_helical_tip_mach"] = mh
            self.limit("pusher helical tip Mach in cruise", mh, 0.70, "-", warn_band=0.08, eq="[H7]")

        # ---------------- stall, speeds
        clmax = w.get("cl_max", a["cl_max_default"])
        vs = math.sqrt(2 * W / (atm_sl["rho"] * w["area_m2"] * clmax))
        vs_hot = math.sqrt(2 * W / (atm_cr["rho"] * w["area_m2"] * clmax))
        self.calc["stall_speed_ms"] = vs
        self.calc["stall_speed_tas_cruise_alt_ms"] = vs_hot
        self.cmp("stall speed (sea level ISA, MTOW)", vs, rep.get("stall_speed_ms"), "speed", "m/s", "[S1]")
        self.limit("cruise speed >= 1.3 x stall (TAS at cruise altitude)", V / vs_hot, 1.3, "-", sense=">=", warn_band=0.05, eq="[S2]")
        self.limit("cruise speed >= requirement", mis["cruise_speed_kmh"], d.get("requirements", {}).get("cruise_speed_kmh_min", 150),
                   "km/h", sense=">=", eq="req.")

        # ---------------- loads
        mac = w.get("mac_m", w["area_m2"] / w["span_m"])
        a_w = lift_slope(AR, w.get("sweep_deg", 0.0))
        WS = W / w["area_m2"]
        V_eas = V * math.sqrt(atm_cr["rho"] / atm_sl["rho"])
        n_g = gust_load_factor(WS, atm_sl["rho"], atm_cr["rho"], mac, a_w, V_eas, a["gust_ude_ms"])
        self.calc["gust_load_factor_Vc"] = n_g
        self.calc["wing_loading_N_m2"] = WS
        nlim = d.get("structure", {}).get("limit_load_factor_positive", 3.8)
        self.limit("gust load factor at VC (Ude 15.24 m/s) <= design limit", n_g, nlim, "g", warn_band=0.0, eq="[L3]")

        # ---------------- battery, mission
        bat = d["battery"]
        E_nom = bat["energy_nominal_kwh"]
        cell = bat.get("cell", {})
        if cell.get("energy_wh") and bat.get("series") and bat.get("parallel"):
            ncell = bat["series"] * bat["parallel"]
            E_cells = ncell * cell["energy_wh"] / 1e3
            self.cmp("nominal energy from cells (series x parallel x cell Wh)", E_cells, E_nom, "geometry", "kWh", "[B1]")
            m_cells = ncell * cell["mass_kg"]
            m_pack_M = m_cells / (1 - a["pack_overhead_fraction"])
            self.calc["battery_cells_kg"] = m_cells
            self.cmp("battery pack mass (cells / (1 - overhead))", m_pack_M, m.get("battery"), "mass", "kg", "[B2]",
                     note=f"overhead fraction {a['pack_overhead_fraction']:.2f}")
            V_nom = bat["series"] * cell.get("v_nom", 3.6)
            self.calc["pack_voltage_nominal_V"] = V_nom
            cap_ah = bat["parallel"] * cell.get("capacity_ah", cell["energy_wh"] / cell.get("v_nom", 3.6))
        else:
            V_nom = bat.get("voltage_nominal_v", 400.0)
            cap_ah = E_nom * 1e3 / V_nom
        E_eol = E_nom * a["battery_eol_fraction"]
        E_res = E_eol * a["reserve_fraction"]
        E_avail_term = (E_eol - E_res)                     # terminal-side energy above reserve [B3]
        eta_b = a["eta_battery"]
        t_to, t_ld = mis.get("hover_takeoff_s", 60), mis.get("hover_landing_s", 60)
        t_tr = mis.get("transition_each_s", 30)
        n_tr = mis.get("transitions", 2)
        Ph = hs["p_elec_total_kw"]
        h_vert = mis.get("vertical_climb_m", 30.0)
        E_hover = Ph * (t_to + t_ld) / 3600 + W * h_vert / (eta_drive * hs["fm_used"]) / 3.6e6 * 0.5  # [E2]
        Ptr = 0.5 * (Ph + p_el_cr) if a["transition_power_rule"] == "mean" else Ph
        E_tr = n_tr * Ptr * t_tr / 3600                                                           # [T1]
        dh = max(h_cr - mis.get("transition_altitude_m", 30.0), 0.0)
        E_climb = W * dh / (eta_p * eta_drive) / 3.6e6                                            # [E3]
        E_fixed = (E_hover + E_tr + E_climb) / eta_b
        R_km = mis["range_km"]
        E_cruise = p_el_cr * (R_km / (V * 3.6)) / eta_b                                            # [E4]
        E_mission = E_fixed + E_cruise
        E_req_nom = (E_mission * eta_b) / (a["battery_eol_fraction"] * (1 - a["reserve_fraction"]))
        rng = max((E_avail_term * eta_b - E_fixed * eta_b), 0) / p_el_cr * V * 3.6                 # [R1]
        mis_c = dict(E_nom_kwh=E_nom, E_eol_kwh=E_eol, E_reserve_kwh=E_res, E_hover_kwh=E_hover / eta_b,
                     E_transitions_kwh=E_tr / eta_b, E_climb_kwh=E_climb / eta_b, E_cruise_kwh=E_cruise,
                     E_mission_kwh=E_mission, E_nominal_required_kwh=E_req_nom, range_km=rng,
                     P_transition_kw=Ptr, eta_battery=eta_b)
        self.calc["mission"] = mis_c
        self.cmp("mission energy (design range, at battery terminals / eta_batt)", E_mission, rep.get("mission_energy_kwh"),
                 "energy", "kWh", "[E2]-[E4]")
        self.cmp("range to 20 % reserve at EOL capacity", rng, rep.get("range_km"), "range", "km", "[R1]")
        self.limit("range at EOL with 20 % reserve >= design range", rng, R_km, "km", sense=">=", warn_band=0.05, eq="[R1]")
        self.limit("nominal battery energy >= required (EOL, reserve)", E_nom, E_req_nom, "kWh", sense=">=", warn_band=0.05, eq="[B3]")
        # C-rates
        for tag, P in (("hover (site)", Ph), ("hover (ceiling)", hov["ceiling"]["p_elec_total_kw"]), ("cruise", p_el_cr)):
            C = P / eta_b / E_eol
            self.calc.setdefault("c_rates_eol", {})[tag] = C
        if ro.get("p_shaft_most_loaded_kw"):
            P_ro = (ro["p_shaft_most_loaded_kw"] + hs["p_shaft_kw"] * (n_disks - 2 if not coax else n_disks - 1)) / eta_drive + aux
            self.calc["c_rates_eol"]["rotor-out (approx.)"] = P_ro / eta_b / E_eol
        Ch = self.calc["c_rates_eol"]["hover (ceiling)"]
        self.cmp("hover C-rate at EOL capacity (ceiling)", Ch, rep.get("c_rate_hover"), "c_rate", "1/h", "[B4]")
        if cell.get("max_continuous_discharge_a") and cell.get("capacity_ah"):
            c_cell = cell["max_continuous_discharge_a"] / (cell["capacity_ah"] * a["battery_eol_fraction"])
            self.limit("hover C-rate <= cell continuous rating - 0.3 C margin", Ch, c_cell - a["c_rate_margin"], "1/h",
                       eq="[B4] req.")
            if "rotor-out (approx.)" in self.calc["c_rates_eol"] and cell.get("max_peak_discharge_a"):
                self.limit("rotor-out C-rate <= cell peak rating", self.calc["c_rates_eol"]["rotor-out (approx.)"],
                           cell["max_peak_discharge_a"] / (cell["capacity_ah"] * a["battery_eol_fraction"]), "1/h", eq="[B4]")
        npk = bat.get("independent_packs", 1)
        self.limit("independent battery packs/buses", npk, 2, "-", sense=">=", eq="req.")
        if npk >= 2:
            # single pack failure: remaining packs supply ceiling hover power for landing
            C_one_out = hov["ceiling"]["p_elec_total_kw"] / eta_b / (E_eol * (npk - 1) / npk)
            self.calc["c_rate_one_pack_out"] = C_one_out
            if cell.get("max_peak_discharge_a") and cell.get("capacity_ah"):
                self.limit("C-rate with one pack failed (hover landing) <= cell peak rating", C_one_out,
                           cell["max_peak_discharge_a"] / (cell["capacity_ah"] * a["battery_eol_fraction"]), "1/h", eq="[B4]")

        # ---------------- masses
        self.mass_check(W, V, atm_cr, ro, hs, V_nom, p_el_cr)

        # ---------------- cost
        self.cost_check()

        status = [r["status"] for r in self.rows]
        summary = {s: status.count(s) for s in ("PASS", "WARN", "FAIL", "INFO", "MISSING")}
        return dict(design_name=d.get("name"), summary=summary, rows=self.rows, computed=self.calc,
                    assumptions=self.a, tolerances=TOL, notes=self.notes)

    # ------------------------------------------------------------------ masses
    def mass_check(self, W, V, atm_cr, ro, hs, V_nom, p_el_cr):
        d, a = self.d, self.a
        m = d["mass_kg"]
        mtow = m["mtow"]
        Wdg = mtow / LB
        lim = d.get("structure", {})
        Nz = 1.5 * lim.get("limit_load_factor_positive", 3.8)
        Nl = 1.5 * lim.get("landing_load_factor", 3.0)
        w = d["wing"]
        S_ft2 = w["area_m2"] / FT**2
        AR = w["span_m"] ** 2 / w["area_m2"]
        Vd = d.get("structure", {}).get("dive_speed_ms", 1.25 * V)
        q_psf = 0.5 * atm_cr["rho"] * V**2 * 0.020885   # Pa -> lb/ft^2 (Raymer: q at cruise)
        tf = a["tech_factor_structure"]
        est = {}
        est["wing"] = tf * raymer_wing_lb(S_ft2, 0, AR, w.get("sweep_deg", 0), q_psf, w.get("taper", 1.0),
                                          w.get("thickness_ratio", 0.15), Nz, Wdg) * LB
        est_wing_afdd = afdd93_wing_lb(S_ft2, AR, w.get("sweep_deg", 0), w.get("taper", 1.0), w.get("thickness_ratio", 0.15),
                                       Nz, Wdg) * LB
        self.calc["wing_mass_afdd93_kg"] = est_wing_afdd
        t = d.get("tail") or {}
        if t.get("horizontal_area_m2"):
            est["tail_horizontal"] = tf * raymer_htail_lb(Nz, Wdg, q_psf, t["horizontal_area_m2"] / FT**2, t.get("thickness_ratio", 0.10),
                                                          t.get("horizontal_aspect_ratio", 4.0)) * LB
        if t.get("vertical_area_m2"):
            nv = t.get("vertical_count", 2)
            est["tail_vertical"] = nv * tf * raymer_vtail_lb(Nz, Wdg, q_psf, t["vertical_area_m2"] / nv / FT**2,
                                                             t.get("thickness_ratio", 0.10), t.get("vertical_aspect_ratio", 1.5)) * LB
        f = d["fuselage"]
        deq = math.sqrt(f["max_width_m"] * f["max_height_m"])
        swet_f = f.get("wetted_area_m2") or 0.80 * math.pi * deq * f["length_m"]
        est["fuselage"] = tf * raymer_fuselage_lb(swet_f / FT**2, Nz, Wdg, f.get("tail_arm_m", 0.5 * f["length_m"]) / FT,
                                                  f["length_m"] / f["max_height_m"], q_psf) * LB
        lg = d.get("landing_gear") or {}
        # NDARC fractional landing gear (f_LG = 0.0325) with crashworthiness increment f_LGcw = 0.14 [M6]
        est["landing_gear"] = 0.0325 * mtow * (1 + 0.14)
        self.calc["landing_gear_raymer_ga_kg"] = raymer_main_gear_lb(Nl, Wdg, lg.get("length_m", 0.5) / 0.0254) * LB
        est["flight_controls"] = raymer_flight_controls_lb(f["length_m"] / FT, w["span_m"] / FT, Nz, Wdg) * LB
        lr = d["lift_rotors"]
        n = lr["count"]
        T_max = (ro or {}).get("T_max_N") or W / max(n - 2, 1)
        est["booms_and_fittings"] = boom_mass_kg(d, T_max * (1 + a["control_thrust_margin"]), a)["kg"]
        # motors: size for the rotor-out torque if known, else 1.5 x hover torque
        Dr = lr["diameter_m"]
        vtip = lr.get("tip_speed_hover_ms", 150.0)
        omega = vtip / (Dr / 2)
        Q_hover = hs["p_shaft_kw"] * 1e3 / omega
        Q_design = (ro or {}).get("torque_most_loaded_nm") or 1.6 * Q_hover
        est["lift_motors"] = n * motor_mass_kg(Q_design)
        self.calc["lift_motor_design_torque_nm"] = Q_design
        mot = lr.get("motor", {})
        if mot.get("mass_kg"):
            self.cmp("lift motor mass each (catalog) vs NDARC torque regression", motor_mass_kg(Q_design), mot["mass_kg"],
                     "mass_component", "kg", "[M8]")
        pu = d.get("pusher", {})
        Vc = V
        Q_push = None
        if pu.get("rpm_cruise"):
            om_p = pu["rpm_cruise"] * 2 * math.pi / 60
            Q_push = 1.25 * self.calc["cruise"]["p_shaft_kw"] * 1e3 / om_p
            est["pusher_motor"] = motor_mass_kg(Q_push)
        R_b, c_b = Dr / 2, lr.get("blade_chord_m", 0.08 * Dr / 2)
        wb, wh = afdd00_rotor_kg(R_b, c_b, vtip, lr.get("blades", 2), a["flap_frequency"], a["tech_factor_rotor"])
        est["lift_rotors_blades_hubs"] = n * (wb + wh)
        if pu.get("diameter_m"):
            vt_p = math.pi * pu["diameter_m"] * pu.get("rpm_cruise", 2000) / 60
            pb, ph = afdd00_rotor_kg(pu["diameter_m"] / 2, pu.get("blade_chord_m", 0.08 * pu["diameter_m"] / 2), vt_p,
                                     pu.get("blades", 3), 1.0, a["tech_factor_rotor"])
            est["pusher_propeller"] = pb + ph
        # inverters / motor accessories: NASA motor tech factor 1.63 -> 0.63 x motor mass
        est["inverters_cooling_accessories"] = a["accessory_factor"] * (est["lift_motors"] + est.get("pusher_motor", 0.0))
        P_peak = hs["p_shaft_kw"] * 1e3 * n / max(n - 2, 1) * 1.2 / 0.93
        # HV harness is part of NASA's 0.63 accessory factor; computed separately only as a cross-check [M14]
        self.calc["hv_harness_physics_kg"] = harness_kg(P_peak, V_nom, d.get("systems", {}).get("hv_cable_length_m", 4.0 * n + 10.0), a)
        est["parachute"] = parachute_kg(mtow, a["parachute_points"])
        av = d.get("systems", {}).get("avionics_uninstalled_kg", 10.0)
        est["avionics_installed"] = 2.117 * (av / LB) ** 0.933 * LB                                   # [M12]
        est["electrical_lv"] = a["lv_electrical_kg"] if a.get("lv_electrical_kg") is not None else \
            12.57 * (est["avionics_installed"] / LB) ** 0.51 * LB                                      # [M13]
        # furnishings incl. seats and restraints: Raymer GA [M11], not less than the per-seat allowance
        est["furnishings_seats"] = max(max(0.0582 * Wdg - 65, 0) * LB, d.get("cabin", {}).get("seats", 2) * a["seat_mass_kg"])
        self.calc["mass_estimates_kg"] = est
        empty_M = sum(est.values())
        self.calc["empty_excl_battery_M_kg"] = empty_M
        bd = m.get("breakdown", {})
        if "hv_harness" in bd and "inverters" in bd:
            self.cmp("inverters + HV harness (vs NASA 0.63 x motor accessory factor)", est["inverters_cooling_accessories"],
                     bd["inverters"] + bd["hv_harness"] + bd.get("cooling", 0), "mass_component", "kg", "[M16]")
            bd = {k: v for k, v in bd.items() if k != "inverters"}
        mapping = dict(wing="wing", fuselage="fuselage", landing_gear="landing_gear", booms_and_fittings="booms",
                       lift_motors="lift_motors", lift_rotors_blades_hubs="lift_rotors", parachute="parachute",
                       tail_horizontal="tail", pusher_motor="pusher_motor", inverters_cooling_accessories="inverters",
                       pusher_propeller="pusher_propeller", furnishings_seats="seats", avionics_installed="avionics",
                       electrical_lv="lv_electrical")
        tail_D = bd.get("tail")
        for k_m, k_d in mapping.items():
            if k_m == "tail_horizontal":
                if tail_D is not None:
                    self.cmp("tail (H + V) mass", est.get("tail_horizontal", 0) + est.get("tail_vertical", 0), tail_D,
                             "mass_component", "kg", "[M3]-[M4]")
                continue
            if k_d in bd and k_m in est:
                self.cmp(f"{k_d.replace('_', ' ')} mass", est[k_m], bd[k_d], "mass_component", "kg", MASS_EQ.get(k_m, ""))
        self.cmp("wing mass, NDARC AFDD93 cross-check", est_wing_afdd, bd.get("wing"), "mass_component", "kg", "[M2]")
        self.cmp("empty mass excluding battery", empty_M, m.get("empty"), "mass", "kg", "[M0]",
                 note="M sums its own component estimates; D's growth allowance excluded from both" if not bd.get("growth") else
                 "D's breakdown contains a growth allowance; M has none")
        mtow_M = empty_M + m.get("battery", 0) + m.get("payload", 0)
        self.calc["mtow_M_kg"] = mtow_M
        self.cmp("MTOW recomputed (M empty + D battery + payload)", mtow_M, mtow, "mass", "kg", "[M0]")

    # ------------------------------------------------------------------ cost
    def cost_check(self):
        d = self.d
        cst = d.get("cost", {})
        rep = d.get("results", {})
        est = self.calc.get("mass_estimates_kg", {})
        airframe = sum(est.get(k, 0) for k in ("wing", "tail_horizontal", "tail_vertical", "fuselage", "booms_and_fittings",
                                                "landing_gear", "flight_controls"))
        VH = d["mission"]["cruise_speed_kmh"] / 3.6 * 1.10 / KT
        N = cst.get("units_produced_5yr", 10)
        rates = cst.get("labour_rates_usd_h", dict(engineering=95.0, tooling=65.0, manufacturing=55.0))
        cpi = cst.get("cpi_factor_vs_2012", 1.40)
        ez = eastlake_cost(airframe, VH, N, cpi, cst.get("composite_fraction", 0.8), rates, cst.get("f_cert", 0.5))
        cots = cst.get("cots_bottom_up_usd")
        self.calc["cost"] = dict(eastlake=ez, airframe_structure_kg=airframe, VH_kts=VH, units=N)
        if cots is not None:
            self.calc["cost"]["cots_bottom_up_usd"] = cots
        self.cmp("acquisition cost per aircraft (Eastlake airframe + COTS propulsion/systems)",
                 ez["per_unit_recurring"] + (cst.get("cots_propulsion_systems_usd") or 0), rep.get("cost_usd"), "cost", "USD",
                 "[C1]-[C9]", note="recurring airframe (Eastlake hours x rate + materials) + D's COTS propulsion/systems total")


MASS_EQ = dict(wing="[M1]", fuselage="[M5]", landing_gear="[M6]", booms_and_fittings="[M10]", lift_motors="[M8]",
               lift_rotors_blades_hubs="[M9]", parachute="[M15]", pusher_motor="[M8]",
               inverters_cooling_accessories="[M16]", hv_harness="[M14]", pusher_propeller="[M9]",
               furnishings_seats="[M11]", avionics_installed="[M12]", electrical_lv="[M13]")


# ============================================================================================
# Reporting
# ============================================================================================
def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        if v != 0 and (abs(v) >= 1e5 or abs(v) < 1e-2):
            return f"{v:.3g}"
        return f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}"
    return str(v)


def write_reports(result: dict, out_dir: Path, tag: str = "", source: str = ""):
    out_dir.mkdir(parents=True, exist_ok=True)
    sfx = f"_{tag}" if tag else ""
    js = out_dir / f"check_report{sfx}.json"
    md = out_dir / f"check_report{sfx}.md"
    js.write_text(json.dumps(result, indent=1, default=float))
    s = result["summary"]
    lines = [f"# Independent design check{(' - ' + tag) if tag else ''}", "",
             f"Design: **{result.get('design_name')}**  ", f"Input: `{source}`  ",
             "Checker: `methods/check_design.py` (equations in `methods/EQUATIONS.md`; tags in the *eq* column).", "",
             f"Summary: **{s.get('PASS', 0)} PASS, {s.get('WARN', 0)} WARN, {s.get('FAIL', 0)} FAIL**, "
             f"{s.get('INFO', 0)} informational (no D value), {s.get('MISSING', 0)} missing.", "",
             "M = this independent check, D = value reported in the design file. diff = (M - D)/D.", "",
             "| status | quantity | M | D | diff | unit | tolerance | eq | note |", "|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        diff = "-" if r.get("diff") is None else f"{r['diff']:+.1%}"
        lines.append(f"| {r['status']} | {r['quantity']} | {fmt(r['M'])} | {fmt(r['D'])} | {diff} | {r['unit']} | {r['tol']} | "
                     f"{r['eq']} | {r.get('note', '')} |")
    c = result["computed"]
    lines += ["", "## Key recomputed values", ""]
    cr = c.get("cruise", {})
    mi = c.get("mission", {})
    hv = c.get("hover", {}).get("site", {})
    lines += [f"- Disk loading {c.get('disk_loading_N_m2', 0):.0f} N/m^2; hover FM (M) {hv.get('fm_used', 0):.3f}; "
              f"hover electrical {hv.get('p_elec_total_kw', 0):.1f} kW at the site, "
              f"{c.get('hover', {}).get('ceiling', {}).get('p_elec_total_kw', 0):.1f} kW at the ceiling.",
              f"- Cruise: CL {cr.get('CL', 0):.3f}, CD0 {cr.get('CD0', 0):.4f}, L/D {cr.get('LD', 0):.2f}, "
              f"drag {cr.get('drag_N', 0):.0f} N, propeller eta {cr.get('eta_prop_M', 0):.3f}, electrical {cr.get('p_elec_kw', 0):.1f} kW.",
              f"- Mission energy {mi.get('E_mission_kwh', 0):.2f} kWh (hover {mi.get('E_hover_kwh', 0):.2f}, transitions "
              f"{mi.get('E_transitions_kwh', 0):.2f}, climb {mi.get('E_climb_kwh', 0):.2f}, cruise {mi.get('E_cruise_kwh', 0):.2f}); "
              f"nominal energy required {mi.get('E_nominal_required_kwh', 0):.1f} kWh; range {mi.get('range_km', 0):.1f} km.",
              f"- C-rates at EOL: " + ", ".join(f"{k} {v:.2f}" for k, v in c.get("c_rates_eol", {}).items()) + ".",
              f"- Gust load factor at VC {c.get('gust_load_factor_Vc', 0):.2f} g; wing loading {c.get('wing_loading_N_m2', 0):.0f} N/m^2.",
              f"- Empty mass excluding battery (M) {c.get('empty_excl_battery_M_kg', 0):.1f} kg; MTOW (M) {c.get('mtow_M_kg', 0):.1f} kg.", ""]
    lines += ["### Drag-area build-up (m^2)", "", "| item | D/q |", "|---|---|"]
    for k, v in cr.get("drag_area_breakdown_m2", {}).items():
        lines.append(f"| {k} | {v:.4f} |")
    lines += ["", "### Component mass estimates (kg)", "", "| item | kg |", "|---|---|"]
    for k, v in c.get("mass_estimates_kg", {}).items():
        lines.append(f"| {k} | {v:.1f} |")
    if result["notes"]:
        lines += ["", "### Notes", ""] + [f"- {n}" for n in result["notes"]]
    lines += ["", "### Assumptions used by the checker", "", "```json", json.dumps(result["assumptions"], indent=1), "```", ""]
    md.write_text("\n".join(lines))
    return js, md


def print_table(result: dict):
    print(f"{'status':6s}  {'quantity':78s} {'M':>11s} {'D':>11s} {'diff':>8s}")
    for r in result["rows"]:
        diff = "" if r.get("diff") is None else f"{r['diff']:+.1%}"
        print(f"{r['status']:6s}  {r['quantity'][:78]:78s} {fmt(r['M']):>11s} {fmt(r['D']):>11s} {diff:>8s}")
    print("summary:", result["summary"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design", nargs="?", default=str(ROOT / "design" / "selected_design.json"))
    ap.add_argument("--geometry", default=None)
    ap.add_argument("--out", default=str(ROOT / "validation" / "methods"))
    ap.add_argument("--tag", default="")
    args = ap.parse_args(argv)
    p = Path(args.design)
    if not p.exists():
        print(f"design file not found: {p}", file=sys.stderr)
        return 2
    design = json.loads(p.read_text())
    gpath = Path(args.geometry) if args.geometry else p.with_name("geometry.json")
    geometry = json.loads(gpath.read_text()) if gpath.exists() else None
    res = Checker(design, geometry).run()
    print_table(res)
    js, md = write_reports(res, Path(args.out), args.tag, source=str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p))
    print("wrote", js, md)
    return 1 if res["summary"].get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
