"""2-D airfoil RANS (OpenFOAM simpleFoam, k-omega SST) on structured O-grids at full-scale Reynolds number.

    python cfd/tools/airfoil2d.py grid-study    # NACA 0012, Re 6e6: 4 nested grids, alpha 0/10/15 (GCI)
    python cfd/tools/airfoil2d.py n0012-polar   # NACA 0012, Re 6e6 polar to stall on the production grid
    python cfd/tools/airfoil2d.py wallfn        # NACA 0012, Re 6e6: wall-resolved vs wall-function grids
    python cfd/tools/airfoil2d.py gaw1-polar    # NASA LS(1)-0417 (GA(W)-1), Re 4.3e6 and 6.3e6 polar to CLmax
    python cfd/tools/airfoil2d.py section --coords FILE --re RE [--alphas ...]   # any section (phase 2)

All cases are non-dimensional: chord 1, U 1, nu = 1/Re (incompressible).  Each angle of attack is an
independent case; cases run concurrently within the 12-core budget.  Scratch cases live in
cfd/.cache/cfd2d/, results go to validation/cfd/data/ (validation) or cfd/results/ (design work).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foamcase import CACHE, CFD, MAX_CORES, VAL, check_mesh_summary, coeffs, sh, wfile  # noqa: E402
from ogrid import build_ogrid_march, coarsen, inverted_cells, resample_surface, write_polymesh  # noqa: E402

RUNS = CACHE / "cfd2d"
DATA = VAL / "data"
REF = VAL / "reference"

# NASA TMR free-stream turbulence for the NACA 0012 validation case (Tu 0.052 %, nu_t/nu 0.009)
TU_TMR, VR_TMR = 0.00052, 0.009


# ----------------------------------------------------------------------------- geometry
def tmr_naca0012(n: int = 801) -> np.ndarray:
    """NASA TMR sharp-trailing-edge NACA 0012 (chord 1), TE -> upper -> LE -> lower."""
    b = np.linspace(0, np.pi, n)
    x = (1 - np.cos(b)) / 2
    y = 0.594689181 * (0.298222773 * np.sqrt(x) - 0.127125232 * x - 0.357907906 * x**2
                       + 0.291984971 * x**3 - 0.105174606 * x**4)
    up = np.column_stack([x[::-1], y[::-1]])
    lo = np.column_stack([x[1:-1], -y[1:-1]])
    return np.vstack([up, lo])


def naca4_closed(code: str, n: int = 401) -> np.ndarray:
    """NACA 4-digit with the closed-TE thickness coefficient (-0.1036), chord 1."""
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    x = (1 - np.cos(np.linspace(0, np.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    if m:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2))
        dy = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    else:
        yc = dy = np.zeros_like(x)
    th = np.arctan(dy)
    up = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])[::-1]
    lo = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])[1:-1]
    return np.vstack([up, lo])


def naca230(code: str, n: int = 401) -> np.ndarray:
    """NACA 230xx five-digit section (closed TE), chord 1."""
    t = int(code[3:]) / 100
    m, k1 = 0.2025, 15.957
    x = (1 - np.cos(np.linspace(0, np.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    yc = np.where(x < m, k1 / 6 * (x**3 - 3 * m * x**2 + m**2 * (3 - m) * x), k1 * m**3 / 6 * (1 - x))
    dy = np.where(x < m, k1 / 6 * (3 * x**2 - 6 * m * x + m**2 * (3 - m)), -k1 * m**3 / 6)
    th = np.arctan(dy)
    up = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])[::-1]
    lo = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])[1:-1]
    return np.vstack([up, lo])


def read_selig(path: Path) -> np.ndarray:
    """Selig-format coordinates (TE -> upper -> LE -> lower -> TE)."""
    rows = []
    for line in path.read_text().splitlines():
        try:
            v = [float(s) for s in line.split()]
        except ValueError:
            continue
        if len(v) == 2 and abs(v[0]) <= 1.5:
            rows.append(v)
    return np.array(rows)


def spline_contour(pts: np.ndarray, n: int = 801) -> np.ndarray:
    """Interpolating parametric cubic spline through a TE->upper->LE->lower->TE contour."""
    from scipy.interpolate import splev, splprep
    pts = np.asarray(pts, float)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9])
    pts = pts[keep]
    tck, u = splprep([pts[:, 0], pts[:, 1]], s=0, k=3)
    i_le = int(np.argmin(pts[:, 0]))
    u_le = u[i_le]
    t = (1 - np.cos(np.linspace(0, np.pi, n // 2 + 1))) / 2
    uu = np.concatenate([u_le * t, u_le + (1 - u_le) * t[1:]])
    x, y = splev(uu, tck)
    return np.column_stack([x, y])


def close_te(pts: np.ndarray, x0: float = 0.8) -> np.ndarray:
    """Close a blunt trailing edge by thinning the aft (1-x0) chord symmetrically about the mean
    of the two TE ordinates (quadratic blend, camber line unchanged)."""
    pts = pts.copy()
    i_le = int(np.argmin(pts[:, 0]))
    zu_te, zl_te = pts[0, 1], pts[-1, 1]
    half = 0.5 * (zu_te - zl_te)
    w = np.clip((pts[:, 0] - x0) / (1 - x0), 0, 1) ** 2
    pts[: i_le + 1, 1] -= half * w[: i_le + 1]
    pts[i_le + 1:, 1] += half * w[i_le + 1:]
    pts[-1] = pts[0]
    return pts


def round_te(pts: np.ndarray, n_arc: int = 25) -> np.ndarray:
    """Keep a blunt trailing edge and close it with a semicircular base on the line joining the two TE points
    (adds half the TE thickness to the chord).  The O-grid then wraps around the base without corners."""
    pu, pl = np.asarray(pts[0], float), np.asarray(pts[-1], float)
    c, r = 0.5 * (pu + pl), 0.5 * np.linalg.norm(pu - pl)
    b = (pu - pl) / (2 * r)
    n = np.array([b[1], -b[0]])
    if n[0] < 0:
        n = -n
    th = np.linspace(-np.pi / 2, np.pi / 2, n_arc)[1:-1]
    arc = c + r * (np.outer(np.cos(th), n) + np.outer(np.sin(th), b))
    return np.vstack([pts, arc])


def gaw1(te: str = "round") -> tuple[np.ndarray, np.ndarray]:
    """NASA LS(1)-0417 / GA(W)-1 from McGhee & Beasley (NASA TN D-7428, table I), 0.71 %-chord blunt TE.
    te = 'round' (blunt base closed by a semicircle, used for the CFD), 'closed' (aft 20 % thinned to a
    sharp TE) or 'blunt' (open contour as measured).  Returns (smooth contour, table points)."""
    raw = read_selig(REF / "ls417_coordinates_TND7428.dat")
    sm = spline_contour(raw, 1201)
    if te == "closed":
        return close_te(sm), raw
    if te == "round":
        return round_te(sm), raw
    return sm, raw


def plain_flap(pts: np.ndarray, delta_deg: float, x_hinge: float = 0.7, blend: float = 0.06) -> np.ndarray:
    """Deflect the aft (1 - x_hinge) chord TE-down by delta: the mean line is sheared down with a slope that
    rises smoothly from 0 to tan(delta) over +-blend chord around the hinge (sealed plain flap with a faired hinge,
    thickness kept vertical).  The projected chord is unchanged; the flap chord grows by 1/cos(delta) - 1."""
    pts = np.asarray(pts, float).copy()
    xs = np.linspace(0, 1.02, 4001)
    t = np.clip((xs - (x_hinge - blend)) / (2 * blend), 0, 1)
    slope = np.tan(np.radians(delta_deg)) * t * t * (3 - 2 * t)
    drop = np.concatenate([[0], np.cumsum(0.5 * (slope[1:] + slope[:-1]) * np.diff(xs))])
    pts[:, 1] -= np.interp(pts[:, 0], xs, drop)
    return pts


# ----------------------------------------------------------------------------- case set-up
def write_case(case: Path, alpha: float, re: float, iters: int, tu: float = TU_TMR, visc_ratio: float = VR_TMR,
               wall: str = "resolved", dz: float = 0.01, avg_window: int = 500, robust: bool = False):
    """Non-dimensional case: chord 1, |U| 1, nu 1/Re.  wall = 'resolved' (y+ ~ 1, low-Re SST)
    or 'wallfn' (Spalding nu_t wall function, blended omega).  Gradients are not limited: with
    cellLimited gradients the symmetric NACA 0012 converged to an asymmetric state (cl = 0.012 at
    alpha 0 on the 512 x 256 grid), see validation/cfd/README.md."""
    U, nu, chord = 1.0, 1.0 / re, 1.0
    a = math.radians(alpha)
    Ux, Uy = U * math.cos(a), U * math.sin(a)
    k = 1.5 * (U * tu) ** 2
    om = k / (visc_ratio * nu)
    empty = "    \"(front|back)\" { type empty; }\n"
    if wall == "resolved":
        kw, nutw = "type kLowReWallFunction; value uniform 1e-14;", "type nutLowReWallFunction; value uniform 0;"
    else:
        kw, nutw = f"type kqRWallFunction; value uniform {k};", "type nutUSpaldingWallFunction; value uniform 0;"
    wfile(case, "0/U", "volVectorField", "U", f"dimensions [0 1 -1 0 0 0 0];\ninternalField uniform ({Ux} {Uy} 0);\nboundaryField\n{{\n"
          f"    farfield {{ type freestreamVelocity; freestreamValue uniform ({Ux} {Uy} 0); }}\n"
          f"    airfoil {{ type noSlip; }}\n{empty}}}\n")
    wfile(case, "0/p", "volScalarField", "p", "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
          "    farfield { type freestreamPressure; freestreamValue uniform 0; }\n"
          f"    airfoil {{ type zeroGradient; }}\n{empty}}}\n")
    wfile(case, "0/k", "volScalarField", "k", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform {k};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {k}; value uniform {k}; }}\n"
          f"    airfoil {{ {kw} }}\n{empty}}}\n")
    wfile(case, "0/omega", "volScalarField", "omega", f"dimensions [0 0 -1 0 0 0 0];\ninternalField uniform {om};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {om}; value uniform {om}; }}\n"
          f"    airfoil {{ type omegaWallFunction; value uniform {om}; }}\n{empty}}}\n")
    wfile(case, "0/nut", "volScalarField", "nut", "dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
          "    farfield { type calculated; value uniform 0; }\n"
          f"    airfoil {{ {nutw} }}\n{empty}}}\n")
    wfile(case, "constant/transportProperties", "dictionary", "transportProperties", f"transportModel Newtonian;\nnu {nu:.10g};\n")
    wfile(case, "constant/turbulenceProperties", "dictionary", "turbulenceProperties",
          "simulationType RAS;\nRAS\n{\n    RASModel kOmegaSST;\n    turbulence on;\n    printCoeffs off;\n}\n")
    lift = (-math.sin(a), math.cos(a), 0)
    drag = (math.cos(a), math.sin(a), 0)
    wfile(case, "system/controlDict", "dictionary", "controlDict", f"""application simpleFoam;
