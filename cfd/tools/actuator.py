"""Actuator-disk rotors as momentum sources (OpenFOAM fvOptions + topoSet cell zones).

Each rotor is a thin cylinder of cells (topoSet cylinderToCell / cylinderAnnulusToCell) that receives a
`vectorSemiImplicitSource` of exactly the rotor thrust (kinematic: T / rho), distributed over the zone
cells by volume.  The thrust per unit disk area can be uniform (ideal rotor) or grow linearly with radius
(closer to a twisted real rotor, unloaded root), by splitting the disk into annuli.  Swirl is neglected.

Rotor dict fields (SI, aircraft axes: x aft, y right, z up):
    name        unique word
    center      (x, y, z) of the hub / disk centre, m
    axis        unit thrust direction, e.g. (0, 0, 1) for a lift rotor, (-1, 0, 0) for a pusher (thrust forward)
    radius      m
    hub_radius  m (no load inside; default 0.12 R for 'linear', 0 for 'uniform')
    thrust_n    N (whole rotor)
    loading     'uniform' | 'linear'      (dT/dA = const | dT/dA proportional to r)
    thickness   axial thickness of the source zone, m (default 0.04 R, at least 2 cells is recommended)
    n_annuli    annuli used for 'linear' loading (default 8)
    domain_fraction  share of the disk inside the computational domain (0.5 for a disk cut by one symmetry
                plane, 0.25 by two); the absolute source is scaled by it (default 1)
"""
from __future__ import annotations

import numpy as np


def _annuli(rot: dict) -> list[tuple[str, float, float, float]]:
    """(zone name, r_in, r_out, thrust fraction) for the rotor."""
    R = rot["radius"]
    if rot.get("loading", "uniform") == "uniform":
        r0 = rot.get("hub_radius", 0.0)
        return [(rot["name"], r0, R, 1.0)]
    r0 = rot.get("hub_radius", 0.12 * R)
    n = rot.get("n_annuli", 8)
    edges = np.linspace(r0, R, n + 1)
    # dT = k r dA = k r 2 pi r dr  ->  fraction in [a, b] proportional to b^3 - a^3
    w = edges[1:] ** 3 - edges[:-1] ** 3
    w = w / w.sum()
    return [(f"{rot['name']}_a{i}", edges[i], edges[i + 1], float(w[i])) for i in range(n)]


def topo_actions(rotors: list[dict]) -> str:
    """topoSetDict actions creating one cellZone per rotor (or per annulus)."""
    acts = []
    for rot in rotors:
        c = np.asarray(rot["center"], float)
        n = np.asarray(rot["axis"], float)
        n = n / np.linalg.norm(n)
        h = rot.get("thickness", 0.04 * rot["radius"])
        p1, p2 = c - 0.5 * h * n, c + 0.5 * h * n
        for zone, ri, ro, _ in _annuli(rot):
            P1 = f"({p1[0]:.6f} {p1[1]:.6f} {p1[2]:.6f})"
            P2 = f"({p2[0]:.6f} {p2[1]:.6f} {p2[2]:.6f})"
            if ri <= 0:
                src = f"source cylinderToCell; p1 {P1}; p2 {P2}; radius {ro:.6f};"
            else:
                src = f"source cylinderAnnulusToCell; p1 {P1}; p2 {P2}; outerRadius {ro:.6f}; innerRadius {ri:.6f};"
            acts.append(f"    {{ name {zone}_c; type cellSet; action new; {src} }}")
            acts.append(f"    {{ name {zone}; type cellZoneSet; action new; source setToCellZone; set {zone}_c; }}")
    return "actions\n(\n" + "\n".join(acts) + "\n);\n"


def fv_options(rotors: list[dict], rho: float, ramp_iters: int = 400) -> str:
    """fvOptions: momentum sink of the rotor thrust (air is pushed opposite to the thrust direction).
    The source is ramped linearly from zero over `ramp_iters` iterations (impulsive start diverges)."""
    blocks = []
    for rot in rotors:
        n = np.asarray(rot["axis"], float)
        n = n / np.linalg.norm(n)
        for zone, _, _, frac in _annuli(rot):
            s = -frac * rot["thrust_n"] * rot.get("domain_fraction", 1.0) / rho * n
            blocks.append(f"""{zone}
{{
    type vectorSemiImplicitSource; selectionMode cellZone; cellZone {zone}; volumeMode absolute;
    sources {{ U {{ explicit table ((0 (0 0 0)) ({ramp_iters} ({s[0]:.6g} {s[1]:.6g} {s[2]:.6g})) (1e9 ({s[0]:.6g} {s[1]:.6g} {s[2]:.6g}))); implicit 0; }} }}
}}""")
    return "\n".join(blocks) + "\n"


def zones(rotors: list[dict]) -> list[str]:
    return [z for rot in rotors for z, *_ in _annuli(rot)]


def momentum_theory(thrust_n: float, radius: float, rho: float) -> dict:
    """Ideal (uniform, inviscid) actuator disk in hover."""
    A = np.pi * radius**2
    vi = np.sqrt(thrust_n / (2 * rho * A))
    return dict(v_induced=vi, v_far_wake=2 * vi, wake_radius_far=radius / np.sqrt(2), power_ideal_w=thrust_n * vi,
                disk_loading=thrust_n / A)
