"""Mass calibration of the sizing model to the CAD (WP G) and FEA (WP F) masses of design iteration 1.

Reads cad/parts.json (CAD volume x density for made parts) and validation/cad/mass_cg_audit.json, applies the
weight-reduction measures adopted in iteration 2 (listed in REDUCTIONS with their justification, for WP G to
implement and WP F to re-check), and writes design/mass_calibration.json:

  * per-group factors k = (CAD mass after reductions) / (sizing-model mass of the same group at iteration 1), applied by
    sizing/model.py on top of its physics/regression estimate so that the factor scales with MTOW and geometry;
  * fixed installation masses that the iteration-1 model did not contain (rotor-station hardware, boom-wing clamps,
    parachute installation, pusher installation);
  * CG offsets of the groups (CAD CG - design CG) used by sizing/design_out.py to place the items.

    ~/tools/cadenv/bin/python -m sizing.calibration
"""
from __future__ import annotations

import json
from collections import defaultdict

from .data import ROOT

OUT = ROOT / "design" / "mass_calibration.json"

# Iteration-1 sizing-model masses of the groups (design/selected_design.json of iteration 1, kept here verbatim so the
# calibration is reproducible after the design file is overwritten by iteration 2)
ITER1 = dict(wing=73.709, tail=8.281, fuselage=39.663, boom_tube_raw=17.466, boom_tube_model=21.833, pylons_model=12.0,
             gear_raw=16.866, gear_model=26.985, avionics=10.684, cooling=9.4, seats=24.0, parachute=21.7,
             pusher_motor=23.8, pusher_propeller=4.583, battery=303.069, cells_kg=2988 * 0.071, mtow=1001.657)

# Weight-reduction measures adopted for iteration 2: (part id, fraction removed, justification).  WP G to implement,
# WP F to confirm margins.
REDUCTIONS = [
    ("W-CORE-*", 0.40, "wing XPS cores: hot-wire-cut spanwise lightening voids, 30 mm of foam kept under each skin and full "
                      "foam at the ribs, spar box and control-surface hinge lines; the skins are stabilised by the 30 mm layer "
                      "(same practice as hollow-core moldless wings); WP F to re-check skin wrinkling and core shear"),
    ("W-SPM-F", 0.4375, "main-spar box foam Divinycell H80 -> H45 (45/80 of the mass); the box webs carry the shear, the foam "
                        "only stabilises them; WP F to re-check web buckling"),
    ("MP", 0.50, "motor plate P3: FEA MS +2.8 (stress 26 % of allowable) -> pocket the plate between the bolt circles"),
    ("PY-C", 0.30, "pylon saddle with socket: pocket the side walls and the socket outside the clamp/bolt bosses"),
    ("PY-HEAD", 0.25, "pylon head: pocket between the isolator bosses"),
    ("LG-SADDLE", 0.20, "gear saddle P4 (MS +0.41 at the 3 g rigid-gear load): with the oleo dampers the limit gear load "
                        "drops to ~2.3 W (WP F) -> 20 % thinner pad/wall, to be confirmed by WP F with the damper load"),
    ("LG-SKCL", 0.30, "skid-to-cross-tube clamps: pocketed clamp halves"),
    ("CH-CRADLE", 0.40, "parachute cradle: open truss/pocketed cradle instead of a solid machined block"),
    ("TL-CLAMP", 0.30, "tail clamps: pocket outside the spar sockets"),
]

GROUP_PARTS = dict(
    wing="W-", tail=("TL-", "HT", "VF", "ELEV", "RUD"),
)


def _match(pid, pat):
    return pid.startswith(pat[:-1]) if pat.endswith("*") else pid == pat


