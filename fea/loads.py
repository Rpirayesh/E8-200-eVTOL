"""Design load cases for the E8-200 lift + cruise eVTOL (parametric on mass and geometry).

    ~/tools/cadenv/bin/python fea/loads.py [geometry.json] [selected_design.json]   # placeholder design if omitted

Frame: x aft from the nose, y right, z up (m); forces N; ALL load factors in g.
Every case returns LIMIT loads unless the case says 'ultimate'; the airframe model multiplies limit loads by
the ultimate factor 1.5 (requirements.safety.ultimate_factor).  Emergency-landing (crash) inertia factors of
CS-23.561 are already ultimate.

Contents
  vn_diagram        CS-23 style manoeuvre envelope + gust lines (CS-23.333/.335/.337/.341, Amdt 4 formulas)
  wing_line_loads   spanwise lift (Schrenk) and pitching moment for a flight point, tail balance load
  rotor_cases       hover / transition: all rotors max, pitch/roll/yaw saturation, one-motor-out (LP thrust
                    re-allocation), motor torque, gyroscopic moments (CS-23.371 rates)
  landing_cases     level 3 g, one-side, side load (CS-23.485 split), drag (inclined reaction)
  crash_cases       CS-23.561 static emergency-landing factors per item, 18 g forward for items aft of /
                    above the occupants, seat/harness factor 1.33; AC 23.562 dynamic pulse data
  parachute_cases   opening shock along riser directions at the attachment points
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

G0 = 9.80665
RHO0 = 1.225
KT = 0.514444
HERE = Path(__file__).resolve().parent


def isa_density(h_m, dT=0.0):
    T = 288.15 - 0.0065 * h_m + dT
    p = 101325.0 * (1 - 0.0065 * h_m / 288.15) ** 5.25588
    return p / (287.053 * T)


# ============================================================================= V-n
def vn_diagram(ac: dict) -> dict:
    """Manoeuvre and gust envelope. ac keys: mtow_kg, wing{S, mac, CLalpha, CLmax, CLmin}, speeds{VC (EAS m/s),
    VD (optional)}, limits{n_pos, n_neg}, altitude_m (gust alleviation density)."""
    W = ac["mtow_kg"] * G0
    w = ac["wing"]
    S, c, a = w["S"], w["mac"], w["CLalpha"]
    WS = W / S
    npos, nneg = ac["limits"]["n_pos"], ac["limits"]["n_neg"]
    rho = isa_density(ac.get("altitude_m", 0.0))
    VS1 = math.sqrt(2 * W / (RHO0 * S * w["CLmax"]))
    VSneg = math.sqrt(2 * W / (RHO0 * S * abs(w["CLmin"])))
    VA = VS1 * math.sqrt(npos)
    VG = VSneg * math.sqrt(abs(nneg))
    WS_psf = WS / 47.880259
    VCmin = 33 * math.sqrt(WS_psf) * KT                       # CS-23.335(a)(1) normal category, EAS
    VC = ac["speeds"]["VC"]
    VD = ac["speeds"].get("VD") or max(1.25 * VC, 1.40 * VC)   # declared-VC rule: VD = 1.4 VC (CS-23.335(b) ratio)
    mu = 2 * WS / (rho * c * a * G0)
    kg = 0.88 * mu / (5.3 + mu)

    def gust(Ude, V):
        dn = kg * RHO0 * Ude * V * a / (2 * WS)
        return 1 + dn, 1 - dn
    Ude_C, Ude_D = 50 * 0.3048, 25 * 0.3048                    # CS-23.341 (Amdt 4): 50 ft/s at VC, 25 ft/s at VD
    gC, gD = gust(Ude_C, VC), gust(Ude_D, VD)
    design = [
        dict(name="A  manoeuvre +n at VA", V=VA, n=npos),
        dict(name="D  manoeuvre +n at VD", V=VD, n=npos),
        dict(name="G  manoeuvre -n at VG", V=VG, n=nneg),
        dict(name="E  -n at VC", V=VC, n=nneg),
        dict(name="F  0 g at VD", V=VD, n=0.0),
        dict(name="C+ gust at VC", V=VC, n=gC[0]),
        dict(name="C- gust at VC", V=VC, n=gC[1]),
        dict(name="D+ gust at VD", V=VD, n=gD[0]),
        dict(name="D- gust at VD", V=VD, n=gD[1]),
    ]
    n_max = max(npos, gC[0], gD[0])
    n_min = min(nneg, gC[1], gD[1])
    V = np.linspace(0, VD, 200)
    stall_pos = np.minimum(RHO0 * V**2 * S * w["CLmax"] / (2 * W), npos)
    stall_neg = np.maximum(-RHO0 * V**2 * S * abs(w["CLmin"]) / (2 * W), nneg)
    return dict(W_N=W, wing_loading_Pa=WS, VS1=VS1, VSneg=VSneg, VA=VA, VG=VG, VC=VC, VC_min_cs23=VCmin, VD=VD,
                mu_g=mu, k_g=kg, gust_VC=gC, gust_VD=gD, n_max=n_max, n_min=n_min, design_points=design,
                curves=dict(V=V.tolist(), stall_pos=stall_pos.tolist(), stall_neg=stall_neg.tolist()),
                notes=["speeds are EAS (m/s)", f"CS-23 minimum VC for this wing loading = {VCmin:.1f} m/s EAS; "
                       "a lower declared VC is used for the eVTOL (SC-VTOL leaves VC to the applicant); gust lines use the declared VC/VD",
                       "manoeuvre limits from requirements.yaml (+3.8 / -1.5)"])


# ============================================================================= wing / tail
def schrenk(y, b, c_root, c_tip):
    """Normalised span load per unit length (integrates to 1 over the full span): Schrenk average of
    the planform chord and the elliptic distribution."""
    s = b / 2
    c = c_root + (c_tip - c_root) * np.abs(y) / s
    S = (c_root + c_tip) * s
    ell = 4 * S / (math.pi * b) * np.sqrt(np.clip(1 - (y / s) ** 2, 0, 1))
    q = 0.5 * (c + ell)
    return q / np.trapezoid(q, y), c


def wing_line_loads(ac: dict, n: float, V: float, ny=81, tail=True) -> dict:
    """Spanwise air loads for a symmetric flight point (limit): lift per length l(y) acting at the quarter chord,
    pitching moment per length m(y) = q c^2 Cm0 about the quarter chord (positive nose-up, i.e. about +y),
    and the horizontal-tail balance load from a moment balance about the cg (x aft: a lift at x_p gives a
    nose-up moment L (x_cg - x_p))."""
    w = ac["wing"]
    W = ac["mtow_kg"] * G0
    b = w["span"]
    y = np.linspace(-b / 2, b / 2, ny)
    shape, c = schrenk(y, b, w["c_root"], w["c_tip"])
    q = 0.5 * RHO0 * V**2
    Lt = 0.0
    M0 = q * w["S"] * w["mac"] * w.get("Cm0", -0.05)
    if tail and "x_ac_tail" in ac and "x_cg" in ac:
        # n W = Lw + Lt ;  Lw (x_cg - x_ac_w) + M0 ... moments about the cg (x aft, nose-up positive):
        # nose-up moment = Lw (x_cg - x_acw) + M0 + Lt (x_cg - x_act)  = 0
        xa, xt, xc = w["x_ac"], ac["x_ac_tail"], ac["x_cg"]
        Lt = -(n * W * (xc - xa) + M0) / ((xc - xt) - (xc - xa))
    Lw = n * W - Lt
    lift = Lw * shape
    mom = q * c**2 * w.get("Cm0", -0.05)
    return dict(y=y.tolist(), chord=c.tolist(), lift_per_m=lift.tolist(), cm_per_m=mom.tolist(), L_wing=Lw, L_tail=Lt, q=q,
                root_shear_half=float(np.trapezoid(lift[y >= 0], y[y >= 0])),
                root_moment_half=float(np.trapezoid(lift[y >= 0] * y[y >= 0], y[y >= 0])))


def asymmetric_wing(line: dict, frac_other=0.75) -> dict:
    """CS-23.349(b) style rolling case: 100 % semispan load on the right, 75 % on the left (applied with 2/3 of n_A by the caller)."""
    y = np.array(line["y"])
    l = np.array(line["lift_per_m"]).copy()
    l[y < 0] *= frac_other
    out = dict(line)
    out["lift_per_m"] = l.tolist()
    return out


# ============================================================================= rotors
def allocate(rotors, W, x_cg, y_cg, n=1.0, failed=None, yaw_free=False):
    """Thrust allocation minimising the highest thrust fraction T_i / T_max,i while trimming vertical force,
    roll, pitch (about the cg) and yaw (rotor reaction torque, Q = kQ T). Returns thrusts and the max fraction."""
    N = len(rotors)
    idx = [i for i in range(N) if i != failed]
    # variables: T_i (i in idx), t (max fraction)
    nv = len(idx) + 1
    c = np.zeros(nv)
    c[-1] = 1.0
    Aeq, beq = [], []
    Aeq.append([1.0] * len(idx) + [0.0]); beq.append(n * W)
    Aeq.append([rotors[i]["y"] - y_cg for i in idx] + [0.0]); beq.append(0.0)
    Aeq.append([rotors[i]["x"] - x_cg for i in idx] + [0.0]); beq.append(0.0)
    if not yaw_free:
        Aeq.append([rotors[i]["spin"] * rotors[i]["kQ"] for i in idx] + [0.0]); beq.append(0.0)
    Aub = np.zeros((len(idx), nv))
    for k, i in enumerate(idx):
        Aub[k, k] = 1.0
        Aub[k, -1] = -rotors[i]["T_max"]
    r = linprog(c, A_ub=Aub, b_ub=np.zeros(len(idx)), A_eq=np.array(Aeq), b_eq=np.array(beq),
                bounds=[(0, None)] * len(idx) + [(0, None)], method="highs")
    if not r.success:
        return None
    T = np.zeros(N)
    T[idx] = r.x[:-1]
    return dict(T=T.tolist(), max_fraction=float(r.x[-1]))


def rotor_cases(ac: dict) -> list[dict]:
    """Lift-rotor and pusher load cases (limit). Each case: thrust/torque per rotor, gyroscopic moments,
    and the corresponding rigid-body state (balanced by inertia relief in the airframe model)."""
    W = ac["mtow_kg"] * G0
    R = ac["rotors"]
    xcg, ycg = ac["x_cg"], ac.get("y_cg", 0.0)
    Tmax = np.array([r["T_max"] for r in R])
    cases = []

    def case(name, T, note="", gyro=None, torque_factor=1.0):
        T = np.asarray(T, float)
        Q = [r["spin"] * r["kQ"] * t * torque_factor for r, t in zip(R, T)]
        cases.append(dict(name=name, category="rotor", thrust_N=T.tolist(), torque_Nm=Q,
                          thrust_fraction=(T / Tmax).tolist(), gyro_Nm=gyro or [[0, 0, 0]] * len(R), note=note,
                          net_vertical_g=float(T.sum() / W)))
    T_hover = allocate(R, W, xcg, ycg)
    case("R1 hover 1 g trimmed", T_hover["T"], "deflection / fatigue reference")
    case("R2 all rotors max thrust", Tmax, "vertical acceleration (sum Tmax / W - 1) g balanced by inertia relief")
    front = [r["x"] < xcg for r in R]
    case("R3 pitch saturation: front max, rear idle", [t if f else 0.0 for t, f in zip(Tmax, front)])
    case("R4 pitch saturation: rear max, front idle", [0.0 if f else t for t, f in zip(Tmax, front)])
    case("R5 roll saturation: right max, left idle", [t if r["y"] > ycg else 0.0 for t, r in zip(Tmax, R)])
    case("R6 yaw saturation: CCW rotors max, CW idle", [t if r["spin"] > 0 else 0.0 for t, r in zip(Tmax, R)],
         "spin +1 = counter-clockwise seen from above; airframe reaction torque = -spin kQ T about +z")
    # one-motor-out: worst rotor, trimmed hover at 1 g (and 1.2 g flare / climb-out) with the others
    worst = None
    for i in range(len(R)):
        for n_g in (1.0,):
            a = allocate(R, W, xcg, ycg, n=n_g, failed=i) or allocate(R, W, xcg, ycg, n=n_g, failed=i, yaw_free=True)
            if a is None:
                continue
            if worst is None or a["max_fraction"] > worst[2]["max_fraction"]:
                worst = (i, n_g, a)
    oei = []
    for i in range(len(R)):
        row = dict(failed=R[i]["name"])
        for n_g in (1.0, 1.2):
            a = allocate(R, W, xcg, ycg, n=n_g, failed=i)
            ay = a or allocate(R, W, xcg, ycg, n=n_g, failed=i, yaw_free=True)
            row[f"max_fraction_{n_g:.1f}g"] = None if ay is None else ay["max_fraction"]
            row[f"yaw_trimmed_{n_g:.1f}g"] = a is not None
        oei.append(row)
    if worst:
        i, n_g, a = worst
        case(f"R7 one motor out ({R[i]['name']} failed), {n_g:.1f} g trimmed", a["T"],
             f"highest remaining thrust fraction {a['max_fraction']:.2f} (requirement: <= 1.0 of peak)")
    # one motor out in the 1.2 g flare (requirement from design iteration 2): worst failed rotor
    wf = None
    nfl = ac.get("oei_flare_g", 1.2)
    for i in range(len(R)):
        a = allocate(R, W, xcg, ycg, n=nfl, failed=i) or allocate(R, W, xcg, ycg, n=nfl, failed=i, yaw_free=True)
        if a and (wf is None or a["max_fraction"] > wf[1]["max_fraction"]):
            wf = (i, a)
    if wf:
        i, a = wf
        case(f"R7b one motor out ({R[i]['name']} failed), {nfl:.2f} g flare", a["T"],
             f"highest remaining thrust fraction {a['max_fraction']:.3f} of max_thrust_N")
    # motor torque: peak / fault torque on every rotor at max thrust
    case("R8 motor peak torque (all rotors at max thrust, torque x torque_fault_factor)", Tmax,
         "limit torque = kQ T_max x torque_fault_factor (ESC fault / sudden stop); applied with thrust", torque_factor=ac.get("torque_fault_factor", 1.25))
    # gyroscopic: CS-23.371 rates (yaw 2.5 rad/s, pitch 1.0 rad/s, max continuous rpm). Global case: hover thrust plus
    # the gyroscopic moments; local mount check: max thrust + 2.5 g inertia of the rotor unit + gyro + torque.
    rates = ac.get("gyro_rates", dict(p=1.0, q=1.0, r=2.5))
    for nm, om in (("pitch", (0, rates["q"], 0)), ("roll", (rates["p"], 0, 0)), ("yaw", (0, 0, rates["r"]))):
        gy, mount = [], []
        for r, Th in zip(R, T_hover["T"]):
            spin_axis = np.array(r.get("axis", (0, 0, 1.0))) * r["spin"]
            Om = 2 * math.pi * r["rpm_max"] / 60
            M = np.cross(r["Ip"] * Om * spin_axis, np.array(om, float))      # moment on the mount = H x omega
            gy.append(M.tolist())
            mount.append(dict(rotor=r["name"], F_N=[0.0, 0.0, r["T_max"] - 2.5 * r.get("mass_kg", 0.0) * G0],
                              F_down_N=[0.0, 0.0, -2.5 * r.get("mass_kg", 0.0) * G0],
                              M_Nm=(M + np.array([0, 0, -r["spin"] * r["kQ"] * r["T_max"] * ac.get("torque_fault_factor", 1.25)])).tolist()))
        case(f"R9 gyroscopic, {nm} rate {np.linalg.norm(om):.1f} rad/s, hover thrust", T_hover["T"],
             "CS-23.371(a): yaw 2.5 rad/s, pitch 1.0 rad/s at max rpm; 'mount' lists the local motor-mount check loads "
             "(max thrust or 2.5 g down on the unit, gyro + fault torque)", gyro=gy)
        cases[-1]["mount"] = mount
    cases.append(dict(name="_one_motor_out_table", category="info", table=oei))
    return cases


def pusher_cases(ac: dict) -> list[dict]:
    """Pusher cases (limit): every unit at max thrust with the fault torque and the CS-23.371 gyroscopic moment (yaw 2.5,
    pitch 1.0 rad/s at max rpm), n = 2.5 on the unit inertia for the local mount; and one unit failed (asymmetric thrust)."""
    P = ac.get("pushers") or ([ac["pusher"]] if ac.get("pusher") else [])
    if not P:
        return []
    tf = ac.get("torque_fault_factor", 1.25)
    out = []
    for nm, om in (("yaw 2.5 rad/s", (0, 0, 2.5)), ("pitch 1.0 rad/s", (0, 1.0, 0))):
        gy = []
        for p in P:
            h = p["Ip"] * 2 * math.pi * p["rpm_max"] / 60 * np.array(p.get("axis", (-1.0, 0, 0))) * p["spin"]
            gy.append(np.cross(h, np.array(om, float)).tolist())
        out.append(dict(name=f"P1 pushers max thrust + fault torque + gyroscopic {nm}", category="pusher",
                        thrust_N=[p["T_max"] for p in P], torque_Nm=[p["spin"] * p["kQ"] * p["T_max"] * tf for p in P], gyro_Nm=gy,
                        n_g=2.5, mount_down_N=[2.5 * p.get("mass_kg", 0.0) * G0 for p in P]))
    if len(P) > 1:
        out.append(dict(name="P2 one pusher failed, the other at max thrust (asymmetric)", category="pusher",
                        thrust_N=[P[0]["T_max"]] + [0.0] * (len(P) - 1),
                        torque_Nm=[P[0]["spin"] * P[0]["kQ"] * P[0]["T_max"] * tf] + [0.0] * (len(P) - 1),
                        gyro_Nm=[[0.0, 0.0, 0.0]] * len(P), n_g=1.0))
    return out


# ============================================================================= landing
def landing_cases(ac: dict) -> list[dict]:
    """Gear reactions (limit). n_land = limit vertical inertia factor; the rotors may carry a fraction of W
    (rotor_lift_fraction, default 0 = all reaction through the gear, conservative for gear and its fittings)."""
    W = ac["mtow_kg"] * G0
    n = ac["limits"]["n_land"]
    lf = ac.get("rotor_lift_fraction_landing", 0.0)
    gear = ac["gear"]
    R_tot = (n - lf) * W
    left = [g for g in gear if g["y"] < 0]
    right = [g for g in gear if g["y"] >= 0]
    out = []

    def mk(name, pts, Fz_each, Fx_each=0.0, Fy_each=0.0, note=""):
        return dict(name=name, category="landing", reactions=[dict(point=g["name"], xyz=[g["x"], g["y"], g["z"]],
                    F=[Fx_each(g) if callable(Fx_each) else Fx_each, Fy_each(g) if callable(Fy_each) else Fy_each, Fz_each])
                    for g in pts], inertia_g=n, rotor_lift_N=lf * W, note=note)
    out.append(mk(f"L1 level landing {n:.1f} g, all gear (gear reaction {n - lf:.2f} W)", gear, R_tot / len(gear)))
    out.append(mk(f"L2 level landing {n:.1f} g with drag 0.25 x vertical (inclined reaction)", gear, R_tot / len(gear),
                  Fx_each=0.25 * R_tot / len(gear), note="ground friction / sliding on skids (CS-23.479 style)"))
    out.append(mk(f"L3 one-side landing {n:.1f} g (right skid only, level-landing reactions of that side)", right, R_tot / len(gear),
                  note="CS-23.483: one side contacts the ground with the same reactions as on that side in level landing; "
                       "the unbalanced roll moment is reacted by inertia (roll acceleration)"))
    out.append(dict(name="L4 side load (CS-23.485): n = 1.33 vertical, 0.5 W inboard right / 0.33 W outboard left", category="landing",
                    reactions=[dict(point=g["name"], xyz=[g["x"], g["y"], g["z"]],
                                    F=[0.0, (-0.5 * W / len(right)) if g["y"] >= 0 else (-0.33 * W / len(left)), 1.33 * W / len(gear)])
                               for g in gear], inertia_g=1.33, note="side reactions both towards -y (inboard on the right, outboard on the left)"))
    return out


# ============================================================================= crash
CS23_561 = dict(up=3.0, forward=9.0, side=1.5, down=6.0)
AC23_562 = [dict(test="1 (combined vertical/longitudinal)", dv_ftps=31, peak_g_front_row=19, peak_g_other=15, t_rise_s=0.05,
                 attitude="60 deg pitch down, 0 yaw"),
            dict(test="2 (longitudinal)", dv_ftps=42, peak_g_front_row=26, peak_g_other=21, t_rise_s=0.05,
                 attitude="10 deg yaw, floor warp 10 deg")]


def crash_cases(ac: dict) -> dict:
    """CS-23.561(b) ultimate static inertia factors for every item of mass; items aft of or above the occupants
    use 18 g forward (14 CFR 23.561(e) engine rule, extended by us to battery packs and motors); seats and
    harness attachments x 1.33 (CS-23.785(f)) on top of the occupant + seat inertia."""
    seats = ac.get("seats", [])
    x_seat_max = max((s["x"] for s in seats), default=-1e9)
    z_head = max((s["z"] + 0.9 for s in seats), default=1e9)
    items = []
    for it in ac["items"]:
        aft_above = it.get("aft_or_above_occupants")
        if aft_above is None:
            aft_above = (it["x"] > x_seat_max + 0.1) or (it["z"] > z_head)
        fwd = 18.0 if aft_above else CS23_561["forward"]
        side = CS23_561["side"]
        if "battery" in it["name"].lower() and ac.get("battery_forward_g"):
            fwd, side = max(fwd, ac["battery_forward_g"]), 3 * CS23_561["side"]
        f = dict(forward=[-fwd, 0, 0], up=[0, 0, CS23_561["up"]], down=[0, 0, -CS23_561["down"]],
                 side_right=[0, side, 0], side_left=[0, -side, 0])
        m = it["kg"]
        items.append(dict(name=it["name"], kg=m, xyz=[it["x"], it["y"], it["z"]], aft_or_above=bool(aft_above),
                          ultimate_force_N={k: (np.array(v) * m * G0).tolist() for k, v in f.items()},
                          note="inertia force on the item (direction of the inertia load = opposite to the deceleration)"))
    seat_rows = []
    for s in seats:
        m = s["occupant_kg"] + s.get("seat_kg", 0.0)
        ff = 1.33
        seat_rows.append(dict(name=s["name"], kg=m, xyz=[s["x"], s["y"], s["z"]], fitting_factor=ff,
                              design_force_N={k: (np.array(v) * m * G0 * ff).tolist() for k, v in
                                              dict(forward=[-9.0, 0, 0], up=[0, 0, 3.0], down=[0, 0, -6.0], side=[0, 1.5, 0]).items()},
                              harness_upper_torso_share=0.4, note="occupant + seat; 4-point harness: lap belt 60 %, shoulder straps 40 % of forward load"))
    return dict(category="crash (ultimate)", factors=CS23_561, items=items, seats=seat_rows, dynamic_seat_tests=AC23_562,
                refs=["CS-23.561(b)(2) Amdt 4 factors (normal category)", "14 CFR 23.561(e)(1) 18 g forward for engines aft of the cabin",
                      "CS-23.785(f) seat/harness attachment factor 1.33", "AC 23.562-1 dynamic seat test pulses"])


# ============================================================================= parachute
def parachute_cases(ac: dict) -> list[dict]:
    """Opening-shock cases for the whole-aircraft parachute. n_open (limit, g on MTOW) from the vendor at the
    max deployment speed; default 6 g is a placeholder until the system is chosen."""
    p = ac.get("parachute")
    if not p:
        return []
    W = ac["mtow_kg"] * G0
    F = p.get("opening_load_N") or p.get("n_open_limit", 6.0) * W
    n_open = F / W
    pts = p["attach"]
    share = p.get("max_share", 1.0 / len(pts) * 1.3)      # uneven riser loading (default 30 % over the even share)
    share = min(share, 1.0)
    out = []
    for nm, d in (("aft (deployment along the flight path)", (1.0, 0, 0)), ("aft-up 45 deg", (1, 0, 1)),
                  ("vertical (inflated, low speed)", (0, 0, 1.0)), ("aft-up-right 45/30 deg", (1, 0.6, 1))):
        u = np.array(d, float) / np.linalg.norm(d)
        out.append(dict(name=f"C{len(out) + 1} parachute opening {n_open:.1f} g, {nm}", category="parachute", total_N=F,
                        direction=u.tolist(), per_attachment_N=(u * F * share).tolist(), attach=pts,
                        note=f"total limit {F:.0f} N; each attachment designed for {share:.2f} of the total; x1.5 ultimate, x1.15 fitting"))
    return out


# ============================================================================= placeholder design + CLI
def placeholder_design() -> dict:
    """Representative 700 kg design used to exercise the tool chain before design/geometry.json exists."""
    return json.loads((HERE / "placeholder" / "geometry_placeholder.json").read_text())


def aircraft_from_geometry(geo: dict, sel: dict | None = None) -> dict:
    """Assemble the loads input dictionary from design/geometry.json (+ selected_design.json)."""
    sel = sel or {}
    w = geo["wing"]
    span = w["span"]
    S = w.get("area") or (w["root_chord"] + w["tip_chord"]) / 2 * span
    lam = w["tip_chord"] / w["root_chord"]
    mac = 2 / 3 * w["root_chord"] * (1 + lam + lam**2) / (1 + lam)
    mtow = sel.get("mtow_kg", geo.get("mtow_kg"))
    aero = dict(geo.get("aero", {}), **sel.get("aero", {}))
    from fea.geometry import mass_items, mass_summary
    ms = mass_summary(geo)
    items = [m for m in mass_items(geo) if m["group"] in ("equipment", "rotor", "pusher")]
    x_cg = geo.get("cg", {}).get("x") or ms["cg"][0]
    rotors = []
    for r in geo["rotors"]:
        rotors.append(dict(name=r["name"], x=r["x"], y=r["y"], z=r["z"], spin=r["spin"], T_max=r["max_thrust_N"],
                           kQ=r.get("torque_per_thrust_m", r.get("max_torque_Nm", 0) / r["max_thrust_N"]),
                           rpm_max=r["rpm_max"], Ip=r.get("rotor_inertia_kgm2", 0.0), axis=r.get("axis", (0, 0, 1)),
                           mass_kg=r.get("mass_kg", 0.0)))
    from fea.geometry import pusher_list
    pushers = [dict(name=pu.get("name", f"pusher_{k}"), T_max=pu["max_thrust_N"],
                    kQ=pu.get("torque_per_thrust_m", pu.get("max_torque_Nm", 0) / pu["max_thrust_N"]),
                    rpm_max=pu["rpm_max"], Ip=pu.get("rotor_inertia_kgm2", 0.0), spin=pu.get("spin", 1), axis=pu.get("axis", (-1, 0, 0)),
                    mass_kg=pu.get("mass_kg", 0.0))
               for k, pu in enumerate(pusher_list(geo))]
    pusher = pushers[0] if pushers else None
    req = geo.get("limits", {})
    return dict(
        mtow_kg=mtow, x_cg=x_cg, y_cg=0.0, mass_summary=ms, altitude_m=aero.get("gust_altitude_m", 0.0),
        wing=dict(S=S, span=span, c_root=w["root_chord"], c_tip=w["tip_chord"], mac=mac, CLalpha=aero.get("CLalpha_per_rad", 5.0),
                  CLmax=aero.get("CLmax", 1.4), CLmin=aero.get("CLmin", -0.8), Cm0=aero.get("Cm0", -0.05),
                  x_ac=w["x_le_root"] + span / 6 * (1 + 2 * lam) / (1 + lam) * math.tan(math.radians(w.get("sweep_le_deg", 0.0)))
                  + 0.25 * mac),
        x_ac_tail=geo.get("tail", {}).get("x_ac"),
        speeds=dict(VC=sel.get("cruise_speed_ms") or aero.get("VC_ms"),
                    VD=geo.get("_fea_inputs", {}).get("VD_ms") or aero.get("VD_ms")),
        limits=dict(n_pos=req.get("n_pos", 3.8), n_neg=req.get("n_neg", -1.5), n_land=req.get("n_land", 3.0)),
        rotors=rotors, pusher=pusher, pushers=pushers, gear=geo["landing_gear"], items=items, seats=geo.get("seats", []),
        parachute=geo.get("parachute"), torque_fault_factor=geo.get("torque_fault_factor", 1.25),
        battery_forward_g=geo.get("_fea_inputs", {}).get("battery_forward_g"),
        rotor_lift_fraction_landing=geo.get("_fea_inputs", {}).get("landing", {}).get("rotor_lift_fraction", 0.0),
        oei_flare_g=geo.get("_fea_inputs", {}).get("oei_flare_g", 1.2))


def all_cases(ac: dict) -> dict:
    vn = vn_diagram(ac)
    flight = []
    for dp in vn["design_points"]:
        ll = wing_line_loads(ac, dp["n"], dp["V"])
        flight.append(dict(name=f"F {dp['name']}", category="flight", n=dp["n"], V=dp["V"], line=ll))
    nA = vn["design_points"][0]
    roll = asymmetric_wing(wing_line_loads(ac, 2 / 3 * nA["n"], nA["V"]))
    flight.append(dict(name="F rolling: 2/3 nA, 100 % / 75 % semispan (CS-23.349)", category="flight", n=2 / 3 * nA["n"], V=nA["V"], line=roll))
    return dict(vn=vn, flight=flight, rotor=rotor_cases(ac), pusher=pusher_cases(ac), landing=landing_cases(ac),
                crash=crash_cases(ac), parachute=parachute_cases(ac))


def _summary(c):
    vn = c["vn"]
    print(f"W/S {vn['wing_loading_Pa']:.0f} Pa  VS1 {vn['VS1']:.1f}  VA {vn['VA']:.1f}  VC {vn['VC']:.1f} (CS-23 min {vn['VC_min_cs23']:.1f})"
          f"  VD {vn['VD']:.1f} m/s EAS;  mu_g {vn['mu_g']:.1f} k_g {vn['k_g']:.3f}  gust n at VC {vn['gust_VC'][0]:.2f}/{vn['gust_VC'][1]:.2f}"
          f"  n_max {vn['n_max']:.2f} n_min {vn['n_min']:.2f}")
    for f in c["flight"]:
        print(f"  {f['name']:52s} n {f['n']:5.2f}  Lw {f['line']['L_wing']:8.0f} N  Lt {f['line']['L_tail']:7.0f} N  "
              f"root M(half) {f['line']['root_moment_half']:8.0f} N m")
    for r in c["rotor"]:
        if r["category"] == "info":
            print("  one-motor-out max thrust fractions (1.0 g / 1.2 g):",
                  [(x["failed"], round(x["max_fraction_1.0g"] or -1, 3), round(x["max_fraction_1.2g"] or -1, 3)) for x in r["table"]])
            continue
        print(f"  {r['name']:70s} sumT/W {r['net_vertical_g']:.2f}  max frac {max(r['thrust_fraction']):.2f}")
    for r in c["landing"] + c["parachute"] + c["pusher"]:
        print("  ", r["name"])
    print(f"  crash items: {len(c['crash']['items'])}, seats {len(c['crash']['seats'])}")


def main():
    if len(sys.argv) > 1:
        from fea.geometry import load as gload
        geo = gload(sys.argv[1])
        sel = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else None
    else:
        geo, sel = placeholder_design(), None
    ac = aircraft_from_geometry(geo, sel)
    c = all_cases(ac)
    _summary(c)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    tag = "placeholder" if len(sys.argv) == 1 else "design"
    (out / f"loads_{tag}.json").write_text(json.dumps(c, indent=1, default=float))


if __name__ == "__main__":
    main()
