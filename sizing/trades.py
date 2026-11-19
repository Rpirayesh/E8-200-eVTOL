"""Trade studies, Pareto fronts and sensitivities for the E8-200 (work package D).

Every point is a full re-optimisation (sizing.optimise) with the traded variable fixed, so the curves show the best
design the rest of the space allows.  Results: sizing/results/trades.json; plots: sizing/plots/*.png.

    ~/tools/cadenv/bin/python -m sizing.trades [--quick]
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from . import data as D
from .airfoils import load as load_airfoils
from .model import evaluate
from .optimise import optimise
from .run import BASELINE_CFG, RESULTS, jsonable

PLOTS = D.ROOT / "sizing" / "plots"
KEYS = ["mtow", "empty", "battery_kg", "E_nom", "cells", "Ns", "Np_pack", "P_hover_site", "P_oei", "Q_oei", "LD", "P_cruise",
        "range_km", "cost_total", "objective", "length", "f_dl", "C_hover", "disk_loading", "n_types", "n_lru"]


def _job(args):
    tag, cfg, fixed, seeds = args
    x, f = optimise(cfg, fixed=fixed, seeds=seeds)
    o = evaluate({k: np.atleast_1d(v) for k, v in x.items()}, cfg)
    row = dict(tag=tag, cfg=cfg, fixed=fixed, x={k: float(v) for k, v in x.items()}, penalised=float(f),
               feasible=bool(o["feasible"][0]))
    row.update({k: float(np.asarray(o[k]).ravel()[0]) for k in KEYS})
    row["violated"] = {k: round(float(v[0]), 4) for k, v in o["g"].items() if v[0] > 1e-9}
    row["cost"] = {k: float(np.asarray(v).ravel()[0]) for k, v in o["cost"].items()}
    row["mass"] = {k: float(np.asarray(v).ravel()[0]) for k, v in o["mass"].items()}
    return row


def base_cfg():
    """Iteration 2: trades at the selected (closing) range with the selected design's OML corrections."""
    sel = json.loads((RESULTS / "selected.json").read_text())
    return dict(sel["cfg"])


def jobs(quick=False):
    base = base_cfg()
    seeds = (1,) if quick else (1, 2)
    J = []
    for name, c in (("8 rotors", dict(n_rot=8)), ("6 rotors", dict(n_rot=6)), ("4 coaxial pairs", dict(n_rot=8, coax=True)),
                    ("4 rotors", dict(n_rot=4))):
        J.append((("config", name), dict(base, **c), {}, seeds))
    for i, m in enumerate(D.LIFT_MOTORS):
        J.append((("lift_motor", m["id"]), base, dict(lm=i), seeds))
    for d in np.round(np.arange(1.50, 2.01, 0.05), 2):
        J.append((("diameter", float(d)), base, dict(D=float(d)), seeds))
    for vt in (150.0, 160.0, 170.0, 175.0, 180.0, 185.0, 190.0):
        J.append((("tip_speed", vt), base, dict(vtip=vt), seeds))
    for sp in (7.0, 7.5, 8.0, 8.5, 9.0):
        J.append((("span", sp), base, dict(span=sp), seeds))
    for v in (150, 160, 170, 180, 190, 200):
        J.append((("speed_kmh", v), base, dict(V=v / 3.6), seeds))
    for k in (2, 3, 4):
        J.append((("packs", k), base, dict(npk=k), seeds))
    for i, c in enumerate(D.CELLS):
        J.append((("cell", c["id"]), base, dict(cell=i), seeds))
    for i, a in enumerate(load_airfoils()):
        J.append((("airfoil", a), base, dict(airfoil=i), seeds))
    for i, m in enumerate(D.PUSHER_MOTORS):
        J.append((("pusher_motor", m["id"]), base, dict(pm=i), seeds))
    for k in (0, 1):
        J.append((("flap", k), base, dict(flap=k), seeds))
    for k in (2, 3):
        J.append((("blades", k), base, dict(nb=k), seeds))
    J.append((("seating", "side-by-side"), dict(base, seating="side"), {}, seeds))
    J.append((("seating", "tandem"), base, {}, seeds))
    asm = dict(base.get("assumptions", {}))
    for r in (10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 100):
        J.append((("range", r), dict(base, range_km=float(r)), {}, seeds))
        J.append((("range_minmass", r), dict(base, range_km=float(r), objective="mtow"), {}, seeds))
        J.append((("range_flare1.0g", r), dict(base, range_km=float(r), assumptions=dict(asm, oei_flare_g=1.0)), {}, seeds))
    for gf in (1.0, 1.1, 1.15, 1.2, 1.25):
        J.append((("flare_g", gf), dict(base, assumptions=dict(asm, oei_flare_g=gf)), {}, seeds))
    return J


