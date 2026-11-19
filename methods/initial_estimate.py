#!/usr/bin/env python3
"""First-order feasible-design-space estimate for E8-200 (work package M).

Closes MTOW = payload + empty(MTOW) + battery(MTOW) with the equations of methods/EQUATIONS.md
(the same functions as methods/check_design.py), for range 50/100/150 km and 4/6/8 lift rotors
(plus 4 coaxial pairs = 8 rotors), and writes methods/initial_estimate.json and plots.

    ~/tools/cadenv/bin/python methods/initial_estimate.py
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np

import check_design as cd

HERE = Path(__file__).resolve().parent
G0 = cd.G0

# ---------------------------------------------------------------- fixed first-order choices
BASE = dict(
    payload=200.0, cruise_kmh=150.0, disk_loading=450.0, wing_loading=650.0, span_max=9.0, cl_max=1.4,
    cell=dict(name="21700 high-energy class (Molicel P50B data, resources ledger S04/S05)", energy_wh=18.0, mass_kg=0.071,
              capacity_ah=5.0, v_nom=3.6, max_continuous_discharge_a=40.0, max_peak_discharge_a=60.0),
    series=110, vtip=150.0, blades=2, chord_over_R=0.10, pusher_D=1.6, pusher_rpm=2400,
    fuselage=dict(length_m=4.6, max_width_m=1.15, max_height_m=1.35),
)
# Cost inputs (USD).  Sources: first-iteration ledger (../E8-eVTOL-Design-Explorer/aircraft/sources/README.md):
# S06 P50B bulk $7.50/cell; S07 T-Motor U15XXL $1999 + Thunder 300A $1599 at ~20 kW bench electrical peak (96 V x 209 A)
# -> about $180 per kW of peak power for COTS motor + controller; S08 E-PROPS two-blade listing EUR 1304 (comparison).
COST = dict(cell_usd=7.50, pack_build_factor=1.6, motor_esc_usd_per_kw_peak=180.0, prop_usd_each=1450.0,
            parachute_usd=8000.0, avionics_fcs_usd=25000.0, misc_systems_usd=10000.0)
# Two technology/estimating scenarios bracket the empty mass (EQUATIONS.md sec. 3 and 12)
SCENARIOS = {
    "conservative": dict(assumptions={}, growth=0.10,
                         note="M default regressions: Raymer GA structure (no composite credit), NASA 1.63 motor "
                              "accessory factor, Raymer GA electrical system, 30 % pack overhead, 10 % growth"),
    "light": dict(assumptions=dict(tech_factor_structure=0.85, accessory_factor=0.35, lv_electrical_kg=12.0,
                                   pack_overhead_fraction=0.25), growth=0.05,
                  note="composite credit 0.85 on structure (Raymer table 15.4 order), COTS inverter/cooling/harness "
                       "0.35 x motor mass, 12 kg LV system, 25 % pack overhead, 5 % growth"),
}
COST_NOTE = ("cell price and motor/controller $/kW from dated listings in the first-iteration ledger (S06, S07); "
             "propeller from the S08 comparison listing (EUR 1304 ~ USD 1450); parachute, avionics/flight control and misc "
             "are estimates to be replaced by bom/catalog.json")


def make_design(mtow: float, batt_kwh: float, n_rot: int, coax: bool, range_km: float, b: dict,
                assumptions: dict | None = None) -> dict:
    W = mtow * G0
    n_disks = n_rot // 2 if coax else n_rot
    Dr = math.sqrt(4 * W / (b["disk_loading"] * n_disks * math.pi))
    S = W / b["wing_loading"]
    span = min(b["span_max"], math.sqrt(9.0 * S))
    R = Dr / 2
    # blade chord for a hover blade loading CT/sigma = 0.11 at the hot-day site [H5]
    rho_h = cd.isa(500.0, 15.0)["rho"]
    ct = W * 1.03 / n_disks / (rho_h * math.pi * R**2 * b["vtip"] ** 2)
    sigma = ct / 0.11 / (2 if coax else 1)
    chord = sigma * math.pi * R / b["blades"]
    ns = b["series"]
    npar = max(1, math.ceil(batt_kwh * 1e3 / (ns * b["cell"]["energy_wh"])))
    batt_kwh = ns * npar * b["cell"]["energy_wh"] / 1e3
    ovh = (assumptions or {}).get("pack_overhead_fraction", cd.DEFAULTS["pack_overhead_fraction"])
    pack = ns * npar * b["cell"]["mass_kg"] / (1 - ovh)
    # booms: rotors fore and aft of the wing, along two booms
    per_boom = max(n_disks // 2, 1)
    boom_len = per_boom * (Dr + 0.15) + 1.0
    arms = [0.5 + R + 0.1 + i * (Dr + 0.15) for i in range(max(per_boom // 2, 1))]
    return dict(
        name=f"first-order {n_rot}{'C' if coax else ''} rotors, {range_km:.0f} km",
        mass_kg=dict(mtow=mtow, payload=b["payload"], battery=pack, empty=mtow - pack - b["payload"]),
        environment=dict(hover_design_altitude_m=500.0, hover_ceiling_m=1000.0, hover_isa_offset_C=15.0, cruise_altitude_m=500.0),
        lift_rotors=dict(count=n_rot, coaxial=coax, diameter_m=Dr, blades=b["blades"], blade_chord_m=chord,
                         tip_speed_hover_ms=b["vtip"], download_fraction=0.03, motor_diameter_m=0.10 + 0.08 * Dr,
                         motor_exposed_height_m=0.08, pylon_frontal_area_m2=0.012),
        pusher=dict(diameter_m=b["pusher_D"], blades=3, rpm_cruise=b["pusher_rpm"]),
        wing=dict(span_m=span, area_m2=S, thickness_ratio=0.15, cl_max=b["cl_max"], taper=0.6, removable_for_transport=True),
        fuselage=dict(b["fuselage"]),
        booms=dict(count=2, length_m=boom_len, diameter_m=0.10 + 0.02 * Dr, rotor_arms_m=arms),
        tail=dict(horizontal_area_m2=0.16 * S, vertical_area_m2=0.10 * S, vertical_count=2, mac_m=0.6),
        landing_gear=dict(type="skid", length_m=0.5, frontal_area_m2=0.05),
        battery=dict(energy_nominal_kwh=batt_kwh, series=ns, parallel=npar, cell=b["cell"], independent_packs=2),
        mission=dict(range_km=range_km, cruise_speed_kmh=b["cruise_kmh"], hover_takeoff_s=60, hover_landing_s=60,
                     transition_each_s=30, transitions=2),
        cabin=dict(seats=2), systems=dict(avionics_uninstalled_kg=10.0),
        structure=dict(limit_load_factor_positive=3.8, landing_load_factor=3.0),
        results={},
        assumptions_for_checker=dict(assumptions or {}),
    )


def size(range_km: float, n_rot: int, coax: bool = False, b: dict | None = None, scenario: str = "conservative",
         extra: dict | None = None) -> dict:
    """Closure MTOW = payload + empty + battery: smallest root of the mass residual between 400 and 3000 kg."""
    b = b or BASE
    growth = SCENARIOS[scenario]["growth"]
    asm = dict(SCENARIOS[scenario]["assumptions"], **(extra or {}))
    eol = asm.get("battery_eol_fraction", cd.DEFAULTS["battery_eol_fraction"])

    def residual(m: float):
        """g(m) = payload + empty(m) + battery(m) - m for a design closed on energy at MTOW m."""
        e = 50.0
        for _ in range(6):  # battery energy depends on m only (through power and drag); short fixed point
            dsg = make_design(m, e, n_rot, coax, range_km, b, asm)
            c = cd.Checker(dsg).run()["computed"]
            e_new = c["mission"]["E_nominal_required_kwh"]
            # power sizing: hover at the ceiling within the continuous C-rating less 0.3 C at EOL [B4]
            cell = b["cell"]
            c_allow = cell["max_continuous_discharge_a"] / (cell["capacity_ah"] * eol) - 0.3
            e_pow = c["hover"]["ceiling"]["p_elec_total_kw"] / 0.95 / c_allow / eol
            e_new = max(e_new, e_pow)
            if abs(e_new - e) < 0.05:
                break
            e = e_new
        dsg = make_design(m, e_new, n_rot, coax, range_km, b, asm)
        c = cd.Checker(dsg).run()["computed"]
        empty = c["empty_excl_battery_M_kg"] * (1 + growth)
        return b["payload"] + empty + dsg["mass_kg"]["battery"] - m, e_new

    grid = np.arange(400.0, 3001.0, 50.0)
    gs = [residual(m)[0] for m in grid]
    root = None
    for i in range(len(grid) - 1):
        if gs[i] > 0 >= gs[i + 1]:
            lo, hi = grid[i], grid[i + 1]
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                if residual(mid)[0] > 0:
                    lo = mid
                else:
                    hi = mid
            root = hi
            break
    if root is None:
        k = int(np.argmin(gs))
        return dict(feasible=False, range_km=range_km, n_rot=n_rot, coax=coax, scenario=scenario,
                    min_mass_excess_kg=float(gs[k]), at_mtow_kg=float(grid[k]))
    mtow = root
    e_req = residual(mtow)[1]
    dsg = make_design(mtow, e_req, n_rot, coax, range_km, b, asm)
    res = cd.Checker(dsg).run()
    c = res["computed"]
    hov = c["hover"]
    ro = c.get("rotor_out", {})
    n_motor = n_rot + 1
    p_peak_lift = ro.get("p_shaft_most_loaded_kw", hov["site"]["p_shaft_per_motor_kw"] * 1.5)
    p_push = 1.25 * c["cruise"]["p_shaft_kw"]
    cells = dsg["battery"]["series"] * dsg["battery"]["parallel"]
    cost = dict(
        battery=cells * COST["cell_usd"] * COST["pack_build_factor"],
        motors_controllers=COST["motor_esc_usd_per_kw_peak"] * (n_rot * p_peak_lift + p_push),
        propellers=COST["prop_usd_each"] * (n_rot + 1),
        parachute=COST["parachute_usd"], avionics_fcs=COST["avionics_fcs_usd"], misc=COST["misc_systems_usd"],
    )
    airframe_kg = sum(c["mass_estimates_kg"].get(k, 0) for k in ("wing", "tail_horizontal", "tail_vertical", "fuselage",
                                                                   "booms_and_fittings", "landing_gear", "flight_controls"))
    ez = cd.eastlake_cost(airframe_kg, dsg["mission"]["cruise_speed_kmh"] * 1.1 / 3.6 / cd.KT, 10, 1.40, 0.8,
                          dict(engineering=95.0, tooling=65.0, manufacturing=55.0), f_cert=0.5)
    cost["airframe_recurring_eastlake_N10"] = ez["per_unit_recurring"]
    total = sum(cost.values())
    # complexity proxy: distinct propulsion parts and count of propulsion line-replaceable units
    parts = dict(motors=n_motor, controllers=n_motor, propellers=n_rot + 1, pylons=n_rot // (2 if coax else 1),
                 distinct_motor_types=1 if p_push <= p_peak_lift * 1.05 else 2)
    return dict(feasible=True, scenario=scenario, range_km=range_km, n_rot=n_rot, coax=coax, mtow_kg=mtow, empty_excl_batt_kg=mtow - b["payload"] - dsg["mass_kg"]["battery"],
                battery_kg=dsg["mass_kg"]["battery"], battery_kwh=dsg["battery"]["energy_nominal_kwh"], rotor_D_m=dsg["lift_rotors"]["diameter_m"],
                span_m=dsg["wing"]["span_m"], wing_area_m2=dsg["wing"]["area_m2"],
                hover_elec_kw_site=hov["site"]["p_elec_total_kw"], hover_elec_kw_ceiling=hov["ceiling"]["p_elec_total_kw"],
                hover_shaft_per_motor_kw=hov["site"]["p_shaft_per_motor_kw"], rotor_out_shaft_kw=p_peak_lift,
                rotor_out_thrust_ratio=ro.get("thrust_ratio_to_hover"), cruise_elec_kw=c["cruise"]["p_elec_kw"], LD=c["cruise"]["LD"],
                CD0=c["cruise"]["CD0"], mission_kwh=c["mission"]["E_mission_kwh"], c_rate_hover=c["c_rates_eol"]["hover (ceiling)"],
                stall_ms=c["stall_speed_ms"], cost_usd=cost, cost_total_usd=total, parts=parts,
                mass_items=c["mass_estimates_kg"], growth=growth,
                eastlake=dict(nonrecurring_usd=ez["items"]["engineering"] + ez["items"]["development_support"] +
                              ez["items"]["flight_test"] + ez["items"]["tooling"], mfg_hours_per_unit=ez["hours"]["mfg_per_unit"]))


def max_range(n_rot: int, coax: bool, scenario: str, b: dict | None = None, extra: dict | None = None) -> dict:
    """Largest design range (km) that closes below 3000 kg, by bisection on range."""
    lo, hi = 5.0, 200.0
    if not size(lo, n_rot, coax, b, scenario, extra)["feasible"]:
        return dict(max_range_km=None)
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if size(mid, n_rot, coax, b, scenario, extra)["feasible"]:
            lo = mid
        else:
            hi = mid
    r = size(lo, n_rot, coax, b, scenario, extra)
    return dict(max_range_km=lo, mtow_kg=r["mtow_kg"], battery_kwh=r["battery_kwh"])


VARIANTS = {
    "as_required": dict(b={}, extra={}),
    "BOL_capacity": dict(b={}, extra=dict(battery_eol_fraction=1.0)),
    "cell_300Whkg": dict(b=dict(cell_wh_per_kg=300), extra={}),
    "BOL_and_300Whkg": dict(b=dict(cell_wh_per_kg=300), extra=dict(battery_eol_fraction=1.0)),
    "span_11m": dict(b=dict(span_max=11.0), extra={}),
}


def variant_base(v: dict) -> dict:
    b = copy.deepcopy(BASE)
    if "cell_wh_per_kg" in v:
        b["cell"] = dict(BASE["cell"], mass_kg=18.0 / v["cell_wh_per_kg"])
    if "span_max" in v:
        b["span_max"] = v["span_max"]
    return b


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cases = []
    for scen in SCENARIOS:
        for rng in (50, 100, 150):
            for n, coax in ((4, False), (6, False), (8, False), (8, True)):
                cases.append(size(rng, n, coax, scenario=scen))

    def sweep(key, values, mutate):
        """Light scenario, 8 rotors: 50 km as required and 100 km with BOL accounting + 300 Wh/kg cells."""
        out = []
        for label, rng, cellwh, extra in (("50 km, as required", 50, None, {}),
                                          ("100 km, BOL + 300 Wh/kg", 100, 300, dict(battery_eol_fraction=1.0))):
            for v in values:
                b = copy.deepcopy(BASE)
                if cellwh:
                    b["cell"] = dict(BASE["cell"], mass_kg=18.0 / cellwh)
                mutate(b, v)
                r = size(rng, 8, False, b, "light", extra)
                row = {key: v, "case": label, "feasible": r["feasible"]}
                if r["feasible"]:
                    row.update(mtow_kg=r["mtow_kg"], battery_kwh=r["battery_kwh"], battery_kg=r["battery_kg"], LD=r["LD"],
                               hover_kw=r["hover_elec_kw_site"], rotor_D_m=r["rotor_D_m"], c_rate_hover=r["c_rate_hover"],
                               cost_usd=r["cost_total_usd"])
                out.append(row)
        return out

    speeds = sweep("cruise_kmh", (150, 165, 180, 200), lambda b, v: b.__setitem__("cruise_kmh", v))
    dls = sweep("disk_loading", (300, 450, 600, 800), lambda b, v: b.__setitem__("disk_loading", v))
    cells = sweep("cell_wh_per_kg", (200, 250, 300), lambda b, v: b.__setitem__("cell", dict(b["cell"], mass_kg=18.0 / v)))
    wls = sweep("wing_loading", (500, 650, 800), lambda b, v: b.__setitem__("wing_loading", v))
    limits = []
    for scen in SCENARIOS:
        for vname, v in VARIANTS.items():
            for n, coax in ((6, False), (8, False), (8, True)):
                r = max_range(n, coax, scen, variant_base(v["b"]), v["extra"])
                limits.append(dict(scenario=scen, variant=vname, n_rot=n, coax=coax, **r))
                print("range limit", scen, vname, n, coax, r)
    variant_cases = []
    for vname in ("BOL_capacity", "cell_300Whkg", "BOL_and_300Whkg"):
        v = VARIANTS[vname]
        for rng in (50, 100, 150):
            for n, coax in ((6, False), (8, False)):
                r = size(rng, n, coax, variant_base(v["b"]), "light", v["extra"])
                r["variant"] = vname
                variant_cases.append(r)
    out = dict(base=BASE, scenarios=SCENARIOS, range_limits=limits, variants=VARIANTS, variant_cases=variant_cases, cost_inputs=COST, cost_note=COST_NOTE, cases=cases, speed_sensitivity=speeds,
               disk_loading_sensitivity=dls, cell_sensitivity=cells, wing_loading_sensitivity=wls)
    (HERE / "initial_estimate.json").write_text(json.dumps(out, indent=1, default=float))
    for c in cases:
        tag = f"{c['scenario'][:5]} {c['range_km']:4.0f} km {c['n_rot']}{'C' if c['coax'] else ' '}"
        if not c["feasible"]:
            print(tag, f" no closure below 3000 kg (smallest mass excess {c['min_mass_excess_kg']:.0f} kg at {c['at_mtow_kg']:.0f} kg)")
            continue
        print(f"{tag}  MTOW {c['mtow_kg']:6.0f} empty {c['empty_excl_batt_kg']:5.0f} batt {c['battery_kwh']:5.1f} kWh "
              f"{c['battery_kg']:5.0f} kg  hover {c['hover_elec_kw_site']:5.0f} kW  RO {c['rotor_out_shaft_kw']:5.1f} kW  "
              f"cruise {c['cruise_elec_kw']:5.1f} kW  L/D {c['LD']:4.1f}  D {c['rotor_D_m']:.2f}  C {c['c_rate_hover']:.2f}  "
              f"$ {c['cost_total_usd']:8.0f}")
    for lst in (speeds, dls, cells, wls):
        for r in lst:
            print(r)

    # MTOW and battery energy vs design range (light scenario), as required and with relaxed energy accounting
    curves = []
    for vname in ("as_required", "BOL_and_300Whkg"):
        v = VARIANTS[vname]
        for n, coax in ((6, False), (8, False), (8, True)):
            pts = []
            for rng in range(20, 125, 5):
                r = size(rng, n, coax, variant_base(v["b"]), "light", v["extra"])
                if not r["feasible"]:
                    break
                pts.append((rng, r["mtow_kg"], r["battery_kwh"]))
            curves.append(dict(variant=vname, n_rot=n, coax=coax, points=pts))
    out["range_curves_light"] = curves
    (HERE / "initial_estimate.json").write_text(json.dumps(out, indent=1, default=float))
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    cols = {(6, False): "#2a78d6", (8, False): "#eb6834", (8, True): "#1baf7a"}
    labs = {(6, False): "6 rotors", (8, False): "8 rotors", (8, True): "4 coaxial pairs"}
    for cv in curves:
        if not cv["points"]:
            continue
        x, m, e = zip(*cv["points"])
        ls = "-" if cv["variant"] == "as_required" else "--"
        lab = labs[(cv["n_rot"], cv["coax"])] + (" - as required" if ls == "-" else " - BOL + 300 Wh/kg")
        col = cols[(cv["n_rot"], cv["coax"])]
        axs[0].plot(x, m, ls=ls, color=col, lw=2, label=lab)
        axs[1].plot(x, e, ls=ls, color=col, lw=2)
        axs[0].plot(x[-1], m[-1], marker="o", color=col, ms=6, mec="white", mew=1.5)
    for ax in axs:
        ax.axvline(100, color="#898781", lw=1, ls=":")
        ax.set_xlabel("Design range (km), 150 km/h")
        ax.grid(alpha=0.25, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].text(101, axs[0].get_ylim()[0] + 20, "requirement", fontsize=7, color="#52514e")
    axs[0].set_ylabel("MTOW (kg)")
    axs[1].set_ylabel("Nominal battery energy (kWh)")
    axs[0].legend(frameon=False, fontsize=7)
    fig.suptitle("E8-200 first-order closure (light mass scenario, 200 kg payload); curves end where the mass spiral diverges",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "initial_estimate_mtow_vs_range.png")


if __name__ == "__main__":
    main()
