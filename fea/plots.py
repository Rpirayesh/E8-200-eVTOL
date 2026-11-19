"""Global-model figures: member utilisation (max demand/allowable over all cases) and the first elastic mode shapes.

    ~/tools/cadenv/bin/python fea/plots.py      -> docs/models/fea/airframe_utilisation.png, airframe_modes.png, airframe_utilisation.glb
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea import sizing as SZ  # noqa: E402
from fea.geometry import ROOT, load  # noqa: E402

OUT = ROOT / "docs" / "models" / "fea"


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    g = load(ROOT / "design" / "geometry.json", sizing=ROOT / "fea" / "results" / "sizing_update.json")
    env, m, ac, allc = SZ.demand(g)
    f = m["f"]
    cmap = plt.get_cmap("turbo")
    fig = plt.figure(figsize=(10, 6.5), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    segs = []
    for (a, b, sec, vref, tag) in f.elems:
        p, q = f.nodes[a], f.nodes[b]
        r = max(env.get((a, b), {}).get("ratios", {}).values(), default=None)
        if r is None:
            ax.plot(*zip(p, q), color="0.75", lw=0.6)
        else:
            ax.plot(*zip(p, q), color=cmap(min(r, 1.0)), lw=2.2)
            segs.append((p, q, r))
    ax.set_box_aspect(np.ptp(np.array(f.nodes), axis=0))
    ax.view_init(28, -125)
    ax.set_axis_off()
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    fig.colorbar(sm, ax=ax, shrink=0.6, label="utilisation = 1 / (1 + MS), envelope of all cases (ultimate)")
    ax.set_title("E8-200 global beam model, sized sections: member utilisation (grey: stiff links)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "airframe_utilisation.png")
    plt.close(fig)
    # GLB: members as thin cylinders coloured by utilisation
    import trimesh
    meshes = []
    for p, q, r in segs:
        v = q - p
        L = np.linalg.norm(v)
        cyl = trimesh.creation.cylinder(radius=0.02, height=L, sections=8)
        z = np.array([0, 0, 1.0])
        ax_ = np.cross(z, v / L)
        ang = np.arccos(np.clip(z @ (v / L), -1, 1))
        T = trimesh.transformations.rotation_matrix(ang, ax_ if np.linalg.norm(ax_) > 1e-9 else [1, 0, 0])
        T[:3, 3] = (p + q) / 2
        cyl.apply_transform(T)
        cyl.visual.vertex_colors = (np.array(cmap(min(r, 1.0))) * 255).astype(np.uint8)
        meshes.append(cyl)
    scene = trimesh.util.concatenate(meshes)
    # glTF is y-up: rotate z-up model
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    scene.export(OUT / "airframe_utilisation.glb")
    # mode shapes
    fr, V = f.modes(14)
    keep = [k for k in range(len(fr)) if fr[k] > 0.5][:6]
    fig = plt.figure(figsize=(12, 7), dpi=110)
    P = np.array(f.nodes)
    for j, k in enumerate(keep):
        axm = fig.add_subplot(2, 3, j + 1, projection="3d")
        d = V[:, k].reshape(-1, 6)[:, :3]
        s = 0.6 / (np.abs(d).max() + 1e-12)
        for (a, b, sec, vref, tag) in f.elems:
            axm.plot(*zip(P[a], P[b]), color="0.85", lw=0.5)
            axm.plot(*zip(P[a] + s * d[a], P[b] + s * d[b]), color="#1f5fa8", lw=1.0)
        axm.set_box_aspect(np.ptp(P, axis=0))
        axm.view_init(28, -125)
        axm.set_axis_off()
        axm.set_title(f"mode {j + 1}: {fr[k]:.1f} Hz", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "airframe_modes.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