def build_iteration2():
    parts = json.loads((ROOT / "cad" / "parts.json").read_text())["parts"]
    audit = json.loads((ROOT / "validation" / "cad" / "mass_cg_audit.json").read_text())
    by_group = defaultdict(dict)
    for p in parts:
        if p.get("qty") and p.get("mass_kg_each") and p.get("mass_group"):
            by_group[p["mass_group"]][p["id"]] = p["mass_kg_each"] * p["qty"]
    saved = {}
    after = {g: dict(v) for g, v in by_group.items()}
    for pat, frac, why in REDUCTIONS:
        for g, v in after.items():
            for pid in list(v):
                if _match(pid, pat):
                    d = v[pid] * frac
                    v[pid] -= d
                    saved[pid] = dict(group=g, kg_removed=round(d, 3), fraction=frac, justification=why)
    tot = lambda g, f=None: sum(m for pid, m in after[g].items() if (f is None or f(pid)))  # noqa: E731
    boom_tube = tot("booms", lambda p: p.startswith("BM-"))
    clamps = tot("booms", lambda p: p in ("BC-W", "BC-WR"))
    station = tot("booms", lambda p: not p.startswith("BM-") and p not in ("BC-W", "BC-WR"))
    chute_inst = tot("parachute", lambda p: p != "CHUTE")
    push_inst = tot("pusher_motor", lambda p: p != "MOT-P") + tot("pusher_propeller", lambda p: p != "PROP-P")
    cells = ITER1["cells_kg"]
    pack_cad = sum(by_group["battery"].values())
    unmodelled = 0.004 * 2988 + 3.0 + 2.0          # nickel/busbars 4 g per cell, liners/thermal pads, BMS harness (estimate)
    f_ovh_cad = (pack_cad - cells + unmodelled) / (pack_cad + unmodelled)
    cal = dict(
        _about="Sizing-model mass calibration to the iteration-1 CAD (WP G) + FEA (WP F) masses after the iteration-2 "
               "weight reductions. Generated by sizing/calibration.py; read by sizing/model.py and sizing/design_out.py.",
        factors=dict(
            wing=round(tot("wing") / ITER1["wing"], 4),
            tail=round(tot("tail") / ITER1["tail"], 4),
            fuselage=round(tot("fuselage") / ITER1["fuselage"], 4),
            boom_tube=round(boom_tube / ITER1["boom_tube_raw"], 4),
            landing_gear=round(tot("landing_gear") / ITER1["gear_raw"], 4),
            avionics=round(tot("avionics") / ITER1["avionics"], 4),
            cooling=round(tot("cooling") / ITER1["cooling"], 4),
        ),
        factor_basis=dict(
            wing="on Raymer [M1] x 0.85 composite factor", tail="on Raymer [M3]+[M4] x 0.85", fuselage="on Raymer [M5] x 0.85",
            boom_tube="on the strength-sized raw tube mass (replaces the x1.25 sleeve factor): includes WP F over-wrap "
                      "segments, +-45 layers, sleeves, bands and end caps",
            landing_gear="on the raw strength-sized skid/cross-tube mass (replaces x1.6): includes the oleo dampers "
                         "(80 mm stroke), collars, saddles P4, clamps, fairings and shoes",
            avionics="on Raymer [M12]: tray, panel and lumped wiring as modelled", cooling="on the cooling build-up",
        ),
        fixed_kg=dict(
            rotor_station_hardware_each=round(station / 8, 3),
            boom_wing_clamps_total=round(clamps, 3),
            parachute_installation=round(chute_inst, 3),
            pusher_installation=round(push_inst, 3),
            seats_and_furnishings=round(sum(after["seats"].values()), 3),
        ),
        fixed_basis=dict(
            rotor_station_hardware_each="pylon tube, pylon saddle with socket, pylon head, motor plate P3, elastomeric "
                                        "isolators, nacelle fairing (per rotor station, after reductions)",
            boom_wing_clamps_total="4 boom-to-wing saddles P2 (front, rear slotted)",
            parachute_installation="cradle, front and rear riser hard points P5 with angles",
            pusher_installation="motor plate, strut end fittings, pultruded struts, spinner",
            seats_and_furnishings="2 crash-rated seats (shell, cushion, EA block, rails, P6 fittings, harness anchors, harnesses) + furnishings",
        ),
        battery=dict(cad_pack_kg=round(pack_cad, 2), cells_kg=round(cells, 2), unmodelled_kg_estimate=round(unmodelled, 1),
                     non_cell_fraction_cad=round(f_ovh_cad, 4), adopted_non_cell_fraction=0.25,
                     basis="CAD packs (boxes, lids, 4 cold plates, G10 holders, BMS, contactors, mounts) + estimated nickel, "
                           "liners, BMS harness give 0.22; 0.25 adopted (= WP M light scenario) for the packs to be reshaped"),
        cg_offsets_m={c["category"]: dict(dx=c["dx_m"], dz=c["dz_m"]) for c in audit["categories"]},
        reductions=saved,
        reductions_total_kg=round(sum(v["kg_removed"] for v in saved.values()), 2),
        cad_iteration1=dict(empty_kg=audit["totals"]["empty (incl. growth)"]["cad_kg"], mtow_kg=audit["totals"]["MTOW (pilot + passenger)"]["cad_kg"],
                            static_margin=audit["static_margin_cad"]),
        group_mass_after_reductions_kg={g: round(sum(v.values()), 2) for g, v in after.items() if g not in ("tooling",)},
        iteration3=dict(note="Factors unchanged in iteration 3. HV harness modelled with aluminium conductors (3.1 A/mm2, "
                             "2700 kg/m3, x1.4 insulation/lugs) instead of copper (5 A/mm2): 10.3 kg instead of ~21 kg; CAD to "
                             "replace the HV-BOOM/HV-WING copper runs with aluminium cable and bimetal lugs. Pusher propeller now the "
                             "2-blade DUC SWIRL (2.72 kg). Bottom-up cost rates from the same CAD parts: design/cost_rates.json "
                             "(sizing/cost.py)."),
    )
    # iteration 3.1: second calibration step on the iteration-3 CAD rebuild (validation/cad/mass_cg_audit.md, iteration 3:
    # CAD MTOW 1,034.5 kg, empty 628.8 kg, SM 0.114), group ratio CAD / design applied on top of the iteration-2 factors
    C3 = dict(wing=63.26 / 65.81, boom_tube=48.95 / 45.66, tail=9.81 / 9.61, landing_gear=34.91 / 51.28, fuselage=61.85 / 65.48,
              avionics=14.05 / 12.53, cooling=11.54 / 10.36)
    for k, r in C3.items():
        cal["factors"][k] = round(cal["factors"][k] * r, 4)
    cal["fixed_kg"]["rotor_station_hardware_each"] = round(cal["fixed_kg"]["rotor_station_hardware_each"] + 6.76 / 8, 3)  # INV-POD, PY-C -11 % only
    cal["fixed_kg"]["seats_and_furnishings"] = 25.17
    cal["fixed_kg"]["parachute_installation"] = round(cal["fixed_kg"]["parachute_installation"] - 0.64, 3)
    cal["fixed_kg"]["flap_actuators"] = 4.0
    cal["iteration3_cad"] = dict(ratios=C3, mtow_kg=1034.5, empty_kg=628.8, static_margin=0.114,
                                 note="iteration-3 CAD rebuild incl. WP F phase-3 changes (pivoting damped gear legs, H45 strips, "
                                      "PY-C -11 %), inverter under-boom pods (INV-POD), 4 flap actuators")
    OUT.write_text(json.dumps(cal, indent=1))
    return cal


