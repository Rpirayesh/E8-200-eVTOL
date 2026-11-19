"""Generic 3-D OpenFOAM set-up: blockMesh background + snappyHexMesh with prism layers, simpleFoam k-omega SST.

Used by the finite-wing validation (wing3d.py), the actuator-disk validation (rotor_disk.py) and the
full-aircraft analysis (aircraft3d.py).

Surfaces : {name: dict(level=(min, max), layers=n, feature_level=L)}  -> one wall patch per surface, all in
           the patch group `aircraft` (forces of the whole aircraft = group, breakdown = per patch).
Regions  : list of dict(name, shape='box'|'cylinder', min/max or p1/p2/radius, level)
Layers   : dict(first=m, expansion=r)  absolute first-layer thickness (wall-function y+ target),
           or dict(relative=True, final=0.4, expansion=1.25)
"""
from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

import numpy as np

from foamcase import check_mesh_summary, sh, wfile


def write_block_mesh(case: Path, bounds, base: float, symmetry: str | None = "ymin"):
    (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
    nx, ny, nz = (max(1, round((xmax - xmin) / base)), max(1, round((ymax - ymin) / base)), max(1, round((zmax - zmin) / base)))
    faces = {"xmin": "(0 4 7 3)", "xmax": "(1 2 6 5)", "ymin": "(0 1 5 4)", "ymax": "(3 7 6 2)", "zmin": "(0 3 2 1)", "zmax": "(4 5 6 7)"}
    sym_faces = [symmetry] if isinstance(symmetry, str) else list(symmetry or [])
    far = " ".join(v for k, v in faces.items() if k not in sym_faces)
    sym = "\n".join(f"    sym_{k} {{ type symmetryPlane; faces ( {faces[k]} ); }}" for k in sym_faces)
    wfile(case, "system/blockMeshDict", "dictionary", "blockMeshDict", f"""convertToMeters 1;
vertices ( ({xmin} {ymin} {zmin}) ({xmax} {ymin} {zmin}) ({xmax} {ymax} {zmin}) ({xmin} {ymax} {zmin})
           ({xmin} {ymin} {zmax}) ({xmax} {ymin} {zmax}) ({xmax} {ymax} {zmax}) ({xmin} {ymax} {zmax}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
boundary
(
    farfield {{ type patch; faces ( {far} ); }}
{sym}
);
""")
    return sym_faces


def _region_geo(r: dict) -> str:
    if r.get("shape", "box") == "box":
        return f"    {r['name']} {{ type box; min ({r['min'][0]} {r['min'][1]} {r['min'][2]}); max ({r['max'][0]} {r['max'][1]} {r['max'][2]}); }}"
    p1, p2 = r["p1"], r["p2"]
    return (f"    {r['name']} {{ type cylinder; point1 ({p1[0]} {p1[1]} {p1[2]}); point2 ({p2[0]} {p2[1]} {p2[2]}); "
            f"radius {r['radius']}; }}")


def write_snappy(case: Path, surfaces: dict, regions: list, location, layers: dict | None, add_layers: bool = True,
                 n_between: int = 3, max_global: int = 40_000_000, resolve_feature_angle: float = 30.0):
    geo = "\n".join(f"    {s}.stl {{ type triSurfaceMesh; name {s}; }}" for s in surfaces)
    geo += "\n" + "\n".join(_region_geo(r) for r in regions)
    feats = "\n".join(f'        {{ file "{s}.eMesh"; level {v.get("feature_level", v["level"][1])}; }}' for s, v in surfaces.items())
    ref = "\n".join(f"        {s} {{ level ({v['level'][0]} {v['level'][1]}); patchInfo {{ type wall; inGroups (aircraft); }} }}"
                    for s, v in surfaces.items())
    regs = "\n".join(f"        {r['name']} {{ mode inside; levels ((1E15 {r['level']})); }}" for r in regions)
    lay = "\n".join(f'        "{s}" {{ nSurfaceLayers {v.get("layers", 0)}; {v.get("layer_opts", "")} }}' for s, v in surfaces.items())
    layers = layers or {}
    if layers.get("relative", False):
        thick = (f"relativeSizes true; expansionRatio {layers.get('expansion', 1.25)}; finalLayerThickness {layers.get('final', 0.4)}; "
                 f"minThickness {layers.get('min', 0.05)};")
    else:
        t1 = layers.get("first", 1e-3)
        thick = (f"relativeSizes false; firstLayerThickness {t1}; expansionRatio {layers.get('expansion', 1.2)}; "
                 f"minThickness {0.2 * t1};")
    wfile(case, "system/snappyHexMeshDict", "dictionary", "snappyHexMeshDict", f"""castellatedMesh true; snap true; addLayers {'true' if add_layers else 'false'};
geometry
{{
{geo}
}}
castellatedMeshControls
{{
    maxLocalCells 6000000; maxGlobalCells {max_global}; minRefinementCells 10; maxLoadUnbalance 0.10;
    nCellsBetweenLevels {n_between};
    features
    (
{feats}
    );
    refinementSurfaces
    {{
{ref}
    }}
    resolveFeatureAngle {resolve_feature_angle};
    refinementRegions
    {{
{regs}
    }}
    locationInMesh ({location[0]} {location[1]} {location[2]});
    allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 100; nRelaxIter 5; nFeatureSnapIter 15;
               implicitFeatureSnap false; explicitFeatureSnap true; multiRegionFeatureSnap true; }}
addLayersControls
{{
    {thick}
    layers
    {{
{lay}
    }}
    nGrow 0; featureAngle 150; slipFeatureAngle 30; nRelaxIter 5; nSmoothSurfaceNormals 1; nSmoothNormals 3;
    nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.5; minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0; nLayerIter 50; nRelaxedIter 20;
}}
meshQualityControls
{{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-15;
    minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05;
    minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
    relaxed {{ maxNonOrtho 75; }}
}}
mergeTolerance 1e-6;
""")
    wfile(case, "system/surfaceFeatureExtractDict", "dictionary", "surfaceFeatureExtractDict",
          "\n".join(f"{s}.stl {{ extractionMethod extractFromSurface; extractFromSurfaceCoeffs {{ includedAngle 150; }} writeObj no; }}"
                    for s in surfaces) + "\n")


def write_decompose(case: Path, n: int):
    wfile(case, "system/decomposeParDict", "dictionary", "decomposeParDict", f"numberOfSubdomains {n};\nmethod scotch;\n")


def write_solver(case: Path, *, U: tuple, nu: float, rho: float, iters: int, sym_patches: list[str], coeff: dict | None,
                 force_patches: list[str], cofr=(0, 0, 0), hover: bool = False, tu: float = 0.002, visc_ratio: float = 1.0,
                 wall: str = "wallfn", u_ref: float | None = None, write_interval: int | None = None, extra_functions: str = "",
                 relax: tuple = (0.7, 0.5, 0.7)):
    """U: free-stream vector (m/s), zero for hover (entrainment boundaries)."""
    Ux, Uy, Uz = U
    Uref = u_ref or max(math.sqrt(Ux**2 + Uy**2 + Uz**2), 1.0)
    k = 1.5 * (Uref * tu) ** 2
    om = k / (visc_ratio * nu)
    if hover:
        farU = "type pressureInletOutletVelocity; value uniform (0 0 0);"
        farP = "type totalPressure; p0 uniform 0; value uniform 0;"
    else:
        farU = f"type freestreamVelocity; freestreamValue uniform ({Ux} {Uy} {Uz});"
        farP = "type freestreamPressure; freestreamValue uniform 0;"
    sym = "".join(f"    {s} {{ type symmetryPlane; }}\n" for s in sym_patches)
    if wall == "wallfn":
        kw, nutw = f"type kqRWallFunction; value uniform {k};", "type nutUSpaldingWallFunction; value uniform 0;"
    else:
        kw, nutw = "type kLowReWallFunction; value uniform 1e-12;", "type nutLowReWallFunction; value uniform 0;"
    wfile(case, "0/U", "volVectorField", "U", f"dimensions [0 1 -1 0 0 0 0];\ninternalField uniform ({Ux} {Uy} {Uz});\nboundaryField\n{{\n"
          f"    farfield {{ {farU} }}\n    aircraft {{ type noSlip; }}\n{sym}}}\n")
    wfile(case, "0/p", "volScalarField", "p", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{{\n"
          f"    farfield {{ {farP} }}\n    aircraft {{ type zeroGradient; }}\n{sym}}}\n")
    wfile(case, "0/k", "volScalarField", "k", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform {k};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {k}; value uniform {k}; }}\n    aircraft {{ {kw} }}\n{sym}}}\n")
    wfile(case, "0/omega", "volScalarField", "omega", f"dimensions [0 0 -1 0 0 0 0];\ninternalField uniform {om};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {om}; value uniform {om}; }}\n"
          f"    aircraft {{ type omegaWallFunction; value uniform {om}; }}\n{sym}}}\n")
    wfile(case, "0/nut", "volScalarField", "nut", "dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
          f"    farfield {{ type calculated; value uniform 0; }}\n    aircraft {{ {nutw} }}\n{sym}}}\n")
    wfile(case, "constant/transportProperties", "dictionary", "transportProperties", f"transportModel Newtonian;\nnu {nu};\n")
    wfile(case, "constant/turbulenceProperties", "dictionary", "turbulenceProperties",
          "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs off; }\n")
    fo = ""
    if coeff:
        fo += f"""    coeffs
    {{
        type forceCoeffs; libs (forces); writeControl timeStep; writeInterval 1;
        patches (aircraft); rho rhoInf; rhoInf {rho}; CofR ({cofr[0]} {cofr[1]} {cofr[2]});
        liftDir ({coeff['lift'][0]} {coeff['lift'][1]} {coeff['lift'][2]}); dragDir ({coeff['drag'][0]} {coeff['drag'][1]} {coeff['drag'][2]});
        pitchAxis (0 1 0); magUInf {Uref}; lRef {coeff['lref']}; Aref {coeff['aref']};
    }}
"""
    for p in force_patches:
        fo += (f"    forces_{p} {{ type forces; libs (forces); patches ({p}); rho rhoInf; rhoInf {rho}; "
               f"CofR ({cofr[0]} {cofr[1]} {cofr[2]}); writeControl timeStep; writeInterval 5; }}\n")
    wi = write_interval or min(iters, 200)
    wfile(case, "system/controlDict", "dictionary", "controlDict", f"""application simpleFoam;
startFrom latestTime; startTime 0; stopAt endTime; endTime {iters}; deltaT 1;
writeControl timeStep; writeInterval {wi}; purgeWrite 1; writeFormat binary; writePrecision 8; runTimeModifiable true;
functions
{{
{fo}    yPlus {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
    residuals {{ type solverInfo; libs (utilityFunctionObjects); fields (U p k omega); writeControl timeStep; writeInterval 10; }}
{extra_functions}}}
""")
    turb_div = "bounded Gauss upwind" if hover else "bounded Gauss limitedLinear 1"
    wfile(case, "system/fvSchemes", "dictionary", "fvSchemes", """ddtSchemes { default steadyState; }
gradSchemes { default cellLimited Gauss linear 1; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) TURB;
    div(phi,omega) TURB;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited 0.5; }
wallDist { method meshWave; }
""".replace("TURB", turb_div))
    if hover and relax == (0.7, 0.5, 0.7):
        relax = (0.5, 0.5, 0.5)
    wfile(case, "system/fvSolution", "dictionary", "fvSolution", """solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.05; nCellsInCoarsestLevel 50; }
    Phi { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.01; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.1; }
}
potentialFlow { nNonOrthogonalCorrectors 3; }
SIMPLE { nNonOrthogonalCorrectors 1; consistent yes; }
relaxationFactors { equations { U %g; ".*" %g; } fields { p %g; } }
""" % relax)


