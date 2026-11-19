"""Write the design-iteration results page (README.md) from cruise.json / summary.json / hover / mission-check files.

    python cfd/tools/results_md.py --res cfd/results/iteration33 --title "design iteration 3.3"
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G0 = 9.80665


def jl(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def f(v, fmt="{:.3f}", none="-"):
    return none if v is None else fmt.format(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=Path, required=True)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    res = a.res
    geo = json.loads((ROOT / "design" / "geometry_cfd.json").read_text())
    sd = json.loads((ROOT / "design" / "selected_design.json").read_text())
    cr = jl(res / "cruise.json") or {}
    sm = jl(res / "summary.json") or {}
    mc = jl(res / "mission_check.json") or {}
    ref = geo["reference"]
    S = ref["S_ref"]
    m = geo["mass"]["mtow_kg"]
    W = m * G0
    aero = geo["aero"]
    V = aero["cruise_speed_ms"]
    CLc = aero["cruise_CL"]
    rho_c = 2 * W / (V**2 * S * CLc)
    groups = cr.get("groups", {})
    prod = groups.get("cruise_L+0w1", {})
    fit = prod.get("fit", {})
    cfd = sm.get("cfd_production_mesh", {}) or {}
    L = []
    L.append(f"# E8-200 design CFD results - {a.title}\n")
    L.append(f"Frozen design `design/geometry_cfd.json`: MTOW {m:,.1f} kg, wing {ref['b_ref']:.1f} x {ref['c_ref']:.2f} m "
             f"(S {S:.2f} m2), cruise {V * 3.6:.0f} km/h ({V:.1f} m/s), cruise CL {CLc:.3f} (sizing density "
             f"{rho_c:.3f} kg/m3). Tool chain and uncertainty bands: [validation/cfd/README.md](../../../validation/cfd/README.md) "
             "(section 7). Set-up as validated: steady k-omega SST, half model, wing and tail surfaces at c/128 "
             "(`--lift-extra 1`), first prism layer for y+ 25-40, stopped lift rotors, pushers as radius-weighted actuator "
             "disks at the cruise thrust (thrust only, no swirl). Inverter pods are a build-up increment "
             f"({sm.get('inverter_pods_drag_area_m2', 0):.4f} m2). Coefficients use sea-level density; the cruise point is "
             "taken at the sizing cruise CL. Angles are fuselage angles of attack.\n")
    # polar table
    L.append("## 1. Cruise polar (production mesh)\n")
    L.append("| alpha (deg) | CL | CD | Cm (CG) | CL oscillation | iterations |")
    L.append("|---|---|---|---|---|---|")
    for r in prod.get("polar", []):
        L.append(f"| {r['alpha']:g} | {r['CL']:.3f} | {r['CD']:.4f} | {r['Cm']:+.3f} | {r['CL_std']:.3f} | {r['iterations']} |")
    L.append("\n![polar](cruise_polar.png)\n")
    # comparison
    siz = sm.get("sizing", {})
    band = sm.get("CD0_band", {})
    L.append("## 2. Comparison with the sizing assumptions\n")
    L.append("| Quantity | Sizing | CFD | Band |")
    L.append("|---|---|---|---|")
    L.append(f"| CL_alpha (/rad) | {f(siz.get('CL_alpha_per_rad'), '{:.2f}')} | {f(cfd.get('CL_alpha_per_rad'), '{:.2f}')} | +-5 % |")
    L.append(f"| CD0 (incl. pods) | {f(siz.get('CD0'), '{:.4f}')} | {f(cfd.get('CD0'), '{:.4f}')} ({f(cfd.get('CD0_incl_pods'), '{:.4f}')}) | "
             f"{f(band.get('low'), '{:.4f}')}-{f(band.get('high'), '{:.4f}')} |")
    L.append(f"| Oswald e | {f(siz.get('oswald'), '{:.3f}')} | {f(cfd.get('oswald_e'), '{:.3f}')} | +-8 % |")
    L.append(f"| Cruise L/D (incl. pods) | {f(siz.get('cruise_LD'), '{:.2f}')} | {f(cfd.get('cruise_LD'), '{:.2f}')} "
             f"({f(cfd.get('cruise_LD_incl_pods'), '{:.2f}')}) | see text |")
    L.append(f"| Cruise drag (incl. pods), N | {f(siz.get('cruise_drag_n'), '{:,.0f}')} | {f(cfd.get('cruise_drag_n'), '{:,.0f}')} "
             f"({f(cfd.get('cruise_drag_n_incl_pods'), '{:,.0f}')}) | |")
    L.append(f"| Fuselage angle in cruise (deg) | {f(geo['wing'].get('fuselage_angle_in_cruise_deg'), '{:.2f}')} | "
             f"{f(cfd.get('cruise_alpha_deg'), '{:.2f}')} | +-0.4 |")
    L.append(f"| Static margin (MAC) | {f(siz.get('static_margin'), '{:.3f}')} | {f(cfd.get('static_margin'), '{:.3f}')} "
             f"(x_np {f(cfd.get('x_neutral_point_m'), '{:.3f}')} m) | +-0.05 |")
    clm = cfd.get("CLmax_mean")
    L.append(f"| CLmax clean | {f(siz.get('CLmax_clean'), '{:.3f}')} | {f(clm, '{:.3f}')} at {f(cfd.get('alpha_CLmax'), '{:g}')} deg | -5 % / +12 % |")
    h = sm.get("hover", {})
    L.append(f"| Hover download | {f(siz.get('download_fraction'), '{:.4f}')} | raw {f(h.get('raw_download_fraction'), '{:.4f}')}, "
             f"corrected {f(h.get('corrected_download_fraction'), '{:.4f}')} | +-30 % |")
    if clm:
        vs_sl = math.sqrt(2 * W / (1.225 * S * clm))
        vs_cr = math.sqrt(2 * W / (rho_c * S * clm))
        L.append(f"\nStall speed with the CFD CLmax: {vs_sl:.1f} m/s (sea level), {vs_cr:.1f} m/s TAS at the cruise density; "
                 f"cruise / Vs = {V / vs_cr:.3f} (cruise density). With the -5 % / +12 % CLmax band: "
                 f"{V / math.sqrt(2 * W / (rho_c * S * clm * 0.95)):.3f} - {V / math.sqrt(2 * W / (rho_c * S * clm * 1.12)):.3f}.\n")
    # drag areas
    lo = cr.get("drag_area_at_lowest_alpha_m2") or cr.get("drag_area_at_zero_lift_m2") or {}
    cru = cr.get("drag_area_at_cruise_m2", {})
    sz = cr.get("drag_area_sizing_m2", {})
    if lo:
        L.append(f"Drag areas D/q (m2) by component: CFD at the lowest computed angle ({lo.get('alpha_deg', '-')} deg) and at the "
                 "cruise CL, sizing build-up (zero lift).\n")
        L.append("| Component | CFD lowest alpha | CFD cruise | Sizing |")
        L.append("|---|---|---|---|")
        for k, v in lo.items():
            if k == "alpha_deg":
                continue
            L.append(f"| {k} | {v:.3f} | {cru.get(k, float('nan')):.3f} | {sz.get(k, 0):.3f} |")
        L.append("\n![drag](drag_breakdown.png)\n")
    # pusher
    pu = sm.get("pusher", {})
    if pu:
        L.append("## 3. Pushers in the tail wake\n")
        L.append(f"Fuselage alpha {pu.get('alpha_deg')} deg, pushers on vs off (same mesh): airframe drag change "
                 f"{pu.get('airframe_drag_change_n', 0):+.0f} N at {pu.get('thrust_total_n', 0):.0f} N total thrust, thrust deduction "
                 f"**{100 * pu.get('thrust_deduction', 0):.1f} %** (sizing 4.5 %). Change of drag area by component (m2): "
                 + ", ".join(f"{k} {v:+.4f}" for k, v in pu.get("drag_area_change_by_region_m2", {}).items()) + ".")
        t = pu.get("tail", {})
        if t:
            L.append(f"Tail surfaces: lift {t['lift_off_n']:.0f} N without, {t['lift_on_n']:.0f} N with the pushers; drag area "
                     f"{t['drag_area_off_m2']:.4f} / {t['drag_area_on_m2']:.4f} m2; Cm {pu.get('Cm_off', 0):+.4f} / {pu.get('Cm_on', 0):+.4f}.")
        for tag, v in pu.get("inflow", {}).items():
            L.append(f"Inflow 0.1 m ahead of the disk ({tag}): mean axial {v['mean_axial_over_Vinf']:.3f} V, min {v['min_over_Vinf']:.3f}, "
                     f"max {v['max_over_Vinf']:.3f}, non-uniformity (std/mean) {100 * v['nonuniformity_std_over_mean']:.1f} %.")
        if "wake_fraction" in pu:
            L.append(f"Wake fraction (pushers off) w = {pu['wake_fraction']:.3f}.\n")
        L.append(f"| Case | thrust per pusher (N) | inflow (m/s) | eta | shaft power per pusher (kW) | power / sizing | "
                 f"margin on the sizing basis ({100 * pu.get('sizing_pusher_margin', 0):.1f} % sized) | torque (N m) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for k, v in pu.get("shaft_power", {}).items():
            L.append(f"| {k} | {v['thrust_per_pusher_n']:.0f} | {v['inflow_ms']:.1f} | {v['eta_prop']:.3f} | {v['shaft_kw_per_pusher']:.1f} | "
                     f"{v.get('power_ratio_to_sizing', float('nan')):.3f} | {100 * v.get('margin_on_sizing_basis', float('nan')):+.1f} % | "
                     f"{v.get('torque_nm_per_pusher', float('nan')):.0f} |")
        if pu.get("note_swirl"):
            L.append(f"\n{pu['note_swirl'][0].upper() + pu['note_swirl'][1:]}.\n")
    # hover
    if h:
        L.append("## 4. Hover download\n")
        L.append(f"Raw download {100 * h['raw_download_fraction']:.1f} % of thrust; corrected (raw / 1.46, validation sec. 5) "
                 f"**{100 * h['corrected_download_fraction']:.1f} %**, band {100 * h['band'][0]:.1f}-{100 * h['band'][1]:.1f} %. "
                 "Vertical force by component (N): " + ", ".join(f"{k} {v:+.0f}" for k, v in h.get("by_region_n", {}).items()) + ".\n")
    # GCI
    g = sm.get("gci_lifting_surface_refinement", {})
    if g and "CD" in g:
        L.append("## 5. Grid convergence at the cruise point\n")
        L.append(f"Fuselage alpha {g['alpha_deg']} deg, wing and tail surface cells c/64, c/128, c/256 ({g['note']}).\n")
        L.append("| Quantity | c/64 | c/128 | c/256 | p (observed) | extrapolated | GCI fine | GCI medium |")
        L.append("|---|---|---|---|---|---|---|---|")
        for q in ("CL", "CD", "Cm"):
            c = g[q]
            fv = c.get("f", (None, None, None))
            L.append(f"| {q} | {fv[2]:.4f} | {fv[1]:.4f} | {fv[0]:.4f} | {f(c.get('p'), '{:.2f}')} | {f(c.get('f_ext'), '{:.4f}')} | "
                     f"{f(c.get('gci21'), '{:.3%}')} | {f(c.get('gci32'), '{:.3%}')} |")
        L.append("")
    # mission
    if mc:
        L.append("## 6. Mission check\n")
        L.append("| Case | CD0 | e | download | L/D | range (model) | range scaled to published |")
        L.append("|---|---|---|---|---|---|---|")
        for k in ("check_same_inputs", "cfd_nominal", "cfd_worst_band", "cfd_best_band"):
            v = mc.get(k)
            if v:
                L.append(f"| {k} | {v['CD0']:.4f} | {v['oswald']:.3f} | {v['download']:.4f} | {v['LD']:.2f} | {v['range_km']:.1f} km | "
                         f"{f(v.get('range_km_scaled_to_published'), '{:.1f}')} km |")
        L.append(f"\nRequired range {mc.get('required_range_km')} km; published capability {mc.get('published_range_km')} km.\n")
    (res / "README.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
