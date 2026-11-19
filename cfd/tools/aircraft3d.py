"""Full-aircraft 3-D RANS of the E8-200 (OpenFOAM simpleFoam, k-omega SST, wall functions) on a
snappyHexMesh half model, built parametrically from design/geometry.json (see cfd/README.md).

    python cfd/tools/aircraft3d.py geometry [--geometry FILE]            # region STLs (cruise and hover sets)
    python cfd/tools/aircraft3d.py mesh  --mode cruise|hover [--lev N]   # blockMesh + snappyHexMesh (parallel)
    python cfd/tools/aircraft3d.py cruise --alphas -4 0 4 8 [--lev N]    # alpha sweep, lift rotors stopped,
                                                                          # pusher as actuator disk (thrust from geometry.json)
    python cfd/tools/aircraft3d.py hover [--loading uniform|linear]      # lift rotors as actuator disks at hover thrust
    python cfd/tools/aircraft3d.py post                                  # cfd/results/*.json + plots

Symmetry plane y = 0 (starboard half).  Rotors are mirrored port/starboard and swirl is not modelled,
so the mean flow is symmetric.  Mesh settings (surface cell sizes relative to the local chord / diameter,
first prism layer for wall-function y+ 40-100) follow the finite-wing validation in validation/cfd/.
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
import actuator  # noqa: E402
import mesh3d  # noqa: E402
import oml  # noqa: E402
from foamcase import CACHE, CFD, MAX_CORES, ROOT, coeffs, wfile  # noqa: E402

WORK = CACHE / "aircraft"
OUT = CFD / "results"
RHO, NU = 1.225, 1.5e-5          # ISA sea level; hot-day / altitude cases pass --rho --nu
REGIONS = ["fuselage", "wing", "tail", "booms", "rotors", "pusher", "gear"]
G0 = 9.80665
LIFT_EXTRA = [0]      # extra surface-refinement levels on the lifting surfaces (wing, tail); 1 = validated c/128


def LT(lev: int) -> str:
    """Mesh/case level tag, e.g. L+0 (all surfaces c/64) or L+0w1 (lifting surfaces one level finer)."""
    return f"L{lev:+d}" + (f"w{LIFT_EXTRA[0]}" if LIFT_EXTRA[0] else "")


# ----------------------------------------------------------------------------- inputs
def load(geometry: Path, design: Path | None = None) -> dict:
    geo = json.loads(geometry.read_text())
    sel = json.loads(design.read_text()) if design and design.exists() else {}
    w = geo["wing"]
    secs = oml.wing_sections(w)
    ref = dict(geo.get("reference", {}))
    if "S_ref" not in ref:   # trapezoidal reference area of the full wing (both sides, to the centre line)
        b = 2 * secs[-1]["y"]
        ref["S_ref"] = 0.5 * (secs[0]["chord"] + secs[-1]["chord"]) * b
        ref["b_ref"] = b
        cr, ct = secs[0]["chord"], secs[-1]["chord"]
        ref["c_ref"] = 2 / 3 * (cr**2 + cr * ct + ct**2) / (cr + ct)
    ref.setdefault("x_ref", geo.get("mass", {}).get("x_cg", secs[0]["x_le"] + 0.25 * secs[0]["chord"]))
    ref.setdefault("z_ref", geo.get("mass", {}).get("z_cg", secs[0]["z"]))
    op = dict(geo.get("operating", {}))
    op.setdefault("cruise_speed_ms", sel.get("cruise_speed_ms", 45.0))
    return dict(geo=geo, sel=sel, ref=ref, op=op)


def disk_fraction(center, axis, R: float, n: int = 400) -> float:
    """Share of a rotor disk on the y >= 0 side (half model)."""
    d = np.asarray(axis, float); d /= np.linalg.norm(d)
    ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    e1 = ref - d * (ref @ d); e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    g = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(g, g)
    inside = X**2 + Y**2 <= 1
    pts = np.asarray(center)[None, :] + R * (X[inside, None] * e1 + Y[inside, None] * e2)
    return float(np.mean(pts[:, 1] >= 0))


def rotors_for(cfg: dict, mode: str, loading: str = "uniform", lift_frac: float | None = None,
               pusher_T: float | None = None, thrust_scale: float = 1.0) -> list[dict]:
    """mode 'hover': lift rotors at hover thrust x thrust_scale; 'cruise': pusher disk; 'transition': lift rotors at
    lift_frac x hover thrust plus the pusher."""
    geo, op = cfg["geo"], cfg["op"]
    out = []
    if mode == "transition":
        lr = rotors_for(cfg, "hover", loading, thrust_scale=lift_frac or 0.0) if lift_frac else []
        return lr + rotors_for(cfg, "cruise", pusher_T=pusher_T)
    if mode == "hover":
        T = op.get("hover_thrust_per_lift_rotor_n")
        if T is None:
            m = geo.get("mass", {}).get("mtow_kg") or cfg["sel"].get("mass", {}).get("mtow_kg")
            T = m * G0 / len(geo["lift_rotors"])
        for r in geo["lift_rotors"]:
            R = r["diameter"] / 2
            f = disk_fraction(r["hub"], r.get("axis", (0, 0, 1)), R)
            if f <= 0:
                continue
            out.append(dict(name=r["name"], center=r["hub"], axis=r.get("axis", (0, 0, 1)), radius=R,
                            thrust_n=thrust_scale * r.get("thrust_hover_n", T),
                            loading=loading, hub_radius=r.get("hub_diameter", 0.1 * r["diameter"]) / 2,
                            thickness=max(0.04 * R, 0.05), domain_fraction=f))
    else:
        pushers = geo.get("pushers") or ([geo["pusher"]] if geo.get("pusher") else [])
        T = op.get("cruise_thrust_pusher_n", 0.0) if pusher_T is None else pusher_T   # total cruise thrust of all pushers
        for i, p in enumerate(pushers):
            if not T:
                break
            R = p["diameter"] / 2
            f = disk_fraction(p["hub"], p.get("axis", (-1, 0, 0)), R)
            if f <= 0:
                continue
            out.append(dict(name="pusher_disk" if len(pushers) == 1 else f"pusher_disk{i}", center=p["hub"], axis=p.get("axis", (-1, 0, 0)),
                            radius=R, thrust_n=T / len(pushers), loading="linear",
                            hub_radius=p.get("spinner_diameter", 0.18 * p["diameter"]) / 2, thickness=max(0.04 * R, 0.04),
                            domain_fraction=f))
    return out


# ----------------------------------------------------------------------------- geometry / mesh
def geometry(cfg: dict):
    for mode in ("cruise", "hover"):
        regions = oml.build(cfg["geo"], hover=(mode == "hover"))
        info = oml.export(regions, WORK / f"geometry_{mode}")
        print(mode, json.dumps({k: (v["faces"], v["parts"], v["watertight_parts"]) for k, v in info.items()}))


def _level(base: float, size: float) -> int:
    return int(max(0, round(math.log2(base / size))))


def first_layer(U: float, c: float, yplus_c: float = 30.0) -> float:
    """Prism first-layer thickness giving a cell-centre y+ of about `yplus_c` at mid-chord (flat-plate cf)."""
    re_x = U * 0.5 * c / NU
    cf = 0.026 / re_x ** (1 / 7)
    ut = U * math.sqrt(cf / 2)
    return 2 * yplus_c * NU / ut


def mesh(cfg: dict, mode: str, lev: int, nproc: int, force: bool = False):
    if not force and (WORK / f"mesh_{mode}_{LT(lev)}" / "mesh_info.json").exists():
        print("mesh exists:", mode, lev)
        return
    geo, ref = cfg["geo"], cfg["ref"]
    stl_dir = WORK / f"geometry_{mode}"
    present = [r for r in REGIONS if (stl_dir / f"{r}.stl").exists()]
    import trimesh
    bb = np.array([trimesh.load(stl_dir / f"{r}.stl").bounds for r in present])
    lo, hi = bb[:, 0].min(axis=0), bb[:, 1].max(axis=0)
    L = max(hi[0] - lo[0], hi[1] - lo[1])
    base = 1.0 if L < 12 else 2.0
    if mode == "cruise":
        bounds = ((lo[0] - 3 * L, 0.0, lo[2] - 3 * L), (hi[0] + 6 * L, 3.5 * L, hi[2] + 3 * L))
    else:   # hover: wake goes down, entrainment from all sides
        bounds = ((lo[0] - 2.5 * L, 0.0, lo[2] - 5 * L), (hi[0] + 2.5 * L, 3 * L, hi[2] + 3 * L))
    # snap to the base cell but offset by a non-dyadic fraction so that no background-cell face coincides with a
    # chord plane or a symmetric body axis (asymmetric castellation otherwise)
    bounds = tuple(tuple(round(v / base) * base + (0.0 if (i == 1 and k == 0) else 0.37 * base) for i, v in enumerate(p))
                   for k, p in enumerate(bounds))
    case = WORK / f"mesh_{mode}_{LT(lev)}"
    if case.exists():
        shutil.rmtree(case)
    case.mkdir(parents=True)
    sym = mesh3d.write_block_mesh(case, bounds, base, symmetry="ymin")
    c = ref["c_ref"]
    lr = geo.get("lift_rotors", [{}])
    size = {"wing": c / 64, "tail": c / 64, "fuselage": c / 64,
            "booms": min(c / 64, geo.get("booms", [{"diameter": 0.15}])[0]["diameter"] / 8),
            "rotors": min(c / 64, lr[0].get("blade_chord", 0.12) / 12),
            "pusher": c / 64, "gear": min(c / 64, 0.012)}
    # prism layers: wall-function y+ ~ 30 on the lifting surfaces and booms; thicker first layer on the fuselage
    # (longer running length); none on blades, hubs and gear tubes (too thin for layers at this cell size)
    nlay = {"wing": 9, "tail": 7, "fuselage": 7, "booms": 5, "rotors": 0, "pusher": 0, "gear": 0}
    fl = first_layer(cfg["op"]["cruise_speed_ms"], c)
    lopts = {"fuselage": f"firstLayerThickness {2 * fl:.6f}; expansionRatio 1.2; minThickness {0.4 * fl:.6f};"}
    surfaces = {}
    for r in present:
        lmax = _level(base, size[r]) + lev + (LIFT_EXTRA[0] if r in ("wing", "tail") else 0)
        surfaces[r] = dict(level=(lmax - 1, lmax), layers=nlay[r], feature_level=lmax, layer_opts=lopts.get(r, ""))
    pad = 0.15 * L
    regions = [dict(name="near", shape="box", min=tuple(lo - pad), max=tuple(hi + pad), level=_level(base, c / 8) + lev),
               dict(name="far", shape="box", min=tuple(lo - 0.6 * L), max=tuple(hi + 0.6 * L), level=_level(base, c / 2) + lev)]
    if mode == "cruise":
        regions.append(dict(name="wake", shape="box", min=(lo[0], 0, lo[2] - 0.1 * L), max=(hi[0] + 1.5 * L, hi[1] + pad, hi[2] + 0.1 * L),
                            level=_level(base, c / 4) + lev))
    for rot in rotors_for(cfg, mode):
        n = np.asarray(rot["axis"], float); n /= np.linalg.norm(n)
        ctr = np.asarray(rot["center"], float)
        regions.append(dict(name=f"disk_{rot['name']}", shape="cylinder", p1=tuple(ctr - 0.15 * rot["radius"] * n),
                            p2=tuple(ctr + 0.15 * rot["radius"] * n), radius=1.1 * rot["radius"], level=_level(base, rot["radius"] / 24) + lev))
        if mode == "hover":
            regions.append(dict(name=f"slip_{rot['name']}", shape="cylinder", p1=tuple(ctr + 0.3 * rot["radius"] * n),
                                p2=tuple(ctr - 4.0 * rot["radius"] * n), radius=1.25 * rot["radius"], level=_level(base, rot["radius"] / 12) + lev))
    U = cfg["op"]["cruise_speed_ms"]
    loc = (bounds[0][0] + 0.37 * base, 0.5 * bounds[1][1] + 0.31 * base, bounds[1][2] - 1.13 * base)
    mesh3d.write_snappy(case, surfaces, regions, loc, dict(first=first_layer(U, c), expansion=1.25))
    mesh3d.write_solver(case, U=(U, 0, 0), nu=NU, rho=RHO, iters=1, sym_patches=[f"sym_{s}" for s in sym], coeff=None, force_patches=[])
    info = mesh3d.mesh(case, stl_dir, present, nproc)
    info.update(base=base, bounds=bounds, surfaces=surfaces, first_layer_m=first_layer(U, c))
    (case / "mesh_info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


# ----------------------------------------------------------------------------- runs
def pusher_inflow_function(cfg: dict) -> str:
    """Velocity samples on rings 0.10 m upstream of each pusher disk (y >= 0 side): r/R 0.2-0.95, 24 azimuths."""
    geo = cfg["geo"]
    pushers = geo.get("pushers") or ([geo["pusher"]] if geo.get("pusher") else [])
    pts = []
    for p in pushers:
        hub = np.asarray(p["hub"], float)
        if hub[1] < -1e-6:
            continue
        R = p["diameter"] / 2
        x = hub[0] - 0.10
        for rr in (0.2, 0.35, 0.5, 0.65, 0.8, 0.95):
            for k in range(24):
                th = 2 * math.pi * k / 24
                y, z = hub[1] + rr * R * math.cos(th), hub[2] + rr * R * math.sin(th)
                if y >= 0.005:
                    pts.append(f"({x:.4f} {y:.4f} {z:.4f})")
    if not pts:
        return ""
    return f"""    pusherInflow
    {{
        type sets; libs (sampling); writeControl writeTime; setFormat raw; interpolationScheme cellPoint; fields (U p);
        sets {{ rings {{ type cloud; axis xyz; points ({' '.join(pts)}); }} }}
    }}
