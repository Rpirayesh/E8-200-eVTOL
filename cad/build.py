"""Build every E8-200 part and tooling item from design/geometry.json, export manufacturing and viewer files,
and run the mass / CG / clearance audit.

    ~/tools/cadenv/bin/python cad/build.py [--no-step-assembly] [--only PID,PID]

Outputs
  cad/parts/<ID>/<ID>.step|.stl          per unique made part and tooling item (mm, part bounding box at the origin)
  cad/assembly/E8-200_assembly.step      aircraft assembly (tooling excluded)
  cad/parts.json, docs/data/parts.json   part records (process, material, qty, mass, envelope, notes, instances)
  cad/mass_properties.json               CAD mass and CG by group
  docs/models/<ID>.glb, docs/models/E8-200_assembly.glb   viewer meshes
  validation/cad/*                       mass/CG audit, clearance and interference checks (cad/audit.py)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from build123d import Compound, Plane, export_step, export_stl
from build123d import CenterOf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from e8cad import booms, fuselage, gear, systems, tail, tooling, wing  # noqa: E402
from e8cad.config import MATS, PANEL, ROOT, S, SHOP, Part, rho  # noqa: E402

PROC_ORDER = ["CNC", "FDM", "composite-layup", "COTS", "COTS-cut", "outsourced-waterjet", "outsourced-bend", "outsourced-thermoform"]
MAT_COLOR = {
    "xps_foam": [236, 232, 214], "pvc_h80": [214, 196, 150], "pvc_h100": [205, 180, 130], "cf_ud_wet": [40, 40, 44],
    "cf_fabric_wet": [52, 54, 60], "cf_tube": [30, 30, 33], "eglass_fabric_wet": [232, 236, 240], "al6061": [176, 182, 190],
    "steel": [120, 124, 130], "polycarbonate": [150, 200, 235, 110], "sandwich": [120, 128, 140], "asa": [220, 220, 220],
    "mdf": [182, 150, 110], "eps_tooling_foam": [200, 220, 240], "birch_plywood": [214, 178, 120], "confor": [40, 70, 140],
    "uhmw": [245, 245, 245], "petg": [70, 120, 200], "pa_cf": [45, 47, 52], "payload": [235, 160, 90, 150],
}
COTS_COLOR = {"MOT": [150, 30, 30], "ROT": [25, 25, 28], "PROP": [25, 25, 28], "INV": [40, 80, 160], "BAT-MOD": [60, 140, 70],
              "BMS": [30, 30, 30], "HV": [240, 120, 20], "CHUTE": [230, 80, 40], "AV": [30, 30, 30], "LV": [70, 70, 70],
              "COOL": [60, 130, 200], "FC": [40, 40, 40], "OCC": [235, 160, 90, 140], "HARN": [30, 60, 140],
              "W-AIL-ACT": [90, 90, 120], "TL-ACT": [90, 90, 120], "CAN-LATCH": [60, 60, 60], "FURN": [90, 90, 95]}


def color_for(p: Part):
    if p.process == "COTS":
        for k, c in COTS_COLOR.items():
            if p.pid.startswith(k):
                return c + [255] if len(c) == 3 else c
        return [200, 60, 60, 255]
    m = p.material
    if m.startswith("sandwich"):
        c = MAT_COLOR["sandwich"]
    else:
        c = next((v for k, v in MAT_COLOR.items() if k in m), [180, 180, 180])
    return c + [255] if len(c) == 3 else c


def material_keys(p: Part):
    keys = [k for k in list(MATS.keys()) + ["xps_foam", "eps_tooling_foam", "mdf", "polycarbonate", "confor_cf45", "g10",
                                             "uhmw_pe", "birch_plywood", "nylon_strap"] if k in p.material]
    if p.material.startswith("sandwich"):
        keys = PANEL["keys"]
    return sorted(set(keys))


def loc_matrix(loc, mirror=False):
    T = loc.wrapped.Transformation()
    M = np.array([[T.Value(i, j) for j in range(1, 5)] for i in range(1, 4)] + [[0, 0, 0, 1]])
    if mirror:
        M = M @ np.diag([1.0, -1.0, 1.0, 1.0])
    return M


def solid_com(s):
    try:
        c = s.center(CenterOf.MASS)
    except Exception:
        c = s.center()
    return np.array([c.X, c.Y, c.Z])


def mass_props(p: Part):
    """mass per instance (kg) and local CG (mm)."""
    if p.mass_kg is not None:
        cg = p.settings.get("_cg_local")
        return float(p.mass_kg), (np.array(cg) if cg is not None else solid_com(p.solid))
    if p.bodies:
        ms, cs = [], []
        for s, r in p.bodies:
            ms.append(s.volume * 1e-9 * r)
            cs.append(solid_com(s))
        ms = np.array(ms)
        return float(ms.sum()), (np.array(cs) * ms[:, None]).sum(0) / ms.sum()
    return float(p.solid.volume * 1e-9 * p.density), solid_com(p.solid)


def tess(solid, tol, ang=0.3):
    try:
        verts, faces = solid.tessellate(tol, ang)
    except Exception:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "m.stl"
            export_stl(solid, str(f), tolerance=tol, angular_tolerance=ang)
            m = trimesh.load(f, force="mesh")
        return trimesh.Trimesh(np.asarray(m.vertices, dtype=np.float32), m.faces, process=False)
    v = np.array([[q.X, q.Y, q.Z] for q in verts], dtype=np.float32)
    f = np.array(faces, dtype=np.int64)
    return trimesh.Trimesh(v, f, process=False)


def piece_size(solid):
    """Envelope of the largest separate body (a part made of several loose pieces is checked piece by piece)."""
    sols = list(solid.solids()) if hasattr(solid, "solids") else [solid]
    best = None
    for s in sols:
        bb = s.bounding_box()
        sz = [bb.size.X, bb.size.Y, bb.size.Z]
        if best is None or max(sz) > max(best):
            best = sz
    return best


def volume_mesh(solid, mesh, tol):
    """Watertight mesh for the interference scan: the display mesh if it is a volume, else the manifold union of the
    separately tessellated bodies (multi-body laminates, cores, manikin)."""
    m = mesh.copy()
    m.merge_vertices()
    if m.is_volume:
        return m
    parts = []
    sols = list(solid.solids())
    for s in sols:
        try:
            q = tess(s, tol, 0.35)
            q.merge_vertices()
            if q.is_volume:
                parts.append(q)
        except Exception:
            pass
    if len(parts) < len(sols):
        return m
    try:
        u = trimesh.boolean.union(parts, engine="manifold") if len(parts) > 1 else parts[0]
        return u if u.is_volume else m
    except Exception:
        return m


def machine_fit(p: Part, size):
    lim = {"cnc": SHOP["cnc_bed_mm"], "cnc_plug": SHOP["cnc_bed_mm"], "cnc_metal": SHOP["cnc_metal_mm"], "fdm": SHOP["fdm_mm"]}
    if p.machine == "hotwire":
        ok = size[1] <= SHOP["hotwire_bow_mm"] and sorted([size[0], size[2]])[1] <= SHOP["cnc_bed_mm"][0]
        return dict(machine="hot-wire bow", limit_mm=SHOP["hotwire_bow_mm"], fits=bool(ok))
    if p.machine not in lim:
        return dict(machine="none (lay-up / bought)", fits=True)
    L = sorted(lim[p.machine])
    ok = all(a <= b + 0.5 for a, b in zip(sorted(size), L))
    return dict(machine=p.machine, limit_mm=lim[p.machine], fits=bool(ok))


def write_tree(meta):
    """Part tree (group -> parts) between the markers of cad/README.md."""
    rd = HERE / "README.md"
    if not rd.exists():
        return
    txt = rd.read_text()
    a, b = "<!-- PART TREE START -->", "<!-- PART TREE END -->"
    if a not in txt:
        return
    L = [a, "", "## Part tree (generated by build.py)", ""]
    groups = {}
    for m in meta:
        groups.setdefault("Tooling" if m["tooling"] else m["group"], []).append(m)
    for g, ms in groups.items():
        n = sum(m["qty"] for m in ms)
        L += [f"### {g} ({len(ms)} unique, {n} pieces)", "", "| ID | name | process | material | qty | kg each | envelope mm | machine |",
              "|---|---|---|---|---|---|---|---|"]
        for m in ms:
            mf = m["machine_fit"]
            fit = mf["machine"] if mf.get("limit_mm") is None else f"{mf['machine']}: {'fits' if mf['fits'] else 'split'}"
            if m["joints"]:
                fit += " (joints)"
            L.append(f"| {m['id']} | {m['name']} | {m['process']} | {m['material']} | {m['qty']} | {m['mass_kg_each']:.3f} | "
                     f"{' x '.join(f'{v:.0f}' for v in m['envelope_mm'])} | {fit} |")
        L.append("")
    L.append(b)
    i0, i1 = txt.index(a), txt.index(b) + len(b)
    rd.write_text(txt[:i0] + "\n".join(L) + txt[i1:])


def generate(only=None):
    t0 = time.time()
    gens = [wing.wing_parts, booms.boom_parts, tail.tail_parts, fuselage.fuselage_parts, gear.gear_parts,
            systems.battery_parts, systems.pusher_parts, systems.chute_parts, systems.cabin_parts, systems.harness_parts,
            tooling.tooling_parts]
    parts = []
    for g in gens:
        t = time.time()
        ps = g()
        parts += ps
        print(f"  {g.__module__.split('.')[-1]}.{g.__name__}: {len(ps)} parts in {time.time() - t:.1f} s", flush=True)
    ids = [p.pid for p in parts]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, dup
    # occupant mass acts at the design occupant point (the part origin)
    empty = [p.pid for p in parts if not getattr(p.solid, "wrapped", None) or p.solid.volume < 1.0]
    if empty:
        print("  skipped empty parts:", empty, flush=True)
    parts = [p for p in parts if p.pid not in empty]
    for p in parts:
        if p.pid == "OCC":
            p.settings["_cg_local"] = [0.0, 0.0, 0.0]
    # HV harness budget shared by conduit volume (all runs ~ same cross-section)
    hv = [p for p in parts if p.mass_group == "hv_harness" and p.mass_kg is None]
    assigned = sum(p.mass_kg * len(p.placements) for p in parts if p.mass_group == "hv_harness" and p.mass_kg is not None)
    vol = sum(p.solid.volume * len(p.placements) for p in hv)
    for p in hv:
        p.mass_kg = max(S["mass_kg"]["breakdown"]["hv_harness"] - assigned, 0.0) * p.solid.volume / vol
        p.mass_source = "remainder of the hv_harness budget shared by conduit volume"
    if only:
        parts = [p for p in parts if p.pid in only]
    print(f"generated {len(parts)} unique parts in {time.time() - t0:.1f} s", flush=True)
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-step-assembly", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--audit-only", action="store_true", help="regenerate and tessellate, run the audit, write no part files")
    a = ap.parse_args()
    t0 = time.time()
    parts = generate(set(a.only.split(",")) if a.only else None)
    out_parts = ROOT / "cad" / "parts"
    out_models = ROOT / "docs" / "models"
    for d in (out_parts, out_models, ROOT / "docs" / "data", ROOT / "cad" / "assembly"):
        d.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    meta, placed = [], []
    meshes, inst_all, disp = {}, [], {}
    tot_m, tot_mx = 0.0, np.zeros(3)
    groups = {}
    for p in parts:
        bb = p.solid.bounding_box()
        size = [bb.size.X, bb.size.Y, bb.size.Z]
        diag = float(np.linalg.norm(size))
        m_each, cg_loc = mass_props(p)
        files = {}
        if p.process != "COTS" and not a.audit_only:
            d = out_parts / p.pid
            d.mkdir(exist_ok=True)
            local = p.solid.translate((-bb.min.X, -bb.min.Y, -bb.min.Z))
            export_step(local, str(d / f"{p.pid}.step"))
            stl_tol = min(max(diag * 1.5e-4, 0.05), 0.6)
            if p.pid.startswith("T-PLUG") or p.pid.startswith("W-CORE"):
                stl_tol = min(max(diag * 4e-4, 0.2), 1.0)
            export_stl(local, str(d / f"{p.pid}.stl"), tolerance=stl_tol, angular_tolerance=0.2)
            files = {"step": f"cad/parts/{p.pid}/{p.pid}.step", "stl": f"cad/parts/{p.pid}/{p.pid}.stl",
                     "stl_tolerance_mm": round(stl_tol, 3)}
        gtol = min(max(diag * 4e-4, 0.3), 3.0)
        if p.pid.startswith(("BAT-MOD", "BAT-TIER")):
            gtol = 1.5
        mesh = tess(p.solid, gtol, 0.35 if not p.pid.startswith(("BAT-MOD", "BAT-TIER")) else 0.9)
        col = color_for(p)
        mesh.visual.face_colors = col
        if not a.audit_only:
            mesh.export(out_models / f"{p.pid}.glb")
        meshes[p.pid] = mesh if p.tooling else volume_mesh(p.solid, mesh, gtol)
        disp[p.pid] = mesh
        inst = []
        for k, (loc, mir) in enumerate(p.placements):
            M = loc_matrix(loc, mir)
            inst.append(np.round(M, 6).tolist())
            if p.tooling:
                continue
            scene.add_geometry(mesh, node_name=f"{p.pid}#{k}", geom_name=p.pid, transform=M)
            c = (M @ np.append(cg_loc, 1.0))[:3]
            tot_m += m_each
            tot_mx += m_each * c
            g = groups.setdefault(p.mass_group, {"kg": 0.0, "mx": np.zeros(3), "parts": []})
            g["kg"] += m_each
            g["mx"] += m_each * c
            if p.pid not in g["parts"]:
                g["parts"].append(p.pid)
            s = p.solid.mirror(Plane.XZ) if mir else p.solid
            if p.pid.startswith(("BAT-MOD", "BAT-TIER")):   # assembly STEP carries the module envelope, cells are in the part STEP
                bb_ = p.solid.bounding_box()
                from e8cad.geom import box as _box
                s = _box(bb_.min.X, bb_.max.X, bb_.min.Y, bb_.max.Y, bb_.min.Z, bb_.max.Z)
            placed.append((p.pid, s.moved(loc)))
            inst_all.append((p.pid, k, M))
        meta.append(dict(
            id=p.pid, name=p.name, group=p.group, process=p.process, material=p.material, material_keys=material_keys(p),
            qty=len(p.placements), mass_kg_each=round(m_each, 4), mass_source=p.mass_source if p.mass_kg is not None or p.bodies is None else "CAD volume x density (per body)",
            mass_group=p.mass_group, envelope_mm=[round(v, 1) for v in size], notes=p.notes, joints=p.joints,
            machine_fit=machine_fit(p, piece_size(p.solid)), settings={k: v for k, v in p.settings.items() if not k.startswith("_")},
            files=files, glb=f"models/{p.pid}.glb", color=col, instances=inst, purchased=p.purchased, skin=p.skin,
            tooling=p.tooling, cg_local_mm=[round(float(v), 1) for v in cg_loc]))
        print(f"  {p.pid:16s} x{len(p.placements):3d} {m_each:9.3f} kg  {time.time() - t0:6.0f} s", flush=True)
    if not a.audit_only:
        scene.export(out_models / "E8-200_assembly.glb")
    cg = tot_mx / tot_m
    mp = dict(cad_mass_kg=tot_m, cg_mm=cg.tolist(),
              by_group={k: dict(kg=v["kg"], cg_mm=(v["mx"] / v["kg"]).tolist() if v["kg"] > 0 else None, parts=v["parts"])
                        for k, v in groups.items()},
              design_mtow_kg=S["mass_kg"]["mtow"], design_cg_m=S["loading_cases"]["pilot + passenger (MTOW)"]["cg_m"])
    (ROOT / "cad" / "mass_properties.json").write_text(json.dumps(mp, indent=1))
    proc_count = {}
    for m in meta:
        key = "tooling" if m["tooling"] else "aircraft"
        proc_count.setdefault(key, {}).setdefault(m["process"], {"unique": 0, "instances": 0})
        proc_count[key][m["process"]]["unique"] += 1
        proc_count[key][m["process"]]["instances"] += m["qty"]
    doc = dict(
        _about="E8-200 part list generated by cad/build.py from design/geometry.json (mm, kg). Instances are 4x4 placement "
               "matrices (mirror placements have a negative determinant) applied to each part's modelling frame.",
        shop_limits=SHOP, design=dict(name=S["name"], mtow_kg=S["mass_kg"]["mtow"]), process_count=proc_count,
        mass=mp, parts=meta)
    if not a.audit_only:
        (ROOT / "cad" / "parts.json").write_text(json.dumps(doc, indent=1))
        (ROOT / "docs" / "data" / "parts.json").write_text(json.dumps(doc, indent=1))
    print(f"CAD mass {tot_m:.1f} kg, CG {np.round(cg, 1)} mm; exports in {time.time() - t0:.0f} s", flush=True)
    if not a.audit_only:
        write_tree(meta)
    if not a.no_step_assembly and not a.audit_only:
        asm = Compound(children=[s for _, s in placed])
        export_step(asm, str(ROOT / "cad" / "assembly" / "E8-200_assembly.step"))
        print(f"assembly STEP written ({time.time() - t0:.0f} s)", flush=True)
        import subprocess                                   # compressed copy for the repository (< 100 MB file limit)
        subprocess.run(["xz", "-T0", "-9", "-k", "-f", str(ROOT / "cad" / "assembly" / "E8-200_assembly.step")], check=False)
    if not a.no_audit:
        import audit
        audit.run(parts, placed, mp, meshes, inst_all, disp)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
