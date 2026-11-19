"""Parametric outer mould line (OML) for CFD, built from design/geometry.json.

Every component is a closed, watertight triangulated surface (numpy + trimesh), one STL per force-breakdown
region: fuselage, wing, tail, booms, rotors (lift-rotor hubs and stopped blades), pusher, gear.
Axes: x aft from the nose, y right, z up, metres.  The full (two-sided) aircraft is built; the half-model
mesh clips it at the y = 0 symmetry plane.  The expected geometry.json fields are documented in cfd/README.md.

    python cfd/tools/oml.py [--geometry design/geometry.json] [--out cfd/.cache/oml] [--hover]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foamcase import CACHE, ROOT  # noqa: E402

AIRFOIL_DIR = ROOT / "validation" / "cfd" / "reference"


# ----------------------------------------------------------------------------- section shapes
def airfoil_coords(spec, n: int = 121) -> np.ndarray:
    """Closed-TE unit-chord airfoil, TE -> upper -> LE -> lower (n points, last point != first).
    spec: 'naca0012', 'naca2412', 'ls417' / 'gaw1', a Selig .dat path, or {'coords_file': path}."""
    from airfoil2d import close_te, naca4_closed, naca230, read_selig, spline_contour
    if isinstance(spec, dict):
        spec = spec.get("coords_file") or spec.get("name")
    s = str(spec).lower().replace("-", "").replace(" ", "")
    if s.startswith("naca") and len(s) == 8 and s[4:].isdigit():
        pts = naca4_closed(s[4:], 401)
    elif s.startswith("naca230") and len(s) == 9:
        pts = naca230(s[4:], 401)
    elif s in ("ls417", "ls(1)0417", "gaw1", "ga(w)1", "ls10417"):
        pts = close_te(spline_contour(read_selig(AIRFOIL_DIR / "ls417_coordinates_TND7428.dat"), 801))  # 3-D: closed TE
    else:
        p = Path(spec)
        if not p.is_absolute():
            p = ROOT / p
        pts = spline_contour(read_selig(p), 801)
        if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
            pts = close_te(pts)
    # re-sample with LE/TE clustering, drop the duplicate closing point
    from ogrid import resample_surface
    return resample_surface(pts, n if n % 2 == 0 else n + 1)


def superellipse(width: float, height: float, n: int = 48, exponent: float = 2.5) -> np.ndarray:
    """(y, z) ring of a super-ellipse |y/a|^e + |z/b|^e = 1, counter-clockwise from +y."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    y = 0.5 * width * np.sign(c) * np.abs(c) ** (2 / exponent)
    z = 0.5 * height * np.sign(s) * np.abs(s) ** (2 / exponent)
    return np.column_stack([y, z])