def mesh(case: Path, stl_dir: Path, surfaces: list[str], nproc: int) -> dict:
    """blockMesh + surfaceFeatureExtract + parallel snappyHexMesh + checkMesh (case already has dicts)."""
    tri = case / "constant" / "triSurface"
    tri.mkdir(parents=True, exist_ok=True)
    for s in surfaces:
        shutil.copy(stl_dir / f"{s}.stl", tri / f"{s}.stl")
    write_decompose(case, nproc)
    assert sh("blockMesh", case, "log.blockMesh") == 0, "blockMesh failed"
    if surfaces:
        assert sh("surfaceFeatureExtract", case, "log.sfe") == 0, "surfaceFeatureExtract failed"
    assert sh("decomposePar -force", case, "log.decompose") == 0
    rc = sh(f"mpirun -np {nproc} snappyHexMesh -overwrite -parallel", case, "log.snappy")
    assert rc == 0, f"snappyHexMesh failed (see {case}/log.snappy)"
    assert sh("reconstructParMesh -constant", case, "log.reconstruct") == 0
    for d in case.glob("processor*"):
        shutil.rmtree(d, ignore_errors=True)
    sh("checkMesh -constant", case, "log.checkMesh")
    info = check_mesh_summary(case / "log.checkMesh")
    info["layers"] = layer_coverage(case / "log.snappy")
    return info


