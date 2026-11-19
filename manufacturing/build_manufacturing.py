#!/usr/bin/env python3
"""Write manufacturing/MANUFACTURING.md from cad/parts.json (per-part table) plus the process families, inspection plan,
build sequence and labour schedule of the E8-200 prototype (WP P, pass 2).

Labour hours: WP D bottom-up model (sizing/cost.py rates on the CAD parts; sizing/results/cost_breakdown.md, incl.
tooling and QC). They are estimates and are re-allocated here to build tasks; the schedule assumes three people at 40 h/week.

    python3 manufacturing/build_manufacturing.py
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CADJ = json.loads((ROOT / "cad/parts.json").read_text())
PARTS = CADJ["parts"]
LIM = CADJ["shop_limits"]

SHOP = {  # process -> where/how (shop label)
    "CNC": "CNC (our 3-axis)",
    "FDM": "FDM (our printers)",
    "composite-layup": "Composite lay-up (in-house)",
    "COTS": "Bought (COTS)",
    "COTS-cut": "Bought stock, cut in-house",
    "outsourced-waterjet": "Outsourced waterjet/laser, finished in-house",
    "outsourced-thermoform": "Outsourced thermoforming, trimmed in-house",
    "outsourced-bend": "Outsourced tube bending, finished in-house",
}
MACHINE = {"cnc": "3-axis router (2440 x 1220 x 250 bed)", "cnc_metal": "3-axis mill, aluminium (1000 x 600 x 150)",
           "cnc_plug": "3-axis router, foam plug (2 set-ups)", "hot-wire bow": "hot-wire bow on templates (1300 mm)", "fdm": "FDM 250 mm cube"}


def family(p):
    m, pr, i = p["material"], p["process"], p["id"]
    if p.get("tooling"):
        return "TOOL"
    if pr == "COTS":
        return "COTS"
    if i.startswith("W-CORE") or (pr == "CNC" and "xps" in m):
        return "F1 hot-wire cores"
    if i.startswith(("W-SPM", "W-SPR")) and "pvc" not in m:
        return "F2 spar caps and webs"
    if "pvc_h45" in m:
        return "F2 spar caps and webs"
    if m.startswith("sandwich"):
        return "F4 flat sandwich panels"
    if i == "W-SKIN" or "skin on xps" in m or i.startswith(("W-FS", "W-TIP")):
        return "F3 skins and surfaces"
    if i.startswith("BM-") and pr == "composite-layup":
        return "F6 booms"
    if i.startswith("BM-T") or (pr == "COTS-cut" and "cf_tube" in m):
        return "F6 booms"
    if i.startswith(("SH-", "HATCH", "F-WRF", "CAN-FRM", "PM-COWL")):
        return "F5 moldless shell"
    if pr == "composite-layup" and "eglass" in m:
        return "F10 printed-mould fairings"
    if i.startswith("SEAT") or "pvc_h100" in m or i == "NOSE-EA":
        return "F11 seats and crush blocks"
    if i.startswith("LG-"):
        return "F12 landing gear"
    if i.startswith(("BAT", "IP")) and pr.startswith("outsourced"):
        return "F8 sheet-metal boxes"
    if i.startswith("BAT-TIER"):
        return "F9 battery packs"
    if pr.startswith("outsourced-thermoform") or i in ("WIN-L",):
        return "F13 canopy"
    if pr == "CNC" and any(a in m for a in ("al6061", "al7075", "steel", "uhmw")):
        return "F7 machined fittings"
    if pr == "FDM":
        return "F10 printed-mould fairings"
    if pr == "COTS-cut":
        return "F7 machined fittings"
    return "F7 machined fittings"


INSPECT = {
    "F1 hot-wire cores": "dimensional check against printed section gauges at both ends; void map; weight",
    "F2 spar caps and webs": "ply-count log per station, witness coupon (D3039/D2344), Barcol, cap thickness by caliper every 300 mm, proof load of the spar to limit before closing",
    "F3 skins and surfaces": "tap test map, backlight (glass), weight vs CAD, twist/incidence on the cradle, hinge-line straightness",
    "F4 flat sandwich panels": "panel coupon per lay-up (flatwise tension C297, short beam), tap test, insert pull-out sample per insert type, CNC first-article check",
    "F5 moldless shell": "tap test, thickness at cut-outs, fit to cabin structure, weight",
    "F6 booms": "incoming 4-point bend test per tube batch, over-wrap thickness/OD by tape every 250 mm, sleeve bond lap-shear coupon, straightness on the strongback",
    "F7 machined fittings": "first-article inspection (bores, hole positions, edge distances) vs STEP; surface finish at lugs; alodine/anodize record; torque log at install",
    "F8 sheet-metal boxes": "flat-pattern check on receipt, bend radii >= 2t, rivet pull-test sample, seal/leak check",
    "F9 battery packs": "cell incoming test (OCV, IR, capacity sample 2 %), weld pull test per shift, insulation resistance >= 1 MOhm at 1000 V, BMS cell-voltage check, thermal soak with BMS log",
    "F10 printed-mould fairings": "visual, fit, weight",
    "F11 seats and crush blocks": "shell coupon, crush-block density check, hard-point pull test (CS-23.785 loads x 1.33 on a sample insert)",
    "F12 landing gear": "bent leg checked on T-XT-TEMPL, pivot bore fit, damper rate/stroke bench check, drop test of one corner",
    "F13 canopy": "optical distortion check, edge cracks after drilling, latch/jettison function",
    "COTS": "receiving inspection: part number, serial, certificate of conformity, visual damage",
    "TOOL": "dimensional check against STEP (surface sweep with a dial gauge on the router), seal/release applied",
}

STEPS = """
### F1 Hot-wire foam cores (W-CORE-*, HT, ELEV, VF, RUD, ailerons)
1. Laminate 2 in XPS boards into blocks of the core height with thin epoxy spots (not across cut lines); stand 24 h.
2. Pin the CNC-cut MDF templates T-HW-* to both block ends (constant chord, so the same pair for every station of a
   section); kerf compensation 0.8 mm is already in the templates.
