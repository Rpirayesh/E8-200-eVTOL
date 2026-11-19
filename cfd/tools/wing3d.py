"""Finite-wing validation of the 3-D snappyHexMesh + wall-function set-up at full-scale Reynolds number.

Rectangular NACA 0012 wing, chord 1 m, span 8 m (AR 8, square tips), 45 m/s, Re 3.0e6, half model.
Lift-curve slope and induced drag are compared with Prandtl lifting-line theory (Glauert series, own
implementation) using the 2-D section lift slope and profile drag of the validated 2-D set-up, with the
DATCOM/Helmbold formula and with the aerosandbox vortex-lattice method.

    python cfd/tools/wing3d.py mesh --lev 0|-1|1      # baseline / coarse / fine surface refinement
    python cfd/tools/wing3d.py run  --lev 0 --alphas 0 2 4 8
    python cfd/tools/wing3d.py theory                  # lifting line, Helmbold, VLM -> data/wing3d_theory.json
    python cfd/tools/wing3d.py post
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesh3d  # noqa: E402
from foamcase import CACHE, MAX_CORES, VAL, coeffs  # noqa: E402

WORK = CACHE / "wing3d"
DATA = VAL / "data"
C, B, U, NU, RHO = 1.0, 8.0, 45.0, 1.5e-5, 1.225
AR = B / C
FIRST_LAYER = 0.5e-3          # m: cell-centre y+ ~ 25-40 over most of the chord (2-D study: y+ 60-120 degrades
                               #    separation onset and drag, y+ ~ 30 reproduces the wall-resolved result)


def stl(out: Path):
    import oml
    secs = [dict(x_le=0.0, y=y, z=0.0, chord=C, twist_deg=0.0) for y in (-B / 2, B / 2)]
    m = oml.lifting_surface(secs, "naca0012", n=201)[0]
    out.mkdir(parents=True, exist_ok=True)
    m.export(out / "wing.stl")
    return m


def mesh(lev: int, nproc: int):
    case = WORK / f"mesh_L{lev:+d}"
    if (case / "mesh_info.json").exists():
        print("mesh exists", lev)
        return
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    stl(case / "stl")
    # background cells must not have faces on the chord plane or at the LE/TE (castellation would be asymmetric)
    bounds = ((-15.37, 0.0, -15.31), (29.63, 20.0, 14.69))
    mesh3d.write_block_mesh(case, bounds, 1.0, symmetry="ymin")
    surfaces = {"wing": dict(level=(6 + lev, 7 + lev), layers=9, feature_level=7 + lev)}
    regions = [
        dict(name="near5", shape="box", min=(-0.25, 0, -0.18), max=(1.35, 4.25, 0.18), level=5 + lev),
        dict(name="near4", shape="box", min=(-0.6, 0, -0.5), max=(2.2, 4.7, 0.5), level=4 + lev),
        dict(name="wake3", shape="box", min=(0.5, 0, -0.9), max=(10.0, 5.5, 0.9), level=3 + lev),
        dict(name="tip5", shape="cylinder", p1=(0.6, 4.0, 0.0), p2=(5.0, 3.95, 0.1), radius=0.2, level=5 + lev),
        dict(name="far2", shape="box", min=(-3, 0, -3), max=(14, 8, 3), level=2 + lev),
    ]
    mesh3d.write_snappy(case, surfaces, regions, (-10.03, 15.07, 10.11), dict(first=FIRST_LAYER, expansion=1.25))
    mesh3d.write_solver(case, U=(U, 0, 0), nu=NU, rho=RHO, iters=1, sym_patches=["sym_ymin"], coeff=None, force_patches=[])
    info = mesh3d.mesh(case, case / "stl", ["wing"], nproc)
    (case / "mesh_info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


def run(lev: int, alphas, iters: int, nproc: int, jobs: int = 1):
    src = WORK / f"mesh_L{lev:+d}"

    def one(a):
        case = WORK / f"run_L{lev:+d}_a{a:+05.1f}"

        def setup():
            mesh3d.copy_mesh(src, case)
            ar = math.radians(a)
            coeff = dict(lift=(-math.sin(ar), 0, math.cos(ar)), drag=(math.cos(ar), 0, math.sin(ar)), lref=C, aref=C * B / 2)
            mesh3d.write_solver(case, U=(U * math.cos(ar), 0, U * math.sin(ar)), nu=NU, rho=RHO, iters=iters, sym_patches=["sym_ymin"],
                                coeff=coeff, force_patches=["wing"], cofr=(0.25 * C, 0, 0), tu=0.001, visc_ratio=1.0,
                                extra_functions=span_load_function())
        mesh3d.run_or_resume(case, nproc, setup)

    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(one, alphas))


def span_load_function() -> str:
    """Spanwise lift distribution: forces on 16 spanwise bins (binField)."""
    return """    spanLoad
    {
        type forces; libs (forces); patches (wing); rho rhoInf; rhoInf 1.225; CofR (0.25 0 0);
        writeControl writeTime;
        binData { nBin 16; direction (0 1 0); cumulative no; }
    }
