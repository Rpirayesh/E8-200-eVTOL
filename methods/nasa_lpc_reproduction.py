#!/usr/bin/env python3
"""Reproduce published numbers of the NASA RVLT Lift+Cruise (electric) concept vehicle with the M equations.

Sources (published values only):
  [S18] Silva, Johnson, Antcliff, Patterson, "VTOL Urban Air Mobility Concept Vehicles for Technology Development",
        AIAA 2018-3847, Table 3 (column "L+C E") and sec. VI. https://www.nasa.gov/wp-content/uploads/2026/03/silva2018.pdf
  [JS22] Johnson & Silva, "NASA concept vehicles and the engineering of advanced air mobility aircraft",
        The Aeronautical Journal 126 (2022), Table 3 (column "Lift+Cruise Electric").
        https://ntrs.nasa.gov/api/citations/20210026170/downloads/1521_Johnson%20%26%20Silva_122721%20.pdf

    ~/tools/cadenv/bin/python methods/nasa_lpc_reproduction.py
Writes validation/methods/nasa_lpc_reproduction.md and .json.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import check_design as cd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "methods"
LB, FT, HP, KT, G0 = cd.LB, cd.FT, cd.HP, cd.KT, cd.G0

# ---- published data, [S18] Table 3, "L+C E" (battery-electric lift+cruise), US units as published
P18 = dict(DL_psf=13.1, R_ft=5.0, solidity=0.267, vtip_fps=585.0, n_lift=8, mrp_hp_per_lifter=139.0, cruise_motor_hp=628.0,
           Dq_ft2=16.9, Dq_hubs_ft2=1.2, Dq_fus_ft2=1.7, battery_MJ=1436.0, battery_lb=1693.0, DGW_lb=8210.0,
           empty_lb=7001.0, structure_lb=2575.0, rotor_group_lb=948.0, propulsion_lb=3186.0, systems_lb=540.0,
           Vbe_kt=88.0, Vbr_kt=112.0, payload_lb=1200.0, energy_burn_MJ=1113.0, LDe=8.5, FM=0.74,
           c_hover=2.4, c_cruise=0.7, pack_Whkg=400.0, motor_tech_factor=1.63)
# ---- [JS22] Table 3, "Lift+Cruise Electric"
P22 = dict(DL_psf=15.1, R_ft=5.0, vtip_fps=550.0, n_lift=8, hp_per_lifter=189.0, cruise_motor_hp=838.0, DGW_lb=9482.0,
           empty_lb=8274.0, structure_lb=2973.0, propulsion_lb=1866.0, battery_lb=2058.0, LDe=7.9, Vbr_kt=83.0)


def mission_energy_2018(W, P_hover_elec_kw, P_cruise_elec_kw, V_ms, P_climb_extra_kw, eta_b=1.0):
    """[S18] sec. IV / Table 1: two flights of 37.5 nm into a 10 kt headwind + 20 min reserve at cruise power.
    Per flight: 30 s vertical take-off + 10 s hover + 10 s hover + 30 s hover + 30 s descent (hover power), 15 s at 10 %
    + 15 s at 10 % (taxi/idle), climb 6050 -> 10000 ft at >= 900 ft/min, cruise at Vbr."""
    t_hover = 30 + 10 + 10 + 30 + 30
    t_idle = 30
    climb_ft = 10000 - 6050
    t_climb = climb_ft / 900 * 60
    gs = V_ms - 10 * KT
    d_climb = gs * t_climb
    d_cruise = 37.5 * 1852 - d_climb
    per = (P_hover_elec_kw * t_hover + 0.1 * P_hover_elec_kw * t_idle + (P_cruise_elec_kw + P_climb_extra_kw) * t_climb
           + P_cruise_elec_kw * d_cruise / gs) / 3600
    reserve = P_cruise_elec_kw * 20 / 60
    return dict(per_flight_kwh=per, reserve_kwh=reserve, total_kwh=2 * per + reserve, t_climb_s=t_climb)


def main():
    rows = []

    def add(name, m, nasa, unit, src, note=""):
        rows.append(dict(quantity=name, M=m, NASA=nasa, unit=unit, diff=(m - nasa) / nasa if nasa else None, source=src, note=note))

    p = P18
    W_lb = p["DGW_lb"]
    W = W_lb * LB * G0
    R = p["R_ft"] * FT
    A_tot = p["n_lift"] * math.pi * R**2
    add("lift-rotor disk loading", W_lb / (A_tot / FT**2), p["DL_psf"], "lb/ft^2", "[S18] T3", "DGW / (8 pi R^2)")
    atm6 = cd.isa(6000 * FT, 0.0)
    vtip = p["vtip_fps"] * FT
    T = W / p["n_lift"]
    # (a) momentum theory with NASA's aircraft figure of merit (download included in NASA's aircraft FM)
    h_fm = cd.hover_rotor(T, 2 * R, atm6["rho"], None, None, 1.0, 0.0, fm_given=p["FM"])
    p_lifter_fm = h_fm["p_shaft_with_D_fm_kw"]
    add("hover shaft power per lifter, 6000 ft ISA, FM = 0.74 (published)", p_lifter_fm / HP * 1e3, p["mrp_hp_per_lifter"], "hp",
        "[S18] T3 MRP per lifter", "M uses [H1] + published FM; NASA MRP is the installed rating")
    # (b) M's own blade-element FM estimate
    h_be = cd.hover_rotor(T, 2 * R, atm6["rho"], vtip, p["solidity"], cd.DEFAULTS["kappa_induced"], cd.DEFAULTS["cd0_blade"])
    add("aircraft hover figure of merit (M blade-element [H2])", h_be["fm_used"], p["FM"], "-", "[S18] T3")
    add("hover shaft power per lifter with M's FM", h_be["p_shaft_kw"] / HP * 1e3, p["mrp_hp_per_lifter"], "hp", "[S18] T3")
    # battery
    E_cap_kwh = p["battery_MJ"] / 3.6
    add("battery mass from published capacity at 530 Wh/kg cell-usable (sec. VI A)", E_cap_kwh / 0.530 / LB * 1.0 * (1 / 1.30) * 1.30,
        p["battery_lb"], "lb", "[S18] T3 + sec. VI A", "1436 MJ / 530 Wh/kg; check of NASA's capacity bookkeeping")
    add("usable energy at 400 Wh/kg pack x battery mass", p["battery_lb"] * LB * 0.400 * 3.6, p["energy_burn_MJ"], "MJ",
        "[S18] T3 + sec. VI A", "battery is sized by the design mission: usable = energy burn")
    # C-rates: NASA C-rate = electrical power / capacity (1436 MJ)
    eta_drive = cd.DEFAULTS["eta_motor"] * cd.DEFAULTS["eta_inverter"] * cd.DEFAULTS["eta_wiring"]
    P_hover_elec = p_lifter_fm * p["n_lift"] / eta_drive
    add("hover C-rate = P_hover,elec / capacity", P_hover_elec / E_cap_kwh, p["c_hover"], "1/h", "[S18] T3",
        f"M drive efficiency {eta_drive:.3f}")
    V = p["Vbr_kt"] * KT
    P_cruise_shaft_from_LDe = W * V / p["LDe"] / 1e3
    P_cruise_elec = P_cruise_shaft_from_LDe / eta_drive
    add("cruise C-rate = (W V / (L/De)) / eta_drive / capacity", P_cruise_elec / E_cap_kwh, p["c_cruise"], "1/h", "[S18] T3")
    # cruise drag: D/q published; induced drag needs the (unpublished) span -> span that reproduces L/De
    atm10 = cd.isa(10000 * FT, 0.0)
    q = 0.5 * atm10["rho"] * V**2
    Dq = p["Dq_ft2"] * FT**2
    eta_p = 0.85
    D_total_from_LDe = W / p["LDe"] * eta_p
    D_par = q * Dq
    D_ind = D_total_from_LDe - D_par
    e = 0.80
    b_req = math.sqrt(W**2 / (q * math.pi * e * D_ind)) if D_ind > 0 else float("nan")
    rep_b = dict(q_Pa=q, D_parasite_N=D_par, D_from_LDe_N=D_total_from_LDe, b_required_m=b_req, eta_p=eta_p, e=e)
    # motor mass, [S18] eq. 1 with the 1.63 accessory factor
    omega = vtip / R
    Q = p["mrp_hp_per_lifter"] * HP / omega
    m_motor = cd.motor_mass_kg(Q)
    lift_motor_group_lb = p["n_lift"] * m_motor / LB * p["motor_tech_factor"]
    # pusher: torque unknown (rpm unpublished); bracket with 2000-2500 rpm
    cr_lo = cd.motor_mass_kg(p["cruise_motor_hp"] * HP / (2500 * 2 * math.pi / 60)) / LB * p["motor_tech_factor"]
    cr_hi = cd.motor_mass_kg(p["cruise_motor_hp"] * HP / (2000 * 2 * math.pi / 60)) / LB * p["motor_tech_factor"]
    motors_mid = lift_motor_group_lb + 0.5 * (cr_lo + cr_hi)
    add("propulsion group excl. battery (8 lift + 1 cruise motor, eq. 1 x 1.63)", motors_mid,
        p["propulsion_lb"] - p["battery_lb"], "lb", "[S18] T3 + eq. 1", f"cruise motor at 2000-2500 rpm: {cr_lo:.0f}-{cr_hi:.0f} lb")
    # rotor group: AFDD00 blades + hubs for 8 lifters and the pusher (pusher size unpublished: excluded)
    chord = p["solidity"] * math.pi * R / 2
    wb, wh = cd.afdd00_rotor_kg(R, chord, vtip, 2, cd.DEFAULTS["flap_frequency"])
    rotor_lb = p["n_lift"] * (wb + wh) / LB
    add("rotor group (8 lift rotors, AFDD00, no tech factor)", rotor_lb, p["rotor_group_lb"], "lb", "[S18] T3",
        "NASA's rotor group also contains the pusher, spinners and rotor supports (not separately published)")
    # mission energy
    P_climb_extra = W * (900 * FT / 60) / (eta_p * eta_drive) / 1e3
    mis = mission_energy_2018(W, P_hover_elec, P_cruise_elec, V, P_climb_extra)
    add("design-mission energy, reading A: 2 x 37.5 nm + 20 min reserve", mis["total_kwh"] * 3.6, p["energy_burn_MJ"], "MJ",
        "[S18] T1, T3", "M hover with published FM, cruise from published L/De at Vbr, 10 kt headwind")
    add("design-mission energy, reading B: 2 x 37.5 nm, reserve not in 'energy burn'", 2 * mis["per_flight_kwh"] * 3.6,
        p["energy_burn_MJ"], "MJ", "[S18] T1, T3", "same segments without segment 10")
    add("design-mission energy, reading C: 1 x 37.5 nm + 20 min reserve (Table 1 as listed)",
        (mis["per_flight_kwh"] + mis["reserve_kwh"]) * 3.6, p["energy_burn_MJ"], "MJ", "[S18] T1, T3", "")
    # empty-weight fractions
    add("empty-weight fraction incl. battery", p["empty_lb"] / p["DGW_lb"], 7001 / 8210, "-", "[S18] T3", "identity check")

    # ---- 2022 update
    q22 = P22
    W22 = q22["DGW_lb"] * LB * G0
    A22 = q22["n_lift"] * math.pi * (q22["R_ft"] * FT) ** 2
    add("[2022] lift-rotor disk loading", q22["DGW_lb"] / (A22 / FT**2), q22["DL_psf"], "lb/ft^2", "[JS22] T3")
    h22 = cd.hover_rotor(W22 / 8, 2 * q22["R_ft"] * FT, atm6["rho"], None, None, 1.0, 0.0, fm_given=0.74)
    add("[2022] hover shaft power per lifter, 6000 ft ISA, FM 0.74", h22["p_shaft_with_D_fm_kw"] / HP * 1e3, q22["hp_per_lifter"],
        "hp", "[JS22] T3", "published power is the installed rating")
    Q22 = q22["hp_per_lifter"] * HP / (q22["vtip_fps"] * FT / (q22["R_ft"] * FT))
    cr22 = cd.motor_mass_kg(q22["cruise_motor_hp"] * HP / (2250 * 2 * math.pi / 60)) / LB * 1.63
    add("[2022] propulsion group (8 lift + 1 cruise motor, eq. 1 x 1.63)", 8 * cd.motor_mass_kg(Q22) / LB * 1.63 + cr22,
        q22["propulsion_lb"], "lb", "[JS22] T3", "2022 table lists battery separately")

    out = dict(rows=rows, cruise_span_backout=rep_b, mission=mis, motor_torque_lifter_Nm=Q, motor_mass_lifter_kg=m_motor)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nasa_lpc_reproduction.json").write_text(json.dumps(out, indent=1, default=float))
    lines = ["# Reproduction of the NASA Lift+Cruise (electric) concept vehicle", "",
             "Script: `methods/nasa_lpc_reproduction.py` (uses the functions of `methods/check_design.py`).", "",
             "Published values: [S18] Silva et al., AIAA 2018-3847, Table 1, Table 3 (L+C E), sec. VI "
             "(https://www.nasa.gov/wp-content/uploads/2026/03/silva2018.pdf); [JS22] Johnson & Silva, Aeronautical Journal 2022, "
             "Table 3 (https://ntrs.nasa.gov/api/citations/20210026170/downloads/1521_Johnson%20%26%20Silva_122721%20.pdf).", "",
             "| quantity | M (this check) | NASA | diff | unit | source | note |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        d = "-" if r["diff"] is None else f"{r['diff']:+.1%}"
        lines.append(f"| {r['quantity']} | {r['M']:.4g} | {r['NASA']:.4g} | {d} | {r['unit']} | {r['source']} | {r['note']} |")
    lines += ["", "## Cruise drag: span back-out", "",
              f"The wing span of the NASA vehicle is not published in [S18]/[JS22]. With the published D/q = 16.9 ft^2 "
              f"({Dq:.3f} m^2), DGW, Vbr = 112 kt at 10,000 ft ISA (q = {q:.0f} Pa), an assumed propeller efficiency "
              f"{eta_p} and Oswald factor {e}, the published L/De = 8.5 implies a total drag of {D_total_from_LDe:.0f} N, of which "
              f"{D_par:.0f} N is parasite; the remaining induced drag {D_ind:.0f} N corresponds to a span of {b_req:.1f} m. "
              "This is offered as a consistency check, not a reproduction.", "",
              "## Mission energy split (M)", "",
              f"Per flight {mis['per_flight_kwh']:.1f} kWh (climb {mis['t_climb_s']:.0f} s); reserve {mis['reserve_kwh']:.1f} kWh; "
              f"total {mis['total_kwh']:.1f} kWh = {mis['total_kwh'] * 3.6:.0f} MJ.", ""]
    (OUT / "nasa_lpc_reproduction_table.md").write_text("\n".join(lines))
    for r in rows:
        print(f"{r['quantity'][:80]:80s} M {r['M']:10.4g}  NASA {r['NASA']:10.4g}  "
              f"{'' if r['diff'] is None else format(r['diff'], '+.1%')}")
    print(rep_b, mis)


if __name__ == "__main__":
    main()
