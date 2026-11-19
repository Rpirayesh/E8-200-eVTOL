"""Vectorised closure model of the E8-200 lift + cruise eVTOL (work package D).

``evaluate(X, cfg)`` sizes N candidate designs at once.  X holds equal-length arrays of design variables; cfg holds
scalars shared by the batch (rotor configuration, seating, design range, assumption overrides).  For each design the
model lays out the aircraft (rotor stations about the CG, wing for a 10 % static margin, tail from volume
coefficients, footprint), closes MTOW = empty + battery + payload by fixed-point iteration with the battery chosen as
an integer series x parallel x packs layout of catalog cells, evaluates every requirement as a normalised constraint
g <= 0, and returns acquisition cost and the complexity-penalised objective.

Equation tags: methods/EQUATIONS.md.  Sources: resources/README.md ids.
"""
from __future__ import annotations

import numpy as np

from . import data as D
from . import physics as ph
from .airfoils import load as load_airfoils
from .calibration import load as load_calibration
from .cost import airframe_cost

G0 = ph.G0

# ------------------------------------------------------------------------------------------------ assumptions
A0 = dict(
    payload_kg=200.0, occupant_kg=100.0,
    kappa=1.20, cd0_blade=0.015,            # [H2] RA01 / EQUATIONS sec. 0
    ct_sigma=0.12,                          # [H5] hover blade loading at the 1000 m ceiling
    f_dl0=0.02,                             # download of booms/pylons/fuselage in the wake (estimate, see README)
    k_overlap=1.0,                          # download / thrust per unit (lifting-surface area under disc / disc area), RA03
    k_ctrl=0.10,                            # [H6] control thrust margin on the most loaded rotor
    eta_m=0.93, eta_inv=0.97, eta_w=0.98,   # EQUATIONS sec. 0; catalog motor peaks 0.93-0.96
    aux_kw=1.5,                             # avionics, pumps, fans (estimate, = WP M default)
    f_eol=0.80, f_res=0.20, dC=0.3,         # requirements.yaml mission.reserve
    dcir_eol_factor=1.5,                    # cell resistance growth to end of life (estimate; BT08 order)
    f_ovh=0.25,                             # [B2] pack non-cell mass fraction: CAD packs + unmodelled items 0.22
                                            # (design/mass_calibration.json), 0.25 adopted (= WP M light); iteration 1 used 0.30
    growth=0.05,                            # empty-mass growth allowance
    tf_struct=0.85,                         # composite factor on Raymer GA structure, AE01 table 15.4
    cd_motor_bell=0.35,                     # stopped motor bell inside a printed spinner/pylon fairing (HOE ch. 3 short
                                            # streamlined body 0.1-0.2; 0.35 kept for the rotor-hub gap); bare bell 0.8 [D7]
    k_exc=1.10, lam_wing=0.10, lam_body=0.05,  # [D2], [D9]
    gap_rotor=0.10,                         # tip clearance rotor-rotor and rotor-wing/tail edge (m)
    gap_fus=0.15,                           # rotor tip to fuselage side (m)
    pylon_h=0.55,                           # boom centre to rotor plane (m); design_out raises it if the burst-fan / wing
                                            # clearance needs more (iteration 2: 0.55 m)
    pylon_fair_t=0.116, pylon_fair_c=0.40,  # fairing over the WP F 100 x 1.6 mm pylon tube (t/c 0.29)
    cd_pylon=0.07,                          # streamline strut t/c ~0.3, C_D on frontal area (AE04 Hoerner ch. 6)
    nacelle_frontal=0.030, cd_nacelle=0.12, # under-boom inverter pod INV-POD (460 x 147 x 270 mm, WP G iteration 3), C_D on
                                            # frontal area of a fineness-2.3 faired body (AE04, estimate); build-up increment
    boom_od=0.11,                           # COTS 4 in ID tube (MAT-TUBE-DP-4x96) + in-house UD over-wrap
    boom_sigma=300e6, boom_tmin=0.0016, cfrp_rho=1550.0,
    boom_r_wrap=0.056,                      # boom outer radius at the WP F over-wrap (OD 112 mm), for exposed tail spans
    x_spar_f=0.20, x_spar_r=0.70,           # main (box) and rear (hinge) spar: iteration 2 moved them apart (0.25/0.65 ->
                                            # 0.20/0.70) so that the passenger door between the spar posts is >= 0.483 m wide
    door_min_w=0.483, post_w=0.04,          # 14 CFR 23.807 exit 19 x 26 in; spar posts 40 mm each side (WP G)
    oei_cg_allowance=0.005,                 # rotor-out thrust allowance for the CG travel of the loading cases
    oei_flare_g=1.10,                       # iteration 3.2 relaxation (was 1.20)                       # one motor out: 1.2 g vertical capability at MTOW, 500 m ISA+15 (flare / arrest
                                            # of the descent; iteration-2 project requirement after WP F found 103 %)
    fus_e=4.0,                              # fuselage super-ellipse exponent (iteration 2: boxier cabin so packs, root
                                            # fittings and the pusher motor fit inside the OML; iteration 1: 2.5)
    eta_b_cap=0.95,                         # battery efficiency taken as min(I2R estimate, WP M screening value)
    sm_target=0.10, Vh=0.50, Vv=0.04,       # AE01 table 6.4 (home-built 0.50 / 0.04)
    eta_h=0.90, K_fus=0.012,                # tail efficiency; Raymer fig. 16.14 fuselage factor (estimate)
    tail_tc=0.14, ARv=1.5,                  # iteration 3.1: NACA 0014 H-tail so the WP F 50 mm spar fits (fins NACA 0012)
    Nz=5.7, n_land=3.0,
    cruise_alt=500.0, site_alt=500.0, ceil_alt=1000.0, dT=15.0, transition_alt=30.0,
    t_hover_to=60.0, t_hover_ld=60.0, t_tr=30.0, h_vclimb=30.0,
    roc_min=1.0,                            # climb rate with pusher peak power at 500 m ISA+15 (stated assumption: 500 m in < 8 min)
    mach_tip_flare_max=0.70,                # one-motor-out flare (< 5 s transient): [H7] compressibility screen 0.70 (as for
                                            # the pusher); the 0.65 noise/compressibility screen stays for continued OEI hover
    pusher_rpm=None,                        # None: rpm from pusher_tip_static; else fixed pusher rpm
    pusher_tip_static=190.0, mach_helical_max=0.70, mach_tip_hover_max=0.55, mach_tip_oei_max=0.65,
    L_max=10.5,                             # iteration 3.2 relaxation (was 9.0): trailer with the wing removed
    stall_factor=1.15,                      # iteration 3.2 relaxation (was 1.30): V_cruise >= 1.15 Vs hot, flaps down
    hub_fairing_kg=0.0, hub_fairing_usd=0.0,   # per lift station when the hub fairings are fitted (set with cfd_rotor_dq_factor)
    flap_dcl=0.9, flap_span_frac=0.45,      # plain flap, AE01 table 12.2; inboard of 60 % semispan, split at the boom
                                            # (2 x 90 mm gap, WP G): 0.47 x (1 - 0.09/2.07)
    clmax_3d_factor=0.90,                   # CLmax = 0.9 clmax (AE01 eq. 12.15)
    coax_kint=1.28,                         # coaxial induced-power factor vs two isolated rotors, RA01 ch. 2
    lambda_type=5000.0, lambda_part=500.0,  # complexity penalty USD per distinct part type / per propulsion LRU
    labour_rate=55.0,                       # USD/h burdened shop rate (parameter)
    pack_per_cell_kg=0.01594, pack_fixed_kg=5.107,   # iteration 3.3: two-point fit to the 3.1 and 3.2 CAD packs (was 0.0262 / 3.44)
    battery_model="cad",                    # "cad" (per cell + per pack, 3.2) or "fraction" (cells / (1 - f_ovh), <= 3.1)
    calibration_path=None,                  # None: design/mass_calibration.json; else a frozen copy (e.g. design/iteration31/)
    aero="cfd",                             # "cfd": drag, Oswald, CLmax, flap and download calibrated to WP C phase 2 (3.1
                                            # geometry, cfd/results/README.md); "buildup": iterations 1-3.1 handbook build-up
    cfd_rotor_dq_factor=0.263 / 0.1726,     # stopped rotors + hubs + pylons + pods: CFD 0.263 m2 vs build-up 0.1726 m2 at 3.1
    cfd_k_exc=1.081,                        # residual factor on the other components so CD0 = 0.0704 at the 3.1 geometry
    cfd_wing_interference=0.075,            # m2, wing/boom/fuselage interference (CFD)
    cfd_gear_dq=0.090,                      # m2 (CFD)
    cfd_thrust_deduction=0.019,             # iteration 3.3 CFD, boom-tail pushers on/off (was 0.045, tail-cone pusher CFD 3.1)
    cfd_wake_fraction=0.045,                # iteration 3.3 CFD, mean axial inflow 0.955 V at the pusher disks (pushers off)
    # iteration 3.3 CFD calibration of the 3.3 geometry (cfd/results/iteration33/summary.json), on top of the 3.1 factors:
    cfd33_cd0_factor=0.07643 / 0.07508,     # CD0 incl. pods 0.0764 vs build-up 0.0751
    cfd33_e_factor=0.6579 / 0.7560,         # Oswald e 0.658 vs 0.756
    cfd33_clmax_factor=0.95 * 1.7136 / 1.5193,   # clean CLmax: CFD 1.714 (not bracketed) - 5 % band = 1.628 (< 1.64)
    cfd33_download_add=0.0200 - 0.0332,     # corrected hover download 2.0 % vs 3.32 %
    cfd_e_factor=0.734 / 0.816, cfd_clmax_factor=1.52 / 1.64,   # Oswald, clean CLmax (CFD / build-up at 3.1)
    cfd_flap_factor=0.18 / 0.3645,          # flap increment CFD (30 % plain flap at 35 deg: 1.70 - 1.52) / build-up
    cfd_download_add=0.008,                 # CFD hover download 5.5 % (corrected) vs 4.7 % build-up
    flap_types=(0.0, 0.9, 1.3, 1.5),        # none, plain, single-slotted, Fowler (c'/c 1.15): dcl_max, AE01 table 12.2
    flap_extra_kg=(0.0, 0.0, 2.0, 5.0), flap_extra_usd=(0.0, 1000.0, 2500.0, 5000.0),   # tracks/vanes, estimates
    reb90_cont_kw=60.0,                     # REB 90 continuous: catalog 60-70 kW; lower bound unless the MGM quote confirms 70
    v_ocv_low=3.45, v_ocv_mid=3.60,         # mid-SOC open-circuit voltage (P50B nominal)
    battery_sag="exact",                    # "exact" quadratic I-R sag (iteration 3.3) or "linear" (I = P / V_nom, up to 3.2)                         # cell open-circuit voltage at the landing reserve (low SOC), WP P estimate
    bus_v_min=400.0,
    ns_min_800=175,                         # 175 x (3.45 - 60 A x 19.2 mOhm) = 402 V: keeps the bus >= 400 V at the cell limit                        # minimum bus voltage under load: REB 60/90 and HBCi winding class 400-800 V
    pusher_margin=0.10,
    reb60_rating="summary",                 # "summary" (60 kW / 250 N m, 36 kW cont. estimate) or "table" (MGM 25 C table)
    pusher_pod_ahead_of_tail=0.30,          # iteration 3.3: twin-pusher inverter pod centre ahead of the tail leading edge
    twin_prop_plane=0.15, twin_lift_clear=0.10,   # prop plane behind the boom end; plan gap prop plane to rear lift-disc edge
    twin_pusher_overhang=0.35,              # motor 0.09 + mount plate 0.06 + hub/spinner 0.20 behind the boom end (estimate)
    twin_cowl_swet=0.30,                    # tail-cone REB 90 cowl wetted area removed with twin pushers (0.32 m square x 0.30 m)
    pusher_feeder_single=3.0,               # bus-to-tail-cone pusher feeder length inside the calibration (estimate)                     # iteration 3.1: >= 10 % margin on the pusher continuous rating in cruise
    hv_conductor="al",                      # iteration 3: aluminium HV feeders (half the copper mass at equal resistance)
    N_units=10, f_comp=0.8, f_cert=0.5,
)

