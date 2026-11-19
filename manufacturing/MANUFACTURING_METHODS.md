# E8-200 manufacturing method guide (WP P, pass 1)

> Pass 2: the per-part plan for the frozen design (process, machine, step-by-step, inspection, schedule) is in
> [MANUFACTURING.md](MANUFACTURING.md); vendor questions in [QUOTES_TO_REQUEST.md](QUOTES_TO_REQUEST.md); priced BOM in
> [bom/BOM.md](../bom/BOM.md). This guide keeps the process-selection rationale.

Scope: which process to use for each part class of a 500-900 kg crewed lift + cruise eVTOL built by a small team
with a 3-axis CNC router/mill and FDM printers, why that process is the cheapest robust choice, what tooling it
needs, an hour estimate, the quality checks, and where the CNC and printers come in. Part-level instructions (per
part ID, plies, settings) follow in pass 2, once the 3-D model (`cad/parts.json`) exists, in the same style as the
subscale build's [MANUFACTURING.md](../../E8-eVTOL-Build/MANUFACTURING.md).

Constraints (from [requirements.yaml](../requirements/requirements.yaml)): in-house 3-axis CNC (aluminium, plywood,
MDF, tooling foam, wax) and FDM (PLA/PETG/ABS/ASA/PA-CF); allowed: wet lay-up and vacuum bagging over CNC/foam/printed
tools, foam-core composites, COTS carbon tubes, aluminium sheet/extrusion with rivets and bonding, outsourced
laser/waterjet flat parts, outsourced 4130 welded tube if justified. Avoid: autoclave prepreg, metal printing,
5-axis machining, custom castings. Prefer: few distinct parts, symmetry, flat-pattern parts.

Material prices quoted below are from [bom/CATALOG.md](../bom/CATALOG.md) (sources there).

## 1. Process selection summary

