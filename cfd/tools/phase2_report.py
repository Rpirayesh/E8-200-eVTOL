"""Design-analysis summary: CFD results of the frozen design vs the sizing assumptions, with the validated
uncertainty bands, flaps-down CLmax estimate and the mission check input.

    python cfd/tools/phase2_report.py        # -> cfd/results/summary.json, cfd/results/*.png
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "cfd" / "results"
G0, RHO = 9.80665, 1.225
DL_FACTOR = 1.46        # actuator-disk download / measured (validation/cfd sec. 5)

# validated bands (validation/cfd/README.md sec. 7): (low, high) relative, applied as true = CFD x (1 + band)
BANDS = dict(CL_alpha=(-0.05, 0.05), CD0_attached=(-0.10, 0.05), CD0_bluff=(-0.30, 0.30), oswald=(-0.08, 0.08),
             CLmax=(-0.05, 0.12), download=(-0.30, 0.30), x_np_mac=0.05)


def jl(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def flap_estimate(clean_CLmax: float | None, geo: dict) -> dict:
    d = jl(ROOT / "cfd" / "results" / "flap_section_gaw1.json")
    if not d:
        return {}
    rows = d["openfoam"]
    out = {}
    for dfl in sorted({r["flap_deg"] for r in rows}):
        rr = sorted([r for r in rows if r["flap_deg"] == dfl and "Cl" in r], key=lambda r: r["alpha"])
        steady = [r for r in rr if r["Cl_std"] < 0.01]
        mean_max = max(r["Cl"] for r in rr)
        st_max = max((r["Cl"] for r in steady), default=float("nan"))
        out[dfl] = dict(clmax_mean=mean_max, clmax_steady=st_max, alpha_clmax=max(rr, key=lambda r: r["Cl"])["alpha"],
                        polar=[(r["alpha"], r["Cl"], r["Cd"], r["Cl_std"]) for r in rr])
    w = geo["wing"]
    fl = (w.get("control_surfaces") or {}).get("flaps")
    if not fl:
        return dict(note="no flaps on this design")
    S = geo["reference"]["S_ref"]
    swf = 2 * (fl["y_to"] - fl["y_from"]) * w["root_chord"]
    res = dict(section=out, Swf_over_S=swf / S, method="DATCOM 6.1.7: dCLmax = dclmax(section) x Swf/S x K_sweep (K = 1 for an "
               "unswept wing); section increments from 2-D CFD of the GA(W)-1 with a sealed 30 %-chord plain flap at Re 2.4e6")
    if 0 in out:
        for dfl, v in out.items():
            if dfl <= 0:   # 0 = clean reference; -1 = clean with the robust (limited) schemes, not converged out of the
                continue   # stalled start-up state within 6000 iterations (kept in `section` for transparency only)
            dcl = v["clmax_mean"] - out[0]["clmax_mean"]
            res[f"delta_{dfl}"] = dict(dclmax_section=dcl, dCLmax_3d=dcl * swf / S,
                                       CLmax_flaps=(clean_CLmax + dcl * swf / S) if clean_CLmax else None)
    return res


WORK = None
SIZING_PUSHER_MARGIN = 0.028     # pusher continuous margin stated by the sizing for the frozen design (iteration 3.3)


def ring_samples(case: Path):
    d = sorted([p for p in (case / "postProcessing" / "pusherInflow").glob("*") if p.is_dir()], key=lambda p: float(p.name))
    if not d:
        return None
    f = next(d[-1].glob("rings*U*.xy"), None) or next(d[-1].glob("rings*.xy"), None)
    if f is None:
        return None
    a = np.loadtxt(f)
    return a   # x y z p Ux Uy Uz  (raw cloud: x y z then fields in the order p, U)


def pusher_analysis(geo: dict, sd: dict, out: dict) -> dict:
    """Thrust deduction, wake fraction and inflow non-uniformity at the pusher disks, tail-load change and the cruise
    shaft power per pusher (sizing propeller model with the CFD inflow)."""
    from importlib import import_module
    sys.path.insert(0, str(ROOT))
    ph = import_module("sizing.physics")
    cr = jl(RES / "cruise.json") or {}
    g_on = cr.get("groups", {}).get("cruise_L+0w1", {}).get("polar", [])
    g_off = cr.get("groups", {}).get("cruise_nopusher_L+0w1", {}).get("polar", [])
    res = {}
    if not (g_on and g_off):
        return res
    a_off = g_off[0]["alpha"]
    on = next((r for r in g_on if r["alpha"] == a_off), None)
    off = g_off[0]
    if on is None:
        return res
    ref = geo["reference"]
    V = on["U"]
    q = 0.5 * 1.225 * V**2
    S = ref["S_ref"]
    pushers = geo.get("pushers") or [geo["pusher"]]
    T_tot = geo["operating"]["cruise_thrust_pusher_n"]
    dD = (on["CD"] - off["CD"]) * q * S
    res["alpha_deg"] = a_off
    res["airframe_drag_change_n"] = dD
    res["thrust_total_n"] = T_tot
    res["thrust_deduction"] = dD / T_tot
    res["drag_area_change_by_region_m2"] = {k: on["regions"][k]["drag_area_m2"] - off["regions"][k]["drag_area_m2"] for k in on["regions"]}
    res["tail"] = dict(lift_on_n=on["regions"]["tail"]["lift_n"], lift_off_n=off["regions"]["tail"]["lift_n"],
                       drag_area_on_m2=on["regions"]["tail"]["drag_area_m2"], drag_area_off_m2=off["regions"]["tail"]["drag_area_m2"])
    res["Cm_on"], res["Cm_off"] = on["Cm"], off["Cm"]
    # inflow at the disk from the no-pusher case (wake only) and the pusher case (wake + induced)
    a = math.radians(a_off)
    ax_dir = np.array([math.cos(a), 0.0, math.sin(a)])
    infl = {}
    for tag, case in (("no_pusher", WORK / off["case"]), ("pusher_on", WORK / on["case"])):
        s = ring_samples(case)
        if s is None:
            continue
        U = s[:, 4:7]
        ua = U @ np.array([1.0, 0.0, 0.0])          # axial (body x, the disk axis)
        hub = np.asarray(next(p for p in pushers if p["hub"][1] > 0)["hub"], float)
        r = np.hypot(s[:, 1] - hub[1], s[:, 2] - hub[2])
        w = r / r.sum()                                # area weighting ~ r on a ring grid
        mean = float((ua * w).sum())
        infl[tag] = dict(mean_axial_over_Vinf=mean / V, min_over_Vinf=float(ua.min() / V), max_over_Vinf=float(ua.max() / V),
                         nonuniformity_std_over_mean=float(np.sqrt(((ua - mean) ** 2 * w).sum()) / mean), n_points=int(len(ua)),
                         freestream_axial_over_Vinf=math.cos(a))
    res["inflow"] = infl
    if "no_pusher" in infl:
        wake = 1 - infl["no_pusher"]["mean_axial_over_Vinf"] / math.cos(a)
        res["wake_fraction"] = wake
        # cruise shaft power per pusher at the sizing cruise condition (density from the sizing cruise CL)
        cfd = out.get("cfd_production_mesh", {})
        m = geo["mass"]["mtow_kg"]
        CLc = geo["aero"]["cruise_CL"]
        Vc = geo["aero"]["cruise_speed_ms"]
        rho = 2 * m * G0 / (Vc**2 * S * CLc)
        D_cfd = cfd.get("cruise_drag_n_incl_pods")      # with the pushers running (deduction included)
        Dp = pushers[0]["diameter"]
        n = len(pushers)
        pw = {}
        for label, T, Va in (("sizing (T as sized, free-stream inflow)", T_tot, Vc),
                             ("CFD drag, free-stream inflow", D_cfd, Vc),
                             ("CFD drag, CFD wake inflow", D_cfd, Vc * (1 - wake))):
            if not T:
                continue
            eta = float(ph.prop_efficiency(T / n, Va, rho, Dp))
            P = T / n * Va / eta / 1e3
            pw[label] = dict(thrust_per_pusher_n=T / n, inflow_ms=Va, eta_prop=eta, shaft_kw_per_pusher=P,
                             useful_power_kw_per_pusher=T / n * Vc / 1e3)
        rpm = pushers[0].get("rpm_cruise")
        qmax = pushers[0].get("max_torque_Nm")
        if rpm:
            om = rpm * 2 * math.pi / 60
            for v in pw.values():
                v["torque_nm_per_pusher"] = v["shaft_kw_per_pusher"] * 1e3 / om
                if qmax:
                    v["torque_margin"] = 1 - v["torque_nm_per_pusher"] / qmax
            res["rpm_cruise"] = rpm
            res["spin_directions"] = [p.get("spin") for p in pushers]
            res["note_swirl"] = ("actuator disks carry thrust only (no swirl); with both pushers turning the same way the "
                                 "reaction torques add (net rolling moment = 2 Q), which the disks do not model; the props "
                                 "are aft of the tail surfaces, so their swirl does not reach the H-tail or fins")
        base = next(iter(pw.values()))["shaft_kw_per_pusher"] if pw else None
        for v in pw.values():   # carry the sizing's own continuous margin (SIZING_PUSHER_MARGIN) through the CFD power ratio
            v["power_ratio_to_sizing"] = v["shaft_kw_per_pusher"] / base if base else None
            v["margin_on_sizing_basis"] = 1 - (1 - SIZING_PUSHER_MARGIN) * v["power_ratio_to_sizing"] if base else None
        res["sizing_pusher_margin"] = SIZING_PUSHER_MARGIN
        cont = (sd.get("pusher", {}).get("motor", {}) or {}).get("continuous_power_kw")
        res["shaft_power"] = pw
        res["rho_cruise"] = rho
        if cont:
            res["continuous_kw_per_pusher"] = cont / n
            for v in pw.values():
                v["continuous_margin"] = 1 - v["shaft_kw_per_pusher"] / (cont / n)
    return res


def gci_study(groups: dict, alpha: float = 5.0) -> dict:
    """Celik/Roache GCI from the three lifting-surface refinements (wing and tail surface cells c/64, c/128, c/256;
    the rest of the mesh unchanged) at one angle of attack."""
    sys.path.insert(0, str(ROOT / "cfd" / "tools"))
    from gci import celik
    names = ["cruise_L+0w2", "cruise_L+0w1", "cruise_L+0"]          # fine -> coarse
    rows = []
    for g in names:
        r = next((x for x in groups.get(g, {}).get("polar", []) if x["alpha"] == alpha), None)
        if r is None:
            return {}
        rows.append(r)
    h = (1 / 256, 1 / 128, 1 / 64)
    out = dict(alpha_deg=alpha, h_over_c=h, note="refinement of the wing and tail surface mesh only (ratio 2); fuselage, "
               "booms, rotors and gear at c/64 on all three meshes", cases=[r["case"] for r in rows])
    for q in ("CL", "CD", "Cm"):
        out[q] = celik(h, tuple(r[q] for r in rows))
    try:
        (ROOT / "validation" / "cfd" / "data" / "aircraft33_gci.json").write_text(json.dumps(out, indent=1, default=float))
    except Exception:  # noqa: BLE001
        pass
    return out


def main():
    geo = json.loads((ROOT / "design" / "geometry_cfd.json").read_text())
    sd = json.loads((ROOT / "design" / "selected_design.json").read_text())
    ref = geo["reference"]
    S, c, b = ref["S_ref"], ref["c_ref"], ref["b_ref"]
    AR = b * b / S
    m = geo["mass"]["mtow_kg"]
    aero = geo["aero"]
    cr = jl(RES / "cruise.json") or {}
    groups = cr.get("groups", {})
    prod = groups.get("cruise_L+0w1", {}).get("fit", {})
    coarse = groups.get("cruise_L+0", {}).get("fit", {})
    out = dict(design=dict(mtow_kg=m, S_ref=S, c_ref=c, b_ref=b, x_cg=ref["x_ref"]))
    # sizing assumptions
    siz = dict(CD0=aero["CD0"], oswald=aero["oswald"], CL_alpha_per_rad=aero["CLalpha_per_rad"], CLmax_clean=aero["CLmax"],
               CLmax_flaps=sd["wing"].get("cl_max"), cruise_CL=aero["cruise_CL"], cruise_drag_n=sd["results"].get("cruise_drag_N"),
               cruise_LD=sd["results"].get("cruise_LD"), Cm0=aero.get("Cm0"), x_np_m=geo.get("neutral_point_x_m"),
               static_margin=sd["results"].get("static_margin_mtow"), download_fraction=sd["lift_rotors"].get("download_fraction"),
               drag_area_m2=sd["drag"]["drag_area_m2"], breakdown_m2=sd["drag"]["breakdown_m2"])
    out["sizing"] = siz
    if prod:
        cfd = {k: prod.get(k) for k in ("CL_alpha_per_rad", "CL0", "alpha_zero_lift_deg", "CD0", "oswald_e", "dCm_dCL", "Cm0",
                                         "x_neutral_point_m", "static_margin", "CLmax_mean", "alpha_CLmax", "cruise_CL", "cruise_alpha_deg",
                                         "cruise_CD", "cruise_drag_n", "cruise_LD", "fitted_alphas")}
        cfd["static_margin_mac"] = cfd.get("static_margin")
        out["cfd_production_mesh"] = cfd
        out["cfd_coarse_mesh_L0"] = {k: coarse.get(k) for k in ("CL_alpha_per_rad", "CD0", "oswald_e", "static_margin", "cruise_LD")} if coarse else None
        rows = groups.get("cruise_L+0w1", {}).get("polar", [])
        if rows and cfd.get("CD0") is not None:
            # bluff items (stopped rotors/pylons/hubs, gear, spinner) are nearly lift-independent: their drag area at the
            # lowest computed angle is their share of CD0; the rest of CD0 is attached-flow (wing, tail, fuselage, booms)
            r0 = min(rows, key=lambda r: r["alpha"])
            bluff = sum(v["drag_area_m2"] for k, v in r0["regions"].items() if k in ("rotors", "gear", "pusher"))
            tot = cfd["CD0"] * S
            att = tot - bluff
            lo = att * BANDS["CD0_attached"][0] + bluff * BANDS["CD0_bluff"][0]
            hi = att * BANDS["CD0_attached"][1] + bluff * BANDS["CD0_bluff"][1]
            out["CD0_band"] = dict(drag_area_cfd_m2=tot, attached_m2=att, bluff_m2=bluff, low=(tot + lo) / S, high=(tot + hi) / S,
                                   rel_low=lo / tot, rel_high=hi / tot)
        out["flaps"] = flap_estimate(cfd.get("CLmax_mean"), geo)
    hov = sorted(RES.glob("hover_linear_*.json"))
    if hov:
        h = json.loads(hov[-1].read_text())
        out["hover"] = dict(raw_download_fraction=h["download_fraction"], corrected_download_fraction=h["download_fraction"] / DL_FACTOR,
                            band=[h["download_fraction"] / DL_FACTOR * (1 + BANDS["download"][0]),
                                  h["download_fraction"] / DL_FACTOR * (1 + BANDS["download"][1])],
                            by_region_n=h["vertical_force_by_region_n"])
    hu = sorted(RES.glob("hover_uniform_*.json"))
    if hu:
        out.setdefault("hover", {})["uniform_disk_raw_download_fraction"] = json.loads(hu[-1].read_text())["download_fraction"]
    tr = sorted(RES.glob("transition_*.json"))
    if tr:
        out["transition"] = json.loads(tr[-1].read_text())
    # inverter pods (not in the CFD geometry): build-up increment as in sizing/README.md (0.030 m2 frontal, C_D 0.12) for the
    # 8 lift stations and, with twin pushers, the 2 pusher pods (the pusher motor cans and spinners are meshed)
    n_pods = 8 + (len(geo.get("pushers") or []) if len(geo.get("pushers") or []) > 1 else 0)
    pods = n_pods * 0.030 * 0.12
    out["inverter_pods_drag_area_m2"] = pods
    cfd = out.get("cfd_production_mesh")
    if cfd and cfd.get("CD0") is not None:
        cfd["CD0_incl_pods"] = cfd["CD0"] + pods / S
        if cfd.get("cruise_CD"):
            cfd["cruise_CD_incl_pods"] = cfd["cruise_CD"] + pods / S
            cfd["cruise_LD_incl_pods"] = cfd["cruise_CL"] / cfd["cruise_CD_incl_pods"]
            cfd["cruise_drag_n_incl_pods"] = m * G0 * cfd["cruise_CD_incl_pods"] / cfd["cruise_CL"]
        dl = (out.get("hover") or {}).get("corrected_download_fraction", siz["download_fraction"])
        e = cfd.get("oswald_e") or siz["oswald"]
        cmd = [sys.executable, str(ROOT / "cfd" / "tools" / "mission_check.py"), "--cd0", f"{cfd['CD0_incl_pods']:.5f}", "--e", f"{e:.4f}",
               "--download", f"{dl:.4f}", "--cd0-band", f"{max(abs(out.get('CD0_band', {}).get('rel_low', 0.12)), 0.12):.3f}",
               "--e-band", "0.08", "--dl-band", "0.30", "--out", str(RES / "mission_check.json")]
        subprocess.run(cmd, check=False, capture_output=True)
        out["mission_check"] = jl(RES / "mission_check.json")
    if WORK:
        out["pusher"] = pusher_analysis(geo, sd, out)
    out["gci_lifting_surface_refinement"] = gci_study(groups)
    (RES / "summary.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=Path, default=RES)
    ap.add_argument("--work", type=Path, default=None)
    a = ap.parse_args()
    RES = a.res
    WORK = a.work
    main()
