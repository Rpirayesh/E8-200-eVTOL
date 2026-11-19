"""Actuator-disk validation in hover.

    python cfd/tools/rotor_disk.py isolated --lev 0|1|2     # quarter model, uniform disk vs momentum theory
    python cfd/tools/rotor_disk.py download --lev 1 [--loading uniform|linear]
                                                            # Felker & Light (NASA TM 88255) small-scale rotor over a
                                                            # NACA 23015 wing (rotor axis at mid-span, 0.4 R gap)
    python cfd/tools/rotor_disk.py post

Same mesher (snappyHexMesh), solver settings and momentum-source disk (actuator.py) as the full-aircraft
hover cases.  Rotor R = 1.067 m (the Felker & Light small-scale rotor), thrust 1000 N (disk loading 280 N/m2,
close to the E8-200 lift rotors).  Scratch cases in cfd/.cache/rotor/.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import actuator  # noqa: E402
import mesh3d  # noqa: E402
from foamcase import CACHE, MAX_CORES, VAL, wfile  # noqa: E402

WORK = CACHE / "rotor"
DATA = VAL / "data"
R = 1.067
T = 1000.0
RHO = 1.225
NU = 1.5e-5
C_WING, B_WING, GAP = 0.447, 1.60, 0.4 * R


def sample_function(lines: dict) -> str:
    sets = "\n".join(f"            {n} {{ type uniform; axis distance; start ({s[0]} {s[1]} {s[2]}); end ({e[0]} {e[1]} {e[2]}); nPoints {k}; }}"
                     for n, (s, e, k) in lines.items())
    return f"""    sample
    {{
        type sets; libs (sampling); writeControl writeTime; setFormat raw; interpolationScheme cellPoint; fields (U p);
        sets
        {{
{sets}
        }}
    }}
"""


def isolated(lev: int, iters: int, nproc: int):
    name = f"isolated_L{lev}"
    case = WORK / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    base = R / 2
    bounds = ((0, 0, -16 * R), (12 * R, 12 * R, 8 * R))
    sym = mesh3d.write_block_mesh(case, bounds, base, symmetry=["xmin", "ymin"])
    regions = [
        dict(name="disk", shape="box", min=(0, 0, -0.12 * R), max=(1.15 * R, 1.15 * R, 0.12 * R), level=4 + lev),
        dict(name="wake1", shape="cylinder", p1=(0, 0, 0.4 * R), p2=(0, 0, -3.0 * R), radius=1.2 * R, level=3 + lev),
        dict(name="wake2", shape="cylinder", p1=(0, 0, 1.5 * R), p2=(0, 0, -8.0 * R), radius=1.7 * R, level=2 + lev),
    ]
    mesh3d.write_snappy(case, {}, regions, (5.13 * R, 5.27 * R, 5.41 * R), None, add_layers=False)
    rot = [dict(name="disk", center=(0, 0, 0), axis=(0, 0, 1), radius=R, thrust_n=T, loading="uniform",
                thickness=0.08 * R, domain_fraction=0.25)]
    wfile(case, "system/topoSetDict", "dictionary", "topoSetDict", actuator.topo_actions(rot))
    wfile(case, "constant/fvOptions", "dictionary", "fvOptions", actuator.fv_options(rot, RHO))
    lines = {f"r_z{z:+.2f}".replace(".", "p").replace("+", "P").replace("-", "M"): ((0.0, 0.002, z * R), (2.5 * R, 0.002, z * R), 501)
             for z in (0.0, -0.25, -0.5, -1.0, -2.0, -3.0, -4.0)}
    lines["axis"] = ((0.002, 0.002, 4 * R), (0.002, 0.002, -12 * R), 801)
    extra = sample_function(lines) + """    diskU { type volFieldValue; libs (fieldFunctionObjects); writeControl timeStep; writeInterval 10;
            regionType cellZone; name disk; operation volAverage; fields (U); writeFields false; }