def build():
    """Iteration 3.1: the iteration-2 calibration (derived from the iteration-1 CAD, kept in design/iteration2/) corrected by the
    group ratios CAD / design of the iteration-3 CAD rebuild.  cad/parts.json now holds the iteration-3 build, so the
    iteration-2 derivation (build_iteration2) is not re-run on it."""
    cal = json.loads((ROOT / "design" / "iteration2" / "mass_calibration.json").read_text())
    C3 = dict(wing=63.26 / 65.81, boom_tube=48.95 / 45.66, tail=9.81 / 9.61, landing_gear=34.91 / 51.28, fuselage=61.85 / 65.48,
              avionics=14.05 / 12.53, cooling=11.54 / 10.36)
    for k, r in C3.items():
        cal["factors"][k] = round(cal["factors"][k] * r, 4)
    fx = cal["fixed_kg"]
    fx["rotor_station_hardware_each"] = round(fx["rotor_station_hardware_each"] + 6.76 / 8, 3)   # INV-POD, PY-C -11 % only
    fx["seats_and_furnishings"] = 25.17
    fx["parachute_installation"] = round(fx["parachute_installation"] - 0.64, 3)
    fx["flap_actuators"] = 4.0
    cal["_about"] = ("Sizing-model mass calibration: iteration-2 factors (iteration-1 CAD/FEA after the adopted reductions) x "
                     "iteration-3 CAD rebuild ratios. Generated by sizing/calibration.py.")
    cal["iteration3_cad"] = dict(ratios={k: round(v, 4) for k, v in C3.items()}, mtow_kg=1034.5, empty_kg=628.8, static_margin=0.114,
                                 source="validation/cad/mass_cg_audit.md (iteration 3 rebuild)",
                                 note="incl. WP F phase-3 changes (pivoting damped gear legs, H45 strips, PY-C -11 %), inverter "
                                      "under-boom pods INV-POD, 4 flap actuators (+4 kg)")
    # iteration 3.2: third step on the 3.1 CAD rebuild (validation/cad/mass_cg_audit.md 23:25: MTOW 1,099.0 kg)
    C31 = dict(wing=69.61 / 73.90, boom_tube=48.93 / 48.84, tail=11.64 / 10.74, landing_gear=36.05 / 35.64, fuselage=64.97 / 62.36,
               avionics=15.57 / 14.05, cooling=12.72 / 11.54)
    for k, r in C31.items():
        cal["factors"][k] = round(cal["factors"][k] * r, 4)
    fx["parachute_installation"] = round(fx["parachute_installation"] + 1.51, 3)
    cal["iteration31_cad"] = dict(ratios={k: round(v, 4) for k, v in C31.items()}, mtow_kg=1099.0, empty_kg=650.2,
                                  battery_kg=248.74, static_margin=0.105,
                                  battery_model="per cell 0.0262 kg + per pack 3.44 kg on top of the cells (fitted to 7 CAD packs, "
                                                "248.7 kg excl. nickel/harness; replaces the 0.25 non-cell fraction)")
    cal["iteration3"] = dict(note="HV harness modelled with aluminium conductors (3.1 A/mm2); pusher propeller DUC SWIRL 2-blade; "
                                  "bottom-up cost rates from the iteration-3 CAD parts as built: design/cost_rates.json (sizing/cost.py)")
    # iteration 3.3: fourth step on the 3.2 (T8) CAD rebuild (validation/cad/mass_cg_audit.json, cad/mass_properties.json of
    # 2026-11-18: MTOW 1,208.2 kg incl. growth, empty 754.5 kg against the design 697.2 kg)
    C32 = dict(wing=86.382 / 74.611, boom_tube=76.462 / 60.056, tail=16.154 / 13.665, landing_gear=44.122 / 37.962,
               fuselage=75.035 / 63.877, avionics=17.091 / 15.572, cooling=15.007 / 13.536)
    for k, r in C32.items():
        cal["factors"][k] = round(cal["factors"][k] * r, 4)
    fx["rotor_station_hardware_each"] = round(fx["rotor_station_hardware_each"] + 2.574 / 8, 3)    # rotor stations +2.57 kg
    fx["pusher_installation"] = round(fx["pusher_installation"] + (2.24 + 1.04) / 2, 3)           # per boom-tail unit
    fx["parachute_installation"] = round(fx["parachute_installation"] + 0.471, 3)
    # battery: two-point fit of the non-cell pack mass to the 3.1 CAD (7 packs, 2,450 cells, 248.74 kg) and the 3.2 CAD
    # (5 packs, 2,625 cells, 253.74 kg) with the P50B at 0.071 kg: per cell 0.0159 kg, per pack 5.11 kg
    a_c = ((253.74 - 2625 * 0.071) * 7 - (248.74 - 2450 * 0.071) * 5) / (2625 * 7 - 2450 * 5)
    b_p = ((248.74 - 2450 * 0.071) - 2450 * a_c) / 7
    cal["battery_pack_model"] = dict(per_cell_kg=round(a_c, 5), per_pack_kg=round(b_p, 3),
                                     basis="two-point fit: 3.1 CAD 7 x 175s2p 248.74 kg; 3.2 CAD 5 x 175s3p 253.74 kg")
    # CAD-minus-design group CG x shifts of the 3.2 build, applied to the layout items of each group (design_out)
    cal["cg_dx_iteration33"] = {"wing": 0.0481, "booms": 0.0923, "rotor stations": 0.0034, "tail": 0.0045, "landing gear": 0.0821,
                                "fuselage": 0.1372, "seats": -0.0102, "avionics": -0.0093, "LV electrical": 0.0015,
                                "flight controls": -0.4233, "parachute": -0.0809, "HV harness": 0.5849, "cooling": 0.027,
                                "battery": -0.0063}
    cal["iteration32_cad"] = dict(ratios={k: round(v, 4) for k, v in C32.items()}, mtow_kg=1208.21, empty_kg=754.47,
                                  battery_kg=253.74, static_margin=0.0579,
                                  source="validation/cad/mass_cg_audit.json (3.2 T8 rebuild)",
                                  note="pusher units +3.3 kg (motor +2.24, propeller +1.04) into pusher_installation per unit; "
                                       "rotor stations +2.57 kg; parachute +0.47 kg")
    cal["_about"] = ("Sizing-model mass calibration: iteration-2 factors (iteration-1 CAD/FEA after the adopted reductions) x "
                     "iteration-3, 3.1 and 3.2 CAD rebuild ratios. Generated by sizing/calibration.py.")
    OUT.write_text(json.dumps(cal, indent=1))
    return cal


def load(path=None):
    if path:
        return json.loads((ROOT / path).read_text())
    return json.loads(OUT.read_text()) if OUT.exists() else build()


if __name__ == "__main__":
    c = build()
    print(json.dumps({k: c[k] for k in ("factors", "fixed_kg", "battery", "reductions_total_kg")}, indent=1))
