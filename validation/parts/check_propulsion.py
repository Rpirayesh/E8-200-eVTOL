#!/usr/bin/env python3
"""Consistency check of the shortlisted motor + inverter + rotor combinations (WP P, pass 1).

What is checked, per combination, for a grid of MTOW, rotor count and rotor diameter:
  * hover and one-motor-out (OEI) shaft power, torque and rpm against the motor ratings,
  * rpm against the voltage available (where a KV is published) at the low-SOC bus voltage,
  * DC current against the inverter rating,
  * tip speed / tip Mach,
  * whether a COTS rotor of that diameter exists (from bom/catalog.json suppliers),
  * pusher: continuous and peak shaft power available at a propeller rpm set by tip speed.

Model (momentum theory with figure of merit; constants below are engineering estimates, each with its basis):
  P_hover = T^1.5 / sqrt(2 rho A) / FM, fixed-pitch rotor so T ~ Omega^2, Q ~ Omega^2, P ~ Omega^3.
  Hover tip speed from a blade-loading limit CT/sigma <= CT_SIGMA_MAX with solidity SIGMA (floored at VTIP_MIN).
  These constants are calibrated against the T-Motor NS62x24 bench point (see calibration() below).

This is a screening check for WP P; WP D (sizing) owns the final propulsion numbers.
Run:  python3 validation/parts/check_propulsion.py   (writes results.json next to this file)
"""
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
CAT = json.loads((ROOT / "bom" / "catalog.json").read_text())
ITEM = {i["id"]: i for i in CAT["items"]}

G = 9.80665
R_AIR = 287.053


def isa_density(h_m, dT=0.0):
    T0, p0, L = 288.15, 101325.0, 0.0065
    T_isa = T0 - L * h_m
    p = p0 * (T_isa / T0) ** (G / (R_AIR * L))
    return p / (R_AIR * (T_isa + dT))


RHO_DESIGN = isa_density(1000.0, 15.0)   # hover ceiling case from requirements.yaml (1000 m, ISA+15)
RHO_SL15 = isa_density(0.0, 15.0)
A_SOUND = math.sqrt(1.4 * R_AIR * (288.15 - 0.0065 * 1000 + 15))

# ---- engineering estimates (basis in comments) -----------------------------------------------
FM = 0.70            # figure of merit of a COTS propeller used as a lift rotor; typical 0.6-0.75 (estimate).
DOWNLOAD = 1.05      # +5 % thrust for wing/boom download under the rotors (estimate; WP C to replace).
ETA_MOTOR = 0.92     # motor efficiency at hover point (estimate; EMRAX quotes up to 96 % peak).
ETA_INV = 0.97       # inverter efficiency (estimate).
SIGMA = 0.10         # 2-blade propeller-type rotor solidity (estimate, calibrated below).
CT_SIGMA_MAX = 0.13  # blade-loading limit at hover (estimate, reproduces NS62x24 at 100 kgf).
VTIP_MIN = 140.0     # lowest hover tip speed considered, m/s (estimate).
MACH_TIP_MAX = 0.65  # hover/OEI tip Mach limit for noise and compressibility (estimate).
CONTROL_MARGIN = 1.10  # +10 % thrust on the worst rotor for attitude control after a failure (estimate).
V_CELL_LOW = 3.3     # loaded cell voltage near the 20 % reserve, V (estimate for P50B at 3-5C).
V_CELL_NOM = 3.6     # nominal (datasheet).
V_CELL_MAX = 4.2     # charge voltage (datasheet).
KV_LOAD_FACTOR = 0.79  # rpm/V under load vs no-load KV; from U15XXL bench (2203 rpm at 96 V, KV29).


def oei_factor(n):
    """Worst-rotor thrust multiplier after one lift motor fails.

    Assumes the diametrically opposite rotor is throttled back to restore roll/pitch/yaw balance, so n-2 rotors carry
    the weight (estimate; a conservative screening rule for symmetric hexa/octo layouts)."""
    if n < 6:
        return float("nan")
    return n / (n - 2)