def layer_coverage(log: Path) -> dict:
    """Per-patch prism-layer statistics from the last snappyHexMesh layer summary table."""
    lines = log.read_text().splitlines() if log.exists() else []
    starts = [i for i, l in enumerate(lines) if l.strip().startswith("patch") and "faces" in l and "layers" in l]
    out = {}
    if not starts:
        return out
    for l in lines[starts[-1] + 1:starts[-1] + 60]:
        v = l.split()
        if not v or v[0].startswith("-") or v[0] in ("target", "near-wall"):
            if out and not v:
                break
            continue
        try:
            nums = [float(x) for x in v[1:]]
        except ValueError:
            break
        if len(nums) >= 5:   # faces target mesh thickness[m] thickness[%]
            out[v[0]] = dict(faces=int(nums[0]), target_layers=nums[1], mean_layers=nums[2], total_thickness_m=nums[3],
                             thickness_pct_of_target=nums[4])
        elif len(nums) == 4:  # faces layers near-wall[m] overall[m]
            out[v[0]] = dict(faces=int(nums[0]), mean_layers=nums[1], near_wall_m=nums[2], total_thickness_m=nums[3])
    return out


def copy_mesh(src: Path, case: Path):
    if case.exists():
        shutil.rmtree(case)
    (case / "constant").mkdir(parents=True)
    shutil.copytree(src / "constant" / "polyMesh", case / "constant" / "polyMesh")
    for f in ("system/blockMeshDict", "system/snappyHexMeshDict"):
        if (src / f).exists():
            (case / "system").mkdir(exist_ok=True)
            shutil.copy(src / f, case / f)