# ----------------------------------------------------------------------------- surface builders
def loft(rings: list[np.ndarray], cap_start: bool = True, cap_end: bool = True):
    """Triangulate a closed loft through rings (each m x 3, same m, same orientation).  A ring of
    (near) zero size is collapsed to a single apex.  Returns trimesh.Trimesh."""
    import trimesh
    V, F = [], []
    m = len(rings[0])
    idx = []
    for r in rings:
        r = np.asarray(r, float)
        size = np.ptp(r, axis=0).max()
        if size < 1e-6:
            idx.append(("apex", len(V)))
            V.append(r.mean(axis=0))
        else:
            idx.append(("ring", len(V)))
            V.extend(r)
    for (ta, a), (tb, b) in zip(idx[:-1], idx[1:]):
        for i in range(m):
            j = (i + 1) % m
            if ta == "ring" and tb == "ring":
                F.append([a + i, a + j, b + j]); F.append([a + i, b + j, b + i])
            elif ta == "apex" and tb == "ring":
                F.append([a, b + j, b + i])
            elif ta == "ring" and tb == "apex":
                F.append([a + i, a + j, b])
    for cap, (t, a), flip in ((cap_start, idx[0], True), (cap_end, idx[-1], False)):
        if cap and t == "ring":
            c = len(V)
            V.append(np.asarray(V[a:a + m]).mean(axis=0))
            for i in range(m):
                j = (i + 1) % m
                F.append([c, a + j, a + i] if flip else [c, a + i, a + j])
    mesh = trimesh.Trimesh(np.array(V), np.array(F), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def lifting_surface(sections: list[dict], airfoil, n: int = 241, mirror: bool = False, vertical: bool = False):
    """Loft through sections [{'x_le','y','z','chord','twist_deg'}] (twist positive nose-up about the LE).
    vertical=True: sections stacked in z (fins), 'y' is the lateral position and the profile lies in x-y."""
    foil = airfoil_coords(airfoil, n)
    rings = []
    for s in sections:
        c = s["chord"]
        tw = math.radians(s.get("twist_deg", 0.0))
        x = foil[:, 0] * c
        t = foil[:, 1] * c
        # rotate nose-up by tw about the leading edge (x aft, z up -> nose up = TE down)
        xr = x * math.cos(tw) + t * math.sin(tw)
        tr = -x * math.sin(tw) + t * math.cos(tw)
        if vertical:
            rings.append(np.column_stack([s["x_le"] + xr, s["y"] + tr, np.full_like(xr, s["z"])]))
        else:
            rings.append(np.column_stack([s["x_le"] + xr, np.full_like(xr, s["y"]), s["z"] + tr]))
    meshes = [loft(rings)]
    if mirror:
        m2 = meshes[0].copy()
        m2.apply_transform(np.diag([1, -1, 1, 1]))
        m2.invert()
        meshes.append(m2)
    return meshes


def body_of_revolution(stations: list[tuple[float, float]], axis_p0, axis_dir, n: int = 36):
    """Body of revolution: stations [(s along axis from p0, radius)], radius 0 -> apex."""
    d = np.asarray(axis_dir, float); d /= np.linalg.norm(d)
    a = np.cross(d, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-6:
        a = np.cross(d, [0, 1.0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(d, a)
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rings = []
    for s, r in stations:
        c = np.asarray(axis_p0, float) + s * d
        rings.append(c + r * (np.outer(np.cos(t), a) + np.outer(np.sin(t), b)))
    return loft(rings)


def tube(p1, p2, diameter: float, n: int = 24, rounded: bool = True):
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    L = np.linalg.norm(p2 - p1)
    r = diameter / 2
    if rounded:
        k = np.linspace(0, np.pi / 2, 6)
        st = [(r - r * np.cos(x), r * np.sin(x)) for x in k]
        st += [(L - r + r * np.sin(x), r * np.cos(x)) for x in k]
    else:
        st = [(0, 0), (0, r), (L, r), (L, 0)]
    return body_of_revolution(st, p1, p2 - p1, n)


def faired_strut(p1, p2, thickness: float, chord: float, n: int = 61):
    """Streamlined strut between p1 and p2: symmetric NACA 00xx section (t/c = thickness/chord) with its chord along +x
    (flow direction) and centred on the strut axis."""
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    tc = int(round(100 * min(max(thickness / chord, 0.06), 0.40)))
    foil = airfoil_coords(f"naca00{tc:02d}", n)
    d = (p2 - p1) / np.linalg.norm(p2 - p1)
    ex = np.array([1.0, 0, 0]) - d * d[0]
    ex /= np.linalg.norm(ex)
    en = np.cross(d, ex)
    rings = [p + np.outer((foil[:, 0] - 0.4) * chord, ex) + np.outer(foil[:, 1] * chord, en) for p in (p1, p2)]
    return loft(rings)


def blade(hub, axis, azimuth_deg: float, r0: float, R: float, chord: float, pitch_deg: float = 8.0,
          thickness: float = 0.12, n: int = 41, spin_sign: float = 1.0):
    """Stopped rotor blade as a flat-lofted symmetric section from r0 to R at a given azimuth."""
    foil = airfoil_coords("naca00" + f"{int(round(thickness * 100)):02d}", n)
    d = np.asarray(axis, float); d /= np.linalg.norm(d)
    ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    e1 = ref - d * (ref @ d); e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    az = math.radians(azimuth_deg)
    span = math.cos(az) * e1 + math.sin(az) * e2          # blade radial direction
    chordwise = np.cross(d, span) * spin_sign            # leading edge points in the direction of rotation
    p = math.radians(pitch_deg)
    cdir = -chordwise * math.cos(p) - d * math.sin(p)    # LE -> TE direction, pitched nose-up
    tdir = np.cross(span, cdir); tdir /= np.linalg.norm(tdir)
    rings = []
    for r in np.linspace(r0, R, 8):
        base = np.asarray(hub, float) + r * span + 0.25 * chord * chordwise
        rings.append(base + np.outer(foil[:, 0] * chord, cdir) + np.outer(foil[:, 1] * chord, tdir))
    return loft(rings)


# ----------------------------------------------------------------------------- aircraft from geometry.json
def wing_sections(w: dict) -> list[dict]:
    """Right-wing sections from either an explicit 'sections' list or a trapezoid (root/tip)."""
    if "sections" in w:
        return [dict(s) for s in w["sections"]]
    b2 = 0.5 * w["span"]
    y0 = w.get("y_root", 0.0)
    sweep = math.radians(w.get("sweep_le_deg", 0.0))
    dih = math.radians(w.get("dihedral_deg", 0.0))
    inc = w.get("incidence_deg", 0.0)
    tw = w.get("twist_tip_deg", 0.0)
    out = []
    for f in (0.0, 1.0):
        y = y0 + f * (b2 - y0)
        out.append(dict(y=y, x_le=w["x_le_root"] + (y - y0) * math.tan(sweep), z=w["z_root"] + (y - y0) * math.tan(dih),
                        chord=w["root_chord"] + f * (w["tip_chord"] - w["root_chord"]), twist_deg=inc + f * tw))
    return out


def build(geo: dict, hover: bool = False) -> dict:
    """Return {region: [trimesh, ...]}.  hover=True leaves out lift-rotor blades (actuator disks replace them)."""
    R = {k: [] for k in ("fuselage", "wing", "tail", "booms", "rotors", "pusher", "gear")}
    # wing (both sides; root section mirrored at y = -y_root)
    w = geo["wing"]
    secs = wing_sections(w)
    if secs[0]["y"] > 1e-9:  # carry-through: extend to the centre line inside the fuselage
        secs = [dict(secs[0], y=0.0)] + secs
    left = [dict(s, y=-s["y"]) for s in reversed(secs[1:])]
    R["wing"] += lifting_surface(left + secs, w.get("airfoil", "naca2412"))
    # fuselage
    f = geo.get("fuselage")
    if f:
        rings = []
        stations = f["stations"]
        if len(stations) < 40:   # smooth the loft: monotone cubic interpolation of the station data
            from scipy.interpolate import PchipInterpolator
            xs = np.array([st["x"] for st in stations])
            xi = xs[0] + (xs[-1] - xs[0]) * (1 - np.cos(np.linspace(0, np.pi, 61))) / 2
            ip = {k: PchipInterpolator(xs, [st[k] for st in stations]) for k in ("width", "height", "z_center")}
            stations = [dict(x=float(x), **{k: float(ip[k](x)) for k in ip}) for x in xi]
            # the end points must close: the interpolated nose/tail sizes are ~0 at the ends
        for st in stations:
            ring = superellipse(max(st["width"], 0.0), max(st["height"], 0.0), 48, f.get("shape_exponent", 2.5))
            rings.append(np.column_stack([np.full(len(ring), st["x"]), ring[:, 0], st["z_center"] + ring[:, 1]]))
        R["fuselage"].append(loft(rings))
    # booms
    for b in geo.get("booms", []):
        d = b["diameter"]
        for y in ([b["y"], -b["y"]] if b.get("mirror", True) else [b["y"]]):
            R["booms"].append(tube((b["x_start"], y, b["z"]), (b["x_end"], y, b["z"]), d))
    # lift rotors: hub (nacelle/motor) + stopped blades
    for r in geo.get("lift_rotors", []):
        hub = np.asarray(r["hub"], float)
        ax = np.asarray(r.get("axis", (0, 0, 1)), float)
        hd = r.get("hub_diameter", 0.08 * r["diameter"])
        hh = r.get("hub_height", 0.6 * hd)
        R["rotors"].append(body_of_revolution([(0, 0), (0, hd / 2), (hh, hd / 2), (hh + 0.25 * hd, 0)], hub - ax * 0.5 * hh, ax, 32))
        # motor mast from the boom to the motor (not in geometry.json: tube of 0.4 hub diameter unless "mast_diameter" given)
        for b in geo.get("booms", []):
            ys = [b["y"], -b["y"]] if b.get("mirror", True) else [b["y"]]
            for yb in ys:
                if abs(hub[1] - yb) < 0.05 and b["x_start"] <= hub[0] <= b["x_end"] and hub[2] - 0.5 * hh - b["z"] > 0.05:
                    # faired pylon as assumed by the sizing drag build-up: 0.05 m thick, t/c 0.25 (override: mast_thickness/chord)
                    mt = r.get("mast_thickness", 0.05)
                    R["rotors"].append(faired_strut((hub[0], yb, b["z"]), (hub[0], yb, hub[2] - 0.5 * hh + 0.01), mt,
                                                    r.get("mast_chord", 4 * mt)))
        if not hover:
            nb = r.get("blades", 2)
            for k in range(nb):
                az = r.get("stopped_azimuth_deg", 0.0) + 360.0 * k / nb
                R["rotors"].append(blade(hub, ax, az, 0.45 * hd, r["diameter"] / 2, r.get("blade_chord", 0.06 * r["diameter"]),
                                         r.get("blade_pitch_deg", 8.0), spin_sign=1.0 if r.get("spin", "ccw") == "ccw" else -1.0))
    # pusher: spinner + stopped blades (blades omitted when the pusher is an actuator disk)
    # pushers: one (tail cone) or several ("pushers" list, e.g. twin boom-tail units): motor can + spinner (+ blades)
    pushers = geo.get("pushers") or ([geo["pusher"]] if geo.get("pusher") else [])
    for p in pushers:
        hub = np.asarray(p["hub"], float)
        ax = np.asarray(p.get("axis", (-1, 0, 0)), float)
        sd = p.get("spinner_diameter", 0.18 * p["diameter"])
        sl = p.get("spinner_length", 1.2 * sd)
        mot = p.get("motor") if isinstance(p.get("motor"), dict) else None
        if mot and mot.get("x_face") is not None and mot.get("diameter"):
            # motor can from its mounting face to the spinner (boom-end units)
            x0 = mot["x_face"]
            x1 = hub[0] + ax[0] * 0.2 * sl
            R["pusher"].append(tube((x0 - 0.01, hub[1], hub[2]), (max(x1, x0 + mot.get("length", 0.09)), hub[1], hub[2]),
                                    mot["diameter"], rounded=False))
        R["pusher"].append(body_of_revolution([(0, 0), (0.15 * sl, 0.5 * sd), (0.55 * sl, 0.45 * sd), (sl, 0)],
                                              hub + ax * 0.2 * sl, -ax, 32))
        if p.get("blades_in_cfd", False):
            nb = p.get("blades", 3)
            for k in range(nb):
                R["pusher"].append(blade(hub, ax, 360.0 * k / nb, 0.45 * sd, p["diameter"] / 2,
                                         p.get("blade_chord", 0.07 * p["diameter"]), p.get("blade_pitch_deg", 25.0)))
    # tail
    t = geo.get("tail", {})
    for h in t.get("horizontal", []):
        secs = wing_sections(h)
        if h.get("mirror", True) and secs[0]["y"] > 1e-9:
            secs = [dict(secs[0], y=0.0)] + secs
        full = ([dict(s, y=-s["y"]) for s in reversed(secs[1:])] + secs) if h.get("mirror", True) else secs
        R["tail"] += lifting_surface(full, h.get("airfoil", "naca0012"))
    for v in t.get("vertical", []):
        h = v["height"]
        secs = [dict(x_le=v["x_le_root"], y=v["y"], z=v["z_root"], chord=v["root_chord"]),
                dict(x_le=v["x_le_root"] + h * math.tan(math.radians(v.get("sweep_le_deg", 0.0))), y=v["y"],
                     z=v["z_root"] + h, chord=v["tip_chord"])]
        R["tail"] += lifting_surface(secs, v.get("airfoil", "naca0012"), vertical=True)
        if v.get("mirror", False):
            R["tail"] += lifting_surface([dict(s, y=-s["y"]) for s in secs], v.get("airfoil", "naca0012"), vertical=True)
    # landing gear
    g = geo.get("landing_gear", {})
    for s in g.get("skids", []):
        for y in ([s["y"], -s["y"]] if s.get("mirror", True) else [s["y"]]):
            R["gear"].append(tube((s["x_start"], y, s["z"]), (s["x_end"], y, s["z"]), s["diameter"]))
    faired = bool(g.get("cross_tube", {}).get("faired", False) or g.get("faired", False))
    for s in g.get("struts", []):
        p1, p2 = np.asarray(s["p1"], float), np.asarray(s["p2"], float)
        mk = (lambda a, b: faired_strut(a, b, s["diameter"], 2.5 * s["diameter"])) if faired else (lambda a, b: tube(a, b, s["diameter"]))
        R["gear"].append(mk(p1, p2))
        if s.get("mirror", True) and abs(p1[1]) + abs(p2[1]) > 1e-6:
            R["gear"].append(mk(p1 * [1, -1, 1], p2 * [1, -1, 1]))
    for wh in g.get("wheels", []):
        c = np.asarray(wh["center"], float)
        for cc in ([c, c * [1, -1, 1]] if wh.get("mirror", True) and abs(c[1]) > 1e-6 else [c]):
            wdt, D = wh["width"], wh["diameter"]
            R["gear"].append(body_of_revolution([(0, 0), (0, D / 2 * 0.8), (0.15 * wdt, D / 2), (0.85 * wdt, D / 2), (wdt, D / 2 * 0.8), (wdt, 0)],
                                                cc - [0, wdt / 2, 0], (0, 1, 0), 32))
    return {k: v for k, v in R.items() if v}


def export(regions: dict, out: Path) -> dict:
    import trimesh
    out.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, meshes in regions.items():
        m = trimesh.util.concatenate(meshes)
        m.export(out / f"{name}.stl")
        info[name] = dict(faces=len(m.faces), watertight_parts=sum(x.is_watertight for x in meshes), parts=len(meshes),
                          bounds=np.round(m.bounds, 4).tolist(), area_m2=float(m.area))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", type=Path, default=ROOT / "design" / "geometry.json")
    ap.add_argument("--out", type=Path, default=CACHE / "oml")
    ap.add_argument("--hover", action="store_true")
    a = ap.parse_args()
    geo = json.loads(a.geometry.read_text())
    info = export(build(geo, hover=a.hover), a.out)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
