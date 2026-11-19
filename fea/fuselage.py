"""Cabin primary structure (flat Divinycell sandwich panels), battery boxes and mounts, seat attachment - sized with
sandwich theory and hand methods on the loads of the global model -> fea/results/fuselage.json

    ~/tools/cadenv/bin/python fea/fuselage.py

Structural concept (WP P method, flat CNC-routed sandwich panels, tab-and-slot, bonded):
  keels      two vertical sandwich keel walls under the floor (y = +-0.36 m, depth 0.22 m, x 0.47 ... 3.5 m) with UD carbon
             caps top and bottom: carry the fuselage bending/shear in the cabin bay (canopy opening: no upper shell credit),
             the gear saddles, battery-box mounts and seat rails
  floor      sandwich floor between the keels (battery bay lid, cargo floor)
  frames     two wing-root ring frames (x = 1.83 / 2.31 m) with UD straps from the wing-root lugs down to the keels
  tail cone  tail-cone keel / frame with the rear parachute hard point and the pusher mount
Checks: face stress (strain cut-off allowables of the quasi-isotropic carbon fabric), core shear, face wrinkling
(0.5 (Ef Ec Gc)^1/3, knock-down 0.8), shear buckling of the keel webs, insert pull-out (potted inserts), bolts and
bearing; batteries 18 g forward / 6 g down / 4.5 g side (design_inputs), seats max(9 g x 1.33, 26 g dynamic peak).
All loads ultimate; fitting factor 1.15 on hard points.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import airframe as AF  # noqa: E402
from fea.geometry import MAT, ROOT, laminate_moduli, load  # noqa: E402

HERE = Path(__file__).resolve().parent
G0 = 9.80665
FF = 1.15
KSI = 6.894757e6

FACE = "cf_fabric_wet"
E_QI, G_QI = laminate_moduli(FACE, "qi")
CUT = MAT[FACE]["knockdowns"]["strain_cutoff"]
F_FACE_T, F_FACE_C, F_FACE_S = CUT["tension"] * E_QI, CUT["compression"] * E_QI, CUT["shear"] * G_QI
UD = MAT["cf_ud_wet"]["design"]
PLY_T = MAT[FACE]["t_ply_m"]


def core(key):
    return MAT[key]["design"]


def wrinkling(Ec, Gc):
    return 0.8 * 0.5 * (E_QI * Ec * Gc) ** (1 / 3)


def ms(allow, demand):
    return allow / demand - 1 if demand > 0 else float("inf")


def main():
    upd = HERE / "results" / "sizing_update.json"
    g = load(ROOT / "design" / "geometry.json", sizing=upd if upd.exists() else None)
    m, ac, allc, U = AF.run_all(g)
    W = g["mtow_kg"] * G0
    R = AF.member_resultants(m, U, "fuselage")          # x y z N Vy Vz T My Mz (ultimate)
    x = R[:, 0]
    cabin = (x > 0.9) & (x < 3.5)
    bay = cabin & ((x < 1.75) | (x > 2.40))              # outside the wing-root frame bay (frames take the local shear)
    My = R[cabin, 7].max()
    Mz = R[cabin, 8].max()
    Vz = R[bay, 5].max()
    Vy = R[bay, 4].max()
    Tq = R[cabin, 6].max()
    out = dict(global_ultimate=dict(My_Nm=My, Mz_Nm=Mz, Vz_N=Vz, Vy_N=Vy, T_Nm=Tq))
    checks = []
    panels = {}

    # ---------------------------------------------------------------- keels (2) with UD caps
    h, yk, n_keel = 0.22, 0.36, 2
    b_cap = 0.040
    F_cap = My / h / n_keel + Mz / (2 * yk) / 2          # vertical + lateral bending into the caps
    A_cap = F_cap / UD["Xc"] * 1.10
    t_cap = max(0.0015, math.ceil(A_cap / b_cap / 0.0003) * 0.0003)
    checks.append(dict(item="keel UD caps (40 mm wide)", demand_MPa=F_cap / (b_cap * t_cap) / 1e6, allow_MPa=UD["Xc"] / 1e6,
                       MS=ms(UD["Xc"], F_cap / (b_cap * t_cap)), t_cap_mm=t_cap * 1000))
    # web: sandwich, H80 12.7 mm, faces n plies quasi-iso
    cr = core("pvc_h80")
    tc = 0.0127
    q_web = Vz / n_keel / h + Tq / (2 * (2 * yk) * h) * 1.0      # shear flow from shear + torsion of the tub
    nply = 2
    while True:
        tf = nply * PLY_T
        tau_f = q_web / (2 * tf)
        D = E_QI * tf * (tc + tf) ** 2 / 2                        # sandwich bending stiffness per width
        tau_cr = 5.35 * math.pi**2 * D / (h**2 * 2 * tf) * 0.8    # long panel, SS edges, 0.8 knock-down
        if tau_f < F_FACE_S / 1.1 and tau_f < tau_cr / 1.1 or nply >= 8:
            break
        nply += 1
    checks.append(dict(item="keel web faces (shear)", plies_each_face=nply, demand_MPa=tau_f / 1e6, allow_MPa=F_FACE_S / 1e6,
                       MS=ms(F_FACE_S, tau_f)))
    checks.append(dict(item="keel web shear buckling", demand_MPa=tau_f / 1e6, allow_MPa=tau_cr / 1e6, MS=ms(tau_cr, tau_f)))
    panels["keel"] = dict(type="sandwich_panel", core="pvc_h80", core_t=tc, face_material=FACE, face_layup="[0/90,+-45]" if nply == 2 else f"{nply} plies quasi-iso",
                          face_t=nply * PLY_T, caps=dict(material="cf_ud_wet", b=b_cap, t=t_cap), depth=h, y=[-yk, yk], x=[0.47, 3.5])

    # ---------------------------------------------------------------- floor (cargo 100 kg at 6 g down crash / 3.8 x 1.5 flight)
    p = 100 * G0 * 6.0 / (0.65 * 0.6)
    span = 2 * yk
    Mf = p * span**2 / 8
    Vf = p * span / 2
    tc_f, nply_f = 0.019, 2
    tf = nply_f * PLY_T
    d = tc_f + tf
    s_face = Mf / (tf * d)
    tau_c = Vf / d
    checks.append(dict(item="floor faces (cargo 6 g)", demand_MPa=s_face / 1e6, allow_MPa=F_FACE_C / 1e6, MS=ms(F_FACE_C, s_face)))
    checks.append(dict(item="floor core shear H80", demand_MPa=tau_c / 1e6, allow_MPa=cr["Fs"] / 1e6, MS=ms(cr["Fs"], tau_c)))
    sw = wrinkling(cr["E"], cr["G"])
    checks.append(dict(item="floor face wrinkling", demand_MPa=s_face / 1e6, allow_MPa=sw / 1e6, MS=ms(sw, s_face)))
    panels["floor"] = dict(type="sandwich_panel", core="pvc_h80", core_t=tc_f, face_material=FACE, face_layup="[0/90,+-45]", face_t=tf, z=0.62)

    # ---------------------------------------------------------------- wing-root frames: UD straps lug -> keel
    lv = AF.link_vectors(m, U, "wing root fitting")
    Fv = max(abs(r["F"][2]) for rr in lv.values() for r in rr) * FF
    Fl = max(abs(r["F"][1]) for rr in lv.values() for r in rr) * FF
    A_strap = Fv / UD["Xt"] * 1.1
    b_s = 0.060
    t_s = math.ceil(A_strap / b_s / 0.0003) * 0.0003
    checks.append(dict(item="wing-root frame UD strap (60 mm, each side, each frame)", demand_MPa=Fv / (b_s * t_s) / 1e6,
                       allow_MPa=UD["Xt"] / 1e6, MS=ms(UD["Xt"], Fv / (b_s * t_s)), t_mm=t_s * 1000, design_vertical_N=Fv))
    # frame web (side-wall post 0.25 m wide, H100 core 19 mm): lateral component as in-plane shear
    tc_w, nply_w, wpost = 0.019, 4, 0.25
    tf = nply_w * PLY_T
    tau = Fl / (2 * tf * wpost)
    checks.append(dict(item="wing-root frame side post faces (lateral lug load)", demand_MPa=tau / 1e6, allow_MPa=F_FACE_S / 1e6,
                       MS=ms(F_FACE_S, tau)))
    # potted insert / strap-to-lug bolting into the frame (8 x AN5 double shear through 2 x 6 mm aluminium doublers)
    A5 = math.pi / 4 * (5 / 16 * 0.0254) ** 2
    checks.append(dict(item="frame-lug bolts 8 x AN5 double shear", demand_N=Fv, allow_N=8 * 2 * A5 * 75 * KSI, MS=ms(8 * 2 * A5 * 75 * KSI, Fv)))
    panels["wing_root_frames"] = dict(x=[1.8336, 2.3136], strap=dict(material="cf_ud_wet", b=b_s, t=t_s), post_core="pvc_h100", post_core_t=tc_w,
                                      post_face_plies=nply_w, doublers="2 x 6 mm 6061-T6 each side at the lug clevis")

    # ---------------------------------------------------------------- batteries: boxes and mounts
    bp = g["battery_packs"][0]
    mb = bp["kg"]
    di = g.get("_fea_inputs", {})
    ax_, az_, ay_ = di.get("battery_forward_g", 18.0), 6.0, 4.5
    Ffwd, Fdn, Fside = mb * G0 * ax_, mb * G0 * az_, mb * G0 * ay_
    nbr = 6                                                  # brackets per pack, 3 per keel wall
    Pbr = max(Ffwd, Fside) / nbr * FF
    Pten = Fdn / nbr * FF                                    # down load on the keel ledges, up (3 g) in bolt tension
    d4 = 0.25 * 0.0254
    A4 = math.pi / 4 * d4**2
    checks.append(dict(item="battery bracket bolts AN4 (shear, 18 g fwd)", demand_N=Pbr, allow_N=A4 * 75 * KSI, MS=ms(A4 * 75 * KSI, Pbr)))
    t_br = 0.003
    Fbru = MAT["al6061_t6_sheet"]["design"]["Fbru_eD2"]
    checks.append(dict(item="battery bracket bearing 6061-T6 3 mm", demand_N=Pbr, allow_N=Fbru * d4 * t_br, MS=ms(Fbru * d4 * t_br, Pbr)))
    # keel insert: potted 20 mm aluminium insert, load into the faces by bearing (both faces) and core shear (pull-out)
    nply_k = panels["keel"]["face_t"] / PLY_T
    t_face = panels["keel"]["face_t"]
    Fb_c = MAT["cf_fabric_wet_bearing"]["design"]["Fbru"]
    P_ins = Fb_c * 2 * t_face * 0.020
    checks.append(dict(item="keel potted insert bearing (battery bracket)", demand_N=Pbr, allow_N=P_ins, MS=ms(P_ins, Pbr),
                       note=f"faces {nply_k:.0f} plies each; add 2 local +-45 doubler plies at each insert if MS < 0"))
    # box: 2 mm 6061-T6 floor in shear (all module loads), G10 cell frames bolted to the floor every 0.21 m
    t_box = 0.002
    tau_box = Ffwd / (bp["width"] * t_box)
    checks.append(dict(item="battery box floor shear (2 mm 6061-T6)", demand_MPa=tau_box / 1e6,
                       allow_MPa=MAT["al6061_t6_sheet"]["design"]["Fsu"] / 1e6, MS=ms(MAT["al6061_t6_sheet"]["design"]["Fsu"], tau_box)))
    # front wall between cell-frame stiffeners (b = 0.21 m, a = 0.2 m), pressure of one cell module at 18 g
    pw = (mb / 3) * G0 * ax_ / (bp["width"] * bp["height"])
    beta = 0.287                                             # Roark table 11.4, SS rectangle a/b ~ 1, max stress coefficient
    t_w = 0.0025
    sw_ = beta * pw * 0.21**2 / t_w**2
    checks.append(dict(item="battery box front wall 2.5 mm between stiffeners (18 g)", demand_MPa=sw_ / 1e6,
                       allow_MPa=MAT["al6061_t6_sheet"]["design"]["Ftu"] / 1e6, MS=ms(MAT["al6061_t6_sheet"]["design"]["Ftu"], sw_)))
    panels["battery_box"] = dict(material="al6061_t6_sheet", floor_t=t_box, walls_t=t_w, cell_frames="G10 every 0.21 m bolted to the floor",
                                 brackets=f"{nbr} x 3 mm 6061-T6 angles per pack, AN4 bolts into potted keel inserts", g_design=dict(fwd=ax_, down=az_, side=ay_))

    # ---------------------------------------------------------------- seats
    st = g["seats"][0]
    msr = st["occupant_kg"] + st["seat_kg"]
    h_cg = st["z"] - g["fuselage"]["cabin"]["floor_z"]
    Fs = max(9.0 * 1.33, 26.0) * msr * G0
    Tleg = Fs * h_cg / 0.45 / 2
    Vleg = Fs / 4
    d5 = 5 / 16 * 0.0254
    A5s = math.pi / 4 * d5**2
    comb = (Vleg / (2 * A5s * 75 * KSI)) ** 2 + (Tleg / (2 * A5s * 125 * KSI)) ** 2
    checks.append(dict(item="seat-leg fitting bolts 2 x AN5 (shear + tension interaction)", demand_ratio=comb, MS=1 / math.sqrt(comb) - 1,
                       basis="max(9 g x 1.33, 26 g dynamic) on 110 kg"))
    P_ins_s = Fb_c * 2 * PLY_T * 4 * 0.025                   # 25 mm potted insert, 4-ply faces at the seat rails
    checks.append(dict(item="seat rail insert in keel cap region (bearing)", demand_N=Vleg, allow_N=P_ins_s, MS=ms(P_ins_s, Vleg)))
    # (a potted insert alone in the H100 core gives only ~1/5 of the rear-leg tension: the rear legs are through-bolted)
    pull_bolt = Fb_c * 2 * 0.0018 * 0.040 * math.pi       # through-bolted backing plate: bearing over 40 mm washer ring (both faces)
    checks.append(dict(item="seat rear leg through-bolted to keel cap with backing plate", demand_N=Tleg, allow_N=pull_bolt, MS=ms(pull_bolt, Tleg)))

    # ---------------------------------------------------------------- tail cone: pusher mount and rear parachute point
    pu = AF.link_vectors(m, U, "pusher mount")
    Fp = max([np.linalg.norm(r["F"]) for rr in pu.values() for r in rr] + [0.0]) * FF
    if Fp > 0:
        checks.append(dict(item="pusher motor plate to boom-end plug: 4 x AN5 (shear)", demand_N=Fp, allow_N=4 * A5 * 75 * KSI,
                           MS=ms(4 * A5 * 75 * KSI, Fp)))
    Pch = g["parachute"].get("opening_load_N", 47400.0) * g["parachute"].get("max_share", 0.5) * 1.5 * FF
    # rear riser point: 4130 hard point (part P5) bolted to a tail-cone ring frame with 2 UD straps (60 x t) running forward to the keels
    t_rs = math.ceil(Pch / 2 / UD["Xt"] / 0.060 / 0.0003 * 1.1) * 0.0003
    checks.append(dict(item="rear parachute frame UD straps (2 x 60 mm)", demand_MPa=Pch / 2 / (0.06 * t_rs) / 1e6, allow_MPa=UD["Xt"] / 1e6,
                       MS=ms(UD["Xt"], Pch / 2 / (0.06 * t_rs)), t_mm=t_rs * 1000))
    panels["tail_cone"] = dict(parachute_frame_straps=dict(material="cf_ud_wet", b=0.06, t=t_rs, n=2), pusher_bolts="4 x AN5 (boom-end plug, iteration 3.2)")

    # ---------------------------------------------------------------- mass of the sized cabin primary structure (estimate)
    rho_c = {"pvc_h80": 80, "pvc_h100": 100}
    rho_f = MAT[FACE]["rho"]
    rho_ud = MAT["cf_ud_wet"]["rho"]
    keel_m = n_keel * (3.03 * h * (2 * panels["keel"]["face_t"] * rho_f + tc * rho_c["pvc_h80"] * 1.15) + 2 * 3.03 * b_cap * t_cap * rho_ud)
    floor_m = 3.0 * 2 * yk * (2 * PLY_T * 2 * rho_f + tc_f * rho_c["pvc_h80"] * 1.15)
    frames_m = 2 * (2 * 1.2 * b_s * t_s * rho_ud + 2 * 1.2 * wpost * (2 * nply_w * PLY_T * rho_f + tc_w * 100 * 1.15)) + 4 * 0.6
    box_m = 2 * (2 * 0.64 * 0.7 * t_box + 2 * (0.7 + 0.64) * 0.2 * t_w) * 2700 + 2 * 1.5
    out.update(checks=checks, panels=panels,
               mass_estimate_kg=dict(keels=keel_m, floor=floor_m, wing_root_frames=frames_m, battery_boxes=box_m,
                                     note="primary members only; bonding, tapes, inserts +15 % included in the core factor"))
    (HERE / "results" / "fuselage.json").write_text(json.dumps(out, indent=1, default=float))
    for c in checks:
        print(f"{c['item']:62s} MS {c['MS']:+.2f}")
    print(json.dumps(out["mass_estimate_kg"], indent=1))
    print(json.dumps(out["global_ultimate"], indent=1))


if __name__ == "__main__":
    main()