SEATING = {
    # width, height, length, x of seat 1 and seat 2 occupant CG from the nose, cabin floor z
    "tandem": dict(w=0.92, h=1.50, L=4.70, x_seat=(1.15, 2.05), y_seat=(0.0, 0.0)),
    "side": dict(w=1.28, h=1.50, L=4.40, x_seat=(1.35, 1.35), y_seat=(-0.30, 0.30)),
}
FUS_Z_AXIS = 1.08            # fuselage centre-line height above ground (skid bottom z = 0)


def fuselage_stations(seating: str):
    s = SEATING[seating]
    L, w, h = s["L"], s["w"], s["h"]
    # (x/L, w/w_max, h/h_max, z_centre)
    tpl = [(0.0, 0.0, 0.0, 0.98), (0.025, 0.45, 0.42, 0.97), (0.10, 0.80, 0.72, 1.01), (0.20, 1.0, 0.95, 1.08),
           (0.40, 1.0, 1.0, 1.10), (0.60, 1.0, 0.99, 1.11), (0.75, 0.78, 0.74, 1.16), (0.90, 0.42, 0.40, 1.16),
           (0.985, 0.22, 0.22, 1.15), (1.0, 0.0, 0.0, 1.15)]
    return [dict(x=round(f * L, 4), width=round(a * w, 4), height=round(b * h, 4), z_center=zc) for f, a, b, zc in tpl]


def fuselage_wetted(seating: str, e=4.0, stations=None):
    st = stations or fuselage_stations(seating)
    x = np.array([s["x"] for s in st])
    per = np.array([float(ph.superellipse_perimeter(s["width"], s["height"], e)) for s in st])
    return float(np.trapezoid(per, x))


def _take(lst, idx, key):
    return np.array([o[key] if o[key] is not None else np.nan for o in lst], float)[np.asarray(idx, int)]


