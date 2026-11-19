#!/usr/bin/env python3
"""Verification of the work package D sizing code and of the selected design (validation/sizing).

  V1-V8   unit tests of the sizing physics against closed-form values and against WP M's independent implementation
  A1-A12  audit of design/selected_design.json and design/geometry.json: mass closure, CG, mass items vs FEA reader,
          footprint and clearances, battery layout, energy chain recomputed by hand, rotor-out LP re-run
  B1-B4   comparison with benchmark trends (methods/benchmarks)

    ~/tools/cadenv/bin/python validation/sizing/verify_sizing.py
Writes validation/sizing/verification_report.md / .json and validation/sizing/benchmark_comparison.png.
Exit code 1 if any check fails.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "methods"))
import check_design as cd  # noqa: E402  (WP M independent implementation, used as a reference)

from sizing import physics as ph  # noqa: E402
from sizing.model import A0  # noqa: E402
from sizing.rotor_out import best_spin_pattern, layout_xy, lp_max_thrust  # noqa: E402

OUT = ROOT / "validation" / "sizing"
ROWS = []


def check(cid, desc, value, ref, tol, unit="", kind="rel"):
    if kind == "rel":
        ok = abs(value - ref) <= tol * abs(ref)
        d = f"{(value - ref) / ref:+.2%}" if ref else "-"
    elif kind == "le":
        ok, d = value <= ref + 1e-12, f"margin {ref - value:.4g}"
    elif kind == "ge":
        ok, d = value >= ref - 1e-12, f"margin {value - ref:.4g}"
    else:
        ok, d = abs(value - ref) <= tol, f"{value - ref:+.4g}"
    ROWS.append(dict(id=cid, check=desc, value=float(value), ref=float(ref), tol=tol, kind=kind, diff=d, unit=unit,
                     status="PASS" if ok else "FAIL"))


def unit_tests():
    # V1 ISA, hand calculation from ICAO Doc 7488: p = 101325 (1 - 2.25577e-5 h)^5.25588, rho = p / (R (T_std + dT)).
    # (methods/EQUATIONS.md sec. 1 quotes 1.123 / 1.065 kg/m3, which its own [A1]-[A2] do not reproduce: they give
    # 1.109 / 1.055; both the sizing code and check_design.py use [A1]-[A2].  Reported to WP M.)
    for cid, h in (("V1a", 500.0), ("V1b", 1000.0)):
        p = 101325.0 * (1 - 2.25577e-5 * h) ** 5.25588
        check(cid, f"ISA+15 density at {h:.0f} m (hand calculation)", float(ph.isa(h, 15)["rho"]), p / (287.053 * (288.15 - 0.0065 * h + 15)),
              1e-5, "kg/m3")
    check("V1c", "ISA sea-level density", float(ph.isa(0)["rho"]), 1.225, 0.001, "kg/m3")
    # V2 momentum theory: kappa = 1, sigma = 0 -> T^1.5 / sqrt(2 rho A)
    T, Dm, rho = 1200.0, 1.8, 1.1
    p, pi = ph.rotor_power(T, Dm, rho, 160.0, 0.0, 1.0, 0.015)
    check("V2", "ideal hover power (momentum theory)", float(p), T**1.5 / math.sqrt(2 * rho * math.pi * Dm**2 / 4), 1e-9, "W")
    # V3 disc strip area: full disc, half disc, Monte Carlo strip
    R = 0.9
    check("V3a", "disc strip area, whole disc", float(ph.disc_strip_area(R, 0.0, -2, 2)), math.pi * R**2, 1e-9, "m2")
    check("V3b", "disc strip area, half disc", float(ph.disc_strip_area(R, 0.0, 0.0, 2)), math.pi * R**2 / 2, 1e-9, "m2")
    rng = np.random.default_rng(0)
    P = rng.uniform(-R, R, (400000, 2))
    inside = (P ** 2).sum(1) <= R**2
    mc = inside & (P[:, 0] > 0.55) & (P[:, 0] < 0.80)
    check("V3c", "disc strip area 0.55..0.80, Monte Carlo", float(ph.disc_strip_area(R, 0.0, 0.55, 0.80)),
          mc.mean() * (2 * R) ** 2, 0.02, "m2")
    # V4 rotor-out LP: symmetric 2 x 4 layout -> n/(n-2) = 4/3 (S18 sec. V C); 4 rotors infeasible; 6 rotors (2 x 3)
    pos = layout_xy([-3.5, -1.6, 1.6, 3.5], 1.5)
    spin, t = best_spin_pattern(pos, 1.0, 0.1)
    check("V4a", "rotor-out LP, 8 rotors: worst T_max / (W/8)", t * 8, 4 / 3, 1e-6)
    check("V4b", "rotor-out LP, 8 rotors: hover yaw balance (sum of spins)", float(spin.sum()), 0.0, 1e-9, kind="abs")
    pos4 = layout_xy([-2.0, 2.0], 1.5)
    t4 = max(lp_max_thrust(pos4, np.array([1, -1, -1, 1.0]), 1.0, 0.1, f)[0] for f in range(4))
    check("V4c", "rotor-out LP, 4 rotors: no trim (inf)", 1.0 if np.isinf(t4) else 0.0, 1.0, 0, kind="abs")
    pos6 = layout_xy([-2.0, 0.0, 2.0], 1.5)
    _, t6 = best_spin_pattern(pos6, 1.0, 0.1)
    check("V4d", "rotor-out LP, 6 rotors on two booms: worst T_max/(W/6) >= 1.5", t6 * 6, 1.5, 0, kind="ge")
    # V5 Raymer masses vs WP M implementation (same equations, independent code)
    S, AR, q, tc, Nz, W = 10.5, 7.4, 975.0, 0.17, 5.7, 1000.0
    m_D = float(ph.raymer_wing_kg(S, AR, q, 1.0, tc, Nz, W))
    m_M = cd.raymer_wing_lb(S / cd.FT**2, 0, AR, 0.0, q * 0.020885, 1.0, tc, Nz, W / cd.LB) * cd.LB
    check("V5a", "Raymer wing [M1] vs WP M", m_D, m_M, 1e-3, "kg")
    m_D = float(ph.raymer_fuselage_kg(12.0, Nz, W, 4.0, 3.4, q))
    m_M = cd.raymer_fuselage_lb(12.0 / cd.FT**2, Nz, W / cd.LB, 4.0 / cd.FT, 3.4, q * 0.020885) * cd.LB
    check("V5b", "Raymer fuselage [M5] vs WP M", m_D, m_M, 1e-3, "kg")
    m_D = float(ph.raymer_htail_kg(1.6, 4.5, q, 0.12, Nz, W))
    m_M = cd.raymer_htail_lb(Nz, W / cd.LB, q * 0.020885, 1.6 / cd.FT**2, 0.12, 4.5) * cd.LB
    check("V5c", "Raymer horizontal tail [M3] vs WP M", m_D, m_M, 1e-3, "kg")
    # V6 propeller efficiency and Oswald vs WP M
    check("V6a", "propeller efficiency [P1]-[P2] vs WP M", float(ph.prop_efficiency(1000, 41.7, 1.123, 1.8)),
          cd.prop_efficiency(1000, 41.7, 1.123, 1.8, 0.9, 0.86), 1e-9)
    check("V6b", "Oswald [I2] vs WP M", float(ph.oswald_raymer(7.3)), cd.oswald_raymer(7.3), 1e-9)
    # V7 Eastlake recurring cost vs WP M
    rec, _ = ph.eastlake_recurring_per_unit(200.0, 89.0, 10, 0.8, 0.5)
    ez = cd.eastlake_cost(200.0, 89.0, 10, 1.40, 0.8, dict(engineering=95, tooling=65, manufacturing=55), 0.5)
    check("V7", "Eastlake recurring airframe cost per unit [C1]-[C8] vs WP M", rec, ez["per_unit_recurring"], 1e-6, "USD")
    # V8 gust load factor vs WP M
    check("V8", "gust load factor [L3] vs WP M", float(ph.gust_load_factor(930.0, 1.225, 1.123, 1.2, 4.9, 40.0)),
          cd.gust_load_factor(930.0, 1.225, 1.123, 1.2, 4.9, 40.0, 15.24), 1e-9)


def audit():
    sd = json.loads((ROOT / "design" / "selected_design.json").read_text())
    geo = json.loads((ROOT / "design" / "geometry.json").read_text())
    m = sd["mass_kg"]
    bd = m["breakdown"]
    # A1 closure and breakdown
    check("A1a", "MTOW = empty + battery + payload", m["empty"] + m["battery"] + m["payload"], m["mtow"], 1e-6, "kg")
    check("A1b", "empty = sum of breakdown (incl. growth)", sum(bd.values()), m["empty"], 1e-4, "kg")
    # A2 mass items in geometry.json sum to MTOW and give cg_mtow_m
    it = geo["mass_items"]
    tot = sum(i["kg"] for i in it)
    check("A2a", "geometry mass_items sum = MTOW", tot, m["mtow"], 1e-4, "kg")
    cgx = sum(i["kg"] * i["x"] for i in it) / tot
    cgz = sum(i["kg"] * i["z"] for i in it) / tot
    check("A2b", "CG x from mass_items = cg_mtow_m", cgx, geo["cg_mtow_m"][0], 1e-3, "m", kind="abs")
    check("A2c", "CG z from mass_items = cg_mtow_m", cgz, geo["cg_mtow_m"][2], 1e-3, "m", kind="abs")
    # A3 FEA reader sees the same total mass and CG
    try:
        from fea import geometry as fg
        G = fg.load(ROOT / "design" / "geometry.json")
        ms = fg.mass_summary(G)
        check("A3a", "FEA reader total mass = MTOW", ms["total_kg"], m["mtow"], 1e-4, "kg")
        check("A3b", "FEA reader CG x vs cg_mtow_m (FEA lumps structure at its own stations; CAD-calibrated positions here)",
              ms["cg"][0], geo["cg_mtow_m"][0], 0.025, "m", kind="abs")
    except Exception as e:  # pragma: no cover
        ROWS.append(dict(id="A3", check=f"FEA reader not available: {e}", status="FAIL", value=0, ref=0, tol=0, kind="", diff="", unit=""))
    # A4 CG on the rotor centroid (hover with equal thrust) and lateral symmetry
    hubs = np.array([r["hub"] for r in geo["lift_rotors"]])
    check("A4a", "rotor centroid x = CG x (MTOW)", float(hubs[:, 0].mean()), geo["cg_mtow_m"][0], 0.005, "m", kind="abs")
    check("A4b", "CG lateral offset", abs(geo["cg_mtow_m"][1]), 0.0, 1e-6, "m", kind="abs")
    # A5 footprint: span and overall length (rotor tips, booms, tail, twin pusher spinners) <= limit (10.5 m from iteration 3.2)
    L_lim = sd.get("limits", {}).get("footprint_max_m", 9.0)
    w = geo["wing"]
    Rr = geo["lift_rotors"][0]["diameter"] / 2
    x_min = min(hubs[:, 0].min() - Rr, min(b["x_front"] for b in geo["booms"]), 0.0)
    x_max = max(hubs[:, 0].max() + Rr, max(b_["x_aft"] for b_ in geo["booms"]), geo["fuselage"]["x_tail"],
                max((pp_["spinner"]["x_to"] for pp_ in (geo.get("pushers") or [])), default=0.0))
    check("A5a", "overall length incl. rotor discs, booms, tail", x_max - x_min, L_lim, 0, "m", kind="le")
    y_max = max(w["span"] / 2, np.abs(hubs[:, 1]).max() + Rr)
    check("A5b", "overall width (span, rotor discs)", 2 * y_max, L_lim, 0, "m", kind="le")
    # A6 clearances: rotor tip-to-tip and rotor-fuselage (the other clearances are the G-checks below)
    gaps = []
    for i in range(len(hubs)):
        for j in range(i + 1, len(hubs)):
            gaps.append(np.hypot(*(hubs[i, :2] - hubs[j, :2])) - 2 * Rr)
    check("A6a", "minimum rotor tip-to-tip clearance (plan view)", min(gaps), 0.10, 0, "m", kind="ge")
    fw = geo["fuselage"]["max_width_m"] / 2
    check("A6b", "rotor tip to fuselage side (plan view)", float(np.abs(hubs[:, 1]).min() - Rr - fw), 0.15, 1e-9, "m", kind="ge")
    # A7 battery layout
    b = sd["battery"]
    c = b["cell"]
    check("A7a", "energy = series x parallel x cell Wh", b["series"] * b["parallel"] * c["energy_wh"] / 1e3, b["energy_nominal_kwh"], 1e-6, "kWh")
    check("A7b", "series count <= Orion BMS 2 limit (180)", b["series"], 180, 0, kind="le")
    check("A7c", "max pack voltage <= inverter 800 V", b["series"] * 4.2, 800, 0, "V", kind="le")
    pm_ = b["pack_mass_model"]
    check("A7d", f"battery mass = cells x (cell + {pm_['per_cell_kg']} kg) + packs x {pm_['per_pack_kg']} kg (CAD-fitted)",
          b["series"] * b["parallel"] * (c["mass_kg"] + pm_["per_cell_kg"]) + b["independent_packs"] * pm_["per_pack_kg"], m["battery"], 1e-4, "kg")
    check("A7e", "independent packs >= 2", b["independent_packs"], 2, 0, kind="ge")
    # A8 energy chain recomputed by hand from the reported powers (terminal energies / battery efficiency)
    r = sd["results"]
    mi = sd["mission"]
    # iteration 3.3: exact cell I-R sag (p_cell = I (V_oc - I R), DCIR x 1.5 EOL), mid-SOC V_oc 3.60 V for take-off,
    # transitions, climb and cruise, low-SOC 3.45 V for the landing hover
    Rcell = c["dcir_ohm"] * 1.5
    ncl = b["series"] * b["parallel"]

    def eta_x(P_kw, v_oc=3.60):
        p_ = P_kw * 1e3 / ncl
        i_ = (v_oc - math.sqrt(v_oc**2 - 4 * Rcell * p_)) / (2 * Rcell)
        return (v_oc - i_ * Rcell) / v_oc
    Wt = m["mtow"] * 9.80665
    eta_d = 0.93 * 0.97 * 0.98
    fm = sd["lift_rotors"]["figure_of_merit"]
    Ph, Pc = r["hover_electrical_power_kw"], r["cruise_electrical_power_kw"]
    E_to = Ph * mi.get("hover_takeoff_s", 60) / 3600 + 0.5 * Wt * 30 / (eta_d * fm) / 3.6e6
    E_ld = Ph * mi.get("hover_landing_s", 60) / 3600
    P_tr = 0.5 * (Ph + Pc)
    E_tr = 2 * P_tr * 30 / 3600
    E_cl = Wt * 470 / (sd["pusher"]["eta_cruise"] * eta_d) / 3.6e6
    E_cr = Pc * mi["range_km"] / mi["cruise_speed_kmh"]
    E_fix = E_to / eta_x(Ph) + E_ld / eta_x(Ph, 3.45) + E_tr / eta_x(P_tr) + E_cl / eta_x(Pc)
    check("A8a", "mission energy at the cells (hand, exact I-R sag per segment)", r["mission_energy_kwh"],
          E_fix + E_cr / eta_x(Pc), 2e-3, "kWh")
    rng_h = (b["energy_nominal_kwh"] * 0.8 * 0.8 - E_fix) * eta_x(Pc) / Pc * mi["cruise_speed_kmh"]
    check("A8c", "range capability (hand, exact sag) = results.range_km", r["range_km"], rng_h, 2e-3, "km")
    check("A8d", "range capability >= 20 km", rng_h, 20.0, 0, "km", kind="ge")
    c_h = r["hover_electrical_power_ceiling_kw"] / eta_x(r["hover_electrical_power_ceiling_kw"]) / (b["energy_nominal_kwh"] * 0.8)
    c_lim = c["max_continuous_discharge_a"] / (c["capacity_ah"] * 0.8) - 0.3
    check("A8e", "hover C-rate at the ceiling (exact sag, EOL) <= continuous screen - 0.3 C", c_h, c_lim, 0, "1/h", kind="le")
    E_use = b["energy_nominal_kwh"] * 0.8 * 0.8
    check("A8b", "usable energy (EOL 80 %, 20 % reserve) >= mission energy", E_use, r["mission_energy_kwh"], 0, "kWh", kind="ge")
    # A9 rotor-out LP re-run on geometry.json (worst failed rotor, 10 % margin) vs reported power
    lr = sd["lift_rotors"]
    vt, Dr, sig = lr["tip_speed_hover_ms"], lr["diameter_m"], lr["solidity"]
    rho_c = float(ph.isa(1000, 15)["rho"])
    pos = hubs[:, :2] - np.array(geo["cg_mtow_m"][:2])
    spin = np.array([rr["spin"] for rr in geo["lift_rotors"]], float)
    Th = geo["operating"]["hover_thrust_per_lift_rotor_n"]
    kqt = geo["rotors"][0]["torque_per_thrust_m"]
    Fz = Th * len(hubs)
    tmax = max(lp_max_thrust(pos, spin, Fz, kqt, f)[0] for f in range(len(hubs)))
    Tc = tmax * 1.10
    rw = math.sqrt(Tc / Th)
    P = float(ph.rotor_power(Tc, Dr, rho_c, vt * rw, sig, A0["kappa"], A0["cd0_blade"])[0]) / 1e3
    Q = P * 1e3 / (vt / (Dr / 2) * rw)
    check("A9a", "rotor-out shaft power (LP on geometry.json, 1000 m ISA+15)", P, r["rotor_out_max_shaft_power_kw"], 0.01, "kW")
    check("A9b", "rotor-out power <= motor peak", P, lr["motor"]["peak_power_kw"], 0, "kW", kind="le")
    check("A9c", "rotor-out torque <= motor max torque", Q, lr["motor"]["max_torque_nm"], 0, "N m", kind="le")
    # A10 static margin in all loading cases within 5-15 %
    for k, cse in sd["loading_cases"].items():
        check("A10", f"static margin, {k}", cse["static_margin"], 0.05, 0, kind="ge")
        check("A10", f"static margin, {k} (upper)", cse["static_margin"], 0.15, 0, kind="le")
        check("A11", f"rotor-out torque, {k}", cse["oei_torque_Nm_1000m"], lr["motor"]["max_torque_nm"], 0, "N m", kind="le")
        check("A11", f"rotor-out power, {k}", cse["oei_shaft_power_kw_1000m"], lr["motor"]["peak_power_kw"], 0, "kW", kind="le")
    # A12 parachute rating and stall margin
    from sizing.data import PARACHUTES
    chute = geo["parachute"]["model"]
    rating = [p_["max_kg"] for p_ in PARACHUTES if p_["id"] == chute][0]
    check("A12a", f"MTOW <= parachute rating ({chute})", m["mtow"], rating, 0, "kg", kind="le")
    for k, cse in sd["loading_cases"].items():
        check("A14", f"rotor-out flare at {sd['results']['rotor_out_flare_load_factor_g']} g, torque (500 m ISA+15), {k}", cse["oei_flare_torque_Nm_500m"], lr["motor"]["max_torque_nm"], 0, "N m", kind="le")
        check("A14", f"rotor-out flare at {sd['results']['rotor_out_flare_load_factor_g']} g, power (500 m ISA+15), {k}", cse["oei_flare_shaft_power_kw_500m"], lr["motor"]["peak_power_kw"], 0, "kW", kind="le")
    # G: integration checks with WP G's CAD-audit definitions (sizing/geometry_checks.py)
    from sizing.geometry_checks import checks as gchecks
    for r in gchecks(geo):
        if r["status"] == "WARN":
            continue
        check(r["id"], r["check"], r["value"], r["reference"], 0, r["unit"], kind=r["sense"])
    # A15 (iteration 3.1): bus sag and cell current at end of life, low-SOC open-circuit voltage 3.45 V, DCIR x 1.5
    rs = sd["results"]
    bt = sd["battery"]
    Rc = bt["cell"]["dcir_ohm"] * 1.5
    npk = bt["independent_packs"]
    ncell = bt["series"] * bt["parallel"]

    def sag(P_kw, ncells):
        p_ = P_kw * 1e3 / ncells
        disc = 3.45**2 - 4 * Rc * p_
        if disc < 0:
            return 999.0, 0.0
        i_ = (3.45 - math.sqrt(disc)) / (2 * Rc)
        return i_, bt["series"] * (3.45 - i_ * Rc)
    i1, v1 = sag(rs["hover_electrical_power_kw"] - sd["aux_power_kw"], ncell * (npk - 1) / npk)
    check("A15a", "one pack out (land immediately, 500 m ISA+15, aux shed): cell current <= P50B 60 A (EOL resistance)", i1, bt["cell"]["max_peak_discharge_a"], 0, "A", kind="le")
    check("A15b", "one pack out (land immediately, 500 m ISA+15, aux shed): bus voltage under load >= 400 V", v1, 400.0, 0, "V", kind="ge")
    eta_d3 = 0.93 * 0.97 * 0.98
    P_fl = (rs["rotor_out_flare_shaft_power_kw"] + rs["hover_shaft_power_per_motor_kw"] * (lr["count"] - 2)) / eta_d3 + sd["aux_power_kw"]
    i2, v2 = sag(P_fl, ncell)
    check("A15c", f"all packs, one-motor-out {rs['rotor_out_flare_load_factor_g']} g flare: cell current <= 60 A", i2, bt["cell"]["max_peak_discharge_a"], 0, "A", kind="le")
    check("A15d", f"all packs, one-motor-out {rs['rotor_out_flare_load_factor_g']} g flare: bus voltage under load >= 400 V", v2, 400.0, 0, "V", kind="ge")
    check("A16", "pusher cruise shaft power x 1.10 <= continuous rating (10 % margin)", (rs["cruise_electrical_power_kw"] - sd["aux_power_kw"]) * eta_d3 * 1.10,
          sd["pusher"]["motor"]["continuous_power_kw"], 0, "kW", kind="le")
    # C: calibration bookkeeping (design/mass_calibration.json)
    cal = json.loads((ROOT / "design" / "mass_calibration.json").read_text())
    tot_after = sum(v for k, v in cal["group_mass_after_reductions_kg"].items() if k not in ("payload", "battery"))
    check("C1", "calibration: CAD empty (excl. battery, payload, growth) - adopted reductions = sum of calibrated groups",
          tot_after, cal["cad_iteration1"]["empty_kg"] - 23.742 - cal["reductions_total_kg"], 0.002, "kg")
    Vs_hot = math.sqrt(2 * Wt / (float(ph.isa(500, 15)["rho"]) * sd["wing"]["area_m2"] * sd["wing"]["cl_max"]))
    check("A12b", "cruise speed / stall (TAS, 500 m ISA+15) >= 1.15 (iteration 3.2; was 1.3)", mi["cruise_speed_kmh"] / 3.6 / Vs_hot, 1.15, 1e-3, kind="ge")
    check("A12c", "cruise speed >= 120 km/h (iteration 3.2; was 135)", mi["cruise_speed_kmh"], 120.0, 0, "km/h", kind="ge")
    return sd, geo


def benchmarks(sd):
    rows = list(csv.DictReader(open(ROOT / "methods" / "benchmarks" / "benchmarks_wide.csv")))
    fits = json.loads((ROOT / "methods" / "benchmarks" / "trend_fits.json").read_text())["empty_fraction_vs_mtow"]
    m = sd["mass_kg"]
    mtow = m["mtow"]
    ef = (m["empty"] + m["battery"]) / mtow
    ef_fit = fits["A"] * mtow ** fits["C"]
    check("B1", "empty fraction incl. battery vs benchmark fit [W3] (+-0.08 scatter)", ef, ef_fit, 0.08, kind="abs")
    pf = m["payload"] / mtow
    pfs = [float(r["payload_fraction"]) for r in rows if r["payload_fraction"]]
    check("B2", "payload fraction within benchmark range", pf, min(pfs), 0, kind="ge")
    DL = sd["results"]["disk_loading_N_m2"]
    PL = mtow * 9.80665 / (sd["results"]["hover_electrical_power_kw"])
    rho5 = float(ph.isa(500, 15)["rho"])
    fdl = sd["lift_rotors"]["download_fraction"]
    P_mt = mtow * 9.80665 * (1 + fdl) ** 1.5 / (sd["lift_rotors"]["figure_of_merit"] * math.sqrt(2 * rho5 / DL)) / 0.884 / 1e3 + 1.5
    check("B3", "hover power loading vs momentum trend [H8] incl. download and aux (electrical)", PL, mtow * 9.80665 / P_mt, 0.01, "N/kW")
    bf = m["battery"] / mtow
    bfs = [float(r["battery_mass_fraction"]) for r in rows if r.get("battery_mass_fraction")]
    # benchmark band +-0.02 (screening: the benchmarks are cruise-sized aircraft; E8-200 packs are sized by hover power and the
    # one-pack-out current limit, iteration 3.3 fraction 0.240 against the highest benchmark 0.233)
    check("B4a", "battery mass fraction >= lowest benchmark - 0.02", bf, min(bfs) - 0.02, 0, kind="ge")
    check("B4b", "battery mass fraction <= highest benchmark + 0.02", bf, max(bfs) + 0.02, 0, kind="le")
    # plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURF, INK2, C1, C2 = "#fcfcfb", "#52514e", "#2a78d6", "#eb6834"
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), dpi=150, facecolor=SURF)
    ax = axs[0]
    xs = [(float(r["mtow"]), float(r["empty_fraction"]), r["aircraft"]) for r in rows if r["mtow"] and r["empty_fraction"]]
    ax.scatter([x[0] for x in xs], [x[1] for x in xs], s=30, color=C1, edgecolor=SURF, label="benchmarks (methods/benchmarks)")
    for x, y, nm in xs:
        ax.annotate(nm.split(" (")[0], (x, y), fontsize=6, color=INK2, xytext=(3, 3), textcoords="offset points")
    mm = np.linspace(200, 4500, 100)
    ax.plot(mm, fits["A"] * mm ** fits["C"], color=INK2, lw=1, label="fit [W3]")
    ax.scatter([mtow], [ef], s=80, marker="P", color=C2, edgecolor=SURF, label="E8-200 selected", zorder=5)
    ax.set_xscale("log")
    ax.set_xlabel("MTOW (kg)")
    ax.set_ylabel("Empty mass incl. battery / MTOW")
    ax.legend(frameon=False, fontsize=7)
    ax = axs[1]
    pts = [(float(r["disk_loading_N_m2"]), float(r["power_loading_N_per_kW"]), r["aircraft"]) for r in rows
           if r["disk_loading_N_m2"] and r["power_loading_N_per_kW"]]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=30, color=C1, edgecolor=SURF, label="benchmarks (installed power)")
    for x, y, nm in pts:
        ax.annotate(nm.split(" (")[0], (x, y), fontsize=6, color=INK2, xytext=(3, 3), textcoords="offset points")
    dl = np.linspace(50, 800, 100)
    ax.plot(dl, 0.72 * np.sqrt(2 * float(ph.isa(500, 15)['rho']) / dl) * 1e3 * 0.884, color=INK2, lw=1, label="[H8] FM 0.72, drive 0.884, 500 m ISA+15")
    ax.scatter([DL], [PL], s=80, marker="P", color=C2, edgecolor=SURF, label="E8-200 hover (electrical)", zorder=5)
    ax.set_xlabel("Disk loading (N/m2)")
    ax.set_ylabel("Power loading (N/kW)")
    ax.legend(frameon=False, fontsize=7)
    for a in axs:
        a.set_facecolor(SURF)
        a.grid(color="#e4e3df", lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "benchmark_comparison.png", facecolor=SURF)


def main():
    unit_tests()
    sd, geo = audit()
    benchmarks(sd)
    n_fail = sum(r["status"] == "FAIL" for r in ROWS)
    lines = ["# Sizing verification report (generated by verify_sizing.py)", "",
             f"**{len(ROWS) - n_fail} PASS, {n_fail} FAIL** of {len(ROWS)} checks.", "",
             "| id | check | value | reference | diff / margin | unit | status |", "|---|---|---|---|---|---|---|"]
    for r in ROWS:
        lines.append(f"| {r['id']} | {r['check']} | {r['value']:.5g} | {r['ref']:.5g} | {r['diff']} | {r['unit']} | {r['status']} |")
    (OUT / "verification_report.md").write_text("\n".join(lines) + "\n")
    (OUT / "verification_report.json").write_text(json.dumps(ROWS, indent=1))
    for r in ROWS:
        print(f"{r['status']:4s} {r['id']:5s} {r['check'][:80]:80s} {r['value']:.5g} vs {r['ref']:.5g} {r['diff']}")
    print(f"{len(ROWS) - n_fail} PASS, {n_fail} FAIL")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
