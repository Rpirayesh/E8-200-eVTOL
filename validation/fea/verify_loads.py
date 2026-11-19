"""Checks of the loads module (fea/loads.py) and the parametric airframe model (fea/airframe.py) on the
placeholder design.

    ~/tools/cadenv/bin/python validation/fea/verify_loads.py

L1  gust load factor: SI implementation vs the CS-23 Appendix / FAR 23.341 imperial formula (independent units)
L2  span load: integral of the Schrenk distribution = wing lift; tail balance closes the pitching-moment equation
L3  rotor allocation: trimmed hover and every one-motor-out case satisfy force / roll / pitch (/ yaw) balance
L4  landing / parachute / crash: reaction and inertia sums
L5  airframe: model mass and cg = mass budget; inertia-relief residual ~0 in every case
L6  airframe: wing-root bending moment from the beam model vs a hand strip-integration of lift and inertia
Results -> validation/fea/results/loads_checks.json, img/vn_placeholder.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fea import airframe as AF  # noqa: E402
from fea import loads as LD  # noqa: E402
from fea.geometry import load  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
IMG = Path(__file__).resolve().parent / "img"
G0 = 9.80665


def main():
    g = load(ROOT / "fea" / "placeholder" / "geometry_placeholder.json")
    ac = LD.aircraft_from_geometry(g)
    ac["x_cg"] = float(AF.build(g)["f"].mass_properties()[1][0])
    allc = LD.all_cases(ac)
    out = {}
    W = ac["mtow_kg"] * G0
    # L1 -----------------------------------------------------------------
    vn = allc["vn"]
    WS_psf = vn["wing_loading_Pa"] / 47.880259
    a = ac["wing"]["CLalpha"]
    c_ft = ac["wing"]["mac"] / 0.3048
    rho_slug = LD.isa_density(ac["altitude_m"]) / 515.379
    mu = 2 * WS_psf / (rho_slug * c_ft * a * 32.174)
    kg = 0.88 * mu / (5.3 + mu)
    V_kt = vn["VC"] / 0.514444
    n_imp = 1 + kg * 50 * V_kt * a / (498 * WS_psf)
    out["L1 gust (CS-23 imperial form)"] = dict(n_SI=vn["gust_VC"][0], n_imperial=n_imp, diff_pct=100 * (vn["gust_VC"][0] - n_imp) / n_imp,
                                                 mu_SI=vn["mu_g"], mu_imperial=mu)
    # L2 -----------------------------------------------------------------
    rows = []
    for fc in allc["flight"]:
        ln = fc["line"]
        y, l = np.array(ln["y"]), np.array(ln["lift_per_m"])
        Lint = np.trapezoid(l, y)
        xa, xt, xc = ac["wing"]["x_ac"], ac["x_ac_tail"], ac["x_cg"]
        M0 = ln["q"] * ac["wing"]["S"] * ac["wing"]["mac"] * ac["wing"]["Cm0"]
        mom = ln["L_wing"] * (xc - xa) + M0 + ln["L_tail"] * (xc - xt)
        sym = "rolling" not in fc["name"]
        rows.append(dict(case=fc["name"], lift_integral_err_pct=100 * (Lint - ln["L_wing"]) / max(abs(ln["L_wing"]), 1.0) if sym else None,
                         total_vs_nW_err_pct=100 * (ln["L_wing"] + ln["L_tail"] - fc["n"] * W) / W, pitch_residual_Nm=mom))
    out["L2 span load and tail balance"] = rows
    # L3 -----------------------------------------------------------------
    R = ac["rotors"]
    rows = []
    for name, T in [("hover", LD.allocate(R, W, ac["x_cg"], 0.0)["T"])] + \
            [(f"OEI {R[i]['name']}", (LD.allocate(R, W, ac["x_cg"], 0.0, failed=i) or
                                      LD.allocate(R, W, ac["x_cg"], 0.0, failed=i, yaw_free=True))["T"]) for i in range(len(R))]:
        T = np.array(T)
        rows.append(dict(case=name, Fz_err_N=float(T.sum() - W), roll_Nm=float(sum(t * r["y"] for t, r in zip(T, R))),
                         pitch_Nm=float(sum(t * (r["x"] - ac["x_cg"]) for t, r in zip(T, R))),
                         yaw_Nm=float(sum(t * r["spin"] * r["kQ"] for t, r in zip(T, R))),
                         max_fraction=float(max(T / np.array([r["T_max"] for r in R])))))
    out["L3 thrust allocation"] = rows
    # L4 -----------------------------------------------------------------
    rows = []
    for lc in allc["landing"]:
        Fz = sum(r["F"][2] for r in lc["reactions"])
        Fy = sum(r["F"][1] for r in lc["reactions"])
        rows.append(dict(case=lc["name"], sum_Fz_over_W=Fz / W, sum_Fy_over_W=Fy / W))
    for pc in allc["parachute"]:
        rows.append(dict(case=pc["name"], total_over_W=pc["total_N"] / W))
    it = allc["crash"]["items"][0]
    rows.append(dict(case=f"crash {it['name']} forward", F_over_mg=-it["ultimate_force_N"]["forward"][0] / (it["kg"] * G0),
                     aft_or_above=it["aft_or_above"]))
    out["L4 reactions"] = rows
    # L5 / L6 ------------------------------------------------------------
    m = AF.build(g)
    f = m["f"]
    mt, cg, I = f.mass_properties()
    out["L5 model mass"] = dict(model_kg=mt, budget_kg=m["mass"]["mtow_kg"], cg_model=cg.tolist(), cg_budget=m["mass"]["cg"])
    res = AF.analyse(m, ac, allc, verbose=False)
    out["L5 inertia relief residual"] = dict(max_support_residual_N=max(r["support_residual_N"] for r in res.values()))
    # L6: wing root bending, case 'F A' (manoeuvre n = 3.8)
    fc = allc["flight"][0]
    F = AF.build_cases(m, ac, dict(flight=[fc], rotor=[], pusher=[], landing=[], parachute=[]))[fc["name"]]
    support = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    u, info = f.solve_inertia_relief(F, support, gravity=(0, 0, -G0))
    yr = g["wing"]["root_fittings_y"]
    # FE: moment about the x-parallel axis through (y_cut, z_root) carried by the members cut at y just outboard of the root
    ycut = yr + 1e-3
    P = np.array([0.0, ycut, g["wing"]["z_root"]])
    Mfe = 0.0
    for fl, (a_, b_, sec, vref, tag) in zip(f.element_forces(u), f.elems):
        ya, yb = f.nodes[a_][1], f.nodes[b_][1]
        if (ya - ycut) * (yb - ycut) < 0:
            out_node = a_ if ya > ycut else b_
            T, _ = f._T(f.nodes[a_], f.nodes[b_], vref)
            fg = T.T @ fl
            k = 0 if out_node == a_ else 6
            Fv, Mv = fg[k:k + 3], fg[k + 3:k + 6]
            # fg = force applied ON the element at its outboard node; the element acts on the outboard body with -fg,
            # and equilibrium of the outboard body gives: (moment of its external + inertia loads) = sum of fg moments
            Mfe += (np.cross(f.nodes[out_node] - P, Fv) + Mv)[0]
    # hand: lift strip integration outboard of the cut + rigid-body inertia of the outboard masses (frame accelerations)
    ln = fc["line"]
    y, l = np.array(ln["y"]), np.array(ln["lift_per_m"])
    sel = y > ycut
    ys = np.r_[ycut, y[sel]]
    ls = np.r_[np.interp(ycut, y, l), l[sel]]
    M_lift = np.trapezoid(ls * (ys - ycut), ys)
    _, Mm = f.assemble()
    Md = Mm.diagonal()
    acc = info["accel"]
    M_in = 0.0
    for i, p in enumerate(f.nodes):
        if p[1] > ycut and Md[6 * i] > 0:
            a_i = acc + np.cross(info["alpha"], p - info["cg"])
            Fz = -Md[6 * i] * (a_i[2] + G0)
            M_in += Fz * (p[1] - ycut)
    # tail lift on the outboard part of the tail spar
    tn = [n for n in m["tail"] if f.nodes[n][1] > ycut]
    M_tail = sum(ln["L_tail"] / len(m["tail"]) * (f.nodes[n][1] - ycut) for n in tn)
    M_hand = M_lift + M_in + M_tail
    out["L6 wing root bending, case F A (limit)"] = dict(M_beam_model_Nm=Mfe, M_strip_integration_Nm=M_hand, diff_pct=100 * (Mfe - M_hand) / M_hand,
                                                         lift_part=M_lift, inertia_part=M_in, tail_part=M_tail, accel_g=(acc / G0).tolist())
    # L7: discretisation study of the beam model (manoeuvre case F A and hover R2)
    rows = []
    sub = dict(flight=[allc["flight"][0]], rotor=[r for r in allc["rotor"] if r["name"].startswith("R2")], pusher=[], landing=[], parachute=[])
    for nh in (5, 10, 20, 40):
        mm = AF.build(g, n_half=nh, n_boom=2 * nh, n_fus=max(10, int(1.5 * nh)))
        rr = AF.analyse(mm, ac, sub, verbose=False)
        ra, rb = rr[allc["flight"][0]["name"]], rr[sub["rotor"][0]["name"]]
        rows.append(dict(n_half_span=nh, elems=len(mm["f"].elems), tip_mm_FA=ra["limit_wing_tip_dz_mm"],
                         front_spar_sigma_c_FA=ra["groups"]["spar front"]["sigma_c"], boom_sigma_c_R2=rb["groups"]["boom_L"]["sigma_c"],
                         boom_end_mm_R2=rb["limit_boom_end_dz_mm"]))
    ref = rows[-1]
    for r in rows:
        for k in ("tip_mm_FA", "front_spar_sigma_c_FA", "boom_sigma_c_R2", "boom_end_mm_R2"):
            r[k + "_diff_pct"] = 100 * (r[k] - ref[k]) / ref[k]
    out["L7 beam-model discretisation"] = rows
    OUT.mkdir(exist_ok=True)
    (OUT / "loads_checks.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:6000])
    plot_vn(vn)


def plot_vn(vn):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    IMG.mkdir(exist_ok=True)
    c = vn["curves"]
    V = np.array(c["V"])
    fig, ax = plt.subplots(figsize=(6, 3.8), dpi=130)
    ax.plot(V, c["stall_pos"], color="#1f5fa8", label="manoeuvre envelope")
    ax.plot(V, c["stall_neg"], color="#1f5fa8")
    ax.plot([vn["VA"], vn["VD"]], [3.8, 3.8], color="#1f5fa8")
    ax.plot([vn["VG"], vn["VC"], vn["VD"]], [-1.5, -1.5, 0], color="#1f5fa8")
    ax.plot([vn["VD"], vn["VD"]], [0, 3.8], color="#1f5fa8")
    for (nC, nD), sty in ((([vn["gust_VC"][0], vn["gust_VD"][0]]), "-"), (([vn["gust_VC"][1], vn["gust_VD"][1]]), "-")):
        ax.plot([0, vn["VC"], vn["VD"]], [1, nC, nD], "--", color="#d1495b", lw=1)
    ax.plot([], [], "--", color="#d1495b", label="gust lines (50/25 ft/s)")
    for nm, v in (("VA", vn["VA"]), ("VC", vn["VC"]), ("VD", vn["VD"])):
        ax.axvline(v, color="0.7", lw=0.6)
        ax.text(v, -2.1, nm, ha="center", fontsize=7)
    ax.set_xlabel("V (m/s EAS)")
    ax.set_ylabel("load factor n")
    ax.set_title("V-n diagram, placeholder design (725 kg, W/S 870 Pa)", fontsize=9)
    ax.set_ylim(-2.3, 4.5)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(IMG / "vn_placeholder.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