# ------------------------------------------------------------------------------------------------ main model
def evaluate(X: dict, cfg: dict) -> dict:
    A = dict(A0, **cfg.get("assumptions", {}))
    CAL = load_calibration(A.get("calibration_path"))
    CF = dict(CAL["factors"], **A.get("cal_factors", {}))
    CX = dict(CAL["fixed_kg"], **A.get("cal_fixed", {}))
    n = int(cfg["n_rot"])
    coax = bool(cfg.get("coax", False))
    seating = cfg.get("seating", "tandem")
    rng_req = float(cfg["range_km"])
    N = len(np.atleast_1d(X["D"]))
    bc = lambda v: np.broadcast_to(np.asarray(v, float), (N,)).copy()
    Dr, vtip, nb, span, chord, V, Dp, dw = (bc(X[k]) for k in ("D", "vtip", "nb", "span", "chord", "V", "Dp", "delta_w"))
    flap = bc(X.get("flap", 0.0))
    lm, pm, ci, npk, afi = (np.broadcast_to(np.asarray(X[k], int), (N,)) for k in ("lm", "pm", "cell", "npk", "airfoil"))
    npk_f = npk.astype(float)

    # ---------------- atmosphere
    site, ceil, cr, sl = ph.isa(A["site_alt"], A["dT"]), ph.isa(A["ceil_alt"], A["dT"]), ph.isa(A["cruise_alt"], A["dT"]), ph.isa(0.0)
    eta_d = A["eta_m"] * A["eta_inv"] * A["eta_w"]

    # ---------------- parts
    LM, PM, CE = D.LIFT_MOTORS, D.PUSHER_MOTORS, D.CELLS
    m_mot, P_pk, P_ct, Q_mx = (_take(LM, lm, k) for k in ("mass_kg", "peak_kw", "cont_kw", "torque_nm"))
    rpm_lo, rpm_hi, vcl = _take(LM, lm, "rpm_min"), _take(LM, lm, "rpm_max"), _take(LM, lm, "vclass")
    mot_d, mot_h = _take(LM, lm, "diameter_m"), _take(LM, lm, "exposed_height_m")
    pr_mot = _take(LM, lm, "price_usd")
    inv_id = np.array([o["inverter"] for o in LM])[lm]
    INV = D.INVERTERS
    m_inv = np.array([INV[i]["mass_kg"] for i in inv_id])
    pr_inv = np.array([INV[i]["price_usd"] for i in inv_id])
    inv_vmax = np.array([INV[i]["v_max"] for i in inv_id])
    inv_icont = np.array([INV[i]["i_cont"] for i in inv_id])
    inv_ipk = np.array([INV[i]["i_peak"] for i in inv_id])
    pm_mass, pm_pk, pm_ct, pm_q = (_take(PM, pm, k) for k in ("mass_kg", "peak_kw", "cont_kw", "torque_nm"))
    pm_qc = np.array([o["torque_cont_nm"] if o["torque_cont_nm"] else np.inf for o in PM])[pm]
    pm_rpm_hi, pm_vcl, pr_pm = _take(PM, pm, "rpm_max"), _take(PM, pm, "vclass"), _take(PM, pm, "price_usd")
    pm_id = np.array([o["id"] for o in PM])[pm]
    twin = np.array([o.get("twin", 0) for o in PM], float)[pm] > 0.5      # two boom-tail pushers (iteration 3.2 option)
    n_push = np.where(twin, 2.0, 1.0)
    if A["reb60_rating"] == "table":
        r6p = pm_id == "MOT-REB60"
        T6 = D.REB60_TABLE
        pm_pk, pm_ct = np.where(r6p, n_push * T6["peak_kw"], pm_pk), np.where(r6p, n_push * T6["cont_kw"], pm_ct)
        pm_q, pm_qc = np.where(r6p, n_push * T6["torque_nm"], pm_q), np.where(r6p, n_push * T6["torque_cont_nm"], pm_qc)
    lm_id = np.array([o["id"] for o in LM])[lm]
    Qc_lift = np.array([o.get("torque_cont_nm") or np.inf for o in LM])[lm]
    if A["reb60_rating"] == "table":     # MGM detailed table (25 C) instead of the summary block, every REB 60
        T6 = D.REB60_TABLE
        r6 = lm_id == "MOT-REB60"
        P_pk, P_ct = np.where(r6, T6["peak_kw"], P_pk), np.where(r6, T6["cont_kw"], P_ct)
        Q_mx, Qc_lift = np.where(r6, T6["torque_nm"], Q_mx), np.where(r6, T6["torque_cont_nm"], Qc_lift)
    c_wh, c_kg, c_ah, c_vn, c_ic, c_ip, c_r, c_pr = (_take(CE, ci, k) for k in
                                                   ("energy_wh", "mass_kg", "capacity_ah", "v_nom", "i_cont_screen", "i_peak", "dcir_ohm", "price_usd"))
    AF = load_airfoils()
    afn = list(AF)
    af_tc = np.array([AF[k]["t_c"] for k in afn])[afi]
    af_xt = np.array([AF[k]["x_t_c"] for k in afn])[afi]
    af_clmax = np.array([AF[k]["cl_max"] for k in afn])[afi]

    # bus voltage class: 800 V parts need the 800 V bus; the pusher on a 400 V bus must be an EMRAX (MV winding)
    bus800 = vcl > 500
    lv_wind = _take(LM, lm, "lv_winding") > 0.5
    ns_max = np.minimum(D.ORION_MAX_SERIES, np.floor(inv_vmax * 0.98 / 4.2))
    ns_min = np.where(bus800, A["ns_min_800"], np.where(lv_wind, 70.0, 40.0))   # 800 V class: >= 400 V under load at 60 A, EOL
    # pusher on a 400 V bus: EMRAX (MV winding) or, with the LV-winding option, the REB family on its LV winding
    pusher_bus_ok = bus800 | lv_wind | np.char.startswith(pm_id.astype(str), "MOT-EMRAX")

    # ---------------- geometry (x relative to the CG at MTOW, which is put on the rotor centroid)
    fus = SEATING[seating]
    wf, hf, Lf = fus["w"], fus["h"], fus["L"]
    R = Dr / 2
    S = span * chord
    AR = span / chord
    b_y = wf / 2 + R + A["gap_fus"]
    a_w = ph.helmbold(AR)
    deps = 2 * a_w / (np.pi * AR)
    n_disk = n // 2 if coax else n
    per_boom = n_disk // 2
    pitch = Dr + A["gap_rotor"]
    # neutral point (fraction of chord from the LE) with tail volume Vh: hn = 0.25 + eta Vh at/aw (1-deps) - dfus
    # first guess for the tail aspect ratio, refined below
    ARh = np.full(N, 5.0)
    Lb_guess = 8.5
    c_v = np.full(N, 0.6)
    for _ in range(4):
        a_t = ph.helmbold(ARh)
        dfus = A["K_fus"] * 57.3 * (wf**2 * Lf + 2 * A["boom_od"] ** 2 * Lb_guess) / (S * chord * a_w)
        hn = 0.25 + A["eta_h"] * A["Vh"] * a_t / a_w * (1 - deps) - dfus
        x_le = -(hn - A["sm_target"]) * chord
        x_te = x_le + chord
        if per_boom == 4:       # two rotors per boom fore and two aft of the wing
            a_in = np.maximum(-x_le, x_te) + R + A["gap_rotor"] - dw
            xr = np.stack([-(a_in + pitch), -a_in, a_in, a_in + pitch], axis=1)
        elif per_boom == 3:     # 6 rotors: one per boom above the wing
            a_in = np.maximum(-x_le, x_te) + R + A["gap_rotor"] - dw
            a_in = np.maximum(a_in, pitch)
            xr = np.stack([-a_in, np.zeros(N), a_in], axis=1)
        else:                   # 4 stations (4 single rotors or 4 coaxial pairs)
            a_in = np.maximum(-x_le, x_te) + R + A["gap_rotor"] - dw
            xr = np.stack([-a_in, a_in], axis=1)
        x_front, x_rear = xr[:, 0], xr[:, -1]
        # tail: LE behind the rearmost disc, pulled forward under the disc only as far as the footprint requires
        S_h_guess = A["Vh"] * S * chord / np.maximum(x_rear + R - x_le, 1.0)
        span_h = 2 * (b_y - A["boom_r_wrap"])        # exposed H-tail span between the boom surfaces (S_h is exposed area)
        c_h = np.maximum(S_h_guess / span_h, 0.30)
        x_tle_free = x_rear + R + A["gap_rotor"]
        L_free = (np.maximum(x_tle_free + np.maximum(c_h, c_v) + np.where(twin, 0.10, 0.05), np.where(twin, x_rear + R + A["twin_lift_clear"] - A["twin_prop_plane"], 0.0))
                  + np.where(twin, A["twin_pusher_overhang"], 0.0) - (x_front - R))
        d_t = np.maximum(L_free - A["L_max"], 0.0)
        x_tle = x_tle_free - d_t
        l_t = (x_tle + 0.25 * c_h) - (x_le + 0.25 * chord)
        S_h = A["Vh"] * S * chord / l_t
        c_h = np.maximum(S_h / span_h, 0.30)
        S_h = c_h * span_h
        ARh = span_h / c_h
        Lb_guess = np.mean(x_tle + c_h + 0.05 - (x_front - 0.15))
        # twin ventral fins under the booms (they may sit under the rear discs without download or blade clearance issues)
        S_v = A["Vv"] * S * span / l_t
        h_v = np.sqrt(A["ARv"] * S_v / 2)
        c_v = S_v / 2 / h_v
    boom_x0 = x_front - 0.15
    boom_x1 = np.maximum(x_tle + np.maximum(c_h, c_v) + np.where(twin, 0.10, 0.05), x_rear + 0.15)   # twin: 0.25 m tail TE to prop plane
    # twin pushers: the prop plane (boom end + twin_prop_plane) sits behind the rear lift-rotor disc, because the pusher disc
    # (radius > pylon height) would otherwise cross the lift-rotor blade plane
    boom_x1 = np.where(twin, np.maximum(boom_x1, x_rear + R + A["twin_lift_clear"] - A["twin_prop_plane"]), boom_x1)
    L_boom = boom_x1 - boom_x0
    length_overall = np.maximum(np.where(twin, boom_x1 + A["twin_pusher_overhang"], boom_x1), x_rear + R) - (x_front - R)
    width_overall = np.maximum(2 * b_y + Dr, span)
    # lifting surface under the discs (download)
    A_disc = n_disk * np.pi * R**2
    ov = np.zeros(N)
    for j in range(xr.shape[1]):
        ov += 2 * ph.disc_strip_area(R, xr[:, j], x_le, x_te)                    # wing, both booms
    ov += 2 * 0.5 * ph.disc_strip_area(R, x_rear, x_tle, x_tle + c_h)            # H-tail, inner half of the rear discs
    f_dl = A["f_dl0"] + A["k_overlap"] * ov / A_disc + (A["cfd_download_add"] + A["cfd33_download_add"] if A["aero"] == "cfd" else 0.0)
    # fuselage
    swet_f = A.get("swet_f") or fuselage_wetted(seating, A["fus_e"])
    if not A.get("swet_f"):           # an OML from the layout (design_out) already has no cowl for twin pushers
        swet_f = swet_f - np.where(twin, A["twin_cowl_swet"], 0.0)   # twin pushers: no tail-cone motor cowl
    wf, hf, Lf = A.get("fus_w", wf), A.get("fus_h", hf), A.get("fus_L", Lf)
    # wing aero
    e_os = ph.oswald_raymer(AR) * (A["cfd_e_factor"] * A["cfd33_e_factor"] if A["aero"] == "cfd" else 1.0)
    fl_i = np.clip(flap.astype(int), 0, 3)
    flap_dcl = np.array(A["flap_types"])[fl_i]
    has_flap = (fl_i > 0).astype(float)
    if A["aero"] == "cfd":
        CLmax = (A["cfd_clmax_factor"] * A["clmax_3d_factor"] * af_clmax
                 + A["cfd_flap_factor"] * 0.9 * flap_dcl * A["flap_span_frac"]) * A["cfd33_clmax_factor"]
    else:
        CLmax = A["clmax_3d_factor"] * af_clmax + 0.9 * flap_dcl * A["flap_span_frac"]

    # ---------------- drag area [D1]-[D9] (independent of mass)
    Mc = V / cr["a"]
    q = 0.5 * cr["rho"] * V**2
    Re = lambda L: cr["rho"] * V * L / cr["mu"]
    s_exp = S - wf * chord
    dq = {}
    dq["wing"] = ph.cf_mixed(Re(chord), Mc, A["lam_wing"]) * ph.ff_wing(af_tc, af_xt, Mc) * s_exp * (1.977 + 0.52 * af_tc)
    deq = np.sqrt(wf * hf)
    dq["fuselage"] = ph.cf_mixed(Re(Lf), Mc, A["lam_body"]) * ph.ff_body(Lf / deq) * swet_f
    dq["booms"] = 2 * ph.cf_mixed(Re(L_boom), Mc, A["lam_body"]) * ph.ff_body(L_boom / A["boom_od"]) * 1.1 * np.pi * A["boom_od"] * L_boom * 0.95
    dq["tail_h"] = ph.cf_mixed(Re(c_h), Mc, A["lam_wing"]) * ph.ff_wing(A["tail_tc"], 0.30, Mc) * 1.04 * S_h * (1.977 + 0.52 * A["tail_tc"])
    dq["tail_v"] = ph.cf_mixed(Re(c_v), Mc, A["lam_wing"]) * ph.ff_wing(A["tail_tc"], 0.30, Mc) * 1.04 * S_v * (1.977 + 0.52 * A["tail_tc"])
    # stopped rotors [D7]: motor bell, faired pylon (0.05 m thick), parked blades aligned with the flow
    sigma_guess = 0.10
    c_bl_guess = sigma_guess * np.pi * R / nb
    blades = nb * ph.cf_mixed(Re(c_bl_guess), Mc, 0.1) * 1.3 * 2 * R * c_bl_guess * 0.9
    dq["stopped_rotors"] = n * (0.8 * mot_d * mot_h + blades) + n_disk * 0.3 * (A["pylon_h"] * 0.05)
    dq["landing_gear"] = 2 * 1.5 * 0.076 * 0.40 + 0.01          # faired cross tubes (C_D 0.4 on frontal, HOE) + skid ends
    dq["cooling_inlets"] = 0.01
    # twin pushers: inverter pod on each boom tail + motor/spinner step from the 0.10 m boom to the 0.27 m motor (C_D 0.10, estimate)
    # iteration 3.3: C_D 0.15 on the 0.27 m motor frontal area for the motor step and again for the inverter pod (same basis as
    # the independent V&V build-up; replaces the 3.2 estimate of 0.017 m2 for both units)
    dq["pusher_pods"] = np.where(twin, 2 * 2 * 0.15 * np.pi / 4 * 0.27**2, 0.0)
    dq_sum = sum(dq.values())
    dq_total = dq_sum * A["k_exc"]
    CD0 = dq_total / S

    # pusher
    rpm_p = A["pusher_tip_static"] * 60 / (np.pi * Dp)
    if A.get("pusher_rpm"):          # fixed pusher rpm (iteration 3.2: 1,550 rpm, clear of the boom/wing modes, FEA)
        rpm_p = np.full_like(np.asarray(Dp, float), A["pusher_rpm"])
    tip_p = rpm_p * np.pi * Dp / 60
    om_p = rpm_p * 2 * np.pi / 60
    mach_hel = np.sqrt(tip_p ** 2 + V**2) / cr["a"]
    pm_ct = np.where(np.char.startswith(pm_id.astype(str), "MOT-REB90"), n_push * A["reb90_cont_kw"], pm_ct)
    pm_pcont = np.minimum(pm_ct, pm_qc * om_p / 1e3)
    pm_ppeak = np.minimum(pm_pk, pm_q * om_p / 1e3)
    pp_idx = np.where(Dp <= D.PUSHER_PROPS[0]["d_max"], 0, 1)
    nb_p = np.broadcast_to(np.asarray(X.get("pnb", 3), float), (N,))
    two = nb_p < 2.5
    m_pprop = np.where(pp_idx == 0, np.where(two, D.PUSHER_PROPS[0]["mass2"], D.PUSHER_PROPS[0]["mass3"]),
                       nb_p * D.blade_mass_kg(Dp) * 0.8 + 1.5)
    pr_pprop = np.where(pp_idx == 0, np.where(two, D.PUSHER_PROPS[0]["price2"], D.PUSHER_PROPS[0]["price3"]),
                        np.where(two, D.PUSHER_PROPS[1]["price2"], D.PUSHER_PROPS[1]["price3"]))

    # lift prop supplier by diameter
    lp_dmax = np.array([p["d_max"] for p in D.LIFT_PROPS])
    lp_idx = np.searchsorted(lp_dmax, Dr - 1e-9)
    prop_ok = lp_idx < len(lp_dmax)
    lp_idx = np.minimum(lp_idx, len(lp_dmax) - 1)
    pr_lprop = np.array([p["price_usd"] for p in D.LIFT_PROPS])[lp_idx] * np.where(nb > 2.5, 1.4, 1.0)
    m_lprop = 2 * D.blade_mass_kg(Dr) + D.PROP_HUB_KG + np.where(nb > 2.5, 0.3, 0.0)

    # ---------------- mass closure
    m = np.full(N, 950.0)
    cells = np.full(N, 2700.0)
    fixed = np.zeros(N, bool)
    ns_sel = np.full(N, 150.0)
    np_sel = np.full(N, 8.0)
    out = {}
    for it in range(70):
        W = m * G0
        # hover per disc
        T_disc = W * (1 + f_dl) / n_disk
        A1 = np.pi * R**2
        if coax:
            T_rot = T_disc / 2
            sigma = ph.solidity_for_blade_loading(T_rot, Dr, ceil["rho"], vtip, A["ct_sigma"])

            def p_disc(T, rho, vt=vtip):
                pi_ = (T / 2) ** 1.5 / np.sqrt(2 * rho * A1)
                return A["kappa"] * A["coax_kint"] * 2 * pi_ + 2 * sigma * A["cd0_blade"] * rho * A1 * vt**3 / 8
        else:
            T_rot = T_disc
            sigma = ph.solidity_for_blade_loading(T_rot, Dr, ceil["rho"], vtip, A["ct_sigma"])

            def p_disc(T, rho, vt=vtip):
                return ph.rotor_power(T, Dr, rho, vt, sigma, A["kappa"], A["cd0_blade"])[0]
        P_disc_site = p_disc(T_disc, site["rho"])
        P_disc_ceil = p_disc(T_disc, ceil["rho"])
        P_mot_site = P_disc_site / (2 if coax else 1)
        P_mot_ceil = P_disc_ceil / (2 if coax else 1)
        P_h_site = n_disk * P_disc_site / eta_d / 1e3 + A["aux_kw"]
        P_h_ceil = n_disk * P_disc_ceil / eta_d / 1e3 + A["aux_kw"]
        omega = vtip / R
        rpm_h = omega * 60 / (2 * np.pi)
        # one motor out [H6], screening factor n/(n-2) (rows for coax), at the 1000 m ceiling, + control margin
        F_oei = n / (n - 2.0) if n > 4 else 2.0     # 4 rotors cannot trim (g["oei_trim"]); 2.0 only keeps numbers finite
        F_oei = F_oei * (1 + A["oei_cg_allowance"])  # CG travel between loading cases (LP: +0.3 % for pilot + cargo)
        r_T = F_oei * (1 + A["k_ctrl"])
        T_ro = T_rot * r_T
        r_w = np.sqrt(r_T)                                  # fixed pitch: T ~ rpm^2
        if coax:
            P_ro = (A["kappa"] * A["coax_kint"] * T_ro**1.5 / np.sqrt(2 * ceil["rho"] * A1)
                    + sigma * A["cd0_blade"] * ceil["rho"] * A1 * (vtip * r_w) ** 3 / 8)
        else:
            P_ro = ph.rotor_power(T_ro, Dr, ceil["rho"], vtip * r_w, sigma, A["kappa"], A["cd0_blade"])[0]
        Q_ro = P_ro / (omega * r_w)
        # one motor out, 1.2 g flare at the 500 m ISA+15 site (no extra control margin: the 0.2 g is the manoeuvre)
        r_Tf = F_oei * A["oei_flare_g"]
        T_fl = T_rot * r_Tf
        r_wf = np.sqrt(r_Tf)
        if coax:
            P_fl = (A["kappa"] * A["coax_kint"] * T_fl**1.5 / np.sqrt(2 * site["rho"] * A1)
                    + sigma * A["cd0_blade"] * site["rho"] * A1 * (vtip * r_wf) ** 3 / 8)
        else:
            P_fl = ph.rotor_power(T_fl, Dr, site["rho"], vtip * r_wf, sigma, A["kappa"], A["cd0_blade"])[0]
        Q_fl = P_fl / (omega * r_wf)
        # parked-blade drag with the current blade chord [D7]
        c_bl = sigma * np.pi * R / nb
        blades = nb * ph.cf_mixed(Re(c_bl), Mc, 0.1) * 1.3 * 2 * R * c_bl * 0.9
        dq["stopped_rotors"] = (n * (A["cd_motor_bell"] * mot_d * mot_h + blades) + n_disk * (A["cd_pylon"] * A["pylon_fair_t"] * A["pylon_h"] + A["cd_nacelle"] * A["nacelle_frontal"]))
        dq_sum = sum(dq.values())
        if A["aero"] == "cfd":
            rest = sum(v for k_, v in dq.items() if k_ not in ("stopped_rotors", "landing_gear"))
            dq_total = (A["cfd_k_exc"] * rest + A["cfd_rotor_dq_factor"] * dq["stopped_rotors"] + A["cfd_gear_dq"]
                        + A["cfd_wing_interference"] * chord / 1.15) * A["cfd33_cd0_factor"]   # interference scales with the junction size
        else:
            dq_total = dq_sum * A["k_exc"]
        CD0 = dq_total / S
        # cruise [I1], [P1]-[P2], [E1]
        CL = W / (q * S)
        CDi = CL**2 / (np.pi * e_os * AR)
        Dcr = q * S * (CD0 + CDi)
        t_ded = A["cfd_thrust_deduction"] if A["aero"] == "cfd" else 0.0
        w_p = A["cfd_wake_fraction"] if A["aero"] == "cfd" else 0.0
        Va = V * (1 - w_p)                                          # mean axial inflow at the disk (iteration 3.3 CFD)
        eta_p = ph.prop_efficiency(Dcr / (1 - t_ded) / n_push, Va, cr["rho"], Dp)   # per propeller, open water at Va
        P_cr_shaft = Dcr / (1 - t_ded) * Va / eta_p
        P_cr = P_cr_shaft / eta_d / 1e3 + A["aux_kw"]
        # climb capability with pusher peak (short time) power
        roc = (pm_ppeak * 1e3 * eta_p * (1 - t_ded) / (1 - w_p) - Dcr * V) / W
        # mission terminal energies (kWh) [E2]-[E4], [T1]
        fm = (T_disc**1.5 / np.sqrt(2 * site["rho"] * A1)) / P_disc_site
        E_h = P_h_site * (A["t_hover_to"] + A["t_hover_ld"]) / 3600 + 0.5 * W * A["h_vclimb"] / (eta_d * fm) / 3.6e6
        P_tr = 0.5 * (P_h_site + P_cr)
        E_tr = 2 * P_tr * A["t_tr"] / 3600
        E_cl = W * (A["cruise_alt"] - A["transition_alt"]) / (eta_p * eta_d) / 3.6e6
        E_cr = P_cr * rng_req / (V * 3.6)
        # battery losses from cell resistance at EOL (iteration 3.3: exact I-R sag, as the independent V&V):
        # p_cell = I (V_oc - I R), eta = V_terminal / V_oc; mid-SOC V_oc for take-off, transitions, climb and cruise,
        # low-SOC V_oc for the landing hover
        Rc = c_r * A["dcir_eol_factor"]
        if A["battery_sag"] == "exact":
            def eta_b(P, v_oc=A["v_ocv_mid"]):
                p_c = P * 1e3 / cells
                disc = v_oc**2 - 4 * Rc * p_c
                i_c = (v_oc - np.sqrt(np.maximum(disc, 0.0))) / (2 * Rc)
                return np.minimum(np.where(disc > 0, (v_oc - i_c * Rc) / v_oc, 0.5), A["eta_b_cap"])
        else:
            def eta_b(P, v_oc=None):
                return np.minimum(1 - (P * 1e3 / (cells * c_vn)) * Rc / c_vn, A["eta_b_cap"])
        eb_h, eb_cr = eta_b(P_h_site), eta_b(P_cr)
        eb_ld = eta_b(P_h_site, A["v_ocv_low"])
        eb_tr = eta_b(P_tr)
        E_h_ld = P_h_site * A["t_hover_ld"] / 3600
        E_fixed_cells = (E_h - E_h_ld) / eb_h + E_h_ld / eb_ld + E_tr / eb_tr + E_cl / eb_cr
        E_cells = E_fixed_cells + E_cr / eb_cr
        E_nom_energy = E_cells / (A["f_eol"] * (1 - A["f_res"]))
        # power limits [B4]: hover at ceiling within continuous-screen - 0.3 C; one pack out and rotor out within peak
        eb_c = eta_b(P_h_ceil)
        c_lim = c_ic / (c_ah * A["f_eol"]) - A["dC"]
        c_pk = c_ip / (c_ah * A["f_eol"])
        E_nom_c = P_h_ceil / eb_c / (c_lim * A["f_eol"])
        E_nom_1p = P_h_ceil / eb_c / (c_pk * A["f_eol"] * (npk_f - 1) / npk_f)
        P_ro_tot = (P_ro + P_mot_ceil * (n - 2)) / eta_d / 1e3 + A["aux_kw"]
        E_nom_ro = P_ro_tot / eb_c / (c_pk * A["f_eol"])
        E_req = np.maximum.reduce([E_nom_energy, E_nom_c, E_nom_1p, E_nom_ro])
        # integer battery layout: Ns x Np per pack x npk, Ns within BMS / inverter limits; minimum cell count
        Np = np.arange(1, 41)[None, :]
        Ns = np.ceil(E_req[:, None] * 1e3 / (npk_f[:, None] * Np * c_wh[:, None]))
        Ns = np.maximum(Ns, ns_min[:, None])
        ok = Ns <= ns_max[:, None]
        tot = np.where(ok, Ns * Np * npk_f[:, None], np.inf)
        k = np.argmin(tot, axis=1)
        cells_new = tot[np.arange(N), k]
        bat_ok = np.isfinite(cells_new)
        cells_new = np.where(bat_ok, cells_new, ns_max * 40 * npk_f)
        if it < 40:
            cells = cells_new
        else:                       # monotone in the last iterations to suppress integer limit cycles
            cells = np.maximum(cells, cells_new)
        ns_sel = np.where(cells == cells_new, Ns[np.arange(N), k], ns_sel)
        np_sel = np.where(cells == cells_new, np.arange(1, 41)[k], np_sel)
        E_nom = cells * c_wh / 1e3
        # iteration 3.2: pack mass fitted to the CAD packs (cad/parts.json, 3.1 build): per cell 71 g cell + 7.7 g G10 holder
        # + 14.5 g area-proportional cold plate / lid / box floor + 4 g nickel and liners (estimate); per pack 3.44 kg fixed
        # (box walls 1.0, Orion BMS 0.6, 2 EV200 + fuse 1.11, vent 0.15, mounts 0.08, BMS/HV harness 0.5 estimate)
        if A["battery_model"] == "cad":
            m_bat = cells * (c_kg + A["pack_per_cell_kg"]) + npk_f * A["pack_fixed_kg"]
        else:
            m_bat = cells * c_kg / (1 - A["f_ovh"])
        V_bus = ns_sel * c_vn
        # ---- component masses
        mass = {}
        # structure: Raymer x composite factor x CAD calibration (design/mass_calibration.json)
        mass["wing"] = CF["wing"] * ph.raymer_wing_kg(S, AR, q, 1.0, af_tc, A["Nz"], m, A["tf_struct"]) + np.array(A["flap_extra_kg"])[fl_i] + has_flap * 2.0
        mass["tail"] = CF["tail"] * (ph.raymer_htail_kg(S_h, ARh, q, A["tail_tc"], A["Nz"], m, A["tf_struct"])
                                     + 2 * ph.raymer_vtail_kg(S_v / 2, A["ARv"], q, A["tail_tc"], A["Nz"], m, A["tf_struct"]))
        mass["fuselage"] = CF["fuselage"] * ph.raymer_fuselage_kg(swet_f, A["Nz"], m, l_t, Lf / hf, q, A["tf_struct"])
        # booms: strength-sized tube wall along the boom, ultimate 1.5 x control-margin rotor-out thrust on every rotor
        Tu = 1.5 * T_ro * (2 if coax else 1)
        x_fs, x_rs = x_le + A["x_spar_f"] * chord, x_le + A["x_spar_r"] * chord
        xs = np.linspace(0, 1, 25)[None, :]
        xb = boom_x0[:, None] + xs * (boom_x1 - boom_x0)[:, None]
        Mb = np.zeros_like(xb)
        for j in range(xr.shape[1]):
            xj = xr[:, j][:, None]
            front = np.where(xb <= x_fs[:, None], Tu[:, None] * np.clip(xb - xj, 0, None), 0.0)
            rear = np.where(xb >= x_rs[:, None], Tu[:, None] * np.clip(xj - xb, 0, None), 0.0)
            Mb += np.where(xj < 0, front, np.where(xj > 0, rear, 0.0))
        r_b = A["boom_od"] / 2
        t_b = np.maximum(Mb / (np.pi * r_b**2 * A["boom_sigma"]), A["boom_tmin"])
        m_tube = 2 * A["cfrp_rho"] * np.pi * A["boom_od"] * np.trapezoid(t_b, xb, axis=1)
        mass["booms"] = m_tube * CF["boom_tube"] + CX["boom_wing_clamps_total"]          # tubes, over-wrap, sleeves, P2 clamps
        mass["rotor_pylons_mounts"] = np.full(N, n_disk * (CX["rotor_station_hardware_each"] + A["hub_fairing_kg"]))  # pylons, P3 plates, isolators, nacelles
        t_boom_root = t_b.max(axis=1)
        # skid gear (6061-T6): two cross tubes in bending, ultimate 1.5 x 3 g, attach at +-0.25 m, skids at +-0.70 m
        M_ct = 1.5 * A["n_land"] * W / 4 * 0.45
        t_ct = np.clip(M_ct / (np.pi * 0.038**2 * 262e6), 0.002, 0.008)
        m_ct = 2 * 1.9 * np.pi * 0.076 * t_ct * 2700
        m_sk = 2 * 2.6 * np.pi * 0.060 * 0.0025 * 2700
        mass["landing_gear"] = CF["landing_gear"] * (m_ct + m_sk)   # incl. oleo dampers, saddles, clamps (CAD calibration)
        mass["lift_motors"] = n * m_mot
        mass["lift_rotors"] = n * m_lprop
        mass["inverters"] = (n + n_push) * m_inv
        mass["cooling"] = CF["cooling"] * (0.6 * (n + n_push) + 4.0)
        # HV harness [M14]: per-motor DC pair sized at 5 A/mm2 for the hover current at the ceiling (continuous); the
        # rotor-out current (< 60 s) is then <= 1.8 x that, i.e. <= 9 A/mm2 short time; + pack-to-bus mains
        I_ro = P_ro / A["eta_m"] / (V_bus * 0.92)
        I_hv = P_mot_ceil / A["eta_m"] / (V_bus * 0.92)
        run = np.abs(xr).mean(axis=1) + b_y + 1.5
        I_tot = P_h_ceil * 1e3 / (V_bus * 0.92)
        rho_c, J_c = (2700.0, 3.1) if A["hv_conductor"] == "al" else (8960.0, 5.0)
        mass["hv_harness"] = (n * 2 * run * (I_hv / J_c * 1e-6) * rho_c * 1.4      # per-motor feeders
                              + 2 * 3.0 * (I_tot / J_c * 1e-6) * rho_c * 1.4)      # pack-to-bus mains
        # twin pushers: the same conductor section split into two feeders, each run from the bus to a boom tail
        # (the single tail-cone feeder, about 3 m, is inside the calibrated harness)
        I_p = P_cr_shaft / A["eta_m"] / (V_bus * 0.92)
        run_tw = boom_x1 + b_y + 1.5
        mass["hv_harness"] = mass["hv_harness"] + np.where(twin, 2 * np.maximum(run_tw - A["pusher_feeder_single"], 0.0)
                                                          * (I_p / J_c * 1e-6) * rho_c * 1.4, 0.0)
        mass["pusher_motor"] = pm_mass + n_push * CX["pusher_installation"]
        mass["pusher_propeller"] = n_push * m_pprop
        chute_max = np.array([c["max_kg"] for c in D.PARACHUTES])
        ch_idx = np.minimum(np.searchsorted(chute_max, m - 1e-6), len(chute_max) - 1)
        chute_ok = m <= chute_max[-1]
        mass["parachute"] = np.array([c["mass_kg"] for c in D.PARACHUTES])[ch_idx] + CX["parachute_installation"]
        mass["seats"] = np.full(N, CX["seats_and_furnishings"])
        mass["avionics"] = np.full(N, CF["avionics"] * ph.avionics_installed_kg(D.AVIONICS_UNINSTALLED_KG))
        mass["lv_electrical"] = np.full(N, D.LV_ELECTRICAL_KG)
        mass["flight_controls"] = D.FLIGHT_CONTROLS_KG + has_flap * CX.get("flap_actuators", 2.0)
        base = sum(mass.values())
        mass["growth"] = A["growth"] * base
        empty = base + mass["growth"]
        m_new = empty + m_bat + A["payload_kg"]
        dm = np.abs(m_new - m)
        if cfg.get("debug"):
            print(it, P_h_site[:1], P_h_ceil[:1], P_cr[:1], eb_h[:1], eb_c[:1], c_r[:1], c_v[:1], m[:1], m_new[:1], E_nom_energy[:1], E_nom_c[:1], E_nom_1p[:1], E_nom_ro[:1], cells[:1], m_bat[:1], empty[:1])
        m = np.where(m_new > 3000, 3000.0, m_new)
        if it > 45 and np.all(dm < 0.05):
            break
    converged = (dm < 0.5) & (m < 2999)

    # ---------------- constraints (g <= 0 feasible)
    g = {}
    E_avail = E_nom * A["f_eol"] * (1 - A["f_res"])
    range_km = (E_avail - E_fixed_cells) * eb_cr / P_cr * V * 3.6
    g["range"] = (rng_req - range_km) / rng_req
    g["footprint_length"] = length_overall / A["L_max"] - 1
    g["footprint_width"] = width_overall / A["L_max"] - 1
    g["oei_power"] = P_ro / 1e3 / P_pk - 1
    g["oei_torque"] = Q_ro / Q_mx - 1
    g["oei_rpm"] = rpm_h * np.maximum(r_w, r_wf) / rpm_hi - 1
    g["oei_flare_power"] = P_fl / 1e3 / P_pk - 1
    g["oei_flare_torque"] = Q_fl / Q_mx - 1
    g["tip_mach_oei_flare"] = vtip * r_wf / site["a"] / A["mach_tip_flare_max"] - 1
    g["door_width"] = 1 - ((A["x_spar_r"] - A["x_spar_f"]) * chord - 2 * A["post_w"]) / A["door_min_w"]
    g["hover_rpm_min"] = 1 - rpm_h / rpm_lo
    g["hover_cont_power"] = P_mot_ceil / 1e3 / np.minimum(P_ct, Qc_lift * omega / 1e3) - 1
    g["tip_mach_hover"] = vtip / site["a"] / A["mach_tip_hover_max"] - 1
    g["tip_mach_oei"] = vtip * r_w / ceil["a"] / A["mach_tip_oei_max"] - 1
    C_h = P_h_ceil / eb_c / (E_nom * A["f_eol"])
    g["c_rate_hover"] = C_h / c_lim - 1
    g["c_rate_one_pack_out"] = C_h * npk_f / (npk_f - 1) / c_pk - 1
    g["c_rate_rotor_out"] = P_ro_tot / eb_c / (E_nom * A["f_eol"]) / c_pk - 1
    g["battery_layout"] = np.where(bat_ok, -1.0, 1.0)
    I_mot_h = P_mot_ceil / A["eta_m"] / (ns_sel * 3.3)
    g["inverter_current"] = np.maximum(I_mot_h / inv_icont, I_ro * V_bus * 0.92 / (ns_sel * 3.3) / inv_ipk) - 1
    g["pusher_cont_power"] = P_cr_shaft / 1e3 * (1 + A["pusher_margin"]) / pm_pcont - 1
    # iteration 3.1: bus sag and cell current at end of life (DCIR x eol factor), low-SOC open-circuit voltage
    def _sag(P_kw, n_cells):
        p_cell = P_kw * 1e3 / n_cells
        disc = A["v_ocv_low"] ** 2 - 4 * Rc * p_cell
        i = np.where(disc >= 0, (A["v_ocv_low"] - np.sqrt(np.maximum(disc, 0))) / (2 * Rc), A["v_ocv_low"] / Rc)
        v = ns_sel * (A["v_ocv_low"] - i * Rc)
        return i, v, disc >= 0
    # one pack out = land-immediately emergency: vertical landing at the 500 m ISA+15 design site with the non-essential
    # auxiliary loads (cabin, cooling fans beyond the inverter loop) shed; the ceiling case is not flown after a pack loss
    i_1p, v_1p, ok_1p = _sag(P_h_site - A["aux_kw"], cells * (npk_f - 1) / npk_f)
    P_fl_tot = (P_fl + P_mot_site * (n - 2)) / eta_d / 1e3 + A["aux_kw"]
    i_fl, v_fl, ok_fl = _sag(P_fl_tot, cells)                                    # all packs: one-motor-out flare
    g["one_pack_out_cell_current"] = np.where(ok_1p, i_1p / c_ip - 1, 1.0)
    g["one_pack_out_bus_voltage"] = np.where(ok_1p, 1 - v_1p / A["bus_v_min"], 1.0)
    g["flare_cell_current"] = np.where(ok_fl, i_fl / c_ip - 1, 1.0)
    g["flare_bus_voltage"] = np.where(ok_fl, 1 - v_fl / A["bus_v_min"], 1.0)
    g["pusher_climb"] = 1 - roc / A["roc_min"]
    g["pusher_helical_mach"] = mach_hel / A["mach_helical_max"] - 1
    g["pusher_rpm"] = rpm_p / pm_rpm_hi - 1
    g["pusher_bus"] = np.where(pusher_bus_ok, -1.0, 1.0)
    # twin pushers: tip-to-tip gap between the two boom-tail propellers >= 0.30 m
    g["twin_prop_lateral"] = np.where(twin, (Dp + 0.30) / (2 * b_y) - 1, -1.0)
    Vs_hot = np.sqrt(2 * W / (cr["rho"] * S * CLmax))
    Vs_sl = np.sqrt(2 * W / (sl["rho"] * S * CLmax))
    g["stall_margin"] = A["stall_factor"] * Vs_hot / V - 1
    # one pusher out (twin): level flight at 1.3 Vs on the remaining pusher (diagnostic, not a constraint; the procedure
    # is a decelerating transition to hover on the lift rotors, which are sized for hover with a rotor out)
    V1 = A["stall_factor"] * Vs_hot
    q1 = 0.5 * cr["rho"] * V1**2
    D1 = q1 * S * (CD0 + (W / (q1 * S)) ** 2 / (np.pi * e_os * AR))
    t_d1 = A["cfd_thrust_deduction"] if A["aero"] == "cfd" else 0.0
    P_1po = D1 / (1 - t_d1) * V1 * (1 - w_p) / ph.prop_efficiency(D1 / (1 - t_d1), V1 * (1 - w_p), cr["rho"], Dp) / 1e3
    n_gust = ph.gust_load_factor(W / S, sl["rho"], cr["rho"], chord, a_w, V * np.sqrt(cr["rho"] / sl["rho"]))
    g["gust"] = n_gust / 3.8 - 1
    blade_chord = sigma * np.pi * R / nb
    g["blade_chord"] = blade_chord / R / 0.25 - 1
    g["prop_available"] = np.where(prop_ok, -1.0, 1.0)
    g["parachute"] = np.where(chute_ok, -1.0, 1.0)
    g["closure"] = np.where(converged, -1.0, 1.0)
    g["oei_trim"] = np.full(N, -1.0 if n > 4 else 1.0)
    G = np.stack(list(g.values()), axis=1)
    feasible = np.all(G <= 1e-9, axis=1)

    # ---------------- cost (USD per aircraft) and complexity
    cost = {}
    cost["lift_motors"] = n * pr_mot
    cost["inverters"] = n * pr_inv + n_push * np.where(bus800, pr_inv, D.price_usd("INV-HBCI400400")[0])
    cost["lift_propellers"] = n * pr_lprop
    cost["hub_fairings"] = np.full(N, n_disk * A["hub_fairing_usd"])
    cost["pusher_motor"] = pr_pm
    cost["pusher_propeller"] = n_push * pr_pprop
    pack_parts = (D.price_usd("BMS-ORION2")[0] + 2 * D.price_usd("HV-EV200")[0] + D.price_usd("HV-FUSE")[0]
                  + 8 * D.price_usd("HV-CONN")[0] + 2500.0)            # + enclosure, cold plate, bus bars (estimate)
    cost["battery"] = cells * (c_pr + 1.0) + npk_f * pack_parts   # cells + holders/nickel 1 USD; assembly hours in labour
    cost["parachute"] = np.array([c["price_usd"] for c in D.PARACHUTES])[ch_idx]
    cost["hv_cooling_harness"] = (400.0 * (n + n_push) + 1000.0 + 30.0 * n * 2 * run
                                  + np.where(twin, 30.0 * 2 * 2 * np.maximum(boom_x1 + b_y + 1.5 - A["pusher_feeder_single"], 0.0), 0.0))
    cost["systems_avionics_cabin"] = np.full(N, sum(r[1] for r in D.systems_cost())) + np.array(A["flap_extra_usd"])[fl_i]
    m_airframe = (mass["wing"] + mass["tail"] + mass["fuselage"] + mass["booms"] + mass["rotor_pylons_mounts"] + mass["landing_gear"]
                  + mass["flight_controls"])
    VH_kt = 1.10 * V / ph.KT
    rec, mfg_h = ph.eastlake_recurring_per_unit(m_airframe, VH_kt, A["N_units"], A["f_comp"], A["f_cert"])   # reference only
    # iteration 3: bottom-up made-part cost from the CAD parts (sizing/cost.py), batch of N_units
    n_cots = (4 * n + 3 * n_push + 10 + 30                  # motor, prop, inverter, pylon per rotor; pusher set(s); systems; misc
              + (n_disk if A["hub_fairing_kg"] > 0 else 0))   # hub fairings
    ac = airframe_cost(mass, A["N_units"], A["labour_rate"], n_cells=cells, n_packs=npk_f, n_cots_instances=n_cots)
    cost["airframe_materials_consumables"] = ac["materials"]
    cost["outsourced_services"] = np.full(N, ac["outsourced"])
    cost["labour"] = ac["labour_batch"]
    cost["tooling_amortised"] = np.full(N, ac["tooling_per_unit"])
    total = sum(cost.values())
    n_types = (1 + (pm_id != lm_id) + (1 + (~bus800)) + 1 + 1 + 1 + 1 + 1 + has_flap)  # motors, inverters, lift prop,
    #                                                                  pusher prop, cell, BMS, pylon, flap actuator
    n_lru = (n + n_push) * 3 + n_disk + npk_f + 4 * has_flap
    penalty = A["lambda_type"] * n_types + A["lambda_part"] * n_lru
    obj = total + penalty
    proto_cash = total - cost["labour"] - cost["tooling_amortised"] + ac["tooling_materials"]
    if cfg.get("objective") == "mtow":         # alternative objective for the minimum-mass Pareto front
        obj = m.copy()

    out.update(dict(
        mtow=m, empty=empty, battery_kg=m_bat, E_nom=E_nom, cells=cells, Ns=ns_sel, Np_pack=np_sel, npk=npk_f, V_bus=V_bus,
        disk_loading=W / (n_disk * np.pi * R**2), f_dl=f_dl, overlap_m2=ov, sigma=sigma, blade_chord=blade_chord, fm=fm,
        P_hover_site=P_h_site, P_hover_ceil=P_h_ceil, P_mot_site=P_mot_site / 1e3, P_mot_ceil=P_mot_ceil / 1e3,
        P_oei=P_ro / 1e3, Q_oei=Q_ro, P_flare=P_fl / 1e3, Q_flare=Q_fl, rpm_flare=rpm_h * r_wf, T_flare=T_fl, rpm_hover=rpm_h, rpm_oei=rpm_h * r_w, T_rotor=T_rot, T_oei=T_ro,
        CL=CL, CD0=CD0, CDi=CDi, dq_total=dq_total, LD=W / Dcr, D_cruise=Dcr, eta_p=eta_p, P_cruise=P_cr,
        P_cruise_shaft=P_cr_shaft / 1e3, roc=roc, rpm_pusher=rpm_p, mach_helical=mach_hel,
        E_hover=E_h, E_tr=E_tr, E_climb=E_cl, E_cruise=E_cr, E_cells=E_cells, eta_b_cruise=eb_cr, eta_b_hover=eb_h,
        range_km=range_km, C_hover=C_h, i_cell_one_pack_out=i_1p, v_bus_one_pack_out=v_1p, i_cell_flare=i_fl, v_bus_flare=v_fl, Vs_sl=Vs_sl, Vs_hot=Vs_hot, CLmax=CLmax, P_one_pusher_out=P_1po, P_pusher_unit_cont=pm_pcont / n_push, P_pusher_unit_peak=pm_ppeak / n_push, twin=twin, n_gust=n_gust, oswald=e_os,
        S=S, AR=AR, b_y=b_y, x_le=x_le, hn=hn, a_in=a_in, pitch=pitch, xr=xr, x_tle=x_tle, c_h=c_h, S_h=S_h, span_h=span_h,
        S_v=S_v, h_v=h_v, c_v=c_v, l_t=l_t, d_t=d_t, boom_x0=boom_x0, boom_x1=boom_x1, L_boom=L_boom, t_boom_root=t_boom_root,
        length=length_overall, width=width_overall, swet_f=swet_f, a_w=a_w, deps=deps, ARh=ARh,
        mass=mass, dq=dq, cost=cost, cost_total=total, penalty=penalty, objective=obj, n_types=n_types, n_lru=n_lru,
        m_airframe=m_airframe, mfg_hours=mfg_h, eastlake_recurring=rec, labour_hours_prototype=ac["hours_prototype"],
        tooling_hours=ac["tooling_hours"], tooling_materials=ac["tooling_materials"], prototype_cash=proto_cash, learning=ac["learning"], chute_idx=ch_idx, lprop_idx=lp_idx, pprop_idx=pp_idx,
        g=g, G=G, feasible=feasible, converged=converged,
    ))
    return out