startFrom latestTime; startTime 0; stopAt endTime; endTime {iters}; deltaT 1;
writeControl timeStep; writeInterval {min(iters, 250)}; purgeWrite 1; writeFormat binary; writePrecision 10; runTimeModifiable true;
functions
{{
    forceCoeffs
    {{
        type forceCoeffs; libs (forces); writeControl timeStep; writeInterval 1;
        patches (airfoil); rho rhoInf; rhoInf 1; CofR ({0.25 * chord} 0 0);
        liftDir ({lift[0]} {lift[1]} 0); dragDir ({drag[0]} {drag[1]} 0); pitchAxis (0 0 1);
        magUInf {U}; lRef {chord}; Aref {chord * dz};
    }}
    yPlus {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
    wallShearStress {{ type wallShearStress; libs (fieldFunctionObjects); patches (airfoil); writeControl writeTime; }}
    surf
    {{
        type surfaces; libs (sampling); writeControl writeTime; surfaceFormat raw; fields (p wallShearStress yPlus);
        surfaces {{ airfoil {{ type patch; patches (airfoil); interpolate false; }} }}
    }}
    residuals {{ type solverInfo; libs (utilityFunctionObjects); fields (U p k omega); writeControl timeStep; writeInterval 10; }}
}}
""")
    wfile(case, "system/fvSchemes", "dictionary", "fvSchemes", """ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss limitedLinear 1;
    div(phi,omega) bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
""")
    wfile(case, "system/fvSolution", "dictionary", "fvSolution", """solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-10; relTol 0.05; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-12; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 0; consistent yes; residualControl { p 2e-7; U 1e-8; "(k|omega)" 1e-8; } }