def rotor_hover(mtow_kg, n, D, rho=RHO_DESIGN):
    T = mtow_kg * G * DOWNLOAD / n
    A = math.pi * D ** 2 / 4
    P_ideal = T ** 1.5 / math.sqrt(2 * rho * A)
    P = P_ideal / FM
    vtip_req = math.sqrt(T / (rho * A * SIGMA * CT_SIGMA_MAX))
    vtip = max(vtip_req, VTIP_MIN)
    omega = vtip / (D / 2)
    rpm = omega * 60 / (2 * math.pi)
    Q = P / omega
    k = oei_factor(n) * CONTROL_MARGIN
    return {
        "thrust_N": T, "thrust_kgf": T / G, "disk_loading_N_m2": T / A,
        "P_hover_kW": P / 1e3, "rpm_hover": rpm, "vtip_hover": vtip, "torque_hover_Nm": Q,
        "oei_thrust_ratio": k,
        "P_oei_kW": P * k ** 1.5 / 1e3, "rpm_oei": rpm * math.sqrt(k), "torque_oei_Nm": Q * k,
        "vtip_oei": vtip * math.sqrt(k), "mach_tip_oei": vtip * math.sqrt(k) / A_SOUND,
    }


# ---- component limits (numbers copied from bom/catalog.json items; IDs given) -------------------
MOTORS = {
    # id: cont power kW (lower bound of range), peak kW, cont torque, peak torque, rpm min/max, KV no-load (or None)
    "MOT-REB30": dict(Pc=25, Pp=40, Qc=None, Qp=150, rpm=(1500, 4000), kv=None, Vmin=63),
    "MOT-REB50": dict(Pc=30, Pp=50, Qc=None, Qp=200, rpm=(1500, 4000), kv=None, Vmin=400),
    "MOT-REB90": dict(Pc=60, Pp=80, Qc=None, Qp=300, rpm=(1500, 4000), kv=None, Vmin=400),
    "MOT-EMRAX208": dict(Pc=52, Pp=86, Qc=83, Qp=150, rpm=(0, 7000), kv=25.02),
    "MOT-EMRAX228": dict(Pc=75, Pp=124, Qc=130, Qp=220, rpm=(0, 6500), kv=15.53),
    "MOT-MAD-M90C60": dict(Pc=45, Pp=55.6, Qc=None, Qp=None, rpm=(0, 9999), kv=9.0),
    "MOT-U15XXL": dict(Pc=None, Pp=20.09, Qc=None, Qp=76.97, rpm=(0, 2203), kv=29.0),
}
INVERTERS = {
    # DC voltage max, continuous A, peak/short A (assumed equal when one figure is published), cont/peak kW
    "INV-HBCI100400": dict(Vmax=400, Ic=100, Ip=125, Pc=25, Pp=50),  # Ip: estimate = 50 kW short-time / 400 V
    "INV-HBCI400400": dict(Vmax=400, Ic=400, Ip=400, Pc=160, Pp=200),
    "INV-HBCI400800": dict(Vmax=800, Ic=400, Ip=400, Pc=320, Pp=400),
    "INV-THUNDER300": dict(Vmax=100.8, Ic=150, Ip=300, Pc=None, Pp=None),
}
# COTS rotor coverage (catalog items PROP-*): (supplier, max diameter m for matched CW+CCW)
PROP_COVERAGE = [("E-PROPS UAV (matched CW/CCW)", 1.90), ("Sensenich UAV", 2.48), ("Helix", 2.80)]


def prop_sources(D):
    s = [name for name, dmax in PROP_COVERAGE if D <= dmax + 1e-9]
    if abs(D - 1.575) < 1e-3:
        s.insert(0, "T-Motor NS62x24")
    return s


COMBOS = [
    dict(name="A: REB 30 + HBCi 100400, 8 rotors, 94s bus", motor="MOT-REB30", inv="INV-HBCI100400", n=8,
         series=94, diameters=[1.8, 1.9, 2.0, 2.2]),
    dict(name="B: REB 50 + HBCi 400800, 6 rotors, 180s bus", motor="MOT-REB50", inv="INV-HBCI400800", n=6,
         series=180, diameters=[2.0, 2.2, 2.4, 2.6]),
    dict(name="B8: REB 50 + HBCi 400800, 8 rotors, 180s bus", motor="MOT-REB50", inv="INV-HBCI400800", n=8,
         series=180, diameters=[1.9, 2.2, 2.4]),
    dict(name="D: MAD M90C60 EEE + HBCi 400400, 8 rotors, 94s bus", motor="MOT-MAD-M90C60", inv="INV-HBCI400400",
         n=8, series=94, diameters=[1.8, 1.9, 2.2]),
    dict(name="E: EMRAX 228 MV + HBCi 400400 as lift, 6 rotors, 94s bus", motor="MOT-EMRAX228", inv="INV-HBCI400400",
         n=6, series=94, diameters=[2.0, 2.4]),
]
MTOWS = [500, 600, 700, 800, 900]


