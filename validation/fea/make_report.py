"""Convergence plots and the summary table of validation/fea/README.md from results/*.json.

    ~/tools/cadenv/bin/python validation/fea/make_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "results"
IMG = HERE / "img"


def J(name):
    return json.loads((R / name).read_text())


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    IMG.mkdir(exist_ok=True)
    fig, axs = plt.subplots(2, 3, figsize=(11, 6.4), dpi=120)
    ax = axs[0, 0]
    c1 = J("ccx_C1.json")
    ax.semilogx([r["elems"] for r in c1["mesh"]], [r["err_pct"] for r in c1["mesh"]], "o-", label="CPS8 mapped")
    ax.semilogx([r["elems"] for r in c1["mesh_gmsh"]], [r["err_pct"] for r in c1["mesh_gmsh"]], "s-", label="CPS6 gmsh")
    ax.set_title("C1 NAFEMS LE1: sigma_yy at D", fontsize=9)
    ax = axs[0, 1]
    c2 = J("ccx_C2.json")
    for et in ("C3D20R", "C3D20"):
        rows = [r for r in c2["mesh"] if r["element"] == et]
        ax.semilogx([r["elems"] for r in rows], [r["err_pct"] for r in rows], "o-", label=et)
    ax.set_title("C2 NAFEMS LE10: sigma_yy at D", fontsize=9)
    ax = axs[0, 2]
    c3 = J("ccx_C3.json")
    for bc, mk in (("hard SS faces", "o-"), ("uz=0 bottom-face edges", "s--"), ("uz=0 mid-plane edges", "^--")):
        rows = [r for r in c3["mesh"] if r["bc"] == bc]
        ax.semilogx([r["elems"] for r in rows], [r["err_vs_nafems_pct"][0] for r in rows], mk, label=f"mode 4, {bc}")
    rows = [r for r in c3["mesh"] if r["bc"] == "hard SS faces"]
    ax.semilogx([r["elems"] for r in rows], [r["err_vs_nafems_pct"][3] for r in rows], "o:", label="mode 7 (2,2), hard SS")
    ax.set_title("C3 NAFEMS FV52 frequencies", fontsize=9)
    ax = axs[1, 0]
    c5 = J("ccx_C5.json")
    for k, lab in (("C5a SS square plate, uniaxial compression", "isotropic plate"), ("C5b SS cross-ply [0/90]s plate", "cross-ply plate"),
                   ("C5c thin cylinder, axial compression", "cylinder")):
        rows = c5[k]["mesh"]
        n = [np.prod([int(v) for v in r["mesh"].split("x")]) for r in rows]
        ax.semilogx(n, [r["err_pct"] for r in rows], "o-", label=lab)
    ax.set_title("C5 linear buckling (S8R)", fontsize=9)
    ax = axs[1, 1]
    c6 = J("ccx_C6.json")
    for model, mk in (("CPS8 layered", "o-"), ("C3D20R layered solid strip", "s-")):
        rows = [r for r in c6["mesh"] if r["model"] == model]
        ax.plot(range(len(rows)), [r["err_pct"] for r in rows], mk, label=model)
    rows = [r for r in c6["mesh"] if r["model"].startswith("S8R")]
    ax.plot(range(len(rows)), [r["err_pct"] for r in rows], "^:", label="S8R composite shell")
    ax.set_xlabel("refinement level")
    ax.set_title("C6 sandwich beam deflection", fontsize=9)
    ax = axs[1, 2]
    c8 = J("ccx_C8.json")
    ax.semilogx([r["elems"] for r in c8["mesh"]], [r["err_tip_pct"] for r in c8["mesh"]], "o-", label="tip deflection")
    ax.semilogx([r["elems"] for r in c8["mesh"]], [r["err_sigma_pct"] for r in c8["mesh"]], "s-", label="mid-span stress")
    c4 = J("ccx_C4.json")
    ax.set_title("C8 gmsh C3D10 cantilever", fontsize=9)
    for a in axs.ravel():
        a.axhline(0, color="0.5", lw=0.6)
        a.grid(alpha=0.3, which="both")
        a.legend(frameon=False, fontsize=7)
        if not a.get_xlabel():
            a.set_xlabel("elements")
        a.set_ylabel("error vs reference (%)")
    axs[1, 1].set_ylim(-75, 5)
    fig.tight_layout()
    fig.savefig(IMG / "ccx_convergence.png")
    plt.close(fig)

    # summary (finest mesh)
    lines = []
    b = J("beam.json")
    lines.append(("B1a cantilever tip load", b["B1a tip load EB"]["mesh"][-1]["err_tip_pct"]))
    lines.append(("B1c Timoshenko tip", b["B1c tip load Timoshenko"]["mesh"][-1]["err_tip_pct"]))
    lines.append(("B2 tapered tip (64 el)", b["B2 tapered cantilever"]["mesh"][-1]["err_tip_pct"]))
    lines.append(("C1 LE1 CPS8 finest", c1["mesh"][-1]["err_pct"]))
    lines.append(("C1 LE1 CPS6 finest", c1["mesh_gmsh"][-1]["err_pct"]))
    lines.append(("C2 LE10 C3D20R finest", [r for r in c2["mesh"] if r["element"] == "C3D20R"][-1]["err_pct"]))
    lines.append(("C2 LE10 C3D20 finest", [r for r in c2["mesh"] if r["element"] == "C3D20"][-1]["err_pct"]))
    hs = [r for r in c3["mesh"] if r["bc"] == "hard SS faces"][-1]
    lines.append(("C3 FV52 hard SS max |err|", max(abs(x) for x in hs["err_vs_nafems_pct"])))
    lines.append(("C4a ply stress max err", c4["C4a quasi-isotropic [0/45/-45/90]s, Nx = 100 N/mm"]["mesh"][-1]["max_ply_stress_err_pct"]))
    lines.append(("C4b curvature", c4["C4b unsymmetric [0/90]T, Nx = 100 N/mm (B-matrix coupling)"]["mesh"][-1]["err_kx_pct"]))
    for k in ("C5a SS square plate, uniaxial compression", "C5b SS cross-ply [0/90]s plate", "C5c thin cylinder, axial compression"):
        lines.append((k[:30], c5[k]["mesh"][-1]["err_pct"]))
    lines.append(("C6 CPS8 sandwich", [r for r in c6["mesh"] if r["model"] == "CPS8 layered"][-1]["err_pct"]))
    lines.append(("C6 S8R composite sandwich", [r for r in c6["mesh"] if r["model"].startswith("S8R")][-1]["err_pct"]))
    c7 = J("ccx_C7.json")
    lines.append(("C7 box twist rate", c7["mesh"][-1]["err_twist_rate_pct"]))
    lines.append(("C8 C3D10 tip", c8["mesh"][-1]["err_tip_pct"]))
    for k, v in lines:
        print(f"{k:34s} {v:+.3f} %")


if __name__ == "__main__":
    main()