3. Cut LE, spar-box-to-rear-spar and aft pieces with the hot-wire bow at constant speed (two operators calling stations).
4. Cut the spanwise lightening voids with the inner templates (30 mm of foam kept under each skin); route the spar-cap
   troughs with the router sled to the cap taper; route boom channels in W-CORE-4/5.
5. Replace the XPS over the main-spar box by the 15 mm H45 strip W-SPM-S (FEA required change 2).
6. Weigh, label (part ID, left/right) and store flat on the cradles.

### F2 Spar caps and webs (W-SPM-CU/CL, W-SPR-CU/CL, W-SPM-W, W-SPR-W, W-SPM-F)
1. Assemble the MDF cap jigs T-CAPJIG-* on the strongback (2.2 m segments, dowel-pinned), seal, wax, PVA.
2. Cut UD 300 g/m2 strips to the ply-drop table in the part notes (cap thickness by station, drops every ~150 mm),
   number them, and lay up wet with MGS L285/H287 in one continuous 7.94 m session per cap (two laminators).
3. Peel ply, perforated film, breather, bag; 24 h RT under vacuum, then 15 h at 50 C post-cure (tent and heaters).
4. Cut a witness coupon from the overlength at each end; record thickness every 300 mm.
5. Bond the cured caps into the core troughs together with the H45 box foam W-SPM-F; wrap the +/-45 carbon webs
   (W-SPM-W, W-SPR-W) onto the box faces with 25 mm wrap onto the caps; bag and cure.
6. Proof-load the closed spar box to limit load on the strongback before the skins go on.

### F3 Skins and control surfaces (W-SKIN, W-TIP, W-AIL, HT, ELEV, VF, RUD, W-FS-*)
1. Place the core/spar assembly in the lower MDF cradles T-CRADLE-L set to the design incidence (digital level).
2. Lay 2 x 193 g/m2 carbon twill at +/-45 on the lower surface (1.27 m widths, 50 mm overlaps), peel ply, bag, cure.
3. Flip into the upper cradles, install the wing ribs W-RIB-* and the root fittings' spacers, lay the upper skin, cure.
4. Trim boom channels and aileron bays; cut out the ailerons, close their edges with the false spars
   W-FS-*; fit hinges W-HINGE through potted inserts.
5. Wing tips W-TIP: glass over the foam plug T-PLUG-TIP. Tail surfaces follow the same steps on their own templates.

