"""Structural dynamics and aeroelastic screening of the sized airframe -> fea/results/dynamics.json, docs/models/fea/*.png

    ~/tools/cadenv/bin/python fea/dynamics.py

1. Free-free modes (beam model with the sized sections) and a Campbell diagram against the lift-rotor 1P / 2P
   (2 blades) and pusher 1P / blade-pass excitations over the operating rpm ranges (all pusher units identical; iteration 3.2:
   one pusher on each boom tail, so the "mount" is the boom-end plug on the flexible boom).
2. Wing torsional divergence: strip-theory aerodynamic stiffness on the beam model (lift slope a0 per station at the
   quarter chord), generalised eigenproblem K u = q Ka u with the fuselage held at the cg.
3. Flutter: modal k-method with strip Theodorsen aerodynamics on the wing, 24 elastic free-free modes of the beam
   model (booms, rotors, tail as inertia); requirement: no flutter below 1.2 VD (CS-23.629). Verified on the
   Hodges & Pierce typical section and the Goland wing (validation D1-D3).
4. Pusher whirl flutter: pivoted-rotor pitch/yaw model with gyroscopic coupling and quasi-steady blade-element
   aerodynamics (numerical derivatives), mount stiffness from the beam model; stiffness margin at 1.2 VD.
   Lift rotors: edgewise flow in transition and stopped in cruise -> classical whirl flutter not applicable (screened
   by frequency placement only).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import scipy.linalg as sla
from scipy.special import hankel2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import airframe as AF  # noqa: E402
from fea import loads as LD  # noqa: E402
from fea.geometry import ROOT, load  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTIMG = ROOT / "docs" / "models" / "fea"
RHO0 = 1.225


# ============================================================================= Theodorsen 2-DOF k-method
def theodorsen_C(k):
    H1, H0 = hankel2(1, k), hankel2(0, k)
    return H1 / (H1 + 1j * H0)


def flutter_k_method(mu, a, x_a, r2, sigma, g_s=0.0, ks=None):
    """Typical section (plunge h, pitch alpha about the elastic axis at 'a' semichords aft of mid-chord).
    Returns arrays (V/(b w_alpha), g, w/w_alpha) for both branches and the flutter point where g = g_s."""
    ks = ks if ks is not None else np.geomspace(0.02, 3.0, 600)
    br = []
    for k in ks:
        C = theodorsen_C(k)
        lh = 1 - 2j * C / k
        la = -a - 1j / k - 2 * C / k**2 - 2j * C * (0.5 - a) / k
        mh = -a + 2j * C * (a + 0.5) / k
        ma = 1 / 8 + a**2 - 1j * (0.5 - a) / k + 2 * C * (a + 0.5) / k**2 + 2j * C * (a + 0.5) * (0.5 - a) / k
        A = mu**2 * sigma**2 * r2
        B = -(mu * sigma**2 * (mu * r2 + ma) + mu * r2 * (mu + lh))
        C0 = (mu + lh) * (mu * r2 + ma) - (mu * x_a + la) * (mu * x_a + mh)
        Z = np.roots([A, B, C0])
        row = []
        for z in sorted(Z, key=lambda z: z.real, reverse=True):
            if z.real <= 0:
                row.append((np.nan, np.nan, np.nan))
                continue
            wr = 1 / math.sqrt(z.real)                    # w / w_alpha
            row.append((1 / (k * math.sqrt(z.real)), z.imag / z.real, wr))
        br.append(row)
    br = np.array(br)                                      # (nk, 2, 3)
    flut = None
    for j in range(2):
        V, g = br[:, j, 0], br[:, j, 1]
        for i in range(len(ks) - 1, 0, -1):               # from low V (high k) upwards
            if np.isfinite(g[i]) and np.isfinite(g[i - 1]) and (g[i] - g_s) * (g[i - 1] - g_s) < 0:
                t = (g_s - g[i]) / (g[i - 1] - g[i])
                Vf = V[i] + t * (V[i - 1] - V[i])
                if flut is None or Vf < flut["V_over_bwa"]:
                    flut = dict(V_over_bwa=float(Vf), branch=j, k=float(ks[i]), w_over_wa=float(br[i, j, 2]))
                break
    return br, flut


# ============================================================================= modal flutter (strip Theodorsen, k-method)
def strip_aero_coeffs(k, a):
    C = theodorsen_C(k)
    lh = 1 - 2j * C / k
    la = -a - 1j / k - 2 * C / k**2 - 2j * C * (0.5 - a) / k
    mh = -a + 2j * C * (a + 0.5) / k
    ma = 1 / 8 + a**2 - 1j * (0.5 - a) / k + 2 * C * (a + 0.5) / k**2 + 2j * C * (a + 0.5) * (0.5 - a) / k
    return lh, la, mh, ma


def modal_flutter(omegas, H, AL, strips, b_ref, rho=RHO0, g_s=0.02, ks=None):
    """k-method flutter on mass-normalised modes.
    omegas: (n,) rad/s; H, AL: (nstrip, n) modal plunge (positive DOWN) and pitch (nose-up) at the strip elastic axis;
    strips: list of dict(b, a, w) (semi-chord, elastic-axis position in semichords aft of mid-chord, strip width).
    Returns the flutter speed (V, omega, mode branch) where the structural damping needed equals g_s, and the V-g data."""
    ks = ks if ks is not None else np.geomspace(0.01, 2.5, 400)
    n = len(omegas)
    Kg = np.diag(omegas**2)
    data = []
    for k in ks:
        A = np.zeros((n, n), complex)
        for i, st in enumerate(strips):
            b = st["b"]
            lh, la, mh, ma = strip_aero_coeffs(k * b / b_ref, st["a"])
            h, al = H[i] / b, AL[i]
            # generalised aerodynamic matrix in the Hodges & Pierce typical-section form (h positive down, coefficients
            # l_h ... m_alpha as in theodorsen above): (M + A) q = Z K q, row h: +(l_h h/b + l_a a), row a: +(m_h h/b + m_a a);
            # reproduces the 2-DOF determinant exactly (validation case D2)
            Lc = np.pi * rho * b**4 * (lh * h + la * al)
            Mc = np.pi * rho * b**4 * (mh * h + ma * al)
            A += st["w"] * (np.outer(h, Lc) + np.outer(al, Mc))
        Z = sla.eigvals(np.eye(n) + A, Kg)                     # (I + A) q = Z K q,  Z = (1 + i g) / omega^2
        row = []
        for z in Z:
            if z.real <= 0:
                continue
            w = 1 / math.sqrt(z.real)
            row.append((w * b_ref / k, z.imag / z.real, w))
        data.append(sorted(row, key=lambda t: t[2]))
    # track branches by sorting on frequency at each k (adequate for well separated modes)
    nb = min(len(r) for r in data)
    arr = np.array([r[:nb] for r in data])                 # (nk, nb, 3)
    flut = None
    for j in range(nb):
        V, g = arr[:, j, 0], arr[:, j, 1]
        for i in range(len(ks) - 1, 0, -1):
            if (g[i] - g_s) * (g[i - 1] - g_s) < 0 and g[i - 1] > g[i]:
                t = (g_s - g[i]) / (g[i - 1] - g[i])
                Vf = V[i] + t * (V[i - 1] - V[i])
                if flut is None or Vf < flut["V"]:
                    flut = dict(V=float(Vf), omega=float(arr[i, j, 2]), branch=j)
                break
    return flut, arr


def wing_modal_flutter(m, nmodes=20, g_s=0.02, rho=RHO0):
    f = m["f"]
    W = m["W"]
    fr, V = f.modes(nmodes + 6, shift_hz=0.5)
    keep = [k for k in range(len(fr)) if fr[k] > 0.5][:nmodes]
    om = 2 * math.pi * fr[keep]
    w = AF.trap_weights(m["ys"])
    strips, Hs, As = [], [], []
    for i, y in enumerate(m["ys"]):
        nb = m["box"][i]
        c = float(W.chord(y))
        b = c / 2
        x_mid = float(W.x_at(y, 0.5))
        strips.append(dict(b=b, a=(f.nodes[nb][0] - x_mid) / b, w=w[i]))
        Hs.append(-V[6 * nb + 2, keep])
        As.append(V[6 * nb + 4, keep])
    b_ref = float(W.chord(0.0)) / 2
    flut, arr = modal_flutter(om, np.array(Hs), np.array(As), strips, b_ref, rho=rho, g_s=g_s)
    return flut, arr, fr[keep]


# ============================================================================= divergence on the beam model
def divergence(m, a0=2 * math.pi, clamp_node=None):
    f = m["f"]
    W = m["W"]
    K, _ = f.assemble(with_mass=False)
    n = f.ndof
    Ka = np.zeros((n, n))
    w = AF.trap_weights(m["ys"])
    for i, y in enumerate(m["ys"]):
        nb = m["box"][i]
        c = float(W.chord(y))
        e = f.nodes[nb][0] - float(W.x_at(y, 0.25))       # ac ahead of the box node (elastic axis) > 0
        dz, dry = 6 * nb + 2, 6 * nb + 4
        Ka[dz, dry] += a0 * c * w[i]                        # lift per unit q per unit nose-up twist
        Ka[dry, dry] += a0 * c * w[i] * e                   # nose-up moment about the elastic axis
    cn = clamp_node if clamp_node is not None else m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    fixed = np.arange(6 * cn, 6 * cn + 6)
    free = np.setdiff1d(np.arange(n), fixed)
    Kf = K[free][:, free].toarray()
    Af = Ka[np.ix_(free, free)]
    lam = sla.eigvals(Af, Kf)                               # Af u = (1/q) Kf u
    lam = lam[np.isfinite(lam) & (np.abs(lam.imag) < 1e-9 * np.abs(lam).max()) & (lam.real > 0)]
    q = 1 / lam.real.max() if len(lam) else np.inf
    return float(q)


# ============================================================================= whirl flutter (pivoted rotor)
def rotor_hub_moments(state, V, Om, R, Rh, B, chord, pitch_r, a, rho=RHO0, a0=5.7, nr=10, naz=48):
    """Aerodynamic moments about the pivot (x', y') for a pivoted rotor; state = (px, py, dpx, dpy)."""
    px, py, dpx, dpy = state
    om = np.array([dpx, dpy, 0.0])
    rot = np.array([px, py, 0.0])
    nvec = np.array([py, -px, 1.0])
    nvec /= np.linalg.norm(nvec)
    g, wg = np.polynomial.legendre.leggauss(nr)
    rr = Rh + (R - Rh) * (g + 1) / 2
    wr = wg * (R - Rh) / 2
    M = np.zeros(3)
    for b_ in np.linspace(0, 2 * math.pi, naz, endpoint=False):
        er0 = np.array([math.cos(b_), math.sin(b_), 0.0])
        et0 = np.array([-math.sin(b_), math.cos(b_), 0.0])
        er = er0 + np.cross(rot, er0)
        et = et0 + np.cross(rot, et0)
        for r, w_ in zip(rr, wr):
            p = a * nvec + r * er                           # position relative to the pivot
            v_struct = np.cross(om, p)
            v_rot = Om * r * et
            rel = np.array([0, 0, V]) - v_struct - v_rot    # air relative to the element
            UP, UT = rel @ nvec, -(rel @ et)
            Wm = math.hypot(UP, UT)
            phi = math.atan2(UP, UT)
            cl = a0 * (pitch_r(r) - phi)
            dL = 0.5 * rho * Wm**2 * chord * cl * w_
            ldir = (-UT * nvec - UP * et) / Wm
            M += np.cross(p, dL * ldir) * B / naz
    return M[:2]


def whirl(K, I, Ip, Om, V, geom, damping=0.01):
    """Eigenvalues of the pivoted rotor at speed V (quasi-steady aero derivatives by central differences)."""
    def pitch_r(r, V0=geom["V_design"]):
        return math.atan2(V0, Om * r) + math.radians(geom["alpha_design_deg"])
    args = (V, Om, geom["R"], geom["Rh"], geom["B"], geom["chord"], pitch_r, geom["a"])
    D = np.zeros((2, 4))
    h = 1e-4
    for j in range(4):
        e = np.zeros(4)
        e[j] = h
        D[:, j] = (rotor_hub_moments(e, *args) - rotor_hub_moments(-e, *args)) / (2 * h)
    Kd, Cd = D[:, :2], D[:, 2:]
    c = 2 * damping * math.sqrt(K * I)
    Mm = np.eye(2) * I
    G = np.array([[0, Ip * Om], [-Ip * Om, 0]])
    Cm = np.eye(2) * c + G - Cd
    Km = np.eye(2) * K - Kd
    A = np.block([[np.zeros((2, 2)), np.eye(2)], [-np.linalg.solve(Mm, Km), -np.linalg.solve(Mm, Cm)]])
    return np.linalg.eigvals(A)


def mount_stiffness(m, node, axis_x=True):
    """Pivot distance and rotational stiffness of the pusher mount from the beam model (fuselage held at the cg)."""
    f = m["f"]
    cn = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    fixed = list(range(6 * cn, 6 * cn + 6))
    out = {}
    for nm, (fd, rd) in (("pitch", (2, 4)), ("yaw", (1, 5))):
        F = np.zeros(f.ndof)
        F[6 * node + fd] = 1.0
        u, _ = f.solve_static(F, fixed)
        w, th = abs(u[6 * node + fd]), abs(u[6 * node + rd])
        a = w / th
        out[nm] = dict(pivot_distance_m=a, K_Nm_per_rad=a / th)
    return out


# ============================================================================= main
def classify(mode_vec, m):
    f = m["f"]
    V = mode_vec.reshape(-1, 6)
    e = {}
    groups = dict(wing=m["front"] + m["rear"] + m["box"], fuselage=m["fus"], tail=m["tail"], hubs=list(m["hubs"].values()),
                  booms=[n for b in m["booms"].values() for n in b["nodes"]])
    for k, nodes in groups.items():
        e[k] = float(np.sum(V[nodes, :3] ** 2))
    tot = sum(e.values()) or 1
    return {k: round(v / tot, 3) for k, v in sorted(e.items(), key=lambda kv: -kv[1]) if v / tot > 0.05}


def main():
    upd = HERE / "results" / "sizing_update.json"
    g = load(ROOT / "design" / "geometry.json", sizing=upd if upd.exists() else None)
    ac = LD.aircraft_from_geometry(g)
    m = AF.build(g)
    f = m["f"]
    OUTIMG.mkdir(parents=True, exist_ok=True)
    res = {}
    # ---------------------------------------------------------------- modes + Campbell
    fr, V = f.modes(70, shift_hz=0.5)
    modes = []
    for k, fk in enumerate(fr):
        if fk < 0.5:
            continue
        modes.append(dict(f_hz=float(fk), shape=classify(V[:, k], m)))
    rot = g["rotors"][0]
    rpm_h = rot.get("rpm_hover", 1964.0)
    lift = dict(rpm_min=0.74 * rpm_h, rpm_hover=rpm_h, rpm_max=rot["rpm_max"], blades=rot.get("blades", 2))
    from fea.geometry import pusher_list
    pu = pusher_list(g)[0]
    push = dict(rpm_min=0.6 * pu.get("rpm_cruise", 2016), rpm_cruise=pu.get("rpm_cruise", 2016), rpm_max=pu["rpm_max"], blades=pu.get("blades", 3))
    exc = [("lift 1P", 1, lift), (f"lift {lift['blades']}P (blade pass)", lift["blades"], lift), ("pusher 1P", 1, push),
           (f"pusher {push['blades']}P (blade pass)", push["blades"], push)]
    flags = []
    for md in modes:
        for nm, nP, r in exc:
            lo, hi = 0.9 * nP * r["rpm_min"] / 60, 1.1 * nP * r["rpm_max"] / 60
            if lo <= md["f_hz"] <= hi:
                rpm_c = md["f_hz"] * 60 / nP
                if "lift" in nm:
                    local = md["shape"].get("hubs", 0) + md["shape"].get("booms", 0)
                elif any("boom" in str(p_.get("attach", "")) for p_ in pusher_list(g)):     # boom-tail pushers (iteration 3.2)
                    local = md["shape"].get("booms", 0) + md["shape"].get("tail", 0)
                else:
                    local = md["shape"].get("fuselage", 0) + md["shape"].get("tail", 0)
                flags.append(dict(mode_hz=md["f_hz"], excitation=nm, crossing_rpm=rpm_c, shape=md["shape"],
                                  severity="HIGH" if local > 0.4 and abs(rpm_c - (r.get("rpm_hover") or r.get("rpm_cruise"))) < 0.1 * (r.get("rpm_hover") or r.get("rpm_cruise")) else
                                  ("MEDIUM" if local > 0.4 else "LOW")))
    res["modes"] = modes
    res["excitation"] = dict(lift=lift, pusher=push)
    res["campbell_flags"] = flags
    plot_campbell(modes, exc, lift, push)
    # ---------------------------------------------------------------- divergence
    VD = ac["speeds"]["VD"]
    qD = divergence(m)
    res["divergence"] = dict(q_div_Pa=qD, V_div_EAS_ms=math.sqrt(2 * qD / RHO0), VD_EAS=VD, required_EAS=1.2 * VD,
                             margin=math.sqrt(2 * qD / RHO0) / (1.2 * VD) - 1, a0_per_rad=2 * math.pi,
                             note="strip theory, 2-D lift slope 2 pi (conservative vs the 3-D 4.62), ac at c/4, elastic axis at the box line")
    # ---------------------------------------------------------------- flutter (modal, strip Theodorsen)
    fl, arr, frs = wing_modal_flutter(m, nmodes=24)
    res["flutter_modal"] = dict(V_flutter_TAS_ms=fl["V"] if fl else None, f_flutter_hz=fl["omega"] / 2 / math.pi if fl else None,
                                required_EAS=1.2 * VD, margin=(fl["V"] / (1.2 * VD) - 1) if fl else None, modes_used_hz=frs.tolist(),
                                note="24 free-free elastic modes, strip Theodorsen aerodynamics on the wing (sea level), k-method, g = 0.02; "
                                     "booms, rotors and tail carry inertia only")
    plot_vg(arr, VD)
    # ---------------------------------------------------------------- pusher whirl
    ms = mount_stiffness(m, m["pushers"][0])
    Kp = min(v["K_Nm_per_rad"] for v in ms.values())
    a_p = float(np.mean([v["pivot_distance_m"] for v in ms.values()]))
    mp = pu["mass_kg"]
    Ip = pu.get("rotor_inertia_kgm2", 0.97)
    Iy = Ip / 2 + 0.25 * mp * 0.15**2 + mp * a_p**2
    geom = dict(R=pu["diameter"] / 2, Rh=0.14, B=pu.get("blades", 3), chord=pu.get("blade_chord", 0.06 * pu["diameter"]), a=a_p,
                V_design=g["aero"].get("cruise_speed_ms", 41.7), alpha_design_deg=4.0)
    Om = 2 * math.pi * pu["rpm_max"] / 60
    sweep = []
    for Vt in np.linspace(5, 1.3 * VD / math.sqrt(0.908), 14):
        ev = whirl(Kp, Iy, Ip, Om, Vt, geom)
        sweep.append(dict(V=float(Vt), max_real=float(ev.real.max()), freqs_hz=sorted(set(np.round(np.abs(ev.imag) / 2 / math.pi, 2).tolist()))))
    # stiffness margin: lowest K (fraction of the actual) that is still stable at 1.2 VD (TAS)
    Vreq = 1.2 * VD / math.sqrt(0.908)
    kf = 1.0
    for frac in np.geomspace(1.0, 0.002, 60):
        if whirl(Kp * frac, Iy, Ip, Om, Vreq, geom).real.max() > 0:
            break
        kf = frac
    res["pusher_whirl"] = dict(mount=ms, K_used=Kp, pivot_distance_m=a_p, I_pitch_kgm2=Iy, Ip=Ip, rpm=pu["rpm_max"], sweep=sweep,
                               stable_to_1p2VD=bool(all(s_["max_real"] < 0 for s_ in sweep if s_["V"] <= Vreq)),
                               stiffness_fraction_still_stable_at_1p2VD=float(kf),
                               note="quasi-steady blade-element derivatives, 1 % structural damping; stiffness margin = 1 / fraction")
    res["lift_rotor_whirl"] = ("not applicable as classical whirl flutter: lift rotors see edgewise flow in transition and are "
                               "stopped and locked in cruise; pylon/boom frequency placement is covered by the Campbell diagram")
    (HERE / "results" / "dynamics.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k not in ("modes",)}, indent=1, default=float)[:5000])
    print("modes:", [round(md["f_hz"], 1) for md in modes[:40]])


def torsion_frequency(m, fr, V):
    """First wing-torsion-dominated frequency: the lowest mode whose box-line pitch motion (rotation about y times
    the semi-chord) carries at least 30 % of the wing modal displacement; falls back to the most torsional mode."""
    rows = []
    for k, fk in enumerate(fr):
        if fk < 0.5:
            continue
        v = V[:, k].reshape(-1, 6)
        wing = m["front"] + m["rear"] + m["box"]
        tw = np.sum((v[m["box"], 4] * 0.6) ** 2)
        tr = np.sum(v[wing, :3] ** 2) + 1e-30
        rows.append((float(fk), float(tw / (tw + tr))))
    for fk, r in rows:
        if r > 0.3:
            return fk, r
    return max(rows, key=lambda t: t[1])


def plot_vg(arr, VD):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 1, figsize=(6.5, 6), dpi=130, sharex=True)
    for j in range(min(arr.shape[1], 12)):
        sel = arr[:, j, 0] < 3 * VD
        axs[0].plot(arr[sel, j, 0], arr[sel, j, 1], lw=1)
        axs[1].plot(arr[sel, j, 0], arr[sel, j, 2] / 2 / math.pi, lw=1)
    for ax in axs:
        ax.axvline(1.2 * VD, color="k", ls="--", lw=0.8)
        ax.grid(alpha=0.3)
    axs[0].axhline(0.02, color="#d1495b", lw=0.8)
    axs[0].set_ylim(-0.6, 0.2)
    axs[0].set_ylabel("required damping g")
    axs[1].set_ylabel("frequency (Hz)")
    axs[1].set_xlabel("V (m/s, sea level)")
    axs[0].set_title("Modal flutter (k-method), dashed: 1.2 VD", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUTIMG / "flutter_vg.png")
    plt.close(fig)


def plot_campbell(modes, exc, lift, push):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), dpi=130)
    for ax, (title, sel, rr) in zip(axs, (("Lift rotors", "lift", lift), ("Pusher", "pusher", push))):
        rpm = np.linspace(0, rr["rpm_max"] * 1.15, 50)
        for md in modes:
            if md["f_hz"] > 130:
                continue
            col = "#d1495b" if (md["shape"].get("hubs", 0) + md["shape"].get("booms", 0)) > 0.4 else "0.6"
            ax.axhline(md["f_hz"], color=col, lw=0.6, alpha=0.8)
        for nm, nP, r in exc:
            if not nm.startswith(sel):
                continue
            ax.plot(rpm, nP * rpm / 60, lw=1.6, label=nm)
            ax.fill_between([r["rpm_min"], r["rpm_max"]], 0, 130, color="#1f5fa8", alpha=0.06)
        ax.axvline(rr.get("rpm_hover", rr.get("rpm_cruise")), color="k", ls="--", lw=0.8)
        ax.set_xlim(0, rpm[-1])
        ax.set_ylim(0, 130)
        ax.set_xlabel("rotor speed (rpm)")
        ax.set_ylabel("frequency (Hz)")
        ax.set_title(f"Campbell diagram - {title} (red: boom/rotor modes)", fontsize=9)
        ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTIMG / "campbell.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
