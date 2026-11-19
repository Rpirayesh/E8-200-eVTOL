#!/usr/bin/env python3
"""WP V - independent hand checks of the E8-200 iteration 3.2 design "T8" (archived record; superseded by
../check_final.py for the frozen iteration 3.3 design). Re-running it against the 3.3 design files is not meaningful.

Every number is recomputed here from first principles (momentum theory, actuator disc, parabolic polar,
elementary beam theory, cell I-R model, learning curve) using only the frozen design files and published
reference data. No code from sizing/ is imported. From methods/ only the WP M atmosphere, the rotor-out
linear programme and the WP M checker are used; WP M wrote them independently of WP D.

Outputs (this folder): results.json, results.md, benchmark_comparison.png.
It also refreshes the generated blocks of validation/README.md (between the <!-- gen:... --> markers),
so the V&V matrix follows the CAD and CFD re-runs when they land.

Run from the project root:  ~/tools/cadenv/bin/python validation/independent/iteration32/check_t8.py
Options: --no-readme (do not touch validation/README.md), --cutoff ISO-time (freshness cut-off for CAD/CFD).
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
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "methods"))
import check_design as wpm  # noqa: E402  (WP M, independent of WP D)

G0 = 9.80665
RHO_SL = 1.225

# Freshness cut-off: CAD and CFD evidence written before this time predates the 3.2 re-runs (CAD rebuild with
# the FEA fixes, then CFD on the 3.2 geometry) and is shown as provisional. Override with --cutoff.
DEFAULT_CUTOFF = "2026-11-18T00:00:00"

# Published / reference inputs used by the hand checks (all independent of WP D's model)
REF = dict(
    fm_benchmark=0.74,          # NASA Lift+Cruise hover FM (methods/benchmarks/benchmarks.csv, S18)
    download_cfd=0.055,         # CFD hover download, corrected (cfd/results/README.md sec. 6, iteration 3.1)
    k_ctrl=0.10,                # requirement: 10 % control margin on the most loaded rotor
    prop_profile=0.90,          # eta_p / actuator-disc ideal, McCormick ch. 6 (methods EQUATIONS [P2])
    thrust_deduction=0.045,     # CFD tail-cone value; boom-tail value not computed (assumption shared with WP D)
    eta_motor=0.93, eta_inv=0.97, eta_wire=0.98,
    aux_kw=1.5,
    v_oc_mid=3.60,              # P50B nominal (mid-SOC) open-circuit voltage
    v_oc_low=3.45,              # open-circuit voltage at the 20 % landing reserve (WP P estimate)
    dcir_eol_factor=1.5,        # cell resistance growth to end of life (common EOL criterion range 1.5-2.0)
    i_cont_cell=40.0, i_peak_cell=60.0,
    f_eol=0.80, f_res=0.20, dC=0.3,
    clmax_flaps_cfd_key=("flaps", "delta_35", "CLmax_flaps"),
    # CFD 3.1 drag-area build (cfd/results/README.md sec. 2), used to scale to the 3.2 geometry
    cfd31_drag_area=0.729, cfd31_S=10.35, cfd31_wing_cd0_area=0.155, cfd31_fus_pusher_on=0.147,
    cfd31_fus_pusher_off=0.089, cfd31_rotors=0.263, cfd31_booms=0.011, cfd31_D=1.85, cfd31_boom_len=8.22,
    cfd31_e=0.734, cfd31_AR=9.0 ** 2 / 10.35,
    pod_cd_frontal=0.15,        # Hoerner, blunt motor step on a boom end (estimate)
    labour_learning=0.85,       # 85 % Wright learning curve (methods EQUATIONS [C])
)

MOTOR_RATINGS = {
    "summary": dict(p_peak=60.0, q_peak=250.0, p_cont=36.0, q_cont=None,
                    src="MGM REB 60 page, summary block (continuous 0.6 x peak assumed by WP D; page says 35-45 kW)"),
    "table": dict(p_peak=33.5, q_peak=133.0, p_cont=25.0, q_cont=95.0,
                  src="MGM REB 60 page, detailed table 'valid for 25 C' (bom/catalog.json table_25C_*)"),
}

TOL_FLAG, TOL_FAIL = 0.05, 0.20       # comparison rows
THIN = 0.02                           # limit rows: |margin| < 2 % is FLAG (inside hand-calculation accuracy)


# ============================================================================== helpers
def jload(p):
    return json.loads((ROOT / p).read_text())


def mtime(p):
    q = ROOT / p
    return dt.datetime.fromtimestamp(q.stat().st_mtime) if q.exists() else None


def cad_is_fresh(cutoff: dt.datetime) -> bool:
    """CAD evidence counts as 3.2 only when the audit (written last by cad/build.py) is newer than the cut-off and
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
    req_txt = (ROOT / "requirements/requirements.yaml").read_text()
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
    dl_cfd = REF["download_cfd"]
    T_h = W * (1 + dl_cfd) / n
    DLd = W / (n * A)
    compare("H1", "hover", "disk loading W/(N A)", DLd, res["disk_loading_N_m2"], "N/m2", "W / (8 pi R^2)")
    p_ideal = T_h ** 1.5 / math.sqrt(2 * rho_h * A)
    P_h = p_ideal / REF["fm_benchmark"] / 1e3
    compare("H2", "hover", "hover shaft power per motor, 500 m ISA+15", P_h, res["hover_shaft_power_per_motor_kw"], "kW",
            "momentum theory, FM 0.74 (NASA L+C benchmark), CFD download 5.5 %",
            note=f"design uses FM {lr['figure_of_merit']:.3f} and download {lr['download_fraction']:.1%}")
    P_h_el = n * P_h / eta_d + REF["aux_kw"]
    compare("H3", "hover", "hover electrical power, 500 m", P_h_el, res["hover_electrical_power_kw"], "kW",
            "8 x shaft / (0.93 x 0.97 x 0.98) + 1.5 kW aux")
    P_h_c = P_h * math.sqrt(rho_h / rho_c)
    P_h_el_c = n * P_h_c / eta_d + REF["aux_kw"]
    compare("H4", "hover", "hover electrical power, 1000 m ceiling", P_h_el_c, res["hover_electrical_power_ceiling_kw"], "kW",
            "P ~ rho^-1/2 at constant thrust")
    vtip = lr["tip_speed_hover_ms"]
    om_h = vtip / R
    Q_h = P_h * 1e3 / om_h
    mtip = vtip / site["a"]
    compare("H5", "hover", "hover tip Mach, 500 m ISA+15", mtip, res["tip_mach_hover"], "-", "V_tip / a")
    limit("H6", "hover", "hover tip Mach <= 0.55 (noise screen)", mtip, 0.55, "-")
    C.update(T_hover_N=T_h, P_hover_kw=P_h, Q_hover_Nm=Q_h, omega_hover=om_h, P_hover_ceiling_kw=P_h_c)

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
    ratio = worst * n                      # worst remaining thrust / mean hover thrust
    C.update(oei_lp_ratio=ratio, oei_worst_failed=worst_name)
    compare("O1", "one motor out", "worst remaining rotor thrust / mean hover thrust (LP)", ratio,
            d["loading_cases"]["pilot + passenger (MTOW)"]["oei_thrust_ratio_to_hover"], "-",
            "WP M linear programme on geometry.json hubs and spins (Fz, roll, pitch, yaw trimmed)")
    # OEI 1.0 g at 1000 m with the 10 % thrust control margin; fixed pitch: Q ~ T at constant CT/CQ
    t_oei = ratio * (1 + REF["k_ctrl"])
    Q_oei = Q_h * t_oei
    om_oei = om_h * math.sqrt(t_oei * rho_h / rho_c)
    P_oei = Q_oei * om_oei / 1e3
    compare("O2", "one motor out", "OEI shaft power, worst rotor, 1000 m, +10 % control", P_oei, res["rotor_out_max_shaft_power_kw"],
            "kW", "fixed pitch: T ~ rho n^2, Q ~ T, P = Q x Omega", design_conservative_if="higher")
    compare("O3", "one motor out", "OEI torque, worst rotor, 1000 m, +10 % control", Q_oei, res["rotor_out_max_torque_nm"],
            "N m", "Q = Q_hover x T/T_hover")
    # flare 1.1 g at 500 m (no extra control margin; the 0.1 g is the reserve)
    n_fl = d["results"]["rotor_out_flare_load_factor_required_g"]
    t_fl = ratio * n_fl
    Q_fl = Q_h * t_fl
    P_fl = Q_fl * om_h * math.sqrt(t_fl) / 1e3
    compare("O4", "one motor out", f"flare {n_fl:.2f} g one motor out, shaft power, 500 m", P_fl, res["rotor_out_flare_shaft_power_kw"], "kW",
            "as O2 at 500 m")
    compare("O5", "one motor out", f"flare {n_fl:.2f} g one motor out, torque, 500 m", Q_fl, res["rotor_out_flare_torque_nm"], "N m", "as O3")
    for key, rt in MOTOR_RATINGS.items():
        tag = "S" if key == "summary" else "T"
        limit(f"M{tag}1", "motor rating", f"hover shaft power, 1000 m <= continuous ({key} ratings)", P_h_c, rt["p_cont"], "kW", note=rt["src"])
        if rt["q_cont"]:
            limit(f"M{tag}2", "motor rating", f"hover torque <= continuous torque ({key})", Q_h, rt["q_cont"], "N m")
        limit(f"M{tag}3", "motor rating", f"OEI power <= peak ({key})", P_oei, rt["p_peak"], "kW", design=res["rotor_out_max_shaft_power_kw"])
        limit(f"M{tag}4", "motor rating", f"OEI torque <= peak ({key})", Q_oei, rt["q_peak"], "N m", design=res["rotor_out_max_torque_nm"])
        limit(f"M{tag}5", "motor rating", f"flare power <= peak ({key})", P_fl, rt["p_peak"], "kW", design=res["rotor_out_flare_shaft_power_kw"])
        limit(f"M{tag}6", "motor rating", f"flare torque <= peak ({key})", Q_fl, rt["q_peak"], "N m", design=res["rotor_out_flare_torque_nm"])
    C.update(P_oei_kw=P_oei, Q_oei_Nm=Q_oei, P_flare_kw=P_fl, Q_flare_Nm=Q_fl)

    # ------------------------------------------------------------------ 3. cruise
    w = d["wing"]
    S, b = w["area_m2"], w["span_m"]
    AR = b * b / S
    V = d["mission"]["cruise_speed_kmh"] / 3.6
    q = 0.5 * rho_h * V * V
    CL = W / (q * S)
    # independent drag area: CFD 3.1 total scaled to the 3.2 geometry, component by component
    f31 = REF["cfd31_drag_area"]
    d_wing = REF["cfd31_wing_cd0_area"] * (S / REF["cfd31_S"] - 1)
    d_fus = -(REF["cfd31_fus_pusher_on"] - REF["cfd31_fus_pusher_off"])          # tail-cone pusher removed
    pm_d = d["lift_rotors"]["motor_diameter_m"]
    d_pods = d["pusher"]["count"] * REF["pod_cd_frontal"] * math.pi * (pm_d / 2) ** 2 * 2.0   # motor + inverter pod
    d_rot = REF["cfd31_rotors"] * ((D / REF["cfd31_D"]) ** 2 - 1)
    d_boom = REF["cfd31_booms"] * (d["booms"]["length_m"] / REF["cfd31_boom_len"] - 1)
    f32 = f31 + d_wing + d_fus + d_pods + d_rot + d_boom
    CD0 = f32 / S
    C.update(drag_area_build=dict(cfd31=f31, wing=d_wing, fuselage_no_tailcone_pusher=d_fus, pusher_pods=d_pods,
                                  rotors=d_rot, booms=d_boom, total=f32))
    compare("A1", "cruise", "zero-lift drag area CD0 x S", f32, d["drag"]["drag_area_m2"], "m2",
            "CFD 3.1 drag area (0.729 m2) scaled to the 3.2 geometry by component")
    compare("A2", "cruise", "CD0", CD0, d["drag"]["cd0"], "-", "A1 / S")

    def oswald_raymer(ar):
        return 1.78 * (1 - 0.045 * ar ** 0.68) - 0.64
    e = REF["cfd31_e"] * oswald_raymer(AR) / oswald_raymer(REF["cfd31_AR"])
    compare("A3", "cruise", "Oswald factor e", e, w["oswald"], "-", "CFD 3.1 e (0.734) x Raymer AR correction")
    CDi = CL * CL / (math.pi * AR * e)
    Dc = q * S * (CD0 + CDi)
    compare("A4", "cruise", "cruise drag, 129 km/h, 500 m ISA+15", Dc, res["cruise_drag_N"], "N", "parabolic polar")
    compare("A5", "cruise", "cruise L/D", W / Dc, res["cruise_LD"], "-", "W / D")
    info("A6", "cruise", "cruise CL (fraction of flaps-down CLmax)", CL, "-",
         note=f"{CL / w['cl_max']:.0%} of CLmax; the CFD polar fit (2-8 deg) and the e validation (CL 0.3) do not cover CL 1.28")
    C.update(V_cruise=V, q_cruise=q, CL_cruise=CL, CD0=CD0, e=e, D_cruise=Dc)

    # pusher: actuator disc x profile factor, thrust deduction
    pu = d["pusher"]
    npu, Dp = pu["count"], pu["diameter_m"]
    Ap = math.pi * Dp ** 2 / 4
    T_p = Dc / (1 - REF["thrust_deduction"]) / npu
    eta_i = 2 / (1 + math.sqrt(1 + T_p / (q * Ap)))
    eta_p = REF["prop_profile"] * eta_i
    compare("P1", "pusher", "pusher propulsive efficiency", eta_p, pu["eta_cruise"], "-", "actuator disc x 0.90 (McCormick)")
    P_p = T_p * V / eta_p / 1e3
    om_p = pu["rpm_cruise"] * math.pi / 30
    Q_p = P_p * 1e3 / om_p
    P_cr_el = npu * P_p / eta_d + REF["aux_kw"]
    compare("P2", "pusher", "cruise electrical power", P_cr_el, res["cruise_electrical_power_kw"], "kW",
            "D/(1-t) V / eta_p / eta_drive + aux")
    limit("P3", "pusher", "pusher shaft power x 1.10 <= continuous (summary 36 kW per REB 60)", P_p * 1.10,
          MOTOR_RATINGS["summary"]["p_cont"], "kW", note="kept rule: 10 % continuous margin")
    limit("P4", "pusher", "pusher cruise torque <= table continuous 95 N m", Q_p, 95.0, "N m",
          note=f"at {pu['rpm_cruise']:.0f} rpm; summary block gives no continuous torque")
    limit("P5", "pusher", "pusher cruise torque <= peak 250 N m", Q_p, 250.0, "N m")
    p_pk = min(MOTOR_RATINGS["summary"]["p_peak"], 250.0 * om_p / 1e3)
    roc = (npu * p_pk * 1e3 * eta_p * (1 - REF["thrust_deduction"]) - Dc * V) / W
    compare("P6", "pusher", "climb rate at cruise speed, pusher peak torque", roc, res["climb_rate_ms"], "m/s",
            "(P_peak eta_p (1-t) - D V) / W, peak torque-limited at 1,550 rpm")
    limit("P7", "pusher", "climb rate >= 1.0 m/s", roc, 1.0, "m/s", sense=">=")
    C.update(T_pusher_each=T_p, eta_p=eta_p, P_pusher_each_kw=P_p, Q_pusher_Nm=Q_p, P_cruise_el_kw=P_cr_el, roc=roc)

    # ------------------------------------------------------------------ 4. battery and range
    bt = d["battery"]
    cell = bt["cell"]
    ncell = bt["series"] * bt["parallel"]
    E_nom = ncell * cell["energy_wh"] / 1e3
    compare("B1", "battery", "nominal energy (cells x Wh)", E_nom, bt["energy_nominal_kwh"], "kWh", "175 x 15 x 18 Wh")
    m_b = d["mass_kg"]["battery"]
    info("B2", "battery", "pack specific energy", E_nom * 1e3 / m_b, "Wh/kg",
         note="Pipistrel Velis pack about 177 Wh/kg on 253 Wh/kg cells (EQUATIONS.md); NASA L+C assumes 400", verdict="PASS")
    r_eol = cell["dcir_ohm"] * REF["dcir_eol_factor"]

    def eta_batt(p_kw, cells=ncell, v=REF["v_oc_mid"]):
        i, vt = cell_current(p_kw * 1e3 / cells, v, r_eol)
        return vt / v if vt else float("nan")
    eb_h, eb_cr = eta_batt(P_h_el), eta_batt(P_cr_el)
    eb_tr = eta_batt(0.5 * (P_h_el + P_cr_el))
    compare("B3", "battery", "battery efficiency in hover (exact I-R, mid SOC, EOL resistance)", eb_h,
            d["efficiencies"]["battery_hover"], "-", "V_terminal / V_oc with I from P = I (V_oc - I R)",
            note="design linearises with I = P / V_nom, which under-states the current when the voltage sags")
    t_h = d["mission"]["hover_takeoff_s"] + d["mission"]["hover_landing_s"]
    t_tr = d["mission"]["transitions"] * d["mission"]["transition_each_s"]
    E_h = P_h_el * t_h / 3600 + W * d["mission"]["vertical_climb_m"] / eta_d / 3.6e6
    E_tr = 0.5 * (P_h_el + P_cr_el) * t_tr / 3600
    E_cl = W * (500.0 - d["mission"]["transition_altitude_m"]) / (eta_p * eta_d) / 3.6e6
    E_fix = E_h / eb_h + E_tr / eb_tr + E_cl / eb_cr
    P_cr_cells = P_cr_el / eb_cr
    E_use = E_nom * REF["f_eol"] * (1 - REF["f_res"])
    rng = (E_use - E_fix) / P_cr_cells * V * 3.6
    E_20 = E_fix + P_cr_cells * 20.0 / (V * 3.6)
    compare("R1", "range", "mission energy at the cells, 20 km", E_20, res["mission_energy_kwh"], "kWh",
            "hover 120 s + vertical climb + 2 x 30 s transitions (mean power) + climb to 500 m + cruise")
    compare("R2", "range", "range capability (EOL 80 %, 20 % reserve)", rng, res["range_km"], "km", "(E_usable - E_fixed) / P_cruise x V",
            design_conservative_if="lower")
    limit("R3", "range", "range >= 20 km", rng, 20.0, "km", sense=">=")
    # sensitivity: design-style linear battery efficiency, same mission
    eb_lin = lambda p: min(1 - (p * 1e3 / (ncell * cell["v_nom"])) * r_eol / cell["v_nom"], 0.95)
    E_fix_lin = E_h / eb_lin(P_h_el) + E_tr / eb_lin(0.5 * (P_h_el + P_cr_el)) + E_cl / eb_lin(P_cr_el)
    rng_lin = (E_use - E_fix_lin) / (P_cr_el / eb_lin(P_cr_el)) * V * 3.6
    info("R4", "range", "range with the linearised battery efficiency (sensitivity)", rng_lin, "km",
         note="isolates the effect of the battery-loss model on R2")
    C.update(eta_batt_hover=eb_h, eta_batt_cruise=eb_cr, E_fixed_kwh=E_fix, E_usable_kwh=E_use, range_km=rng,
             range_lin_km=rng_lin)

    # C-rate and cell currents
    E_eol = E_nom * REF["f_eol"]
    c_h = P_h_el_c / eta_batt(P_h_el_c) / E_eol
    compare("B4", "battery", "hover C-rate at the ceiling (EOL capacity)", c_h, res["c_rate_hover"], "1/h", "P_cells / E_EOL")
    c_lim = REF["i_cont_cell"] / (cell["capacity_ah"] * REF["f_eol"]) - REF["dC"]
    limit("B5", "battery", "hover C-rate <= 40 A continuous / EOL Ah - 0.3 C", c_h, c_lim, "1/h", note="requirement '0.3 C margin'")
    i_all, v_all = cell_current(P_h_el_c * 1e3 / ncell, REF["v_oc_low"], r_eol)
    limit("B6", "battery", "hover cell current, all packs, ceiling, low SOC, EOL", i_all, REF["i_peak_cell"], "A")
    npk = bt["independent_packs"]
    cells_1 = ncell * (npk - 1) / npk
    P_1 = n * P_h / eta_d                 # land immediately at the 500 m site, aux shed
    i_1, v_1 = cell_current(P_1 * 1e3 / cells_1, REF["v_oc_low"], r_eol)
    limit("B7", "battery", "one pack out: cell current <= 60 A (hover 500 m, aux shed, low SOC, EOL)", i_1, 60.0, "A", design=59.6)
    limit("B8", "battery", "one pack out: bus voltage >= 400 V", v_1 * bt["series"], 400.0, "V", sense=">=", design=403.6)
    i_1c, v_1c = cell_current(n * P_h_c / eta_d * 1e3 / cells_1, REF["v_oc_low"], r_eol)
    info("B9", "battery", "one pack out at the 1000 m ceiling: cell current / bus (sensitivity)",
         i_1c if i_1c else float("nan"), "A", note=f"bus {v_1c * bt['series']:.0f} V" if v_1c else "beyond the pack maximum power")
    i_r12, v_r12 = cell_current(P_1 * 1e3 / cells_1, REF["v_oc_low"], cell["dcir_ohm"] * 1.2)
    info("B10", "battery", "one pack out with EOL resistance x 1.2 instead of x 1.5 (sensitivity)", i_r12, "A",
         note=f"bus {v_r12 * bt['series']:.0f} V")
    C.update(i_cell_hover_all=i_all, i_cell_1pack=i_1, v_bus_1pack=v_1 * bt["series"])

    # ------------------------------------------------------------------ 5. stall
    clmax = w["cl_max"]
    cfd_flap = None
    sp = ROOT / "cfd/results/summary.json"
    if sp.exists():
        s = json.loads(sp.read_text())
        cfd_flap = s.get("flaps", {}).get("delta_35", {}).get("CLmax_flaps")
    if cfd_flap:
        compare("S1", "stall", "CLmax flaps down (35 deg) vs CFD 3.1", cfd_flap, clmax, "-",
                "2-D CFD flap increment x Swf/S on the 3-D clean CFD CLmax (cfd/results/summary.json)")
    Vs = math.sqrt(2 * W / (RHO_SL * S * clmax))
    compare("S2", "stall", "stall speed EAS, MTOW, flaps down", Vs, res["stall_speed_ms"], "m/s", "sqrt(2W / (rho0 S CLmax))")
    V_eas = V * math.sqrt(rho_h / RHO_SL)
    limit("S3", "stall", "cruise >= 1.15 Vs (EAS)", V_eas / Vs, 1.15, "-", sense=">=")
    limit("S4", "stall", "cruise speed >= 120 km/h", V * 3.6, 120.0, "km/h", sense=">=")
    C.update(Vs_eas=Vs, V_cruise_eas=V_eas)

    # ------------------------------------------------------------------ 6. footprint
    xs = [r["hub"][0] - r["diameter_m"] / 2 for r in rot] + [r["hub"][0] + r["diameter_m"] / 2 for r in rot]
    xs += [p.get("spinner", {}).get("x_to", p["hub"][0]) for p in g["pushers"]] + [g["fuselage"]["x_nose"], g["fuselage"]["x_tail"]]
    xs += [bm["x_front"] for bm in g["booms"]] + [bm["x_aft"] for bm in g["booms"]]
    length = max(xs) - min(xs)
    ys = [abs(r["hub"][1]) + r["diameter_m"] / 2 for r in rot] + [b / 2]
    width = 2 * max(ys)
    limit("F1", "footprint", "overall length (rotor discs to pusher spinners)", length, 10.5, "m", design=10.457,
          note="original requirement 9.0 m: exceeded by %.2f m" % (length - 9.0))
    limit("F2", "footprint", "overall width", width, 10.5, "m")
    C.update(length=length, width=width)

    # ------------------------------------------------------------------ 7. weight build-up vs CAD
    bd = d["mass_kg"]["breakdown"]
    empty_sum = sum(bd.values())
    compare("W1", "mass", "empty mass = sum of the breakdown", empty_sum, d["mass_kg"]["empty"], "kg", "sum")
    compare("W2", "mass", "MTOW = empty + battery + payload", empty_sum + m_b + d["mass_kg"]["payload"], mtow, "kg", "sum")
    cad_fresh = cad_is_fresh(cutoff)
    out["inputs"]["cad_mass_properties_mtime"] = str(mtime("cad/mass_properties.json"))
    cadp = ROOT / "cad/mass_properties.json"
    cad_note = "" if cad_fresh else " [provisional: CAD files of %s; the 3.2 rebuild with the FEA fixes has not finished]" % mtime("cad/mass_properties.json").strftime("%Y-%m-%d %H:%M")
    if cadp.exists():
        cad = json.loads(cadp.read_text())
        grp = {k: v["kg"] for k, v in cad["by_group"].items()}
        growth = bd.get("growth", 0.0)
        cad_mtow = cad["cad_mass_kg"] + growth
        cad_empty = cad_mtow - grp.get("battery", 0) - grp.get("payload", 0)
        rows_cad = [
            compare("W3", "mass vs CAD", "MTOW, CAD (incl. the design growth allowance)", cad_mtow, mtow, "kg", "cad/mass_properties.json + growth", note=cad_note.strip()),
            compare("W4", "mass vs CAD", "empty mass excl. battery, CAD (incl. growth)", cad_empty, d["mass_kg"]["empty"], "kg", "CAD", note=cad_note.strip()),
            compare("W5", "mass vs CAD", "battery, CAD", grp.get("battery", 0), m_b, "kg", "CAD", note=cad_note.strip()),
        ]
        for k in ("wing", "booms", "fuselage", "tail", "landing_gear", "rotor_pylons_mounts", "pusher_motor"):
            if k in grp and k in bd:
                rows_cad.append(compare(f"W6-{k}", "mass vs CAD", f"group {k}, CAD", grp[k], bd[k], "kg", "CAD", note=cad_note.strip()))
        r = limit("W7", "mass vs CAD", "CAD MTOW excl. growth <= parachute rating 1,190 kg", cad["cad_mass_kg"], 1190.0, "kg",
                  note="growth allowance consumed by the as-built CAD" + cad_note)
        rows_cad.append(r)
        r = limit("W8", "mass vs CAD", "CAD MTOW incl. growth <= parachute rating 1,190 kg", cad_mtow, 1190.0, "kg", note=cad_note.strip())
        rows_cad.append(r)
        if not cad_fresh:
            for rr in rows_cad:
                rr["provisional_verdict"] = rr["verdict"]
                rr["verdict"] = "PENDING"
        C.update(cad_mtow_incl_growth=cad_mtow, cad_mtow_excl_growth=cad["cad_mass_kg"], cad_fresh=cad_fresh)
    else:
        pending("W3", "mass vs CAD", "MTOW vs CAD", "cad/mass_properties.json missing")

    # ------------------------------------------------------------------ 8. wing and boom bending
    lim_n = d["structure"]["limit_load_factor_positive"]
    n_ult = 1.5 * lim_n
    s_half = b / 2
    y = np.linspace(0, s_half, 4001)
    L_half = n_ult * W / 2
    l0 = 4 * L_half / (math.pi * s_half)
    lift = l0 * np.sqrt(np.clip(1 - (y / s_half) ** 2, 0, None))
    y0 = g["wing"]["root_fittings_y"]
    msk = y >= y0
    M_lift = np.trapezoid(lift[msk] * (y[msk] - y0), y[msk])
    boom_items = [m for m in g["mass_items"] if m.get("attach") == "boom_L"]
    m_boom_side = sum(m["kg"] for m in boom_items) + bd["tail"] / 2
    y_boom = abs(g["booms"][0]["y"])
    m_wing_out = bd["wing"] / 2 * (s_half - y0) / s_half
    M_rel = n_ult * G0 * (m_boom_side * (y_boom - y0) + m_wing_out * (s_half - y0) / 2)
    M_root = M_lift - M_rel
    fe = jload("fea/results/airframe_design.json")
    fa = fe["cases"]["F A  manoeuvre +n at VA"]["groups"]
    M_fea = fa["spar main"]["M"] + fa["spar rear"]["M"]
    compare("ST1", "structure", "wing ultimate bending at the root fitting, +3.8 g x 1.5", M_root / 1e3, M_fea / 1e3, "kN m",
            "elliptic lift on the full span minus the inertia of the boom groups and outer wing (no tail load)",
            note="FEA value = main + rear spar moments, case F A", design_conservative_if="higher")
    lift_s = 0.5 * (lift + L_half / s_half)               # Schrenk for the rectangular planform
    M_schrenk = np.trapezoid(lift_s[msk] * (y[msk] - y0), y[msk]) - M_rel
    info("ST1b", "structure", "wing ultimate bending with the Schrenk distribution (sensitivity)", M_schrenk / 1e3, "kN m",
         note=f"{100 * (M_schrenk / M_fea - 1):+.1f} % vs FEA (the FEA loads module uses Schrenk, verify_loads L2)")
    su = jload("fea/results/sizing_update.json")["wing"]["spars"]

    def sec_at(sp, eta):
        st = min(sp["stations"], key=lambda s_: abs(s_["eta"] - eta))["section"]
        return st
    eta0 = y0 / s_half
    I_tot, h_main = 0.0, None
    for sp in su:
        sc = sec_at(sp, eta0)
        a_cap = sc["b_cap"] * sc["t_cap"]
        dcap = sc["h"] / 2 - sc["t_cap"] / 2
        I_tot += 2 * a_cap * dcap ** 2
        if sp["name"] == "main":
            h_main = sc["h"]
    sig_w = M_fea * (h_main / 2) / I_tot / 1e6   # stress from the FEA moment, own section
    sig_w_own = M_root * (h_main / 2) / I_tot / 1e6
    compare("ST2", "structure", "main-spar cap stress, ultimate, case F A", sig_w_own, -fa["spar main"]["sigma_c"] / 1e6, "MPa",
            "M c / I of the four spar caps at the root fitting (sizing_update.json sections)",
            note=f"with the FEA moment the same section gives {sig_w:.0f} MPa", design_conservative_if="higher")
    mat = jload("fea/materials.json")["materials"]
    ud = mat["cf_ud_wet"]["design"]
    allow_c = min(ud["Xc"], ud["E1"] * ud["eps_c"]) / 1e6
    limit("ST3", "structure", "main-spar cap compression <= UD design allowable", sig_w_own, allow_c, "MPa")

    # boom: overhang moments at the saddles (statically determinate) for R2 (all rotors max thrust)
    bseg = jload("fea/results/sizing_update.json")["booms"][0]["segments"]
    xs_att = g["booms"][0]["attach_x"]
    x_f, x_r = min(xs_att), max(xs_att)
    T_max = rot[0].get("max_thrust_N") or g["rotors"][0]["max_thrust_N"]
    a_z = (n * T_max - W) / mtow
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
    M_r2 = 1.5 * max(abs(overhang(x_f, "front", T_max, n_eff)), abs(overhang(x_r, "aft", T_max, n_eff)))
    fr2 = fe["cases"]["R2 all rotors max thrust"]["groups"]["boom_L"]
    compare("ST4", "structure", "boom ultimate bending, all rotors at max thrust (R2)", M_r2 / 1e3, fr2["M"] / 1e3, "kN m",
            "overhang moment at the wing saddle, inertia relief, x 1.5")
    # parachute vertical opening (C3): n_open x 1.5 on the boom masses
    n_open = g["parachute"]["n_open_limit"]
    M_c3 = 1.5 * max(abs(overhang(x_f, "front", 0.0, n_open)), abs(overhang(x_r, "aft", 0.0, n_open)))
    fc3 = fe["cases"]["C3 parachute opening 4.3 g, vertical (inflated, low speed)"]["groups"]["boom_L"]
    compare("ST5", "structure", "boom ultimate bending, parachute opening vertical (C3)", M_c3 / 1e3, fc3["M"] / 1e3, "kN m",
            "overhang moment at the rear saddle, n_open 4.25 x 1.5 on the boom masses", design_conservative_if="higher",
            note="FEA higher: its peak boom moment in C3 is not the saddle overhang; load path to be confirmed by WP F")

    def tube_stress(M, x):
        seg = [s_ for s_ in bseg if s_["x_from"] <= x <= s_["x_to"]][0]["section"]
        r_in = seg["id"] / 2
        EI, layers = 0.0, []
        for L_ in seg["layers"]:
            r_out = r_in + L_["t"]
            mname = L_["material"]
            mm = mat.get(mname) or mat.get("cf_fabric_wet")
            E = (mm.get("design", {}).get("E1") or mm.get("design", {}).get("E") or 15e9)
            if mname.endswith("_45"):
                E = 15e9                     # +-45 fabric, axial modulus (estimate)
            I = math.pi / 4 * (r_out ** 4 - r_in ** 4)
            EI += E * I
            layers.append((mname, r_out, E))
            r_in = r_out
        return {mn: M * r * E / EI / 1e6 for mn, r, E in layers}
    st_r2 = tube_stress(M_r2, x_f)
    compare("ST6", "structure", "boom UD over-wrap stress, R2, front saddle", st_r2["cf_ud_wet"], -fr2["sigma_c"] / 1e6, "MPa",
            "E-weighted composite tube, M r E / sum(E I)")
    C.update(wing_root_M_kNm=M_root / 1e3, wing_root_M_fea_kNm=M_fea / 1e3, boom_M_R2_kNm=M_r2 / 1e3, boom_M_C3_kNm=M_c3 / 1e3,
             boom_stress_R2=st_r2)

    # ------------------------------------------------------------------ 9. parachute
    para_rating = 1190.0
    limit("CH1", "parachute", "MTOW <= GRS 6 990-1190 rating", mtow, para_rating, "kg")
    F_open = 48.8e3
    compare("CH2", "parachute", "opening load factor at MTOW (48.8 kN vendor)", F_open / W, n_open, "g", "F / W")

    # ------------------------------------------------------------------ 10. cost
    cst = d["cost"]
    bom = list(csv.DictReader((ROOT / "bom/BOM.csv").open()))
    bom_total = sum(float(x["total_usd"] or 0) for x in bom)
    bom_tool = sum(float(x["total_usd"] or 0) for x in bom if x["group"] == "tooling")
    compare("K1", "cost", "prototype cash, BOM.csv roll-up", bom_total, cst["prototype_out_of_pocket_usd"], "USD", "sum of BOM.csv total_usd")
    b_ = math.log2(REF["labour_learning"])
    Nn = cst["units_produced_5yr"]
    lf = sum((k + 1) ** b_ for k in range(Nn)) / Nn
    compare("K2", "cost", "cumulative-average learning factor, N = 10, 85 %", lf, cst["learning_factor_N"], "-", "(1/N) sum n^log2(0.85)")
    labour = cst["labour_hours_prototype"] * cst["labour_rate_usd_h"] * lf
    unit_N = bom_total - bom_tool + bom_tool / Nn + labour
    compare("K3", "cost", "cost per aircraft at N = 10 from the BOM", unit_N, res["cost_usd"], "USD",
            "BOM - tooling + tooling/N + hours x rate x learning")
    est = sum(float(x["total_usd"] or 0) for x in bom if "estimate" in x["price_type"] or "quote" in x["price_type"])
    info("K4", "cost", "share of the BOM on estimates / quote-required prices", 100 * est / bom_total, "%",
         note="manufacturing/QUOTES_TO_REQUEST.md")
    C.update(bom_total=bom_total, unit_N_from_bom=unit_N)

    # ------------------------------------------------------------------ 11. WP M checker on the frozen design (in memory)
    try:
        chk = wpm.Checker(d, g).run()
        out["wpm_checker_summary"] = chk["summary"]
        out["wpm_checker_nonpass"] = [dict(quantity=r_["quantity"], M=r_["M"], D=r_["D"], status=r_["status"],
                                           diff=r_.get("diff")) for r_ in chk["rows"] if r_["status"] not in ("PASS", "INFO")]
    except Exception as exc:  # pragma: no cover
        out["wpm_checker_summary"] = {"error": str(exc)}

    # ------------------------------------------------------------------ 12. CFD 3.2 rows
    cfd32 = ROOT / "cfd/results/iteration32/summary.json"
    cfd32c = ROOT / "cfd/results/iteration32/cruise.json"
    out["inputs"]["cfd32_present"] = cfd32.exists()
    if cfd32.exists():
        s32 = json.loads(cfd32.read_text())
        pm = s32.get("cfd_production_mesh", {})
        cd0_32 = pm.get("CD0_incl_pods", pm.get("CD0"))
        if cd0_32:
            compare("CF1", "CFD 3.2", "CD0, CFD on the 3.2 geometry", cd0_32, d["drag"]["cd0"], "-", "cfd/results/iteration32/summary.json")
        if pm.get("oswald_e"):
            compare("CF2", "CFD 3.2", "Oswald e, CFD 3.2", pm["oswald_e"], w["oswald"], "-", "cfd/results/iteration32/summary.json")
        fl = s32.get("flaps", {}).get("delta_35", {}).get("CLmax_flaps")
        if fl:
            compare("CF3", "CFD 3.2", "CLmax flaps down, CFD 3.2", fl, clmax, "-", "cfd/results/iteration32/summary.json")
        for k_, lab in (("download_fraction", "hover download"), ("thrust_deduction", "pusher thrust deduction")):
            v_ = s32.get(k_) or s32.get("hover", {}).get(k_) or s32.get("pusher", {}).get(k_)
            ref_ = lr["download_fraction"] if k_ == "download_fraction" else REF["thrust_deduction"]
            if v_:
                compare("CF4" if k_ == "download_fraction" else "CF5", "CFD 3.2", lab + ", CFD 3.2", v_, ref_, "-", "cfd/results/iteration32/summary.json")
            else:
                pending("CF4" if k_ == "download_fraction" else "CF5", "CFD 3.2", lab + ", CFD 3.2", "key not in the 3.2 summary yet")
    else:
        for cid, qn in (("CF1", "CD0 on the 3.2 geometry"), ("CF2", "Oswald e on the 3.2 geometry"),
                        ("CF3", "CLmax flaps down on the 3.2 geometry (1.15 Vs margin 0.2 %)"),
                        ("CF4", "hover download on the 3.2 geometry"),
                        ("CF5", "boom-tail pusher thrust deduction (assumed 4.5 %)")):
            pending(cid, "CFD 3.2", qn, "cfd/results/iteration32/summary.json not present yet")
    out["inputs"]["cfd32_cruise_present"] = cfd32c.exists()
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
    e8 = dict(name="E8-200 T8", mtow=mt, empty_fraction=(m["empty"] + m["battery"]) / mt, disk_loading=res["disk_loading_N_m2"],
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
        ax.scatter([e8["mtow"]], [e8[k]], s=90, marker="D", color=ORANGE, edgecolor="#fcfcfb", linewidth=1.5, zorder=4, label="E8-200 T8")
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
    fig.suptitle("E8-200 T8 against benchmark eVTOL and electric aircraft (methods/benchmarks, resources/benchmarks_raw.json)",
                 fontsize=10.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


# ============================================================================== WP evidence and the matrix
def wp_evidence(cutoff, R, out):
    """Status of each WP's own V&V evidence; CAD / CFD rows go to PENDING until their 3.2 files land."""
    ev = {}
    # sizing
    vr = ROOT / "validation/sizing/verification_report.md"
    m_ = re.search(r"\*\*(\d+) PASS, (\d+) FAIL\*\*", vr.read_text()) if vr.exists() else None
    ev["sizing"] = dict(status="PASS" if m_ and m_.group(2) == "0" else "FLAG",
                        result=f"verify_sizing.py: {m_.group(1)} PASS, {m_.group(2)} FAIL" if m_ else "report missing")
    # methods
    s = out.get("wpm_checker_summary", {})
    ev["methods"] = dict(status="PASS", result="NASA L+C reproduction: hover power, C-rate and battery energy within 5 %, mission energy -3 %; "
                         f"WP M checker on the 3.2 design (run in memory here): {s.get('PASS', '?')} PASS, {s.get('WARN', '?')} WARN, {s.get('FAIL', '?')} FAIL")
    # parts
    ev["parts"] = dict(status="FLAG", result="pass-2 duty check vs both REB 60 rating sets; table ratings fail; parts check still at 1,770 rpm and counter-rotating pushers (design is 1,550 rpm, co-rotating)")
    # fea
    mg = jload("fea/results/margins.json")["margins"]
    neg = [x for x in mg if x["MS"] < 0]
    ev["fea_tool"] = dict(status="PASS", result="B1-B7 beam exact to 1.3 %; NAFEMS LE1 +0.5 %, LE10 +0.7 %, FV52 0.6 %; CLT 0.3 %; Goland flutter 137.3 vs 137.2 m/s; L6 root bending -0.5 %")
    ev["fea_design"] = dict(status="FAIL" if neg else "PASS", result=f"{len(neg)} of {len(mg)} margins negative (lowest {min(x['MS'] for x in mg):+.2f})", neg=neg)
    # cfd tool validation
    ev["cfd_tool"] = dict(status="PASS", result="NACA 0012 cd(0) +0.9 %, cl(10) -0.5 %, cl(15) +3 %; GA(W)-1 clmax -3 %; actuator disc +3 %; 3-D wing L+1 CD0 +6 %; download conservative x 1.46")
    cfd_fresh = (ROOT / "cfd/results/iteration32/summary.json").exists()
    cfdv_fresh = (mtime("validation/cfd/README.md") or dt.datetime.min) >= cutoff
    ev["cfd_design"] = dict(status="PENDING" if not cfd_fresh else "PASS",
                            result="3.2 aircraft CFD present" if cfd_fresh else "3.1 CFD only (CD0 0.0704, e 0.734, CLmax flaps 1.70, download 5.5 %); 3.2 re-run in progress")
    ev["cfd_mesh32"] = dict(status="PASS" if cfdv_fresh else "PENDING",
                            result="validation/cfd updated for 3.2" if cfdv_fresh else "aircraft mesh check is for 3.1 (validation/cfd sec. 6.1)")
    # cad
    cad_fresh = cad_is_fresh(cutoff)
    cl = jload("validation/cad/clearance_checks.json")
    nf = sum(1 for c in cl if c["status"] == "FAIL")
    nw = sum(1 for c in cl if c["status"] == "WARN")
    itf = jload("validation/cad/interference.json")
    unexp = [o for o in itf["overlaps"] if not o.get("expected_contact")]
    au = jload("validation/cad/mass_cg_audit.json")
    st = "FAIL" if nf else ("FLAG" if (nw or unexp) else "PASS")
    ev["cad"] = dict(status=st if cad_fresh else "PENDING",
                     provisional=st,
                     result=(f"{len(cl) - nf - nw} of {len(cl)} clearance checks pass, {nw} WARN, {nf} FAIL; "
                             f"{len(unexp)} unexpected overlaps > 2 cm3, {itf.get('failed_pairs')} pairs not evaluated; "
                             f"CAD MTOW {au['totals']['MTOW (pilot + passenger)']['cad_kg']:.1f} kg, static margin {au['static_margin_cad']:.3f}"),
                     clear=cl, sm=au["static_margin_cad"])
    return ev


def build_matrix(R, ev, req_txt):
    """One row per requirement (incl. the relaxed ones) and per analysis tool."""
    def st(*ids):
        vs = [R[i]["verdict"] for i in ids if i in R]
        for k in ("FAIL", "PENDING", "FLAG", "OPEN", "PASS"):
            if k in vs:
                return k
        return "OPEN"

    def val(i, fmt="{:.3g}"):
        r = R.get(i)
        if not r or r.get("independent") is None:
            return "-"
        return fmt.format(r["independent"])

    def mg(i):
        r = R.get(i)
        return f"{r['margin_pct']:+.1f} %" if r and "margin_pct" in r else "-"
    I = "independent/results.md"
    Y = lambda k, blk=None: yaml_scalar(req_txt, k, blk)
    rows = []

    def add(group, req, method, evid, result, status):
        rows.append(dict(group=group, req=req, method=method, evidence=evid, result=result, status=status))
    # payload
    add("Payload", f"Payload {Y('total_kg'):.0f} kg (pilot + 100 kg cargo or 2 x 100 kg)", "mass closure; three loading cases",
        f"[{I}](../independent/iteration32/results.md#mass), [design/selected_design.json](../design/selected_design.json)",
        f"MTOW closes ({val('W2', '{:.1f}')} kg); static margin 0.072-0.100 in the three cases", st("W1", "W2"))
    add("Payload", "Cabin: 2 seats, removable second seat, cargo bay >= 0.6 x 0.5 x 0.5 m", "CAD clearance audit, geometry",
        "[cad/clearance_checks.md](cad/clearance_checks.md)", "bay 0.65 x 0.60 x 0.55 m; door 0.62 x 0.67 m; head clearance 88 / 62 mm",
        ev["cad"]["status"])
    # mission
    add("Mission", f"Design range {Y('design_range_km'):.0f} km (was 100 -> 50 -> 20 km, see requirements.yaml)", "hand mission energy, exact cell I-R",
        f"[{I}](../independent/iteration32/results.md#range)", f"{val('R2', '{:.1f}')} km vs design 21.2 km (margin {mg('R3')})", st("R1", "R2", "R3"))
    add("Mission", "Range sensitivity to 30 / 60 / 100 km reported", "document review",
        "[sizing/README.md](../sizing/README.md), [methods/initial_estimate.md](../methods/initial_estimate.md)",
        "reported for iteration 3 (largest closing 25.9 km) and the initial estimate; not re-run for 3.2", "FLAG")
    add("Mission (relaxed)", "Cruise >= 120 km/h. Was 135 (3.1) and 150 (1-3); relaxed by the owner if cheaper, provided cruise >= 1.15 Vs",
        "design value", f"[{I}](../independent/iteration32/results.md#stall)", f"129 km/h (margin {mg('S4')})", st("S4"))
    add("Mission", "Hover 60 s take-off (incl. 30 m climb) + 60 s landing, 2 x 30 s transitions", "included in the hand mission energy",
        f"[{I}](../independent/iteration32/results.md#range)", f"mission energy {val('R1', '{:.2f}')} kWh vs design 29.48", st("R1"))
    add("Mission", "Reserve 20 % at landing, 0.3 C margin, cells at 80 % EOL", "usable energy and C-rate by hand",
        f"[{I}](../independent/iteration32/results.md#battery)", f"usable 30.24 kWh; hover C-rate {val('B4', '{:.2f}')} vs limit 9.7 ({mg('B5')})", st("B4", "B5"))
    add("Mission", "Hover power at 500 m ISA+15", "momentum theory, benchmark FM, CFD download",
        f"[{I}](../independent/iteration32/results.md#hover)", f"{val('H2', '{:.1f}')} kW per motor vs design 31.9", st("H2", "H3"))
    add("Mission (kept)", "Hover ceiling 1000 m ISA+15 OGE within continuous rating", "P ~ rho^-1/2",
        f"[{I}](../independent/iteration32/results.md#motor-rating)", f"{val('H4', '{:.0f}')} kW electrical; per motor {val('MS1', '{:.1f}')} kW vs 36 (summary) / 25 (table)",
        "OPEN" if R.get("MT1", {}).get("verdict") == "FAIL" else st("MS1"))
    add("Configuration", "Lift + cruise, fixed lift rotors on two booms, high wing, rear pusher, H-tail between booms", "inspection of geometry.json",
        "[design/geometry.json](../design/geometry.json)", "8 fixed rotors on 2 booms, shoulder wing, twin boom-tail pushers, H-tail", "PASS")
    add("Objective", "Minimum acquisition cost and complexity; report MTOW, energy, cost", "cost roll-up from the BOM, learning curve",
        f"[{I}](../independent/iteration32/results.md#cost)", f"BOM USD {R['K1']['independent']:,.0f} vs 335,187 ({R['K1']['diff_pct']:+.1f} %); N = 10 USD {R['K3']['independent']:,.0f} vs 442,286",
        st("K1", "K2", "K3"))
    # safety
    add("Safety (kept)", "Ultimate factor 1.5 and all load cases (+3.8 / -1.5 g, 3 g landing)", "FEA margins; hand beam checks of wing and booms",
        "[../fea/results/margins.json](../fea/results/margins.json), [fea/README.md](fea/README.md)",
        f"{ev['fea_design']['result']}; hand wing/boom moments {R['ST1']['diff_pct']:+.0f} % / {R['ST4']['diff_pct']:+.0f} % vs FEA",
        ev["fea_design"]["status"])
    add("Safety (kept)", "One lift motor out: continued hover at MTOW <= 100 % peak, 10 % control margin, OEI torque and rpm",
        "LP thrust allocation, fixed-pitch scaling", f"[{I}](../independent/iteration32/results.md#one-motor-out)",
        f"{val('O2', '{:.1f}')} kW / {val('O3', '{:.0f}')} N m: summary rating {mg('MS3')} / {mg('MS4')}; table rating {mg('MT3')} / {mg('MT4')}",
        "OPEN" if st("MT3", "MT4") == "FAIL" else st("O2", "O3", "MS3", "MS4"))
    add("Safety (relaxed)", "One-motor-out flare 1.10 g. Was 1.20 g; keeps a reserve above the 1.0 g rule (floor 1.05 g)", "as above at 500 m",
        f"[{I}](../independent/iteration32/results.md#one-motor-out)", f"{val('O4', '{:.1f}')} kW / {val('O5', '{:.0f}')} N m: summary {mg('MS5')} / {mg('MS6')}; table {mg('MT5')} / {mg('MT6')}",
        "OPEN" if st("MT5", "MT6") == "FAIL" else st("O4", "O5", "MS5", "MS6"))
    add("Safety (kept)", ">= 2 independent packs; one pack out allows a controlled landing; cell <= 60 A and bus >= 400 V at EOL",
        "exact cell I-R model, low SOC, EOL resistance x 1.5", f"[{I}](../independent/iteration32/results.md#battery)",
        f"5 packs; one out: {val('B7', '{:.1f}')} A ({mg('B7')}), {val('B8', '{:.0f}')} V ({mg('B8')})", st("B7", "B8"))
    add("Safety (kept)", "Whole-aircraft ballistic parachute sized for MTOW", "rating vs MTOW (design and CAD)",
        f"[{I}](../independent/iteration32/results.md#parachute)", f"1,169.5 / 1,190 kg ({mg('CH1')}); CAD incl. growth {val('W8', '{:.0f}')} kg ({mg('W8')})",
        st("CH1", "CH2", "W8"))
    add("Safety", "Occupant: energy-absorbing seats, 4-point harness, rotor plane clear of the cabin", "CAD clearance audit",
        "[cad/clearance_checks.md](cad/clearance_checks.md)", "blade plane 562 mm above the highest occupant point; burst fan 5.3 deg (>= 5); seat stroke 160 mm",
        ev["cad"]["status"])
    add("Safety", "Regulations referenced (Part 103, powered-lift SFAR / AC 21.17-4, SC-VTOL-01, ASTM F3264, CS-23)", "document review",
        "[../resources/README.md](../resources/README.md)", "all cited in resources/README.md with use", "PASS")
    # manufacturing
    add("Manufacturing", "In-house 3-axis CNC / FDM, wet lay-up, COTS tubes; avoid autoclave, metal printing, 5-axis, castings; one motor type",
        "document review", "[../manufacturing/MANUFACTURING_METHODS.md](../manufacturing/MANUFACTURING_METHODS.md)",
        "one motor type (10 x REB 60), 8 distinct part types; wet lay-up over CNC plugs", "PASS")
    # constraints / relaxations
    add("Constraint (relaxed)", "Footprint <= 10.5 m. Was 9.0 m; trailer transport with the wing removed (<= 9.0 preferred if under USD 5k)",
        "extremes of geometry.json", f"[{I}](../independent/iteration32/results.md#footprint)", f"{val('F1', '{:.3f}')} m ({mg('F1')}); 9.0 m does not close (sizing T8_9m)", st("F1", "F2"))
    add("Constraint (relaxed)", "Cruise >= 1.15 Vs (hot day, flaps down). Was 1.30; stall backed up by the lift rotors",
        "Vs EAS from CLmax (CFD 3.1 flaps 35 deg)", f"[{I}](../independent/iteration32/results.md#stall)",
        f"{val('S3', '{:.3f}')} x Vs ({mg('S3')}); CLmax rests on 3.1 CFD", st("S1", "S2", "S3", "CF3"))
    add("Kept", "Pusher continuous margin 10 % and climb >= 1 m/s", "actuator disc, thrust deduction 4.5 %",
        f"[{I}](../independent/iteration32/results.md#pusher)", f"1.1 x shaft {val('P3', '{:.1f}')} kW vs 36 ({mg('P3')}); climb {val('P6', '{:.2f}')} m/s; torque {val('P4', '{:.0f}')} N m vs table 95",
        "OPEN" if st("P4") == "FAIL" else st("P3", "P7"))
    add("Kept", "Tip Mach, door width, blade chord and other constraints", "hand tip Mach; CAD door; sizing G-checks",
        f"[{I}](../independent/iteration32/results.md#hover), [sizing/verification_report.md](sizing/verification_report.md)",
        f"hover Mtip {val('H5', '{:.3f}')}; door 0.62 m >= 0.483", st("H5", "H6"))
    # tools
    add("Tool: sizing", "Sizing code verification (WP D)", "unit tests, audit, integration checks",
        "[sizing/verification_report.md](sizing/verification_report.md)", ev["sizing"]["result"], ev["sizing"]["status"])
    add("Tool: methods", "Equation set and independent checker (WP M)", "NASA Lift+Cruise reproduction",
        "[methods/nasa_lpc_reproduction.md](methods/nasa_lpc_reproduction.md)", ev["methods"]["result"], ev["methods"]["status"])
    add("Tool: parts", "Propulsion parts consistency (WP P)", "duty points vs catalog ratings",
        "[parts/README.md](parts/README.md)", ev["parts"]["result"], ev["parts"]["status"])
    add("Tool: CFD", "CFD solver validation (OpenFOAM SST)", "NASA TMR NACA 0012, TN D-7428, momentum theory, Felker & Light, lifting line",
        "[cfd/README.md](cfd/README.md)", ev["cfd_tool"]["result"], ev["cfd_tool"]["status"])
    add("Tool: CFD", "Aircraft CFD on the 3.2 geometry (CD0, e, CLmax, download, thrust deduction, tail wake)", "production mesh",
        "[../cfd/results/](../cfd/results/README.md)", ev["cfd_design"]["result"], ev["cfd_design"]["status"])
    add("Tool: CFD", "3.2 aircraft mesh-sensitivity check", "L0 vs L+1 lifting-surface resolution", "[cfd/README.md](cfd/README.md)",
        ev["cfd_mesh32"]["result"], ev["cfd_mesh32"]["status"])
    add("Tool: FEA", "FEA benchmarks (beam, CalculiX, CLT, flutter)", "closed form, NAFEMS, Goland", "[fea/README.md](fea/README.md)",
        ev["fea_tool"]["result"], ev["fea_tool"]["status"])
    add("Tool: FEA", "Fitting peak stress mesh convergence", "D6 mesh study", "[fea/README.md](fea/README.md)",
        "peak not converged at the production mesh; x 1.19-1.27 applied to every fitting", "FLAG")
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
                "mass": "mass", "mass vs CAD": "mass", "structure": "structure", "parachute": "parachute", "cost": "cost",
                "CFD 3.2": "cfd-32"}


def write_md(out, B, path):
    rows = out["rows"]
    cnt = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("PASS", "FLAG", "FAIL", "PENDING", "INFO")}
    L = ["# Independent checks of the E8-200 T8 design (WP V)", "",
         "Written by `check_t8.py`. Do not edit by hand.", "",
         f"Run: {out['meta']['run_time']}. Inputs: `design/selected_design.json`, `design/geometry.json`, `bom/BOM.csv`, "
         "`cad/mass_properties.json`, `fea/results/*.json`, `cfd/results/`, `methods/benchmarks/`.", "",
         f"**Summary: {cnt['PASS']} PASS, {cnt['FLAG']} FLAG, {cnt['FAIL']} FAIL, {cnt['PENDING']} pending 3.2 re-run, {cnt['INFO']} information.**", "",
         "Verdict rules:",
         "- Comparison rows (independent value against the design or WP value): PASS within 5 %, FLAG 5-20 %, FAIL above 20 %.",
         "  Above 20 % the row stays FLAG when the design value is on the conservative side.",
         "- Limit rows (requirement or rating checked with the independent value): PASS when the margin is at least 2 %.",
         "  FLAG when the margin is within +-2 % (inside the accuracy of a hand calculation). FAIL below -2 %.",
         "- PENDING: the row needs a CAD or CFD file of the 3.2 re-run that is not there yet. Provisional values are shown.", "",
         "Assumptions of the hand checks (independent of WP D's model unless stated):", ""]
    for k, v in REF.items():
        if not k.startswith("cfd31") and k != "clmax_flaps_cfd_key":
            L.append(f"- `{k}` = {v}")
    L += ["- The thrust deduction (4.5 %) and the EOL resistance factor (1.5) are the same values as WP D's; no independent data exist.",
          "- CFD 3.1 drag-area inputs are from `cfd/results/README.md` section 2.", ""]
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
    L += ['<a id="wpm"></a>', "", "## WP M checker on the 3.2 design (run in memory, no files written)", "",
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
          f"{cnt['PENDING']} pending 3.2 re-run** (generated {out['meta']['run_time']}).", "",
          "| # | group | requirement or tool | method | evidence | result | status |", "|---|---|---|---|---|---|---|"]
    for k, r in enumerate(matrix, 1):
        stt = "pending 3.2 re-run" if r["status"] == "PENDING" else r["status"]
        Lm.append(f"| {k} | {r['group']} | {r['req']} | {r['method']} | {r['evidence']} | {r['result']} | **{stt}** |")
    t = replace_block(t, "matrix", "\n".join(Lm))
    neg = sorted(ev["fea_design"]["neg"], key=lambda x: x["MS"])
    Lf = ["| MS | item | source |", "|---|---|---|"] + [f"| {x['MS']:+.2f} | {x['item']} | `{x['source']}` |" for x in neg]
    t = replace_block(t, "fea_negative", "\n".join(Lf))
    pend = [r for r in out["rows"] if r["verdict"] == "PENDING"]
    Lp = [f"- {r['id']}: {r['quantity']}" + (f" (provisional {r['provisional_verdict']})" if r.get("provisional_verdict") else "") for r in pend]
    Lp += [f"- matrix: {r['req']}" for r in matrix if r["status"] == "PENDING"]
    t = replace_block(t, "pending", "\n".join(Lp) if Lp else "None: all CAD and CFD rows are on 3.2 files.")
    rows = out["rows"]
    c2 = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("PASS", "FLAG", "FAIL", "PENDING", "INFO")}
    t = replace_block(t, "independent_summary",
                      f"Independent checks: **{c2['PASS']} PASS, {c2['FLAG']} FLAG, {c2['FAIL']} FAIL, {c2['PENDING']} pending, "
                      f"{c2['INFO']} information** ([independent/results.md](../independent/iteration32/results.md)).")
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
    out["meta"] = dict(run_time=dt.datetime.now().strftime("%Y-%m-%d %H:%M"), cutoff=a.cutoff, script="validation/independent/check_t8.py")
    d = jload("design/selected_design.json")
    B = benchmarks(d)
    out["benchmarks"] = B
    plot_benchmarks(B, HERE / "benchmark_comparison.png")
    Rm = {r["id"]: r for r in ROWS}
    ev = wp_evidence(cutoff, Rm, out)
    matrix = build_matrix(Rm, ev, (ROOT / "requirements/requirements.yaml").read_text())
    out["matrix"] = matrix
    out["wp_evidence"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("neg", "clear")} for k, v in ev.items()}
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)))
    write_md(out, B, HERE / "results.md")
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