def max_feasible_range(lo=10.0, hi=50.0, tol=0.5, label="iteration-2 requirements", asm=None):
    """Largest design range with a feasible optimum (bisection on full re-optimisations)."""
    base = base_cfg()
    best = None
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        r = _job((("range", mid), dict(base, range_km=mid, assumptions=dict(base.get("assumptions", {}), **(asm or {}))), {}, (1, 2)))
        if r["feasible"]:
            lo, best = mid, r
        else:
            hi = mid
    return dict(label=label, max_range_km=lo, first_infeasible_km=hi, design=best)


def assumption_sensitivity(x_sel):
    """Fixed selected geometry and parts; only the battery (integer layout) and the mass closure respond."""
    cfg = base_cfg()
    X = {k: np.atleast_1d(v) for k, v in x_sel.items()}
    ref = evaluate(X, cfg)
    rows = []
    cases = [("pack overhead 0.25 / 0.35", "f_ovh", 0.25, 0.35), ("induced factor kappa 1.15 / 1.25", "kappa", 1.15, 1.25),
             ("blade cd0 0.012 / 0.018", "cd0_blade", 0.012, 0.018), ("download base 0.01 / 0.04", "f_dl0", 0.01, 0.04),
             ("growth 0 / 10 %", "growth", 0.0, 0.10), ("structure factor 0.75 / 1.0", "tf_struct", 0.75, 1.0),
             ("excrescence 1.05 / 1.20", "k_exc", 1.05, 1.20), ("battery eta cap 0.97 / 0.93", "eta_b_cap", 0.97, 0.93),
             ("motor bell CD 0.2 / 0.8 (bare)", "cd_motor_bell", 0.2, 0.8)]
    for label, key, lo, hi in cases:
        r = dict(label=label, key=key)
        for tag, v in (("low", lo), ("high", hi)):
            o = evaluate(X, dict(cfg, assumptions=dict(cfg.get("assumptions", {}), **{key: v})))
            r[tag] = dict(value=v, mtow=float(o["mtow"][0]), cost=float(o["cost_total"][0]), E_nom=float(o["E_nom"][0]),
                          feasible=bool(o["feasible"][0]), violated=[k for k, g in o["g"].items() if g[0] > 1e-9])
        rows.append(r)
    return dict(reference=dict(mtow=float(ref["mtow"][0]), cost=float(ref["cost_total"][0]), E_nom=float(ref["E_nom"][0])), rows=rows)


# ------------------------------------------------------------------------------------------------ plots
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _ax_style(ax):
    ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)


