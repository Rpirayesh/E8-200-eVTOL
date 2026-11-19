"""3-D frame finite-element solver (6 DOF per node) for the global airframe model.

Element: 2-node beam, Euler-Bernoulli or Timoshenko (shear-flexible when shear areas are given),
uncoupled axial / torsion / two bending planes about the section principal axes.
Mass: consistent (default) or lumped.  Geometric stiffness for linear (Euler) buckling.
Solutions: constrained static, free-free static with inertia relief, modal (shift-invert Lanczos),
linear buckling.

Units: SI (N, m, Pa, kg).  Verified in validation/fea/ (cases B1-B8).

Adapted from the E8-S subscale frame solver (tools/fea/frame.py): Timoshenko shear, consistent mass,
rigid-body-mode inertia relief (valid for consistent mass), geometric stiffness and non-circular
section stress recovery were added.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla


# ----------------------------------------------------------------------------- sections
@dataclass
class Section:
    A: float                 # m^2 (axial-stiffness weighted area for composites: A = EA/E)
    Iy: float                # m^4 bending about local y (deflection w along local z)
    Iz: float                # m^4 bending about local z (deflection v along local y)
    J: float                 # m^4 torsion constant (St Venant / Bredt)
    E: float                 # Pa reference modulus
    G: float                 # Pa shear modulus
    rho: float               # kg/m^3 (mass per length = rho*A unless m_per_len is set)
    cy: float = 0.0          # extreme fibre distance along local y (for Mz)
    cz: float = 0.0          # extreme fibre distance along local z (for My)
    Ay: float | None = None  # shear area for shear along local y (None -> Euler-Bernoulli)
    Az: float | None = None
    tau_per_T: float = 0.0   # max torsional shear stress per unit torque (1/m^3)
    round: bool = False      # resultant bending moment is used (axisymmetric section)
    m_per_len: float | None = None
    name: str = ""
    material: str = ""
    Av: float | None = None  # area carrying the local-z shear for stress recovery (spar webs); None -> not reported
    kind: str = ""           # tube / rect_tube / cap_web / rigid / props
    meta: dict = field(default_factory=dict)

    @property
    def mass_per_length(self):
        return self.m_per_len if self.m_per_len is not None else self.rho * self.A

    @classmethod
    def pipe(cls, ro, ri, E, G, rho, name="", material="", shear=True):
        A = np.pi * (ro**2 - ri**2)
        I = np.pi / 4 * (ro**4 - ri**4)
        J = 2 * I
        As = 0.5 * A if shear else None          # thin-walled circular tube shear coefficient k = 0.5
        return cls(A, I, I, J, E, G, rho, ro, ro, As, As, ro / J, True, None, name, material)

    @classmethod
    def rect_tube(cls, b, h, t_web, t_flange, E, G, rho, name="", material="", shear=True):
        """Thin-walled rectangular tube, outer width b (local y) and height h (local z); Bredt torsion."""
        bi, hi = b - 2 * t_web, h - 2 * t_flange
        A = b * h - bi * hi
        Iy = (b * h**3 - bi * hi**3) / 12
        Iz = (h * b**3 - hi * bi**3) / 12
        bm, hm = b - t_web, h - t_flange                      # mid-line dimensions
        Am = bm * hm
        J = 4 * Am**2 / (2 * bm / t_flange + 2 * hm / t_web)
        tmin = min(t_web, t_flange)
        Az = 2 * hi * t_web if shear else None                 # webs carry vertical shear
        Ay = 2 * bi * t_flange if shear else None
        return cls(A, Iy, Iz, J, E, G, rho, b / 2, h / 2, Ay, Az, 1 / (2 * Am * tmin), False, None, name, material)

    @classmethod
    def solid_rect(cls, b, h, E, G, rho, name="", material="", shear=True):
        A = b * h
        a, c = max(b, h) / 2, min(b, h) / 2
        J = a * c**3 * (16 / 3 - 3.36 * c / a * (1 - c**4 / (12 * a**4)))   # Roark
        As = 5 / 6 * A if shear else None
        return cls(A, b * h**3 / 12, h * b**3 / 12, J, E, G, rho, b / 2, h / 2, As, As, 0.0, False, None, name, material)

    @classmethod
    def pin(cls, name="pinned link", scale=1.0):
        """Stiff link with a spherical joint at its second node (all three rotations released there)."""
        s = cls.rigid(name, scale)
        s.meta = {"release": [9, 10, 11]}
        return s

    @classmethod
    def rigid(cls, name="rigid link", scale=1.0):
        """Stiff massless connector (fittings, ribs) - stiffness ~1e3 x a typical boom."""
        return cls(A=1e-2 * scale, Iy=1e-4 * scale, Iz=1e-4 * scale, J=2e-4 * scale, E=7e10, G=2.7e10, rho=0.0,
                   cy=0.05, cz=0.05, name=name)


# ----------------------------------------------------------------------------- model
@dataclass
class Frame:
    nodes: list = field(default_factory=list)
    elems: list = field(default_factory=list)      # (n1, n2, Section, vref, tag)
    masses: dict = field(default_factory=dict)     # node -> (m, Ixx, Iyy, Izz) about the node, global axes
    lumped: bool = False

    def node(self, xyz) -> int:
        self.nodes.append(np.asarray(xyz, float))
        return len(self.nodes) - 1

    def find(self, xyz, tol=1e-6):
        for i, p in enumerate(self.nodes):
            if np.linalg.norm(p - np.asarray(xyz)) < tol:
                return i
        return self.node(xyz)

    def nearest(self, xyz, among=None):
        idx = np.arange(len(self.nodes)) if among is None else np.asarray(among)
        P = np.array([self.nodes[i] for i in idx])
        return int(idx[np.argmin(np.linalg.norm(P - np.asarray(xyz), axis=1))])

    def beam(self, a: int, b: int, sec: Section, n: int = 1, vref=(0, 0, 1), tag="") -> list[int]:
        """Beam from node a to b split into n elements; vref sets local z (in the plane of ex and vref)."""
        pa, pb = self.nodes[a], self.nodes[b]
        if np.linalg.norm(pb - pa) < 1e-9:
            raise ValueError(f"zero-length beam between nodes {a} and {b} ({tag})")
        prev, chain = a, [a]
        for k in range(1, n + 1):
            nxt = b if k == n else self.node(pa + (pb - pa) * k / n)
            self.elems.append((prev, nxt, sec, np.asarray(vref, float), tag))
            prev = nxt
            chain.append(nxt)
        return chain

    def add_mass(self, n: int, m: float, I=(0.0, 0.0, 0.0)):
        old = self.masses.get(n, (0.0, 0.0, 0.0, 0.0))
        self.masses[n] = (old[0] + m, old[1] + I[0], old[2] + I[1], old[3] + I[2])

    @property
    def ndof(self):
        return 6 * len(self.nodes)

    # ------------------------------------------------------------------ element matrices
    @staticmethod
    def _T(p1, p2, vref):
        ex = (p2 - p1) / np.linalg.norm(p2 - p1)
        v = np.asarray(vref, float)
        if abs(np.dot(v / np.linalg.norm(v), ex)) > 0.99:
            v = np.array([0, 1.0, 0]) if abs(ex[1]) < 0.9 else np.array([1.0, 0, 0])
        ez = v - np.dot(v, ex) * ex
        ez /= np.linalg.norm(ez)
        ey = np.cross(ez, ex)
        R = np.vstack([ex, ey, ez])
        T = np.zeros((12, 12))
        for i in range(4):
            T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = R
        return T, R

    @staticmethod
    def _k_local(L, s: Section):
        E, G, A, Iy, Iz, J = s.E, s.G, s.A, s.Iy, s.Iz, s.J
        k = np.zeros((12, 12))
        a = E * A / L
        k[0, 0] = k[6, 6] = a
        k[0, 6] = k[6, 0] = -a
        t = G * J / L
        k[3, 3] = k[9, 9] = t
        k[3, 9] = k[9, 3] = -t
        # (I, translation dof, rotation dof, sign, shear area)
        for (I, i1, i2, sgn, As) in ((Iz, 1, 5, 1, s.Ay), (Iy, 2, 4, -1, s.Az)):
            phi = 12 * E * I / (G * As * L**2) if As else 0.0
            d = 1 + phi
            c1, c2 = 12 * E * I / L**3 / d, 6 * E * I / L**2 / d
            c3, c4 = (4 + phi) * E * I / L / d, (2 - phi) * E * I / L / d
            j1, j2 = i1 + 6, i2 + 6
            k[i1, i1] = k[j1, j1] = c1
            k[i1, j1] = k[j1, i1] = -c1
            k[i1, i2] = k[i2, i1] = sgn * c2
            k[i1, j2] = k[j2, i1] = sgn * c2
            k[j1, i2] = k[i2, j1] = -sgn * c2
            k[j1, j2] = k[j2, j1] = -sgn * c2
            k[i2, i2] = k[j2, j2] = c3
            k[i2, j2] = k[j2, i2] = c4
        rel = s.meta.get("release") if s.meta else None
        if rel:                                          # end releases (e.g. pins): static condensation
            rel = list(rel)
            keep = [i for i in range(12) if i not in rel]
            kc = k[np.ix_(keep, keep)] - k[np.ix_(keep, rel)] @ np.linalg.solve(k[np.ix_(rel, rel)], k[np.ix_(rel, keep)])
            k = np.zeros((12, 12))
            k[np.ix_(keep, keep)] = kc
        return k

    @staticmethod
    def _m_local(L, s: Section, lumped=False):
        m = s.mass_per_length * L
        Ip = (s.Iy + s.Iz) / s.A * m / L if s.A else 0.0      # polar mass moment per length
        M = np.zeros((12, 12))
        if lumped:
            for i in (0, 1, 2, 6, 7, 8):
                M[i, i] = m / 2
            for i in (3, 9):
                M[i, i] = Ip * L / 2
            for i in (4, 5, 10, 11):
                M[i, i] = m / 2 * L**2 / 12 * 1e-3 + 1e-12   # small rotary term keeps M positive definite
            return M
        c = m / 420.0
        M[0, 0] = M[6, 6] = 140 * c
        M[0, 6] = M[6, 0] = 70 * c
        M[3, 3] = M[9, 9] = Ip * L / 3
        M[3, 9] = M[9, 3] = Ip * L / 6
        for (i1, i2, sgn) in ((1, 5, 1), (2, 4, -1)):
            j1, j2 = i1 + 6, i2 + 6
            M[i1, i1] = M[j1, j1] = 156 * c
            M[i1, j1] = M[j1, i1] = 54 * c
            M[i1, i2] = M[i2, i1] = sgn * 22 * L * c
            M[j1, j2] = M[j2, j1] = -sgn * 22 * L * c
            M[i1, j2] = M[j2, i1] = -sgn * 13 * L * c
            M[j1, i2] = M[i2, j1] = sgn * 13 * L * c
            M[i2, i2] = M[j2, j2] = 4 * L**2 * c
            M[i2, j2] = M[j2, i2] = -3 * L**2 * c
        return M

    @staticmethod
    def _kg_local(L, P):
        """Geometric stiffness for axial force P (tension positive)."""
        k = np.zeros((12, 12))
        c = P / (30 * L)
        for (i1, i2, sgn) in ((1, 5, 1), (2, 4, -1)):
            j1, j2 = i1 + 6, i2 + 6
            k[i1, i1] = k[j1, j1] = 36 * c
            k[i1, j1] = k[j1, i1] = -36 * c
            k[i1, i2] = k[i2, i1] = sgn * 3 * L * c
            k[i1, j2] = k[j2, i1] = sgn * 3 * L * c
            k[j1, i2] = k[i2, j1] = -sgn * 3 * L * c
            k[j1, j2] = k[j2, j1] = -sgn * 3 * L * c
            k[i2, i2] = k[j2, j2] = 4 * L**2 * c
            k[i2, j2] = k[j2, i2] = -L**2 * c
        return k

    def _assemble(self, fn):
        rows, cols, vals = [], [], []
        for e, (a, b, s, vref, _) in enumerate(self.elems):
            p1, p2 = self.nodes[a], self.nodes[b]
            L = np.linalg.norm(p2 - p1)
            T, _ = self._T(p1, p2, vref)
            ke = T.T @ fn(e, L, s) @ T
            dofs = np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]
            rows.append(np.repeat(dofs, 12))
            cols.append(np.tile(dofs, 12))
            vals.append(ke.ravel())
        n = self.ndof
        return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()

    def assemble(self, with_mass=True):
        K = self._assemble(lambda e, L, s: self._k_local(L, s))
        if not with_mass:
            return K, None
        M = self._assemble(lambda e, L, s: self._m_local(L, s, self.lumped)).tolil()
        for nd, (m, Ix, Iy, Iz) in self.masses.items():
            for k in range(3):
                M[6 * nd + k, 6 * nd + k] += m
            for k, I in enumerate((Ix, Iy, Iz)):
                M[6 * nd + 3 + k, 6 * nd + 3 + k] += I
        return K, M.tocsr()

    # ------------------------------------------------------------------ rigid body
    def rigid_modes(self, r0=np.zeros(3)):
        n = len(self.nodes)
        Phi = np.zeros((6 * n, 6))
        for i, p in enumerate(self.nodes):
            r = p - r0
            Phi[6 * i:6 * i + 3, 0:3] = np.eye(3)
            # rotation theta: u = theta x r
            Phi[6 * i:6 * i + 3, 3:6] = np.array([[0, r[2], -r[1]], [-r[2], 0, r[0]], [r[1], -r[0], 0]])
            Phi[6 * i + 3:6 * i + 6, 3:6] = np.eye(3)
        return Phi

    def mass_properties(self, M=None):
        if M is None:
            _, M = self.assemble()
        Phi = self.rigid_modes()
        Mrr = Phi.T @ (M @ Phi)
        m = Mrr[0, 0]
        S = Mrr[0:3, 3:6]
        c = np.array([-S[2, 1], -S[0, 2], -S[1, 0]]) / m
        I0 = Mrr[3:6, 3:6]
        Icg = I0 - m * (np.dot(c, c) * np.eye(3) - np.outer(c, c))
        return m, c, Icg

    # ------------------------------------------------------------------ solutions
    def solve_static(self, F, fixed_dofs):
        K, _ = self.assemble(with_mass=False)
        n = K.shape[0]
        free = np.setdiff1d(np.arange(n), fixed_dofs)
        u = np.zeros(n)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), F[free])
        return u, K @ u - F

    def solve_inertia_relief(self, F: np.ndarray, support: int, gravity=None):
        """Free-free static response: applied loads F (plus optional gravity vector, m/s^2) are balanced
        by rigid-body inertia (D'Alembert) loads -M Phi a; one node is held only to remove the
        rigid-body null space, its reaction is ~0 when balanced (returned as a check)."""
        K, M = self.assemble()
        F = F.copy()
        if gravity is not None:
            Phi = self.rigid_modes()
            F += M @ (Phi[:, 0:3] @ np.asarray(gravity, float))
        m, cg, Icg = self.mass_properties(M)
        Phi = self.rigid_modes(cg)
        Mrr = Phi.T @ (M @ Phi)
        acc = np.linalg.solve(Mrr, Phi.T @ F)       # [a_cg (m/s^2), alpha (rad/s^2)] about the cg
        Fi = F - M @ (Phi @ acc)
        fixed = np.arange(6 * support, 6 * support + 6)
        free = np.setdiff1d(np.arange(self.ndof), fixed)
        u = np.zeros(self.ndof)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), Fi[free])
        R = K @ u - Fi
        return u, dict(accel=acc[:3], alpha=acc[3:], reaction=R[fixed], cg=cg, mass=m, F_balanced=Fi)

    def modes(self, n_modes=12, fixed_dofs=(), shift_hz=0.5):
        """Natural frequencies (Hz) and mode shapes by shift-invert Lanczos (negative shift handles rigid modes)."""
        K, M = self.assemble()
        n = K.shape[0]
        free = np.setdiff1d(np.arange(n), np.asarray(fixed_dofs, int))
        Kf, Mf = K[free][:, free].tocsc(), M[free][:, free].tocsc()
        sigma = -(2 * np.pi * shift_hz) ** 2
        k = min(n_modes + 6, len(free) - 2)
        w2, V = spla.eigsh(Kf, k=k, M=Mf, sigma=sigma, which="LM")
        order = np.argsort(w2)
        w2, V = w2[order], V[:, order]
        f = np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)
        full = np.zeros((n, V.shape[1]))
        full[free] = V
        return f, full

    def buckling(self, F, fixed_dofs, n_modes=4):
        """Linear buckling load factors for the reference load F: (K + lambda Kg(F)) phi = 0."""
        u, _ = self.solve_static(F, fixed_dofs)
        P = [-fl[0] for fl in self.element_forces(u)]          # axial force, tension positive
        Kg = self._assemble(lambda e, L, s: self._kg_local(L, P[e]))
        K, _ = self.assemble(with_mass=False)
        free = np.setdiff1d(np.arange(self.ndof), fixed_dofs)
        Kf, Gf = K[free][:, free].toarray(), Kg[free][:, free].toarray()
        mu, V = sla.eigh(-Gf, Kf)                              # mu = 1/lambda
        pos = mu > 1e-12
        lam = np.sort(1 / mu[pos])
        return lam[:n_modes]

    def element_forces(self, u):
        """Local end forces per element [N1, Vy1, Vz1, T1, My1, Mz1, N2, ...] (element on node convention)."""
        out = []
        for (a, b, s, vref, tag) in self.elems:
            p1, p2 = self.nodes[a], self.nodes[b]
            L = np.linalg.norm(p2 - p1)
            T, _ = self._T(p1, p2, vref)
            ue = u[np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]]
            out.append(self._k_local(L, s) @ (T @ ue))
        return out

    def stresses(self, u):
        """Per element: internal resultants (max over both ends) and max normal / torsional shear stress."""
        res = []
        for fl, (a, b, s, vref, tag) in zip(self.element_forces(u), self.elems):
            row = None
            for end, sg in ((0, -1), (6, 1)):              # internal force = -end force at node 1, +end force at node 2
                N, Vy, Vz, Tq, My, Mz = (sg * fl[end + k] for k in range(6))
                if s.round:
                    sig = abs(N) / s.A + np.hypot(My, Mz) * s.cy / s.Iy
                else:
                    sig = abs(N) / s.A + abs(My) * s.cz / s.Iy + abs(Mz) * s.cy / s.Iz
                tau = abs(Tq) * s.tau_per_T
                tau_v = abs(Vz) / s.Av if s.Av else 0.0
                if row is None or sig > row["sigma"]:
                    row = dict(tag=tag, n1=a, n2=b, N=N, Vy=Vy, Vz=Vz, T=Tq, My=My, Mz=Mz,
                               M=float(np.hypot(My, Mz)), sigma=sig, tau=tau, tau_v=tau_v, sec=s.name, material=s.material)
            res.append(row)
        return res