relaxationFactors { equations { U 0.85; ".*" 0.6; } fields { p 1; } }
""")
    if robust:   # flapped sections: limited gradients, non-orthogonal correction, lower relaxation (start-up diverged otherwise)
        fs = case / "system" / "fvSchemes"
        fs.write_text(fs.read_text().replace("gradSchemes { default Gauss linear; }",
                                             "gradSchemes { default cellLimited Gauss linear 1; }"))
        fv = case / "system" / "fvSolution"
        fv.write_text(fv.read_text().replace("nNonOrthogonalCorrectors 0", "nNonOrthogonalCorrectors 1")
                      .replace("equations { U 0.85; \".*\" 0.6; } fields { p 1; }", "equations { U 0.7; \".*\" 0.5; } fields { p 0.5; }"))


def run(case: Path, nproc: int = 1) -> None:
    sh("checkMesh", case, "log.checkMesh")
    if nproc > 1:
        wfile(case, "system/decomposeParDict", "dictionary", "decomposeParDict", f"numberOfSubdomains {nproc};\nmethod scotch;\n")
        sh("decomposePar -force", case, "log.decompose")
        sh(f"mpirun -np {nproc} simpleFoam -parallel", case, "log.simpleFoam")
        sh("reconstructPar -latestTime", case, "log.reconstruct")
        for d in case.glob("processor*"):
            shutil.rmtree(d, ignore_errors=True)
    else:
        sh("simpleFoam", case, "log.simpleFoam")


CORES = [MAX_CORES]


def run_pool(tasks: list[tuple[Path, int]], cores: int | None = None) -> None:
    """Run (case, nproc) tasks concurrently without exceeding `cores` (default: --cores)."""
    cores = cores or CORES[0]
    cond = threading.Condition()
    free = [cores]

    def work(t):
        case, n = t
        with cond:
            cond.wait_for(lambda: free[0] >= n)
            free[0] -= n
        try:
            run(case, n)
        finally:
            with cond:
                free[0] += n
                cond.notify_all()

    if not tasks:
        return
    tasks = sorted(tasks, key=lambda t: -t[1])  # big jobs first
    with ThreadPoolExecutor(len(tasks)) as ex:
        list(ex.map(work, tasks))


def surface_data(case: Path, alpha: float) -> dict:
    """Cp and signed Cf along the airfoil from the raw surface samples of the last time step."""
    d = sorted((case / "postProcessing" / "surf").glob("*"), key=lambda p: float(p.name))[-1]

    def load(name):
        f = next(d.glob(f"{name}*airfoil*.raw"), None) or next(d.glob(f"airfoil*{name}*.raw"))
        return np.loadtxt(f, comments="#")
    p = load("p")
    tau = load("wallShearStress")
    yp = load("yPlus")
    x, y = p[:, 0], p[:, 1]
    cp = p[:, 3] / 0.5
    a = math.radians(alpha)
    tx = tau[:, 3] * math.cos(a) + tau[:, 4] * math.sin(a)   # component along the free stream
    cf = -tx / 0.5        # OpenFOAM wall shear stress acts on the fluid: attached flow gives cf > 0
    i_le = int(np.argmin(x))  # faces are stored in grid order TE -> upper -> LE -> lower
    side = np.where(np.arange(len(x)) <= i_le, "upper", "lower")
    return dict(x=x.tolist(), y=y.tolist(), cp=cp.tolist(), cf=cf.tolist(), side=side.tolist(),
                yplus_max=float(yp[:, 3].max()), yplus_mean=float(yp[:, 3].mean()))


def make_grid(foil: np.ndarray, ni: int, nj: int, ds: float, R_far: float, blend: bool = False,
              blend_len: float = 2.0) -> np.ndarray:
    surf = resample_surface(foil, ni)
    X = build_ogrid_march(surf, nj, ds, R_far, 1.0, blend=blend, blend_len=blend_len)
    nbad = inverted_cells(X)
    assert nbad == 0, f"{nbad} folded cells"
    return X


def setup(X: np.ndarray, case: Path, alpha: float, re: float, iters: int, **kw) -> dict:
    if case.exists():
        shutil.rmtree(case)
    info = write_polymesh(X, case, dz=0.01)
    write_case(case, alpha, re, iters, **kw)
    return info


def collect(case: Path, alpha: float, avg: int = 500, extra: dict | None = None) -> dict:
    try:
        c = coeffs(case, avg)
    except Exception as e:  # noqa: BLE001
        c = {"error": str(e)}
    try:
        s = surface_data(case, alpha)
        c["yplus_max"], c["yplus_mean"] = s["yplus_max"], s["yplus_mean"]
    except Exception:  # noqa: BLE001
        s = None
    out = dict(alpha=alpha, **c, mesh=check_mesh_summary(case / "log.checkMesh"), **(extra or {}))
    return out, s


# ----------------------------------------------------------------------------- tasks
def grid_study(iters: int):
    """Nested family: finest 1024 x 512 cells, far field 500 c (as TMR), coarsened by 2."""
    foil = tmr_naca0012()
    Xf = make_grid(foil, 1024, 513, 5.0e-7, 500.0)
    # L1 is run afterwards by grid_study_fine, initialised from the converged L2 solution
    levels = {"L2": coarsen(Xf, 1), "L3": coarsen(Xf, 2), "L4": coarsen(Xf, 3)}
    nproc = {"L1": 4, "L2": 1, "L3": 1, "L4": 1}
    its = {"L1": iters * 2, "L2": int(iters * 1.5), "L3": iters, "L4": iters}
    tasks, meta = [], []
    for name, X in levels.items():
        assert inverted_cells(X) == 0
        for a in (0.0, 10.0, 15.0):
            case = RUNS / "n0012_grid" / f"{name}_a{a:04.1f}"
            info = setup(X, case, a, 6e6, its[name])
            tasks.append((case, nproc[name])); meta.append((name, a, case, info))
    run_pool(tasks)
    res = []
    for name, a, case, info in meta:
        r, s = collect(case, a)
        res.append(dict(grid=name, ni=info["ni"], nj=info["nj"], cells=info["cells"], **r))
        if s is not None:
            (RUNS / "n0012_grid" / f"surf_{name}_a{a:04.1f}.json").write_text(json.dumps(s))
        print(res[-1])
    (DATA / "n0012_grid_study_raw.json").write_text(json.dumps(res, indent=1))


def grid_study_fine(iters: int, alphas=(0.0, 10.0), nproc: int = 3):
    """Finest level L1 (1024 x 512), initialised from the converged L2 solution (mapFields) to cut the
    iteration count; the converged result does not depend on the initial field."""
    foil = tmr_naca0012()
    Xf = make_grid(foil, 1024, 513, 5.0e-7, 500.0)
    tasks, meta = [], []
    for a in alphas:
        case = RUNS / "n0012_grid" / f"L1_a{a:04.1f}"
        src = RUNS / "n0012_grid" / f"L2_a{a:04.1f}"
        if not any(p.name.replace(".", "").isdigit() and p.name != "0" for p in src.iterdir()):
            src = RUNS / "n0012_grid" / f"L3_a{a:04.1f}"   # L2 fields not written: map from L3
        info = setup(Xf, case, a, 6e6, iters)
        sh(f"mapFields {src} -consistent -sourceTime latestTime", case, "log.mapFields")
        tasks.append((case, nproc)); meta.append(("L1", a, case, info))
    run_pool(tasks)
    res = json.loads((DATA / "n0012_grid_study_raw.json").read_text()) if (DATA / "n0012_grid_study_raw.json").exists() else []
    res = [r for r in res if not (r["grid"] == "L1" and r["alpha"] in alphas)]
    for name, a, case, info in meta:
        r, s = collect(case, a)
        res.append(dict(grid=name, ni=info["ni"], nj=info["nj"], cells=info["cells"], initialised_from="L2", **r))
        if s is not None:
            (RUNS / "n0012_grid" / f"surf_{name}_a{a:04.1f}.json").write_text(json.dumps(s))
        print(res[-1])
    (DATA / "n0012_grid_study_raw.json").write_text(json.dumps(res, indent=1))


def fsturb(iters: int):
    """Free-stream eddy-viscosity sensitivity on the L2 grid (TMR value nu_t/nu = 0.009 vs 1 and 10)."""
    X = coarsen(make_grid(tmr_naca0012(), 1024, 513, 5.0e-7, 500.0), 1)
    tasks, meta = [], []
    for vr in (1.0,):
        for a in (0.0, 10.0):
            case = RUNS / "n0012_fsturb" / f"vr{vr:g}_a{a:04.1f}"
            setup(X, case, a, 6e6, iters, visc_ratio=vr)
            tasks.append((case, 1)); meta.append((vr, a, case))
    run_pool(tasks)
    res = []
    for vr, a, case in meta:
        r, s = collect(case, a, extra=dict(visc_ratio=vr))
        res.append(r); print(vr, a, r.get("Cl"), r.get("Cd"))
        if s is not None:
            (case.parent / f"surf_{case.name}.json").write_text(json.dumps(s))
    (DATA / "n0012_fsturb.json").write_text(json.dumps(res, indent=1))


def iter_limit(case: Path, window: int = 3000) -> dict:
    """Iterative-convergence check: fit c(n) = c_inf - A exp(-n/tau) to the last `window` iterations.
    Returns the fitted limits and the iterative error estimate |c_inf - c_last|."""
    from scipy.optimize import curve_fit
    from foamcase import coeff_history
    col, arr = coeff_history(case)
    n = arr[:, 0]
    out = {}
    m = n >= n[-1] - window
    for q in ("Cl", "Cd"):
        y = arr[:, col[q]]
        drift = abs(y[-1] - y[m][0])
        if drift < 1e-6 * max(abs(y[-1]), 1e-3):
            out[q + "_limit"], out[q + "_iter_err"] = float(y[-1]), 0.0
            continue
        try:
            f = lambda x, c, a, t: c - a * np.exp(-(x - n[m][0]) / t)
            p, _ = curve_fit(f, n[m], y[m], p0=(y[-1], y[-1] - y[m][0], window / 2), maxfev=20000)
            if p[2] <= 0 or p[2] > 20 * window:
                raise RuntimeError("no exponential tail")
            out[q + "_limit"], out[q + "_iter_err"] = float(p[0]), float(abs(p[0] - y[-1]))
        except Exception:  # noqa: BLE001
            out[q + "_limit"], out[q + "_iter_err"] = float(y[-1]), float(drift)
    return out


def grid_collect():
    """Collect whatever grid-study cases exist (runs stopped by hand are included with their iteration count)."""
    res = []
    for case in sorted((RUNS / "n0012_grid").glob("L*_a*")):
        name, a = case.name.split("_a")
        r, s = collect(case, float(a))
        r.update(iter_limit(case))
        ni = {"L1": 1024, "L2": 512, "L3": 256, "L4": 128}[name]
        res.append(dict(grid=name, ni=ni, nj=ni // 2 + 1, cells=ni * ni // 2, **r))
        if s is not None:
            (RUNS / "n0012_grid" / f"surf_{case.name}.json").write_text(json.dumps(s))
        print(name, a, r.get("Cl"), r.get("Cd"), r.get("iterations"))
    (DATA / "n0012_grid_study_raw.json").write_text(json.dumps(res, indent=1))


def n0012_polar(iters: int, alphas=None):
    """Production grid = level L2 of the study (512 x 256, far field 500 c)."""
    foil = tmr_naca0012()
    X = coarsen(make_grid(foil, 1024, 513, 5.0e-7, 500.0), 1)
    alphas = alphas or [2, 4, 6, 8, 12, 14, 16, 17, 18, 19]   # 0, 10, 15: grid-study L2 cases are reused
    tasks = []
    for a in alphas:
        case = RUNS / "n0012_polar" / f"a{a:04.1f}"
        log = case / "log.simpleFoam"
        if log.exists() and "\nEnd" in log.read_text()[-2000:]:
            continue                      # finished in an earlier (interrupted) session
        times = [float(p.name) for p in case.glob("[0-9]*") if p.name != "0"] if case.exists() else []
        if not times:                     # otherwise resume from the last written iteration (startFrom latestTime)
            setup(X, case, a, 6e6, iters)
        tasks.append((case, 1))
    run_pool(tasks)
    res, surf = [], {}
    for a in sorted(alphas + [0, 10, 15]):
        case = RUNS / "n0012_polar" / f"a{a:04.1f}"
        if a in (0, 10, 15):
            case = RUNS / "n0012_grid" / f"L2_a{float(a):04.1f}"
        r, s = collect(case, a, avg=500)
        res.append(r); print(r.get("alpha"), r.get("Cl"), r.get("Cd"))
        if s is not None and a in (0, 10, 15):
            surf[str(a)] = s
    (DATA / "n0012_polar.json").write_text(json.dumps(dict(openfoam=res, surface=surf), indent=1))


def wallfn(iters: int):
    """Same airfoil and far field; first-cell height set for y+ ~ 1 (resolved) and ~ 30, 60, 120 with
    wall functions.  Isolates the wall-treatment error used by the 3-D snappyHexMesh cases."""
    foil = tmr_naca0012()
    # u_tau/U ~ 0.036 at Re 6e6 -> y+ = ds * Re * 0.036 (cell-centre y+ is about half of this)
    cases = {"yp1_resolved": (2 * 1 / (6e6 * 0.036), "resolved"), "yp30_wf": (2 * 30 / (6e6 * 0.036), "wallfn"),
             "yp60_wf": (2 * 60 / (6e6 * 0.036), "wallfn"), "yp120_wf": (2 * 120 / (6e6 * 0.036), "wallfn"),
             "yp30_resolvedBC": (2 * 30 / (6e6 * 0.036), "resolved")}
    tasks, meta = [], []
    for name, (ds, wall) in cases.items():
        nj = 257 if wall == "resolved" and ds < 1e-5 else 161
        X = make_grid(foil, 512, nj, ds, 500.0)
        for a in (0.0, 10.0):
            case = RUNS / "n0012_wallfn" / f"{name}_a{a:04.1f}"
            setup(X, case, a, 6e6, iters, wall=wall)
            tasks.append((case, 1)); meta.append((name, a, case, ds, wall))
    run_pool(tasks)
    res = []
    for name, a, case, ds, wall in meta:
        r, _ = collect(case, a)
        res.append(dict(variant=name, ds_wall=ds, wall=wall, **r)); print(res[-1])
    (DATA / "n0012_wallfn.json").write_text(json.dumps(res, indent=1))


def n0012_re3(iters: int):
    """NACA 0012 at Re 3e6 (the 3-D wing validation condition): wall-function grid with the same first-cell
    height as the 3-D prism layers (1.2 mm on a 1 m chord) and a wall-resolved grid; gives the 2-D lift slope and
    profile-drag polar used in the lifting-line comparison."""
    foil = tmr_naca0012()
    grids = {"wallfn": (make_grid(foil, 512, 161, 1.2e-3, 500.0), "wallfn"),
             "resolved": (coarsen(make_grid(foil, 1024, 513, 1.0e-6, 500.0), 1), "resolved")}
    alphas = {"wallfn": [0, 2, 4, 6, 8], "resolved": [0, 4, 8]}
    tasks, meta = [], []
    for name, (X, wall) in grids.items():
        for a in alphas[name]:
            case = RUNS / "n0012_re3" / f"{name}_a{a:04.1f}"
            setup(X, case, a, 3e6, iters, tu=0.001, visc_ratio=1.0, wall=wall)
            tasks.append((case, 1)); meta.append((name, a, case))
    run_pool(tasks)
    res = []
    for name, a, case in meta:
        r, _ = collect(case, a, extra=dict(wall=name, Re=3e6))
        res.append(r); print(name, a, r.get("Cl"), r.get("Cd"))
    (DATA / "n0012_re3e6.json").write_text(json.dumps(dict(openfoam=res), indent=1))


def gaw1_polar(iters: int):
    foil, _ = gaw1("round")
    X = make_grid(foil, 512, 257, 1.6e-6, 500.0, blend=True)
    alphas = {4.3e6: [-4, 0, 4, 8, 10, 12, 14, 16, 17, 18, 19, 20], 6.3e6: [0, 8, 12, 16, 17, 18, 19, 20]}
    tasks, meta = [], []
    for re in (4.3e6, 6.3e6):
        for a in alphas[re]:
            case = RUNS / f"gaw1_re{re / 1e6:.1f}" / f"a{a:+05.1f}"
            setup(X, case, a, re, iters, tu=0.001, visc_ratio=1.0)
            tasks.append((case, 1)); meta.append((re, a, case))
    run_pool(tasks)
    res, surf = [], {}
    for re, a, case in meta:
        r, s = collect(case, a, avg=1000, extra=dict(Re=re))
        res.append(r); print(r)
        if s is not None and a in (0, 8, 12, 16) and re == 4.3e6:
            surf[str(a)] = s
    (DATA / "gaw1_polar.json").write_text(json.dumps(dict(openfoam=res, surface=surf), indent=1))


def flap_study(iters: int, re: float = 2.4e6):
    """GA(W)-1 with a 30 %-chord sealed plain flap (the E8-200 wing flap) at the stall Reynolds number:
    clean and flap 20 / 35 deg, alpha sweep through clmax -> section clmax increment for the flaps-down CLmax."""
    cases = {0: [8, 12, 14, 16, 18], 20: [4, 8, 10, 12, 14], 35: [0, 4, 8, 10, 12], -1: [14, 16, 18]}   # -1: clean, robust schemes
    tasks, meta = [], []
    for dfl, alphas in cases.items():
        sm, _ = gaw1("blunt")
        foil = round_te(plain_flap(sm, dfl)) if dfl > 0 else round_te(sm)
        robust = dfl != 0
        X = None
        for a in alphas:
            case = RUNS / (f"flap_d{dfl:02d}" if dfl >= 0 else "flap_clean_robust") / f"a{a:+05.1f}"
            meta.append((dfl, a, case))
            log = case / "log.simpleFoam"
            if log.exists() and "\nEnd" in log.read_text()[-2000:]:
                continue
            if case.exists() and [p for p in case.glob("[0-9]*") if p.name != "0"]:
                tasks.append((case, 1)); continue
            if X is None:
                X = make_grid(foil, 512, 257, 1.6e-6 * 6e6 / re, 500.0, blend=True, blend_len=0.5)
            setup(X, case, a, re, iters, tu=0.001, visc_ratio=1.0, robust=robust)
            tasks.append((case, 1))
    run_pool(tasks)
    res = []
    for dfl, a, case in meta:
        r, _ = collect(case, a, avg=1000, extra=dict(Re=re, flap_deg=dfl))
        res.append(r); print(dfl, a, r.get("Cl"), r.get("Cd"), r.get("Cl_std"))
    (DATA.parent.parent.parent / "cfd" / "results" / "flap_section_gaw1.json").write_text(json.dumps(dict(openfoam=res), indent=1))


def section(coords: Path, re: float, alphas, iters: int, tag: str):
    """Design-phase section polar for any Selig-format airfoil (blunt TE closed over the aft 20 %)."""
    raw = read_selig(coords)
    foil = spline_contour(raw, 1201)
    blunt = np.linalg.norm(foil[0] - foil[-1]) > 1e-5
    if blunt:
        foil = round_te(foil)
    X = make_grid(foil, 512, 257, 1.6e-6 * 6e6 / re, 500.0, blend=True)
    tasks = []
    for a in alphas:
        case = RUNS / f"section_{tag}" / f"a{a:+05.1f}"
        setup(X, case, a, re, iters, tu=0.001, visc_ratio=1.0)
        tasks.append((case, 1))
    run_pool(tasks)
    res = [collect(RUNS / f"section_{tag}" / f"a{a:+05.1f}", a, avg=1000, extra=dict(Re=re))[0] for a in alphas]
    out = CFD / "results" / f"section_{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(coords=str(coords), Re=re, openfoam=res), indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["grid-study", "grid-collect", "grid-study-fine", "n0012-polar", "n0012-re3", "fsturb", "flap", "wallfn", "gaw1-polar", "section", "test"])
    ap.add_argument("--iters", type=int, default=12000)
    ap.add_argument("--coords", type=Path)
    ap.add_argument("--re", type=float, default=4e6)
    ap.add_argument("--alphas", type=float, nargs="*", default=[-4, 0, 4, 8, 12, 14, 16, 18])
    ap.add_argument("--tag", default="wing")
    ap.add_argument("--cores", type=int, default=MAX_CORES)
    a = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    CORES[0] = min(a.cores, MAX_CORES)
    if a.what == "grid-study":
        grid_study(a.iters)
    elif a.what == "grid-collect":
        grid_collect()
    elif a.what == "grid-study-fine":
        grid_study_fine(a.iters)
    elif a.what == "n0012-polar":
        n0012_polar(a.iters)
    elif a.what == "flap":
        flap_study(a.iters)
    elif a.what == "fsturb":
        fsturb(a.iters)
    elif a.what == "n0012-re3":
        n0012_re3(a.iters)
    elif a.what == "wallfn":
        wallfn(a.iters)
    elif a.what == "gaw1-polar":
        gaw1_polar(a.iters)
    elif a.what == "section":
        section(a.coords, a.re, a.alphas, a.iters, a.tag)
    elif a.what == "test":
        X = coarsen(make_grid(tmr_naca0012(), 1024, 513, 5.0e-7, 500.0), 2)
        case = RUNS / "test"
        setup(X, case, 10.0, 6e6, a.iters)
        run(case, 1)
        print(collect(case, 10.0, avg=100))


if __name__ == "__main__":
    main()