| Part class | Process (baseline) | Why this one | Tooling | In-house / out | Labour estimate* |
|---|---|---|---|---|---|
| Wing panels (2, removable) | Moldless foam-core sandwich: CNC hot-wire or CNC-routed foam cores, wet-laid glass/carbon skins, vacuum bagged; constant chord | One pair of rib templates serves every panel; no female mould; proven in amateur-built two-seat composite aircraft (Rutan VariEze/Long-EZ method) | CNC-cut MDF rib templates, hot-wire bow, CNC MDF cradle jigs, vacuum pump and bagging kit | in-house | 250-350 h |
| Wing spar | I-beam: wet-laid unidirectional carbon caps in a CNC-machined MDF cap jig + foam core shear web with +/-45 carbon or glass; root fittings in machined 6061-T6/7075 plate, bonded and bolted | Uses the full wing depth (a round tube in a 15 % thick wing uses only part of it); caps are straight, constant-width lay-ups | CNC MDF cap jig and web jig; drill templates for root fittings | in-house (fittings: in-house CNC or job shop) | included above + 40-60 h |
| Lift-rotor booms (2) | COTS roll-wrapped carbon tube 76-102 mm (DragonPlate / Rock West), local UD carbon over-wrap where FEA needs it | No tooling, known geometry and mass; tube price USD 387-645 per length | Printed/CNC alignment jig on a strongback; drill guides | buy + in-house | 60-100 h incl. fittings |
| Boom-to-wing and boom-to-tail fittings | 2.5-D machined 6061-T6 split clamps / saddles, bonded (EA 9394) and through-bolted (AN) | 3-axis machinable, inspectable, replaceable; avoids custom castings | soft jaws, CNC fixtures; printed drill templates | in-house CNC (or job shop) | 40-80 h |
| Motor mounts and rotor pylons | Machined 6061-T6 motor plate + short carbon-tube or folded-aluminium pylon; motor bolt pattern from datasheet | Flat-pattern 2.5-D parts; one design repeated 8 times (identical left/right) | CNC fixture plate; torque/witness procedure | in-house CNC; waterjet blanks optional | 40-60 h |
| Cabin primary structure (keel, floor, seat bulkheads, parachute and gear hard points) | Flat sandwich panels: vacuum-bagged carbon or glass on Divinycell H80, laminated as large sheets then CNC-routed to shape; tab-and-slot assembly, bonded with fillets and tapes | Flat panels are the cheapest sandwich to make well; CNC cutting gives accurate, repeatable parts and self-jigging joints | flat bagging table (MDF/melamine or glass), CNC router | in-house | 200-300 h |
| Cabin outer shell and fairings | Thin glass (2-3 plies) wet lay-up over CNC-machined foam plugs (moldless) or in FDM-printed/CNC-MDF single-sided moulds for small repeated parts | Non-primary structure; shape freedom; no large moulds needed | foam blocks, printed mould sections sealed with epoxy and release agent | in-house | 200-300 h |
| Cabin cage (option) | Outsourced 4130 welded-tube cage carrying seats, harness, parachute bridle and gear | Use only if WP F shows the flat-panel tub cannot meet the crash/hard-point loads economically; common practice on light helicopters/gyroplanes | welding jig at the vendor; in-house CNC tube-notch templates | outsourced | vendor + 30 h |
| Tail (H/V between booms) | Same moldless foam-core method as the wing, constant chord, carbon UD caps; surfaces hinged on COTS piano hinge or machined hinge brackets | Re-uses wing tooling method; small parts | hot-wire templates, MDF cradles | in-house | 80-120 h |
| Landing gear | Skids: straight 6061-T6 skid tubes + two outsourced-bent cross tubes, machined clamp saddles; wear shoes; optional clip-on ground-handling wheels | Helicopter practice; cross tubes absorb the landing energy by bending; no castings | bending by a tube shop; printed drill templates | outsourced bending, in-house rest | 40-60 h |
| Battery boxes (>= 2) | Folded aluminium sheet boxes from waterjet/laser flat patterns, riveted (CherryMAX/solid) and sealed, fire-resistant liner, vent to outside, cold plate or air ducts | Flat patterns cost little outsourced; metal box contains and conducts heat; easy to inspect | press-brake (outsourced or in-house hand brake), rivet tools | outsourced cutting, in-house assembly | 40-60 h |
| Seats | Wet-laid carbon/glass seat shells over CNC foam plugs on a crushable stroke zone; CONFOR CF-45/47 cushions | Energy absorption is designed in the pan + stroke zone; COTS foam | CNC foam plug | in-house | 30-50 h |
| Canopy / windows | Thermoformed polycarbonate (or PETG for trials) over a CNC-machined MDF plug; side windows cold-curved single-curvature | Free-blowing/drape forming of a large bubble needs an oven bigger than in-house equipment | CNC MDF plug, frame | forming outsourced to a plastics shop; trimming in-house | 30-60 h |
| Tooling and jigs (all) | CNC MDF/plywood jigs, printed drill and alignment templates | Accuracy without 5-axis or large moulds | - | in-house | 100-150 h |