def check_combo(c, mtow, D):
    m, inv = MOTORS[c["motor"]], INVERTERS[c["inv"]]
    r = rotor_hover(mtow, c["n"], D)
    Vlow, Vmax = c["series"] * V_CELL_LOW, c["series"] * V_CELL_MAX
    Pe_h = r["P_hover_kW"] / (ETA_MOTOR * ETA_INV)
    Pe_o = r["P_oei_kW"] / (ETA_MOTOR * ETA_INV)
    I_h, I_o = Pe_h * 1e3 / Vlow, Pe_o * 1e3 / Vlow
    fails, notes = [], []
    if m["Pc"] is not None and r["P_hover_kW"] > m["Pc"]:
        fails.append(f"hover power {r['P_hover_kW']:.1f} > cont {m['Pc']} kW")
    if m["Qc"] is not None and r["torque_hover_Nm"] > m["Qc"]:
        fails.append(f"hover torque {r['torque_hover_Nm']:.0f} > cont {m['Qc']} Nm")
    if m["Pp"] is not None and r["P_oei_kW"] > m["Pp"]:
        fails.append(f"OEI power {r['P_oei_kW']:.1f} > peak {m['Pp']} kW")
    if m["Qp"] is not None and r["torque_oei_Nm"] > m["Qp"]:
        fails.append(f"OEI torque {r['torque_oei_Nm']:.0f} > peak {m['Qp']} Nm")
    lo, hi = m["rpm"]
    if r["rpm_hover"] < lo:
        notes.append(f"hover rpm {r['rpm_hover']:.0f} below listed band {lo}")
    if r["rpm_oei"] > hi:
        fails.append(f"OEI rpm {r['rpm_oei']:.0f} > {hi}")
    if m["kv"]:
        rpm_avail = m["kv"] * KV_LOAD_FACTOR * Vlow
        if r["rpm_oei"] > rpm_avail:
            fails.append(f"OEI rpm {r['rpm_oei']:.0f} > {rpm_avail:.0f} available at {Vlow:.0f} V")
    else:
        notes.append("KV not published: winding to be specified by supplier for the bus voltage")
    if m.get("Vmin") and Vlow < m["Vmin"]:
        fails.append(f"bus low {Vlow:.0f} V < motor minimum {m['Vmin']} V")
    if Vmax > inv["Vmax"]:
        fails.append(f"bus max {Vmax:.0f} V > inverter {inv['Vmax']} V")
    if I_h > inv["Ic"]:
        fails.append(f"hover DC current {I_h:.0f} A > inverter cont {inv['Ic']} A")
    if I_o > inv["Ip"]:
        fails.append(f"OEI DC current {I_o:.0f} A > inverter {inv['Ip']} A")
    if inv["Pp"] is not None and Pe_o > inv["Pp"]:
        fails.append(f"OEI electrical {Pe_o:.1f} kW > inverter peak {inv['Pp']} kW")
    if r["mach_tip_oei"] > MACH_TIP_MAX:
        fails.append(f"OEI tip Mach {r['mach_tip_oei']:.2f} > {MACH_TIP_MAX}")
    props = prop_sources(D)
    if not props:
        fails.append("no COTS rotor at this diameter")
    return {
        "combo": c["name"], "mtow_kg": mtow, "n_rotors": c["n"], "D_m": D,
        **{k: round(v, 3) for k, v in r.items()},
        "bus_V_low": round(Vlow, 1), "bus_V_max": round(Vmax, 1),
        "P_elec_hover_kW": round(Pe_h, 2), "P_elec_oei_kW": round(Pe_o, 2),
        "I_dc_hover_A": round(I_h, 1), "I_dc_oei_A": round(I_o, 1),
        "total_hover_elec_kW": round(Pe_h * c["n"], 1),
        "cots_rotor": props, "pass": not fails, "fails": fails, "notes": notes,
    }


