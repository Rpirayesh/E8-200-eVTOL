"""Strength sizing of the primary structure on the global beam model (fea/airframe.py) -> fea/results/sizing_update.json.

    ~/tools/cadenv/bin/python fea/sizing.py [--iters 10]

Variables (all others as in design/geometry.json):
  wing spars   cap thickness and web thickness at spanwise stations (eta = |y| / semi-span); cap width and depth kept
  wing skin    torsion-box skin thickness (+-45 carbon)
  booms        three segments (front overhang / between the inner rotors / rear overhang): COTS 4 in ID roll-wrapped tube
               (1.6 mm) + wet-laid UD over-wrap (sized) + +-45 over-wrap (torsion / stiffness, sized by the modal target)
  tail spar    tube wall
  rotor pylon  6061-T6 tube wall (od fixed)
  gear         cross-tube wall (strength from the 3 g cases; energy check in fea/gear.py)
Rule: each thickness is scaled by r (1 + MS_target), r = max over all cases of the demand/allowable ratio of the elements
it controls (fixed-point iteration with full re-analysis, min gauges from fea/design_inputs.json).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import airframe as AF  # noqa: E402
from fea import loads as LD  # noqa: E402
from fea.geometry import ROOT, load, section, spar_spec  # noqa: E402

HERE = Path(__file__).resolve().parent
DI = json.loads((HERE / "design_inputs.json").read_text())
MIN = DI["min_gauge"]
TGT_C, TGT_M = DI["ms_target"]["composite"], DI["ms_target"]["metal"]
ETAS = [0.0, 0.0977, 0.2, 0.33, 0.5, 0.7, 0.85, 1.0]
BOOM_ID = 0.1016
COTS_T = 0.0016
PYLON_OD = 0.10


def initial_update(g):
    upd = {"_about": "WP F sized sections (fea/sizing.py); geometry.json section format, merged by fea/geometry.load(sizing=...)"}
    spars = []
    s_ = g["wing"]["span"] / 2
    etas = sorted({0.0, round(g["wing"]["root_fittings_y"] / s_, 4), 0.2, round(abs(g["booms"][0]["y"]) / s_, 4), 0.55, 0.7, 0.85, 1.0})
    for sp in g["wing"]["spars"]:
        st = [dict(eta=e, section=spar_spec(sp, e)) for e in etas]
        spars.append(dict(name=sp["name"], stations=st))
    upd["wing"] = dict(spars=spars, torsion_box=dict(skin_t=g["wing"]["torsion_box"]["skin_t"]))
    booms = []
    for b in g["booms"]:
        xr = sorted(r["x"] for r in g["rotors"] if r["boom"] == b["name"])
        cuts = [b["x_front"], xr[1], xr[2], b["x_aft"]]
        segs = []
        for k in range(3):
            t_ud = 0.0024 if k == 1 else 0.0008
            segs.append(dict(x_from=cuts[k], x_to=cuts[k + 1], section=boom_spec(t_ud, 0.0005)))
        booms.append(dict(name=b["name"], segments=segs))
    upd["booms"] = booms
    upd["tail"] = dict(spar_section=dict(g["tail"]["spar_section"]))
    upd["rotor_pylon_section"] = dict(g.get("rotor_pylon_section") or DI["rotor_pylon_section"])
    upd["landing_gear_oml"] = dict(cross_tube=dict(g["landing_gear_oml"]["cross_tube"]))
    return upd


def boom_spec(t_ud, t_45):
    layers = [dict(t=COTS_T, material="cf_tube_rollwrapped_twill")]
    if t_ud > 1e-5:
        layers.append(dict(t=round(t_ud, 5), material="cf_ud_wet"))
    if t_45 > 1e-5:
        layers.append(dict(t=round(t_45, 5), material="cf_fabric_wet_45"))
    return dict(type="tube_layers", id=BOOM_ID, layers=layers,
                construction="COTS 4 in ID roll-wrapped twill tube 1.6 mm + wet-laid UD over-wrap + +-45 over-wrap (outer)")


def boom_t(spec, mat):
    return sum(L["t"] for L in spec["layers"] if L["material"] == mat)


def demand(g):
    """Run every case; return per-element max ratio by mode, the model and the case results."""
    ac = LD.aircraft_from_geometry(g)
    m = AF.build(g)
    f = m["f"]
    ac["x_cg"] = float(f.mass_properties()[1][0])
    allc = LD.all_cases(ac)
    cases = AF.build_cases(m, ac, allc)
    support = m["fus"][int(np.argmin(np.abs(m["fx"] - m["mass"]["cg"][0])))]
    env = {}
    for name, F in cases.items():
        u, _ = f.solve_inertia_relief(F, support, gravity=(0, 0, -AF.G0))
        for r in AF.member_check(f, u):
            e = env.setdefault(r["elem"], dict(tag=r["tag"], ratios={}, case={}))
            for k, v in r.get("ratios", {}).items():
                if v > e["ratios"].get(k, 0):
                    e["ratios"][k], e["case"][k] = v, name
    return env, m, ac, allc


def update(upd, env, m, g):
    f = m["f"]
    s = g["wing"]["span"] / 2
    changed = 0.0

    def mid(e):
        return 0.5 * (f.nodes[e[0]] + f.nodes[e[1]])
    # spars
    for sp in upd["wing"]["spars"]:
        tag = f"spar {sp['name']}"
        els = [(abs(mid(e)[1]) / s, v["ratios"]) for e, v in env.items() if v["tag"] == tag]
        etas = [st["eta"] for st in sp["stations"]]
        for j, st in enumerate(sp["stations"]):
            lo = 0.5 * (etas[j - 1] + etas[j]) if j > 0 else -1
            hi = 0.5 * (etas[j] + etas[j + 1]) if j < len(etas) - 1 else 2
            sel = [r for (eta, r) in els if lo <= eta <= hi]
            rc = max([max(r.get("tension", 0), r.get("compression", 0)) for r in sel] + [0.0])
            rw = max([r.get("web shear", 0) for r in sel] + [0.0])
            sec = st["section"]
            for key, rr, mn in (("t_cap", rc, MIN["t_cap"]), ("t_web", rw, MIN["t_web"])):
                if rr <= 0:
                    continue
                new = float(np.clip(sec[key] * (rr * (1 + TGT_C)) ** 0.85, 0.6 * sec[key], 1.8 * sec[key]))
                new = max(mn, round(new, 5))
                changed = max(changed, abs(new - sec[key]) / sec[key])
                sec[key] = new
    # skin
    rs = max([v["ratios"].get("shear", 0) for v in env.values() if v["tag"] == "wing skin box"] + [0.0])
    tb = upd["wing"]["torsion_box"]
    if rs > 0:
        new = max(MIN["skin_t"], round(float(np.clip(tb["skin_t"] * rs * (1 + TGT_C), 0.6 * tb["skin_t"], 1.8 * tb["skin_t"])), 5))
        changed = max(changed, abs(new - tb["skin_t"]) / tb["skin_t"])
        tb["skin_t"] = new
    # booms (left and right sized together, symmetric)
    nb = len(upd["booms"][0]["segments"])
    for k in range(nb):
        r = 0.0
        for b in upd["booms"]:
            sg = b["segments"][k]
            for e, v in env.items():
                if v["tag"] == b["name"] and sg["x_from"] - 1e-6 <= mid(e)[0] <= sg["x_to"] + 1e-6:
                    r = max(r, max(v["ratios"].values()))
        for b in upd["booms"]:
            sg = b["segments"][k]
            t_ud, t_45 = boom_t(sg["section"], "cf_ud_wet"), boom_t(sg["section"], "cf_fabric_wet_45")
            t_tot = COTS_T + t_ud + t_45
            req = float(np.clip(t_tot * r * (1 + TGT_C), 0.7 * t_tot, 1.6 * t_tot))
            new_ud = max(0.0, round(req - COTS_T - t_45, 5))
            new_ud = 0.0005 if 0 < new_ud < 0.0005 else new_ud     # at least two UD plies when an over-wrap is needed
            changed = max(changed, abs(new_ud - t_ud) / max(t_tot, 1e-3))
            sg["section"] = boom_spec(new_ud, t_45)
    # tail spar, pylon, gear cross tube: wall scaling
    for tag, holder, key, tgt, mn in (("tail spar", upd["tail"], "spar_section", TGT_C, 0.0010),
                                      ("rotor pylon", upd, "rotor_pylon_section", TGT_M, 0.0016),
                                      ("gear cross tube", upd["landing_gear_oml"], "cross_tube", TGT_M, 0.0020)):
        r = max([max(v["ratios"].values()) for v in env.values() if v["tag"] == tag] + [0.0])
        spec = holder[key]
        if r > 0:
            new = max(mn, round(float(np.clip(spec["t"] * r * (1 + tgt), 0.6 * spec["t"], 1.8 * spec["t"])), 5))
            new = min(new, spec["od"] * 0.25)
            changed = max(changed, abs(new - spec["t"]) / spec["t"])
            spec["t"] = new
    return changed


def section_masses(g):
    m = AF.build(g)
    mm = dict(m["member_mass"])
    tb = g["wing"]["torsion_box"]
    from fea.geometry import MAT
    width = (g["wing"]["spars"][-1]["x_c"] - g["wing"]["spars"][0]["x_c"]) * g["wing"]["root_chord"]
    mm["wing torsion skin (+-45, box upper+lower)"] = 2 * width * g["wing"]["span"] * tb["skin_t"] * MAT[tb["skin_material"]]["rho"]
    return mm


def min_ms(env):
    out = {}
    for v in env.values():
        if not v["ratios"]:
            continue
        k, r = max(v["ratios"].items(), key=lambda kv: kv[1])
        if r > out.get(v["tag"], (0, "", ""))[0]:
            out[v["tag"]] = (r, k, v["case"][k])
    return {t: dict(MS=1 / r - 1, mode=k, case=c) for t, (r, k, c) in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=10)
    a = ap.parse_args()
    g0 = load(ROOT / "design" / "geometry.json")
    upd = initial_update(g0)
    hist = []
    for it in range(a.iters):
        g = load(ROOT / "design" / "geometry.json", sizing=copy.deepcopy(upd))
        env, m, ac, allc = demand(g)
        ms = min_ms(env)
        hist.append({k: round(v["MS"], 3) for k, v in ms.items()})
        print(it, {k: round(v["MS"], 2) for k, v in sorted(ms.items(), key=lambda kv: kv[1]["MS"])})
        ch = update(upd, env, m, g)
        if ch < 0.01 and it > 2:
            break
    g = load(ROOT / "design" / "geometry.json", sizing=copy.deepcopy(upd))
    env, m, ac, allc = demand(g)
    ms = min_ms(env)
    m_old, m_new = section_masses(g0), section_masses(g)
    upd["_member_masses_kg"] = dict(original_geometry=m_old, sized=m_new)
    upd["_min_MS"] = ms
    upd["_history"] = hist
    (HERE / "results" / "sizing_update.json").write_text(json.dumps(upd, indent=1, default=float))
    print(json.dumps(ms, indent=1))
    for k in sorted(set(m_old) | set(m_new)):
        print(f"{k:45s} {m_old.get(k, 0):7.2f} -> {m_new.get(k, 0):7.2f} kg")


if __name__ == "__main__":
    main()