"""


# ----------------------------------------------------------------------------- theory
def lifting_line(a0: float, AR_: float, alpha_rad: float = 1.0, n: int = 400) -> dict:
    """Prandtl lifting line (Glauert sine series) for an untwisted rectangular wing, section slope a0 (/rad)."""
    th = np.linspace(0, np.pi, n + 2)[1:-1]
    k = np.arange(1, 2 * n, 2)                      # odd terms (symmetric loading)
    mu = a0 / (4 * AR_)                             # a0 c / (4 b), c = b / AR
    Amat = np.sin(np.outer(th, k)) * (mu * k[None, :] + np.sin(th)[:, None])
    rhs = mu * alpha_rad * np.sin(th)
    A = np.linalg.lstsq(Amat, rhs, rcond=None)[0]
    CL = np.pi * AR_ * A[0]
    delta = float(np.sum(k[1:] * (A[1:] / A[0]) ** 2))
    y = -np.cos(th)                                 # y / (b/2)
    gamma_ratio = np.sin(np.outer(th, k)) @ A       # Gamma / (2 b U)
    cl_local = 4 * AR_ * gamma_ratio                # cl = 2 Gamma / (U c) = 4 (b/c) Gamma / (2 b U)
    return dict(CL_alpha_per_rad=CL / alpha_rad, e=1 / (1 + delta), delta=delta, y=y.tolist(),
                cl_over_CL=(cl_local / CL).tolist())


def helmbold(a0: float, AR_: float) -> float:
    k = a0 / (math.pi * AR_)
    return a0 / (math.sqrt(1 + k**2) + k)


def vlm_flat(AR_: float) -> dict:
    import aerosandbox as asb
    wing = asb.Wing(symmetric=True, xsecs=[asb.WingXSec(xyz_le=[0, 0, 0], chord=1.0, airfoil=asb.Airfoil("naca0012")),
                                           asb.WingXSec(xyz_le=[0, AR_ / 2, 0], chord=1.0, airfoil=asb.Airfoil("naca0012"))])
    plane = asb.Airplane(wings=[wing], s_ref=AR_, c_ref=1.0, b_ref=AR_)
    out = {}
    for a in (2.0, 4.0):
        r = asb.VortexLatticeMethod(plane, asb.OperatingPoint(velocity=45, alpha=a), spanwise_resolution=24, chordwise_resolution=12).run()
        out[a] = dict(CL=float(r["CL"]), CDi=float(r["CD"]))
    cla = (out[4.0]["CL"] - out[2.0]["CL"]) / math.radians(2.0)
    e = out[4.0]["CL"] ** 2 / (math.pi * AR_ * out[4.0]["CDi"])
    return dict(CL_alpha_per_rad=cla, e=e, points=out)


def theory():
    """2-D slope and profile-drag polar of the NACA 0012 at Re 3e6 from the 2-D wall-function runs."""
    d2 = json.loads((DATA / "n0012_re3e6.json").read_text())
    rows = [r for r in d2["openfoam"] if r.get("wall") == "resolved"]
    al = np.radians([r["alpha"] for r in rows]); cl = np.array([r["Cl"] for r in rows]); cd = np.array([r["Cd"] for r in rows])
    a0 = float(np.polyfit(al, cl, 1)[0])
    k2, cd0 = np.polyfit(cl**2, cd, 1)
    ll = lifting_line(a0, AR)
    ll2pi = lifting_line(2 * math.pi, AR)
    res = dict(a0_per_rad=a0, a0_source="2-D OpenFOAM SST, NACA 0012, Re 3e6, wall-resolved 512 x 256 grid (alpha 0, 4, 8)",
               cd_profile_fit=dict(cd0=float(cd0), k2=float(k2)),
               lifting_line=ll, lifting_line_2pi=dict(CL_alpha_per_rad=ll2pi["CL_alpha_per_rad"], e=ll2pi["e"]),
               helmbold_CL_alpha_per_rad=helmbold(a0, AR))
    try:
        res["vlm_aerosandbox"] = vlm_flat(AR)
    except Exception as e:  # noqa: BLE001
        res["vlm_aerosandbox"] = dict(error=str(e))
    (DATA / "wing3d_theory.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "lifting_line"}, indent=1), ll["CL_alpha_per_rad"], ll["e"])


def post():
    th = json.loads((DATA / "wing3d_theory.json").read_text())
    ll = th["lifting_line"]
    cd0, k2 = th["cd_profile_fit"]["cd0"], th["cd_profile_fit"]["k2"]
    y = np.array(ll["y"]); r = np.array(ll["cl_over_CL"])
    res = dict(theory=th, runs=[])
    for case in sorted(WORK.glob("run_L*")):
        lev = int(case.name.split("_L")[1].split("_")[0])
        a = float(case.name.split("_a")[1])
        try:
            c = coeffs(case, avg=200, fo="coeffs")
        except Exception as e:  # noqa: BLE001
            print(case, e)
            continue
        CL = c["Cl"]
        # profile drag by strip integration of the 2-D polar with the lifting-line span loading
        cdp = float(np.trapezoid(cd0 + k2 * (CL * r) ** 2, y) / 2) if CL else cd0
        CDi = c["Cd"] - cdp
        info = json.loads((WORK / f"mesh_L{lev:+d}" / "mesh_info.json").read_text())
        res["runs"].append(dict(lev=lev, alpha=a, CL=CL, CD=c["Cd"], Cm=c["CmPitch"], CL_std=c["Cl_std"], CD_std=c["Cd_std"],
                                iterations=c["iterations"], CD_profile_strip=cdp, CDi=CDi,
                                e_cfd=(CL**2 / (math.pi * AR * CDi)) if abs(CL) > 0.05 and CDi > 0 else None,
                                cells=info.get("cells"), layers=info.get("layers"), mesh_ok=info.get("mesh_ok")))
    # induced drag relative to the CFD's own zero-lift drag (removes the zero-lift profile-drag error of the mesh)
    for r in res["runs"]:
        r0 = next((x for x in res["runs"] if x["lev"] == r["lev"] and x["alpha"] == 0.0), None)
        if r0 and abs(r["CL"]) > 0.05:
            dcdp = float(np.trapezoid(k2 * (r["CL"] * np.array(ll["cl_over_CL"])) ** 2, np.array(ll["y"])) / 2)
            r["CDi_rel_zero_lift"] = r["CD"] - r0["CD"] - dcdp
            r["e_cfd_rel_zero_lift"] = (r["CL"] - r0["CL"]) ** 2 / (math.pi * AR * r["CDi_rel_zero_lift"]) if r["CDi_rel_zero_lift"] > 0 else None
    # lift slope per mesh level from the attached points
    slopes = {}
    for lev in sorted({r["lev"] for r in res["runs"]}):
        pts = sorted([(r["alpha"], r["CL"]) for r in res["runs"] if r["lev"] == lev and r["alpha"] <= 8.01])
        if len(pts) >= 2:
            al, cl = np.array(pts).T
            slopes[lev] = float(np.polyfit(np.radians(al), cl, 1)[0])
    res["CL_alpha_per_rad_by_level"] = slopes
    (DATA / "wing3d.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(slopes, indent=1))
    for r in res["runs"]:
        print({k: r.get(k) for k in ("lev", "alpha", "CL", "CD", "CDi_rel_zero_lift", "e_cfd_rel_zero_lift", "cells", "iterations")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["mesh", "run", "theory", "post", "stl"])
    ap.add_argument("--lev", type=int, default=0)
    ap.add_argument("--alphas", type=float, nargs="*", default=[0, 2, 4, 8])
    ap.add_argument("--iters", type=int, default=1500)
    ap.add_argument("--nproc", type=int, default=MAX_CORES)
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    if a.what == "mesh":
        mesh(a.lev, a.nproc)
    elif a.what == "run":
        run(a.lev, a.alphas, a.iters, a.nproc, a.jobs)
    elif a.what == "theory":
        theory()
    elif a.what == "post":
        post()
    elif a.what == "stl":
        m = stl(WORK / "stl")
        print(m.is_watertight, m.bounds)


if __name__ == "__main__":
    main()