def u15xxl_check():
    """U15XXL + NS62x24 against its own bench table (density-corrected)."""
    bench = [  # thrust g, current A, rpm, power W  (T-Motor table at 96-99 V)
        (13633, 11.20, 834, 1104), (19599, 18.15, 996, 1787), (23521, 23.37, 1122, 2299), (27670, 29.22, 1212, 2876),
        (33170, 37.94, 1296, 3727), (40488, 50.66, 1437, 4971), (48312, 65.63, 1560, 6421), (53443, 75.88, 1635, 7414),
        (67606, 109.04, 1800, 10613), (72109, 119.37, 1890, 11591), (76707, 132.01, 1950, 12796),
        (82635, 148.66, 2010, 14390), (88756, 167.53, 2085, 16180), (95211, 188.35, 2130, 18153),
        (101449, 209.09, 2203, 20089)]
    rho_bench = 1.18  # bench air density unknown; estimate for a warm low-altitude test site.

    def interp(tg):
        for (t0, i0, r0, p0), (t1, i1, r1, p1) in zip(bench, bench[1:]):
            if t0 <= tg <= t1:
                f = (tg - t0) / (t1 - t0)
                return i0 + f * (i1 - i0), r0 + f * (r1 - r0), p0 + f * (p1 - p0)
        return None
    rows = []
    for mtow in MTOWS:
        for rho, case in ((RHO_SL15, "SL ISA+15"), (RHO_DESIGN, "1000 m ISA+15")):
            T = mtow * DOWNLOAD / 8 * 1000  # grams-force per rotor, 8 rotors
            Teq = T * rho_bench / rho     # bench thrust giving the same rpm
            k = oei_factor(8) * CONTROL_MARGIN
            h, o = interp(Teq), interp(Teq * k)
            row = {"mtow_kg": mtow, "case": case, "thrust_kgf": round(T / 1000, 1),
                   "bench_equiv_kgf": round(Teq / 1000, 1)}
            if h:
                row.update(hover_current_A=round(h[0], 1), hover_rpm=round(h[1]), hover_elec_kW=round(h[2] * rho / rho_bench / 1e3, 2))
            else:
                row.update(hover_current_A=None, note="hover thrust beyond bench table (>101 kgf)")
            if o:
                row.update(oei_current_A=round(o[0], 1), oei_rpm=round(o[1]))
            else:
                row.update(oei_current_A=None)
            ok = bool(h) and bool(o) and h[0] <= 150 and o[0] <= 209.09
            row["pass"] = ok
            row["fails"] = [] if ok else [
                ("hover beyond bench" if not h else ("hover current > ESC 150 A cont" if h[0] > 150 else "")),
                ("OEI thrust beyond bench max 101.4 kgf (motor coil 184 C after 1 min)" if not o else "")]
            row["fails"] = [f for f in row["fails"] if f]
            rows.append(row)
    return rows


def pusher_check():
    """Shaft power available at a direct-drive pusher rpm set by a static tip speed of 200 m/s (estimate)."""
    rows = []
    for mid in ["MOT-REB50", "MOT-REB90", "MOT-EMRAX208", "MOT-EMRAX228"]:
        m = MOTORS[mid]
        for D in [1.6, 1.75, 1.9]:
            rpm = 200.0 / (D / 2) * 60 / (2 * math.pi)
            w = rpm * 2 * math.pi / 60
            Pc = m["Pc"] if m["Qc"] is None else min(m["Pc"], m["Qc"] * w / 1e3)
            Pp = m["Pp"] if m["Qp"] is None else min(m["Pp"], m["Qp"] * w / 1e3)
            v_cruise = 150 / 3.6
            mach_helical = math.hypot(200.0, v_cruise) / A_SOUND
            rows.append({"motor": mid, "D_m": D, "rpm": round(rpm), "P_cont_avail_kW": round(Pc, 1),
                         "P_peak_avail_kW": round(Pp, 1), "helical_tip_mach_150kmh": round(mach_helical, 3),
                         "meets_40kW_cont": Pc >= 40, "meets_60kW_cont": Pc >= 60, "meets_100kW_peak": Pp >= 100,
                         "cots_prop": prop_sources(D)})
    return rows


def calibration():
    """NS62x24 at 101.4 kgf / 2203 rpm: implied CT and overall hover efficiency vs this model."""
    T = 101.449 * G
    D = 1.575
    A = math.pi * D ** 2 / 4
    vtip = math.pi * D * 2203 / 60
    rho = 1.18
    ct = T / (rho * A * vtip ** 2)
    P_ideal = T ** 1.5 / math.sqrt(2 * rho * A)
    eta_overall = P_ideal / 20089.0
    # 67.6 kgf point (typical hover setting)
    T2 = 67.606 * G
    eta2 = (T2 ** 1.5 / math.sqrt(2 * rho * A)) / 10613.0
    return {"NS62x24_CT_at_max": round(ct, 4), "implied_CT_over_sigma_if_sigma_0.10": round(ct / SIGMA, 3),
            "overall_eta_bench_max(FM*eta_m*eta_esc)": round(eta_overall, 3),
            "overall_eta_bench_67kgf": round(eta2, 3),
            "model_overall_eta(FM*eta_m*eta_inv)": round(FM * ETA_MOTOR * ETA_INV, 3),
            "comment": "Model is more conservative than the bench (bench rho assumed 1.18 kg/m3; stand effects unknown)."}


