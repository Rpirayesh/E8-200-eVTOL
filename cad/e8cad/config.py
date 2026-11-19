"""Design inputs, shop limits, materials and the Part record for the E8-200 CAD.

Every aircraft dimension is read from design/geometry.json and design/selected_design.json
(converted to mm). Numbers written in this package are detail features (wall thicknesses,
bolt sizes, flange widths, gaps) and shop/tooling limits, listed in DETAIL below.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from build123d import Location, Pos, Rot
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[2]
G = json.loads((ROOT / "design" / "geometry.json").read_text())
S = json.loads((ROOT / "design" / "selected_design.json").read_text())
CAT = {i["id"]: i for i in json.loads((ROOT / "bom" / "catalog.json").read_text())["items"]}
MATS = json.loads((ROOT / "fea" / "materials.json").read_text())["materials"]
AIRFOIL_DIR = ROOT / "validation" / "cfd" / "reference"

MM = 1000.0


def mm(v):
    return float(v) * MM


# --------------------------------------------------------------------------- shop limits (assumed, see cad/README.md)
SHOP = {
    "cnc_bed_mm": [2440.0, 1220.0, 250.0],   # 3-axis router, 8 x 4 ft table, usable cutting depth
    "cnc_metal_mm": [1000.0, 600.0, 150.0],  # aluminium work envelope (router with spindle or job-shop mill)
    "fdm_mm": [250.0, 250.0, 250.0],         # FDM build volume (256 mm class printer, 6 mm margin)
    "hotwire_bow_mm": 1300.0,                # longest hot-wire core (bow width)
    "foam_block_mm": [2440.0, 1220.0, 300.0],
    "tube_stock_mm": CAT["MAT-TUBE-DP-4x96"]["ratings"]["length_mm"],
}

# --------------------------------------------------------------------------- detail features (not design numbers)
DETAIL = {
    "panel_face_t": 0.5, "panel_core_t": 10.0,      # cabin sandwich: 2 x 200 g/m2 carbon each face on H80
    "shell_t": 1.0,                                 # fuselage glass shell (3 x 300 g/m2)
    "canopy_t": CAT["CAB-PC-SHEET"]["ratings"]["thickness_mm"],
    "rib_t": 11.0,                                  # wing ribs: same sandwich as cabin panels
    "ctrl_skin_t": 0.6, "ctrl_gap": 3.0,            # control-surface skins and hinge gaps
    "clamp_wall": 12.0, "clamp_len": 90.0,          # machined boom clamps
    "boom_clear": 3.0,                              # boom channel clearance in cores/skins
    "motor_len": 105.0,                             # REB 50 axial length placeholder (datasheet: diameter only)
    "pusher_motor_len": 150.0,                      # REB 90 axial length placeholder
    "inverter_box": [230.0, 90.0, 180.0],           # HBCi placeholder envelope (x, y, z)
    "cell_d": 21.7, "cell_h": 70.4, "cell_pitch": 22.4,  # 21700 cells in G10 holders
    "bat_wall": 1.6,                                # 5052/6061 battery box sheet
    "seat_srp_back": 100.0,                         # seat reference point aft of occupant CG
    "sitting_height_p95": 970.0,                    # 95th percentile male sitting height (head clearance check)
}

# --------------------------------------------------------------------------- materials (kg/m3)
EXTRA_DENSITY = {  # non-structural or tooling materials not in fea/materials.json
    "xps_foam": 32.0, "eps_tooling_foam": 30.0, "pu_tooling_board": 240.0, "mdf": 750.0, "birch_plywood": 680.0,
    "polycarbonate": 1200.0, "confor_cf45": 93.0, "g10": 1850.0, "uhmw_pe": 940.0,
    "nylon_strap": 1140.0, "copper": 8900.0, "pvc_h45": 48.0, "aluminium_cable": 2700.0,
}


def rho(key: str) -> float:
    if key in MATS and MATS[key].get("rho"):
        return float(MATS[key]["rho"])
    if key in EXTRA_DENSITY:
        return EXTRA_DENSITY[key]
    raise KeyError(key)


for _k, _r in (("pla", 1240.0), ("petg", 1270.0), ("asa", 1070.0), ("pa_cf", 1150.0), ("pvc_h100", 100.0)):
    EXTRA_DENSITY.setdefault(_k, _r)


def sandwich(face_mat="cf_fabric_wet", face_t=None, core_mat="pvc_h80", core_t=None):
    ft = DETAIL["panel_face_t"] if face_t is None else face_t
    ct = DETAIL["panel_core_t"] if core_t is None else core_t
    t = 2 * ft + ct
    r = (2 * ft * rho(face_mat) + ct * rho(core_mat)) / t
    return dict(t=t, rho=r, label=f"sandwich {face_mat} 2 x {ft} mm on {core_mat} {ct} mm", keys=[face_mat, core_mat])


PANEL = sandwich()

# --------------------------------------------------------------------------- Part record


@dataclass
class Part:
    pid: str
    name: str
    group: str            # viewer group
    process: str          # CNC, FDM, composite-layup, COTS, COTS-cut, outsourced-waterjet, outsourced-bend, outsourced-thermoform
    material: str         # material key(s) / description
    solid: object         # build123d Solid / Compound in the modelling frame (mm)
    placements: list      # [(Location, mirrored_about_local_XZ)]
    mass_group: str       # selected_design breakdown key, or 'battery', 'payload', 'tooling'
    notes: str = ""
    settings: dict = field(default_factory=dict)
    density: float | None = None          # kg/m3 of the solid
    bodies: list | None = None            # [(solid, kg/m3)] for multi-material parts
    mass_kg: float | None = None          # COTS / placeholder mass per instance
    mass_source: str = "CAD volume x density"
    skin: bool = False                    # hidden by the viewer's "hide skins"
    tooling: bool = False
    purchased: bool = False
    joints: str = ""                      # split / joint statement for parts larger than a machine
    machine: str = ""                     # envelope checked against: cnc, cnc_metal, fdm, none


def place(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, mirror=False):
    return (Pos(x, y, z) * Rot(rx, ry, rz), mirror)


IDENT = place()

# --------------------------------------------------------------------------- wing frame
W = G["wing"]
WING = dict(
    span=mm(W["span"]), half=mm(W["span"]) / 2, chord=mm(W["root_chord"]), xle=mm(W["x_le_root"]), zle=mm(W["z_root"]),
    inc=W["incidence_deg"], spars=W["spars"], skin_t=W["torsion_box"]["skin_t"] * MM, root_y=mm(W["root_fittings_y"]),
    ail=W["control_surfaces"]["ailerons"], flaps=W["control_surfaces"].get("flaps"),
)
WLOC = Pos(WING["xle"], 0, WING["zle"]) * Rot(0, WING["inc"], 0)   # local airfoil frame (LE origin, y span) -> aircraft


def wing_to_global(x, z, y=0.0):
    a = math.radians(WING["inc"])
    return np.array([WING["xle"] + x * math.cos(a) + z * math.sin(a), y, WING["zle"] - x * math.sin(a) + z * math.cos(a)])


def global_to_wing(X, Z):
    a = math.radians(WING["inc"])
    dx, dz = X - WING["xle"], Z - WING["zle"]
    return dx * math.cos(a) - dz * math.sin(a), dx * math.sin(a) + dz * math.cos(a)


# --------------------------------------------------------------------------- fuselage OML (super-ellipse stations)
F = G["fuselage"]
_st = F["stations"]
_fx = np.array([mm(s["x"]) for s in _st])
_fw = PchipInterpolator(_fx, [mm(s["width"]) for s in _st])
_fh = PchipInterpolator(_fx, [mm(s["height"]) for s in _st])
_fz = PchipInterpolator(_fx, [mm(s["z_center"]) for s in _st])
FUS_N = F["shape_exponent"]
FUS_L = float(_fx.max())                     # last OML station (the cowl end may be open)


def oml(x):
    """(width, height, z_center) of the fuselage OML at station x (mm)."""
    return float(max(_fw(x), 0.0)), float(max(_fh(x), 0.0)), float(_fz(x))


def oml_z_range(x, y):
    """Lower and upper OML z at (x, y); None if |y| outside."""
    w, h, zc = oml(x)
    if w <= 0 or abs(y) >= w / 2:
        return None
    r = (1 - (abs(y) / (w / 2)) ** FUS_N) ** (1 / FUS_N)
    return zc - h / 2 * r, zc + h / 2 * r


def oml_half_width(x, z):
    w, h, zc = oml(x)
    if h <= 0 or abs(z - zc) >= h / 2:
        return 0.0
    return w / 2 * (1 - (abs(z - zc) / (h / 2)) ** FUS_N) ** (1 / FUS_N)


def oml_section_xz(y, x0, x1, inset=0.0, n=120):
    """Closed (x, z) outline of the OML cut by the plane y (inset normal to the surface, approx.)."""
    xs = np.linspace(x0, x1, n)
    lo, hi = [], []
    for x in xs:
        r = oml_z_range(x, abs(y) + inset)
        if r is None:
            lo.append(np.nan); hi.append(np.nan)
        else:
            lo.append(r[0] + inset); hi.append(r[1] - inset)
    lo, hi = np.array(lo), np.array(hi)
    ok = ~np.isnan(lo) & (hi > lo)
    xs, lo, hi = xs[ok], lo[ok], hi[ok]
    return np.vstack([np.column_stack([xs, lo]), np.column_stack([xs[::-1], hi[::-1]])])


def oml_ring(x, inset=0.0, npts=72):
    w, h, zc = oml(x)
    from .geom import superellipse
    return superellipse(max(w - 2 * inset, 2.0), max(h - 2 * inset, 2.0), 0.0, zc, FUS_N, npts)


# --------------------------------------------------------------------------- other frames
BOOMS = G["booms"]
BOOM_Y = mm(abs(BOOMS[0]["y"]))
BOOM_Z = mm(BOOMS[0]["z"])
BOOM_OD = mm(BOOMS[0]["diameter"])
BOOM_X0, BOOM_X1 = mm(BOOMS[0]["x_start"]), mm(BOOMS[0]["x_end"])
ROTORS = G["lift_rotors"]
PUSH = G["pusher"]
TAIL = G["tail"]
GEAR = G["landing_gear_oml"]
BATS = G["battery_packs"]
SEATS = G["seats"]
CHUTE = G["parachute"]


def mass_item(prefix, default=None):
    """Mass of the design mass item(s) whose name starts with prefix (kg); default if none."""
    its = [m for m in G["mass_items"] if m["name"].startswith(prefix)]
    return sum(m["kg"] for m in its) / max(len(its), 1) if its else default

# --------------------------------------------------------------------------- WP F (FEA) inputs
# phase 3.1 results not yet in sizing_update.json / geometry.json (fea/README.md phase 3.1, fea/results/margins.json)
FEA_31 = {"ht_spar_t": 0.00248, "ht_airfoil": "naca0014"}
_SZ = ROOT / "fea" / "results" / "sizing_update.json"
SIZING = json.loads(_SZ.read_text()) if _SZ.exists() else {}
# fitting dimensions modelled parametrically by WP F in fea/parts.py (P1..P6); kept identical here so the FEA can be
# re-run on the CAD STEP parts (mm)
FEA_FIT = {
    "P1_wing_root_lug": dict(material="al7075_t6_sheet", t=12.0, plate_w=170.0, plate_h=120.0, lug_w=60.0, pin_d=19.05,
                             lug_zc=-95.0, neck_h=70.0, eye_t_main=14.0, eye_t_main32=22.0, t_main33=18.0, edge_main32=34.0, bolts=[(x, z) for x in (-60, -20, 20, 60) for z in (-25, 25)], bolt_d=8.0),
    "P2_boom_clamp": dict(material="al6061_t6_extr", wall=12.0, width=110.0, pad_w=150.0, pad_t=16.0, bolt_d=9.5,
                          bolts=[(x, y) for x in (-38, 38) for y in (-58, 58)], slot_len=16.0),
    "P3_motor_plate": dict(material="al6061_t6_extr", R=140.0, t=10.0, bolt_pcd_r=90.0, n_bolts=8, bolt_d=8.0, centre_d=40.0,
                           stub_r=50.0, stub_wall=4.0, stub_len=30.0),
    "P4_gear_saddle": dict(material="al6061_t6_extr", wall=18.0, width=150.0, pad_w=160.0, pad_t=20.0, bolt_d=9.5,
                           bolts=[(x, y) for x in (-55, 0, 55) for y in (-62, 62)]),
    "P5_parachute_hardpoint": dict(material="steel_4130_n", t=15.0, plate_w=120.0, plate_h=70.0, neck_w=64.0, neck_h=50.0,
                                   eye_zc=75.0, pin_d=16.0, bolts=[(x, z) for x in (-45, -15, 15, 45) for z in (-18, 18)], bolt_d=8.0),
    "P6_seat_fitting": dict(material="al7075_t6_sheet", base=(90.0, 50.0, 10.0), web=(40.0, 14.0, 40.0), eye_r=20.0, eye_z=45.0,
                            pin_d=9.5, bolts=[(-32, 0), (32, 0)], bolt_d=8.0),
}

if SIZING.get("wing", {}).get("torsion_box", {}).get("skin_t"):
    WING["skin_t"] = SIZING["wing"]["torsion_box"]["skin_t"] * MM
WING["skin_source"] = "fea/results/sizing_update.json" if SIZING.get("wing") else "design/geometry.json"
