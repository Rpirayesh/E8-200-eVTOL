"""Structured 2-D O-grid around an airfoil, written directly as an OpenFOAM polyMesh.

Normal-marching generator (adapted from the E8-S subscale tool chain): each grid line is
offset along the smoothed normals of the previous one, with geometric wall-normal
stretching from `ds_wall` to a circular far field of radius `R_far` chords.  The grid is
one cell thick in z (front/back = empty).

For grid-convergence studies the finest grid is generated once and the coarser levels are
obtained by removing every second grid line (`coarsen`), so the family is exactly nested
(refinement ratio 2), as in the NASA TMR grid families.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def resample_surface(pts: np.ndarray, n: int, te_cluster: float = 0.3, le_cluster: float = 1.0) -> np.ndarray:
    """Re-distribute a closed TE->upper->LE->lower->TE profile with n points (first point = TE),
    clustered at the leading and trailing edges (cosine in arc length per side)."""
    pts = np.asarray(pts, float)
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    i_le = int(np.argmin(pts[:, 0]))
    s_le, s_tot = s[i_le], s[-1]
    nh = n // 2
    t = (1 - np.cos(np.linspace(0, np.pi, nh + 1))) / 2
    t = (1 - te_cluster) * t + te_cluster * np.linspace(0, 1, nh + 1)
    su = s_le * t
    sl = s_le + (s_tot - s_le) * t
    snew = np.concatenate([su, sl[1:-1]])
    return np.column_stack([np.interp(snew, s, pts[:, 0]), np.interp(snew, s, pts[:, 1])])


def stretching(nj: int, ds_wall: float, length: float) -> np.ndarray:
    """Wall distances of nj grid lines, geometric growth from ds_wall to `length`."""
    lo, hi = 1.0000001, 1.6
    for _ in range(200):
        r = 0.5 * (lo + hi)
        L = ds_wall * (r ** (nj - 1) - 1) / (r - 1)
        lo, hi = (r, hi) if L < length else (lo, r)
    return ds_wall * (r ** np.arange(nj) - 1) / (r - 1)


def build_ogrid_march(surf: np.ndarray, nj: int, ds_wall: float, R_far: float, chord: float, blend: bool = False,
                      blend_len: float = 2.0) -> np.ndarray:
    """Normal-marching O-grid X[ni, nj, 2] (periodic in i, j = 0 on the wall).  blend=True ramps the smoothing
    from tangential-only to full Laplacian between 0.3 and 1 chord (needed for concave/cusped lower surfaces);
    blend=False switches at 0.5 chord (the setting used for the NACA 0012 grid family)."""
    target = R_far * chord
    d = stretching(nj, ds_wall, target)
    c = surf.mean(axis=0)
    ni = len(surf)
    X = np.zeros((ni, nj, 2))
    X[:, 0] = surf
    layer = surf.copy()
    for j in range(1, nj):
        tang = np.roll(layer, -1, axis=0) - np.roll(layer, 1, axis=0)
        nrm = np.column_stack([tang[:, 1], -tang[:, 0]])
        nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        if np.mean(np.sum((layer - c) * nrm, axis=1)) < 0:
            nrm = -nrm
        rad = layer - c
        rad /= np.linalg.norm(rad, axis=1)[:, None]
        f = (d[j] / target) ** 0.5
        if blend:  # turn towards the radial direction within a few chords (defocuses concave regions)
            f = max(f, min(1.0, d[j] / (blend_len * chord)) ** 0.7)
        dirv = (1 - f) * nrm + f * rad
        dirv /= np.linalg.norm(dirv, axis=1)[:, None]
        new = layer + dirv * (d[j] - d[j - 1])
        eps = min(0.45, 0.02 + 0.6 * (d[j] / chord) ** 0.5)
        npass = 3 if d[j] < 0.05 * chord else 8
        if blend and d[j] > 0.2 * chord:
            npass = 20
        for _ in range(npass):
            disp = 0.5 * (np.roll(new, 1, 0) + np.roll(new, -1, 0)) - new
            # tangential only near the body, blending to full Laplacian smoothing between 0.3 and 1 chord
            if blend:
                keep = float(np.clip((d[j] - 0.3 * chord) / (0.7 * chord), 0.0, 1.0))
            else:
                keep = 0.0 if d[j] < 0.5 * chord else 1.0
            disp -= (1.0 - keep) * np.sum(disp * dirv, axis=1)[:, None] * dirv
            new = new + eps * disp
        X[:, j] = new
        layer = new
    return X


def untangle(X: np.ndarray, window: int = 12, max_sweeps: int = 400) -> np.ndarray:
    """Local Laplacian smoothing of the grid points around folded cells until none are left
    (wall points j = 0 and the far-field ring are fixed)."""
    X = X.copy()
    ni, nj, _ = X.shape
    for _ in range(max_sweeps):
        A, B = X[:, :-1], np.roll(X, -1, 0)[:, :-1]
        Cc, D = np.roll(X, -1, 0)[:, 1:], X[:, 1:]
        area = (Cc - A)[..., 0] * (D - B)[..., 1] - (Cc - A)[..., 1] * (D - B)[..., 0]
        bad = np.argwhere(area * np.sign(np.median(area)) <= 0)
        if len(bad) == 0:
            break
        mask = np.zeros((ni, nj), bool)
        for i, j in bad:
            ii = np.arange(i - window, i + window + 1) % ni
            mask[np.ix_(ii, np.arange(max(1, j - window), min(nj - 1, j + window + 1)))] = True
        avg = 0.25 * (np.roll(X, 1, 0) + np.roll(X, -1, 0) + np.roll(X, 1, 1) + np.roll(X, -1, 1))
        X[mask] = 0.5 * X[mask] + 0.5 * avg[mask]
    return X


def coarsen(X: np.ndarray, levels: int = 1) -> np.ndarray:
    """Remove every second grid line in both directions (nested family, ratio 2 per level).
    Requires ni divisible by 2**levels and (nj-1) divisible by 2**levels."""
    s = 2 ** levels
    assert X.shape[0] % s == 0 and (X.shape[1] - 1) % s == 0
    return X[::s, ::s]


def inverted_cells(X: np.ndarray) -> int:
    """Number of quads whose orientation differs from the majority."""
    A, B = X[:, :-1], np.roll(X, -1, 0)[:, :-1]
    Cc, D = np.roll(X, -1, 0)[:, 1:], X[:, 1:]
    area = (Cc - A)[..., 0] * (D - B)[..., 1] - (Cc - A)[..., 1] * (D - B)[..., 0]
    sign = np.sign(np.median(area))
    return int(np.sum(area * sign <= 0))


def write_polymesh(X: np.ndarray, case: Path, dz: float = 0.01) -> dict:
    """Write an O-grid X[ni, nj, 2] as a one-cell-thick polyMesh (vectorised)."""
    ni, nj, _ = X.shape
    pm = case / "constant" / "polyMesh"
    pm.mkdir(parents=True, exist_ok=True)
    P = np.zeros((2, nj, ni, 3))
    P[0, :, :, :2] = X.transpose(1, 0, 2)
    P[1, :, :, :2] = X.transpose(1, 0, 2)
    P[1, :, :, 2] = dz
    P = P.reshape(-1, 3)
    I, J = np.meshgrid(np.arange(ni), np.arange(nj), indexing="xy")  # [j, i]

    def pid(i, j, k):
        return k * ni * nj + j * ni + (i % ni)

    def cid(i, j):
        return j * ni + (i % ni)

    nc = ni * (nj - 1)
    ii, jj = np.meshgrid(np.arange(ni), np.arange(nj - 1), indexing="xy")
    ii, jj = ii.ravel(), jj.ravel()
    q = np.stack([pid(ii, jj, 0), pid(ii + 1, jj, 0), pid(ii + 1, jj + 1, 0), pid(ii, jj + 1, 0)], 1)
    cents = P[q].mean(axis=1) + np.array([0, 0, dz / 2])

    def orient(f, o, target):
        """Flip faces whose normal does not point from the owner centre towards `target`."""
        p = P[f]
        n = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
        bad = np.einsum("ij,ij->i", n, target - cents[o]) < 0
        f[bad] = f[bad][:, ::-1]
        return f

    # internal faces of constant i (between cells i-1 and i)
    a, b = cid(ii - 1, jj), cid(ii, jj)
    f1 = np.stack([pid(ii, jj, 0), pid(ii, jj, 1), pid(ii, jj + 1, 1), pid(ii, jj + 1, 0)], 1)
    o1, n1 = np.minimum(a, b), np.maximum(a, b)
    # internal faces of constant j (between cells j-1 and j)
    i2, j2 = np.meshgrid(np.arange(ni), np.arange(1, nj - 1), indexing="xy")
    i2, j2 = i2.ravel(), j2.ravel()
    f2 = np.stack([pid(i2, j2, 0), pid(i2 + 1, j2, 0), pid(i2 + 1, j2, 1), pid(i2, j2, 1)], 1)
    o2, n2 = cid(i2, j2 - 1), cid(i2, j2)
    F = np.vstack([f1, f2]); O = np.concatenate([o1, o2]); N = np.concatenate([n1, n2])
    order = np.lexsort((N, O))
    F, O, N = F[order], O[order], N[order]
    F = orient(F, O, cents[N])
    n_internal = len(F)
    faces, owner = [F], [O]
    patches = []
    start = n_internal
    i0 = np.arange(ni)
    # wall j = 0
    fw = np.stack([pid(i0, 0, 0), pid(i0, 0, 1), pid(i0 + 1, 0, 1), pid(i0 + 1, 0, 0)], 1)
    ow = cid(i0, 0)
    fw = orient(fw, ow, P[fw].mean(axis=1))
    faces.append(fw); owner.append(ow); patches.append(("airfoil", "wall", start, ni)); start += ni
    ff = np.stack([pid(i0, nj - 1, 0), pid(i0 + 1, nj - 1, 0), pid(i0 + 1, nj - 1, 1), pid(i0, nj - 1, 1)], 1)
    of = cid(i0, nj - 2)
    ff = orient(ff, of, P[ff].mean(axis=1))
    faces.append(ff); owner.append(of); patches.append(("farfield", "patch", start, ni)); start += ni
    for name, k in (("back", 0), ("front", 1)):
        fe = np.stack([pid(ii, jj, k), pid(ii + 1, jj, k), pid(ii + 1, jj + 1, k), pid(ii, jj + 1, k)], 1)
        oe = cid(ii, jj)
        fe = orient(fe, oe, P[fe].mean(axis=1))
        faces.append(fe); owner.append(oe); patches.append((name, "empty", start, nc)); start += nc
    F = np.vstack(faces); O = np.concatenate(owner)

    hdr = lambda cls, obj, note="": ("FoamFile\n{\n    version 2.0;\n    format ascii;\n    class " + cls +
                                     ";\n    location \"constant/polyMesh\";\n    object " + obj + ";\n" + note + "}\n\n")
    with open(pm / "points", "w") as fh:
        fh.write(hdr("vectorField", "points"))
        fh.write(f"{len(P)}\n(\n" + "\n".join(f"({p[0]:.12g} {p[1]:.12g} {p[2]:.12g})" for p in P) + "\n)\n")
    with open(pm / "faces", "w") as fh:
        fh.write(hdr("faceList", "faces"))
        fh.write(f"{len(F)}\n(\n" + "\n".join(f"4({f[0]} {f[1]} {f[2]} {f[3]})" for f in F) + "\n)\n")
    note = f"    note \"nPoints:{len(P)} nCells:{nc} nFaces:{len(F)} nInternalFaces:{n_internal}\";\n"
    with open(pm / "owner", "w") as fh:
        fh.write(hdr("labelList", "owner", note))
        fh.write(f"{len(O)}\n(\n" + "\n".join(map(str, O.tolist())) + "\n)\n")
    with open(pm / "neighbour", "w") as fh:
        fh.write(hdr("labelList", "neighbour", note))
        fh.write(f"{len(N)}\n(\n" + "\n".join(map(str, N.tolist())) + "\n)\n")
    with open(pm / "boundary", "w") as fh:
        fh.write(hdr("polyBoundaryMesh", "boundary"))
        fh.write(f"{len(patches)}\n(\n")
        for name, typ, st, n in patches:
            extra = "        inGroups List<word> 1(wall);\n" if typ == "wall" else ""
            fh.write(f"    {name}\n    {{\n        type {typ};\n{extra}        nFaces {n};\n        startFace {st};\n    }}\n")
        fh.write(")\n")
    return dict(cells=nc, ni=ni, nj=nj)