def plots(T, sel):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    PLOTS.mkdir(parents=True, exist_ok=True)

    def series(kind):
        rows = sorted([r for r in T if r["tag"][0] == kind], key=lambda r: r["tag"][1])
        return rows

    # ---- Pareto / range
    rr, rm, r10 = series("range"), series("range_minmass"), series("range_flare1.0g")
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), dpi=150, facecolor=SURF)
    for ax, key, lab, scale in ((axs[0], "cost_total", "Acquisition cost per aircraft (kUSD)", 1e-3), (axs[1], "mtow", "MTOW (kg)", 1.0)):
        _ax_style(ax)
        for rows, col, name, mk in ((rr, C1, "min. cost + complexity (1.2 g OEI flare)", "o"), (rm, C2, "min. MTOW (1.2 g OEI flare)", "s"),
                                    (r10, C3, "min. cost, OEI 1.0 g + 10 % only", "^")):
            f = [r for r in rows if r["feasible"]]
            ax.plot([r["tag"][1] for r in f], [r[key] * scale for r in f], color=col, lw=2, marker=mk, ms=6, mec=SURF, mew=1.5, label=name)
            nf = [r for r in rows if not r["feasible"] and r["tag"][1] <= 60]
            ax.plot([r["tag"][1] for r in nf], [r[key] * scale for r in nf], ls="none", marker="x", color=col, ms=6)
        ax.axvline(50, color=INK2, lw=1, ls=":")
        ax.axvline(sel["requirements"]["range_km"], color=INK, lw=1, ls="--")
        ax.set_xlabel("Design range (km), 150 km/h, 20 % reserve at EOL")
        ax.set_ylabel(lab)
        ax.set_xlim(5, 62)
    axs[1].text(50.5, axs[1].get_ylim()[0] + 0.05 * np.ptp(axs[1].get_ylim()), "requirement 50 km", fontsize=7, color=INK2)
    axs[1].text(sel["requirements"]["range_km"] + 0.5, axs[1].get_ylim()[1] - 0.08 * np.ptp(axs[1].get_ylim()), "selected (iteration 3)",
                fontsize=7, color=INK)
    axs[0].legend(frameon=False, fontsize=7)
    axs[0].set_title("Cost vs range (x = best design violates a constraint)", fontsize=10, color=INK, loc="left")
    axs[1].set_title("MTOW vs range", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(PLOTS / "pareto_range.png", facecolor=SURF)
    plt.close(fig)

    # ---- continuous trades
    for kind, xlab, fname in (("diameter", "Lift rotor diameter (m)", "trade_diameter.png"), ("span", "Wing span (m)", "trade_span.png"),
                              ("speed_kmh", "Cruise speed (km/h)", "trade_speed.png"), ("tip_speed", "Lift-rotor hover tip speed (m/s)", "trade_tip_speed.png"),
                              ("flare_g", "One-motor-out flare load factor (g)", "trade_flare_g.png")):
        rows = series(kind)
        fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), dpi=150, facecolor=SURF)
        for ax, key, lab, scale in ((axs[0], "objective", "Cost + complexity penalty (kUSD)", 1e-3), (axs[1], "mtow", "MTOW (kg)", 1.0)):
            _ax_style(ax)
            f = [r for r in rows if r["feasible"]]
            nf = [r for r in rows if not r["feasible"]]
            ax.plot([r["tag"][1] for r in f], [r[key] * scale for r in f], color=C1, lw=2, marker="o", ms=6, mec=SURF, mew=1.5,
                    label="feasible optimum")
            if nf:
                ax.plot([r["tag"][1] for r in nf], [r[key] * scale for r in nf], ls="none", marker="x", color=C2, ms=7,
                        label="best design violates a constraint")
            xs = {"diameter": sel["x"]["D"], "span": sel["x"]["span"], "speed_kmh": sel["x"]["V"] * 3.6, "tip_speed": sel["x"]["vtip"],
                  "flare_g": 1.2}[kind]
            ax.axvline(xs, color=INK2, lw=1, ls=":")
            ax.set_xlabel(xlab)
            ax.set_ylabel(lab)
        axs[0].legend(frameon=False, fontsize=8)
        axs[0].set_title(f"{xlab.split(' (')[0]} trade (dotted: selected)", fontsize=10, color=INK, loc="left")
        fig.tight_layout()
        fig.savefig(PLOTS / fname, facecolor=SURF)
        plt.close(fig)

    # ---- discrete trades: one horizontal bar chart per variable
    groups = [("config", "Rotor configuration"), ("lift_motor", "Lift motor"), ("packs", "Battery packs"), ("cell", "Cell"),
              ("airfoil", "Wing airfoil"), ("pusher_motor", "Pusher motor"), ("seating", "Cabin"), ("blades", "Lift-rotor blades"),
              ("flap", "Flaps")]
    fig, axs = plt.subplots(3, 3, figsize=(12, 9), dpi=150, facecolor=SURF)
    for ax, (kind, title) in zip(axs.ravel(), groups):
        _ax_style(ax)
        rows = [r for r in T if r["tag"][0] == kind]
        labels = [str(r["tag"][1]).replace("MOT-", "").replace("CELL-", "") for r in rows]
        if kind == "flap":
            labels = ["none" if r["tag"][1] == 0 else "plain flap" for r in rows]
        vals = [r["objective"] / 1e3 for r in rows]
        y = np.arange(len(rows))
        cols = [C1 if r["feasible"] else "#d9d7d0" for r in rows]
        ax.barh(y, vals, color=cols, height=0.6)
        for yi, r, v in zip(y, rows, vals):
            txt = f"{v:.0f} k, {r['mtow']:.0f} kg" if r["feasible"] else \
                "infeasible: " + ", ".join(sorted(r["violated"], key=lambda k: -r["violated"][k])[:2])
            ax.text(min(v, 560) * 0.02 + 5, yi, txt, va="center", fontsize=7, color=INK if r["feasible"] else INK2)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlim(0, 600)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("cost + complexity (kUSD)", fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "trade_discrete.png", facecolor=SURF)
    plt.close(fig)

    # ---- mass and cost breakdown of the selected design
    m = sel["mass_kg"]["breakdown"]
    c = sel["cost"]["breakdown_usd"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), dpi=150, facecolor=SURF)
    for ax, dd, lab, unit in ((axs[0], dict(m, battery=sel["mass_kg"]["battery"], payload=sel["mass_kg"]["payload"]), "Mass (kg)", "kg"),
                              (axs[1], {k: v / 1e3 for k, v in c.items()}, "Cost (kUSD)", "k")):
        _ax_style(ax)
        items = sorted(dd.items(), key=lambda kv: kv[1])
        y = np.arange(len(items))
        ax.barh(y, [v for _, v in items], color=C1, height=0.6)
        for yi, (_, v) in zip(y, items):
            ax.text(v, yi, f" {v:.0f}", va="center", fontsize=7, color=INK2)
        ax.set_yticks(y)
        ax.set_yticklabels([k.replace("_", " ") for k, _ in items], fontsize=7)
        ax.set_xlabel(lab)
    axs[0].set_title(f"Mass breakdown, MTOW {sel['mass_kg']['mtow']:.0f} kg", fontsize=10, color=INK, loc="left")
    axs[1].set_title(f"Acquisition cost, {sel['results']['cost_usd'] / 1e3:.0f} kUSD per aircraft (N = 10)", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(PLOTS / "selected_breakdown.png", facecolor=SURF)
    plt.close(fig)


def plan_view(geo, path):
    """Top and side view of the selected design from design/geometry.json (quick-look drawing)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, axs = plt.subplots(2, 1, figsize=(10, 9), dpi=150, facecolor=SURF, gridspec_kw=dict(height_ratios=[1.6, 1]))
    ax = axs[0]
    _ax_style(ax)
    w = geo["wing"]
    ax.add_patch(Rectangle((w["x_le_root"], -w["span"] / 2), w["root_chord"], w["span"], fc="#d6e4f5", ec=C1, lw=1))
    for b in geo["booms"]:
        ax.plot([b["x_front"], b["x_aft"]], [b["y"], b["y"]], color=INK2, lw=3)
    for r in geo["lift_rotors"]:
        ax.add_patch(Circle((r["hub"][0], r["hub"][1]), r["diameter"] / 2, fc="none", ec=C2 if r["spin"] > 0 else C3, lw=1.2))
        ax.text(r["hub"][0], r["hub"][1], "ccw" if r["spin"] > 0 else "cw", ha="center", va="center", fontsize=6, color=INK2)
    st = geo["fuselage"]["stations"]
    xs = [s_["x"] for s_ in st]
    ax.fill_between(xs, [-s_["width"] / 2 for s_ in st], [s_["width"] / 2 for s_ in st], color="#cfcdc6")
    t = geo["tail"]["horizontal"][0]
    ax.add_patch(Rectangle((t["x_le_root"], -t["span"] / 2), t["root_chord"], t["span"], fc="#d6e4f5", ec=C1, lw=1))
    p = geo["pusher"]
    ax.plot([p["x"], p["x"]], [-p["diameter"] / 2, p["diameter"] / 2], color=C4, lw=2)
    for sname in geo["seats"]:
        ax.plot(sname["x"], sname["y"], marker="o", color=INK, ms=5)
    for bp in geo["battery_packs"]:
        ax.add_patch(Rectangle((bp["x"] - bp["length"] / 2, -bp["width"] / 2), bp["length"], bp["width"], fc="none", ec=C4, lw=1, ls="--"))
    cg = geo["cg_mtow_m"]
    ax.plot(cg[0], 0, marker="P", color=INK, ms=9)
    ax.plot(geo["neutral_point_x_m"], 0, marker="x", color=INK, ms=8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m) aft of the nose")
    ax.set_ylabel("y (m)")
    ax.set_title("E8-200 selected design, top view (+ CG at MTOW, x neutral point; rotor colour = spin)", fontsize=10, color=INK, loc="left")
    ax = axs[1]
    _ax_style(ax)
    ax.fill_between(xs, [s_["z_center"] - s_["height"] / 2 for s_ in st], [s_["z_center"] + s_["height"] / 2 for s_ in st], color="#cfcdc6")
    ax.add_patch(Rectangle((w["x_le_root"], w["z_root"] - 0.45 * w["t_c"] * w["root_chord"]), w["root_chord"], w["t_c"] * w["root_chord"],
                           fc="#d6e4f5", ec=C1))
    b = geo["booms"][1]
    ax.plot([b["x_front"], b["x_aft"]], [b["z"], b["z"]], color=INK2, lw=3)
    for r in geo["lift_rotors"]:
        if r["hub"][1] > 0:
            ax.plot([r["hub"][0] - r["diameter"] / 2, r["hub"][0] + r["diameter"] / 2], [r["hub"][2]] * 2, color=C2, lw=1.5)
            ax.plot([r["hub"][0]] * 2, [b["z"], r["hub"][2]], color=INK2, lw=1.5)
    ax.plot([p["x"]] * 2, [p["z"] - p["diameter"] / 2, p["z"] + p["diameter"] / 2], color=C4, lw=2)
    v = geo["tail"]["vertical"][1]
    ax.add_patch(Rectangle((v["x_le_root"], v["z_root"]), v["root_chord"], v["height"], fc="#d6e4f5", ec=C1))
    sk = geo["landing_gear_oml"]["skids"][0]
    ax.plot([sk["x_start"], sk["x_end"]], [sk["z"]] * 2, color=INK2, lw=2)
    for s2 in geo["landing_gear_oml"]["struts"]:
        ax.plot([s2["p1"][0], s2["p2"][0]], [s2["p1"][2], s2["p2"][2]], color=INK2, lw=2)
    for sname in geo["seats"]:
        ax.plot(sname["x"], sname["z"], marker="o", color=INK, ms=5)
    ax.plot(cg[0], cg[2], marker="P", color=INK, ms=9)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("z (m)")
    ax.set_title("Side view (starboard rotors)", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF)
    plt.close(fig)


def main(quick=False, workers=10, plots_only=False):
    sel = json.loads((RESULTS / "selected.json").read_text())
    if plots_only:
        out = json.loads((RESULTS / "trades.json").read_text())
        T = out["trades"]
        for r in T:
            r["tag"] = tuple(r["tag"])
        sel_design = json.loads((D.ROOT / "design" / "selected_design.json").read_text())
        plots(T, dict(sel_design, x=sel["x"]))
        plan_view(json.loads((D.ROOT / "design" / "geometry.json").read_text()), PLOTS / "selected_layout.png")
        return out
    J = jobs(quick)
    with ProcessPoolExecutor(workers) as ex:
        T = list(ex.map(_job, J))
    sens = assumption_sensitivity(sel["x"])
    mr = max_feasible_range()
    mr10 = max_feasible_range(label="flare 1.0 g (iteration-1 rotor-out rule only)", asm=dict(oei_flare_g=1.0))
    sel_design = json.loads((D.ROOT / "design" / "selected_design.json").read_text())
    out = dict(trades=T, assumption_sensitivity=sens, max_range=mr, max_range_flare1p0=mr10)
    (RESULTS / "trades.json").write_text(json.dumps(jsonable(out), indent=1))
    plots(T, dict(sel_design, x=sel["x"]))
    plan_view(json.loads((D.ROOT / "design" / "geometry.json").read_text()), PLOTS / "selected_layout.png")
    for r in T:
        print(f"{str(r['tag']):45s} feas={r['feasible']!s:5s} obj={r['objective']:9.0f} cost={r['cost_total']:9.0f} mtow={r['mtow']:7.1f} "
              f"E={r['E_nom']:5.1f} D={r['x']['D']:.2f} lm={int(r['x']['lm'])} V={r['x']['V'] * 3.6:.0f} span={r['x']['span']:.1f} "
              f"viol={r['violated']}")
    return out


if __name__ == "__main__":
    main(quick="--quick" in sys.argv, plots_only="--plots" in sys.argv)
