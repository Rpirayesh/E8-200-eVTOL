"""CalculiX (ccx 2.23) interface: structured meshes, gmsh meshes, deck helpers, result readers.

Units are the caller's choice but must be consistent (the verification cases use N, mm, MPa, t/mm^3
or N, m, Pa, kg/m^3 as stated per case).

Element node orderings follow the CalculiX manual (Abaqus convention):
  C3D20(R): corners 1-4 bottom (counter-clockwise), 5-8 top; mid-side 9-12 bottom edges,
            13-16 top edges, 17-20 vertical edges.  Faces: S1 bottom (1234), S2 top (5678),
            S3 (1265), S4 (2376), S5 (3487), S6 (4158).
  S8R / CPS8: corners 1-4, mid-side 5 (1-2), 6 (2-3), 7 (3-4), 8 (4-1).

Adapted from the E8-S subscale tools (tools/fea/ccx.py): the C3D10 gmsh pipeline is kept and
extended with structured hex/shell meshes, composite shell sections, frequency and buckling steps.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ENV = Path.home() / "tools" / "foamenv.sh"     # micromamba env holding ccx 2.23 and gmsh
CACHE = Path(__file__).resolve().parent / ".cache"
NCPU = int(os.environ.get("FEA_NCPU", "6"))      # project rule: FEA uses at most 6 cores (FEA_NCPU lowers it)


# ----------------------------------------------------------------------------- meshes
@dataclass
class Mesh:
    nodes: np.ndarray                 # (n, 3) coordinates
    elems: np.ndarray                 # (m, k) 1-based node ids
    etype: str                        # C3D20R, S8R, CPS8, C3D10, ...
    lattice: dict = field(default_factory=dict)   # (i, j[, k]) -> node id for structured meshes
    shape: tuple = ()                 # (nx, ny[, nz]) element counts for structured meshes

    @property
    def ids(self):
        return np.arange(1, len(self.nodes) + 1)

    def nid(self, *ijk):
        return self.lattice[tuple(ijk)]

    def xyz(self, nid):
        return self.nodes[nid - 1]

    def near(self, p, tol=1e-9):
        d = np.linalg.norm(self.nodes - np.asarray(p, float), axis=1)
        k = int(np.argmin(d))
        if d[k] > tol:
            raise ValueError(f"no node within {tol} of {p} (closest {d[k]:.3g})")
        return k + 1

    def select(self, fn):
        """Node ids whose coordinates satisfy fn(x, y, z) (vectorised)."""
        x, y, z = self.nodes.T
        return self.ids[fn(x, y, z)]


def quad8_block(mapfn, nx: int, ny: int, etype="S8R") -> Mesh:
    """Structured 8-node quadrilateral mesh of the unit square mapped by mapfn(u, v) -> (x, y, z)."""
    lat, pts = {}, []
    for j in range(2 * ny + 1):
        for i in range(2 * nx + 1):
            if i % 2 and j % 2:
                continue
            pts.append(mapfn(i / (2 * nx), j / (2 * ny)))
            lat[(i, j)] = len(pts)
    el = []
    for ey in range(ny):
        for ex in range(nx):
            i, j = 2 * ex, 2 * ey
            c = [lat[(i, j)], lat[(i + 2, j)], lat[(i + 2, j + 2)], lat[(i, j + 2)]]
            m = [lat[(i + 1, j)], lat[(i + 2, j + 1)], lat[(i + 1, j + 2)], lat[(i, j + 1)]]
            el.append(c + m)
    return Mesh(np.array(pts, float), np.array(el, int), etype, lat, (nx, ny))


def hex20_block(mapfn, nx: int, ny: int, nz: int, etype="C3D20R") -> Mesh:
    """Structured 20-node hexahedral mesh of the unit cube mapped by mapfn(u, v, w) -> (x, y, z).

    nz may be a list of layer boundaries in w (0..1) to make graded/multi-material layers."""
    wz = np.linspace(0, 1, nz + 1) if np.isscalar(nz) else np.asarray(nz, float)
    nz = len(wz) - 1
    wfine = np.empty(2 * nz + 1)
    wfine[0::2] = wz
    wfine[1::2] = 0.5 * (wz[:-1] + wz[1:])
    lat, pts = {}, []
    for k in range(2 * nz + 1):
        for j in range(2 * ny + 1):
            for i in range(2 * nx + 1):
                if (i % 2) + (j % 2) + (k % 2) >= 2:
                    continue
                pts.append(mapfn(i / (2 * nx), j / (2 * ny), wfine[k]))
                lat[(i, j, k)] = len(pts)
    el = []
    for ez in range(nz):
        for ey in range(ny):
            for ex in range(nx):
                i, j, k = 2 * ex, 2 * ey, 2 * ez
                L = lambda a, b, c: lat[(i + a, j + b, k + c)]
                corners = [L(0, 0, 0), L(2, 0, 0), L(2, 2, 0), L(0, 2, 0), L(0, 0, 2), L(2, 0, 2), L(2, 2, 2), L(0, 2, 2)]
                mids = [L(1, 0, 0), L(2, 1, 0), L(1, 2, 0), L(0, 1, 0), L(1, 0, 2), L(2, 1, 2), L(1, 2, 2), L(0, 1, 2),
                        L(0, 0, 1), L(2, 0, 1), L(2, 2, 1), L(0, 2, 1)]
                el.append(corners + mids)
    return Mesh(np.array(pts, float), np.array(el, int), etype, lat, (nx, ny, nz))


def gmsh_mesh(geo: str, work: Path, name="mesh") -> dict:
    """Run gmsh on a .geo script (which must Save name.inp); returns read_inp_mesh() of the result."""
    work.mkdir(parents=True, exist_ok=True)
    (work / f"{name}.geo").write_text(geo)
    (work / f"{name}.inp").unlink(missing_ok=True)
    subprocess.run(["bash", "-c", f"source {ENV} >/dev/null 2>&1 && cd {work} && gmsh {name}.geo -nt {NCPU} -v 1 -0 > log.gmsh 2>&1"])
    if not (work / f"{name}.inp").exists():          # high-order optimisation warnings return a non-zero code; the mesh is kept
        raise RuntimeError(f"gmsh produced no mesh in {work}")
    return read_inp_mesh(work / f"{name}.inp")


def read_inp_mesh(path: Path) -> dict:
    """gmsh .inp -> {'nodes': (n,3), 'blocks': {elset: (type, conn)}, 'groups': {physical name: [(type, conn)]}}.

    Node ids are renumbered 1..n in file order; connectivity uses the new ids."""
    txt = path.read_text()
    nblock = re.search(r"\*NODE[^\n]*\n(.*?)\n\*", txt, re.S).group(1)
    nd = np.array([[float(v) for v in l.split(",")[:4]] for l in nblock.strip().splitlines()])
    ids = nd[:, 0].astype(int)
    remap = np.zeros(ids.max() + 1, int)
    remap[ids] = np.arange(1, len(ids) + 1)
    blocks, byid = {}, {}
    for typ, name, blk in re.findall(r"\*ELEMENT, type=(\w+), ELSET=(\w+)[^\n]*\n(.*?)(?=\n\*|\Z)", txt, re.S):
        rows = [[int(v) for v in l.replace(" ", "").rstrip(",").split(",")] for l in blk.strip().splitlines() if l.strip()]
        arr = np.array(rows)
        blocks[name] = (typ, remap[arr[:, 1:]])
        for r in arr:
            byid[int(r[0])] = (typ, remap[r[1:]])
    groups = {}
    for name, blk in re.findall(r"\*ELSET,\s*ELSET=(\w+)[^\n]*\n(.*?)(?=\n\*|\Z)", txt, re.S):
        members = [m.strip() for m in blk.replace("\n", ",").split(",") if m.strip()]
        if all(m.isdigit() for m in members):          # element ids
            by_type = {}
            for m in members:
                t, c = byid[int(m)]
                by_type.setdefault(t, []).append(c)
            groups[name] = [(t, np.array(c)) for t, c in by_type.items()]
        else:
            groups[name] = [blocks[m] for m in members if m in blocks]
    return {"nodes": nd[:, 1:], "blocks": blocks, "groups": groups}


# ----------------------------------------------------------------------------- deck writing
def deck_mesh(meshes: list[tuple[Mesh, str]], offset_nodes=True) -> str:
    """*NODE / *ELEMENT text for one or several meshes (elset names given). Single mesh: ids as is."""
    s = ["*NODE, NSET=NALL"]
    nofs, eofs = 0, 0
    for m, _ in meshes:
        s += [f"{i + nofs},{p[0]:.10g},{p[1]:.10g},{p[2]:.10g}" for i, p in zip(m.ids, m.nodes)]
        nofs += len(m.nodes) if offset_nodes else 0
    nofs = 0
    for m, eset in meshes:
        s.append(f"*ELEMENT, TYPE={m.etype}, ELSET={eset}")
        for k, e in enumerate(m.elems, 1):
            vals = [str(k + eofs)] + [str(n + nofs) for n in e]
            # at most 16 entries per line (continuation lines end with a comma)
            s.append(",\n".join(",".join(vals[i:i + 16]) for i in range(0, len(vals), 16)))
        eofs += len(m.elems)
        nofs += len(m.nodes) if offset_nodes else 0
    return "\n".join(s) + "\n"


def nset(name: str, ids) -> str:
    ids = sorted(set(int(i) for i in ids))
    rows = [",".join(map(str, ids[i:i + 12])) for i in range(0, len(ids), 12)]
    return f"*NSET, NSET={name}\n" + "\n".join(rows) + "\n"


def elset(name: str, ids) -> str:
    ids = sorted(set(int(i) for i in ids))
    rows = [",".join(map(str, ids[i:i + 12])) for i in range(0, len(ids), 12)]
    return f"*ELSET, ELSET={name}\n" + "\n".join(rows) + "\n"


def cload(loads: dict) -> str:
    """loads: {node: (fx, fy, fz)} -> *CLOAD lines."""
    s = ["*CLOAD"]
    for n, f in loads.items():
        for k in range(3):
            if abs(f[k]) > 0:
                s.append(f"{n},{k + 1},{f[k]:.10e}")
    return "\n".join(s) + "\n"


def iso_material(name, E, nu, rho=None) -> str:
    s = f"*MATERIAL, NAME={name}\n*ELASTIC\n{E:.8g},{nu:.6g}\n"
    if rho is not None:
        s += f"*DENSITY\n{rho:.8g}\n"
    return s


def ortho_material(name, E1, E2, E3, nu12, nu13, nu23, G12, G13, G23, rho=None) -> str:
    s = (f"*MATERIAL, NAME={name}\n*ELASTIC, TYPE=ENGINEERING CONSTANTS\n"
         f"{E1:.8g},{E2:.8g},{E3:.8g},{nu12:.6g},{nu13:.6g},{nu23:.6g},{G12:.8g},{G13:.8g}\n{G23:.8g}\n")
    if rho is not None:
        s += f"*DENSITY\n{rho:.8g}\n"
    return s


def orientation(name, angle_deg, axis=(0, 0, 1)) -> str:
    """Rectangular material system rotated by angle about the global z axis (shell normal for xy plates)."""
    a = np.radians(angle_deg)
    if tuple(axis) != (0, 0, 1):
        raise NotImplementedError
    return f"*ORIENTATION, NAME={name}, SYSTEM=RECTANGULAR\n{np.cos(a):.12f},{np.sin(a):.12f},0.,{-np.sin(a):.12f},{np.cos(a):.12f},0.\n"


# ----------------------------------------------------------------------------- run + read
def run(deck: str, work: Path, name="job", threads=NCPU, timeout=3600) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    (work / f"{name}.inp").write_text(deck)
    for ext in ("frd", "dat", "sta", "cvg"):
        (work / f"{name}.{ext}").unlink(missing_ok=True)
    env = f"OMP_NUM_THREADS={threads} CCX_NPROC_EQUATION_SOLVER={threads} CCX_NPROC_RESULTS={threads}"
    r = subprocess.run(["bash", "-c", f"source {ENV} >/dev/null 2>&1 && cd {work} && {env} ccx -i {name} > log.{name} 2>&1"],
                       timeout=timeout)
    log = (work / f"log.{name}").read_text(errors="ignore")
    if r.returncode or "*ERROR" in log:
        err = [l for l in log.splitlines() if "ERROR" in l][:5]
        raise RuntimeError(f"ccx failed in {work}/{name}: {err}")
    return work / name


def read_frd(path: Path) -> list[dict]:
    """All nodal result blocks: [{'name': 'DISP', 'step': k, 'value': v, 'data': {nid: array}}]."""
    blocks, cur, value, step = [], None, 0.0, 0
    with open(path) as fh:
        for line in fh:
            if line.startswith("    1PSTEP"):
                step = int(line.split()[2]) if len(line.split()) > 2 else step + 1
            elif line.startswith("  100C"):
                try:
                    value = float(line[12:24])
                except ValueError:
                    value = 0.0
            elif line.startswith(" -4"):
                cur = dict(name=line.split()[1], step=step, value=value, data={})
                blocks.append(cur)
            elif line.startswith(" -3"):
                cur = None
            elif cur is not None and line.startswith(" -1"):
                nid = int(line[3:13])
                n = (len(line.rstrip("\n")) - 13) // 12
                cur["data"][nid] = np.array([float(line[13 + 12 * k:25 + 12 * k]) for k in range(n)])
    return blocks


def frd_field(blocks, name, step_index=-1) -> dict:
    sel = [b for b in blocks if b["name"].startswith(name)]
    return sel[step_index]["data"] if sel else {}


def frd_fields(blocks, name) -> list[dict]:
    return [b for b in blocks if b["name"].startswith(name)]


def read_eigen(dat: Path) -> np.ndarray:
    """Frequencies (Hz) from a *FREQUENCY step or buckling factors from a *BUCKLE step (.dat)."""
    txt = Path(dat).read_text()
    if "B U C K L I N G" in txt:
        blk = txt.split("B U C K L I N G")[1]
        rows = re.findall(r"^\s+(\d+)\s+([-\d.E+]+)\s*$", blk, re.M)
        return np.array([float(v) for _, v in rows])
    blk = txt.split("E I G E N V A L U E   O U T P U T")[1].split("P A R T I C I P A T I O N")[0]
    rows = re.findall(r"^\s+(\d+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s*$", blk, re.M)
    return np.array([float(r[3]) for r in rows])


def read_reaction_totals(dat: Path) -> list[np.ndarray]:
    txt = Path(dat).read_text()
    out = []
    for m in re.finditer(r"total force[^\n]*\n\s*\n?\s*([-\dE.+]+)\s+([-\dE.+]+)\s+([-\dE.+]+)", txt, re.I):
        out.append(np.array([float(m.group(i)) for i in (1, 2, 3)]))
    return out


def read_el_print(dat: Path, key="stresses") -> list[np.ndarray]:
    """Integration point rows from *EL PRINT blocks: [elem, ip, values...] arrays per block."""
    txt = Path(dat).read_text()
    out = []
    for blk in re.split(r"\n\s*(?=" + key + r"\b)", txt)[1:]:
        rows = []
        for line in blk.splitlines()[1:]:
            p = line.split()
            if not p:
                if rows:
                    break
                continue
            vals = []
            for v in p:
                try:
                    vals.append(float(v))
                except ValueError:
                    break                           # trailing orientation / material label
            if len(vals) < 3:
                break
            rows.append(vals)
        out.append(np.array(rows))
    return out


def von_mises(S):
    S = np.atleast_2d(S)
    sxx, syy, szz, sxy, syz, szx = S[:, :6].T
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * (sxy**2 + syz**2 + szx**2))


# ----------------------------------------------------------------------------- consistent edge loads
def edge_load_quadratic(p_xyz: np.ndarray, traction_fn, ngauss=4) -> list[np.ndarray]:
    """Consistent nodal forces of a quadratic (3-node) edge with a traction vector function.

    p_xyz: (3, 3) end, mid, end coordinates; traction_fn(x, n) -> force/area*thickness (force per length)
    given point x and unit in-plane outward normal n (edge assumed in the xy plane, traversed so that the
    outward normal is the tangent rotated by -90 deg)."""
    g, w = np.polynomial.legendre.leggauss(ngauss)
    F = [np.zeros(3) for _ in range(3)]
    for s, ws in zip(g, w):
        N = np.array([0.5 * s * (s - 1), 1 - s**2, 0.5 * s * (s + 1)])
        dN = np.array([s - 0.5, -2 * s, s + 0.5])
        x = N[0] * p_xyz[0] + N[1] * p_xyz[1] + N[2] * p_xyz[2]
        t = dN[0] * p_xyz[0] + dN[1] * p_xyz[1] + dN[2] * p_xyz[2]
        J = np.linalg.norm(t)
        n = np.array([t[1], -t[0], 0.0]) / J
        q = np.asarray(traction_fn(x, n))
        for a in range(3):
            F[a] += N[a] * q * J * ws
    return F


def merge(meshes: list[Mesh], tol=1e-6) -> tuple[Mesh, list[np.ndarray]]:
    """Merge meshes of one element type, fusing coincident nodes. Returns (mesh, element-id arrays per input)."""
    P = np.vstack([m.nodes for m in meshes])
    key = np.round(P / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    order = np.argsort(first)                       # keep first-appearance order
    newid = np.empty(len(order), int)
    newid[order] = np.arange(1, len(order) + 1)
    nodes = P[first[order]]
    elems, ranges, nofs, eofs = [], [], 0, 0
    for m in meshes:
        elems.append(newid[inv[m.elems - 1 + nofs]])
        ranges.append(np.arange(eofs + 1, eofs + len(m.elems) + 1))
        nofs += len(m.nodes)
        eofs += len(m.elems)
    return Mesh(nodes, np.vstack(elems), meshes[0].etype), ranges


def mesh_from_gmsh(g: dict, group: str) -> Mesh:
    """Mesh object for one physical group of a read_inp_mesh() result (single element type)."""
    blocks = g["groups"][group]
    etype = blocks[0][0]
    return Mesh(g["nodes"], np.vstack([b[1] for b in blocks]), etype)


# ----------------------------------------------------------------------------- solid parts (C3D10) from build123d
TET_FACES = ((0, 1, 2, 4, 5, 6), (0, 1, 3, 4, 8, 7), (1, 2, 3, 5, 9, 8), (0, 2, 3, 6, 9, 7))


def mesh_solid(solid, work: Path, hmax: float, hmin: float, refine=None, straight=False) -> Mesh:
    """build123d solid -> STEP -> gmsh second-order tetrahedra (C3D10). refine: list of (x, y, z, r, h) balls
    with a local element size h inside radius r (stress raisers)."""
    from build123d import export_step
    work.mkdir(parents=True, exist_ok=True)
    export_step(solid, str(work / "part.step"))
    fields = ""
    if refine:
        ids = []
        for k, (x, y, z, r, h) in enumerate(refine, 1):
            fields += (f"Field[{k}] = Ball;\nField[{k}].Radius = {r};\nField[{k}].XCenter = {x};\nField[{k}].YCenter = {y};\n"
                       f"Field[{k}].ZCenter = {z};\nField[{k}].VIn = {h};\nField[{k}].VOut = {hmax};\n")
            ids.append(k)
        n = len(ids) + 1
        fields += f"Field[{n}] = Min;\nField[{n}].FieldsList = {{{','.join(map(str, ids))}}};\nBackground Field = {n};\n"
    geo = f"""SetFactory("OpenCASCADE");
