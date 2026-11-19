"""Collect every margin of safety of the E8-200 structural analysis into fea/results/margins.json (lowest first)
and the mass change versus design/selected_design.json.

    ~/tools/cadenv/bin/python fea/margins.py

Sources: fea/results/sizing_update.json (beam-model members, all load cases), parts.json (CalculiX fittings + analytic
lug/bolt checks), fuselage.json (sandwich panels, battery box/mounts, seats), gear.json (landing energy),
dynamics.json (divergence, flutter, whirl, Campbell).  Run airframe/sizing/parts/fuselage/gear/dynamics first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HERE = Path(__file__).resolve().parent
R = HERE / "results"
ROOT = HERE.parent
COUNT = dict(P1=4, P2=4, P3=8, P4=4, P5=3, P6=8, P7=8)


def J(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    rows = []

    def add(item, ms, mode, case="", source="", note=""):
        rows.append(dict(item=item, MS=float(ms), mode=mode, case=case, source=source, note=note))
    sz = J("sizing_update.json")
    g_now = json.loads((ROOT / "design" / "geometry.json").read_text())
    fin = J("airframe_final33.json")
    if fin.get("envelope"):
        # final iteration-3.3 configuration (geometry.json rotors/gear + sizing, CAD gear leg 76.2 x 2.41 mm); loads scaled
        # up to the design MTOW kept for the fittings (1,350.4 kg)
        kw = 1350.378 / g_now["mtow_kg"]
        for grp, v in fin["envelope"].items():
            add(f"member: {grp}", (1 + v["MS"]) / kw - 1, v["mode"], v["case"], "beam model, final 3.3 configuration (airframe_final33.json)",
                f"ultimate; result x 1/{kw:.4f} to MTOW 1,350.4 kg")
    else:
        for grp, v in sz.get("_min_MS", {}).items():
            add(f"member: {grp}", v["MS"], v["mode"], v["case"], "beam model (fea/airframe.py + sizing.py)",
                "ultimate; strength allowables of fea/materials.json")
    # mesh-sensitivity factor on the CalculiX fitting peaks from the P1 convergence study (validation D6): finest-mesh peak
    # over the production-mesh peak; applied to every fitting
    vd = json.loads((ROOT / "validation" / "fea" / "results" / "dynamics_checks.json").read_text()) \
        if (ROOT / "validation" / "fea" / "results" / "dynamics_checks.json").exists() else {}
    kmesh = 1.0
    if vd.get("D6"):
        mesh = vd["D6"]["mesh"]
        prod = min(mesh, key=lambda r: abs(r["hmax"] - 7.0))
        kmesh = max(1.0, mesh[-1]["peak_MPa"] / prod["peak_MPa"])
    cadp = J("parts_cad.json")
    CADMAP = dict(P1=("W-FIT-MS", "W-FIT-RS"), P2=("BC-W", "BC-WR"), P3=("MP",), P4=("LG-SADDLE",), P5=("CH-ATT-R", "W-CHUTE-FIT"),
                  P6=("SEAT-FIT",), P7=("PY-C",))
    # every CAD part was run on the iteration-3.3 STEP at MTOW 1,350.4 kg; the lift-rotor mount parts last run at the 4,240 N
    # structural thrust are scaled to the final 4,267 N (PY-C was re-run at 4,267 N)
    T_now = max(r["max_thrust_N"] for r in g_now["rotors"])
    for k in ("MP", "MP-EMX"):
        if k in cadp:
            f_ = T_now / 4240.0
            v = cadp[k]
            cadp[k] = dict(v, MS_ultimate=(1 + v["MS_ultimate"]) / f_ - 1, MS_yield_limit=(1 + v["MS_yield_limit"]) / f_ - 1,
                           note=f"run at 4,240 N, scaled x 1/{f_:.4f} to {T_now:.0f} N")
    for k, v in cadp.items():
        add(f"fitting {k} (CAD STEP part, CalculiX C3D10)", (1 + v["MS_ultimate"]) / kmesh - 1,
            f"von Mises vs Ftu (ult. x 1.15, x {kmesh:.2f} mesh factor)", "", "fea/parts_cad.py", v.get("note", ""))
        add(f"fitting {k} (CAD) yield at limit", (1 + v["MS_yield_limit"]) / kmesh - 1, "von Mises vs Fty at limit", "", "fea/parts_cad.py")
    for k, v in J("parts.json").items():
        if all(c in cadp for c in CADMAP.get(k, ("-",))):
            continue                                   # the CAD part governs; parametric result kept in parts.json only
        add(f"fitting {v['part']} (CalculiX C3D10)", (1 + v["MS_ultimate"]) / kmesh - 1, f"von Mises vs Ftu (ult. x 1.15, x {kmesh:.2f} mesh factor)",
            v.get("load_case", ""), "fea/parts.py")
        add(f"fitting {v['part']} yield at limit", (1 + v["MS_yield_limit"]) / kmesh - 1, "von Mises vs Fty at limit", v.get("load_case", ""), "fea/parts.py")
        for chk in ("lug", "bolts", "motor_bolts", "isolator_studs"):
            if chk in v:
                for kk, vv in v[chk].items():
                    if kk.endswith("_MS"):
                        add(f"fitting {v['part']} {chk} {kk[:-3]}", vv, "analytic", v.get("load_case", ""), "fea/parts.py")
    p2 = J("parts.json").get("P2")
    if p2 and "boom_bearing_MPa" in p2:
        from fea.geometry import MAT
        allow = 0.5 * MAT["cf_ud_wet"]["design"]["Yc"] / 1e6
        add("boom wall bearing under the saddle clamp (transverse crushing)", allow / p2["boom_bearing_MPa"] - 1,
            "clamp pressure vs 0.5 Yc (wet UD over-wrap)", p2.get("load_case", ""), "fea/parts.py")
    fu = J("fuselage.json")
    for c in fu.get("checks", []):
        add(f"cabin: {c['item']}", c["MS"], "sandwich / hand method", "envelope", "fea/fuselage.py", c.get("note", ""))
    de = J("details.json")
    for c in de.get("checks", []):
        if "wrinkling on xps_foam" in c["item"] and (ROOT / "cad" / "parts" / "W-H45-U" / "W-H45-U.step").exists():
            continue                    # the H45 support (W-H45-U) is in the CAD; the H45 row governs
        if "parachute cradle beam" in c["item"] and "CH-CRADLE" in cadp:
            continue                    # superseded by the CalculiX run on the one-body CAD cradle
        add(f"detail: {c['item']}", c["MS"], "hand method", "envelope", "fea/details.py", c.get("note", ""))
    ge = J("gear.json")
    if ge.get("damped_gear"):
        dg = ge["damped_gear"]
        add("landing gear (oleo dampers, pivoted legs): limit drop inertia factor <= 3.0", dg["MS_inertia_factor"], "energy (0.33 m drop, L = 2/3 W)",
            "limit drop", "fea/gear.py", f"n = {dg['n_inertia']:.2f}, skid travel {dg['skid_travel_at_full_stroke_mm']:.0f} mm at full stroke")
        if dg.get("reserve_drop_1p5h_stroke_needed_mm"):
            add("landing gear reserve drop 1.5 h: stroke available / needed", dg["stroke_mm"] / dg["reserve_drop_1p5h_stroke_needed_mm"] - 1,
                "stroke", "reserve drop", "fea/gear.py")
    elif ge:
        cg = ge["current_gear"]
        add("landing gear: limit drop, inertia factor <= 3.0", 3.0 / cg["n_inertia"] - 1, "energy (0.33 m drop, L = 2/3 W)", "limit drop",
            "fea/gear.py", ge["verdict"])
        add("landing gear: cross tube yield at the limit drop", cg["MS_yield_at_limit_drop"], "elastic stress vs Fty", "limit drop", "fea/gear.py")
    dy = J("dynamics.json")
    if dy:
        add("wing divergence vs 1.2 VD", dy["divergence"]["margin"], "speed margin", "", "fea/dynamics.py")
        fl = dy.get("flutter_modal", {})
        if fl.get("margin") is not None:
            add("flutter (modal, strip Theodorsen) vs 1.2 VD", fl["margin"], "speed margin", "", "fea/dynamics.py")
        wh = dy.get("pusher_whirl", {})
        if wh:
            add("pusher whirl flutter: stiffness margin at 1.2 VD", 1 / wh["stiffness_fraction_still_stable_at_1p2VD"] - 1,
                "mount stiffness ratio", "", "fea/dynamics.py")
        high = [f for f in dy.get("campbell_flags", []) if f["severity"] == "HIGH"]
        add("frequency placement: boom/rotor modes within +-10 % of hover 1P/2P", -1.0 if high else 1.0, f"{len(high)} HIGH flags", "",
            "fea/dynamics.py", "not a strength margin: -1 flags an open item (see README)")
    cm = J("cad_member_checks.json")
    for k, v in cm.items():
        if not isinstance(v, dict):
            continue
        for kk, vv in v.items():
            if kk == "MS" or kk.endswith("_MS"):
                add(f"CAD section {k} {'' if kk == 'MS' else kk[:-3]}".strip(), vv, v.get("basis", ""), "", "fea/results/cad_member_checks.json",
                    v.get("section", ""))
    rows.sort(key=lambda r: r["MS"])
    for r in rows:              # sensitivity: all loads scaled with MTOW (+3.3 %, iteration 3.3 estimate)
        r["MS_at_plus_3p3pct_MTOW"] = (1 + r["MS"]) / 1.033 - 1 if r["MS"] > -1 else r["MS"]
    # ---------------------------------------------------------------- masses
    sel = json.loads((ROOT / "design" / "selected_design.json").read_text())
    bd = sel["mass_kg"]["breakdown"]
    mm = sz.get("_member_masses_kg", {})
    o, n = mm.get("original_geometry", {}), mm.get("sized", {})
    d = {}
    d["wing spars + torsion skin (in wing)"] = sum(n.get(k, 0) - o.get(k, 0) for k in ("spar main", "spar rear", "wing torsion skin (+-45, box upper+lower)"))
    d["boom tubes (in booms)"] = (n.get("boom_L", 0) + n.get("boom_R", 0)) - (o.get("boom_L", 0) + o.get("boom_R", 0))
    d["tail spar (in tail)"] = n.get("tail spar", 0) - o.get("tail spar", 0)
    d["gear legs, pivoted, 76 mm (in landing gear)"] = n.get("gear cross tubes", 0) - o.get("gear cross tubes", 0)
    de = J("details.json")
    if de:
        reg = de.get("skin_support_region", {})
        if reg.get("x_c_from") is not None:
            g = json.loads((ROOT / "design" / "geometry.json").read_text())
            w = g["wing"]
            area = (reg["x_c_to"] - reg["x_c_from"]) * w["root_chord"] * 2 * reg["y_to_m"]
            d[f"H45 15 mm under the upper skin, x/c {reg['x_c_from']:.2f}-{reg['x_c_to']:.2f}, |y| <= {reg['y_to_m']:.2f} m (replaces XPS)"] = \
                area * 0.015 * (48 - 33)
    d["pivot hardware for the gear legs (4 bushed pivots, estimate; required change)"] = 2.0
    parts = J("parts.json")
    fit = {k: v.get("mass_kg", 0) * COUNT.get(k, 1) for k, v in parts.items()}
    if cadp:
        cp = {it["id"]: it for it in json.loads((ROOT / "cad" / "parts.json").read_text())["parts"]}
        fit = {f"{k} (CAD)": v["mass_kg"] * len(cp[k]["instances"]) for k, v in cadp.items()}
    total = sum(d.values())
    mass = dict(deltas_kg=d, total_delta_kg=total, new_mtow_estimate_kg=sel["mass_kg"]["mtow"] + total,
                fittings_kg=dict(per_type=fit, total=sum(fit.values()),
                                 note="machined fittings (CAD STEP parts when available, else fea/parts.py); already in the CAD-calibrated breakdown (not added)"),
                cabin_primary_kg=fu.get("mass_estimate_kg", {}), selected_design_breakdown=bd,
                note="deltas of the members sized by WP F against the sections of design/geometry.json; fuselage shell, tail surfaces "
                     "and systems are unchanged")
    out = dict(_about="All margins of safety (MS = allowable / (ultimate demand x special factor) - 1), lowest first. Generated by fea/margins.py.",
               margins=rows, mass=mass)
    (R / "margins.json").write_text(json.dumps(out, indent=1, default=float))
    for r in rows:
        print(f"{r['MS']:+8.2f}  {r['item'][:70]:70s} {r['mode'][:28]:28s} {r['case'][:40]}")
    print(json.dumps(mass["deltas_kg"], indent=1), "total", round(total, 1))


if __name__ == "__main__":
    main()