"""
    mesh3d.write_solver(case, U=(0, 0, 0), nu=NU, rho=RHO, iters=iters, sym_patches=[f"sym_{s}" for s in sym], coeff=None,
                        force_patches=[], hover=True, u_ref=10.0, extra_functions=extra)
    # snappy needs no surfaces here; run the mesh steps directly
    info = mesh3d.mesh(case, case, [], nproc)
    print(name, info)
    mesh3d.run(case, nproc, potential=False, topo=True)
    (case / "mesh_info.json").write_text(json.dumps(info))


def wing_stl(out: Path):
    import oml
    secs = [dict(x_le=-0.5 * C_WING, y=y, z=-GAP, chord=C_WING, twist_deg=0.0) for y in (-B_WING / 2, B_WING / 2)]
    m = oml.lifting_surface(secs, "naca23015", n=161)[0]
    out.mkdir(parents=True, exist_ok=True)
    m.export(out / "wing.stl")
    return m.is_watertight


def download(lev: int, iters: int, nproc: int, loading: str):
    name = f"download_{loading}_L{lev}"
    case = WORK / name
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    wing_stl(case / "stl")
    base = R / 2
    bounds = ((-8 * R, 0, -16 * R), (8 * R, 8 * R, 8 * R))
    sym = mesh3d.write_block_mesh(case, bounds, base, symmetry=["ymin"])
    surfaces = {"wing": dict(level=(5 + lev, 6 + lev), layers=3, feature_level=6 + lev)}
    regions = [
        dict(name="disk", shape="box", min=(-1.15 * R, 0, -0.12 * R), max=(1.15 * R, 1.15 * R, 0.12 * R), level=4 + lev),
        dict(name="wingbox", shape="box", min=(-0.9 * C_WING, 0, -GAP - 0.5 * C_WING), max=(0.9 * C_WING, 0.62 * B_WING, -GAP + 0.25 * C_WING), level=5 + lev),
        dict(name="wake1", shape="cylinder", p1=(0, 0, 0.4 * R), p2=(0, 0, -3.0 * R), radius=1.25 * R, level=3 + lev),
        dict(name="wake2", shape="cylinder", p1=(0, 0, 1.5 * R), p2=(0, 0, -8.0 * R), radius=1.8 * R, level=2 + lev),
    ]
    mesh3d.write_snappy(case, surfaces, regions, (4.13 * R, 4.27 * R, 4.41 * R), dict(relative=True, final=0.5, expansion=1.25))
    rot = [dict(name="disk", center=(0, 0, 0), axis=(0, 0, 1), radius=R, thrust_n=T, loading=loading,
                hub_radius=0.0 if loading == "uniform" else 0.12 * R, thickness=0.08 * R, domain_fraction=0.5)]
    wfile(case, "system/topoSetDict", "dictionary", "topoSetDict", actuator.topo_actions(rot))
    wfile(case, "constant/fvOptions", "dictionary", "fvOptions", actuator.fv_options(rot, RHO))
    lines = {"span_wake": ((0.0, 0.002, -GAP + 0.5 * C_WING), (2.0 * R, 0.002, -GAP + 0.5 * C_WING), 401),
             "chord_above": ((-1.5 * R, 0.3, -GAP + 0.25 * C_WING), (1.5 * R, 0.3, -GAP + 0.25 * C_WING), 401)}
    mesh3d.write_solver(case, U=(0, 0, 0), nu=NU, rho=RHO, iters=iters, sym_patches=[f"sym_{s}" for s in sym], coeff=None,
                        force_patches=["wing"], hover=True, u_ref=10.0, extra_functions=sample_function(lines))
    info = mesh3d.mesh(case, case / "stl", ["wing"], nproc)
    print(name, info)
    mesh3d.run(case, nproc, potential=False, topo=True)
    (case / "mesh_info.json").write_text(json.dumps(info))


# ----------------------------------------------------------------------------- post-processing
def _load_set(case: Path, name: str) -> np.ndarray:
    d = sorted([p for p in (case / "postProcessing" / "sample").glob("*") if p.is_dir()], key=lambda p: float(p.name))[-1]
    f = next(d.glob(f"{name}_*U*.xy"), None) or next(d.glob(f"{name}*.xy"))
    return np.loadtxt(f)


def post_isolated(case: Path) -> dict:
    mt = actuator.momentum_theory(T, R, RHO)
    vi = mt["v_induced"]
    out = dict(case=case.name, momentum_theory=mt, slices=[])
    info = json.loads((case / "mesh_info.json").read_text())
    out["cells"] = info.get("cells")
    for z in (0.0, -0.25, -0.5, -1.0, -2.0, -3.0, -4.0):
        nm = f"r_z{z:+.2f}".replace(".", "p").replace("+", "P").replace("-", "M")
        a = _load_set(case, nm)
        r, w = a[:, 0], -a[:, 4]                       # downwash positive
        core = w[r < 0.3 * R].mean()
        flux = np.trapezoid(w * 2 * np.pi * r, r) if hasattr(np, "trapezoid") else np.trapz(w * 2 * np.pi * r, r)
        inside = r <= R
        q_disk = np.trapezoid((w * 2 * np.pi * r)[inside], r[inside])
        # half-velocity radius of the slipstream (outermost crossing of w = 0.5 core)
        above = np.where(w >= 0.5 * core)[0]
        r_half = float(r[above[-1]]) if len(above) else float("nan")
        mom = np.trapezoid(np.clip(w, 0, None) ** 2 * 2 * np.pi * r, r)
        r_mom = math.sqrt(mom / (math.pi * core**2)) if core > 0 else float("nan")
        out["slices"].append(dict(z_over_R=z, w_core_over_vi=core / vi, w_mean_disk_over_vi=q_disk / (math.pi * R**2) / vi,
                                  r_half_over_R=r_half / R, r_momentum_over_R=r_mom / R, profile_r_over_R=(r / R)[::5].tolist(),
                                  profile_w_over_vi=(w / vi)[::5].tolist()))
    ax = _load_set(case, "axis")
    out["axis"] = dict(z_over_R=(ax[:, 0] * -1 + 4).tolist()[::4], w_over_vi=(-ax[:, 4] / vi).tolist()[::4])
    # induced power from the zone-averaged velocity (P = T * mean downwash through the source cells)
    f = sorted((case / "postProcessing" / "diskU").glob("*/volFieldValue.dat"), key=lambda p: float(p.parent.name))[-1]
    rows = [l.replace("(", " ").replace(")", " ").split() for l in f.read_text().splitlines() if l and not l.startswith("#")]
    arr = np.array(rows, float)
    w_zone = -arr[-50:, 3].mean()
    out["w_zone_mean_over_vi"] = w_zone / vi
    out["power_ratio_cfd_over_ideal"] = w_zone / vi
    out["iterations"] = int(arr[-1, 0])
    return out


def post_download(case: Path) -> dict:
    f = mesh3d.read_forces(case, "wing", avg=80)   # forces every 5 iterations -> last 400 iterations
    hist = f.pop("history")
    DL = -2 * f["F"][2]
    band = [-2 * f["F_max"][2], -2 * f["F_min"][2]]
    mt = actuator.momentum_theory(T, R, RHO)
    q_w = 0.5 * RHO * (2 * mt["v_induced"]) ** 2
    out = dict(case=case.name, DL_n=DL, DL_over_T=DL / T, DL_over_T_band=[b / T for b in band], iterations=f["iterations"],
               wing_area_m2=C_WING * B_WING, wing_area_over_disk_area=C_WING * B_WING / (math.pi * R**2),
               equivalent_cd_on_far_wake_q=DL / (q_w * C_WING * B_WING),
               history_it=hist[::10, 0].tolist(), history_DL_over_T=(-2 * hist[::10, 3] / T).tolist())
    info = json.loads((case / "mesh_info.json").read_text())
    out["cells"] = info.get("cells")
    out["layers"] = info.get("layers")
    return out


def post():
    res = dict(isolated=[], download=[])
    for c in sorted(WORK.glob("isolated_L*")):
        try:
            res["isolated"].append(post_isolated(c))
        except Exception as e:  # noqa: BLE001
            print(c, e)
    for c in sorted(WORK.glob("download_*")):
        try:
            res["download"].append(post_download(c))
        except Exception as e:  # noqa: BLE001
            print(c, e)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "rotor_disk.json").write_text(json.dumps(res, indent=1))
    for r in res["isolated"]:
        print(r["case"], r["cells"], "w_zone/vi", round(r["w_zone_mean_over_vi"], 3),
              [(s["z_over_R"], round(s["w_core_over_vi"], 3), round(s["r_half_over_R"], 3)) for s in r["slices"]])
    for r in res["download"]:
        print(r["case"], r["cells"], "DL/T", round(r["DL_over_T"], 4), r["DL_over_T_band"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["isolated", "download", "post"])
    ap.add_argument("--lev", type=int, default=1)
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--nproc", type=int, default=MAX_CORES)
    ap.add_argument("--loading", default="uniform")
    a = ap.parse_args()
    if a.what == "isolated":
        isolated(a.lev, a.iters, a.nproc)
    elif a.what == "download":
        download(a.lev, a.iters, a.nproc, a.loading)
    else:
        post()


if __name__ == "__main__":
    main()
