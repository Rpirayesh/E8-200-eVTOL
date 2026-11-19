"""Geometry helpers for the E8-200 part library (all lengths in millimetres).

Adapted from the E8-S subscale library (../E8-eVTOL-Build/tools/cad/geom.py): 2-D profile
operations with shapely, prisms/lofts/tubes with build123d.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from build123d import Face, Location, Plane, Solid, Vector, Wire, extrude, Compound
from scipy.interpolate import PchipInterpolator
from shapely.geometry import LineString, Polygon, box as sbox

# --------------------------------------------------------------------------- airfoils


def _cosine(n: int) -> np.ndarray:
    return (1 - np.cos(np.linspace(0, np.pi, n))) / 2


def selig_airfoil(path: Path, chord: float, n: int = 90) -> np.ndarray:
    """Closed profile (x, z) from a Selig file, TE upper -> LE -> TE lower, resampled with
    cosine spacing (interpolation in sqrt(x) keeps the leading edge smooth)."""
    d = np.loadtxt(path, skiprows=1)
    i = int(np.argmin(d[:, 0]))
    up, lo = d[: i + 1][::-1], d[i:]
    x = _cosine(n)
    zu = PchipInterpolator(np.sqrt(up[:, 0]), up[:, 1])(np.sqrt(x))
    zl = PchipInterpolator(np.sqrt(lo[:, 0]), lo[:, 1])(np.sqrt(x))
    pts = np.vstack([np.column_stack([x[::-1], zu[::-1]]), np.column_stack([x[1:], zl[1:]])]) * chord
    return pts


def naca4(code: str, chord: float, n: int = 60, te_mm: float = 1.0) -> np.ndarray:
    """Closed NACA 4-digit profile with a finite trailing edge (te_mm total)."""
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    x = _cosine(n)
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)
    yt = np.maximum(yt, te_mm / 2 / chord * x)
    if m == 0:
        yc = np.zeros_like(x)
    else:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2))
    xu, zu, xl, zl = x, yc + yt, x, yc - yt
    return np.vstack([np.column_stack([xu[::-1], zu[::-1]]), np.column_stack([xl[1:], zl[1:]])]) * chord


def thickness_at(pts: np.ndarray, x: float) -> tuple[float, float]:
    """Lower and upper z of a closed profile at chordwise station x."""
    cut = Polygon(pts).buffer(0).intersection(LineString([(x, -1e5), (x, 1e5)]))
    if cut.is_empty:
        raise ValueError(f"x={x} outside profile")
    zs = [c[1] for c in cut.coords] if hasattr(cut, "coords") else [c[1] for g in cut.geoms for c in g.coords]
    return min(zs), max(zs)


def _poly_pts(poly) -> np.ndarray:
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return np.array(poly.exterior.coords)[:-1]


def offset2d(pts: np.ndarray, d: float) -> np.ndarray:
    return _poly_pts(Polygon(pts).buffer(d, join_style=2, mitre_limit=3.0))


def clip2d(pts: np.ndarray, xmin=-1e9, xmax=1e9, zmin=-1e9, zmax=1e9) -> np.ndarray:
    return _poly_pts(Polygon(pts).buffer(0).intersection(sbox(xmin, zmin, xmax, zmax)))


def simplify2d(pts: np.ndarray, tol: float = 0.05) -> np.ndarray:
    return _poly_pts(Polygon(pts).simplify(tol))


# --------------------------------------------------------------------------- faces / solids


SMOOTH = False         # fit splines through smooth runs of profile points (smaller STEP, smooth surfaces)
CORNER_DEG = 25.0


def _wire(verts, smooth=None) -> Wire:
    P = np.asarray(verts, float)
    # drop duplicate consecutive points
    keep = [0]
    for i in range(1, len(P)):
        if np.linalg.norm(P[i] - P[keep[-1]]) > 1e-6:
            keep.append(i)
    P = P[keep]
    if np.linalg.norm(P[0] - P[-1]) < 1e-6:
        P = P[:-1]
    n = len(P)
    if not (SMOOTH if smooth is None else smooth) or n < 6:
        return Wire.make_polygon([Vector(*v) for v in P], close=True)
    from build123d import Edge
    ang = np.zeros(n)
    for i in range(n):
        a, b = P[i] - P[i - 1], P[(i + 1) % n] - P[i]
        c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        ang[i] = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    corners = [i for i in range(n) if ang[i] > CORNER_DEG]
    if not corners:
        return Wire([Edge.make_spline([Vector(*v) for v in P], periodic=True)])
    edges = []
    for k, c0 in enumerate(corners):
        c1 = corners[(k + 1) % len(corners)]
        idx = list(range(c0, c1 + 1)) if c1 > c0 else list(range(c0, n)) + list(range(0, c1 + 1))
        pts = [Vector(*P[i]) for i in idx]
        if len(pts) == 2:
            edges.append(Edge.make_line(pts[0], pts[1]))
        elif len(pts) == 3:
            edges += [Edge.make_line(pts[0], pts[1]), Edge.make_line(pts[1], pts[2])]
        else:
            edges.append(Edge.make_spline(pts))
    return Wire(edges)


def face_xz(pts, y=0.0) -> Face:
    return Face(_wire([(p[0], y, p[1]) for p in pts]))


def face_yz(pts, x=0.0) -> Face:
    return Face(_wire([(x, p[0], p[1]) for p in pts]))


def face_xy(pts, z=0.0) -> Face:
    return Face(_wire([(p[0], p[1], z) for p in pts]))


def prism_y(pts, y0, y1) -> Solid:
    return extrude(face_xz(pts, y0), y1 - y0, dir=(0, 1, 0))


def prism_x(pts, x0, x1) -> Solid:
    """pts are (y, z)."""
    return extrude(face_yz(pts, x0), x1 - x0, dir=(1, 0, 0))


def prism_z(pts, z0, z1) -> Solid:
    """pts are (x, y)."""
    return extrude(face_xy(pts, z0), z1 - z0, dir=(0, 0, 1))


def loft3d(rings: list[np.ndarray], ruled: bool = False, smooth: bool = False) -> Solid:
    """Loft through closed 3-D point rings (same point count); smooth=True fits closed splines."""
    return Solid.make_loft([_wire(r, smooth) for r in rings], ruled=ruled)


def superellipse(w: float, h: float, yc=0.0, zc=0.0, n: float = 2.5, npts: int = 72) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, npts, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    return np.column_stack([yc + w / 2 * np.sign(c) * np.abs(c) ** (2 / n), zc + h / 2 * np.sign(s) * np.abs(s) ** (2 / n)])


def circle(r, cy=0.0, cz=0.0, npts=48) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, npts, endpoint=False)
    return np.column_stack([cy + r * np.cos(t), cz + r * np.sin(t)])


def rounded_rect(a, b, r, ca=0.0, cb=0.0) -> np.ndarray:
    poly = sbox(ca - a / 2 + r, cb - b / 2 + r, ca + a / 2 - r, cb + b / 2 - r).buffer(r, quad_segs=6)
    return np.array(poly.exterior.coords)[:-1]


def cyl(r, p0, d, length) -> Solid:
    return Solid.make_cylinder(r, length, Plane(origin=tuple(map(float, p0)), z_dir=tuple(map(float, d))))


def cyl_x(r, x0, x1, y=0.0, z=0.0) -> Solid:
    return cyl(r, (x0, y, z), (1, 0, 0), x1 - x0)


def cyl_y(r, y0, y1, x=0.0, z=0.0) -> Solid:
    return cyl(r, (x, y0, z), (0, 1, 0), y1 - y0)


def cyl_z(r, z0, z1, x=0.0, y=0.0) -> Solid:
    return cyl(r, (x, y, z0), (0, 0, 1), z1 - z0)


def tube_x(ro, ri, x0, x1, y=0.0, z=0.0) -> Solid:
    return cyl_x(ro, x0, x1, y, z) - cyl_x(ri, x0 - 1, x1 + 1, y, z)


def tube_y(ro, ri, y0, y1, x=0.0, z=0.0) -> Solid:
    return cyl_y(ro, y0, y1, x, z) - cyl_y(ri, y0 - 1, y1 + 1, x, z)


def tube_z(ro, ri, z0, z1, x=0.0, y=0.0) -> Solid:
    return cyl_z(ro, z0, z1, x, y) - cyl_z(ri, z0 - 1, z1 + 1, x, y)


def tube_between(p1, p2, ro, ri=0.0) -> Solid:
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    d = p2 - p1
    L = float(np.linalg.norm(d))
    s = cyl(ro, p1, d / L, L)
    if ri > 0:
        s = s - cyl(ri, p1 - d / L, d / L, L + 2)
    return s


def box(x0, x1, y0, y1, z0, z1) -> Solid:
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0, Plane(origin=(x0, y0, z0)))


def sphere(r, c) -> Solid:
    return Solid.make_sphere(r, Plane(origin=tuple(map(float, c))))


def compound(solids) -> Compound:
    out = []
    for s in solids:
        out += list(s.solids()) if hasattr(s, "solids") else [s]
    return Compound(children=out)


def fuse_all(solids):
    s = solids[0]
    for t in solids[1:]:
        s = s + t
    return s


def bolt_holes_z(solid, pts, d, z0, z1):
    for x, y in pts:
        solid = solid - cyl_z(d / 2, z0, z1, x, y)
    return solid


def swept_tube(path_pts: np.ndarray, bend_r: float, ro: float, ri: float) -> Solid:
    """Tube swept along a polyline with circular bends of radius bend_r at the inner vertices."""
    from build123d import Edge, Wire as W
    P = [np.asarray(p, float) for p in path_pts]
    edges = []
    cur = P[0]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        u1 = (b - a) / np.linalg.norm(b - a)
        u2 = (c - b) / np.linalg.norm(c - b)
        ang = math.acos(max(-1.0, min(1.0, float(u1 @ u2))))
        t = bend_r * math.tan(ang / 2)
        s, e = b - u1 * t, b + u2 * t
        edges.append(Edge.make_line(Vector(*cur), Vector(*s)))
        mid_dir = (u2 - u1) / np.linalg.norm(u2 - u1)
        ctr = b + mid_dir * bend_r / math.cos(ang / 2)
        m = ctr + (b - ctr) / np.linalg.norm(b - ctr) * bend_r
        edges.append(Edge.make_three_point_arc(Vector(*s), Vector(*m), Vector(*e)))
        cur = e
    edges.append(Edge.make_line(Vector(*cur), Vector(*P[-1])))
    path = W(edges)
    d0 = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])
    pl = Plane(origin=tuple(P[0]), z_dir=tuple(d0))
    from build123d import Circle  # noqa: F401
    outer = Face(Wire.make_circle(ro, pl))
    inner = Wire.make_circle(ri, pl)
    sec = Face(Wire.make_circle(ro, pl), [inner]) if ri > 0 else outer
    return Solid.sweep(sec, path, transition=__import__("build123d").Transition.ROUND)


def p5_hardpoint(P):
    """WP F part P5 (parachute riser hard point) in its part frame: plate in x-z, thickness along y, eye axis along y."""
    s = box(-P["plate_w"] / 2, P["plate_w"] / 2, -P["t"] / 2, P["t"] / 2, -P["plate_h"] / 2, P["plate_h"] / 2)
    s = s + box(-P["neck_w"] / 2, P["neck_w"] / 2, -P["t"] / 2, P["t"] / 2, 20.0, 20.0 + P["neck_h"])
    s = s + cyl_y(P["neck_w"] / 2, -P["t"] / 2, P["t"] / 2, 0, P["eye_zc"])
    s = s - cyl_y(P["pin_d"] / 2, -P["t"], P["t"], 0, P["eye_zc"])
    for x, z in P["bolts"]:
        s = s - cyl_y(P["bolt_d"] / 2, -P["t"], P["t"], x, z)
    return s


def p5_angle(P, face_dx, t=6.0):
    """Angle that carries a P5 plate (centred at the origin) to a face normal to x at x = face_dx (< plate start)."""
    a = box(face_dx + t, P["plate_w"] / 2, P["t"] / 2, P["t"] / 2 + t, -P["plate_h"] / 2, P["plate_h"] / 2)
    b = box(face_dx, face_dx + t, -40.0, P["t"] / 2 + t, -P["plate_h"] / 2, P["plate_h"] / 2)
    s = a + b
    for x, z in P["bolts"]:
        s = s - cyl_y(P["bolt_d"] / 2, -P["t"], P["t"] + t + 1, x, z)
    for z in (-18.0, 18.0):
        for y in (-20.0, 2.0):
            s = s - cyl_x(P["bolt_d"] / 2, face_dx - 1, face_dx + t + 1, y, z)
    return s


def sector_z(r0, r1, a0_deg, a1_deg, z0, z1, n=16):
    """Annular sector prism about the z axis (for pocketing round plates)."""
    a = np.radians(np.linspace(a0_deg, a1_deg, n))
    pts = np.vstack([np.column_stack([r1 * np.cos(a), r1 * np.sin(a)]), np.column_stack([r0 * np.cos(a[::-1]), r0 * np.sin(a[::-1])])])
    return prism_z(pts, z0, z1)