def latest_proc_time(case: Path) -> float:
    d = case / "processor0"
    ts = [float(x.name) for x in d.iterdir() if x.is_dir() and re.fullmatch(r"[0-9.eE+-]+", x.name)] if d.exists() else []
    return max(ts) if ts else 0.0


def resumable(case: Path) -> bool:
    """True when a decomposed case has written an intermediate time (restart from it)."""
    return latest_proc_time(case) > 0


def run_or_resume(case: Path, nproc: int, setup, potential: bool = True, topo: bool = False) -> int:
    """Idempotent run: skip finished cases (file DONE), resume interrupted decomposed cases from their latest
    written time, otherwise set up (callable `setup()`) and run.  Writes DONE when the solver exits normally."""
    if (case / "DONE").exists():
        return 0
    if case.exists() and resumable(case):
        rc = sh(f"mpirun -np {nproc} simpleFoam -parallel", case, f"log.simpleFoam.resume{int(latest_proc_time(case))}")
    else:
        setup()
        rc = run(case, nproc, potential=potential, topo=topo)
    if rc == 0:
        (case / "DONE").write_text("ok\n")
    return rc


def run(case: Path, nproc: int, potential: bool = True, topo: bool = False) -> int:
    write_decompose(case, nproc)
    if topo:
        sh("topoSet", case, "log.topoSet")
    sh("decomposePar -force", case, "log.decompose")
    if potential:
        sh(f"mpirun -np {nproc} potentialFoam -parallel -writephi", case, "log.potential")
    rc = sh(f"mpirun -np {nproc} simpleFoam -parallel", case, "log.simpleFoam")
    return rc


def reconstruct(case: Path, fields: str | None = None):
    f = f" -fields '({fields})'" if fields else ""
    sh(f"reconstructPar -latestTime{f}", case, "log.reconstruct")


def read_forces(case: Path, patch: str, avg: int = 100) -> dict:
    """Mean and band of the total force (x, y, z) on a patch over the last `avg` samples."""
    files = sorted((case / "postProcessing" / f"forces_{patch}").glob("*/force.dat"), key=lambda p: float(p.parent.name))
    rows = []
    for f in files:
        for l in f.read_text().splitlines():
            if l and not l.startswith("#"):
                rows.append([float(x) for x in l.replace("(", " ").replace(")", " ").split()])
    arr = np.array(rows)
    t = arr[-avg:]
    return dict(F=t[:, 1:4].mean(axis=0).tolist(), F_min=t[:, 1:4].min(axis=0).tolist(), F_max=t[:, 1:4].max(axis=0).tolist(),
                iterations=int(arr[-1, 0]), history=arr[:, :4])