Merge "part.step";
v() = Volume{{:}};
If (#v() > 1)
  BooleanFragments{{ Volume{{:}}; Delete; }}{{ }}
EndIf
Mesh.CharacteristicLengthMax = {hmax};
Mesh.CharacteristicLengthMin = {hmin};
Mesh.CharacteristicLengthFromCurvature = 1;
Mesh.MinimumElementsPerTwoPi = 10;
Mesh.MeshSizeExtendFromBoundary = 0;
{fields}Mesh.ElementOrder = 2;
Mesh.SecondOrderLinear = {1 if straight else 0};
Mesh.HighOrderOptimize = {0 if straight else 1};
Mesh.Optimize = 1;
Physical Volume("PART") = Volume{{:}};
Mesh 3;
Save "mesh.inp";
"""
    g = gmsh_mesh(geo, work, "mesh")
    part = mesh_from_gmsh(g, "PART")
    used = np.unique(part.elems)
    remap = np.zeros(len(g["nodes"]) + 1, int)
    remap[used] = np.arange(1, len(used) + 1)
    return Mesh(g["nodes"][used - 1], remap[part.elems], "C3D10")


def boundary_faces(m: Mesh):
    allf = np.concatenate([m.elems[:, list(f)] for f in TET_FACES])
    key = np.sort(allf[:, :3], axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bf = allf[cnt[inv.ravel()] == 1]
    # orient outward: compare with the centroid of the owning element
    own = np.concatenate([np.arange(len(m.elems))] * 4)[cnt[inv.ravel()] == 1]
    P = m.nodes
    c = P[bf[:, :3] - 1]
    nrm = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    ec = P[m.elems[own, :4] - 1].mean(axis=1)
    flip = np.einsum("ij,ij->i", nrm, c.mean(axis=1) - ec) < 0
    bf[flip] = bf[flip][:, [0, 2, 1, 5, 4, 3]]
    return bf


def face_props(m: Mesh, faces):
    P = m.nodes
    c = P[faces[:, :3] - 1]
    nrm = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    return c.mean(axis=1), nrm / (2 * area[:, None]), area


def face_loads(m: Mesh, faces, trac):
    """Consistent nodal loads of T6 faces with per-face traction vectors trac (force/area): mid-side nodes 1/3 each."""
    _, _, area = face_props(m, faces)
    loads = {}
    for f_, a, t in zip(faces, area, trac):
        for n in f_[3:]:
            loads[int(n)] = loads.get(int(n), 0) + np.asarray(t) * a / 3
    return loads


def solve_solid(m: Mesh, E, nu, fixed_nodes, loads: dict, work: Path, name="part", fixed_dofs="1,3"):
    deck = (deck_mesh([(m, "E")]) + nset("FIX", fixed_nodes) + iso_material("M", E, nu) +
            f"*SOLID SECTION, ELSET=E, MATERIAL=M\n*STEP\n*STATIC\n*BOUNDARY\nFIX,{fixed_dofs}\n" + cload(loads) +
            "*NODE FILE\nU\n*EL FILE\nS\n*NODE PRINT, NSET=FIX, TOTALS=ONLY\nRF\n*END STEP\n")
    p = run(deck, work, name)
    b = read_frd(p.with_suffix(".frd"))
    U, S = frd_field(b, "DISP"), frd_field(b, "STRESS")
    ids = np.array(sorted(S))
    vm = von_mises(np.array([S[i][:6] for i in ids]))
    Ua = np.array([U[i][:3] for i in ids])
    R = read_reaction_totals(p.with_suffix(".dat"))
    return dict(ids=ids, vm=vm, U=Ua, reaction=R[0].tolist() if R else None)