def battery_rate():
    """C-rate and per-cell current of a P50B pack for a range of pack energies and hover powers."""
    cell_Wh, cell_Ah = 18.0, 5.0  # P50B datasheet
    rows = []
    for E in [40, 60, 80]:
        for P in [150, 200, 300]:
            c = P / E
            rows.append({"pack_kWh": E, "hover_elec_kW": P, "C_rate": round(c, 2),
                         "cell_current_A": round(c * cell_Ah, 1),
                         "one_of_two_packs_out_cell_A": round(2 * c * cell_Ah, 1),
                         "cells": round(E * 1000 / cell_Wh)})
    return rows


def write_tables(res):
    L = ["# Propulsion consistency tables (generated by check_propulsion.py - do not edit)", "",
         f"Design air density {res['_meta']['rho_design']} kg/m3 (1000 m, ISA+15); constants: "
         + ", ".join(f"{k}={v}" for k, v in res['_meta']['constants'].items()), "",
         "## Calibration against T-Motor NS62x24 bench data", ""]
    for k, v in res["calibration"].items():
        L.append(f"- {k}: {v}")
    for c in COMBOS:
        L += ["", f"## {c['name']}", "",
              "| MTOW kg | D m | T/rotor kgf | P hover kW | rpm hover | Q hover Nm | P OEI kW | Q OEI Nm | rpm OEI | tip Mach OEI | I_dc hover A | I_dc OEI A | COTS rotor | result |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in res["combos"]:
            if r["combo"] != c["name"]:
                continue
            res_txt = "PASS" if r["pass"] else "FAIL: " + "; ".join(r["fails"])
            if r["notes"]:
                res_txt += " (note: " + "; ".join(r["notes"]) + ")"
            L.append(f"| {r['mtow_kg']} | {r['D_m']:.2f} | {r['thrust_kgf']:.1f} | {r['P_hover_kW']:.1f} | {r['rpm_hover']:.0f} | "
                     f"{r['torque_hover_Nm']:.0f} | {r['P_oei_kW']:.1f} | {r['torque_oei_Nm']:.0f} | {r['rpm_oei']:.0f} | "
                     f"{r['mach_tip_oei']:.2f} | {r['I_dc_hover_A']:.0f} | {r['I_dc_oei_A']:.0f} | {', '.join(r['cots_rotor']) or 'none'} | {res_txt} |")
    L += ["", "## T-Motor U15XXL + NS62x24 against its own bench table (8 rotors)", "",
          "| MTOW kg | case | T/rotor kgf | bench-equivalent kgf | hover A | hover rpm | OEI A | result |", "|---|---|---|---|---|---|---|---|"]
    for r in res["u15xxl_bench"]:
        L.append(f"| {r['mtow_kg']} | {r['case']} | {r['thrust_kgf']} | {r['bench_equiv_kgf']} | {r.get('hover_current_A')} | "
                 f"{r.get('hover_rpm', '-')} | {r.get('oei_current_A')} | {'PASS' if r['pass'] else 'FAIL: ' + '; '.join(r['fails'])} |")
    L += ["", "## Pusher: shaft power available in direct drive (static tip speed 200 m/s)", "",
          "| motor | D m | rpm | P cont avail kW | P peak avail kW | helical tip Mach at 150 km/h | >=40 kW cont | >=60 kW cont |", "|---|---|---|---|---|---|---|---|"]
    for r in res["pusher"]:
        L.append(f"| {r['motor']} | {r['D_m']} | {r['rpm']} | {r['P_cont_avail_kW']} | {r['P_peak_avail_kW']} | {r['helical_tip_mach_150kmh']} | "
                 f"{'yes' if r['meets_40kW_cont'] else 'no'} | {'yes' if r['meets_60kW_cont'] else 'no'} |")
    L += ["", "## Battery C-rate with Molicel P50B (18 Wh, 5 Ah, 60 A cell)", "",
          "| pack kWh | hover electrical kW | C-rate | cell A | cell A with one of two packs out | cells |", "|---|---|---|---|---|---|"]
    for r in res["battery_rate"]:
        L.append(f"| {r['pack_kWh']} | {r['hover_elec_kW']} | {r['C_rate']} | {r['cell_current_A']} | {r['one_of_two_packs_out_cell_A']} | {r['cells']} |")
    fd = res["final_design"]
    L += ["", "## Final design (frozen): propulsion set from design/selected_design.json", "",
          "| motor rating set | point | shaft kW | limit kW | torque N m | limit N m | rpm | thrust N | power margin | torque margin | result |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fd["rotor_points"]:
        L.append(f"| {r['rating_set']} | {r['point']} | {r['P_kW']} | {r['P_limit_kW']} | {r['Q_Nm']} | {r['Q_limit_Nm']} | {r['rpm']} | "
                 f"{r['thrust_N']} | {r['power_margin']:+.1%} | {r['torque_margin']:+.1%} | {'PASS' if r['pass_'] else 'FAIL'} |")
    L += ["", "| bus case | OCV V | bus A | loaded V | A per cell |", "|---|---|---|---|---|"]
    for k, v in fd["bus"].items():
        L.append(f"| {k} | {v['V_ocv']} | {v['I_bus_A']} | {v['V_loaded']} | {v['I_cell_A']} |")
    L += ["", "| check | value |", "|---|---|"]
    for sec in ("winding", "inverter", "axial_load", "lift_rotor", "independent_hover_check", "pusher"):
        for k, v in fd[sec].items():
            L.append(f"| {sec}: {k} | {v} |")
    (OUT / "results_tables.md").write_text("\n".join(L) + "\n")


# ================================================================================================ final design (pass 2)
def final_design_check():
    """Consistency of the frozen propulsion set (design/selected_design.json) against the published motor ratings."""
    D = json.loads((ROOT / "design" / "selected_design.json").read_text())
    lr, res, bat, pu = D["lift_rotors"], D["results"], D["battery"], D["pusher"]
    case = D["loading_cases"]["pilot + passenger (MTOW)"]
    reb = ITEM["MOT-REB60"]["ratings"]
    lift_id = lr["motor"]["name"].split(":")[0].strip()
    if lift_id == "MOT-EMRAX268":
        # EMRAX 268 datasheet v1.7 (catalog): LC continuous 91 kW / 205 N m, peak 210 kW (30 s) / 500 N m, limit 4,500 rpm
        sets = {"EMRAX 268 MV datasheet, liquid cooled": dict(Pp=210.0, Pc=91.0, Qp=500.0, Qc=205.0)}
        kv_pub, axial_max = 8.68, None
    else:
        sets = {
            "summary block (used by WP D)": dict(Pp=60.0, Pc=35.0, Qp=250.0, Qc=None),
            "detailed table, 25 C": dict(Pp=float(reb["table_25C_peak_power_kW"]), Pc=float(reb["table_25C_cont_power_kW"]),
                                         Qp=float(reb["table_25C_peak_torque_Nm"]), Qc=float(reb["table_25C_cont_torque_Nm"])),
        }
        kv_pub, axial_max = float(reb["table_kv_no_load_rpm_per_V"]), reb["max_axial_load_N"]
    # independent momentum-theory hover check with the WP D rotor constants
    rho_h = isa_density(D["environment"]["hover_ceiling_m"], D["environment"]["hover_isa_offset_C"])
    W = D["mass_kg"]["mtow"] * G
    D_r, n = lr["diameter_m"], lr["count"]
    A = math.pi * D_r ** 2 / 4
    T = W * (1 + lr["download_fraction"]) / n
    P_h = T ** 1.5 / math.sqrt(2 * rho_h * A) / lr["figure_of_merit"] / 1e3
    rpm_h = lr["tip_speed_hover_ms"] / (D_r / 2) * 60 / (2 * math.pi)
    Q_h = res["hover_shaft_power_per_motor_kw"] * 1e3 / (rpm_h * 2 * math.pi / 60)   # WP D hover power at the hover rpm
    pts = {
        "hover (1000 m ISA+15)": dict(P=res["hover_shaft_power_per_motor_kw"], Q=Q_h, rpm=rpm_h, T=T, cont=True),
        "one motor out, 1.0 g (1000 m)": dict(P=case["oei_shaft_power_kw_1000m"], Q=case["oei_torque_Nm_1000m"], rpm=case["oei_rpm"],
                                              T=case["oei_max_thrust_N"], cont=False),
        "one motor out, flare (500 m)": dict(P=case["oei_flare_shaft_power_kw_500m"], Q=case["oei_flare_torque_Nm_500m"],
                                                   rpm=case["oei_flare_rpm"], T=case["oei_flare_max_thrust_N"], cont=False),
    }
    rows = []
    for rname, r in sets.items():
        for pname, pt in pts.items():
            lim_P = r["Pc"] if pt["cont"] else r["Pp"]
            lim_Q = (r["Qc"] if r["Qc"] is not None else r["Qp"]) if pt["cont"] else r["Qp"]
            rows.append(dict(rating_set=rname, point=pname, P_kW=round(pt["P"], 1), P_limit_kW=lim_P, Q_Nm=round(pt["Q"], 1),
                             Q_limit_Nm=lim_Q, rpm=round(pt["rpm"]), thrust_N=round(pt["T"]),
                             power_margin=round(lim_P / pt["P"] - 1, 3), torque_margin=round(lim_Q / pt["Q"] - 1, 3),
                             pass_=bool(pt["P"] <= lim_P and pt["Q"] <= lim_Q)))
    # bus voltage with sag (P50B DCIR 12.8 mOhm), low SOC open-circuit 3.45 V/cell (estimate)
    ns, npp, npk = bat["series"], bat["parallel_per_pack"], bat["independent_packs"]
    R_pack = ns * bat["cell"]["dcir_ohm"] / npp
    P_bus = res["hover_electrical_power_ceiling_kw"] * 1e3
    volt = {}
    for label, packs in (("all packs", npk), ("one pack out", npk - 1)):
        R = R_pack / packs
        V_ocv = ns * 3.45
        I = (V_ocv - math.sqrt(max(V_ocv ** 2 - 4 * R * P_bus, 0))) / (2 * R)
        volt[label] = dict(V_ocv=round(V_ocv, 1), I_bus_A=round(I, 1), V_loaded=round(V_ocv - I * R, 1),
                           I_cell_A=round(I / (packs * npp), 1))
    V_min = volt["one pack out"]["V_loaded"]
    rpm_need = pts["one motor out, flare (500 m)"]["rpm"]
    kv_min = rpm_need / (V_min * KV_LOAD_FACTOR)
    kv_bemf = 4000.0 / 800.0     # back-EMF at the 4,000 rpm limiting speed must stay below the 800 V inverter rating
    inv_I = pts["one motor out, flare (500 m)"]["P"] / (D["efficiencies"]["motor"] * D["efficiencies"]["inverter"]) * 1e3 / V_min
    a_snd = math.sqrt(1.4 * R_AIR * (288.15 - 0.0065 * 500 + 15))
    tip_flare = math.pi * D_r * rpm_need / 60
    # pusher (one or two units)
    n_pu = pu.get("count", 1)
    P_cr_shaft = (res["cruise_electrical_power_kw"] - D["aux_power_kw"]) * D["efficiencies"]["motor"] * D["efficiencies"]["inverter"] * D["efficiencies"]["wiring"] / n_pu
    w_p = pu["rpm_cruise"] * 2 * math.pi / 60
    tip_p = math.pi * pu["diameter_m"] * pu["rpm_cruise"] / 60
    V_cr = D["mission"]["cruise_speed_kmh"] / 3.6
    a_cr = math.sqrt(1.4 * R_AIR * (288.15 - 0.0065 * D["environment"]["cruise_altitude_m"] + 15))
    pm = pu["motor"]
    pc_unit = pm["continuous_power_kw"] / n_pu
    tq_unit = pm["max_torque_nm"] / n_pu
    out = dict(
        rotor_points=rows, bus=volt, battery=dict(series=ns, parallel=bat["parallel"], packs=npk, R_pack_ohm=round(R_pack, 3),
                                                   cell_limit_A="60 (P50B, 80 C cut-off) / 40 (WP D continuous screen)"),
        winding=dict(motor=lift_id, V_min_loaded=V_min, rpm_required=round(rpm_need), kv_noload_min=round(kv_min, 2),
                     published_kv_noload=kv_pub, V_bus_max=round(ns * 4.2, 1),
                     no_load_rpm_at_V_max=round(kv_pub * ns * 4.2),
                     verdict=(f"published KV {kv_pub} rpm/V meets the minimum {kv_min:.1f}; no-load speed at full charge "
                              f"{kv_pub * ns * 4.2:.0f} rpm exceeds the 4,500 rpm limit - inverter speed limit / field-weakening and an EMRAX winding check for the {ns}s bus are required"
                              if lift_id == "MOT-EMRAX268" else
                              f"specify KV >= {kv_min:.1f} rpm/V (no load); the {kv_pub} rpm/V table winding is not usable on the {ns}s bus")),
        inverter=dict(I_dc_oei_flare_A=round(inv_I, 1), HBCi400800_A=400, V_bus_max=round(ns * 4.2, 1), V_inverter_max=800,
                      pass_=bool(inv_I <= 400 and ns * 4.2 <= 800)),
        axial_load=dict(flare_thrust_N=round(pts["one motor out, flare (500 m)"]["T"]), motor_max_axial_N=axial_max if axial_max else "not published (EMRAX quote)",
                        margin=round(axial_max / pts["one motor out, flare (500 m)"]["T"] - 1, 3) if axial_max else None),
        lift_rotor=dict(D_m=D_r, matched_max_m=1.90, power_rating_2blade_kW=86, P_max_kW=pts["one motor out, flare (500 m)"]["P"],
                        tip_hover_ms=lr["tip_speed_hover_ms"], tip_flare_ms=round(tip_flare, 1), mach_flare=round(tip_flare / a_snd, 3)),
        independent_hover_check=dict(P_shaft_kW_momentum=round(P_h, 2), P_shaft_kW_WP_D=res["hover_shaft_power_per_motor_kw"],
                                     rpm=round(rpm_h), thrust_N=round(T)),
        pusher=dict(units=n_pu, motor=pm["name"], P_cruise_shaft_kW_per_unit=round(P_cr_shaft, 1), torque_Nm_per_unit=round(P_cr_shaft * 1e3 / w_p, 1),
                    rpm=round(pu["rpm_cruise"]), cont_rating_assumed_kW=pc_unit, margin_vs_assumed=round(pc_unit / P_cr_shaft - 1, 3),
                    peak_torque_assumed_Nm=tq_unit,
                    rating_basis="MGM REB 90 page: 60-70 kW max continuous, 300 N m, no torque-speed curve published (quote item 2)",
                    cont_torque_implied_at_cruise_rpm_Nm=round(pc_unit * 1e3 / w_p, 1),
                    helical_tip_mach=round(math.hypot(tip_p, V_cr) / a_cr, 3), prop=f"{pu['propeller']} {pu['diameter_m']} m {pu['blades']}-blade",
                    prop_availability=("same rotation, " + ("within" if pu["diameter_m"] / 0.0254 <= 82 else "beyond") + " the published CW range (82 in)"),
                    axial_thrust_max_N=json.loads((ROOT / "design" / "geometry.json").read_text())["pusher"].get("max_thrust_N")),
    )
    return out


def main():
    combos = []
    for c in COMBOS:
        for mtow in MTOWS:
            for D in c["diameters"]:
                combos.append(check_combo(c, mtow, D))
    res = {
        "_meta": {"generator": "validation/parts/check_propulsion.py", "rho_design": round(RHO_DESIGN, 4),
                  "rho_sl_isa15": round(RHO_SL15, 4), "a_sound_design": round(A_SOUND, 1),
                  "constants": {"FM": FM, "DOWNLOAD": DOWNLOAD, "ETA_MOTOR": ETA_MOTOR, "ETA_INV": ETA_INV,
                                "SIGMA": SIGMA, "CT_SIGMA_MAX": CT_SIGMA_MAX, "VTIP_MIN": VTIP_MIN,
                                "MACH_TIP_MAX": MACH_TIP_MAX, "CONTROL_MARGIN": CONTROL_MARGIN,
                                "V_CELL_LOW": V_CELL_LOW, "KV_LOAD_FACTOR": KV_LOAD_FACTOR}},
        "calibration": calibration(),
        "combos": combos,
        "u15xxl_bench": u15xxl_check(),
        "pusher": pusher_check(),
        "battery_rate": battery_rate(),
        "final_design": final_design_check(),
    }
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    write_tables(res)

    # console summary
    print("calibration:", res["calibration"])
    for c in COMBOS:
        print("\n" + c["name"])
        print(" MTOW  D    T/kgf  Ph/kW rpm_h  Qh/Nm  Poei/kW Qoei/Nm rpm_o Mo   I_h  I_o  pass")
        for r in combos:
            if r["combo"] != c["name"]:
                continue
            print(f" {r['mtow_kg']:4d} {r['D_m']:.2f} {r['thrust_kgf']:6.1f} {r['P_hover_kW']:5.1f} {r['rpm_hover']:5.0f}"
                  f" {r['torque_hover_Nm']:6.0f} {r['P_oei_kW']:7.1f} {r['torque_oei_Nm']:6.0f} {r['rpm_oei']:5.0f}"
                  f" {r['mach_tip_oei']:.2f} {r['I_dc_hover_A']:5.0f} {r['I_dc_oei_A']:4.0f}  {'OK' if r['pass'] else 'FAIL: ' + '; '.join(r['fails'])}")
    print("\nU15XXL bench check")
    for r in res["u15xxl_bench"]:
        print(" ", r)
    print("\npusher")
    for r in res["pusher"]:
        print(" ", r)


if __name__ == "__main__":
    main()
