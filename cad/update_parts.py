"""Regenerate selected parts only (STEP/STL/GLB, parts.json entries, mass_properties by delta).

    ~/tools/cadenv/bin/python cad/update_parts.py CH-CRADLE PY-C W-FIT-MS ...

Runs only the generator modules that own the requested parts. The assembly STEP/GLB, the audit and the README part
tree are refreshed by the next full `cad/build.py` run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from build123d import export_step, export_stl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as Bd  # noqa: E402
from e8cad.config import ROOT  # noqa: E402

OWNER = {  # part ID prefix -> (module, generator)
    "W-": ("wing", "wing_parts"), "F-CLV": ("wing", "root_fittings"), "W-FIT": ("wing", "root_fittings"),
    "W-PIN": ("wing", "root_fittings"), "W-CHUTE": ("wing", "wing_parts"),
    "PY-": ("booms", "station_parts"), "MP": ("booms", "station_parts"), "NAC": ("booms", "station_parts"),
    "CH-": ("systems", "chute_parts"), "CAN-": ("fuselage", "fuselage_parts"), "WIN-": ("fuselage", "fuselage_parts"),
    "SH-": ("fuselage", "fuselage_parts"),
}


def owner(pid):
    for k in sorted(OWNER, key=len, reverse=True):
        if pid.startswith(k):
            return OWNER[k]
    raise KeyError(pid)


def main(pids):
    import importlib
    gens = sorted({owner(p) for p in pids})
    new = {}
    for mod, fn in gens:
        for p in getattr(importlib.import_module(f"e8cad.{mod}"), fn)():
            if p.pid in pids:
                new[p.pid] = p
    doc = json.loads((ROOT / "cad" / "parts.json").read_text())
    meta = {m["id"]: m for m in doc["parts"]}
    mp = doc["mass"]
    tot_m, tot_mx = mp["cad_mass_kg"], np.array(mp["cg_mm"]) * mp["cad_mass_kg"]
    report = []
    for pid, p in new.items():
        old = meta[pid]
        m_new, cg_new = Bd.mass_props(p)
        bb = p.solid.bounding_box()
        size = [bb.size.X, bb.size.Y, bb.size.Z]
        diag = float(np.linalg.norm(size))
        d = ROOT / "cad" / "parts" / pid
        d.mkdir(parents=True, exist_ok=True)
        local = p.solid.translate((-bb.min.X, -bb.min.Y, -bb.min.Z))
        export_step(local, str(d / f"{pid}.step"))
        stl_tol = min(max(diag * 1.5e-4, 0.05), 0.6)
        export_stl(local, str(d / f"{pid}.stl"), tolerance=stl_tol, angular_tolerance=0.2)
        mesh = Bd.tess(p.solid, min(max(diag * 4e-4, 0.3), 3.0), 0.35)
        mesh.visual.face_colors = old["color"]
        mesh.export(ROOT / "docs" / "models" / f"{pid}.glb")
        g = mp["by_group"].setdefault(p.mass_group, {"kg": 0.0, "cg_mm": [0, 0, 0], "parts": [pid]})
        for M in old["instances"]:
            M = np.array(M)
            c_old = (M @ np.append(old["cg_local_mm"], 1.0))[:3]
            c_new = (M @ np.append(cg_new, 1.0))[:3]
            tot_m += m_new - old["mass_kg_each"]
            tot_mx += m_new * c_new - old["mass_kg_each"] * c_old
            g["kg"] += m_new - old["mass_kg_each"]
        report.append((pid, old["mass_kg_each"], m_new, len(old["instances"])))
        old.update(mass_kg_each=round(m_new, 4), envelope_mm=[round(v, 1) for v in size], notes=p.notes, joints=p.joints,
                   machine_fit=Bd.machine_fit(p, Bd.piece_size(p.solid)), material=p.material, material_keys=Bd.material_keys(p),
                   cg_local_mm=[round(float(v), 1) for v in cg_new],
                   files={"step": f"cad/parts/{pid}/{pid}.step", "stl": f"cad/parts/{pid}/{pid}.stl", "stl_tolerance_mm": round(stl_tol, 3)})
    mp["cad_mass_kg"] = tot_m
    mp["cg_mm"] = (tot_mx / tot_m).tolist()
    mp["note_incremental"] = "updated by cad/update_parts.py; assembly files and the audit refresh on the next full build"
    (ROOT / "cad" / "parts.json").write_text(json.dumps(doc, indent=1))
    (ROOT / "docs" / "data" / "parts.json").write_text(json.dumps(doc, indent=1))
    (ROOT / "cad" / "mass_properties.json").write_text(json.dumps(mp, indent=1))
    dm = 0.0
    for pid, mo, mn, q in report:
        print(f"{pid:12s} x{q}  {mo:8.3f} -> {mn:8.3f} kg each  ({(mn - mo) * q:+.3f} kg)")
        dm += (mn - mo) * q
    print(f"total delta {dm:+.3f} kg; CAD mass {tot_m:.1f} kg, CG {np.round(tot_mx / tot_m, 1)} mm")


if __name__ == "__main__":
    main(sys.argv[1:])