### F4 Flat sandwich panels (FLOOR, SIDE, BH-*, AF-KEEL, AV-TRAY, W-RIB-*)
1. Vacuum table: glass or melamine sheet, release, 2 plies carbon twill, 10 mm H80, 2 plies carbon twill, peel ply,
   bag; one full 2440 x 1220 sheet per session; cure 24 h RT + post-cure.
2. Lay the panel on the router, nest from the STEP (tabs/slots in the CAD), cut with a compression cutter, dust extraction.
3. Rout insert holes oversize, pot aluminium inserts with flox, local UD straps (keel caps 40 mm, frame straps 60 mm)
   wet-laid after potting.
4. Dry-fit the tub on the build table (tabs locate the parts), then bond with flox fillets and 2 x 45 deg glass tapes.

### F5 Moldless shell (SH-NOSE/CAB/MID/AFT/TAIL, hatches, F-WRF, CAN-FRM, PM-COWL)
1. Machine the laminated foam plug blocks T-PLUG-F* (two set-ups each), assemble left/right halves on dowels.
2. Seal with lightweight filler + epoxy; the plug surface is OML minus shell thickness.
3. Lay 3 plies 7781 glass wet on the plug, peel ply; cure; fair the outer surface (this is where moldless costs hours).
4. Cut on the centre line, remove from the plug, bond to the cabin structure; cut hatches and fit hinges/fasteners.

### F6 Booms (BM-T1..T4, BM-SLV, BM-WRAP1..3, BM-BAND1/2, BM-CAP-F/A)
1. Cut the DragonPlate 4 in tubes to the cut list (BOM.md) on the V-blocks T-VBLOCK; square the ends.
2. Make the internal splice sleeves BM-SLV (wet-laid carbon on a release-wrapped mandrel), bond 150 mm each side with EA 9394.
3. Align the boom on the strongback (laser line), abrade, wet-wind UD over-wrap to the WP F thickness per zone, then
   +/-45 sleeve/fabric; shrink-tape, 50 C post-cure; measure OD every 250 mm.
4. Wind the UD bands BM-BAND at the clamp stations; slide on the clamp rings (BC-W/BC-WR, PY-C, TL-CLAMP) and bond
   them at their stations in the alignment jig; drill cross-bolts through T-DRILL-BC.

### F7 Machined fittings (aluminium 6061/7075, 4130; 31 parts on the metal CNC)
1. CAM from the STEP; stock per the BOM nesting table (plate <= 25 mm, bar/block above).
2. Op 1 face/profile/pockets, op 2 flip on soft jaws; lugs and bores finished with a reamer; deburr, edge-break.
3. Lugs (W-FIT-MS/RS, W-CHUTE-FIT, CH-ATT-R, SEAT-FIT): eye boss per WP F change 3 (14 mm on W-FIT-MS); drill-ream
   the wing pins through T-DRILL-RF at assembly.
4. Alodine (outsourced) or anodize; prime faying surfaces; 4130 parts normalized, primed.
5. If the in-house mill cannot hold the tolerances on the rings and lugs, send these CAM files to a job shop. Parts taller
   than the 150 mm Z of the metal mill (flagged "DOES NOT FIT" in the per-part table, e.g. CH-CRADLE) are machined in two
   set-ups from opposite faces or sent to the job shop.
6. MP-EMX adapter rings (12 mm 6061-T6) join the EMRAX 268 stator bolt circle to the motor plate MP: confirm the bolt circle
   and the coolant-port clearance on the EMRAX drawing before cutting; then route the COOL-MOT hoses from the boom manifold
   up each pylon and pressure-test every motor loop before the first motor run.

### F8 Sheet-metal battery boxes (BAT-BOX, BAT-LID, IP)
1. Send DXF flat patterns (794 x 998 mm for the box) to the waterjet supplier; deburr on receipt.
2. Bend on a brake (radius 2 t), rivet corners with CherryMAX, seal with polysulfide; mica liner bonded inside.
3. Fit the vent BAT-VENT with its burst disc; mount points to the floor inserts.