"""


def setup_run(cfg: dict, mode: str, lev: int, name: str, alpha: float, iters: int, loading: str = "uniform",
              speed: float | None = None, lift_frac: float | None = None, pusher_T: float | None = None,
              thrust_scale: float = 1.0) -> Path:
    src = WORK / f"mesh_{'hover' if mode == 'transition' else mode}_{LT(lev)}"
    case = WORK / name
    mesh3d.copy_mesh(src, case)
    present = [r for r in REGIONS if (src / "constant" / "triSurface" / f"{r}.stl").exists()]
    ref = cfg["ref"]
    U = speed or cfg["op"]["cruise_speed_ms"]
    a = math.radians(alpha)
    if mode == "hover":
        coeff = None
        Uvec = (0.0, 0.0, 0.0)
    else:
        coeff = dict(lift=(-math.sin(a), 0, math.cos(a)), drag=(math.cos(a), 0, math.sin(a)), lref=ref["c_ref"], aref=ref["S_ref"] / 2)
        Uvec = (U * math.cos(a), 0.0, U * math.sin(a))
    mesh3d.write_solver(case, U=Uvec, nu=NU, rho=RHO, iters=iters, sym_patches=["sym_ymin"], coeff=coeff, force_patches=present,
                        cofr=(ref["x_ref"], 0, ref["z_ref"]), hover=(mode == "hover"), u_ref=(U if mode != "hover" else 10.0),
                        tu=0.002, visc_ratio=1.0, extra_functions=(pusher_inflow_function(cfg) if mode != "hover" else ""))
    rots = rotors_for(cfg, mode, loading, lift_frac=lift_frac, pusher_T=pusher_T, thrust_scale=thrust_scale)
    if rots:
        wfile(case, "system/topoSetDict", "dictionary", "topoSetDict", actuator.topo_actions(rots))
        wfile(case, "constant/fvOptions", "dictionary", "fvOptions", actuator.fv_options(rots, RHO))
    (case / "run_info.json").write_text(json.dumps(dict(mode=mode, alpha=alpha, U=U, rho=RHO, nu=NU, ref=ref, rotors=rots, regions=present,
                                                       lift_frac=lift_frac, pusher_T=pusher_T, thrust_scale=thrust_scale), indent=1))
    return case


def cruise(cfg, alphas, lev, iters, nproc, jobs, tag="", pusher_T=None):
    def one(a):
        name = f"cruise{tag}_{LT(lev)}_a{a:+05.1f}"
        mesh3d.run_or_resume(WORK / name, nproc, lambda: setup_run(cfg, "cruise", lev, name, a, iters, pusher_T=pusher_T),
                             potential=True, topo=True)
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(one, alphas))


def hover(cfg, lev, iters, nproc, loading, thrust_scale=1.0, tag=""):
    name = f"hover_{loading}{tag}_{LT(lev)}"
    mesh3d.run_or_resume(WORK / name, nproc, lambda: setup_run(cfg, "hover", lev, name, 0.0, iters, loading, thrust_scale=thrust_scale),
                         potential=False, topo=True)


def transition(cfg, lev, iters, nproc, speed, alpha, lift_frac, pusher_T, loading, tag=""):
    name = f"transition{tag}_{LT(lev)}_a{alpha:+05.1f}"
    mesh3d.run_or_resume(WORK / name, nproc, lambda: setup_run(cfg, "transition", lev, name, alpha, iters, loading, speed=speed,
                                                                lift_frac=lift_frac, pusher_T=pusher_T), potential=True, topo=True)


# ----------------------------------------------------------------------------- post-processing
def _case_row(case: Path, q: float) -> dict:
    info = json.loads((case / "run_info.json").read_text())
    q = 0.5 * RHO * info["U"] ** 2
    a = info["alpha"]
    c = coeffs(case, avg=200, fo="coeffs")
    ar = math.radians(a)
    ddir = np.array([math.cos(ar), 0, math.sin(ar)])
    ldir = np.array([-math.sin(ar), 0, math.cos(ar)])
    reg = {}
    for r in info["regions"]:
        f = mesh3d.read_forces(case, r, avg=40)
        F = np.array(f["F"])
        reg[r] = dict(drag_area_m2=float(2 * F @ ddir / q), lift_n=float(2 * F @ ldir),
                      CL=float(2 * F @ ldir / (q * info["ref"]["S_ref"])), CD=float(2 * F @ ddir / (q * info["ref"]["S_ref"])))
    return dict(case=case.name, alpha=a, CL=c["Cl"], CD=c["Cd"], Cm=c["CmPitch"], CL_std=c["Cl_std"], CD_std=c["Cd_std"],
                iterations=c["iterations"], regions=reg, U=info["U"])


def polar_fit(rows: list, ref: dict, mtow: float | None, U: float, cl_cruise: float | None = None) -> dict:
    al = np.array([r["alpha"] for r in rows]); CL = np.array([r["CL"] for r in rows]); CD = np.array([r["CD"] for r in rows])
    Cm = np.array([r["Cm"] for r in rows]); std = np.array([r["CL_std"] for r in rows])
    out = dict(CLmax_mean=float(CL.max()), alpha_CLmax=float(al[int(np.argmax(CL))]))
    i_max = int(np.argmax(CL))
    ok = (std < 0.01) & (np.arange(len(al)) < i_max) & (CL < 0.9 * CL.max())   # attached, pre-stall points
    if ok.sum() < 2:
        ok = (std < 0.01) & (np.arange(len(al)) <= i_max)
    out["fitted_alphas"] = al[ok].tolist()
    if ok.sum() >= 2:
        cla, cl0 = np.polyfit(al[ok], CL[ok], 1)
        k, cd0 = np.polyfit(CL[ok] ** 2, CD[ok], 1)   # with two points: exact parabola through both (no fit quality)
        cma, cm0 = np.polyfit(CL[ok], Cm[ok], 1)
        AR = ref["b_ref"] ** 2 / ref["S_ref"]
        out.update(CL_alpha_per_deg=cla, CL_alpha_per_rad=cla * 180 / math.pi, CL0=cl0, alpha_zero_lift_deg=-cl0 / cla,
                   CD0=cd0, k_induced=k, oswald_e=1 / (math.pi * AR * k) if k and k > 0 else None,
                   dCm_dCL=cma, Cm0=cm0, x_neutral_point_m=ref["x_ref"] - cma * ref["c_ref"], static_margin=-cma)
        if mtow:
            q = 0.5 * RHO * U**2
            # cruise CL at the sizing cruise condition (altitude / hot-day density) when given, else sea level
            CLc = cl_cruise or mtow * G0 / (q * ref["S_ref"])
            CDc = float(cd0 + k * CLc**2)
            out.update(cruise_CL=CLc, cruise_alpha_deg=(CLc - cl0) / cla, cruise_CD=CDc,
                       cruise_drag_n=float(mtow * G0 * CDc / CLc), cruise_CD_from=f"CD0 + k CL^2 through {int(ok.sum())} points")
            out["cruise_LD"] = CLc / out["cruise_CD"] if out.get("cruise_CD") else None
            out["stall_speed_ms_from_CLmax_mean"] = math.sqrt(2 * mtow * G0 / (RHO * ref["S_ref"] * out["CLmax_mean"]))
    return out


def post(cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    ref = cfg["ref"]
    U = cfg["op"]["cruise_speed_ms"]
    q = 0.5 * RHO * U**2
    mtow = cfg["geo"].get("mass", {}).get("mtow_kg") or cfg["geo"].get("mtow_kg")
    groups = {}
    for case in sorted(WORK.glob("cruise*_L*_a*")):
        try:
            row = _case_row(case, q)
        except Exception as e:  # noqa: BLE001
            print(case, e)
            continue
        groups.setdefault(case.name.split("_a")[0], []).append(row)
    res = dict(reference=ref, U=U, rho=RHO, mtow_kg=mtow, groups={})
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), dpi=140)
    for gname, rows in sorted(groups.items()):
        rows.sort(key=lambda r: r["alpha"])
        fit = polar_fit(rows, ref, mtow, U, cfg["geo"].get("aero", {}).get("cruise_CL")) if len(rows) >= 2 else {}
        res["groups"][gname] = dict(polar=rows, fit=fit)
        al = [r["alpha"] for r in rows]
        ax[0].plot(al, [r["CL"] for r in rows], "o-", label=gname)
        ax[1].plot([r["CD"] for r in rows], [r["CL"] for r in rows], "o-", label=gname)
        ax[2].plot([r["CL"] for r in rows], [r["Cm"] for r in rows], "o-", label=gname)
    sz = cfg["geo"].get("aero", {})
    if sz:
        cl = np.linspace(-0.2, sz.get("CLmax", 1.6), 40)
        AR = ref["b_ref"] ** 2 / ref["S_ref"]
        ax[1].plot(sz["CD0"] + cl**2 / (math.pi * AR * sz["oswald"]), cl, "k--", lw=1, label="sizing assumption")
        ax[0].axhline(sz.get("CLmax", 1.6), color="k", ls=":", lw=1, label="sizing CLmax")
    ax[0].set(xlabel="fuselage angle of attack (deg)", ylabel="CL"); ax[1].set(xlabel="CD", ylabel="CL")
    ax[2].set(xlabel="CL", ylabel="Cm about the CG"); ax[0].legend(fontsize=7); ax[1].legend(fontsize=7)
    for a_ in ax:
        a_.grid(alpha=.3)
    fig.suptitle(f"E8-200 full aircraft, OpenFOAM k-omega SST, {U:.1f} m/s, lift rotors stopped, pusher disk at cruise thrust")
    fig.tight_layout(); fig.savefig(OUT / "cruise_polar.png"); plt.close(fig)
    # drag breakdown of the baseline group at the cruise CL
    base = res["groups"].get("cruise_L+0w1") or res["groups"].get("cruise_L+0")
    if base and base["fit"].get("cruise_alpha_deg") is not None:
        rows = base["polar"]
        ac = base["fit"]["cruise_alpha_deg"]
        al = np.array([r["alpha"] for r in rows])
        regs = rows[0]["regions"].keys()
        bd = {r: float(np.interp(ac, al, [x["regions"][r]["drag_area_m2"] for x in rows])) for r in regs}
        a_zl = base["fit"]["alpha_zero_lift_deg"]
        zl = {r: float(np.interp(a_zl, al, [x["regions"][r]["drag_area_m2"] for x in rows])) for r in regs}
        res["drag_area_at_cruise_m2"] = bd
        if a_zl >= al.min():
            res["drag_area_at_zero_lift_m2"] = zl
        else:   # zero lift lies below the computed range: report the lowest computed angle instead (includes some induced drag)
            res["drag_area_at_lowest_alpha_m2"] = dict(zl, alpha_deg=float(al.min()))
        sd = json.loads((ROOT / "design" / "selected_design.json").read_text()).get("drag", {}).get("breakdown_m2", {})
        sizing_map = {"wing": sd.get("wing", 0), "fuselage": sd.get("fuselage", 0) + sd.get("cooling_inlets", 0),
                      "tail": sd.get("tail_h", 0) + sd.get("tail_v", 0), "booms": sd.get("booms", 0),
                      "rotors": sd.get("stopped_rotors", 0), "pusher": sd.get("pusher_pods", 0.0), "gear": sd.get("landing_gear", 0)}
        res["drag_area_sizing_m2"] = sizing_map
        fig, ax = plt.subplots(figsize=(8, 3.8), dpi=140)
        names = list(bd)
        xs = np.arange(len(names))
        ax.bar(xs - 0.27, [zl[n] for n in names], 0.27,
               label="CFD at zero lift" if a_zl >= al.min() else f"CFD at alpha {al.min():.0f} deg (lowest computed)")
        ax.bar(xs, [bd[n] for n in names], 0.27, label=f"CFD at cruise CL (alpha {ac:.1f} deg)")
        ax.bar(xs + 0.27, [sizing_map.get(n, 0) for n in names], 0.27, label="sizing build-up (zero lift)")
        ax.set_xticks(xs, names); ax.set_ylabel("drag area D/q (m^2)"); ax.legend(fontsize=7); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(OUT / "drag_breakdown.png"); plt.close(fig)
    (OUT / "cruise.json").write_text(json.dumps(res, indent=1, default=float))
    # hover and transition
    for case in sorted(WORK.glob("hover_*")) + sorted(WORK.glob("transition*")):
        if not (case / "postProcessing").exists():
            continue
        info = json.loads((case / "run_info.json").read_text())
        lift_rot = [r for r in info["rotors"] if not r["name"].startswith("pusher_disk")]
        T_tot = sum(r["thrust_n"] * 2 * r["domain_fraction"] for r in lift_rot)
        reg, band, fx = {}, {}, {}
        for r in info["regions"]:
            try:
                f = mesh3d.read_forces(case, r, avg=100)
            except Exception:  # noqa: BLE001
                continue
            reg[r] = float(2 * f["F"][2]); band[r] = [float(2 * f["F_min"][2]), float(2 * f["F_max"][2])]
            fx[r] = float(2 * f["F"][0])
        out = dict(case=case.name, mode=info["mode"], U=info["U"], alpha=info["alpha"], vertical_force_by_region_n=reg, band_n=band,
                   axial_force_by_region_n=fx, rotor_thrust_total_n=T_tot, iterations=f["iterations"] if reg else None)
        if info["mode"] == "hover":
            DL = -sum(reg.values())
            out.update(download_n=DL, download_fraction=DL / T_tot if T_tot else None, weight_n=mtow * G0 if mtow else None)
        else:
            out.update(airframe_lift_n=sum(reg.values()), airframe_drag_n=sum(fx.values()), pusher_thrust_n=info.get("pusher_T"),
                       lift_rotor_thrust_n=T_tot)
        (OUT / f"{case.name}.json").write_text(json.dumps(out, indent=1))
        print(json.dumps({k: v for k, v in out.items() if "band" not in k}, indent=1))
    print(json.dumps({g: v["fit"] for g, v in res["groups"].items()}, indent=1, default=float))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["geometry", "mesh", "cruise", "hover", "transition", "post"])
    ap.add_argument("--geometry", type=Path, default=ROOT / "design" / "geometry.json")
    ap.add_argument("--design", type=Path, default=ROOT / "design" / "selected_design.json")
    ap.add_argument("--mode", default="cruise", choices=["cruise", "hover"])
    ap.add_argument("--lev", type=int, default=0)
    ap.add_argument("--alphas", type=float, nargs="*", default=[-4, 0, 4, 8])
    ap.add_argument("--iters", type=int, default=2000)
    ap.add_argument("--nproc", type=int, default=MAX_CORES)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--loading", default="linear", choices=["uniform", "linear"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--work", type=Path, default=None, help="scratch folder of the cases (default cfd/.cache/aircraft)")
    ap.add_argument("--out", type=Path, default=None, help="results folder (default cfd/results)")
    ap.add_argument("--lift-extra", type=int, default=0, help="extra refinement levels on wing and tail (1 = c/128)")
    ap.add_argument("--pusher-thrust", type=float, default=None)
    ap.add_argument("--thrust-scale", type=float, default=1.0)
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--lift-frac", type=float, default=None)
    a = ap.parse_args()
    cfg = load(a.geometry, a.design)
    LIFT_EXTRA[0] = a.lift_extra
    global WORK, OUT
    if a.work:
        WORK = a.work
    if a.out:
        OUT = a.out
    if a.what == "geometry":
        geometry(cfg)
    elif a.what == "mesh":
        mesh(cfg, a.mode, a.lev, a.nproc)
    elif a.what == "cruise":
        cruise(cfg, a.alphas, a.lev, a.iters, max(1, a.nproc // a.jobs), a.jobs, tag=a.tag, pusher_T=a.pusher_thrust)
    elif a.what == "hover":
        hover(cfg, a.lev, a.iters, a.nproc, a.loading, a.thrust_scale, a.tag)
    elif a.what == "transition":
        transition(cfg, a.lev, a.iters, a.nproc, a.speed, a.alphas[0], a.lift_frac, a.pusher_thrust, a.loading, a.tag)
    else:
        post(cfg)


if __name__ == "__main__":
    main()