\* Labour estimates are team planning figures for one prototype airframe (structure only; systems, wiring and
assembly are excluded), basis: lay-up area and CNC/CAM time scaled from the E8-S subscale build. For calibration, Van's
quotes about 800 h to build a complete RV-12iS kit with factory-made parts ([Van's](https://www.vansaircraft.com/time-to-build/));
a one-off composite structure built from raw materials should be expected to take more. Total structure: about
1,100-1,600 h (estimate); to be replaced by a bottom-up estimate from the CAD part list in pass 2.

## 2. Part classes in detail

### 2.1 Wing panels and spar

- **Method.** Constant-chord panels so that a single pair of root/tip templates (CNC-cut MDF or aluminium) cuts every
  foam core with a hot wire, or the cores are CNC-routed from block foam in two halves. Spar slot cut in the core;
  I-beam spar made separately: unidirectional carbon caps wet-laid in a CNC-machined MDF cap jig, shear web of foam
  with +/-45 carbon or glass, then bonded into the core. Skins: +/-45 and 0/90 glass or carbon wet-laid on the core,
  peel ply and vacuum bag on the cradle. This is the Rutan "moldless" sandwich method
  ([EAA book](https://shop.eaa.org/products/moldless-composite-sandwich-aircraft-construction),
  [EAA composite articles](https://www.eaa.org/eaa/aircraft-building/builderresources/while-youre-building/building-articles/composite/building-composite-aircraft-part-1)).
- **Why.** No female mould, low tooling cost, repeatable cores; the wing must be removable for road transport
  (footprint 9 m), and constant-chord panels make the left/right panels mirror images built on the same jig.
- **Core foam.** PVC (Divinycell H80) or polyurethane/XPS for non-load-bearing fill; never polystyrene with
  vinylester (it dissolves; [EAA](https://eaa.org/eaa/aircraft-building/BuilderResources/while-youre-building/building-articles/composite/Part-1-Working-With-Composites)). Epoxy (MGS L285) is the laminating resin.
- **Root joint.** Machined aluminium spar-root fittings (2.5-D, two set-ups) bonded and bolted to the caps; drilled
  through CNC-made drill templates on the assembled panel, then reamed. Wing pins are COTS AN bolts/clevis pins.
- **Tooling.** Rib templates, hot-wire bow (constant-temperature supply), CNC MDF cradles (upper/lower), spar-cap jig,
  vacuum pump, bagging film, breather, peel ply.
- **Quality.** Witness coupon from every spar-cap and skin batch (cured beside the part; tension/short-beam shear test
  for the first batches, Barcol hardness for every batch); resin mix log (ratio by weight, batch, temperature, pot
  time); part weight versus planned fibre/resin weight; tap test of skin-to-core bond; spar proof-load test to limit
  load before closing the panel; dimensional check of twist and incidence on the jig.

### 2.2 Booms, fittings, motor mounts and rotor pylons

- **Method.** COTS roll-wrapped carbon tubes as booms (76-102 mm ID class). Where FEA asks for more bending stiffness,
  an in-house UD carbon over-wrap is wet-laid on the tube and shrink-taped/bagged. All joints are machined aluminium
  split clamps or saddles: inside surface abraded and primed, bonded with EA 9394 and through-bolted with bushings
  to avoid crushing the tube. Motor plates are 2.5-D machined 6061-T6 with the motor bolt circle; the rotor pylon is a
  short tube or folded aluminium channel so the rotor plane is clear of the wing and cabin.
- **Why.** No moulds; tube mass and stiffness are known; identical parts at all 8 rotor stations; aluminium fittings
  are inspectable and replaceable and carry concentrated loads well.
- **Tooling.** Strongback and alignment jig (printed V-blocks and laser line) to set rotor-shaft cant and spacing;
  CNC fixture plates; printed drill templates indexed on the tube.
- **Quality.** First-article dimensional inspection of fittings (calipers/CMM arm if available); bond-line thickness
  controlled by glass beads; one boom/fitting joint built as a test article and loaded to ultimate (1.5 x limit) plus a
  vibration/fatigue test at the rotor 1P and blade-pass frequencies; torque-seal on every bolt; rotor shaft
  alignment check after assembly.

### 2.3 Cabin structure and shell

- **Method (baseline).** Primary structure from flat sandwich: laminate full sheets of carbon or glass on Divinycell
  H80 on a flat table under vacuum, then CNC-route keel beams, floor, seat bulkheads and battery bay walls with
  tab-and-slot features so the parts locate each other. Join with thickened-epoxy fillets and glass tapes; insert
  potted aluminium or phenolic hard points where bolts pass through the core. The aerodynamic shell is a light
  (2-3 ply) glass skin laid over CNC-machined foam plugs (moldless) and bonded to the tub.
- **Why.** Flat panels give high quality with simple tooling; CNC cutting makes the assembly self-jigging; the shell
  carries little load so it can be thin and quick.
- **Option.** If WP F shows that the seat, harness, parachute and gear hard points need a cage, an outsourced 4130
  welded-tube cage with composite fairings is used (vendor welds to our notched-tube drawings; in-house printed tube
  notch templates).
- **Quality.** Panel coupons per laminate batch; void check by tap test and backlight (glass); insert pull-out test
  on samples of each insert type; dimensional check of seat rail and harness anchor positions against the CAD.

### 2.4 Tail

Same method as the wing (constant chord, hot-wire cores, UD carbon caps, wet-laid skins). Hinges are COTS piano hinge
or machined aluminium hinge brackets bonded and bolted. Mass-balance and free-play checked before closing.

### 2.5 Landing gear

Skid gear: two straight 6061-T6 skid tubes, two bent cross tubes (bent by a tube shop to our drawing), machined
clamp saddles to the cabin keel, bolt-on wear shoes. The cross tubes are sized by WP F to absorb the 3 g landing case
by elastic bending and the crash case by plastic bending, as on helicopter skid gears (aluminium skid tubes are COTS
spares for certified helicopters, e.g. [DART Aerospace](https://dartaerospace.com/collections/skidtubes-407/skidtubes-float-w-standard-wearplates.oembed)).
Clip-on ground-handling wheels are used for moving the aircraft. A wheeled gear (Matco W51LT wheels and brakes,
[Aircraft Spruce](https://www.aircraftspruce.com/catalog/pnpages/06-00079.php)) is only justified if rolling take-off
is required. Quality: drop test of one gear assembly at the design sink speed before first hover.

### 2.6 Battery boxes

Flat patterns in 5052 or 6061 aluminium sheet are outsourced to waterjet/laser, bent on a brake, riveted and sealed.
Each box has a fire-resistant liner. Cells are held by machined or laser-cut G10/FR4 or aluminium frames; printed
cell holders are not used in flight packs. A vent path routes gases overboard away from the
cabin. Each box carries its BMS, contactors and fuse. Quality: leak/vent check, insulation-resistance test of the
assembled pack, thermal soak test with the BMS logging. (Thermal-runaway containment practice: see the H55 test
campaign reported by [electrive](https://www.electrive.com/2026/02/03/h55-completes-certification-tests-for-propulsion-battery-modules-for-electric-aircraft).)

### 2.7 Fairings, nacelles and spinners

Small repeated parts (motor fairings x 8) are laid up in FDM-printed single-sided moulds (ASA or PETG, sanded,
sealed with epoxy, waxed and PVA-released), cured at room temperature. Larger fairings are moldless over CNC foam.
Non-structural covers (cable glands, sensor housings) are printed directly in ASA or PA-CF.

### 2.8 Canopy and windows

A CNC-machined MDF plug (sealed) is used by a plastics shop to drape- or blow-form polycarbonate; PETG may be formed
in-house for fit trials (it forms at about 170 C without pre-drying per supplier data). Trimming with a router and
printed trim templates; edges drilled oversize and fixed with rubber grommets to allow thermal movement.

### 2.9 Rotor blades (not made in-house for flight)

Rotor blades are bought (E-PROPS / Sensenich / Helix, see catalog). In-house CNC-machined laminated wood or
wet-laid composite blades are physically feasible (two-sided machining with a flip jig and dowel registration, or
lay-up in CNC-machined split moulds), but flight use would require the strength, vibratory-stress, fatigue and
endurance programme of [ASTM F2506](https://store.astm.org/f2506-22.html), [FAA AC 20-66A](https://www.faa.gov/sites/faa.gov/files/2022-11/AC20-66A.pdf)
and composite-blade fatigue substantiation guidance in the AC 35.37-1 series
([FAA](https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/22940)).
Lift rotors on a lift + cruise aircraft also run in edgewise flow during transition, which adds 1P cyclic loading.
In-house blades are therefore limited to ground test rigs and whirl-tower work.

## 3. How the in-house CNC and FDM printers are used

| Use | 3-axis CNC | FDM |
|---|---|---|
| Foam cores | CNC-routed cores in two halves; hot-wire templates | - |
| Plugs and moulds | MDF/tooling-foam plugs for shell, seats, canopy; MDF cradles | Single-sided moulds for small repeated parts (nacelles, ducts) |
| Jigs | spar-cap jig, wing cradles, boom strongback, flat lay-up table edge stops | V-blocks, alignment cradles, cable guides |
| Drill / trim templates | aluminium templates for critical holes (wing pins, root fittings) | printed templates indexed on tubes and panels for non-critical holes and trims |
| Flat sandwich parts | routing of pre-laminated panels (dust extraction, diamond/compression cutters) | - |
| Metal fittings | 2.5-D 6061-T6 clamps, saddles, motor plates, hinge brackets (if the machine cuts aluminium; else a job shop) | - |
| Non-structural parts | - | ASA/PA-CF brackets, grommets, covers, switch panels |

Printed parts are never used as primary structure; PLA tooling is limited to room-temperature cure (PLA softens far
below an epoxy post-cure); ASA or PA-CF tools are used where a warm post-cure is planned.

## 4. Materials and allowables

- Allowables for wet lay-up are lower and more scattered than prepreg; the team derives its own design values from
  coupons made with the production resin, fabric and process, and keeps process control records. This follows the
  intent of FAA [AC 20-107B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC20-107B.pdf) (material
  and process control, environmental effects, damage tolerance) even though the aircraft is built under an
  experimental certificate.
- Repair and standard-practice references: FAA [AC 43.13-1B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43.13-1B_w-chg1.pdf)
  (hardware, riveting, bonding) and the FAA [Aviation Maintenance Technician Handbook - Airframe](https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/amt_airframe_handbook)
  (composite chapter); vacuum-bagging practice: [West System Vacuum Bagging Techniques](https://www.westsystem.com/app/uploads/2023/06/2023.05_WS_Vacuum-Bagging-Techniques-Manual.pdf).
- Resin: MGS L285 + H285/H287 for structure, West System 105/206 for tooling and fillets; foam: Divinycell H80
  (Rohacell IG-F where weight is critical); fabrics: 193 g/m2 carbon twill and UD carbon tape; adhesive: EA 9394
  for metal-to-composite; hardware: AN/MS.

## 5. Quality plan (all composite and bonded work)

1. Material receipt log (batch, shelf life, storage temperature).
2. Shop environment log (temperature and humidity at lay-up; minimum temperature per resin TDS).
3. Resin mix log by weight; one witness coupon per lay-up session for structural parts.
4. Cure and post-cure temperature log.
5. Visual and tap-test inspection with a marked-up inspection map; backlighting for glass.
6. Weight of every part recorded against the CAD mass (`cad/parts.json`) - feeds WP D mass properties.
7. Bonded joints: surface preparation record (abrade, solvent wipe, primer), bond-line thickness control, a lap-shear
   coupon per bonding session.
8. Proof tests: spar to limit load, one boom joint and one gear assembly to ultimate, insert pull-out samples.
9. Torque log and torque-seal on all fasteners; independent inspection before closing any structure.

## 6. Manufacturing risks

| Risk | Mitigation |
|---|---|
| Wet lay-up variability (voids, resin-rich laminates) | vacuum bagging, weighed resin, coupons, conservative allowables |
| Moldless surfaces need much filling and sanding | accept for prototype; constant-chord panels; use female moulds only for parts made more than a few times |
| CNC cannot cut aluminium accurately | outsource the 2.5-D fittings to a job shop (drawings from the same CAD) |
| Tube-to-fitting bonds | test joint to ultimate and in fatigue before building the set |
| Large canopy forming needs an oven | outsource forming; in-house only trims |
| Battery box fire safety | metal box, liner, vent path, BMS-controlled contactors; test before flight |
| Labour underestimated | bottom-up estimate in pass 2; track actual hours per part class |