### F9 Battery packs (BAT-TIER1/2, BMS, HV-SW) - packs per design/selected_design.json (iteration 3.2: 5 x 175s3p)
1. Cell incoming test: OCV and AC IR on 100 %, capacity on 2 %; reject outliers; group into p-groups by IR.
2. Insert cells in the waterjet-cut G10 holder plates; laser- or resistance-weld nickel-plated copper strips (pull test
   each shift); sense leads to every p-group with fuse links.
3. Install the BMS (Orion BMS 2), contactors, fuse and precharge; insulation resistance test; first charge with BMS logging.
4. Close in the box with the cold plates BAT-CP and thermal pads; thermal soak test.

### F10 FDM moulds and glass fairings (INV-POD, NAC, LG-FAIR, SPIN-P, COOL-FAIR, BM-CAP)
1. Print the mould sections (ASA, 4 walls, 15 % infill), bolt and seal the split flanges, sand, epoxy-coat, wax, PVA.
2. Lay 2 plies glass, peel ply, cure at room temperature (ASA tools allow a mild post-cure, PLA does not).
3. Trim, fit and screw to the saddles/fittings.

### F11 Seats and crush blocks (SEAT-SHELL, SEAT-EA, NOSE-EA)
1. Machine the seat plugs T-SEAT-PLUG*, seal; lay 6 plies carbon twill (4 mm) with potted hard points; bag, cure.
2. Bond and machine the H100 crush blocks (160 mm stroke) and the H80 nose block; glass-wrap with tear strips.
3. Cut CONFOR cushions to template; fit harness anchors HA-FIT and seat fittings SEAT-FIT.

### F12 Landing gear (LG-*)
1. Send T-XT-TEMPL and the drawing to the tube shop; bend the four LG-LEG tubes; check each on the template.
2. Machine LG-LEGEND, LG-SADDLE (bushed 20 mm pivot), LG-DCL, LG-DUP, LG-SKCL; bond/pin the leg ends.
3. Cut the skid tubes, plug the ends, fit the UHMW shoes; install the oleo dampers (spherical bearings).
4. Drop-test one corner before first hover (WP F limit drop 0.33 m).

