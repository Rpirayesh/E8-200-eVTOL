"""Iteration-3 detail checks of the weight reductions and new parts -> fea/results/details.json

    ~/tools/cadenv/bin/python fea/details.py

1. Wing skin wrinkling on the voided XPS cores (30 mm of foam kept under each skin) and with an H45 strip over the spar box
2. Main-spar +-45 webs on the H45 box foam: face wrinkling under the principal compression of the web shear
3. Pylon head flange (PY-HEAD, pocketed -25 %) between the isolator bosses
4. Skid clamp (LG-SKCL, pocketed -30 %): bolts and bonded socket
5. Tail-spar clamp (TL-CLAMP, pocketed -30 %): socket bond and bolts
6. Gear damper hard point (LG-DUP) and pivot saddle loads with the oleo dampers
7. Parachute cradle (CH-CRADLE, -40 %): required post section (geometry to be confirmed on the CAD part)
Loads: global beam model with the sized sections, ultimate x 1.15 fitting factor.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import airframe as AF  # noqa: E402
from fea import sizing as SZ  # noqa: E402
from fea.geometry import MAT, ROOT, laminate_moduli, load  # noqa: E402

HERE = Path(__file__).resolve().parent
G0 = 9.80665
FF = 1.15
KSI = 6.894757e6


def wrinkling(Ef, Ec, Gc):
    return 0.8 * 0.5 * (Ef * Ec * Gc) ** (1 / 3)


def ms(a, d):
    return a / d - 1 if d > 0 else float("inf")


def main():
    upd = HERE / "results" / "sizing_update.json"
    g = load(ROOT / "design" / "geometry.json", sizing=upd)
    env, m, ac, allc = SZ.demand(g)
    cases = AF.build_cases(m, ac, allc)
    f = m["f"]
    support = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    U = {k: f.solve_inertia_relief(F, support, gravity=(0, 0, -G0))[0] for k, F in cases.items()}
    checks = []
    ud = MAT["cf_ud_wet"]["design"]
    # 1 wing skin wrinkling ------------------------------------------------------------------------------------------
    # skin strain = cap strain x (z_skin - z_NA) / (z_cap - z_NA) from the LS(1)-0417 ordinates (plane sections)
    af = np.loadtxt(ROOT / "validation" / "cfd" / "reference" / "ls417_coordinates_TND7428.dat", skiprows=1)
    i0 = int(np.argmin(af[:, 0]))
    up, lo = af[:i0 + 1][::-1], af[i0:]
    zu = lambda x: np.interp(x, up[:, 0], up[:, 1])          # noqa: E731
    zl = lambda x: np.interp(x, lo[:, 0], lo[:, 1])          # noqa: E731
    c = g["wing"]["root_chord"]
    xm, xr = g["wing"]["spars"][0]["x_c"], g["wing"]["spars"][-1]["x_c"]
    sm = g["wing"]["spars"][0]
    s_ = g["wing"]["span"] / 2
    st0 = sm["stations"][1]["section"] if sm.get("stations") else sm["section_root"]
    Am_, Ar_ = 2 * st0["b_cap"] * st0["t_cap"], 2 * 0.048 * 0.0015
    zNA = (Am_ * (zu(xm) + zl(xm)) / 2 + Ar_ * (zu(xr) + zl(xr)) / 2) / (Am_ + Ar_)
    zcap = zu(xm) - st0["t_cap"] / c / 2
    xs = np.linspace(0.02, 0.95, 187)
    fac = (zu(xs) - zNA) / (zcap - zNA)
    # spanwise: compressive cap ratio by station
    span_r = sorted(((abs(0.5 * (f.nodes[e[0]][1] + f.nodes[e[1]][1])) / s_, v["ratios"].get("compression", 0))
                     for e, v in env.items() if v["tag"] == "spar main"))
    rc = max(r for _, r in span_r)
    eps = rc * ud["Xc"] / ud["E1"]                                  # ultimate cap strain at the critical station
    Es, _ = laminate_moduli("cf_fabric_wet", "+-45")
    sig = Es * eps * fac.max()
    t_sk = g["wing"]["torsion_box"]["skin_t"]
    sw_x = None
    for core in ("xps_foam", "pvc_h45", "pvc_h80"):
        cm = MAT[core]["design"]
        sw = wrinkling(Es, cm["E"], cm["G"])
        lam = 1.82 * t_sk * (Es * cm["E"] / cm["G"] ** 2) ** (1 / 3)
        if core == "xps_foam":
            sw_x = sw
        checks.append(dict(item=f"wing upper skin (+-45, {t_sk*1e3:.1f} mm) wrinkling on {core} (peak at x/c {xs[fac.argmax()]:.2f})",
                           demand_MPa=sig / 1e6, allow_MPa=sw / 1e6, MS=ms(sw, sig), wrinkle_half_wave_mm=lam * 1000,
                           note=f"ultimate cap strain {eps*100:.3f} % x skin/cap height ratio {fac.max():.2f}; foam depth needed "
                                "~0.5 x half-wave << 30 mm kept by the voids"))
    bad_x = xs[Es * eps * fac > sw_x]
    bad_eta = [eta for eta, r in span_r if Es * (r * ud["Xc"] / ud["E1"]) * fac.max() > sw_x]
    region = dict(x_c_from=float(bad_x.min()) if len(bad_x) else None, x_c_to=float(bad_x.max()) if len(bad_x) else None,
                  eta_to=float(max(bad_eta)) if bad_eta else 0.0, y_to_m=float(max(bad_eta) * s_) if bad_eta else 0.0)
    cad_strip = dict(x_c_from=xm - (st0["b_cap"] / 2 + 0.03) / c, x_c_to=xm + (st0["b_cap"] / 2 + 0.03) / c)
    checks_strip = dict(item="H45 support region needed under the upper skin (XPS would wrinkle there)", **region,
                        cad_strips_W_SPM_S=cad_strip,
                        satisfied_by_cad_strips=bool(region["x_c_from"] is None or (cad_strip["x_c_from"] <= region["x_c_from"]
                                                                                      and cad_strip["x_c_to"] >= region["x_c_to"])))
    # 2 main-spar webs on H45 ---------------------------------------------------------------------------------------
    rw = max(v["ratios"].get("web shear", 0) for v in env.values() if v["tag"] == "spar main")
    fab = MAT["cf_fabric_wet"]["design"]
    tau = rw * 0.5 * min(fab["Xt"], fab["Xc"])
    c45 = MAT["pvc_h45"]["design"]
    sw = wrinkling(fab["E1"], c45["E"], c45["G"])                  # principal compression along the +-45 fibres
    checks.append(dict(item="main-spar +-45 webs on H45 box foam: wrinkling under web shear", demand_MPa=tau / 1e6, allow_MPa=sw / 1e6,
                       MS=ms(sw, tau), note="principal compression = tau, along the fibres (E1 of the fabric)"))
    h = 0.18
    b = 0.08
    D = fab["E1"] * 0.0005 * b**2 / 2
    tcr = 5.35 * math.pi**2 * D / (h**2 * 2 * 0.0005) * 0.8
    checks.append(dict(item="main-spar box (2 webs + H45) shear buckling as a sandwich panel", demand_MPa=tau / 1e6, allow_MPa=tcr / 1e6,
                       MS=ms(tcr, tau)))
    al = MAT["al6061_t6_extr"]["design"]
    # 3 pylon head flange ------------------------------------------------------------------------------------------------
    rot = ac["rotors"][0]
    k = 1.5 * FF
    T = rot["T_max"] * k
    Q = rot["kQ"] * rot["T_max"] * 1.25 * k
    Mg = max(np.linalg.norm(mm[0]["M_Nm"][:2]) for mm in [r["mount"] for r in allc["rotor"] if "mount" in r]) * k
    ni, ri, rp, t_fl = 6, 0.105, 0.05, 0.008
    F_iso = T / ni + Mg / (ni * ri / 2)
    w = 2 * math.pi * ri / ni * 0.75                                # 25 % pocketed between the bosses
    M = F_iso * (ri - rp)
    s_fl = 6 * M / (w * t_fl**2)
    checks.append(dict(item="pylon head flange 8 mm between isolators (PY-HEAD, -25 %)", demand_MPa=s_fl / 1e6, allow_MPa=al["Ftu"] / 1e6,
                       MS=ms(al["Ftu"], s_fl), note=f"isolator load {F_iso:.0f} N ultimate x 1.15 as a cantilever strip"))
    A4 = math.pi / 4 * (0.25 * 0.0254) ** 2
    A5 = math.pi / 4 * (5 / 16 * 0.0254) ** 2
    tau_bond = MAT["ea9394"]["design"]["tau_avg"]
    # 4 skid clamp --------------------------------------------------------------------------------------------------------
    lv = AF.link_vectors(m, U, "skid saddle")
    Fs = max(np.linalg.norm(r["F"]) for rr in lv.values() for r in rr) * FF
    P_bolts = 2 * 2 * A4 * 75 * KSI                                  # 2 x AN4 double shear
    P_bond = math.pi * 0.076 * 0.060 * tau_bond / 1.5                # 60 mm socket, bonded-joint factor 1.5
    checks.append(dict(item="skid clamp (LG-SKCL, -30 %): 2 x AN4 double shear", demand_N=Fs, allow_N=P_bolts, MS=ms(P_bolts, Fs)))
    checks.append(dict(item="skid clamp socket bond (60 mm, EA 9394, factor 1.5)", demand_N=Fs, allow_N=P_bond, MS=ms(P_bond, Fs),
                       note="bond and bolts are redundant paths; the bolts alone carry the load"))
    tclamp = 0.7 * 0.012                                             # clamp wall after pocketing
    s_cl = Fs / (2 * 0.06 * tclamp)
    checks.append(dict(item="skid clamp wall (12 mm -> 8.4 mm, 60 mm long), shear", demand_MPa=s_cl / 1e6, allow_MPa=al["Fsu"] / 1e6,
                       MS=ms(al["Fsu"], s_cl)))
    # 5 tail clamp --------------------------------------------------------------------------------------------------------
    Rt = AF.member_resultants(m, U, "tail spar")
    yb = abs(g["booms"][0]["y"])
    end = Rt[np.argmax(np.abs(Rt[:, 1]))]
    Mt = float(np.hypot(end[7], end[8])) * FF
    Vt = float(np.hypot(end[4], end[5])) * FF
    d_ts = g["tail"]["spar_section"]["od"]
    L_s = 0.110                                                     # iteration 3.3 CAD sockets
    p_br = 6 * Mt / (d_ts * L_s**2) + Vt / (d_ts * L_s)              # moment transferred by bearing at the socket ends
    allow_br = 0.5 * ud["Yc"]
    checks.append(dict(item="tail spar bearing in the TL-CLAMP socket (110 mm, moment by end bearing)", demand_MPa=p_br / 1e6,
                       allow_MPa=allow_br / 1e6, MS=ms(allow_br, p_br),
                       note=f"M {Mt:.0f} N m, V {Vt:.0f} N ultimate x 1.15; the bond carries axial load and torsion only"))
    s_tc = Mt / (math.pi / 4 * ((d_ts / 2 + 0.006) ** 4 - (d_ts / 2) ** 4) / (d_ts / 2 + 0.006))
    checks.append(dict(item="TL-CLAMP socket wall 6 mm after pocketing, bending", demand_MPa=s_tc / 1e6, allow_MPa=al["Ftu"] / 1e6,
                       MS=ms(al["Ftu"], s_tc)))
    # 6 damper hard point / pivot saddle ------------------------------------------------------------------------------------
    lv = AF.link_vectors(m, U, "gear damper hard point")
    Fd = max(np.linalg.norm(r["F"]) for rr in lv.values() for r in rr) * FF
    checks.append(dict(item="damper upper fitting (LG-DUP): 4 x AN5 single shear", demand_N=Fd, allow_N=4 * A5 * 75 * KSI, MS=ms(4 * A5 * 75 * KSI, Fd)))
    Fbru = MAT["cf_fabric_wet_bearing"]["design"]["Fbru"]
    P_ins = 4 * Fbru * 2 * (6 * 0.25e-3 + 2 * 0.25e-3) * 0.025         # 4 potted inserts, faces 2 plies + 6 doubler plies
    checks.append(dict(item="damper hard point inserts in the cabin side panel (4 x 25 mm, 8-ply local faces)", demand_N=Fd, allow_N=P_ins,
                       MS=ms(P_ins, Fd)))
    lv = AF.link_vectors(m, U, "gear attach")
    Fp = max(np.linalg.norm(r["F"]) for rr in lv.values() for r in rr) * FF
    d_pin = 0.019
    P_pin = 2 * math.pi / 4 * d_pin**2 * MAT["steel_4130_n"]["design"]["Fsu"]
    checks.append(dict(item="gear leg pivot pin 19 mm 4130 double shear", demand_N=Fp, allow_N=P_pin, MS=ms(P_pin, Fp)))
    # 6b pusher boom-end plug (iteration 3.2): 6061 plug bonded 150 mm into the boom end
    lvp = AF.link_vectors(m, U, "pusher mount")
    if lvp:
        rows = [r for rr in lvp.values() for r in rr]
        rM = max(rows, key=lambda r: np.linalg.norm(r["M"][1:]))
        Fx = max(abs(r["F"][0]) for r in rows) * FF
        Tq = max(abs(r["M"][0]) for r in rows) * FF
        Mb = float(np.linalg.norm(rM["M"][1:])) * FF
        D_in, Lp = 0.1016, 0.150
        tau_b = Fx / (math.pi * D_in * Lp) + Tq / (2 * math.pi * (D_in / 2) ** 2 * Lp)
        checks.append(dict(item="pusher boom-end plug bond (150 mm, EA 9394, factor 1.5): thrust + torque", demand_MPa=tau_b / 1e6,
                           allow_MPa=tau_bond / 1.5 / 1e6, MS=ms(tau_bond / 1.5, tau_b), note="cross-bolts redundant"))
        p_br = 6 * Mb / (D_in * Lp**2)
        checks.append(dict(item="boom wall bearing at the pusher plug (gyroscopic + inertia moment by end bearing)", demand_MPa=p_br / 1e6,
                           allow_MPa=0.5 * ud["Yc"] / 1e6, MS=ms(0.5 * ud["Yc"], p_br), note=f"plug moment {Mb:.0f} N m ultimate x 1.15"))
        Ip_ = math.pi / 64 * (D_in**4 - (D_in - 0.03) ** 4)
        s_pl = Mb * (D_in / 2) / Ip_
        checks.append(dict(item="pusher plug 6061 (15 mm wall) bending at the boom end", demand_MPa=s_pl / 1e6, allow_MPa=al["Ftu"] / 1e6,
                           MS=ms(al["Ftu"], s_pl)))
    # 7 parachute cradle ------------------------------------------------------------------------------------------------------
    mc = g["parachute"]["kg"]
    Fc = mc * G0 * 18.0 * FF
    hpost = 0.12
    Zreq = Fc / 2 * hpost / al["Ftu"]
    checks_cr = dict(item="parachute cradle posts (CH-CRADLE, -40 %): required section modulus per post", design_load_N=Fc,
                     Z_required_mm3=Zreq * 1e9, note="18 g forward on the 28.2 kg canister, two posts 120 mm high; confirm on the CAD part")
    # CH-CRADLE as built in the CAD (iteration 3.1): 8 mm beam 100 mm wide with 76 mm lightening holes under the posts
    zc_ = 0.078                                                       # canister cg above the post tops (CAD)
    Fz_c = Fc * zc_ / 0.240                                           # push-pull couple between the posts (240 mm apart)
    M_b = Fz_c * 0.16 * (0.637 - 0.16) / 0.637                        # beam (simply supported 637 mm) at the post
    Ftu = al["Ftu"]
    for label, wnet in (("solid 100 mm", 0.100), ("through a 76 mm lightening hole (as drawn)", 0.024)):
        sb = M_b / (wnet * 0.008**2 / 6)
        checks.append(dict(item=f"parachute cradle beam 8 mm, section {label}", demand_MPa=sb / 1e6, allow_MPa=Ftu / 1e6, MS=ms(Ftu, sb),
                           note="18 g forward x 1.15 on the 28.2 kg canister; post couple into the beam"))
    sp = Fc / 2 / (0.024 * 0.024) + Fz_c / (0.024 * 0.024)
    checks.append(dict(item="parachute cradle posts 24 x 24 mm (shear + push-pull)", demand_MPa=sp / 1e6, allow_MPa=al["Fsu"] / 1e6,
                       MS=ms(al["Fsu"], sp)))
    # LG-DCL damper collar bond on the leg
    A_c = math.pi * 0.076 * 0.096
    checks.append(dict(item="damper collar LG-DCL bond on the 76 mm leg (96 mm, EA 9394, factor 1.5)", demand_N=Fd, allow_N=A_c * tau_bond / 1.5,
                       MS=ms(A_c * tau_bond / 1.5, Fd), note="collar also pinned (redundant)"))
    out = dict(checks=checks, cradle_requirement=checks_cr, skin_support_region=checks_strip,
               loads=dict(skid_clamp_N=Fs, tail_clamp_M_Nm=Mt, damper_hard_point_N=Fd, gear_pivot_N=Fp, ultimate_cap_strain=eps))
    (HERE / "results" / "details.json").write_text(json.dumps(out, indent=1, default=float))
    for c in checks:
        print(f"{c['MS']:+7.2f}  {c['item']}")
    print(checks_cr)


if __name__ == "__main__":
    main()
