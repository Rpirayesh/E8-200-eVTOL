"""Validation plots and tables from validation/cfd/data/*.json -> validation/cfd/img/*.png, data/summary.json.

    python cfd/tools/report.py neuralfoil     # NeuralFoil (XFOIL-trained) reference polars
    python cfd/tools/report.py                # all plots + summary
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foamcase import VAL  # noqa: E402
from gci import celik  # noqa: E402

DATA, IMG, REF = VAL / "data", VAL / "img", VAL / "reference"
TMR = REF / "tmr_naca0012"


def jload(name):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else None


def tec_zones(path: Path) -> dict:
    zones, cur = {}, "data"
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.lower().startswith("zone"):
            cur = s.split("=", 1)[-1].strip().strip('"')
            zones[cur] = []
        elif s and (s[0] in "-.0123456789"):
            zones.setdefault(cur, []).append([float(v) for v in s.split()])
    return {k: np.array(v) for k, v in zones.items() if v}


# ----------------------------------------------------------------------------- NeuralFoil
def neuralfoil():
    import aerosandbox as asb
    import neuralfoil as nf
    from airfoil2d import gaw1, tmr_naca0012
    out = {}

    def pol(coords, re, alphas):
        r = nf.get_aero_from_airfoil(asb.Airfoil(coordinates=coords), alpha=np.array(alphas, float), Re=re, model_size="xxxlarge",
                                     n_crit=9.0, xtr_upper=0.05, xtr_lower=0.05)
        return dict(alpha=list(map(float, alphas)), Cl=np.ravel(r["CL"]).tolist(), Cd=np.ravel(r["CD"]).tolist(),
                    Cm=np.ravel(r["CM"]).tolist(), confidence=np.ravel(r["analysis_confidence"]).tolist())
    a = list(range(-4, 23))
    n12 = tmr_naca0012(201)
    out["naca0012_re6e6_trip5pc"] = pol(n12, 6e6, a)
    closed, raw = gaw1("closed")
    sm, _ = gaw1("blunt")
    for re in (4.3e6, 6.3e6):
        out[f"gaw1_closed_re{re / 1e6:.1f}e6_trip5pc"] = pol(closed[::3], re, a)
        out[f"gaw1_blunt_re{re / 1e6:.1f}e6_trip5pc"] = pol(sm[::3], re, a)
    (DATA / "neuralfoil.json").write_text(json.dumps(out, indent=1))
    print("neuralfoil written")


# ----------------------------------------------------------------------------- figures
def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "legend.frameon": False})
    return plt


def fig_n0012(summary):
    plt = plt_setup()
    pol = jload("n0012_polar.json")
    if not pol:
        return
    of = [r for r in pol["openfoam"] if "Cl" in r]
    lad = tec_zones(TMR / "CLCD_Ladson_expdata.dat")
    cfl = tec_zones(TMR / "n0012clcd_cfl3d_sst.dat")["data"]
    gre = tec_zones(TMR / "CL_Gregory_expdata.dat")
    nfo = (jload("neuralfoil.json") or {}).get("naca0012_re6e6_trip5pc")
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=140)
    al = np.array([r["alpha"] for r in of]); cl = np.array([r["Cl"] for r in of]); cd = np.array([r["Cd"] for r in of])
    unst = np.array([r["Cl_std"] > 0.01 for r in of])
    for k, mk in zip(lad, ("s", "^", "v")):
        ax[0].plot(lad[k][:, 0], lad[k][:, 1], mk, ms=3.5, mfc="none", color="0.45", label=f"Ladson 1988, {k}")
        ax[1].plot(lad[k][:, 2], lad[k][:, 1], mk, ms=3.5, mfc="none", color="0.45")
    for k in gre:
        ax[0].plot(gre[k][:, 0], gre[k][:, 1], "d", ms=3.5, mfc="none", color="C2", label="Gregory & O'Reilly")
    ax[0].plot(cfl[:, 0], cfl[:, 1], "x", ms=8, mew=2, color="k", label="CFL3D SST, 897x257 (TMR)")
    ax[1].plot(cfl[:, 2], cfl[:, 1], "x", ms=8, mew=2, color="k")
    if nfo:
        ax[0].plot(nfo["alpha"], nfo["Cl"], "-", color="C1", lw=1, label="NeuralFoil (XFOIL-based), trip 5 %")
        ax[1].plot(nfo["Cd"], nfo["Cl"], "-", color="C1", lw=1)
    ax[0].plot(al[~unst], cl[~unst], "o-", color="C0", label="OpenFOAM SST, 512x256 (L2)")
    ax[0].plot(al[unst], cl[unst], "o", color="C3", mfc="none", label="OpenFOAM, unsteady (CL_std>0.01)")
    ax[1].plot(cd[~unst], cl[~unst], "o-", color="C0")
    ax[0].set(xlabel="alpha (deg)", ylabel="cl", xlim=(-1, 21), ylim=(-0.1, 1.9))
    ax[1].set(xlabel="cd", ylabel="cl", xlim=(0.006, 0.03), ylim=(-0.1, 1.9))
    ax[0].legend(fontsize=7, loc="upper left")
    fig.suptitle("NACA 0012, Re 6 million: OpenFOAM k-omega SST vs NASA TMR data")
    fig.tight_layout(); fig.savefig(IMG / "n0012_polar.png"); plt.close(fig)
    # Cp / Cf
    cpc = tec_zones(TMR / "n0012cp_cfl3d_sst.dat"); cfc = tec_zones(TMR / "n0012cf_cfl3d_sst.dat")
    cpg = tec_zones(TMR / "CP_Gregory_expdata.dat")
    surf = dict(pol.get("surface", {}))
    from foamcase import CACHE
    for a_, f_ in (("0", "surf_L1_a00.0.json"), ("10", "surf_L1_a10.0.json")):   # finest-grid surface data where available
        fp = CACHE / "cfd2d" / "n0012_grid" / f_
        if fp.exists():
            surf[a_] = json.loads(fp.read_text())
    fig, ax = plt.subplots(2, 3, figsize=(12, 6.5), dpi=140)
    for j, a in enumerate(("0", "10", "15")):
        s = surf.get(a) or surf.get(a + ".0") or surf.get(str(float(a)))
        k = f"alpha={a}"
        if k in cpc:
            ax[0, j].plot(cpc[k][:, 0], cpc[k][:, 1], "k-", lw=0.8, label="CFL3D SST")
        if k in cpg:
            ax[0, j].plot(cpg[k][:, 0], cpg[k][:, 1], "s", ms=3, mfc="none", color="0.4", label="Gregory & O'Reilly")
        for z in cfc:
            if z.replace(" ", "").lower().startswith(f"alpha={a},upper") or z.replace(" ", "").lower() == f"alpha={a}":
                ax[1, j].plot(cfc[z][:, 0], cfc[z][:, 1], "k-", lw=0.8, label="CFL3D SST (upper)")
        if s:
            x, cp, cf, side = np.array(s["x"]), np.array(s["cp"]), np.array(s["cf"]), np.array(s["side"])
            ax[0, j].plot(x, cp, ".", ms=1.5, color="C0", label="OpenFOAM SST " + ("1024 x 512" if a != "15" else "512 x 256"))
            up = np.array(s["y"]) >= 0          # symmetric section: upper surface = y >= 0
            o = np.argsort(x[up])
            ax[1, j].plot(x[up][o], cf[up][o], "-", color="C0", lw=1, label="OpenFOAM (upper)")
        ax[0, j].invert_yaxis(); ax[0, j].set(title=f"alpha {a} deg", xlabel="x/c", ylabel="Cp")
        ax[1, j].set(xlabel="x/c", ylabel="Cf", ylim=(-0.002, 0.012 if a == "0" else 0.03))
        ax[0, j].legend(fontsize=7); ax[1, j].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(IMG / "n0012_cp_cf.png"); plt.close(fig)
    rows = []
    cfl_d = {round(r[0]): r for r in cfl}
    for r in of:
        c = cfl_d.get(round(r["alpha"]))
        rows.append(dict(alpha=r["alpha"], Cl=r["Cl"], Cd=r["Cd"], Cl_std=r["Cl_std"],
                         Cl_cfl3d=c[1] if c is not None else None, Cd_cfl3d=c[2] if c is not None else None))
    summary["n0012_polar"] = rows


def fig_grid(summary):
    plt = plt_setup()
    g = jload("n0012_grid_study_raw.json")
    if not g:
        return
    cfl = {round(r[0]): r for r in tec_zones(TMR / "n0012clcd_cfl3d_sst.dat")["data"]}
    out = {}
    fig, ax = plt.subplots(2, 3, figsize=(12, 6), dpi=140)
    for j, a in enumerate((0.0, 10.0, 15.0)):
        rows = sorted([r for r in g if r["alpha"] == a and "Cl" in r and r["iterations"] > 1000], key=lambda r: -r["cells"])
        if len(rows) < 3:
            continue
        h = [1 / math.sqrt(r["cells"]) for r in rows]
        for i, q in enumerate(("Cl", "Cd")):
            f = [r.get(q + "_limit", r[q]) for r in rows]   # iteratively extrapolated where a slow drift remained
            res = celik(tuple(h[:3]), tuple(f[:3])) if not (q == "Cl" and a == 0) else {}
            res4 = celik(tuple(h[1:4]), tuple(f[1:4])) if len(rows) >= 4 and not (q == "Cl" and a == 0) else {}
            out[f"a{a:g}_{q}"] = dict(grids=[dict(grid=r["grid"], cells=r["cells"], value=r[q], value_iter_limit=r.get(q + "_limit"),
                                                  iter_err=r.get(q + "_iter_err"), it=r["iterations"]) for r in rows],
                                      gci_fine3=res, gci_coarse3=res4)
            ax[i, j].plot(np.array(h) * 1e3, f, "o-", label="OpenFOAM, nested grids")
            if res.get("f_ext") is not None and "p" in res:
                ax[i, j].plot([0], [res["f_ext"]], "*", ms=10, color="C3", label=f"Richardson (p_obs={res['p']:.2f}, used {res['p_used']:.2f})")
            c = cfl.get(round(a))
            if c is not None:
                ax[i, j].axhline(c[1 if q == "Cl" else 2], color="k", lw=0.8, ls="--", label="CFL3D SST 897x257")
            ax[i, j].set(xlabel="h = 1000 / sqrt(cells)", ylabel=q.lower(), title=f"alpha {a:g} deg", xlim=(-0.3, None))
            ax[i, j].legend(fontsize=7)
    fig.suptitle("NACA 0012, Re 6e6: nested grid family (ratio 2), far field 500 c")
    fig.tight_layout(); fig.savefig(IMG / "n0012_grid_convergence.png"); plt.close(fig)
    summary["grid_study"] = out


def fig_gaw1(summary):
    plt = plt_setup()
    d = jload("gaw1_polar.json")
    if not d:
        return
    exp = {}
    for line in (REF / "gaw1_TND7428_fig12b_digitized.csv").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        k, re, a, cl, cd = line.split(",")
        exp.setdefault((k, float(re)), []).append([float(a) if a else np.nan, float(cl), float(cd) if cd else np.nan])
    nfo = jload("neuralfoil.json") or {}
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=140)
    summ = {}
    for re, col in ((4.3e6, "C0"), (6.3e6, "C2")):
        L = np.array(exp[("lift", re)]); D = np.array(exp[("drag", re)])
        ax[0].plot(L[:, 0], L[:, 1], "s", ms=4, mfc="none", color=col, label=f"TN D-7428 exp., Re {re / 1e6:.1f}e6 (fixed transition)")
        ax[1].plot(D[:, 2], D[:, 1], "s", ms=4, mfc="none", color=col)
        rows = sorted([r for r in d["openfoam"] if r.get("Re") == re and "Cl" in r], key=lambda r: r["alpha"])
        al = np.array([r["alpha"] for r in rows]); cl = np.array([r["Cl"] for r in rows]); cd = np.array([r["Cd"] for r in rows])
        un = np.array([r["Cl_std"] > 0.01 for r in rows])
        ax[0].plot(al[~un], cl[~un], "o-", color=col, ms=3, label=f"OpenFOAM SST, Re {re / 1e6:.1f}e6")
        ax[0].plot(al[un], cl[un], "o", color="C3", mfc="none", ms=5)
        ax[1].plot(cd[~un], cl[~un], "o-", color=col, ms=3)
        k = f"gaw1_blunt_re{re / 1e6:.1f}e6_trip5pc"
        if k in nfo:
            ax[0].plot(nfo[k]["alpha"], nfo[k]["Cl"], "--", color=col, lw=0.9, label=f"NeuralFoil, Re {re / 1e6:.1f}e6")
            ax[1].plot(nfo[k]["Cd"], nfo[k]["Cl"], "--", color=col, lw=0.9)
        lin = (al >= -4) & (al <= 8.01)
        cla, cl0 = np.polyfit(al[lin], cl[lin], 1)
        Ll = L[(L[:, 0] >= -4.1) & (L[:, 0] <= 8.1)]
        cla_e, cl0_e = np.polyfit(Ll[:, 0], Ll[:, 1], 1)
        ok = ~un
        i = int(np.argmax(np.where(ok, cl, -9)))
        D_cd = np.interp(0.5, D[:, 1], D[:, 2])
        summ[f"Re{re / 1e6:.1f}e6"] = dict(cl_alpha_cfd=cla, cl_alpha_exp=cla_e, alpha0_cfd=-cl0 / cla, alpha0_exp=-cl0_e / cla_e,
                                           clmax_cfd=float(cl[i]), alpha_clmax_cfd=float(al[i]),
                                           clmax_cfd_mean_incl_unsteady=float(cl.max()), alpha_clmax_mean=float(al[np.argmax(cl)]),
                                           clmax_exp=float(L[:, 1].max()),
                                           alpha_clmax_exp=float(L[np.argmax(L[:, 1]), 0]),
                                           cd_at_cl05_cfd=float(np.interp(0.5, cl[(al >= -4) & (al <= 8)], cd[(al >= -4) & (al <= 8)])),
                                           cd_at_cl05_exp=float(D_cd))
        if k in nfo:
            a_n = np.array(nfo[k]["alpha"]); c_n = np.array(nfo[k]["Cl"])
            summ[f"Re{re / 1e6:.1f}e6"]["clmax_neuralfoil"] = float(c_n.max())
            summ[f"Re{re / 1e6:.1f}e6"]["cd_at_cl05_neuralfoil"] = float(np.interp(0.5, c_n[a_n <= 8], np.array(nfo[k]["Cd"])[a_n <= 8]))
    ax[0].set(xlabel="alpha (deg)", ylabel="cl", xlim=(-9, 23)); ax[1].set(xlabel="cd", ylabel="cl", xlim=(0.005, 0.03))
    ax[0].legend(fontsize=6.5, loc="upper left")
    fig.suptitle("NASA LS(1)-0417 / GA(W)-1, M 0.15 data, roughness at 0.08c: OpenFOAM SST (fully turbulent) vs experiment")
    fig.tight_layout(); fig.savefig(IMG / "gaw1_polar.png"); plt.close(fig)
    summary["gaw1"] = summ


def fig_rotor(summary):
    plt = plt_setup()
    d = jload("rotor_disk.json")
    if not d:
        return
    iso = d.get("isolated", [])
    if iso:
        fig, ax = plt.subplots(1, 3, figsize=(13, 4), dpi=140)
        ax[0].axhline(2.0, color="k", ls="--", lw=1, label="momentum theory, far wake (2 v_i)")
        ax[0].plot([0], [1.0], "kx", ms=8, label="momentum theory, disk-average at the disk (v_i)")
        for r in iso:
            z = [s["z_over_R"] for s in r["slices"]]
            ax[0].plot(z, [s["w_core_over_vi"] for s in r["slices"]], "o-", ms=3, label=f"{r['case']} core r<0.3R ({r['cells'] / 1e3:.0f}k cells)")
            ax[0].plot(z, [s["w_mean_disk_over_vi"] for s in r["slices"]], "s:", ms=3, label=f"{r['case']} mean over r<R")
            ax[1].plot(z, [s["r_half_over_R"] for s in r["slices"]], "o-", ms=3, label=f"{r['case']} half-velocity radius")
            ax[1].plot(z, [s["r_momentum_over_R"] for s in r["slices"]], "s:", ms=3, label=f"{r['case']} momentum radius")
        ax[1].axhline(1 / math.sqrt(2), color="k", ls="--", lw=1, label="momentum theory, far wake (R/sqrt 2)")
        for s in iso[-1]["slices"]:
            ax[2].plot(s["profile_r_over_R"], s["profile_w_over_vi"], lw=1, label=f"z = {s['z_over_R']:g} R")
        ax[0].set(xlabel="z / R (below disk < 0)", ylabel="core downwash / v_i", title="slipstream downwash", ylim=(0.8, 2.4))
        ax[1].set(xlabel="z / R", ylabel="r_1/2 / R", title="slipstream radius", ylim=(0.5, 1.6))
        ax[2].set(xlabel="r / R", ylabel="w / v_i", title=f"profiles, {iso[-1]['case']}", xlim=(0, 2))
        for a in ax:
            a.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(IMG / "rotor_isolated.png"); plt.close(fig)
    dl = d.get("download", [])
    if dl:
        fig, ax = plt.subplots(figsize=(6, 3.6), dpi=140)
        for r in dl:
            ax.plot(r["history_it"], r["history_DL_over_T"], lw=0.8, label=f"{r['case']}: mean {r['DL_over_T']:.3f}")
        ax.axhspan(0.151, 0.161, color="0.8", label="Felker & Light 1986, CT 0.004-0.009")
        ax.set(xlabel="iteration", ylabel="DL / T", ylim=(0, 0.3)); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(IMG / "rotor_download.png"); plt.close(fig)
    summary["rotor"] = dict(isolated=[{k: v for k, v in r.items() if k not in ("axis",)} | {"slices": [
        {k: v for k, v in s.items() if not k.startswith("profile")} for s in r["slices"]]} for r in iso],
        download=[{k: v for k, v in r.items() if not k.startswith("history")} for r in dl])


def fig_wing3d(summary):
    plt = plt_setup()
    d = jload("wing3d.json")
    if not d:
        return
    th = d["theory"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=140)
    a = np.linspace(0, 10, 20)
    ax[0].plot(a, th["lifting_line"]["CL_alpha_per_rad"] * np.radians(a), "k--", lw=1, label="lifting line (a0 from 2-D CFD)")
    ax[0].plot(a, th["helmbold_CL_alpha_per_rad"] * np.radians(a), "k:", lw=1, label="Helmbold / DATCOM")
    for lev in sorted({r["lev"] for r in d["runs"]}):
        rr = sorted([r for r in d["runs"] if r["lev"] == lev], key=lambda r: r["alpha"])
        ax[0].plot([r["alpha"] for r in rr], [r["CL"] for r in rr], "o-", ms=4, label=f"OpenFOAM mesh L{lev:+d} ({rr[0]['cells'] / 1e6:.1f} M)")
        ax[1].plot([r["CL"] ** 2 for r in rr], [r["CD"] for r in rr], "o-", ms=4, label=f"CFD total, L{lev:+d}")
        ri = [r for r in rr if r.get("CDi_rel_zero_lift") is not None]
        ax[1].plot([0] + [r["CL"] ** 2 for r in ri], [0] + [r["CDi_rel_zero_lift"] for r in ri], "s--", ms=3,
                   label=f"CFD lift-dependent drag (CD - CD(0) - profile increase), L{lev:+d}")
    c2 = np.linspace(0, 0.5, 10)
    AR = 8.0
    ax[1].plot(c2, c2 / (math.pi * AR * th["lifting_line"]["e"]), "k--", lw=1, label=f"lifting line induced, e = {th['lifting_line']['e']:.3f}")
    cdp = th["cd_profile_fit"]
    ax[1].plot(c2, cdp["cd0"] + cdp["k2"] * c2 + c2 / (math.pi * AR * th["lifting_line"]["e"]), "k:", lw=1,
               label="lifting line + 2-D CFD profile drag (total)")
    ax[0].set(xlabel="alpha (deg)", ylabel="CL"); ax[1].set(xlabel="CL^2", ylabel="CD")
    ax[0].legend(fontsize=7); ax[1].legend(fontsize=6.5)
    fig.suptitle("Rectangular NACA 0012 wing, AR 8, Re 3e6, snappyHexMesh + wall functions")
    fig.tight_layout(); fig.savefig(IMG / "wing3d.png"); plt.close(fig)
    summary["wing3d"] = dict(theory={k: v for k, v in th.items() if k != "lifting_line"} | {
        "lifting_line": {k: th["lifting_line"][k] for k in ("CL_alpha_per_rad", "e", "delta")}},
        runs=d["runs"], CL_alpha_per_rad_by_level=d.get("CL_alpha_per_rad_by_level"))


def tables(summary):
    for name in ("n0012_wallfn.json", "n0012_fsturb.json", "n0012_re3e6.json"):
        d = jload(name)
        if d:
            summary[name.replace(".json", "")] = d if isinstance(d, list) else d.get("openfoam")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "neuralfoil":
        neuralfoil()
        return
    IMG.mkdir(parents=True, exist_ok=True)
    summary = {}
    for f in (fig_n0012, fig_grid, fig_gaw1, fig_rotor, fig_wing3d, tables):
        try:
            f(summary)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f.__name__, "failed:", e)
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(json.dumps({k: (v if k in ("gaw1",) else "...") for k, v in summary.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