### F13 Canopy and windows (CAN-F, CAN-R, WIN-L)
1. Machine the stacked MDF plug T-CAN-PLUG1..4, seal and polish; ship with the PC sheet to the forming shop (PC dried 120 C 12 h).
2. Trim with printed templates, drill oversize, rubber grommets; bond into CAN-FRM; fit hinges and latches.
"""

# ------------------------------------------------------------------ labour (WP D hours, re-allocated to tasks)
import re as _re
_cb = (ROOT / "sizing/results/cost_breakdown.md").read_text()
H = {m.group(1).strip(): float(m.group(2).replace(",", "")) for m in _re.finditer(r"\|\s*([^|]+?)\s*\|\s*\**([\d,]+)\**\s*\|", _cb.split("Labour (own shop)")[1].split("At USD")[0])}
def h(k):
    return H.get(k, 0.0)
DES = json.loads((ROOT / "design/selected_design.json").read_text())
N_CELLS = DES["battery"]["series"] * DES["battery"]["parallel"]
N_PACKS = DES["battery"]["independent_packs"]
TASKS = [  # id, name, lane, hours, depends-on, note  (hours from sizing/results/cost_breakdown.md)
    ("P0", "Quotes and long-lead orders (motors, inverters, rotors, parachute, cells)", "M", 0, [], "lead times by quote; no shop hours"),
    ("T1", "Tooling: cap jigs, templates, cradles, drill templates, V-blocks", "B", 0.5 * h("tooling"), [], "WP D tooling, half"),
    ("Q1", "Process qualification: coupons for laminates, bonds, inserts", "A", 60, [], "part of the 10 % QC"),
    ("T2", "Tooling: shell plugs, seat plugs, canopy plug, FDM moulds", "B", 0.5 * h("tooling"), ["T1"], "WP D tooling, half"),
    ("F4", "Flat sandwich panels and cabin tub", "A", 0.47 * h("made parts: fuselage"), ["Q1", "T1"], "fuselage, panels share (estimate 47 %)"),
    ("W1", "Wing cores, spars (caps, webs) and spar proof test", "A", 0.5 * h("made parts: wing"), ["T1", "Q1"], "wing, half"),
    ("M1", "Machined fittings batch 1: wing root, boom clamps, pylons, motor plates, boom-end plugs", "B", h("made parts: rotor pylons mounts"), ["T1"], "rotor pylons/mounts"),
    ("W2", "Wing skins, ribs, control surfaces, tips", "A", 0.5 * h("made parts: wing"), ["W1"], "wing, half"),
    ("B1", "Booms: cut, splice, over-wrap, clamps bonded", "B", h("made parts: booms"), ["M1", "T1"], "booms"),
    ("F5", "Shell, hatches, canopy frame on the plugs", "C", 0.53 * h("made parts: fuselage"), ["T2", "F4"], "fuselage, shell share"),
    ("M2", "Machined fittings batch 2: gear, seats, parachute, tail clamps", "B", h("made parts: landing gear"), ["M1"], "landing gear"),
    ("TL", "Tail surfaces, tail spar, assembly to booms", "A", h("made parts: tail"), ["B1", "W2"], "tail"),
    ("SE", "Seats and crush blocks", "C", h("made parts: seats"), ["T2"], "seats"),
    ("BA", f"Battery packs ({N_CELLS:,} cells, {N_PACKS} packs), boxes", "C", h("battery assembly"), ["P0"], "battery assembly"),
    ("MI", "Parachute install, cooling, avionics tray, pusher pods and props", "B",
     h("made parts: parachute") + h("made parts: cooling") + h("made parts: avionics") + h("made parts: pusher motor") + h("made parts: pusher propeller"),
     ["F4", "M2"], "parachute + cooling + avionics + pusher"),
    ("CO", "COTS installation (motors, inverters, rotors, avionics, gear dampers)", "C", h("COTS installation"), ["B1", "MI", "P0"], "COTS installation"),
    ("WI", "HV and LV wiring", "C", h("HV and LV wiring"), ["CO", "BA"], "wiring"),
    ("FA", "Final assembly, rigging, weight and balance, systems ground test", "A", h("final assembly, rigging, systems test"), ["WI", "TL", "F5", "SE"], "final assembly"),
    ("Q2", "Quality control and inspections (rest of the 10 %)", "Q", h("quality control (10 %)") - 60, [], "QC spread over the build"),
]
LANES = {"A": "composites lead", "B": "CNC / metal and tooling", "C": "systems / composites 2", "M": "procurement", "Q": "QC (shared)"}
H_WEEK = 40.0


def schedule():
    end, start = {}, {}
    lane_free = defaultdict(float)
    for tid, name, lane, h, dep, note in TASKS:
        if lane == "Q":
            continue
        s = max([end[d] for d in dep] + [lane_free[lane] if lane != "M" else 0.0])
        if tid == "BA":
            s = max(s, 10.0)          # cells and BMS arrive (lead time estimate 10 weeks, confirm by quote)
        if tid == "CO":
            s = max(s, 16.0)          # MGM motors/inverters assumed at week 16 (estimate, to confirm by quote)
        d = h / H_WEEK if h else 0.0
        start[tid], end[tid] = s, s + d
        if lane != "M":
            lane_free[lane] = s + d
    tot = max(end.values())
    start["Q2"], end["Q2"] = 0.0, tot
    return start, end, tot


def main():
    rows = []
    by_fam = defaultdict(list)
    for p in PARTS:
        f = family(p)
        by_fam[f].append(p["id"])
        mf = p.get("machine_fit", {})
        mach = MACHINE.get(mf.get("machine"), "-")
        if p["process"] == "composite-layup":
            mach = "lay-up bench, vacuum pump"
        if p["process"] == "COTS":
            mach = "-"
        fits = "" if mf.get("fits", True) else " (DOES NOT FIT)"
        rows.append((p["group"], p["id"], p["name"], p["qty"], SHOP.get(p["process"], p["process"]) + ("" if not p.get("tooling") else " - tooling"),
                     mach + fits, p["material"], round(p["mass_kg_each"], 3), "x".join(str(round(x)) for x in p["envelope_mm"]), f))
    start, end, tot = schedule()
    weeks = math.ceil(tot)
    total_h = sum(t[3] for t in TASKS)

    cad_des = CADJ.get("design", {}) or {}
    stale = abs((cad_des.get("mtow_kg") or 0) - DES["mass_kg"]["mtow"]) > 1.0
    L = ["# E8-200 manufacturing plan (per part)", "",
         (f"> WARNING: the per-part table below comes from cad/parts.json generated for '{cad_des.get('name')}' (MTOW "
          f"{cad_des.get('mtow_kg')} kg), not yet for the frozen design '{DES['name']}' (MTOW {DES['mass_kg']['mtow']:.0f} kg). "
          "Labour hours and the schedule follow the frozen design. Re-run this script after the CAD rebuild." if stale else ""), "",
         "Generated by [build_manufacturing.py](build_manufacturing.py) from [cad/parts.json](../cad/parts.json) "
         f"({len(PARTS)} part types). Process selection and rationale: [MANUFACTURING_METHODS.md](MANUFACTURING_METHODS.md); "
         "materials and prices: [bom/BOM.md](../bom/BOM.md); vendor questions: [QUOTES_TO_REQUEST.md](QUOTES_TO_REQUEST.md).", "",
         "Legend: **CNC (our 3-axis)** = in-house router/mill; **FDM (our printers)**; **Composite lay-up (in-house)** = wet lay-up "
         "and vacuum bagging; **Outsourced** = waterjet/laser, tube bending, thermoforming, surface treatment; **Bought** = COTS.",
         "", f"Shop limits from the CAD: router bed {LIM['cnc_bed_mm']} mm, metal CNC {LIM['cnc_metal_mm']} mm, FDM {LIM['fdm_mm']} mm, "
         f"hot-wire bow {LIM['hotwire_bow_mm']} mm, foam block {LIM['foam_block_mm']} mm, tube stock {LIM['tube_stock_mm']} mm.", "",
         "## Process count", "", "| Where | part types | instances |", "|---|---|---|"]
    for k, v in CADJ["process_count"]["aircraft"].items():
        L.append(f"| {SHOP.get(k, k)} | {v['unique']} | {v['instances']} |")
    for k, v in CADJ["process_count"]["tooling"].items():
        L.append(f"| tooling: {SHOP.get(k, k)} | {v['unique']} | {v['instances']} |")
    L += ["", "## Process families: step by step", STEPS.strip(), "", "## Inspection by family", "",
          "| Family | Inspection | Parts |", "|---|---|---|"]
    for f in sorted(by_fam):
        ids = by_fam[f]
        L.append(f"| {f} | {INSPECT.get(f, '-')} | {', '.join(ids[:14])}{' ...' if len(ids) > 14 else ''} |")
    L += ["", "## Build sequence and schedule", "",
          f"Labour hours are the WP D bottom-up estimate ({total_h:,.0f} h incl. tooling and QC; sizing/results/cost_breakdown.md), "
          "re-allocated to build tasks. Three people at 40 h/week (lanes A, B, C), QC shared. Purchased-part arrival weeks are "
          f"placeholders until the quotes return. Duration about **{weeks} weeks**.", "",
          "| ID | Task | Lane | Hours | Depends on | Start wk | End wk | " + " ".join(f"{w}" for w in range(0, weeks + 1, 2)) + " |",
          "|---|---|---|---|---|---|---|" + "---|"]
    for tid, name, lane, h, dep, note in TASKS:
        s, e = start[tid], end[tid]
        bar = "".join("█" if (w + 2 > s and w < e) else "·" for w in range(0, weeks + 1, 2))
        L.append(f"| {tid} | {name} ({note}) | {LANES[lane]} | {h:.0f} | {', '.join(dep) or '-'} | {s:.1f} | {e:.1f} | `{bar}` |")
    L += ["", f"Total {total_h:,.0f} h. Cash cost of the hours is not in the BOM; at the WP D rate of USD 55/h it is USD {total_h*55:,.0f}.", "",
          "## Per-part table", "",
          "| Group | ID | Part | Qty | Where | Machine | Material | kg each | Envelope mm | Family |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| " + " | ".join(str(x) for x in r) + " |")
    L += ["", "Part notes (lay-up schedules, hole patterns, joints) are in each part's `notes`/`settings` in cad/parts.json and in the "
          "3-D viewer (docs/index.html).", ""]
    (ROOT / "manufacturing/MANUFACTURING.md").write_text("\n".join(L))
    print(f"MANUFACTURING.md: {len(rows)} parts, {total_h:.0f} h, {weeks} weeks")


if __name__ == "__main__":
    main()
