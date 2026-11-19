#!/usr/bin/env python3
"""WP V - final independent hand checks of the frozen E8-200 design (iteration 3.3, "ALL_rpmfree").

The design: 8 x 1.85 m lift rotors on EMRAX 268 motors, twin REB 90 boom-tail pushers at 2,074 rpm, an 8.0 x 1.15 m wing,
4 packs of 175s5p P50B, cruise 167 km/h, a GRS 6 1200-1390 parachute.

Every number here is recomputed from first principles: momentum theory, actuator disc with wake fraction and thrust
deduction, the CFD polar itself, the exact cell I-R model, elementary beam theory, a neutral-point build-up and a
learning curve. The inputs are the frozen design files, the CFD results and published data. No code from sizing/ is
imported. From methods/ only the WP M atmosphere, the rotor-out linear programme and the WP M checker are used; WP M
wrote them independently of WP D.

Outputs in this folder: results.json, results.md and benchmark_comparison.png. The script also refreshes the generated
blocks of validation/README.md (between the <!-- gen:... --> markers).

Run from the project root, memory-capped:
  systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 ~/tools/cadenv/bin/python validation/independent/check_final.py
Options: --no-readme (do not touch validation/README.md); --cutoff ISO-time (CAD freshness cut-off).
The iteration-3.2 record is kept in iteration32/.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "methods"))
import check_design as wpm  # noqa: E402  (WP M, independent of WP D)

G0 = 9.80665
RHO_SL = 1.225

# CAD evidence written before this time predates the final 3.3 CAD build and is shown as provisional.
DEFAULT_CUTOFF = "2026-11-19T00:00:00"
CFD_DIR = "cfd/results/iteration33"

# Published / reference inputs of the hand checks (independent of WP D's model unless stated)
REF = dict(
    fm_benchmark=0.74,          # NASA Lift+Cruise hover FM (methods/benchmarks/benchmarks.csv, S18)
    k_ctrl=0.10,                # requirement: 10 % control margin on the most loaded rotor
    prop_profile=0.90,          # eta_p / actuator-disc ideal, McCormick ch. 6 (methods EQUATIONS [P2])
    eta_motor=0.93, eta_inv=0.97, eta_wire=0.98,
    aux_kw=1.5,
    v_oc_mid=3.60,              # P50B nominal (mid-SOC) open-circuit voltage
    v_oc_low=3.45,              # open-circuit voltage at the 20 % landing reserve (WP P estimate)
    dcir_eol_factor=1.5,        # cell resistance growth to end of life (common EOL criterion range 1.5-2.0)
    i_cont_cell=40.0, i_peak_cell=60.0,
    f_eol=0.80, f_res=0.20, dC=0.3,
    clmax_2d=1.74,              # LS(1)-0417 clean section clmax at Re 2.4-4.3e6 (CFD 1.736-1.75; TN D-7428 1.80)
    k_3d=0.90,                  # 3-D CLmax / 2-D clmax, unswept rectangular wing (Raymer 12.4.4)
    fus_kf_per_deg=0.012,       # Raymer fig. 16.14, quarter-chord at about 46 % of the fuselage length
    eta_tail=0.90,              # tail dynamic-pressure ratio
    parachute_rating_kg=1390.0, parachute_shock_kN=57.4,   # Galaxy GRS 6 1200-1390 SDS/FF (galaxysky.cz p45)
    labour_learning=0.85,       # 85 % Wright learning curve (methods EQUATIONS [C])
)

# Published motor ratings (bom/catalog.json, with sources)
EMRAX = dict(p_cont=91.0, q_cont=205.0, p_peak=210.0, q_peak=500.0, rpm_limit=4500.0, peak_time_s=30.0,
             src="EMRAX 268 MV LC datasheet v1.7 (bom/catalog.json MOT-EMRAX268)")
REB90 = dict(p_cont=60.0, p_peak=80.0, q_peak=300.0, q_cont=None,
             src="MGM REB 90 page: 80 kW peak, 60-70 kW continuous, 300 N m (bom/catalog.json MOT-REB90); continuous torque not published")

TOL_FLAG, TOL_FAIL = 0.05, 0.20       # comparison rows
THIN = 0.02                           # limit rows: |margin| < 2 % is FLAG (inside hand-calculation accuracy)


# ============================================================================== helpers
def jload(p):
    return json.loads((ROOT / p).read_text())


def mtime(p):
    q = ROOT / p
    return dt.datetime.fromtimestamp(q.stat().st_mtime) if q.exists() else None


def cad_is_fresh(cutoff: dt.datetime) -> bool:
    """CAD evidence counts as final only when the audit (written last by cad/build.py) is newer than the cut-off and
    not older than the mass properties, i.e. the rebuild has finished."""
    au, mp = mtime("validation/cad/mass_cg_audit.json"), mtime("cad/mass_properties.json")
    return bool(au and mp and au >= cutoff and au >= mp - dt.timedelta(minutes=10))


def yaml_scalar(text: str, key: str, block: str | None = None):
    """Minimal reader for 'key: value  # comment' lines (requirements.yaml has no nested lists for these)."""
    if block:
        i = text.find(block + ":")
        text = text[i:] if i >= 0 else ""
    m = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", text, re.M)
    if not m:
        return None
    v = m.group(1).strip().strip('"')
    try:
        return float(v)
    except ValueError:
        return v


ROWS: list[dict] = []


def compare(cid, group, quantity, mine, design, unit, method, note="", design_conservative_if="none"):
    """Independent value vs design value. design_conservative_if: 'higher' / 'lower' / 'none'."""
    diff = (mine - design) / abs(design) if design else float("nan")
    mag = abs(diff)
    if mag <= TOL_FLAG:
        v = "PASS"
    elif mag <= TOL_FAIL:
        v = "FLAG"
    else:
        cons = (design_conservative_if == "higher" and design > mine) or (design_conservative_if == "lower" and design < mine)
        v = "FLAG" if cons else "FAIL"
    r = dict(id=cid, group=group, kind="compare", quantity=quantity, independent=mine, design=design, unit=unit,
             diff_pct=100 * diff, verdict=v, method=method, note=note)
    ROWS.append(r)
    return r


def limit(cid, group, quantity, value, lim, unit, sense="<=", method="", note="", design=None):
    """Requirement / rating check on the independent value. margin > 0 means the limit is met."""
    margin = (lim / value - 1) if sense == "<=" else (value / lim - 1)
    v = "PASS" if margin >= THIN else ("FLAG" if margin > -THIN else "FAIL")
    r = dict(id=cid, group=group, kind="limit", quantity=quantity, independent=value, limit=lim, sense=sense,
             unit=unit, margin_pct=100 * margin, verdict=v, method=method, note=note, design=design)
    if design is not None:
        r["diff_pct"] = 100 * (value - design) / abs(design) if design else None
    ROWS.append(r)
    return r


def info(cid, group, quantity, value, unit, note="", verdict="INFO"):
    r = dict(id=cid, group=group, kind="info", quantity=quantity, independent=value, unit=unit, verdict=verdict, note=note)
    ROWS.append(r)
    return r


def pending(cid, group, quantity, note):
    r = dict(id=cid, group=group, kind="pending", quantity=quantity, verdict="PENDING", note=note)
    ROWS.append(r)
    return r


def cell_current(p_cell_w, v_oc, r):
    """Cell current and terminal voltage for a power demand (exact I-R model). None if beyond max power."""
    disc = v_oc ** 2 - 4 * r * p_cell_w
    if disc < 0:
        return None, None
    i = (v_oc - math.sqrt(disc)) / (2 * r)
    return i, v_oc - i * r


# ============================================================================== checks
def run_checks(cutoff: dt.datetime) -> dict:
    d = jload("design/selected_design.json")
    g = jload("design/geometry.json")
    cfd = jload(f"{CFD_DIR}/summary.json")
    res = d["results"]
    out: dict = {"inputs": {}, "computed": {}}
    C = out["computed"]

    mtow = d["mass_kg"]["mtow"]
    W = mtow * G0
    site, ceil = wpm.isa(500.0, 15.0), wpm.isa(1000.0, 15.0)
    rho_h, rho_c = site["rho"], ceil["rho"]
    C.update(rho_500=rho_h, rho_1000=rho_c)
    eta_d = REF["eta_motor"] * REF["eta_inv"] * REF["eta_wire"]

    # ------------------------------------------------------------------ 1. hover
    lr = d["lift_rotors"]
    n, D = lr["count"], lr["diameter_m"]
    R = D / 2
    A = math.pi * R ** 2
    dl = cfd["hover"]["corrected_download_fraction"]
    T_h = W * (1 + dl) / n
    compare("H1", "hover", "disk loading W/(N A)", W / (n * A), res["disk_loading_N_m2"], "N/m2", "W / (8 pi R^2)")
    compare("H1b", "hover", "hover download fraction (CFD 3.3 corrected)", dl, lr["download_fraction"], "-",
            f"{CFD_DIR}/summary.json hover.corrected_download_fraction")
    P_h = T_h ** 1.5 / math.sqrt(2 * rho_h * A) / REF["fm_benchmark"] / 1e3
    compare("H2", "hover", "hover shaft power per motor, 500 m ISA+15", P_h, res["hover_shaft_power_per_motor_kw"], "kW",
            "momentum theory, FM 0.74 (NASA L+C benchmark), CFD 3.3 download",
            note=f"design uses FM {lr['figure_of_merit']:.3f}")
    P_h_el = n * P_h / eta_d + REF["aux_kw"]
    compare("H3", "hover", "hover electrical power, 500 m", P_h_el, res["hover_electrical_power_kw"], "kW",
            "8 x shaft / (0.93 x 0.97 x 0.98) + 1.5 kW aux")
    P_h_c = P_h * math.sqrt(rho_h / rho_c)
    P_h_el_c = n * P_h_c / eta_d + REF["aux_kw"]
    compare("H4", "hover", "hover electrical power, 1000 m ceiling", P_h_el_c, res["hover_electrical_power_ceiling_kw"], "kW",
            "P ~ rho^-1/2 at constant thrust")
    vtip = lr["tip_speed_hover_ms"]
    om_h = vtip / R
    Q_h = P_h * 1e3 / om_h          # fixed pitch at constant thrust: Q is independent of density
    om_h_c = om_h * math.sqrt(rho_h / rho_c)
    mtip = vtip / site["a"]
    compare("H5", "hover", "hover tip Mach, 500 m ISA+15", mtip, res["tip_mach_hover"], "-", "V_tip / a")
    limit("H6", "hover", "hover tip Mach <= 0.55 (noise screen)", mtip, 0.55, "-")
    limit("M1", "motor rating", "hover shaft power at 1000 m <= EMRAX 268 LC continuous 91 kW", P_h_c, EMRAX["p_cont"], "kW", note=EMRAX["src"])
    limit("M2", "motor rating", "hover torque <= EMRAX 268 LC continuous 205 N m", Q_h, EMRAX["q_cont"], "N m",
          note=f"fixed pitch: Q at the ceiling equals Q at 500 m ({om_h_c * 30 / math.pi:.0f} rpm at 1000 m); WP P quotes 202 N m (+1.6 %), sizing 0.1 %")
    C.update(T_hover_N=T_h, P_hover_kw=P_h, Q_hover_Nm=Q_h, rpm_hover=om_h * 30 / math.pi)

    # ------------------------------------------------------------------ 2. one motor out and flare
    cg = g["cg_mtow_m"]
    rot = g["lift_rotors"]
    pos = np.array([[r["hub"][0] - cg[0], r["hub"][1] - cg[1]] for r in rot])
    spin = np.array([r["spin"] for r in rot], float)
    k_qt = Q_h / T_h
    worst, worst_name = 0.0, ""
    for f in range(n):
        sol = wpm.rotor_out_allocation(pos, spin, 1.0, k_qt, f)
        if sol and sol[0] > worst:
            worst, worst_name = sol[0], rot[f]["name"]
    ratio = worst * n
    C.update(oei_lp_ratio=ratio, oei_worst_failed=worst_name)
    compare("O1", "one motor out", "worst remaining rotor thrust / mean hover thrust (LP)", ratio,
            d["loading_cases"]["pilot + passenger (MTOW)"]["oei_thrust_ratio_to_hover"], "-",
            "WP M linear programme on geometry.json hubs and spins (Fz, roll, pitch, yaw trimmed)", note=f"worst failed rotor {worst_name}")
    t_oei = ratio * (1 + REF["k_ctrl"])
    Q_oei = Q_h * t_oei
    om_oei = om_h * math.sqrt(t_oei * rho_h / rho_c)
    P_oei = Q_oei * om_oei / 1e3
    compare("O2", "one motor out", "OEI shaft power, worst rotor, 1000 m, +10 % control", P_oei, res["rotor_out_max_shaft_power_kw"],
            "kW", "fixed pitch: T ~ rho n^2, Q ~ T, P = Q x Omega")
    compare("O3", "one motor out", "OEI torque, worst rotor, 1000 m, +10 % control", Q_oei, res["rotor_out_max_torque_nm"], "N m",
            "Q = Q_hover x T/T_hover")
    n_fl = res["rotor_out_flare_load_factor_required_g"]
    t_fl = ratio * n_fl
    Q_fl = Q_h * t_fl
    P_fl = Q_fl * om_h * math.sqrt(t_fl) / 1e3
    T_fl = T_h * t_fl
    compare("O4", "one motor out", f"flare {n_fl:.2f} g one motor out, shaft power, 500 m", P_fl, res["rotor_out_flare_shaft_power_kw"], "kW", "as O2 at 500 m")
    compare("O5", "one motor out", f"flare {n_fl:.2f} g one motor out, torque, 500 m", Q_fl, res["rotor_out_flare_torque_nm"], "N m", "as O3")
    limit("M3", "motor rating", "OEI power <= EMRAX peak 210 kW", P_oei, EMRAX["p_peak"], "kW", design=res["rotor_out_max_shaft_power_kw"])
    limit("M4", "motor rating", "OEI torque <= EMRAX peak 500 N m", Q_oei, EMRAX["q_peak"], "N m", design=res["rotor_out_max_torque_nm"])
    limit("M5", "motor rating", "flare torque <= EMRAX peak 500 N m", Q_fl, EMRAX["q_peak"], "N m", design=res["rotor_out_flare_torque_nm"])
    info("M6", "motor rating", "OEI torque above the 205 N m continuous rating (time-limited operation)", Q_oei / EMRAX["q_cont"], "x cont.",
         note="the datasheet peak rating is for 30 s; a one-motor-out descent and landing from 30 m lasts longer: EMRAX quote item 2 must give the 300 N m time limit",
         verdict="FLAG")
    rpm_oei = om_oei * 30 / math.pi
    limit("M7", "motor rating", "OEI rpm <= flight-controller cap 2,460 rpm", rpm_oei, 2460.0, "rpm")
    fc_cap = rot[0].get("max_thrust_n") or 2860.0
    limit("M8", "motor rating", "flare thrust on the worst rotor <= flight-controller thrust cap", T_fl, fc_cap, "N")
    C.update(P_oei_kw=P_oei, Q_oei_Nm=Q_oei, rpm_oei=rpm_oei, P_flare_kw=P_fl, Q_flare_Nm=Q_fl, T_flare_N=T_fl)

    # ------------------------------------------------------------------ 3. cruise with the CFD polar
    w = d["wing"]
    S, b = w["area_m2"], w["span_m"]
    AR = b * b / S
    V = d["mission"]["cruise_speed_kmh"] / 3.6
    q = 0.5 * rho_h * V * V
    CL = W / (q * S)
    cr = jload(f"{CFD_DIR}/cruise.json")
    grp = max(cr["groups"].values(), key=lambda gg: len(gg["polar"]))["polar"]
    pol = sorted((p["CL"], p["CD"]) for p in grp)
    cd_pods = cfd.get("inverter_pods_drag_area_m2", 0.0) / S
    CD_cfd = float(np.interp(CL, [p[0] for p in pol], [p[1] for p in pol])) + cd_pods
    Dc = q * S * CD_cfd
    compare("A1", "cruise", "cruise drag at 167 km/h (CFD 3.3 polar interpolated at the cruise CL, + pods)", Dc, res["cruise_drag_N"], "N",
            f"{CFD_DIR}/cruise.json points, linear in CL; the design uses the parabolic fit CD0 0.0764 / e 0.658")
    compare("A2", "cruise", "cruise L/D", W / Dc, res["cruise_LD"], "-", "W / D")
    compare("A3", "cruise", "CD0 incl. pods: CFD fit vs design", cfd["cfd_production_mesh"]["CD0_incl_pods"], d["drag"]["cd0"], "-", f"{CFD_DIR}/summary.json")
    compare("A4", "cruise", "Oswald e: CFD fit vs design", cfd["cfd_production_mesh"]["oswald_e"], w["oswald"], "-", f"{CFD_DIR}/summary.json")
    info("A5", "cruise", "cruise CL", CL, "-", note=f"{CL / w['cl_max']:.0%} of the design CLmax; inside the CFD polar (2-16 deg)", verdict="PASS")
    info("A6", "cruise", "CFD run speed vs frozen cruise speed", 172.0, "km/h",
         note="the 3.3 CFD was run at 172 km/h (CL 1.137); the frozen cruise is 167 km/h (CL 1.20), inside the computed polar")
    C.update(V_cruise=V, q_cruise=q, CL_cruise=CL, CD_cruise=CD_cfd, D_cruise=Dc)

    # ------------------------------------------------------------------ 4. pushers with thrust deduction and wake
    pu = d["pusher"]
    npu, Dp = pu["count"], pu["diameter_m"]
    Ap = math.pi * Dp ** 2 / 4
    t_ded = cfd["pusher"]["thrust_deduction"]
    w_f = cfd["pusher"]["wake_fraction"]

    def prop(Dtot, Vin):
        T = Dtot / (1 - t_ded) / npu
        qa = 0.5 * rho_h * Vin * Vin
        eta = REF["prop_profile"] * 2 / (1 + math.sqrt(1 + T / (qa * Ap)))
        return T, eta, T * Vin / eta / 1e3
    T_p, eta_p, P_p = prop(Dc, V * (1 - w_f))
    _, eta_fs, P_fs = prop(Dc, V)
    compare("P1", "pusher", "propeller efficiency at the wake inflow", eta_p, pu["eta_cruise"], "-", "actuator disc x 0.90, V_a = V (1 - w)")
    om_p = pu["rpm_cruise"] * math.pi / 30
    Q_p = P_p * 1e3 / om_p
    P_cr_el = npu * P_p / eta_d + REF["aux_kw"]
    compare("P2", "pusher", "cruise electrical power", P_cr_el, res["cruise_electrical_power_kw"], "kW",
            "T = D/(1-t)/2, P = T V_a / eta / eta_drive + aux", note=f"t {t_ded:.3f}, w {w_f:.3f} from CFD 3.3")
    limit("P3", "pusher", "pusher shaft power x 1.10 <= REB 90 continuous 60 kW (t and w credited once)", P_p * 1.10, REB90["p_cont"], "kW",
          note="sizing +2.7 %; the CFD table's -1.8 % applied the drag ratio to a figure that already carried the old 4.5 % deduction")
    info("P3b", "pusher", "pusher continuous margin without the wake credit (free-stream inflow, sensitivity)",
         100 * (REB90["p_cont"] / (1.1 * P_fs) - 1), "%", note=f"shaft {P_fs:.1f} kW per pusher")
    limit("P4", "pusher", "pusher cruise torque <= REB 90 peak 300 N m", Q_p, REB90["q_peak"], "N m",
          note=f"at {pu['rpm_cruise']:.0f} rpm; continuous torque at this speed not published (MGM quote item 1)")
    p_pk = min(REB90["p_peak"], REB90["q_peak"] * om_p / 1e3)
    roc = (npu * p_pk * 1e3 * eta_p * (1 - t_ded) / (1 - w_f) - Dc * V) / W
    compare("P5", "pusher", "climb rate at cruise speed, pusher peak (torque-limited)", roc, res["climb_rate_ms"], "m/s",
            "(P_peak eta (1-t)/(1-w) - D V) / W, cruise efficiency")
    limit("P6", "pusher", "climb rate >= 1.0 m/s", roc, 1.0, "m/s", sense=">=")
    hel = math.hypot(om_p * Dp / 2, V) / site["a"]
    limit("P7", "pusher", "pusher helical tip Mach <= 0.70", hel, 0.70, "-")
    C.update(T_pusher_each=T_p, eta_p=eta_p, P_pusher_each_kw=P_p, P_pusher_free_stream_kw=P_fs, Q_pusher_Nm=Q_p, roc=roc)

    # ------------------------------------------------------------------ 5. battery and range
    bt = d["battery"]
    cell = bt["cell"]
    ncell = bt["series"] * bt["parallel"]
    E_nom = ncell * cell["energy_wh"] / 1e3
    compare("B1", "battery", "nominal energy (cells x Wh)", E_nom, bt["energy_nominal_kwh"], "kWh", f"{bt['series']} x {bt['parallel']} x 18 Wh")
    m_b = d["mass_kg"]["battery"]
    info("B2", "battery", "pack specific energy", E_nom * 1e3 / m_b, "Wh/kg",
         note="Pipistrel Velis pack about 177 Wh/kg on 253 Wh/kg cells (EQUATIONS.md)", verdict="PASS")
    r_eol = cell["dcir_ohm"] * REF["dcir_eol_factor"]

    def eta_batt(p_kw, cells=ncell, v=REF["v_oc_mid"]):
        i, vt = cell_current(p_kw * 1e3 / cells, v, r_eol)
        return vt / v if vt else float("nan")
    eb_h, eb_cr = eta_batt(P_h_el), eta_batt(P_cr_el)
    eb_tr = eta_batt(0.5 * (P_h_el + P_cr_el))
    compare("B3", "battery", "battery efficiency in hover (exact I-R, mid SOC, EOL resistance)", eb_h, d["efficiencies"]["battery_hover"], "-",
            "V_terminal / V_oc with I from P = I (V_oc - I R)", note="design: exact sag, landing hover at the low-SOC 3.45 V")
    ms = d["mission"]
    t_h = ms["hover_takeoff_s"] + ms["hover_landing_s"]
    t_tr = ms["transitions"] * ms["transition_each_s"]
    E_h = P_h_el * t_h / 3600 + W * ms["vertical_climb_m"] / eta_d / 3.6e6
    E_tr = 0.5 * (P_h_el + P_cr_el) * t_tr / 3600
    E_cl = W * (500.0 - ms["transition_altitude_m"]) / (eta_p * eta_d) / 3.6e6
    E_fix = E_h / eb_h + E_tr / eb_tr + E_cl / eb_cr
    P_cr_cells = P_cr_el / eb_cr
    E_use = E_nom * REF["f_eol"] * (1 - REF["f_res"])
    rng = (E_use - E_fix) / P_cr_cells * V * 3.6
    E_20 = E_fix + P_cr_cells * 20.0 / (V * 3.6)
    compare("R1", "range", "mission energy at the cells, 20 km", E_20, res["mission_energy_kwh"], "kWh",
            "hover 120 s + vertical climb + 2 x 30 s transitions (mean power) + climb to 500 m + cruise")
    compare("R2", "range", "range capability (EOL 80 %, 20 % reserve), CFD drag, t and w", rng, res["range_km"], "km",
            "(E_usable - E_fixed) / P_cruise x V", design_conservative_if="lower")
    limit("R3", "range", "range >= 20 km", rng, 20.0, "km", sense=">=")
    # low end of the CFD bands (CD0 +23.3 %, e -8 %, download +30 %), same hand method
    bands = jload(f"{CFD_DIR}/mission_check.json")["inputs"]["bands"]
    CD0c, ec = cfd["cfd_production_mesh"]["CD0_incl_pods"], cfd["cfd_production_mesh"]["oswald_e"]
    CDw = CD0c * (1 + bands["cd0"]) + CL * CL / (math.pi * AR * ec * (1 - bands["e"]))
    Dw = q * S * CDw
    _, eta_w, P_w = prop(Dw, V * (1 - w_f))
    P_cr_w = npu * P_w / eta_d + REF["aux_kw"]
    P_h_w = P_h_el * ((1 + dl * (1 + bands["download"])) / (1 + dl)) ** 1.5
    E_fix_w = (P_h_w * t_h / 3600) / eta_batt(P_h_w) + 0.5 * (P_h_w + P_cr_w) * t_tr / 3600 / eta_batt(0.5 * (P_h_w + P_cr_w)) \
        + W * 470.0 / (eta_w * eta_d) / 3.6e6 / eta_batt(P_cr_w)
    rng_w = (E_use - E_fix_w) / (P_cr_w / eta_batt(P_cr_w)) * V * 3.6
    compare("R4", "range", "range at the unfavourable end of the CFD bands", rng_w, jload(f"{CFD_DIR}/mission_check.json")["cfd_worst_band"]["range_km_scaled_to_published"],
            "km", "hand method with CD0 +23 %, e -8 %, download +30 % (CFD 19.0 km was at 172 km/h without t and w)")
    info("R5", "range", "range at the unfavourable band end against 20 km", rng_w, "km",
         note="documented risk (not a requirement case)", verdict="FLAG" if rng_w < 20 else "PASS")
    C.update(eta_batt_hover=eb_h, eta_batt_cruise=eb_cr, E_fixed_kwh=E_fix, E_usable_kwh=E_use, range_km=rng, range_worst_km=rng_w)

    E_eol = E_nom * REF["f_eol"]
    c_h = P_h_el_c / eta_batt(P_h_el_c) / E_eol
    compare("B4", "battery", "hover C-rate at the ceiling (EOL capacity)", c_h, res["c_rate_hover"], "1/h", "P_cells / E_EOL")
    c_lim = REF["i_cont_cell"] / (cell["capacity_ah"] * REF["f_eol"]) - REF["dC"]
    limit("B5", "battery", "hover C-rate <= 40 A continuous / EOL Ah - 0.3 C", c_h, c_lim, "1/h", note="requirement '0.3 C margin'")
    i_all, _ = cell_current(P_h_el_c * 1e3 / ncell, REF["v_oc_low"], r_eol)
    limit("B6", "battery", "hover cell current, all packs, ceiling, low SOC, EOL", i_all, REF["i_peak_cell"], "A")
    npk = bt["independent_packs"]
    cells_1 = ncell * (npk - 1) / npk
    P_1 = n * P_h / eta_d
    i_1, v_1 = cell_current(P_1 * 1e3 / cells_1, REF["v_oc_low"], r_eol)
    limit("B7", "battery", "one pack out: cell current <= 60 A (hover 500 m, aux shed, low SOC, EOL)", i_1, 60.0, "A", design=59.7,
          note="design 59.7 A is the more conservative figure (its hover power is 2 % higher: FM 0.725 vs 0.74)")
    limit("B8", "battery", "one pack out: bus voltage >= 400 V", v_1 * bt["series"], 400.0, "V", sense=">=", design=403.0)
    i_1c, v_1c = cell_current(n * P_h_c / eta_d * 1e3 / cells_1, REF["v_oc_low"], r_eol)
    info("B9", "battery", "one pack out at the 1000 m ceiling (sensitivity)", i_1c if i_1c else float("nan"), "A",
         note=f"bus {v_1c * bt['series']:.0f} V" if v_1c else "beyond the pack maximum power")
    info("B10", "battery", "battery mass fraction (B4 benchmark band of verify_sizing widened by +-0.02)", m_b / mtow, "-",
         note="set by hover power and one-pack-out current, not by cruise energy", verdict="FLAG")
    C.update(i_cell_hover_all=i_all, i_cell_1pack=i_1, v_bus_1pack=v_1 * bt["series"])

    # ------------------------------------------------------------------ 6. stall (1.15 Vs)
    clmax = w["cl_max"]
    cl_hand = REF["k_3d"] * REF["clmax_2d"]
    compare("S1", "stall", "clean CLmax: 0.9 x section clmax vs design", cl_hand, clmax, "-",
            "Raymer 12.4.4 with the validated LS(1)-0417 clmax 1.74", note=f"CFD aircraft 1.714 (not bracketed); design = CFD - 5 %")
    Vs = math.sqrt(2 * W / (RHO_SL * S * clmax))
    compare("S2", "stall", "stall speed EAS, MTOW, design CLmax", Vs, res["stall_speed_ms"], "m/s", "sqrt(2W / (rho0 S CLmax))")
    V_eas = V * math.sqrt(rho_h / RHO_SL)
    limit("S3", "stall", "cruise >= 1.15 Vs with the design CLmax 1.628", V_eas / Vs, 1.15, "-", sense=">=")
    limit("S3b", "stall", "cruise >= 1.15 Vs with the handbook CLmax", V_eas / math.sqrt(2 * W / (RHO_SL * S * cl_hand)), 1.15, "-", sense=">=",
          note="the aircraft CFD (1.714) gives 1.19; the handbook value omits fuselage and tail lift")
    limit("S4", "stall", "cruise speed >= 120 km/h", V * 3.6, 120.0, "km/h", sense=">=")
    C.update(Vs_eas=Vs, V_cruise_eas=V_eas, clmax_hand=cl_hand)

    # ------------------------------------------------------------------ 7. CG and static margin (neutral point build-up)
    cbar = w["mac_m"]
    a_w = 2 * math.pi * AR / (2 + math.sqrt(4 + AR ** 2))
    tl = g["tail"]
    AR_h = tl["span"] ** 2 / tl["area_h_m2"]
    a_t = 2 * math.pi * AR_h / (2 + math.sqrt(4 + AR_h ** 2))
    deps = 2 * a_w / (math.pi * AR)
    x_ac_w = g["wing"]["x_le_root"] + 0.25 * cbar
    Vh = tl["area_h_m2"] * (tl["x_ac"] - x_ac_w) / (S * cbar)
    dx_tail = REF["eta_tail"] * Vh * a_t / a_w * (1 - deps)
    Lf, Wf = g["fuselage"]["length_m"], g["fuselage"]["max_width_m"]
    cma_f = REF["fus_kf_per_deg"] * Wf ** 2 * Lf / (cbar * S) * 180 / math.pi
    x_np = x_ac_w + (dx_tail - cma_f / a_w) * cbar
    sm_hand = (x_np - cg[0]) / cbar
    sm_d = res["static_margin_mtow"]
    compare("SM1", "stability", "neutral point x (wing + tail + fuselage build-up)", x_np, g["neutral_point_x_m"], "m",
            "Helmbold lift slopes, downwash 2a/(pi AR), Raymer fuselage K_f", note=f"CFD {cfd['cfd_production_mesh']['x_neutral_point_m']:.3f} m")
    compare("SM2", "stability", "static margin at MTOW (hand) vs sizing", sm_hand, sm_d, "MAC", "(x_np - x_cg) / c", design_conservative_if="lower")
    compare("SM3", "stability", "static margin: CFD vs sizing", cfd["cfd_production_mesh"]["static_margin"], sm_d, "MAC",
            f"{CFD_DIR}/summary.json (slope dCm/dCL; the Cm level is mesh-sensitive, GCI 475 %)", design_conservative_if="lower")
    au = jload("validation/cad/mass_cg_audit.json")
    limit("SM4", "stability", "static margin with the CAD CG >= 0.05", au["static_margin_cad"], 0.05, "MAC", sense=">=",
          note="validation/cad/mass_cg_audit.json")
    for k_, (case, lc) in enumerate(d["loading_cases"].items(), 1):
        limit(f"SM5-{k_}", "stability", f"static margin, {case}", lc["static_margin"], 0.05, "MAC", sense=">=")
    C.update(x_np_hand=x_np, sm_hand=sm_hand)

    # ------------------------------------------------------------------ 8. footprint
    xs = [r["hub"][0] - r["diameter_m"] / 2 for r in rot] + [r["hub"][0] + r["diameter_m"] / 2 for r in rot]
    xs += [p.get("spinner", {}).get("x_to", p["hub"][0]) for p in g["pushers"]] + [g["fuselage"]["x_nose"], g["fuselage"]["x_tail"]]
    xs += [bm["x_front"] for bm in g["booms"]] + [bm["x_aft"] for bm in g["booms"]]
    length = max(xs) - min(xs)
    width = 2 * max([abs(r["hub"][1]) + r["diameter_m"] / 2 for r in rot] + [b / 2])
    limit("F1", "footprint", "overall length (rotor discs to pusher spinners)", length, 10.5, "m", note="original requirement 9.0 m")
    limit("F2", "footprint", "overall width", width, 10.5, "m")
    C.update(length=length, width=width)

    # ------------------------------------------------------------------ 9. mass: sizing vs CAD
    bd = d["mass_kg"]["breakdown"]
    empty_sum = sum(bd.values())
    compare("W1", "mass", "empty mass = sum of the breakdown", empty_sum, d["mass_kg"]["empty"], "kg", "sum")
    compare("W2", "mass", "MTOW = empty + battery + payload", empty_sum + m_b + d["mass_kg"]["payload"], mtow, "kg", "sum")
    compare("W2b", "mass", "geometry.json mass items = MTOW", sum(m["kg"] for m in g["mass_items"]), mtow, "kg", "sum of mass_items")
    cad_fresh = cad_is_fresh(cutoff)
    cad = jload("cad/mass_properties.json")
    grp_c = {k: v["kg"] for k, v in cad["by_group"].items()}
    growth = bd.get("growth", 0.0)
    cad_mtow = cad["cad_mass_kg"] + growth
    cad_empty = cad_mtow - grp_c.get("battery", 0) - grp_c.get("payload", 0)
    note_c = "" if cad_fresh else "provisional: CAD files older than the cut-off"
    rows_cad = [
        compare("W3", "mass vs CAD", "MTOW, CAD (incl. the design growth allowance)", cad_mtow, mtow, "kg", "cad/mass_properties.json + growth", note=note_c),
        compare("W4", "mass vs CAD", "empty mass excl. battery, CAD (incl. growth)", cad_empty, d["mass_kg"]["empty"], "kg", "CAD", note=note_c),
        compare("W5", "mass vs CAD", "battery, CAD", grp_c.get("battery", 0), m_b, "kg", "CAD", note=note_c),
    ]
    for k in ("wing", "booms", "fuselage", "tail", "landing_gear", "rotor_pylons_mounts", "lift_motors", "pusher_motor", "parachute"):
        if k in grp_c and k in bd:
            rows_cad.append(compare(f"W6-{k}", "mass vs CAD", f"group {k}, CAD", grp_c[k], bd[k], "kg", "CAD", note=note_c,
                                    design_conservative_if="higher"))
    xcad = np.array(cad["cg_mm"]) / 1e3
    # CAD CG at MTOW including the growth allowance at the design CG
    x_cg_cad = (cad["cad_mass_kg"] * xcad[0] + growth * cg[0]) / cad_mtow
    rows_cad.append(compare("W7", "mass vs CAD", "CG x at MTOW, CAD (growth at the design point)", x_cg_cad, cg[0], "m", "CAD", note=note_c))
    rows_cad.append(limit("W8", "mass vs CAD", "CAD MTOW incl. growth <= parachute rating 1,390 kg", cad_mtow, REF["parachute_rating_kg"], "kg", note=note_c))
    if not cad_fresh:
        for rr in rows_cad:
            rr["provisional_verdict"] = rr["verdict"]
            rr["verdict"] = "PENDING"
    C.update(cad_mtow_incl_growth=cad_mtow, cad_fresh=cad_fresh)

    # ------------------------------------------------------------------ 10. wing and boom bending
    fe_path = "fea/results/airframe_final33.json" if (ROOT / "fea/results/airframe_final33.json").exists() else "fea/results/airframe_design.json"
    fe = jload(fe_path)
    lim_n = d["structure"]["limit_load_factor_positive"]
    n_ult = 1.5 * lim_n
    s_half = b / 2
    y = np.linspace(0, s_half, 4001)
    L_half = n_ult * W / 2
    ell = 4 * L_half / (math.pi * s_half) * np.sqrt(np.clip(1 - (y / s_half) ** 2, 0, None))
    lift_s = 0.5 * (ell + L_half / s_half)          # Schrenk, rectangular planform (as the FEA loads module)
    y0 = g["wing"]["root_fittings_y"]
    msk = y >= y0
    boom_items = [m for m in g["mass_items"] if m.get("attach") == "boom_L"]
    m_boom_side = sum(m["kg"] for m in boom_items) + bd["tail"] / 2
    y_boom = abs(g["booms"][0]["y"])
    m_wing_out = bd["wing"] / 2 * (s_half - y0) / s_half
    M_rel = n_ult * G0 * (m_boom_side * (y_boom - y0) + m_wing_out * (s_half - y0) / 2)
    M_root = np.trapezoid(lift_s[msk] * (y[msk] - y0), y[msk]) - M_rel
    fa = fe["cases"]["F A  manoeuvre +n at VA"]["groups"]
    M_fea = fa["spar main"]["M"] + fa["spar rear"]["M"]
    compare("ST1", "structure", "wing ultimate bending at the root fitting, +3.8 g x 1.5 (Schrenk)", M_root / 1e3, M_fea / 1e3, "kN m",
            "Schrenk lift minus the inertia of the boom groups and the outer wing", note=f"FEA {fe_path}, case F A, main + rear spar")
    su = jload("fea/results/sizing_update.json")["wing"]["spars"]
    I_tot, h_main = 0.0, None
    for sp in su:
        sc = min(sp["stations"], key=lambda s_: abs(s_["eta"] - y0 / s_half))["section"]
        a_cap = sc["b_cap"] * sc["t_cap"]
        I_tot += 2 * a_cap * (sc["h"] / 2 - sc["t_cap"] / 2) ** 2
        if sp["name"] == "main":
            h_main = sc["h"]
    sig_w = M_root * (h_main / 2) / I_tot / 1e6
    compare("ST2", "structure", "main-spar cap stress, ultimate, case F A", sig_w, -fa["spar main"]["sigma_c"] / 1e6, "MPa",
            "M c / I of the four spar caps at the root fitting (sizing_update.json)", design_conservative_if="higher")
    mat = jload("fea/materials.json")["materials"]
    ud = mat["cf_ud_wet"]["design"]
    limit("ST3", "structure", "main-spar cap compression <= UD design allowable", sig_w, min(ud["Xc"], ud["E1"] * ud["eps_c"]) / 1e6, "MPa")

    bseg = jload("fea/results/sizing_update.json")["booms"][0]["segments"]
    x_f, x_r = min(g["booms"][0]["attach_x"]), max(g["booms"][0]["attach_x"])
    T_st = g["rotors"][0]["max_thrust_N"]
    a_z = (n * T_st - W) / mtow
    n_eff = (G0 + a_z) / G0
    bx0, bx1 = g["booms"][0]["x_front"], g["booms"][0]["x_aft"]
    m_tube = [m for m in boom_items if m["group"] == "structure"][0]["kg"]
    lin = m_tube / (bx1 - bx0)
    pts = [(m["x"], m["kg"]) for m in boom_items if m["group"] != "structure"] + [(g["tail"]["x_ac"], bd["tail"] / 2)]
    rot_x = [r["hub"][0] for r in rot if r["hub"][1] < 0]

    def overhang(x_s, side, thrust, nload):
        arm = (lambda x: x_s - x) if side == "front" else (lambda x: x - x_s)
        Mt = sum(thrust * arm(x) for x in rot_x if arm(x) > 0)
        Mi = sum(mk * arm(x) for x, mk in pts if arm(x) > 0)
        L = (x_s - bx0) if side == "front" else (bx1 - x_s)
        Mi += lin * L * L / 2
        return Mt - nload * G0 * Mi
    Mf, Ma = abs(overhang(x_f, "front", T_st, n_eff)), abs(overhang(x_r, "aft", T_st, n_eff))
    M_r2, x_crit = (1.5 * Mf, x_f) if Mf >= Ma else (1.5 * Ma, x_r)
    fr2 = fe["cases"]["R2 all rotors max thrust"]["groups"]["boom_L"]
    compare("ST4", "structure", f"boom ultimate bending, all rotors at {T_st:.0f} N (R2)", M_r2 / 1e3, fr2["M"] / 1e3, "kN m",
            "overhang moment at the wing saddle, inertia relief, x 1.5", design_conservative_if="higher")

    def tube_stress(M, x):
        seg = [s_ for s_ in bseg if s_["x_from"] <= x <= s_["x_to"]][0]["section"]
        r_in = seg["id"] / 2
        EI, layers = 0.0, []
        for L_ in seg["layers"]:
            r_out = r_in + L_["t"]
            mm = mat.get(L_["material"]) or mat["cf_fabric_wet"]
            E = 15e9 if L_["material"].endswith("_45") else (mm.get("design", {}).get("E1") or mm.get("design", {}).get("E") or 15e9)
            EI += E * math.pi / 4 * (r_out ** 4 - r_in ** 4)
            layers.append((L_["material"], r_out, E))
            r_in = r_out
        return {mn: M * r * E / EI / 1e6 for mn, r, E in layers}
    st_r2 = tube_stress(M_r2, x_crit)
    compare("ST5", "structure", "boom UD over-wrap stress, R2, at the saddle", st_r2["cf_ud_wet"], -fr2["sigma_c"] / 1e6, "MPa",
            "E-weighted composite tube, M r E / sum(E I)", design_conservative_if="higher",
            note=(f"FEA uses a homogeneous section checked against the twill allowable (248 MPa); layer by layer the UD is at "
                  f"{st_r2['cf_ud_wet']:.0f} of 460 MPa and the twill at {st_r2['cf_tube_rollwrapped_twill']:.0f} of 248 MPa, so the FEA margin is conservative"))
    mg_all = jload("fea/results/margins.json")["margins"]
    strength = [x for x in mg_all if "frequency" not in x["item"]]
    lo = min(strength, key=lambda x: x["MS"])
    limit("ST6", "structure", "lowest FEA strength margin >= 0", 1 + lo["MS"], 1.0, "1+MS", sense=">=",
          note=f"{lo['item']} MS {lo['MS']:+.3f} (fea/results/margins.json; margins are at ultimate, so MS > 0 passes)")
    nfreq = [x for x in mg_all if "frequency" in x["item"]]
    if nfreq:
        info("ST7", "structure", "frequency placement (boom/rotor and pusher 1P/2P)", nfreq[0]["MS"], "MS flag",
             note="pusher 1P 34.6 Hz is 3-9 % below boom/tail modes 35.5-37.6 Hz: GVT and notch filtering", verdict="FLAG")
    C.update(wing_root_M_kNm=M_root / 1e3, boom_M_R2_kNm=M_r2 / 1e3, boom_stress_R2=st_r2)

    # ------------------------------------------------------------------ 11. parachute
    limit("CH1", "parachute", "MTOW <= GRS 6 1200-1390 rating", mtow, REF["parachute_rating_kg"], "kg")
    n_open = REF["parachute_shock_kN"] * 1e3 / W
    compare("CH2", "parachute", "opening load factor at MTOW (57.4 kN vendor) vs geometry.json n_open_limit", n_open,
            g["parachute"]["n_open_limit"], "g", "F / W",
            note="geometry.json keeps the GRS 990-1190 value (48.8 kN); FEA used 57.4 kN directly (fea/README.md phase 3.3B)")
    limit("CH3", "parachute", "cruise speed <= parachute VNE 260 km/h (1,390 kg variant)", V * 3.6, 260.0, "km/h")

    # ------------------------------------------------------------------ 12. cost
    cst = d["cost"]
    bom = list(csv.DictReader((ROOT / "bom/BOM.csv").open()))
    bom_total = sum(float(x["total_usd"] or 0) for x in bom)
    bom_tool = sum(float(x["total_usd"] or 0) for x in bom if x["group"] == "tooling")
    compare("K1", "cost", "prototype cash, BOM.csv roll-up", bom_total, cst["prototype_out_of_pocket_usd"], "USD", "sum of BOM.csv total_usd")
    b_ = math.log2(REF["labour_learning"])
    Nn = cst["units_produced_5yr"]
    lf = sum((k + 1) ** b_ for k in range(Nn)) / Nn
    compare("K2", "cost", "cumulative-average learning factor, N = 10, 85 %", lf, cst["learning_factor_N"], "-", "(1/N) sum n^log2(0.85)")
    unit_N = bom_total - bom_tool + bom_tool / Nn + cst["labour_hours_prototype"] * cst["labour_rate_usd_h"] * lf
    compare("K3", "cost", "cost per aircraft at N = 10 from the BOM", unit_N, res["cost_usd"], "USD", "BOM - tooling + tooling/N + hours x rate x learning")
    est = sum(float(x["total_usd"] or 0) for x in bom if "estimate" in x["price_type"] or "quote" in x["price_type"])
    info("K4", "cost", "share of the BOM on estimates / quote-required prices", 100 * est / bom_total, "%", note="manufacturing/QUOTES_TO_REQUEST.md")
    C.update(bom_total=bom_total, unit_N_from_bom=unit_N)

    # ------------------------------------------------------------------ 13. WP M checker (in memory)
    try:
        chk = wpm.Checker(d, g).run()
        out["wpm_checker_summary"] = chk["summary"]
        out["wpm_checker_nonpass"] = [dict(quantity=r_["quantity"], M=r_["M"], D=r_["D"], status=r_["status"], diff=r_.get("diff"))
                                      for r_ in chk["rows"] if r_["status"] not in ("PASS", "INFO")]
    except Exception as exc:  # pragma: no cover
        out["wpm_checker_summary"] = {"error": str(exc)}
    out["inputs"].update(cfd_dir=CFD_DIR, fea_airframe=fe_path, cad_mass_properties_mtime=str(mtime("cad/mass_properties.json")))
    return out


# ============================================================================== benchmarks
def benchmarks(d) -> dict:
    rows = list(csv.DictReader((ROOT / "methods/benchmarks/benchmarks_wide.csv").open()))
    long = list(csv.DictReader((ROOT / "methods/benchmarks/benchmarks.csv").open()))
    extra = {}
    for r in long:
        extra.setdefault(r["aircraft"], {})[r["parameter"]] = r["value"]

    def f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    bm = []
    for r in rows:
        name = r["aircraft"]
        mt = f(r["mtow_used"])
        e = dict(name=name, config=r["configuration"], mtow=mt, empty_fraction=f(r["empty_fraction"]),
                 disk_loading=f(r["disk_loading_N_m2"]) or f(extra.get(name, {}).get("disk_loading")),
                 battery_fraction=f(r["battery_mass_fraction"]), LD=f(extra.get(name, {}).get("L_De")))
        S = f(extra.get(name, {}).get("wing_area"))
        e["wing_loading"] = mt * G0 / S if (mt and S) else None
        E, Rk = f(r["battery_energy"]), f(r["range"])
        e["kwh_per_km"] = E / Rk if (E and Rk) else None
        e["kwh_per_km_t"] = e["kwh_per_km"] / (mt / 1000) if (e["kwh_per_km"] and mt) else None
        bm.append(e)
    # resources/benchmarks_raw.json: add aircraft with SI-convertible data that the curated table lacks
    raw = jload("resources/benchmarks_raw.json")
    conv = {"lb": 0.45359237, "kg": 1.0}
    have = {re.split(r"[ /]", b["name"].lower())[0] for b in bm if not b["name"].startswith("NASA")}

    def duplicate(nm):
        lo = nm.lower()
        if lo.startswith("nasa"):
            return "lift+cruise" in lo
        return re.split(r"[ /]", lo)[0] in have or any(w in lo for w in ("vahana", "blackfly", "hexa", "volocopter"))
    for a in raw["aircraft"]:
        dd = a["data"]
        if duplicate(a["aircraft"]):
            continue
        mt, me, ek = dd.get("mtow"), dd.get("empty_mass"), dd.get("battery_kWh")
        if not (isinstance(mt, dict) and mt.get("value") and mt.get("unit") in conv):
            continue
        mtk = mt["value"] * conv[mt["unit"]]
        rec = dict(name=a["aircraft"], config=a.get("class", ""), mtow=mtk, empty_fraction=None, disk_loading=None,
                   battery_fraction=None, LD=None, wing_loading=None, kwh_per_km=None, kwh_per_km_t=None, source="benchmarks_raw.json")
        if isinstance(me, dict) and me.get("value") and me.get("unit") in conv:
            rec["empty_fraction"] = me["value"] * conv[me["unit"]] / mtk
        rd = dd.get("rotor_diameter"); rc = dd.get("rotor_count")
        if isinstance(rd, dict) and rd.get("value") and isinstance(rc, dict) and rc.get("value"):
            Dm = rd["value"] * (0.3048 if rd.get("unit") == "ft" else 1.0)
            rec["disk_loading"] = mtk * G0 / (rc["value"] * math.pi * Dm * Dm / 4)
        bm.append(rec)

    m = d["mass_kg"]
    mt = m["mtow"]
    res = d["results"]
    e8 = dict(name="E8-200 3.3", mtow=mt, empty_fraction=(m["empty"] + m["battery"]) / mt, disk_loading=res["disk_loading_N_m2"],
              battery_fraction=m["battery"] / mt, LD=res["cruise_LD"], wing_loading=mt * G0 / d["wing"]["area_m2"],
              kwh_per_km=d["battery"]["energy_nominal_kwh"] / res["range_km"],
              kwh_per_km_mission=res["mission_energy_kwh"] / d["mission"]["range_km"])
    e8["kwh_per_km_t"] = e8["kwh_per_km"] / (mt / 1000)
    e8["kwh_per_km_t_mission"] = e8["kwh_per_km_mission"] / (mt / 1000)
    fit = jload("methods/benchmarks/trend_fits.json")["empty_fraction_vs_mtow"]
    e8["empty_fraction_trend"] = fit["A"] * mt ** fit["C"]
    return dict(aircraft=bm, e8=e8, trend=fit)


def plot_benchmarks(B, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401
    BLUE, ORANGE, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
    e8 = B["e8"]
    panels = [
        ("empty_fraction", "Empty-mass fraction (incl. battery)", True),
        ("disk_loading", "Disk loading (N/m$^2$)", True),
        ("wing_loading", "Wing loading (N/m$^2$)", False),
        ("battery_fraction", "Battery mass fraction", True),
        ("LD", "Cruise L/D (NASA: L/D$_e$)", False),
        ("kwh_per_km_t", "Battery energy per km per tonne\n(kWh / km / t, nameplate / range)", True),
    ]
    fig, axs = plt.subplots(2, 3, figsize=(13, 7.6), dpi=130)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, (k, lab, logx) in zip(axs.flat, panels):
        ax.set_facecolor("#fcfcfb")
        pts = [(b["mtow"], b[k], b["name"]) for b in B["aircraft"] if b.get(k) and b.get("mtow")]
        if pts:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=34, color=BLUE, edgecolor="#fcfcfb", linewidth=1.5,
                       zorder=3, label="benchmark aircraft")
            for x_, y_, nm in pts:
                ax.annotate(nm.replace(" (2018)", " 18").replace(" (2022)", " 22")[:18], (x_, y_), xytext=(4, 3),
                            textcoords="offset points", fontsize=6.5, color=INK2)
        ax.scatter([e8["mtow"]], [e8[k]], s=90, marker="D", color=ORANGE, edgecolor="#fcfcfb", linewidth=1.5, zorder=4, label="E8-200 3.3")
        ax.annotate("E8-200", (e8["mtow"], e8[k]), xytext=(6, -10), textcoords="offset points", fontsize=8, color=INK, weight="bold")
        if k == "empty_fraction":
            xx = np.logspace(np.log10(150), np.log10(5000), 50)
            ax.plot(xx, B["trend"]["A"] * xx ** B["trend"]["C"], color=INK2, lw=1.2, ls="--", label="benchmark fit [W3]")
        if k == "kwh_per_km_t":
            ax.scatter([e8["mtow"]], [e8["kwh_per_km_t_mission"]], s=60, marker="d", facecolor="none", edgecolor=ORANGE,
                       linewidth=1.5, zorder=4, label="E8-200 mission energy / 20 km")
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([200, 500, 1000, 2000, 5000]))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel("MTOW (kg)")
        ax.set_title(lab, fontsize=9.5, color=INK, loc="left")
        ax.grid(True, color=GRID, lw=0.6)
        if not pts:
            ax.text(0.5, 0.5, "no published benchmark value", transform=ax.transAxes, ha="center", color=INK2)
        ax.legend(fontsize=7, frameon=False, loc="best")
    fig.suptitle("E8-200 (iteration 3.3) against benchmark eVTOL and electric aircraft (methods/benchmarks, resources/benchmarks_raw.json)",
                 fontsize=10.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


# ============================================================================== WP evidence and the matrix
def wp_evidence(cutoff, R, out):
    ev = {}
    vr = ROOT / "validation/sizing/verification_report.md"
    m_ = re.search(r"\*\*(\d+) PASS, (\d+) FAIL\*\*", vr.read_text()) if vr.exists() else None
    ev["sizing"] = dict(status="PASS" if m_ and m_.group(2) == "0" else "FLAG",
                        result=(f"verify_sizing.py: {m_.group(1)} PASS, {m_.group(2)} FAIL; B4 battery-fraction band widened by +-0.02 to pass"
                                if m_ else "report missing"))
    s = out.get("wpm_checker_summary", {})
    ev["methods"] = dict(status="PASS", result="NASA L+C reproduction: hover power, C-rate and battery energy within 5 %, mission energy -3 %; "
                         f"WP M checker on the 3.3 design (in memory): {s.get('PASS', '?')} PASS, {s.get('WARN', '?')} WARN, {s.get('FAIL', '?')} FAIL")
    ev["parts"] = dict(status="FLAG", result="EMRAX 268 LC: hover 202 N m vs 205 continuous (+1.6 %); MV winding over-speeds (6,400 rpm no-load at 735 V vs 4,500 limit): winding / inverter speed limit open")
    mg = jload("fea/results/margins.json")["margins"]
    strength = [x for x in mg if "frequency" not in x["item"]]
    neg = [x for x in strength if x["MS"] < 0]
    ev["fea_tool"] = dict(status="PASS", result="B1-B7 beam exact to 1.3 %; NAFEMS LE1 +0.5 %, LE10 +0.7 %, FV52 0.6 %; CLT 0.3 %; Goland flutter 137.3 vs 137.2 m/s; L6 root bending -0.5 %")
    ev["fea_design"] = dict(status="FAIL" if neg else "PASS",
                            result=f"{len(strength)} strength margins, {len(neg)} negative, minimum {min(x['MS'] for x in strength):+.3f}; frequency placement open (GVT)",
                            neg=neg, low=sorted(strength, key=lambda x: x["MS"])[:8])
    ev["cfd_tool"] = dict(status="PASS", result="NACA 0012 cd(0) +0.9 %, cl(10) -0.5 %, cl(15) +3 %; GA(W)-1 clmax -3 %; actuator disc +3 %; 3-D wing L+1 CD0 +6 %; download conservative x 1.46")
    cfd_ok = (ROOT / f"{CFD_DIR}/summary.json").exists()
    ev["cfd_design"] = dict(status="PASS" if cfd_ok else "PENDING",
                            result="3.3 production-mesh polar, pusher wake and thrust deduction, hover download, mission check (run at 172 km/h; frozen cruise 167 km/h inside the polar)")
    gci = ROOT / "validation/cfd/data/aircraft33_gci.json"
    ev["cfd_mesh"] = dict(status="FLAG" if gci.exists() else "PENDING",
                          result="lifting-surface GCI at cruise: CL 2.3 %, CD 0.6 %; Cm not converging (GCI 475 %): Cm level not usable, slope only")
    cad_fresh = cad_is_fresh(cutoff)
    cl = jload("validation/cad/clearance_checks.json")
    nf = sum(1 for c in cl if c["status"] == "FAIL")
    nw = sum(1 for c in cl if c["status"] == "WARN")
    itf = jload("validation/cad/interference.json")
    notch = "SH-AFT notch" in (ROOT / "validation/cad/interference.md").read_text()
    unexp = [o for o in itf["overlaps"] if not o.get("expected_contact")]
    au = jload("validation/cad/mass_cg_audit.json")
    st = "FAIL" if nf else "FLAG"
    ev["cad"] = dict(status=st if cad_fresh else "PENDING", provisional=st,
                     result=(f"{len(cl) - nf - nw} of {len(cl)} clearance checks pass, {nw} WARN (boom height on the egress path); "
                             f"{len(unexp)} unexpected overlap(s){' fixed by the SH-AFT notch' if notch else ''}; {itf.get('failed_pairs')} pairs not evaluated; "
                             f"CAD MTOW {au['totals']['MTOW (pilot + passenger)']['cad_kg']:.1f} kg, static margin {au['static_margin_cad']:.3f}; assembly STEP not yet re-exported"),
                     sm=au["static_margin_cad"])
    occ = [c for c in cl if c["id"] in ("C8", "C9", "C22a", "C22b", "C23")]
    ev["cad"]["occupant"] = ("PASS" if all(c["status"] == "PASS" for c in occ) else "FLAG") if cad_fresh else "PENDING"
    return ev


def build_matrix(R, ev, req_txt):
    def st(*ids):
        vs = [R[i]["verdict"] for i in ids if i in R]
        for k in ("FAIL", "PENDING", "FLAG", "OPEN", "PASS"):
            if k in vs:
                return k
        return "OPEN"

    def val(i, fmt="{:.3g}"):
        r = R.get(i)
        return fmt.format(r["independent"]) if r and r.get("independent") is not None else "-"

    def mg(i):
        r = R.get(i)
        return f"{r['margin_pct']:+.1f} %" if r and "margin_pct" in r else "-"

    def lk(anchor):
        return f"[independent/results.md](independent/results.md#{anchor})"
    Y = lambda k, blk=None: yaml_scalar(req_txt, k, blk)
    rows = []

    def add(group, req, method, evid, result, status):
        rows.append(dict(group=group, req=req, method=method, evidence=evid, result=result, status=status))
    REQ = "[requirements.yaml](../requirements/requirements.yaml)"
    add("Payload", f"Payload {Y('total_kg'):.0f} kg (pilot + 100 kg cargo or 2 x 100 kg)", "mass closure; three loading cases",
        f"{lk('mass')}, [selected_design.json](../design/selected_design.json)", f"MTOW closes ({val('W2', '{:.1f}')} kg); static margin 0.063-0.098", st("W1", "W2", "W2b"))
    add("Payload", "Cabin: 2 seats, removable second seat, cargo bay >= 0.6 x 0.5 x 0.5 m", "CAD clearance audit",
        "[cad/clearance_checks.md](cad/clearance_checks.md)", "door 0.49 x 0.67 m; passenger head clearance 75 mm; cargo bay unchanged from 3.2", ev["cad"]["status"])
    add("Mission", f"Design range {Y('design_range_km'):.0f} km (was 100 -> 50 -> 20 km, {REQ})", "hand mission energy, CFD drag, exact cell I-R",
        lk("range"), f"{val('R2', '{:.1f}')} km vs design 24.1 (margin on 20 km {mg('R3')}); CFD band low end {val('R4', '{:.1f}')} km (CFD 19.0 km at 172 km/h)", st("R1", "R2", "R3"))
    add("Mission", "Range sensitivity to 30 / 60 / 100 km reported", "document review",
        "[../sizing/README.md](../sizing/README.md), [../methods/initial_estimate.md](../methods/initial_estimate.md)",
        "iteration 3 and the initial estimate only; not re-run for 3.3", "FLAG")
    add("Mission (relaxed)", "Cruise >= 120 km/h. Was 135 (3.1) and 150 (1-3); allowed if cheaper and cruise >= 1.15 Vs",
        "design value", lk("stall"), f"167 km/h ({mg('S4')})", st("S4"))
    add("Mission", "Hover 60 s take-off (incl. 30 m climb) + 60 s landing, 2 x 30 s transitions", "in the hand mission energy",
        lk("range"), f"mission energy {val('R1', '{:.2f}')} kWh vs design 37.19", st("R1"))
    add("Mission (kept)", "Reserve 20 % at landing, 0.3 C margin, cells at 80 % EOL", "usable energy and C-rate by hand", lk("battery"),
        f"hover C-rate {val('B4', '{:.2f}')} vs limit 9.7 ({mg('B5')})", st("B4", "B5"))
    add("Mission", "Hover power at 500 m ISA+15", "momentum theory, benchmark FM, CFD 3.3 download", lk("hover"),
        f"{val('H2', '{:.1f}')} kW per motor vs design 39.1", st("H2", "H3"))
    add("Mission (kept)", "Hover ceiling 1000 m ISA+15 OGE within continuous rating", "P ~ rho^-1/2; fixed-pitch torque", lk("motor-rating"),
        f"{val('M1', '{:.1f}')} kW ({mg('M1')}), {val('M2', '{:.0f}')} N m vs 205 ({mg('M2')}); EMRAX winding / bus quote open", "OPEN")
    add("Configuration", "Lift + cruise, fixed lift rotors on two booms, high wing, rear pusher, H-tail between booms", "inspection of geometry.json",
        "[geometry.json](../design/geometry.json)", "8 fixed rotors on 2 booms, shoulder wing, twin boom-tail pushers, H-tail", "PASS")
    add("Objective", "Minimum acquisition cost and complexity; report MTOW, energy, cost", "BOM roll-up, learning curve", lk("cost"),
        f"BOM USD {R['K1']['independent']:,.0f} vs 381,046 ({R['K1']['diff_pct']:+.1f} %); N = 10 USD {R['K3']['independent']:,.0f} vs 497,538", st("K1", "K2", "K3"))
    add("Safety (kept)", "Ultimate factor 1.5 and all load cases (+3.8 / -1.5 g, 3 g landing, parachute)", "FEA margins; hand wing and boom checks",
        "[../fea/results/margins.json](../fea/results/margins.json), [fea/README.md](fea/README.md)",
        f"{ev['fea_design']['result']}; hand wing / boom moments {R['ST1']['diff_pct']:+.1f} % / {R['ST4']['diff_pct']:+.1f} % vs FEA",
        "FAIL" if ev["fea_design"]["status"] == "FAIL" else st("ST1", "ST4", "ST6"))
    add("Safety (kept)", "One lift motor out: continued hover at MTOW <= 100 % peak, 10 % control margin, OEI torque and rpm",
        "LP thrust allocation, fixed-pitch scaling", lk("one-motor-out"),
        f"{val('O2', '{:.1f}')} kW / {val('O3', '{:.0f}')} N m vs 210 kW / 500 N m peak ({mg('M3')} / {mg('M4')}); {val('M7', '{:.0f}')} rpm vs 2,460 cap; time limit above 205 N m open",
        "FLAG" if st("O2", "O3", "M3", "M4", "M7") == "PASS" else st("O2", "O3", "M3", "M4", "M7"))
    add("Safety (relaxed)", "One-motor-out flare 1.10 g. Was 1.20 g; keeps a reserve above the 1.0 g rule (floor 1.05 g)", "as above at 500 m",
        lk("one-motor-out"), f"{val('O4', '{:.1f}')} kW / {val('O5', '{:.0f}')} N m ({mg('M5')}); thrust {val('M8', '{:.0f}')} N vs FC cap ({mg('M8')})",
        st("O4", "O5", "M5", "M8"))
    add("Safety (kept)", ">= 2 independent packs; one pack out allows a controlled landing; cell <= 60 A and bus >= 400 V at EOL",
        "exact cell I-R model, low SOC, EOL resistance x 1.5", lk("battery"),
        f"4 packs; one out: {val('B7', '{:.1f}')} A ({mg('B7')}), {val('B8', '{:.0f}')} V ({mg('B8')})", st("B7", "B8"))
    add("Safety (kept)", "Whole-aircraft ballistic parachute sized for MTOW", "rating vs MTOW (design and CAD); opening load", lk("parachute"),
        f"GRS 6 1200-1390: 1,347.8 / 1,390 kg ({mg('CH1')}); CAD {val('W8', '{:.0f}')} kg ({mg('W8')}); 57.4 kN = {val('CH2', '{:.2f}')} g", st("CH1", "CH3", "W8"))
    add("Safety", "Occupant: energy-absorbing seats, 4-point harness, rotor plane clear of the cabin", "CAD clearance audit",
        "[cad/clearance_checks.md](cad/clearance_checks.md)", "blade plane above the occupants; burst fan, seat stroke and head clearance pass (C8, C9, C22, C23)", ev["cad"]["occupant"])
    add("Safety", "Regulations referenced (Part 103, powered-lift SFAR / AC 21.17-4, SC-VTOL-01, ASTM F3264, CS-23)", "document review",
        "[../resources/README.md](../resources/README.md)", "all cited with their use", "PASS")
    add("Manufacturing", "In-house 3-axis CNC / FDM, wet lay-up, COTS tubes; avoid autoclave, metal printing, 5-axis, castings; few motor types",
        "document review", "[../manufacturing/MANUFACTURING_METHODS.md](../manufacturing/MANUFACTURING_METHODS.md)",
        "two motor types (EMRAX 268 lift, REB 90 pusher); CH-CRADLE needs two machining set-ups; HT-SPAR needs a splice sleeve", "FLAG")
    add("Constraint (relaxed)", "Footprint <= 10.5 m. Was 9.0 m; trailer transport with the wing removed", "extremes of geometry.json",
        lk("footprint"), f"{val('F1', '{:.2f}')} m ({mg('F1')}); 9.0 m not met", st("F1", "F2"))
    add("Constraint (relaxed)", "Cruise >= 1.15 Vs (hot day). Was 1.30; stall backed up by the lift rotors", "Vs EAS from CLmax 1.628 (CFD - 5 %)",
        lk("stall"), f"{val('S3', '{:.3f}')} x Vs ({mg('S3')}); handbook CLmax gives {val('S3b', '{:.3f}')} ({mg('S3b')}); CFD 1.714 gives 1.19",
        st("S1", "S2", "S3", "S3b"))
    add("Kept", "Pusher continuous margin 10 % and climb >= 1 m/s", "actuator disc with CFD wake fraction and thrust deduction", lk("pusher"),
        f"1.1 x {val('P3', '{:.1f}')} kW vs 60 ({mg('P3')}); climb {val('P5', '{:.2f}')} m/s ({mg('P6')}); REB 90 continuous torque at 2,074 rpm not published",
        "OPEN" if st("P3", "P6") in ("PASS", "FLAG") else st("P3", "P6"))
    add("Kept", "Static stability (static margin >= 0.05 in all loading cases)", "neutral-point build-up; CFD; CAD CG", lk("stability"),
        f"hand {val('SM2', '{:.3f}')}, sizing 0.098, CFD 0.195, CAD {val('SM4', '{:.3f}')}; pilot only {val('SM5-3', '{:.3f}')}", st("SM2", "SM4", "SM5-1", "SM5-2", "SM5-3"))
    add("Kept", "Tip Mach, door width, blade chord and other constraints", "hand tip Mach; CAD door; sizing G-checks",
        f"{lk('hover')}, [sizing/verification_report.md](sizing/verification_report.md)", f"hover Mtip {val('H5', '{:.3f}')}; pusher helical {val('P7', '{:.2f}')}", st("H5", "H6", "P7"))
    # tools
    add("Tool: sizing", "Sizing code verification (WP D)", "unit tests, audit, integration checks",
        "[sizing/verification_report.md](sizing/verification_report.md)", ev["sizing"]["result"], ev["sizing"]["status"])
    add("Tool: methods", "Equation set and independent checker (WP M)", "NASA Lift+Cruise reproduction",
        "[methods/nasa_lpc_reproduction.md](methods/nasa_lpc_reproduction.md)", ev["methods"]["result"], ev["methods"]["status"])
    add("Tool: parts", "Propulsion parts consistency (WP P)", "duty points vs catalog ratings", "[parts/README.md](parts/README.md)",
        ev["parts"]["result"], ev["parts"]["status"])
    add("Tool: CFD", "CFD solver validation (OpenFOAM SST)", "NASA TMR NACA 0012, TN D-7428, momentum theory, Felker & Light, lifting line",
        "[cfd/README.md](cfd/README.md)", ev["cfd_tool"]["result"], ev["cfd_tool"]["status"])
    add("Tool: CFD", "Aircraft CFD on the 3.3 geometry", "production mesh, actuator-disc pushers, hover download",
        "[../cfd/results/iteration33/README.md](../cfd/results/iteration33/README.md)", ev["cfd_design"]["result"], ev["cfd_design"]["status"])
    add("Tool: CFD", "3.3 aircraft grid convergence", "three lifting-surface resolutions, Celik GCI", "[cfd/README.md](cfd/README.md)",
        ev["cfd_mesh"]["result"], ev["cfd_mesh"]["status"])
    add("Tool: FEA", "FEA benchmarks (beam, CalculiX, CLT, flutter)", "closed form, NAFEMS, Goland", "[fea/README.md](fea/README.md)",
        ev["fea_tool"]["result"], ev["fea_tool"]["status"])
    add("Tool: FEA", "Fitting peak-stress mesh convergence", "D6 mesh study", "[fea/README.md](fea/README.md)",
        "peak not converged at the production mesh; x 1.27 applied to every fitting (conservative)", "PASS")
    add("Tool: CAD", "CAD audit: mass/CG, clearances, interference", "cad/audit.py", "[cad/README.md](cad/README.md)",
        ev["cad"]["result"] + ("" if ev["cad"]["status"] != "PENDING" else f" (provisional: {ev['cad']['provisional']})"), ev["cad"]["status"])
    return rows


# ============================================================================== reports
def fmt(v, unit=""):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if isinstance(v, float) and math.isnan(v):
        return "-"
    a = abs(v)
    if unit == "USD":
        return f"{v:,.0f}"
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 100:
        return f"{v:.1f}"
    if a >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


GROUP_ANCHOR = {"hover": "hover", "one motor out": "one-motor-out", "motor rating": "motor-rating", "cruise": "cruise",
                "pusher": "pusher", "battery": "battery", "range": "range", "stall": "stall", "footprint": "footprint",
                "mass": "mass", "mass vs CAD": "mass", "stability": "stability", "structure": "structure", "parachute": "parachute", "cost": "cost",
                "stability": "stability"}


def write_md(out, B, path):
    rows = out["rows"]
    cnt = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("PASS", "FLAG", "FAIL", "PENDING", "INFO")}
    L = ["# Final independent checks of the E8-200 iteration 3.3 design (WP V)", "",
         "Written by `check_final.py`. Do not edit by hand.", "",
         f"Run: {out['meta']['run_time']}. Inputs: `design/selected_design.json`, `design/geometry.json`, `bom/BOM.csv`, "
         "`cad/mass_properties.json`, `validation/cad/`, `fea/results/*.json`, `cfd/results/iteration33/`, `methods/benchmarks/`.", "",
         f"**Summary: {cnt['PASS']} PASS, {cnt['FLAG']} FLAG, {cnt['FAIL']} FAIL, {cnt['PENDING']} pending CAD re-run, {cnt['INFO']} information.**", "",
         "Verdict rules:",
         "- Comparison rows (independent value against the design or WP value): PASS within 5 %, FLAG 5-20 %, FAIL above 20 %.",
         "  Above 20 % the row stays FLAG when the design value is on the conservative side.",
         "- Limit rows (requirement or rating checked with the independent value): PASS when the margin is at least 2 %.",
         "  FLAG when the margin is within +-2 % (inside the accuracy of a hand calculation). FAIL below -2 %.",
         "- PENDING: the row needs a CAD file newer than the cut-off. Provisional values are shown.", "",
         "Assumptions of the hand checks (independent of WP D's model unless stated):", ""]
    for k, v in REF.items():
        if True:
            L.append(f"- `{k}` = {v}")
    L += ["- Thrust deduction, wake fraction and hover download are the CFD 3.3 values; the EOL resistance factor (1.5) is the same as WP D's.",
          "- Motor ratings: " + EMRAX["src"] + "; " + REB90["src"] + ".", ""]
    groups = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])
    seen = set()
    for gname in groups:
        anc = GROUP_ANCHOR.get(gname, gname.lower().replace(" ", "-"))
        if anc not in seen:
            L += [f'<a id="{anc}"></a>', ""]
            seen.add(anc)
        L += [f"## {gname}", "", "| id | quantity | independent | design / limit | unit | diff / margin | verdict | method / note |",
              "|---|---|---|---|---|---|---|---|"]
        for r in [x for x in rows if x["group"] == gname]:
            if r["kind"] == "compare":
                dl, dm = fmt(r["design"], r["unit"]), f"{r['diff_pct']:+.1f} %"
            elif r["kind"] == "limit":
                dl = f"{r['sense']} {fmt(r['limit'])}" + (f" (design {fmt(r['design'])})" if r.get("design") is not None else "")
                dm = f"{r['margin_pct']:+.1f} %"
            else:
                dl, dm = "-", "-"
            verdict = r["verdict"] + (f" (provisional {r['provisional_verdict']})" if r.get("provisional_verdict") else "")
            note = "; ".join(x for x in (r.get("method", ""), r.get("note", "")) if x)
            L.append(f"| {r['id']} | {r['quantity']} | {fmt(r.get('independent'), r.get('unit', ''))} | {dl} | {r.get('unit', '')} | {dm} | {verdict} | {note} |")
        L.append("")
    s = out.get("wpm_checker_summary", {})
    L += ['<a id="wpm"></a>', "", "## WP M checker on the 3.3 design (run in memory, no files written)", "",
          f"`methods/check_design.py` Checker: {s}.", "",
          "| status | quantity | M | D | diff |", "|---|---|---|---|---|"]
    for r in out.get("wpm_checker_nonpass", []):
        L.append(f"| {r['status']} | {r['quantity']} | {fmt(r['M'])} | {fmt(r['D'])} | {('%+.1f %%' % (100 * r['diff'])) if r.get('diff') is not None else '-'} |")
    L += ["", '<a id="benchmarks"></a>', "", "## Benchmark comparison", "",
          "![benchmarks](benchmark_comparison.png)", "",
          "| aircraft | MTOW kg | empty fraction | disk loading N/m2 | wing loading N/m2 | battery fraction | L/D | kWh/km | kWh/km/t |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in [B["e8"]] + sorted(B["aircraft"], key=lambda x: x["mtow"] or 0):
        L.append(f"| {'**' + b['name'] + '**' if b is B['e8'] else b['name']} | {fmt(b.get('mtow'))} | {fmt(b.get('empty_fraction'))} | {fmt(b.get('disk_loading'))} | "
                 f"{fmt(b.get('wing_loading'))} | {fmt(b.get('battery_fraction'))} | {fmt(b.get('LD'))} | {fmt(b.get('kwh_per_km'))} | {fmt(b.get('kwh_per_km_t'))} |")
    e8 = B["e8"]
    L += ["", f"E8-200 empty fraction {e8['empty_fraction']:.3f} against the benchmark fit {e8['empty_fraction_trend']:.3f} at its MTOW "
          f"({100 * (e8['empty_fraction'] / e8['empty_fraction_trend'] - 1):+.0f} %). Energy per km uses the nameplate energy over the range "
          f"capability; on the mission energy over 20 km it is {e8['kwh_per_km_mission']:.2f} kWh/km ({e8['kwh_per_km_t_mission']:.2f} per tonne).", ""]
    path.write_text("\n".join(L) + "\n")


def replace_block(text, name, body):
    a, b = f"<!-- gen:{name}:start -->", f"<!-- gen:{name}:end -->"
    i, j = text.find(a), text.find(b)
    if i < 0 or j < 0:
        return text
    return text[: i + len(a)] + "\n" + body.rstrip() + "\n" + text[j:]


def update_readme(matrix, out, ev):
    p = ROOT / "validation/README.md"
    if not p.exists():
        return
    t = p.read_text()
    cnt = {k: sum(1 for r in matrix if r["status"] == k) for k in ("PASS", "FLAG", "FAIL", "OPEN", "PENDING")}
    Lm = [f"**{len(matrix)} rows: {cnt['PASS']} PASS, {cnt['FLAG']} FLAG, {cnt['FAIL']} FAIL, {cnt['OPEN']} OPEN, "
          f"{cnt['PENDING']} pending CAD re-run** (generated {out['meta']['run_time']}).", "",
          "| # | group | requirement or tool | method | evidence | result | status |", "|---|---|---|---|---|---|---|"]
    for k, r in enumerate(matrix, 1):
        stt = "pending CAD re-run" if r["status"] == "PENDING" else r["status"]
        Lm.append(f"| {k} | {r['group']} | {r['req']} | {r['method']} | {r['evidence']} | {r['result']} | **{stt}** |")
    t = replace_block(t, "matrix", "\n".join(Lm))
    low = ev["fea_design"]["low"]
    Lf = ["| MS | item | source |", "|---|---|---|"] + [f"| {x['MS']:+.3f} | {x['item']} | `{x['source']}` |" for x in low]
    t = replace_block(t, "fea_negative", "\n".join(Lf))
    pend = [r for r in out["rows"] if r["verdict"] == "PENDING"]
    Lp = [f"- {r['id']}: {r['quantity']}" + (f" (provisional {r['provisional_verdict']})" if r.get("provisional_verdict") else "") for r in pend]
    Lp += [f"- matrix: {r['req']}" for r in matrix if r["status"] == "PENDING"]
    t = replace_block(t, "pending", "\n".join(Lp) if Lp else "None: every CAD and CFD row reads the final 3.3 files.")
    rows = out["rows"]
    c2 = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("PASS", "FLAG", "FAIL", "PENDING", "INFO")}
    t = replace_block(t, "independent_summary",
                      f"Independent checks: **{c2['PASS']} PASS, {c2['FLAG']} FLAG, {c2['FAIL']} FAIL, {c2['PENDING']} pending, "
                      f"{c2['INFO']} information** ([independent/results.md](independent/results.md)).")
    p.write_text(t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-readme", action="store_true")
    ap.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    a = ap.parse_args(argv)
    cutoff = dt.datetime.fromisoformat(a.cutoff)
    ROWS.clear()
    out = run_checks(cutoff)
    out["rows"] = ROWS
    out["meta"] = dict(run_time=dt.datetime.now().strftime("%Y-%m-%d %H:%M"), cutoff=a.cutoff, script="validation/independent/check_final.py")
    d = jload("design/selected_design.json")
    B = benchmarks(d)
    out["benchmarks"] = B
    plot_benchmarks(B, HERE / "benchmark_comparison.png")
    Rm = {r["id"]: r for r in ROWS}
    ev = wp_evidence(cutoff, Rm, out)
    matrix = build_matrix(Rm, ev, (ROOT / "requirements/requirements.yaml").read_text())
    out["matrix"] = matrix
    out["wp_evidence"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("neg", "low", "clear")} for k, v in ev.items()}
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)))
    write_md(out, B, HERE / "results.md")
    if not a.no_readme:
        update_readme(matrix, out, ev)
    cnt = {k: sum(1 for r in ROWS if r["verdict"] == k) for k in ("PASS", "FLAG", "FAIL", "PENDING", "INFO")}
    mc = {k: sum(1 for r in matrix if r["status"] == k) for k in ("PASS", "FLAG", "FAIL", "OPEN", "PENDING")}
    print("independent checks:", cnt)
    print("matrix:", mc)
    for r in ROWS:
        if r["verdict"] in ("FLAG", "FAIL") or (r.get("diff_pct") is not None and abs(r["diff_pct"]) > 5):
            print(f"  {r['verdict']:7s} {r['id']:10s} {r['quantity'][:70]:70s} ind={fmt(r.get('independent'))} "
                  f"diff={r.get('diff_pct', float('nan')):+.1f}% margin={r.get('margin_pct', float('nan')):+.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
