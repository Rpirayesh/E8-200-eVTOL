"""Reader for design/geometry.json (schema in fea/README.md): planform helpers, mass breakdown, beam sections.

x aft from the nose, y right, z up, metres; masses kg.  Section specs refer to keys of fea/materials.json.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from fea import clt
from fea.frame import Section

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAT = json.loads((HERE / "materials.json").read_text())["materials"]


def load(path=None, sizing=None, inputs=True) -> dict:
    """Geometry dict; FEA design inputs (fea/design_inputs.json) and an optional sizing update (same section
    format as geometry.json, e.g. fea/results/sizing_update.json) are merged on top."""
    p = Path(path) if path else ROOT / "design" / "geometry.json"
    if not p.exists():
        p = HERE / "placeholder" / "geometry_placeholder.json"
    g = json.loads(p.read_text())
    g["_path"] = str(p)
    if inputs and "placeholder" not in str(p) and (HERE / "design_inputs.json").exists():
        di = json.loads((HERE / "design_inputs.json").read_text())
        g["_fea_inputs"] = di
        if g.get("parachute") and di.get("parachute"):
            g["parachute"].update({k: v for k, v in di["parachute"].items() if k in ("opening_load_N", "max_share")})
        for k in ("rotor_pylon_section", "rotor_hub_mass_fraction", "gear_model"):
            if k in di:
                g.setdefault(k, di[k])
    if sizing:
        apply_sizing(g, json.loads(Path(sizing).read_text()) if not isinstance(sizing, dict) else sizing)
    return g


def apply_sizing(g: dict, upd: dict):
    """Merge a sizing update {wing: {spars: [...], torsion_box: {...}}, booms: [{name, section}], tail: {spar_section},
    rotor_pylon_section, landing_gear_oml: {...}, gear_strut_section} into the geometry dict."""
    w = upd.get("wing", {})
    for sp in w.get("spars", []):
        for gs in g["wing"]["spars"]:
            if gs["name"] == sp["name"]:
                gs.update({k: v for k, v in sp.items() if k != "name"})
    if "torsion_box" in w:
        g["wing"]["torsion_box"].update(w["torsion_box"])
    for b in upd.get("booms", []):
        for gb in g["booms"]:
            if gb["name"] == b["name"]:
                for k in ("section", "segments"):
                    if k in b:
                        gb[k] = b[k]
    if "tail" in upd:
        g["tail"].update(upd["tail"])
    for k in ("rotor_pylon_section", "gear_strut_section"):
        if k in upd:
            g[k] = upd[k]
    if "landing_gear_oml" in upd:
        for k, v in upd["landing_gear_oml"].items():
            if isinstance(v, dict) and isinstance(g["landing_gear_oml"].get(k), dict):
                g["landing_gear_oml"][k].update(v)
            else:
                g["landing_gear_oml"][k] = v
    g["_sizing"] = upd.get("_about", "sizing update applied")
    return g


def spar_spec(sp: dict, eta: float) -> dict:
    """Section spec of a spar at eta = |y| / semi-span: piecewise-linear between 'stations' [{eta, section}] if
    given, else linear between section_root and section_tip."""
    st = sp.get("stations")
    if not st:
        return interp_section(sp["section_root"], sp["section_tip"], eta)
    st = sorted(st, key=lambda s: s["eta"])
    if eta <= st[0]["eta"]:
        return dict(st[0]["section"])
    for a, b in zip(st[:-1], st[1:]):
        if eta <= b["eta"]:
            return interp_section(a["section"], b["section"], (eta - a["eta"]) / (b["eta"] - a["eta"]))
    return dict(st[-1]["section"])


# ----------------------------------------------------------------------------- wing planform
class Wing:
    def __init__(self, w: dict):
        self.w = w
        self.b = w["span"]
        self.s = self.b / 2
        self.cr, self.ct = w["root_chord"], w["tip_chord"]
        self.tan_le = math.tan(math.radians(w.get("sweep_le_deg", 0.0)))
        self.tan_dih = math.tan(math.radians(w.get("dihedral_deg", 0.0)))

    def chord(self, y):
        return self.cr + (self.ct - self.cr) * np.abs(y) / self.s

    def x_le(self, y):
        return self.w["x_le_root"] + np.abs(y) * self.tan_le

    def z(self, y):
        return self.w["z_root"] + np.abs(y) * self.tan_dih

    def x_at(self, y, x_c):
        return self.x_le(y) + x_c * self.chord(y)

    @property
    def area(self):
        return self.w.get("area") or (self.cr + self.ct) * self.s

    @property
    def mac(self):
        lam = self.ct / self.cr
        return 2 / 3 * self.cr * (1 + lam + lam**2) / (1 + lam)


# ----------------------------------------------------------------------------- materials / sections
def _ply(key):
    d = MAT[key]["design"]
    return dict(E1=d["E1"], E2=d["E2"], nu12=d["nu12"], G12=d["G12"])


def laminate_moduli(material: str, layup: str = "0/90"):
    """Membrane Ex, Gxy of a fabric/UD laminate for a named simple lay-up ('0/90', '+-45', 'qi')."""
    p = _ply(material)
    lay = {"0/90": [0, 90, 90, 0], "+-45": [45, -45, -45, 45], "qi": [0, 45, -45, 90, 90, -45, 45, 0], "0": [0]}[layup]
    ec = clt.engineering_constants([(p, a, 1e-3) for a in lay])
    return ec["Ex"], ec["Gxy"]


def material_props(key: str):
    """(E, G, rho) for beam sections; '<laminate>_qi' / '_45' suffixes select a lay-up of a lamina entry."""
    if key.endswith("_qi") or key.endswith("_45"):
        base = key.rsplit("_", 1)[0]
        E, G = laminate_moduli(base, "qi" if key.endswith("_qi") else "+-45")
        return E, G, MAT[base]["rho"]
    m = MAT[key]
    if m["kind"] in ("isotropic",):
        return m["E"], m["G"], m["rho"]
    if m["kind"] == "tube":
        return m["design"]["E"], m["design"]["G"], m["rho"]
    if m["kind"] == "lamina":
        return m["design"]["E1"], m["design"]["G12"], m["rho"]
    raise KeyError(key)


def layer_allowables(key: str, E: float, G: float):
    """(Ft, Fc, Fs) of a material key at its modulus E, G (fabric lay-ups use the strain cut-off)."""
    base = key.rsplit("_", 1)[0] if key.endswith("_qi") or key.endswith("_45") else key
    m = MAT[base]
    d = m["design"]
    if m["kind"] == "tube":
        return d["Ft"], d["Fc"], d["Fs"]
    if m["kind"] == "isotropic":
        return d["Ftu"], d.get("Fty", d["Ftu"]), d["Fsu"]
    cut = m["knockdowns"]["strain_cutoff"]
    if key == base:                                    # UD / 0-deg lamina along the member
        return d["Xt"], d["Xc"], d["S"]
    return cut["tension"] * E, cut["compression"] * E, cut["shear"] * G


def section(spec: dict, name="") -> Section:
    t = spec["type"]
    if t == "tube":
        E, G, rho = material_props(spec["material"])
        ro = spec["od"] / 2
        s = Section.pipe(ro, ro - spec["t"], E, G, rho, name=name, material=spec["material"])
        s.kind, s.meta = "tube", dict(spec)
        return s
    if t == "tube_layers":
        # concentric layers from the inside out, e.g. COTS tube + UD over-wrap + +-45 over-wrap; each layer
        # material key as in material_props ('<lamina>_45' gives a +-45 wrap). Stress output is a reference
        # stress E_ref x strain; allowables are the minimum layer strain allowables x E_ref (meta).
        ri = spec["od"] / 2 - sum(L["t"] for L in spec["layers"]) if "od" in spec else spec["id"] / 2
        EA = EI = GJ = GA = m = 0.0
        eps_t, eps_c, gam = [], [], []
        r = ri
        for L in spec["layers"]:
            E, G, rho = material_props(L["material"])
            ro = r + L["t"]
            A_ = np.pi * (ro**2 - r**2)
            I_ = np.pi / 4 * (ro**4 - r**4)
            EA, EI, GJ, GA, m = EA + E * A_, EI + E * I_, GJ + G * 2 * I_, GA + G * A_, m + rho * A_
            ft, fc, fs = layer_allowables(L["material"], E, G)
            eps_t.append(ft / E); eps_c.append(fc / E); gam.append(fs / G)
            r = ro
        Ro = r
        E0, G0 = material_props(spec["layers"][0]["material"])[:2]
        Iref = EI / E0
        s = Section(A=EA / E0, Iy=Iref, Iz=Iref, J=GJ / G0, E=E0, G=G0, rho=0.0, cy=Ro, cz=Ro, Ay=0.5 * GA / G0,
                    Az=0.5 * GA / G0, tau_per_T=Ro * G0 / GJ, round=True, m_per_len=m, name=name,
                    material=spec["layers"][0]["material"], kind="tube_layers",
                    meta=dict(spec, od=2 * Ro, t=Ro - ri, eps_t=min(eps_t), eps_c=min(eps_c), gamma=min(gam), EI=EI, GJ=GJ))
        return s
    if t == "rect_tube":
        E, G, rho = material_props(spec["material"])
        s = Section.rect_tube(spec["b"], spec["h"], spec["t_web"], spec["t_flange"], E, G, rho, name=name, material=spec["material"])
        s.kind, s.meta = "rect_tube", dict(spec)
        return s
    if t == "cap_web":
        # two UD caps (b_cap x t_cap) at the top and bottom of a spar of depth h, n_web shear webs (t_web, +-45 fabric)
        Ec, Gc, rc = material_props(spec["cap_material"])
        Ew, Gw = laminate_moduli(spec["web_material"], spec.get("web_layup", "+-45"))
        rw = MAT[spec["web_material"]]["rho"]
        h, bc, tc, nw, tw = spec["h"], spec["b_cap"], spec["t_cap"], spec.get("n_web", 1), spec["t_web"]
        Acap = bc * tc
        hw = h - 2 * tc
        d = h / 2 - tc / 2
        EA = Ec * 2 * Acap + Ew * nw * tw * hw
        EIy = Ec * (2 * Acap * d**2 + 2 * bc * tc**3 / 12) + Ew * nw * tw * hw**3 / 12
        EIz = Ec * 2 * tc * bc**3 / 12 + Ew * nw * hw * tw**3 / 12 + (Ew * nw * tw * hw * (bc / 2) ** 2 if nw == 2 else 0)
        if nw >= 2:          # closed box between the webs (Bredt) - caps act as flanges of the box
            Am = (bc - tw) * (h - tc)
            GJ = 4 * Am**2 / (2 * (bc - tw) / (tc * Gc) + 2 * (h - tc) / (tw * Gw))
            tau_T = 1 / (2 * Am * tw)
        else:                # open section
            GJ = Gc * 2 * bc * tc**3 / 3 + Gw * hw * tw**3 / 3
            tau_T = tw / (GJ / Gw) if GJ else 0
        A = EA / Ec
        s = Section(A=A, Iy=EIy / Ec, Iz=EIz / Ec, J=GJ / Gc, E=Ec, G=Gc, rho=0.0, cy=bc / 2, cz=h / 2,
                    Ay=None, Az=nw * tw * hw * Gw / Gc, tau_per_T=tau_T, round=False,
                    m_per_len=rc * 2 * Acap + rw * nw * tw * hw, name=name, material=spec["cap_material"],
                    Av=nw * tw * hw, kind="cap_web", meta=dict(spec, web_E=Ew, web_G=Gw))
        return s
    if t == "props":
        E = spec.get("E", 70e9)
        G = spec.get("G", E / 2.6)
        s = Section(A=spec["EA"] / E, Iy=spec["EIy"] / E, Iz=spec["EIz"] / E, J=spec["GJ"] / G, E=E, G=G, rho=0.0,
                    cy=spec.get("cy", 0.05), cz=spec.get("cz", 0.05), m_per_len=spec.get("m_per_len", 0.0), name=name,
                    material=spec.get("material", ""), kind="props", meta=dict(spec))
        return s
    raise ValueError(f"unknown section type {t}")


def interp_section(s0: dict, s1: dict, f: float) -> dict:
    """Linear interpolation of numeric fields of two section specs of the same type (root -> tip)."""
    out = dict(s0)
    for k, v in s0.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k in s1 and k != "n_web":
            out[k] = v + (s1[k] - v) * f
    return out


# ----------------------------------------------------------------------------- masses
def pusher_list(g: dict) -> list[dict]:
    """All pusher units: geometry['pushers'] (iteration 3.2: one per boom tail) or the single legacy geometry['pusher']."""
    if g.get("pushers"):
        return list(g["pushers"])
    return [g["pusher"]] if g.get("pusher") else []


def mass_items(g: dict) -> list[dict]:
    """Point-mass list for cg / crash purposes: equipment, occupants + seats, rotor units, pusher, structure lumped
    at component centroids (the airframe model distributes the structural masses along the members instead)."""
    W = Wing(g["wing"])
    out = []
    for m in g.get("masses", []):
        out.append(dict(m, group="equipment"))
    for s in g.get("seats", []):
        out.append(dict(name=s["name"] + "+occupant", kg=s["occupant_kg"] + s.get("seat_kg", 0.0), x=s["x"], y=s["y"], z=s["z"],
                        attach=s.get("attach", "fuselage"), group="occupant", aft_or_above_occupants=False))
    for r in g["rotors"]:
        out.append(dict(name=r["name"], kg=r["mass_kg"], x=r["x"], y=r["y"], z=r["z"], attach=r["boom"], group="rotor"))
    for p in pusher_list(g):
        out.append(dict(name=p.get("name", "pusher"), kg=p["mass_kg"], x=p["x"], y=p["y"], z=p["z"], attach=p.get("attach", "fuselage"),
                        group="pusher"))
    out.append(dict(name="wing structure", kg=g["wing"]["mass_kg"], x=float(W.x_at(W.s * 0.42, 0.40)), y=0.0, z=float(W.z(W.s * 0.42)),
                    attach="wing", group="structure"))
    f = g["fuselage"]
    out.append(dict(name="fuselage structure", kg=f["mass_kg"], x=0.45 * (f["x_nose"] + f["x_tail"]), y=0.0, z=f["z_axis"],
                    attach="fuselage", group="structure"))
    for b in g["booms"]:
        out.append(dict(name=b["name"], kg=b["mass_kg"], x=0.5 * (b["x_front"] + b["x_aft"]), y=b["y"], z=b["z"], attach=b["name"],
                        group="structure"))
    if g.get("tail"):
        t = g["tail"]
        out.append(dict(name="tail structure", kg=t.get("mass_kg", 0.0), x=t.get("x_spar", t["x_ac"]), y=0.0, z=t["z"], attach="tail",
                        group="structure"))
    for lg in g.get("landing_gear", []):
        out.append(dict(name=lg["name"], kg=lg.get("mass_kg", 0.0), x=lg["x"], y=lg["y"], z=lg["z"] + 0.3, attach=lg.get("attach", "fuselage"),
                        group="structure"))
    return out


def mass_summary(g: dict) -> dict:
    it = mass_items(g)
    m = sum(i["kg"] for i in it)
    cg = np.array([sum(i["kg"] * i[k] for i in it) for k in "xyz"]) / m
    return dict(total_kg=m, cg=cg.tolist(), mtow_kg=g.get("mtow_kg", m), unallocated_kg=g.get("mtow_kg", m) - m)
