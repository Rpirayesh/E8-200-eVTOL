# WP F – Structures (FEA)

Status: **phase 3.3 final** (final CAD checked; all strength margins positive) – previously phase 3.2, frozen design iteration 3.2 "T8" (MTOW 1,169.5 kg, twin boom-tail pushers), [results](#phase-32-results-design-iteration-32-t8-frozen-2026-11-16); earlier phases below for traceability – design iteration 3 (MTOW 1,042.8 kg, 8 x REB 60 / 1.85 m rotors, 8.1 m wing) re-analysed
and re-sized; results in [Phase 3 results](#phase-3-results-design-iteration-3-current). The phase 2 section (iteration 1) is
kept for traceability. Phase 1 (tool verification, allowables, load definitions) is unchanged.

Verification evidence: [`validation/fea/README.md`](../validation/fea/README.md).

## Files

| File | Purpose |
|---|---|
| `frame.py` | 3-D beam/frame FE solver (6 DOF/node): Euler-Bernoulli or Timoshenko, consistent or lumped mass, free-free static with inertia relief (rigid-body modes, gravity), shift-invert modes, linear (Euler) buckling, stress recovery for round / rectangular / cap-and-web sections |
| `ccx.py` | CalculiX 2.23 interface: structured hex20 / quad8 meshes, gmsh `.geo` -> `.inp` meshes, deck helpers (materials, orientations, composite shell sections), runner (6 threads), `.frd` / `.dat` readers (fields, eigenvalues, buckling factors, integration-point stresses) |
| `clt.py` | Classical Lamination Theory: ABD, ply stresses/strains, max-stress / Tsai-Wu / max-strain indices, sandwich beam D and S |
| `materials.py` -> `materials.json` | Material properties and design allowables with sources and knock-downs (edit the script, not the JSON) |
| `loads.py` | V-n diagram and flight cases, rotor/hover cases, landing, crash (CS-23.561), parachute opening; parametric on mass and geometry |
| `geometry.py` | Reader of `design/geometry.json`: planform helpers, mass breakdown, beam sections from section specs |
| `airframe.py` | Global beam model built from `geometry.json`: all load cases, member margins, fitting loads, modes |
| `design_inputs.json` | FEA-owned inputs not in geometry.json: parachute opening load (47.4 kN), pylon section, rotor mass split, battery crash g, drop height, min gauges, MS targets |
| `sizing.py` -> `results/sizing_update.json` | strength sizing loop on the beam model (spar caps/webs per station, skin, boom over-wraps, tail spar, pylons, gear cross tube); output in geometry.json section format |
| `gear.py` -> `results/gear.json` | skid-gear landing-energy (drop) check |
| `fuselage.py` -> `results/fuselage.json` | cabin sandwich structure (keels, floor, wing-root frames, tail cone), battery boxes and mounts, seat attachment |
| `parts.py` -> `results/parts.json` | CalculiX C3D10 models of the six critical fittings (P1-P6) + analytic lug/bolt checks, PNG and GLB stress views in `docs/models/fea/` |
| `dynamics.py` -> `results/dynamics.json` | free-free modes, Campbell diagram, divergence, modal flutter (strip Theodorsen), pusher whirl flutter |
| `parts_cad.py` -> `results/parts_cad.json` | the same fitting analyses on the WP G STEP parts (`cad/parts/<ID>/<ID>.step`): supports and load surfaces found by cylinder radius/axis, loads rotated with the CAD instance matrix |
| `details.py` -> `results/details.json` | iteration-3 detail checks: wing skin wrinkling on the voided XPS cores, spar webs on H45, pylon head, skid and tail clamps, damper hard points, parachute cradle |
| `margins.py` -> `results/margins.json` | every margin in one table (lowest first) and the mass change vs selected_design.json |
| `plots.py` | utilisation and mode-shape figures of the global model |
| `placeholder/geometry_placeholder.json` | Representative 725 kg design (schema example) used to test the chain; **not a design** |
| `results/` | `loads_<tag>.json`, `airframe_<tag>.json` (small); scratch runs live in `fea/.cache/` (git-ignored) |

Run (python: `~/tools/cadenv/bin/python`; CalculiX and gmsh come from `~/tools/envs/cfd` via `~/tools/foamenv.sh`):

```
python fea/materials.py                     # regenerate materials.json
python fea/loads.py [geometry.json [selected_design.json]]
python fea/airframe.py [geometry.json [selected_design.json]] [--tag NAME] [--sizing FILE|none]
# phase 2 chain (frozen design), ~15 min on 6 cores:
python fea/sizing.py; python fea/gear.py; python fea/fuselage.py; python fea/parts.py; python fea/dynamics.py
python fea/airframe.py design/geometry.json --tag design; python fea/plots.py; python validation/fea/verify_dynamics.py
python fea/margins.py
python validation/fea/verify_beam.py        # B1-B7, ~5 s
python validation/fea/verify_ccx.py [C1..C8]  # ~5 min on 6 cores
python validation/fea/verify_loads.py       # L1-L7
python validation/fea/make_report.py        # plots + summary table
```

## Conventions

* Axes: x aft from the nose, y right, z up; SI units (m, kg, N, Pa). Rotor `spin` = +1 counter-clockwise seen from
  above (angular velocity along +axis); the airframe receives the reaction torque `-spin * kQ * T` about the rotor axis.
* Loads from `loads.py` are **limit** loads; `airframe.py` reports **ultimate** results (x 1.5, requirement
  `safety.ultimate_factor`). Emergency-landing (crash) factors are already ultimate.
* Margin of safety MS = F_allowable / (f_ultimate x special factor) - 1, with only the highest pertinent special
  factor (CS-23.619). Fitting loads in `airframe_<tag>.json` are listed both as ultimate and x 1.15 (fitting factor).
* Flight and rotor cases are solved free-free with inertia relief and gravity: the rigid-body accelerations that
  balance lift / thrust / gear / parachute loads are applied to every mass (D'Alembert). The single support node
  reaction is printed as a check (~1e-6 N).

## What `design/geometry.json` must provide

The placeholder file is a complete, working example of the schema. Required (R) and optional (O) fields:

### Top level
| Field | | Meaning |
|---|---|---|
| `mtow_kg` | R | design mass (if the sum of listed masses is lower, the difference is added at the cg as 'unallocated') |
| `limits` | O | `n_pos` (3.8), `n_neg` (-1.5), `n_land` (3.0) – defaults from requirements.yaml |
| `aero` | R | `CLalpha_per_rad`, `CLmax` (clean), `CLmin`, `Cm0` (about c/4, clean), `VC_ms` (EAS), `VD_ms` (O, default 1.4 VC), `cruise_thrust_N`, `gust_altitude_m` |
| `cg` | O | `{x,y,z}`; default: cg of the distributed mass model |
| `torque_fault_factor` | O | motor fault / sudden-stop torque factor on max torque (default 1.25) |

### `wing`
`span`, `root_chord`, `tip_chord`, `x_le_root`, `z_root`, `sweep_le_deg`, `dihedral_deg`, `incidence_deg`, `airfoil`, `t_c`,
`mass_kg` (all R); `area` (O); `root_fittings_y` (R: spanwise station of the wing-fuselage fittings);
`spars` (R, front first, rear last; 2 or more): each `{name, x_c, section_root, section_tip}` – sections are linearly
interpolated root -> tip; `torsion_box` (R): `{skin_t, skin_material, skin_layup ('+-45'|'0/90'|'qi'), depth_factor}`.

### `fuselage`
`x_nose`, `x_tail`, `z_axis`, `mass_kg`, `section` (equivalent beam of the cabin shell / frame, R).

### `booms` (list)
`name`, `y`, `z`, `x_front`, `x_aft`, `mass_kg`, `section` (R). Booms are attached to every spar at the boom station
(wing ribs/saddles); a fitting is created for each spar crossing.

### `rotors` (list, one entry per rotor, coaxial pairs as two entries)
`name`, `boom`, `x`, `y`, `z` (hub), `diameter`, `blades`, `spin` (+1/-1), `max_thrust_N`, `max_torque_Nm`
(or `torque_per_thrust_m`), `rpm_max`, `rotor_inertia_kgm2` (polar, rotating parts), `mass_kg` (motor + rotor + ESC +
mount) – all R; `rpm_hover`, `axis` (default [0,0,1]) – O.

### `pusher` (O)
`x`, `y`, `z`, `axis` (default [-1,0,0]), `spin`, `max_thrust_N`, `max_torque_Nm`, `rpm_max`, `rotor_inertia_kgm2`,
`mass_kg`, `attach` (component name).

### `tail`
`type`, `x_ac` (tail aerodynamic centre, used for trim), `x_spar`, `z`, `span`, `mass_kg`, `spar_section`.

### `landing_gear` (list) and `gear_strut_section`
Contact points `{name, x, y, z, attach, mass_kg}`; the strut joins the contact point to the fuselage beam
(section `gear_strut_section`, or stiff if omitted). Skid cross-tubes are sized in phase 2 with a local model.

### `masses` (list), `seats` (list), `parachute`
* `masses`: every equipment item `{name, kg, x, y, z, attach}` – batteries (one entry per pack), avionics, parachute
  canister, cargo, harness. `attach` = `fuselage`, `wing`, `tail` or a boom name. Optional
  `aft_or_above_occupants` (bool) overrides the automatic crash-factor rule.
* `seats`: `{name, x, y, z, occupant_kg, seat_kg, attach}` – occupant cg position.
* `parachute`: `{n_open_limit (vendor peak opening load / W at max deployment speed), attach: [{name, x, y, z}],
  max_share (O)}`.

### Section specs (`section`, `section_root`, `spar_section`, ...)
| `type` | fields | notes |
|---|---|---|
| `tube` | `od`, `t`, `material` | round tube; material = a `tube`, `isotropic` or `lamina` key of materials.json |
| `rect_tube` | `b` (y), `h` (z), `t_web`, `t_flange`, `material` | Bredt torsion; `<lamina>_qi` / `_45` select a lay-up |
| `cap_web` | `h`, `b_cap`, `t_cap`, `n_web` (1 = C/I spar, 2 = box), `t_web`, `cap_material`, `web_material`, `web_layup` | UD caps + +/-45 webs; web shear stress reported separately |
| `props` | `EA`, `EIy`, `EIz`, `GJ`, `E`, `G`, `m_per_len`, `cy`, `cz` | stiffness-only member |
| `tube_layers` | `id` (or `od`), `layers: [{t, material}]` inside -> out | COTS tube + over-wraps; `<lamina>_45` = +-45 wrap; strain-based allowables (minimum over the layers) |

Spars may give `stations: [{eta, section}]` (eta = |y| / semi-span, piecewise linear) instead of `section_root/tip`;
booms may give `segments: [{x_from, x_to, section}]`. `fea/results/sizing_update.json` uses these forms and is merged
with `fea.geometry.load(path, sizing=...)` (also `rotor_pylon_section`, `tail.spar_section`, `landing_gear_oml.cross_tube`).

Mass bookkeeping: component `mass_kg` values (from the mass budget) are distributed over the component nodes;
the mass implied by the section specs is reported separately (`member_section_mass_kg`) so the sizing loop can update
the budget.

Also needed from `selected_design.json` (or the `aero` block): MTOW, cruise speed, CLmax, CLalpha, Cm0, cruise
thrust; rotor max thrust/torque/rpm from the chosen motor+propeller data.

## Material allowables (summary of `materials.json`)

Design values are ultimate allowables at 60 C wet (worst service condition); full table with sources in the JSON.

| Material | E (GPa) | Design allowables (MPa) | Status |
|---|---|---|---|
| Carbon UD wet lay-up (T700-class, Vf 0.50) | 115 / 6.8 | Xt 575*, Xc 460*, Yt 19, Yc 65, S 30, ILSS 24 | estimate |
| Carbon 0/90 fabric wet lay-up (Vf 0.45) | 52 / 47 | Xt 260*, Xc 208*, S 30 | estimate |
| E-glass fabric wet lay-up (Vf 0.40) | 20 | Xt 100*, Xc 80* | estimate |
| Roll-wrapped CF tube, UD-dominated | 106 | Ft 530*, Fc 408, Fs 36 | datasheet E, Ft; estimate others |
| Roll-wrapped CF tube, twill + UD | 62 | Ft 310*, Fc 248*, Fs 54 | estimate |
| Pultruded CF tube | 125 | Ft 625*, Fc 500*, Fs 24 (no clamps/holes without sleeves) | estimate |
| Divinycell H80 / H100, ROHACELL 71 WF (core) | 0.064 / 0.092 / 0.076 | shear 0.76 / 1.12 / 0.88 | datasheet min x 0.8 |
| Divinycell H45 (spar-box foam) / XPS board (wing cores) | 0.036 / 0.008 | shear 0.37 / 0.16; G 9.6 / 4.8 MPa | datasheet min x 0.8 / typical x 0.85 x 0.8 (estimate) |
| Al 6061-T6 sheet / extrusion | 68.3 | Ftu 290 / 262, Fty 248 / 241, Fsu 186 / 165 (A/S) | MIL-HDBK-5J |
| Al 6061-T6 welded (HAZ) | 68.3 | Ftu 165, Fty 103 | ADM |
| Al 7075-T6 sheet | 71 | Ftu 538, Fty 476, Fsu 324 (A) | MIL-HDBK-5J |
| 4130 N tube / welded | 200 | Ftu 655 / 552, Fty 517 / 414 | MIL-HDBK-5J |
| Bolted bearing, QI carbon fabric | – | Fbru 324, Fbry 227 | estimate |
| EA 9394 / Plexus MA530 (average lap shear) | – | 8.3 / 3.3 | TDS + team rule |
| FDM PLA / PETG / ASA / PA6-CF | 1.6–2.8 | 12–21 | non-structural only |

\* capped by the damage-tolerance strain cut-off (0.5 % tension, 0.4 % compression, 0.8 % shear).

### Knock-down factors and special factors applied

* **Statistical (B-basis approximation, CMH-17-1G ch. 8):** B = mean (1 - k_B CV); with CV 8 % (fibre-dominated)
  and 10–11 % (matrix-dominated) of wet lay-up and k_B ~ 1.8 -> **0.85 / 0.80** of the mean.
* **Environment (hot/wet, 60 C, moisture-saturated, RT-cure laminating epoxy post-cured, Tg wet >= 80 C, light paint):**
  fibre tension **0.95**, compression **0.80**, matrix-dominated **0.75**, matrix moduli **0.90**.
* **Wet lay-up process (part vs coupon):** **0.90** on strength (porosity, Vf and thickness scatter, waviness);
  dropped only with witness-panel coupons from production lay-ups.
* **Damage tolerance:** ultimate design strain cut-off 0.50 % tension / 0.40 % compression / 0.80 % shear
  (BVID and open holes, AC 20-107B); the design allowable is the lower of strength x knock-downs and E x cut-off.
* **COTS tubes:** supplier-cured prepreg, so no process factor; B 0.85 and environment as above (Tg of the tubes
  115–121 C); incoming 4-point-bend test per batch. Local wall buckling checked with 0.3 E t / R.
* **Cores:** datasheet minimum values x **0.80** (60 C, moisture). Face wrinkling and core shear checked in phase 2.
* **Metals:** A (or S) basis for single load paths, B basis for redundant structure (CS-23.613); no temperature
  reduction up to 60 C.
* **Special factors (CS-23.619, highest one only):** fitting **1.15** (CS-23.625; rotor mounts, boom saddles,
  wing-root, gear and parachute fittings); seat/harness attachments **1.33** (CS-23.785(f)); bearing factor **2.0**
  for pinned joints with clearance and vibration (CS-23.623); control-system joints **3.33** (CS-23.693); plain-bearing
  hinges **6.67** (CS-23.657); bonded joints **1.5** (team rule until joint tests exist).
* **Adhesives:** lap shear at max service temperature x 0.8 (scatter, surface preparation) x 0.5 (average-to-peak
  for short stiff overlaps) as average design shear, then the 1.5 bonded-joint factor on the load.
* **Printed parts:** never in a load path whose failure is hazardous; 0.3 x XY strength for jigs and fixtures.

Coupon programme that replaces the 'estimate' values: listed in `materials.json -> policy.coupon_programme`
(D3039, D6641, D3518, D2344, D5766/D6484, D5961, D7136/7137, D1002/D5868, C273/C393/D7249, D3171, tube bend tests).

## Load cases (`loads.py`)

| Group | Cases | Basis |
|---|---|---|
| Flight (V-n) | A (+n at VA), D (+n at VD), G (-n at VG), E (-n at VC), F (0 g at VD), gust +/- at VC (50 ft/s) and VD (25 ft/s), rolling (2/3 nA, 100/75 % semispan) | CS-23.333/.335/.337/.341/.349 (Amdt 4 formulas); n limits +3.8/-1.5; Schrenk span load; tail balance load from the cg moment equation |
| Rotors | hover trimmed; all rotors at max thrust; one motor out in the 1.2 g flare (R7b, iteration 3); pitch / roll / yaw saturation (max vs idle); one motor out (worst rotor, thrust re-allocated by linear programming with force, roll, pitch and yaw trim, max fraction reported for 1.0 g and 1.2 g); motor peak/fault torque; gyroscopic (yaw 2.5, pitch 1.0 rad/s at max rpm, CS-23.371) plus motor-mount check loads | requirements `one_lift_motor_out` |
| Pusher | max thrust + fault torque + gyroscopic | CS-23.371 |
| Landing | level 3 g all gear; with drag 0.25; one side 3 g; side load (1.33 g, 0.5 W / 0.33 W) | CS-23.473/.479/.483/.485; rotor lift 2/3 W from iteration 3 (gear reaction 2.33 W, design_inputs); damped gear energy in gear.py |
| Emergency landing | per item: up 3, forward 9 (18 for items aft of/above the occupants), side 1.5, down 6 g, ultimate; seats x 1.33; AC 23.562 dynamic pulses listed for the seat tests | CS-23.561, CS-23.785(f), 14 CFR 23.561(e) |
| Parachute | opening load n_open x W along aft, aft-up 45, vertical and an asymmetric direction; uneven riser share for the fittings | **n_open = 6 g is a placeholder** until the vendor value at maximum deployment speed is known |

## Placeholder results (phase 1 tool-chain test only)

`python fea/airframe.py` on the placeholder: 297 nodes, 390 elements, mass 725 kg; flight, rotor, pusher,
landing and parachute cases (31) in ~4 s; inertia-relief residual < 1e-5 N; first free-free modes 6.2–12.5 Hz vs rotor
1P 20–28 Hz. The placeholder margins (gear strut and rear-spar web negative, parachute cases driving the booms) only
show that every case runs and is reported; they are **not** design results.


## Phase 3.3 final: final CAD fittings and final global loads

Final CAD build (cad/parts.json, 19 Nov), CalculiX C3D10 on the STEP parts at MTOW 1,350.4 kg (x 1.27 mesh factor), beam model
re-run on the final geometry with the sizing update and the CAD gear leg (`fea/results/airframe_final33.json`, `--tag final33`).

Load inputs. V_D 61.8 m/s EAS: the 63.64 m/s loads are kept (conservative). Lift-rotor structural thrust 4,267 N (was 4,240 N):
the beam model was re-run at 4,267 N with the final rotor data; R8 (all rotors at maximum thrust, torque x 1.25) now sets the
booms at +0.094 (MTOW-scaled), all members stay positive. The flight controller limits thrust to 2,860 N, so R8 at 4,267 N
carries a further factor of 1.49 on the real thrust. MP and MP-EMX (run at 4,240 N) are scaled x 1/1.0064; PY-C re-run at 4,267 N.

| Item | Final MS |
|---|---|
| CH-CRADLE (forward post z 49-114, redrawn, 5.091 kg) | +0.32 (yield at limit +0.82, deflection 1.4 mm) |
| W-FIT-MS 18 mm, R10 fillets / W-FIT-RS | +0.33 / +0.14 |
| PY-C 8 mm wall (4,267 N) | +0.17 |
| CH-ATT-R 15 mm eye plate / W-CHUTE-FIT | +0.24 / +0.28 |
| F-CLV-MS / -RS | +1.15 / +1.30 |
| LG-LEG 76.2 x 2.41 (beam model with the CAD section) | +0.32 |
| LG-DUP / LG-SADDLE / LG-LEGEND / LG-SKCL / LG-SKID | +0.42 / +0.52 / +0.51 / +9.0 / +2.98 |
| TL-CLAMP (FE / socket bearing) | +0.79 / +0.32 |
| MP / MP-EMX / PY-HEAD flange / PB-PLUG | +0.91 / +5.08 / +0.50 / +5.64 |
| SEAT-FIT / BC-W / BC-WR / W-PIN-M (bending) / W-CHUTE-ANG | +0.33 / +4.73 / +1.90 / +0.27 / +1.07 |
| Members: booms (R8) / spar main / tail spar / spar rear | +0.094 / +0.10 / +0.10 / +0.11 |

CH-CRADLE: first drawn with the forward post above the ring (-0.49, no load path); redrawn from the beam web (z 49) into
the front of the ring (z 114), one fused body: +0.32.

Margin criterion. All margins are at ultimate (limit x 1.5; fittings x 1.15 more) against allowables that already contain the
composite knockdowns (B-basis, environment, process, strain cut-offs), so MS > 0 is the pass criterion. The `ms_target`
(composite 0.115, metal 0.05) in `fea/design_inputs.json` is only the sizing-loop target that makes the fixed-point iteration
stop with some reserve; it is not a requirement. The booms at +0.094 pass.

Overall minimum strength margin: +0.094 (booms, R8 at 4,267 N); no strength margin below zero. Frequency placement remains
open (GVT).

## Phase 3.3C results: re-check of the revised fittings (design MTOW 1,350.4 kg)

The revised CAD parts were run in `fea/parts_cad.py` (6 GB, 2 threads, one part at a time; same meshes; x 1.27 mesh factor).
Where a revision did not clear, the fix was modelled on a modified copy of the CAD STEP (`FEA_CAD_PARTS` / `FEA_RESULTS`
options, results in `fea/results/parts_cad_fix_checks.json`) and is given to CAD as the drawing change.

| Part | CAD 3.3C as drawn | Cause | Required change (checked in FE) | MS with change | Mass vs 3.3C |
|---|---|---|---|---|---|
| CH-CRADLE (40 x 8 flanges) | **-0.50** | the ring is held only at its aft posts; the 18 g pull bends the post roots (deflection 13.8 mm), flanges do not help | forward post 28 x 56 mm from the beam web (x 112-140, y 140-196) up into the front of the ring, trimmed flush with the bore | +0.15 (deflection 1.3 mm) | +0.23 kg |
| PY-C (60 mm socket) | **-0.11** | socket wall bending at the mouth | socket wall 6 -> 8 mm (outer R 58.15) | +0.13 | +0.11 kg each (+0.9 kg, 8) |
| W-FIT-MS (22 mm boss) | **-0.35** | the boss grew on the outboard side only: the pin is 5 mm off the plate mid-plane, and the step at the plate edge is a sharp corner | uniform 18 mm plate, lug and eye (no boss step; web face unchanged), R 10 fillets at the lug/plate corners | +0.10 (eye bearing governs) | +0.31 kg each (+0.62 kg, 2) |
| F-CLV-MS | +1.15 | | none | | |
| CH-ATT-R (15 mm) | +0.24 | | none | | |
| W-CHUTE-FIT (15 mm) | +0.28 | | none | | |

Overall minimum: -0.50 (CH-CRADLE) as drawn in 3.3C; with the three changes above (+1.75 kg) the minimum strength margin is +0.10
(W-FIT-MS eye), then the members at +0.11. Frequency placement remains open (GVT).

## Phase 3.3B results: fittings on the iteration-3.3 CAD (loads at the design MTOW 1,350.4 kg)

CalculiX C3D10 on the CAD STEP parts (`fea/parts_cad.py`, x 1.27 mesh factor, 10 GB / 6 threads, one job at a time); lift-rotor
mounts at the structural rotor loads (T 4,240 N, Q 500 N m x 1.25), parachute 57.4 kN (one leg 50 %). New part MP-EMX (EMRAX
adapter ring: loaded at the EMRAX bolt circle, held at the P3 bolt circle). CAD materials are read from cad/parts.json.

| Part | MS | Fix (if negative) | Mass |
|---|---|---|---|
| F-CLV-MS / -RS | +1.13 / +1.30 | | |
| W-FIT-MS | **-0.18** (76.9 kN pin load) | eye boss 16 -> 22 mm (est. +0.12) | +0.12 kg (2 lugs) |
| W-FIT-RS | +0.14 | | |
| W-PIN-M (3/4 in) | shear +2.8, bending +0.27 | | |
| TL-CLAMP (110 mm sockets) | +0.79; socket bearing +0.32 | | |
| CH-CRADLE (25 x 6 flanges) | **-0.50** (15 mm deflection, flanged beam still bends) | flanges 40 x 8 mm (Z x ~2.4, est. +0.19) | +0.5 kg |
| LG-DUP (7075) | +0.42 | | |
| LG-SADDLE / LG-LEGEND / LG-SKCL | +0.51 / +0.50 / +9.9 | | |
| LG-LEG 76.2 x 2.41 / LG-SKID 57.1 x 3.17 | +0.32 / +2.98 | | |
| PB-PLUG (REB 90) | +5.6 | | |
| MP-EMX / MP | +5.1 / +0.91 | | |
| PY-HEAD (hand, flange) | +0.51 | | |
| PY-C | **-0.27** (rotor loads doubled; peak at the socket mouth) | socket 40 -> 60 mm deep (couple bearing x 0.44, est. +0.35) | +2.0 kg (8) |
| SEAT-FIT | +0.32 | | |
| CH-ATT-R / W-CHUTE-FIT | **-0.09 / -0.06** (57.4 kN) | plate 12 -> 15 mm (est. +0.14 / +0.17) | +1.2 kg (3) |
| W-CHUTE-ANG (hand) | bolts +1.07, bearing +1.12 | | |
| BC-W / BC-WR | +4.7 / +1.89 | | |
| HT-SPAR 50 x 4.84 | +0.12 | | |

Overall minimum: -0.50 (CH-CRADLE) as drawn; with the four fixes (+3.8 kg) the lowest strength margins are the members at
+0.11 (spars, booms, gear legs) and the fittings at about +0.12. Open item unchanged: frequency placement (12 HIGH flags, GVT).

## Phase 3.3A results (iteration 3.3 "ALL_rpmfree", frozen; global model only)

Inputs: MTOW 1,350.4 kg; wing 8.0 x 1.15 m (no flaps), LE x 2.145; V_D 63.6 m/s EAS (q +78 %); GRS 6 1200-1390, 57.4 kN (pitch
term kept); booms x -1.100 ... 7.650; lift rotors EMRAX 268 (geometry: T_max 4,240 N, Q_max 500 N m - the all-rotors-max case
R2 is 2.56 W and now drives the booms with the parachute case); REB 90 pushers at the boom ends (2,074 / 2,281 rpm); 4 packs;
OEI flare 1.10 g (57 % of T_max). Runs under 6 GB / 4 threads (CAD building in parallel).

Re-sized members (`results/sizing_update.json`, MS target 0.115 so that all members end >= +0.10):
* main spar t_cap/t_web (mm) eta 0.00: 6.1/0.5, eta 0.10: 6.7/1.2, eta 0.20: 5.6/1.1, eta 0.38: 4.4/1.1, eta 0.55: 2.3/0.5; outboard of eta 0.55 minimum gauge
* rear spar eta 0.00: 1.0/0.5, eta 0.10: 3.6/4.9, eta 0.20: 3.1/4.6, eta 0.38: 2.3/4.6, eta 0.55: 1.0/0.5
* booms: x -1.10-1.00: UD 1.78 mm, OD 109.4; x 1.00-4.12: UD 8.25 mm, OD 122.3; x 4.12-7.65: UD 5.11 mm, OD 116.0 (**clamp bores BC-W/BC-WR/PY-C/TL-CLAMP to 122.3 mm**)
* tail spar 50 x 4.84 mm (pusher gyroscopic pitch case); pylons 100 x 1.6; gear legs >= 2 mm; skin 0.5 mm
* keel caps 40 x 4.5 mm UD; H45 under the upper skin x/c 0.085-0.735, abs(y) <= 2.90 m

Min MS: spar main +0.11 (web shear, +3.8 g at V_A), spar rear +0.11, booms +0.11 (C3 parachute), tail spar +0.12, gear legs +0.11,
keel caps +0.12, wing-root straps +0.22, H45 skin +0.22, spar webs on H45 +0.12, pusher plug >= +12.8, gear n = 1.88 (MS +0.59).
**TL-CLAMP socket bearing -0.30** (tail-spar end moment): lengthen the sockets 80 -> 110 mm (MS ~+0.32).
Mass vs the 3.2 sections: booms +7.2 kg, rear spar +1.1, main spar +0.4, tail spar +0.6, skin -2.5 (smaller wing), keels +4.7;
net about +11.5 kg.

Dynamics: modes 2.0-4.9 Hz rotor rocking (as before). Pusher 1P at cruise (34.6 Hz) sits 3-9 % below a band of boom/tail modes at
35.5-37.6 Hz (HIGH, crossings 2,129-2,258 rpm, within the cruise-to-max range) and 2P (69.1 Hz) between boom modes at 67.4 and
72.6 Hz; lift 2P at 1,889 rpm hover (63 Hz) is clear, 67.4 Hz crosses at 2,023 rpm. With +-5 % separation the only clear pusher
speed in 1,600-2,600 rpm is about 1,920 rpm: cruise at <= 1,950 rpm or GVT-confirmed separation required.
Flutter 172 m/s vs 1.2 V_D = 76.4 m/s (margin +1.25); divergence 546 m/s EAS; pusher whirl stable with 7 % of the
mount stiffness at 1.2 V_D. Phase B (fittings on the CAD parts) follows the CAD rebuild.

## Phase 3.2b: fittings on the rebuilt CAD (2026-11-18) and the parachute boom check

Loads: iteration 3.2 (MTOW 1,169.5 kg). Sensitivity: all loads scale with MTOW, so MS(+3.3 %) = (1 + MS)/1.033 - 1 (column 2;
iteration 3.3 ~1,210 kg). Jobs run one at a time under a 10 GB memory limit and 6 threads. The mesh factor from the P1 study at the 3.2 loads is 1.27.

| Part (CAD) | MS (x 1.27 mesh factor, validation D6) | Note |
|---|---|---|
| F-CLV-MS / F-CLV-RS (7075, cheeks on the 24 mm plate, flange, gusset) | +1.72 / +2.46 | fixed (were -0.77 / -0.73) |
| W-FIT-MS (16 mm boss, e 34 mm) | +0.49 ligament (peak >= 6 mm from the pin bore); lug method +3.9 | fixed; W-PIN-M 3/4 in bolt: shear +4.2, bending +0.73 |
| W-FIT-RS | +0.62 | same evaluation |
| TL-CLAMP (10 mm socket walls) | +0.31 | fixed (was -0.38) |
| PB-PLUG (pusher boom-end plug) | +3.24 | bond/bearing hand checks >= +7.9 |
| LG-SADDLE / LG-LEGEND / LG-SKCL | +0.76 / +0.82 / +11.3 | |
| LG-DUP (12 mm cheeks, 6061) | **-0.22** | still negative: make it 7075-T6 (MS ~+0.6, same mass) |
| CH-CRADLE (one body, 100 x 9 mm flat beam) | **-0.75** | the flat 9 mm beam is loaded in plate bending by the canister couple (18 g x 36.3 kg, ring 0.2 m above the beam): 90 mm deflection, peak at the beam edges/holes. Needs a flanged beam (e.g. channel 100 x 9 with two 25 x 6 mm flanges, Z x ~5, +0.6 kg) |
| SEAT-FIT / CH-ATT-R | +0.30 / +0.07 | re-run at the 3.2 loads (no longer scaled) |
| LG-LEG 76.2 x 6.35 / LG-SKID 57.1 x 3.17 | +2.4 / +3.5 | LG-LEG is 3x the sized 2.0 mm wall: 3 x 0.095 in stock would do (-5 kg) |
| HT-SPAR 50 x 3.76 | +0.11 | = sized |
| W-H45-U (15 mm H45, 0.65 c x 6.52 m) | wrinkling +0.22 | covers the required x/c 0.085-0.735, abs(y) <= 3.26 m |

### Lowest margins
| MS (3.2 loads) | MS at +3.3 % MTOW | Item |
|---|---|---|
| -1.00 | -1.00 | frequency placement: boom/rotor modes within +-10 % of hover 1P/2P |
| -0.75 | -0.76 | fitting CH-CRADLE (CAD STEP part, CalculiX C3D10) |
| -0.66 | -0.67 | fitting CH-CRADLE (CAD) yield at limit |
| -0.22 | -0.24 | fitting LG-DUP (CAD STEP part, CalculiX C3D10) |
| +0.07 | +0.04 | fitting PY-C (CAD STEP part, CalculiX C3D10) |
| +0.07 | +0.04 | fitting CH-ATT-R (CAD STEP part, CalculiX C3D10) |
| +0.08 | +0.05 | fitting LG-DUP (CAD) yield at limit |
| +0.09 | +0.06 | detail: tail spar bearing in the TL-CLAMP socket (80 mm, moment by end bearing) |
| +0.10 | +0.06 | member: spar main |
| +0.10 | +0.06 | member: boom_R |
| +0.10 | +0.06 | member: boom_L |
| +0.10 | +0.07 | member: spar rear |
| +0.10 | +0.07 | fitting W-CHUTE-FIT (CAD STEP part, CalculiX C3D10) |
| +0.11 | +0.07 | member: tail spar |
| +0.11 | +0.07 | CAD section HT_SPAR |
| +0.11 | +0.07 | cabin: wing-root frame UD strap (60 mm, each side, each frame) |
| +0.11 | +0.07 | detail: main-spar +-45 webs on H45 box foam: wrinkling under web shear |
| +0.16 | +0.12 | cabin: keel UD caps (40 mm wide) |
| +0.17 | +0.13 | landing gear reserve drop 1.5 h: stroke available / needed |
| +0.22 | +0.18 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on pvc_h45 (peak at x/c 0.40) |
| +0.27 | +0.23 | member: gear cross tube |
| +0.27 | +0.23 | fitting CH-ATT-R (CAD) yield at limit |

### Parachute vertical case C3: boom moment at the saddle
The boom bending moment of case C3 (limit) is 19.1 kN m at x = 3.0 m, i.e. **at the rear saddle (aft face of BC-WR, x 2.96 m), 28.6
kN m ultimate**; at the front saddle (x 2.26 m) it is 6.7 kN m limit. The difference to the independent 20.8 kN m is the
aircraft pitch acceleration: the three bridle legs (two at x 2.26 m, one at 4.10 m, equal shares) pull 0.38 m aft of the cg, so the
free-free solution has a_z = +3.25 g and a pitch acceleration of 3.08 rad/s^2, which adds 0.31 g per metre aft of the cg to the
inertia of the aft overhang (rotors at 4.19 and 6.19 m, pusher at 7.87 m, tail). A hand integration of the aft overhang about the
rear saddle gives 13.9 kN m limit (20.9 ultimate) with a uniform 4.25 g, matching the independent value, and 18.1 kN m limit
(27.2 ultimate) with the pitch-acceleration term, matching the model (remaining 5 %: tail-spar end moment and pylon mass split).
If the bridle is rigged to put the resultant through the cg, the 20.8 kN m figure applies; until the bridle geometry is fixed
the booms are sized with the pitch term.

## Phase 3.2 results (design iteration 3.2 "T8", frozen 2026-11-16)

Inputs: `design/geometry.json` of iteration 3.2: MTOW 1,169.5 kg, wing 9.0 x 1.40 m, booms 9.31 m (x -1.389 ... 7.918 m), 8 lift rotors
1.90 m (T_max 2,234 N, hover 1,829 rpm), **two pushers on the boom tails** (2.05 m, 2,042 N, 250 N m, 1,770 rpm cruise, 1,947 max,
Ip 1.58 kg m^2, each on a 6061 plug bonded 150 mm into the boom end), 5 battery packs, H-tail 1.75 m^2, fins 0.90 m^2,
Galaxy GRS 6 990-1190 (opening 48.8 kN = 4.25 g). FEA inputs changed: parachute 48.8 kN, rotor-station mass 68 % at the hub
(0.63 m pylon), one-motor-out flare 1.10 g (owner relaxation), V_D 50.2 m/s (selected_design structure.dive_speed_ms, higher
than 1.4 V_C = 47.7).

Tool fixes: `fea/geometry.py mass_items` (and loads, airframe, dynamics) now read every unit of `pushers[]`; the reader total
is 1,169.5 kg and its cg 2.491 m vs 2.474 m (validation/sizing/verify_sizing.py A3a/A3b PASS, 102 PASS / 0 FAIL).
New pusher load cases: both pushers at max thrust with the 1.25 fault torque and the CS-23.371 gyroscopic moment (yaw 2.5 /
pitch 1.0 rad/s at 1,947 rpm: 807 / 323 N m limit per unit) and one pusher failed (asymmetric thrust).

### Loads
W/S 910 Pa; V_S1 30.1, V_A 58.7, V_C 34.1, V_D 50.2 m/s EAS; gust +2.14 / -0.14 at V_C, +1.84 / +0.16 at V_D; +3.8 / -1.5 g.
One motor out: 86 % of T_max at 1.0 g, 94 % in the 1.10 g flare. Parachute (4.25 g) still drives the booms, rear-spar web and
tail spar.

### Re-sized members (`results/sizing_update.json`)
| spar | eta | y (m) | h (mm) | b_cap (mm) | t_cap (mm) | t_web (mm) x webs |
|---|---|---|---|---|---|---|
| main | 0.000 | 0.00 | 219 | 80 | 5.28 | 0.50 x 2 |
| main | 0.084 | 0.38 | 219 | 77 | 5.66 | 0.67 x 2 |
| main | 0.200 | 0.90 | 219 | 74 | 4.76 | 0.56 x 2 |
| main | 0.347 | 1.56 | 219 | 70 | 3.87 | 0.54 x 2 |
| main | 0.550 | 2.48 | 219 | 64 | 1.70 | 0.50 x 2 |
| main | 0.700 | 3.15 | 219 | 59 | 1.00 | 0.50 x 2 |
| main | 0.850 | 3.82 | 219 | 55 | 1.00 | 0.50 x 2 |
| main | 1.000 | 4.50 | 219 | 50 | 1.00 | 0.50 x 2 |
| rear | 0.000 | 0.00 | 143 | 50 | 1.00 | 0.50 x 1 |
| rear | 0.084 | 0.38 | 143 | 48 | 1.88 | 2.48 x 1 |
| rear | 0.200 | 0.90 | 143 | 46 | 1.57 | 2.24 x 1 |
| rear | 0.347 | 1.56 | 143 | 43 | 1.30 | 2.25 x 1 |
| rear | 0.550 | 2.48 | 143 | 39 | 1.00 | 0.50 x 1 |
| rear | 0.700 | 3.15 | 143 | 36 | 1.00 | 0.50 x 1 |
| rear | 0.850 | 3.82 | 143 | 33 | 1.00 | 0.50 x 1 |
| rear | 1.000 | 4.50 | 143 | 30 | 1.00 | 0.50 x 1 |

| boom segment x (m) | wall (inside -> out) | OD (mm) |
|---|---|---|
| -1.39 ... 0.76 | 1.60 mm cf_tube_rollwrapped_twill + 0.79 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 107.4 |
| 0.76 ... 4.19 | 1.60 mm cf_tube_rollwrapped_twill + 6.73 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 119.3 |
| 4.19 ... 7.92 | 1.60 mm cf_tube_rollwrapped_twill + 4.08 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 114.0 |

**The middle boom over-wrap grows to 6.7 mm (OD 119.3 mm; CAD has 113.1 mm)** and the aft segment to 4.1 mm (OD 113.9 mm):
the longer boom with a 27 kg pusher at its tail, the 0.63 m pylons and the parachute vertical case. All boom clamps (BC-W, BC-WR,
PY-C, TL-CLAMP) must be re-bored to the new ODs. Tail spar 50 x 3.75 mm (was 2.14 in the CAD). Skin 0.5 mm (min gauge),
pylons 100 x 1.6 mm, gear legs 76 x 2.0 mm (pivoted).

### Detail and cabin checks (`results/details.json`, `fuselage.json`)
Pusher boom-end plug: bond (thrust + torque) MS +17.9, boom wall bearing under the plug moment MS +7.9, plug bending MS +13.6,
motor-plate bolts MS +28. Skin wrinkling: the H45 region grows to x/c 0.08-0.73, |y| <= 3.26 m (MS +0.22 on H45, -0.42 on XPS).
TL-CLAMP socket bearing MS +0.09 (tail spar moment). Parachute cradle with the 36.3 kg canister: posts need Z >= 1687 mm^3
(CAD 2,304: OK); the 8 mm beam needs solid material under the posts (solid 100 x 8 mm: MS -0.03 -> 100 x 9 mm). Cabin: keel caps
+0.16, frame straps +0.11, all others higher. Damped gear: n = 1.88 (energy), reserve stroke +0.17.

### Dynamics (`results/dynamics.json`, `docs/models/fea/campbell.png`, `flutter_vg.png`)
* Modes (Hz): 2.0, 2.2, 3.0, 3.0, 3.1, 3.1, 3.6, 4.1, 4.8, 6.6, 7.8, 9.1 ... (rotor/boom rocking 2.0-4.8 Hz: notch filters as before).
* **Pusher on the boom tail: at the 1,770 rpm cruise, 1P = 29.5 Hz coincides with a wing/boom mode at 29.5 Hz and 2P = 59 Hz with
  boom modes at 58.5 and 60.0 Hz** (HIGH). Sweeping the pusher rpm, the only window with no boom/tail-dominated mode within
  +-5 % of 1P and 2P is **1,525-1,575 rpm** (the beam model is coarse above 30 Hz: confirm by GVT). Required: set the pusher
  pitch for ~1,550 rpm cruise, or accept the crossing with isolators and a GVT-confirmed separation.
* Lift rotors at 1,829 rpm hover (30.5 Hz): boom/wing modes at 28.0-33.2 Hz and 2P at 58.5-64.8 Hz are inside +-10 % (HIGH,
  as in iteration 3).
* Pusher whirl on the long boom: effective pivot 3.6 m ahead of the hub, K = 79 kN m/rad (pitch); stable to 1.3 V_D, still stable
  with 8.9 % of the stiffness at 1.2 V_D (margin x 11).
* Divergence 440 m/s EAS; flutter 148 m/s at 5.1 Hz vs 1.2 V_D = 60.2 m/s (margin +1.46).

### Mass change of the WP F members vs selected_design.json (iteration 3.2)
| item | delta (kg) |
|---|---|
| wing spars + torsion skin (in wing) | -12.1 |
| boom tubes (in booms) | +10.1 |
| tail spar (in tail) | +1.2 |
| gear legs, pivoted, 76 mm (in landing gear) | -4.9 |
| H45 15 mm under the upper skin, x/c 0.08-0.73, |y| <= 3.26 m (replaces XPS) | +1.3 |
| pivot hardware for the gear legs (4 bushed pivots, estimate; required change) | +2.0 |
| **total** | **-2.3** |

### Fittings on the CAD parts (`fea/parts_cad.py`)
The WP G rebuild for iteration 3.2 stopped with an error (build log: AssertionError in the cabin/gear stage) after writing the wing,
boom and tail parts; `cad/parts.json` is still the iteration-3.1 file. Analysed on the new STEP parts: W-FIT-MS/RS, F-CLV-MS/RS,
BC-W, BC-WR, PY-C, TL-CLAMP (bores now 119.6 mm, following the re-sized boom), W-CHUTE-FIT, MP. Gear, seat, cradle and the rear
parachute fitting keep their iteration-3.1 CAD results scaled to the new loads (MTOW 1.122, parachute 48.8/47.4, canister
36.3/28.2 kg). The boom-end pusher plug is not in the CAD yet: hand checks above (all MS >= +7.9).

Model change: the wing-root lug link is now vertical from a stiff frame arm at the fitting station (the inclined link from the
fuselage axis added a spurious lateral load).

### All margins, lowest first (full list: `results/margins.json`)
| MS | Item | Mode | Note |
|---|---|---|---|
| -1.00 | frequency placement: boom/rotor modes within +-10 % of hover 1P/2P | 13 HIGH flags | not a strength margin: -1 flags an open item (see README) |
| -0.81 | fitting CH-CRADLE (CAD, beam + posts; ring not attached to the posts in the CAD) | von Mises vs Ftu (model unconstrained: posts sit over lightening holes) | ring separate from the posts in the CAD (gap); canister cg 78 mm above the post tops; post |
| -0.77 | fitting F-CLV-MS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| -0.77 | detail: parachute cradle beam 8 mm, section through a 76 mm lightening hole (as drawn) | hand method | 18 g forward x 1.15 on the 28.2 kg canister; post couple into the beam |
| -0.73 | fitting F-CLV-RS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| -0.68 | fitting F-CLV-MS (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.63 | fitting F-CLV-RS (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.42 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on xps_foam (peak at x/c 0.40) | hand method | ultimate cap strain 0.364 % x skin/cap height ratio 1.20; foam depth needed ~0.5 x half-wa |
| -0.41 | fitting LG-DUP (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.122 to the iteration-3.2 loads] |
| -0.38 | fitting TL-CLAMP (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| -0.18 | fitting LG-DUP (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.14 | fitting TL-CLAMP (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.08 | fitting W-FIT-MS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| -0.03 | detail: parachute cradle beam 8 mm, section solid 100 mm | hand method | 18 g forward x 1.15 on the 28.2 kg canister; post couple into the beam |
| +0.07 | fitting PY-C (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| +0.07 | fitting CH-ATT-R (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.030 to the iteration-3.2 loads] |
| +0.09 | detail: tail spar bearing in the TL-CLAMP socket (80 mm, moment by end bearing) | hand method | M 1564 N m, V 1396 N ultimate x 1.15; the bond carries axial load and torsion only |
| +0.10 | member: spar main | compression | ultimate; strength allowables of fea/materials.json |
| +0.10 | member: boom_R | compression | ultimate; strength allowables of fea/materials.json |
| +0.10 | member: boom_L | compression | ultimate; strength allowables of fea/materials.json |
| +0.10 | member: spar rear | compression | ultimate; strength allowables of fea/materials.json |
| +0.10 | fitting W-CHUTE-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |
| +0.11 | member: tail spar | compression | ultimate; strength allowables of fea/materials.json |
| +0.11 | cabin: wing-root frame UD strap (60 mm, each side, each frame) | sandwich / hand method |  |
| +0.11 | detail: main-spar +-45 webs on H45 box foam: wrinkling under web shear | hand method | principal compression = tau, along the fibres (E1 of the fabric) |
| +0.16 | cabin: keel UD caps (40 mm wide) | sandwich / hand method |  |
| +0.17 | landing gear reserve drop 1.5 h: stroke available / needed | stroke |  |
| +0.22 | fitting W-FIT-MS (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.22 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on pvc_h45 (peak at x/c 0.40) | hand method | ultimate cap strain 0.364 % x skin/cap height ratio 1.20; foam depth needed ~0.5 x half-wa |
| +0.27 | member: gear cross tube | compression | ultimate; strength allowables of fea/materials.json |
| +0.27 | fitting CH-ATT-R (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.31 | fitting W-CHUTE-FIT (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.32 | fitting SEAT-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.011 to the iteration-3.2 loads] |
| +0.33 | fitting W-FIT-RS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.27 mesh factor) | [iteration-3.1 CAD part, result scaled x 1/1.000 to the iteration-3.2 loads] |

### Failing parts and required changes (iteration 3.2)
1. **F-CLV-MS / F-CLV-RS fuselage clevises (new parts): MS -0.77 / -0.73.** The cheeks stand on a flange that overhangs the bolted
   stem; the 56 kN pin load bends that flange at its junction with the 12 mm stem (FE peak 894 MPa). Redesign: cheeks directly over
   the bolted plate (no overhang) with gussets to the stem, flange >= 2 x thicker, or a one-piece 7075 block; then re-run.
2. **W-FIT-MS main lug: MS -0.08** (higher MTOW): eye boss 14 -> 16 mm and edge distance e 30 -> 34 mm (est. MS ~+0.1).
3. **TL-CLAMP: MS -0.38** (tail-spar end moment with the stiffer 50 x 3.76 mm spar and the boom-tail pushers): restore the socket
   wall (no windows within 20 mm of the socket, socket wall 6 -> 10 mm); re-run.
4. **LG-DUP damper fitting (scaled): MS -0.41**: 12 mm cheeks or 7075-T6 (as in phase 3.1, now also for the higher MTOW).
5. **CH-CRADLE**: ring fused to the posts, no lightening holes under the posts, beam 100 x 9 mm (36.3 kg canister).
6. **H45 under the upper skin**: the CAD part W-H45-U covers x/c 0.085-0.735 over 5.88 m; with the 9 m wing it must reach
   |y| = 3.26 m (6.53 m).
7. **Booms**: middle over-wrap 6.7 mm (OD 119.3 mm), aft 4.1 mm (OD 114.0 mm), front 0.8 mm (OD 107.4 mm): +10.1 kg; the CAD
   clamp bores already follow (119.6 mm).
8. **Pusher rpm**: cruise 1,770 rpm puts 1P/2P on boom/wing modes (29.5 / 58.5-60 Hz); move to ~1,550 rpm or prove separation by GVT.
9. Tail spar 50 x 3.76 mm (+1.2 kg; the CAD has 2.14 mm).

Mass change of the WP F members vs selected_design.json: **-2.3 kg** (wing spars and skin -12.1, booms +10.1,
tail spar +1.2, gear legs -4.9, H45 region +1.3, gear pivots +2.0); the fitting redesigns 1-5 add an estimated +1.5 kg.


## Phase 3.1 results (CAD rebuild with the phase-3 changes)

Re-run on the WP G rebuild of 2026-11-15 22:20 (cad/parts.json; pivoting gear LG-*, H45 strips W-SPM-S, 14 mm boss on
W-FIT-MS with the new fuselage clevis F-CLV-MS, CH-CRADLE with 24 x 24 mm posts, boom clamps for the 113.1 mm over-wrap, HT-SPAR
50 x 2.14 mm). design/selected_design.json still gives MTOW 1,042.8 kg (the iteration-3.1 re-freeze had not changed it), so the
loads are those of phase 3 (no scaling). All 16 critical fittings were analysed in CalculiX on the CAD STEP parts
(`fea/parts_cad.py`; multi-body STEP parts are fused conformally in gmsh; peaks x 1.19 mesh factor). Gear: unchanged geometry,
n = 1.88 by energy (`fea/gear.py`); the gear fittings carry the 2.33 W design reaction (3 g limit with 2/3 W lift).

### Lowest margins
| MS | Item | Mode | Critical case |
|---|---|---|---|
| -1.00 | frequency placement: boom/rotor modes within +-10 % of hover 1P/2P | 8 HIGH flags |  |
| -0.75 | fitting CH-CRADLE (CAD, beam + posts; ring not attached to the posts in the CAD) | von Mises vs Ftu (model unconstrained: posts sit over lightening holes) |  |
| -0.70 | detail: parachute cradle beam 8 mm, section through a 76 mm lightening hole (as drawn) | hand method | envelope |
| -0.42 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on xps_foam (peak at x/c 0.40) | hand method | envelope |
| -0.33 | fitting F-CLV-MS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| -0.29 | fitting LG-DUP (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| -0.07 | fitting F-CLV-MS (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.02 | fitting LG-DUP (CAD) yield at limit | von Mises vs Fty at limit |  |
| -0.01 | fitting W-FIT-RS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.10 | member: spar main | web shear | R7b one motor out (LR_L4 failed), 1.2 g flare |
| +0.10 | member: tail spar | compression | C4 parachute opening 4.6 g, aft-up-right 45/30 deg |
| +0.10 | member: boom_R | compression | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | member: boom_L | compression | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | member: spar rear | web shear | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | detail: main-spar +-45 webs on H45 box foam: wrinkling under web shear | hand method | envelope |
| +0.17 | cabin: wing-root frame UD strap (60 mm, each side, each frame) | sandwich / hand method | envelope |
| +0.17 | fitting PY-C (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.17 | landing gear reserve drop 1.5 h: stroke available / needed | stroke | reserve drop |
| +0.18 | fitting CH-ATT-R (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.20 | fitting TL-CLAMP (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.21 | cabin: keel UD caps (40 mm wide) | sandwich / hand method | envelope |
| +0.21 | fitting W-CHUTE-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.21 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on pvc_h45 (peak at x/c 0.40) | hand method | envelope |
| +0.25 | detail: parachute cradle beam 8 mm, section solid 100 mm | hand method | envelope |
| +0.31 | fitting W-FIT-RS (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.34 | fitting W-FIT-MS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.38 | cabin: floor face wrinkling | sandwich / hand method | envelope |
| +0.39 | fitting CH-ATT-R (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.42 | cabin: floor faces (cargo 6 g) | sandwich / hand method | envelope |
| +0.42 | fitting SEAT-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |

### Findings on the rebuilt CAD
1. **W-SPM-S H45 strips (30 mm either side of the main-spar cap, x/c 0.14-0.26) do not cover the wrinkling region.** With the
   LS(1)-0417 ordinates the upper skin strain is up to 1.21 x the cap strain (peak at x/c 0.40, skin above the cap); on XPS the
   +-45 skin wrinkles (MS -0.42) for **x/c 0.08 to 0.73 and |y| <= 2.94 m**. H45 (15 mm) over that region gives MS +0.21
   (+1.0 kg net vs XPS). The phase-3 number (MS -0.30) used the cap strain without the skin/cap height ratio and is superseded.
2. **F-CLV-MS fuselage clevis (6061-T6): MS -0.32** at the cheek roots and the pin eye (parachute vertical case, 50.9 kN design).
   Make it in 7075-T6 like the lug (MS ~+0.39) or thicken the cheeks by ~50 % with root fillets.
3. **LG-DUP damper upper fitting: MS -0.29** (8 mm cheeks bending, 20.7 kN design damper force). Cheeks 12 mm with
   root fillets, or 7075-T6 (MS ~+0.45).
4. **W-FIT-RS rear-spar lug: MS -0.01** - give it the same 14 mm eye boss as W-FIT-MS (then ~+0.15).
5. **CH-CRADLE as drawn does not work:** the clamp ring is a separate body that does not touch the posts (gap in the STEP), and the
   24 x 24 mm posts stand over the 76 mm lightening holes of the 8 mm beam (only a ligament under each post). The posts
   themselves are fine (MS +19); the beam needs solid material under and 30 mm around each post (hand check: solid 100 x 8 mm
   section MS +0.25, through a hole MS -0.70), and the ring must be fused to the posts. The CalculiX run of the beam + posts
   (MS -0.74) is not meaningful until then (unsupported posts).
6. Confirmed on the CAD: W-FIT-MS with the 14 mm boss MS +0.35; pivoting gear saddle LG-SADDLE +1.16, leg end
   LG-LEGEND +1.19, skid clamp LG-SKCL +12.3, damper collar bond +5.1; boom clamps BC-W +1.09 /
   BC-WR +6.3, PY-C +0.17, TL-CLAMP +0.20; motor plate +2.31; parachute hard points
   +0.18 / +0.21; seat fitting +0.42. **HT-SPAR: the CAD uses 50 x 2.14 mm, but the sizing gave
   50 x 2.48 mm (MS +0.10); 2.14 mm scales to MS ~-0.05 in compression** - keep 2.48 mm (the NACA 0014 tail section gives room).

### Masses
CAD machined fittings 80.9 kg and cabin primaries 20.5 kg (WP G audit) replace the 48 / 43 kg assumed in phase 3; both are inside
the CAD-calibrated breakdown, so the WP F mass delta is unchanged: **-10.6 kg** (members, H45 region, gear pivots).
The required changes above add about +0.6 kg: 7075 instead of 6061 for F-CLV-MS / LG-DUP (+0.04 kg), W-FIT-RS boss (+0.05 kg),
cradle beam without holes under the posts (+0.3 kg), tail spar 2.48 mm (+0.2 kg).

## Phase 3 results (design iteration 3)

Inputs: `design/geometry.json` of iteration 3 (MTOW 1,042.8 kg, 8 x REB 60 / 1.85 m rotors, T_max 2,156 N, Q_max 250 N m,
hover 1,703 rpm, wing 8.1 x 1.15 m at z 1.98 m with spars at 0.20 / 0.70 c, booms at z 1.80 m, pylons 0.55 m, 3 battery
packs of 70 kg, damped skid gear with 4 oleos (80 mm), seats with 150 mm stroke, Galaxy GRS 6 800-990/1050 kg: 47.4 kN = 4.64 g)
and `fea/design_inputs.json` (rotor-station mass 64 % at the hub so that the station cg is 0.20 m below the hub; landing
cases with 2/3 W rotor lift, gear reaction 2.33 W). The fittings were first analysed on the parametric `fea/parts.py`
solids with the iteration-3 reductions; WP G published the rebuilt iteration-3 STEP parts during this run (cad/parts.json of
2026-11-15 21:21), and **the final fitting margins are from the CAD STEP parts** (`fea/parts_cad.py`, same loads, supports and
margin definitions; `docs/models/fea/CAD_*.png/.glb`). The parametric results stay in `results/parts.json` for reference.
The CH-CRADLE was not modelled in CalculiX (frame/cradle geometry): its requirement is stated below.

### Loads
W/S 1,098 Pa; V_S1 33.1, V_A 64.5, V_C 39.6, V_D 55.5 m/s EAS; gust +2.18 / -0.18 (V_C), +1.83 / +0.17 (V_D); manoeuvre
+3.8 / -1.5 governs. One motor out: 79 % of T_max at 1.0 g and **95 % in the 1.2 g flare** (new load case R7b, yaw-trimmed,
all 8 failure cases) - the flare requirement is met with the REB 60. The parachute cases still drive the booms, rear spar
web, root lugs and pylon saddles.

### Sized primary structure (`results/sizing_update.json`)
| spar | eta | y (m) | b_cap (mm) | t_cap (mm) | t_web (mm) x webs |
|---|---|---|---|---|---|
| main | 0.000 | 0.00 | 80 | 5.04 | 0.50 x 2 |
| main | 0.094 | 0.38 | 77 | 5.40 | 0.65 x 2 |
| main | 0.200 | 0.81 | 74 | 4.45 | 0.62 x 2 |
| main | 0.379 | 1.53 | 69 | 3.33 | 0.61 x 2 |
| main | 0.550 | 2.23 | 64 | 1.71 | 0.50 x 2 |
| main | 0.700 | 2.83 | 59 | 1.00 | 0.50 x 2 |
| main | 0.850 | 3.44 | 55 | 1.00 | 0.50 x 2 |
| main | 1.000 | 4.05 | 50 | 1.00 | 0.50 x 2 |
| rear | 0.000 | 0.00 | 50 | 1.00 | 0.50 x 1 |
| rear | 0.094 | 0.38 | 48 | 1.54 | 2.08 x 1 |
| rear | 0.200 | 0.81 | 46 | 1.39 | 1.90 x 1 |
| rear | 0.379 | 1.53 | 42 | 1.04 | 1.96 x 1 |
| rear | 0.550 | 2.23 | 39 | 1.00 | 0.50 x 1 |
| rear | 0.700 | 2.83 | 36 | 1.00 | 0.50 x 1 |
| rear | 0.850 | 3.44 | 33 | 1.00 | 0.50 x 1 |
| rear | 1.000 | 4.05 | 30 | 1.00 | 0.50 x 1 |

Skin +-45 carbon 0.50 mm (minimum gauge). Booms:

| x range (m) | wall (inside -> out) | OD (mm) |
|---|---|---|
| -1.47 ... 0.63 | 1.60 mm cf_tube_rollwrapped_twill + 0.69 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 107.2 |
| 0.63 ... 3.36 | 1.60 mm cf_tube_rollwrapped_twill + 3.63 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 113.1 |
| 3.36 ... 6.76 | 1.60 mm cf_tube_rollwrapped_twill + 1.80 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 109.4 |

Tail spar 50 x 2.14 mm; pylons 6061-T6 100 x 1.6 mm (0.55 m); gear legs 76 x
2.0 mm 6061-T6 (minimum gauge, pivoted legs, see below). Cabin structure as in phase 2 (keel caps 40 x 3.6 mm UD,
frame straps 60 x 1.8 mm UD): all cabin margins positive with the 3 x 70 kg packs.

### Weight reductions requested by WP D - verdict
| Part | Reduction | Verdict | Basis |
|---|---|---|---|
| MP motor plate | pocket 50 % | **confirmed on the CAD part** (windows -48 %): MS +2.31 incl. mesh factor | CAD MP |
| PY-C pylon saddle + socket | pocket 30 % | CAD part removes only 11 %: MS +0.17; the parametric study shows -30 % and -15 % fail (MS < 0) -> **keep the CAD -11 % version** | CAD PY-C, P7 |
| PY-HEAD | pocket 25 % | confirmed, flange MS +1.46 | details.py |
| LG-SADDLE | 20 % thinner | **confirmed on the CAD part** with the damper/pivot loads: MS +9.3 (could be lighter still) | CAD LG-SADDLE |
| LG-SKCL | pocket 30 % | confirmed, MS >= +5.4 (bolts) | details.py |
| CH-CRADLE | -40 % (CAD -47 %) | **to confirm by WP G**: each of the two posts needs Z >= 1312 mm^3 (18 g fwd on the 28.2 kg canister) | details.py |
| TL-CLAMP | pocket 30 % | confirmed (socket bearing MS +0.78, wall MS +2.7) | details.py |
| W-CORE voided XPS | -40 % | voids OK (wrinkle half-wave 15 mm << 30 mm kept), **but the +-45 skin wrinkles on XPS at ultimate (MS -0.30) whether voided or not**: 15 mm H45 strip under the upper skin between the spars (MS +0.46, +1.0 kg) | details.py |
| W-SPM-F box foam H80 -> H45 | -2.7 kg | confirmed: web wrinkling MS +0.10, box shear buckling not critical | details.py |
| W-FIT-MS root lug (no reduction) | - | **CAD lug MS -0.04** (peak at the eye, parachute vertical case): thicken the eye boss 12 -> 14 mm (MS ~+0.12) | CAD W-FIT-MS |

### Landing gear with dampers
Energy (0.33 m drop, 2/3 W lift, eta 0.8): damper peak force 6.7 kN, gear reaction 1.22 W, **n = 1.88 <= 3.0**,
skid travel 171 mm at full stroke (lever ratio 2.14); reserve drop (1.5 h) needs 68 mm of the 80 mm stroke.
**This works only if each leg pivots on its keel saddle** (bushed pivot about x, the model of `airframe.py` gear_model "damped").
With the continuous, clamped, bent cross tube of the iteration-3 CAD note ("bending cross-tube leg"), the tube is ~100 x stiffer
than the oleo path, the dampers cannot stroke and the gear stays at ~12 g (phase 2 result). Required change: split legs on
pivots (or a torsion-free sleeve joint in the saddles); then the legs can drop to minimum gauge (-4.9 kg) and the saddles
carry only the pivot force.

### All margins, lowest first (full list: `results/margins.json`)
| MS | Item | Mode | Critical case |
|---|---|---|---|
| -1.00 | frequency placement: boom/rotor modes within +-10 % of hover 1P/2P | 8 HIGH flags |  |
| -0.30 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on xps_foam | hand method | envelope |
| -0.04 | fitting W-FIT-MS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.05 | fitting W-FIT-RS (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.10 | member: spar main | web shear | R7b one motor out (LR_L4 failed), 1.2 g flare |
| +0.10 | member: tail spar | compression | C4 parachute opening 4.6 g, aft-up-right 45/30 deg |
| +0.10 | member: boom_R | compression | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | member: boom_L | compression | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | member: spar rear | web shear | C3 parachute opening 4.6 g, vertical (inflated, low speed) |
| +0.10 | detail: main-spar +-45 webs on H45 box foam: wrinkling under web shear | hand method | envelope |
| +0.17 | cabin: wing-root frame UD strap (60 mm, each side, each frame) | sandwich / hand method | envelope |
| +0.17 | fitting PY-C (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.17 | landing gear reserve drop 1.5 h: stroke available / needed | stroke | reserve drop |
| +0.17 | fitting CH-ATT-R (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.19 | fitting W-CHUTE-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.21 | cabin: keel UD caps (40 mm wide) | sandwich / hand method | envelope |
| +0.27 | fitting W-FIT-MS (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.38 | fitting CH-ATT-R (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.38 | cabin: floor face wrinkling | sandwich / hand method | envelope |
| +0.39 | fitting W-FIT-RS (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.41 | fitting W-CHUTE-FIT (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.42 | cabin: floor faces (cargo 6 g) | sandwich / hand method | envelope |
| +0.42 | fitting SEAT-FIT (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +0.43 | cabin: keel web faces (shear) | sandwich / hand method | envelope |
| +0.46 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on pvc_h45 | hand method | envelope |
| +0.46 | member: gear cross tube | compression | L2 level landing 3.0 g with drag 0.25 x vertical (inclined r |
| +0.52 | cabin: rear parachute frame UD straps (2 x 60 mm) | sandwich / hand method | envelope |
| +0.59 | landing gear (oleo dampers, pivoted legs): limit drop inertia factor <= 3.0 | energy (0.33 m drop, L = 2/3 W) | limit drop |
| +0.61 | fitting PY-C (CAD) yield at limit | von Mises vs Fty at limit |  |
| +0.78 | detail: tail spar bearing in the TL-CLAMP socket (80 mm, moment by end bearing) | hand method | envelope |
| +0.88 | fitting SEAT-FIT (CAD) yield at limit | von Mises vs Fty at limit |  |
| +1.09 | fitting BC-W (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +1.18 | cabin: wing-root frame side post faces (lateral lug load) | sandwich / hand method | envelope |
| +1.20 | detail: wing upper skin (+-45, 0.5 mm) wrinkling on pvc_h80 | hand method | envelope |
| +1.32 | cabin: seat rail insert in keel cap region (bearing) | sandwich / hand method | envelope |
| +1.46 | detail: pylon head flange 8 mm between isolators (PY-HEAD, -25 %) | hand method | envelope |
| +1.73 | cabin: floor core shear H80 | sandwich / hand method | envelope |
| +1.73 | cabin: keel potted insert bearing (battery bracket) | sandwich / hand method | envelope |
| +1.89 | fitting BC-W (CAD) yield at limit | von Mises vs Fty at limit |  |
| +1.99 | flutter (modal, strip Theodorsen) vs 1.2 VD | speed margin |  |
| +2.31 | fitting MP (CAD STEP part, CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.19 mesh factor) |  |
| +2.57 | member: rotor pylon | compression | C1 parachute opening 4.6 g, aft (deployment along the flight |

### Mass change vs selected_design.json (iteration 3)
| item | delta (kg) |
|---|---|
| wing spars + torsion skin (in wing) | -9.0 |
| boom tubes (in booms) | +0.3 |
| tail spar (in tail) | +0.1 |
| gear legs, pivoted, 76 mm (in landing gear) | -4.9 |
| H45 strip 15 mm under the upper skin over the spar box (replaces XPS; required change) | +1.0 |
| pivot hardware for the gear legs (4 bushed pivots, estimate; required change) | +2.0 |
| **total** | **-10.5** (MTOW ~1032 kg) |

Fittings as modelled: 51 kg in total (already in the CAD-calibrated breakdown; P7 is heavier than the
-30 % assumption). Seats with 150 mm stroke: attachment loads unchanged (forward 26 g governs).

### Deflections (limit)
Wing tip 195 mm at +3.8 g; boom ends 94 mm in hover, 157 mm one motor out at 1 g, 188 mm in the 1.2 g OEI flare, 379 mm in the
parachute vertical case.

### Dynamics and aeroelasticity
* Modes (Hz): 2.2, 2.5, 3.0, 3.3, 3.4, 3.4, 3.8, 4.5, 4.5, 7.1, 8.7, 9.4, ... The first nine (2.2-4.5 Hz) are rotors rocking on the booms
  (boom torsion + 0.55 m pylons): flight-control notch filters and a structural-coupling test remain required.
* Campbell (hover 1,703 rpm = 28.4 Hz, 1P band 21-36 Hz, 2P 42-72 Hz): the lift 1P no longer has HIGH flags (the dense boom
  band at 29-36 Hz now sits above the hover 1P); HIGH: lift 2P at 52-56 Hz (wing/boom modes, crossings 1,565-1,668 rpm, i.e. 8 %
  below hover), pusher 1P with tail/boom modes at 37-41 Hz (2,238-2,462 rpm, cruise 2,341) and pusher 2P with tail modes at 73
  and 86 Hz. Mitigations unchanged (balance/track, isolators - now in the design, GVT); pusher: check the tail-boom/H-tail modes
  in the GVT and keep the cruise rpm away from 2,240-2,460 rpm if they are confirmed.
* Divergence 467 m/s EAS; flutter 199 m/s at 4.0 Hz (1.2 V_D = 66.6 m/s, margin
  +2.0); pusher whirl stable with 0.5 % of the mount stiffness at 1.2 V_D.

### Required changes (iteration 3)
1. **Gear legs must pivot** on the keel saddles (bushed pivot about x); with the continuous clamped cross tube the dampers cannot
   stroke. Legs can then go to 76 x 2 mm (-4.9 kg); +2 kg pivot hardware.
2. **Wing upper skin over the spar box on 15 mm H45 instead of XPS** (skin wrinkling, MS -0.30 on XPS); voids are fine.
3. **Main-spar root lug W-FIT-MS: eye boss 14 mm** (CAD part MS -0.04 at 12 mm).
4. PY-C: keep the CAD version (-11 %); the -30 % reduction is not achievable.
5. CH-CRADLE posts: Z >= 1312 mm^3 each (WP G to check on the part).
6. Open item (not a strength margin): boom/rotor modes near the lift 2P and pusher 1P/2P (8 HIGH flags) -> GVT, isolators (in
   the design), rpm schedule.

## Phase 2 results (design iteration 1, superseded)

Inputs: `design/geometry.json` (MTOW 1,001.7 kg, cg x 1.97 m) + `fea/design_inputs.json`. CFD results (`cfd/results/`) were
not yet available: CL_alpha 4.62 /rad, CL_max 1.64, C_m0 -0.12 from geometry.json `aero`. Parachute opening load: Galaxy
GRS 6/800-990, **47.4 kN** (1,050 kg variant, resources ST12) = 4.8 g on MTOW, one leg up to 50 %. All results ultimate
(x 1.5) unless stated; fittings x 1.15. No CAD parts existed in `cad/parts/` when this was run, so the fittings were
modelled parametrically in `fea/parts.py` (dimensions listed there and below) for WP G to adopt.

### Loads (`results/loads_design.json`)
* V-n: W/S 930 Pa, V_S1 30.4, V_A 59.3, V_C 39.6 (declared, EAS), V_D 55.5 m/s; gust load factors +2.37 / -0.37 at V_C,
  +1.96 / +0.04 at V_D; envelope +3.8 / -1.5 (manoeuvre governs). CS-23 minimum V_C for this W/S would be 74.8 m/s (not used).
* Rotors: T_max 1,902 N, Q_max 198 N m (x 1.25 fault factor). One motor out: the remaining rotors need at most **86 %** of
  T_max at 1.0 g and **103 %** at 1.2 g (all eight failure cases yaw-trimmed) -> the 1.0 g requirement is met, but there is
  no margin for a 1.2 g flare/climb with a rotor out.
* Landing 3 g (gear reaction 3 W, no rotor lift), one-side, side load; crash factors per item (batteries 18 g fwd);
  parachute in four directions.

### Sized primary structure (`results/sizing_update.json`, geometry.json section format)
Main / rear spar (UD caps, +-45 webs; `stations`, eta = |y| / 4.4 m):

| spar | eta | y (m) | b_cap (mm) | t_cap (mm) | t_web (mm) x webs |
|---|---|---|---|---|---|
| main | 0.000 | 0.00 | 80 | 5.68 | 0.50 x 2 |
| main | 0.098 | 0.43 | 77 | 6.04 | 0.80 x 2 |
| main | 0.200 | 0.88 | 74 | 4.97 | 0.73 x 2 |
| main | 0.330 | 1.45 | 70 | 3.85 | 0.73 x 2 |
| main | 0.500 | 2.20 | 65 | 2.15 | 0.50 x 2 |
| main | 0.700 | 3.08 | 59 | 1.00 | 0.50 x 2 |
| main | 0.850 | 3.74 | 55 | 1.00 | 0.50 x 2 |
| main | 1.000 | 4.40 | 50 | 1.00 | 0.50 x 2 |
| rear | 0.000 | 0.00 | 50 | 1.00 | 0.50 x 1 |
| rear | 0.098 | 0.43 | 48 | 1.48 | 2.21 x 1 |
| rear | 0.200 | 0.88 | 46 | 1.34 | 1.91 x 1 |
| rear | 0.330 | 1.45 | 43 | 1.15 | 2.04 x 1 |
| rear | 0.500 | 2.20 | 40 | 1.00 | 0.50 x 1 |
| rear | 0.700 | 3.08 | 36 | 1.00 | 0.50 x 1 |
| rear | 0.850 | 3.74 | 33 | 1.00 | 0.50 x 1 |
| rear | 1.000 | 4.40 | 30 | 1.00 | 0.50 x 1 |

Torsion skin +-45 carbon 0.50 mm (minimum gauge, MS +2.5). Booms (both, `segments`, `tube_layers`):

| x range (m) | wall (inside -> out) | OD (mm) |
|---|---|---|
| -1.51 ... 0.49 | 1.60 mm cf_tube_rollwrapped_twill + 0.50 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 106.8 |
| 0.49 ... 3.46 | 1.60 mm cf_tube_rollwrapped_twill + 3.07 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 111.9 |
| 3.46 ... 6.76 | 1.60 mm cf_tube_rollwrapped_twill + 1.24 mm cf_ud_wet + 0.50 mm cf_fabric_wet_45 | 108.3 |

Tail spar: 50 x 2.48 mm twill tube. Rotor pylons: 6061-T6 tube
100 x 1.6 mm, 0.5 m. Gear cross tubes 76 x 5.8 mm 6061-T6 (strength only; see gear).
Cabin (`results/fuselage.json`): two keel walls H80 12.7 mm + 2-ply faces with 40 x 3.6 mm UD caps; floor H80 19 mm 2-ply faces;
wing-root ring frames with 60 x 1.8 mm UD straps from the lugs to the keels and H100 19 mm side posts; tail-cone parachute
frame straps 2 x 60 x 0.9 mm UD; battery boxes 2 / 2.5 mm 6061-T6 with G10 cell frames, 6 AN4 brackets per pack.
Sandwich panels were checked with sandwich theory (face stress, core shear, wrinkling, shear buckling), not with CalculiX
composite shells (see verification C6).

Fittings (CalculiX C3D10, `docs/models/fea/P*.png/.glb`): P1 wing-root lug 7075-T6 12 mm, pin 3/4 in, 8 x AN5; P2 boom saddle
6061-T6 wall 12 mm x 110 mm, 4 x AN6 (rear saddle with fore-aft slotted holes so the boom-spar portal is not redundant);
P3 motor plate 6061-T6 10 mm on the pylon; P4 gear saddle 6061-T6 wall 18 x 150 mm, 6 x AN6; P5 parachute riser point
4130 N 12 mm, 8 x AN5; P6 seat-leg fitting 7075-T6 14 mm lug, 2 x AN5. FE peaks are multiplied by 1.20 (mesh factor from
the P1 convergence study, validation D6).

### All margins, lowest first (full list: `results/margins.json`)
| MS | Item | Mode | Critical case |
|---|---|---|---|
| -1.00 | frequency placement: boom/rotor modes within +-10 % of hover 1P/2P | 11 HIGH flags |  |
| -0.77 | landing gear: limit drop, inertia factor <= 3.0 | energy (0.33 m drop, L = 2/3 W) | limit drop |
| -0.61 | landing gear: cross tube yield at the limit drop | elastic stress vs Fty | limit drop |
| +0.05 | member: gear cross tube | compression | L2 level landing 3.0 g with drag 0.25 x vertical (inclined r |
| +0.10 | member: boom_L | compression | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +0.10 | member: boom_R | compression | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +0.10 | member: spar main | compression | F A  manoeuvre +n at VA |
| +0.10 | member: spar rear | compression | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +0.10 | member: tail spar | compression | C4 parachute opening 4.8 g, aft-up-right 45/30 deg |
| +0.16 | fitting P1_wing_root_lug (CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.20 mesh factor) | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +0.18 | cabin: keel UD caps (40 mm wide) | sandwich / hand method | envelope |
| +0.19 | fitting P5_parachute_hardpoint (CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.20 mesh factor) |  |
| +0.22 | cabin: wing-root frame UD strap (60 mm, each side, each frame) | sandwich / hand method | envelope |
| +0.26 | cabin: keel potted insert bearing (battery bracket) | sandwich / hand method | envelope |
| +0.38 | cabin: floor face wrinkling | sandwich / hand method | envelope |
| +0.41 | fitting P4_gear_saddle (CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.20 mesh factor) | L2 level landing 3.0 g with drag 0.25 x vertical (inclined r |
| +0.41 | fitting P5_parachute_hardpoint yield at limit | von Mises vs Fty at limit |  |
| +0.42 | cabin: floor faces (cargo 6 g) | sandwich / hand method | envelope |
| +0.43 | cabin: keel web faces (shear) | sandwich / hand method | envelope |
| +0.52 | cabin: rear parachute frame UD straps (2 x 60 mm) | sandwich / hand method | envelope |
| +0.54 | fitting P1_wing_root_lug yield at limit | von Mises vs Fty at limit | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +0.56 | fitting P6_seat_fitting (CalculiX C3D10) | von Mises vs Ftu (ult. x 1.15, x 1.20 mesh factor) |  |
| +0.66 | cabin: wing-root frame side post faces (lateral lug load) | sandwich / hand method | envelope |
| +0.95 | fitting P4_gear_saddle yield at limit | von Mises vs Fty at limit | L2 level landing 3.0 g with drag 0.25 x vertical (inclined r |
| +1.07 | fitting P6_seat_fitting yield at limit | von Mises vs Fty at limit |  |
| +1.25 | cabin: battery box front wall 2.5 mm between stiffeners (18 g) | sandwich / hand method | envelope |
| +1.25 | cabin: battery bracket bearing 6061-T6 3 mm | sandwich / hand method | envelope |
| +1.31 | cabin: seat rail insert in keel cap region (bearing) | sandwich / hand method | envelope |
| +1.63 | fitting P2_boom_wing_clamp bolts shear | analytic | C1 parachute opening 4.8 g, aft (deployment along the flight |
| +1.73 | cabin: floor core shear H80 | sandwich / hand method | envelope |
| +2.10 | fitting P1_wing_root_lug lug shear_out | analytic | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +2.19 | cabin: battery bracket bolts AN4 (shear, 18 g fwd) | sandwich / hand method | envelope |
| +2.22 | fitting P1_wing_root_lug lug bearing | analytic | C3 parachute opening 4.8 g, vertical (inflated, low speed) |
| +2.30 | boom wall bearing under the saddle clamp (transverse crushing) | clamp pressure vs 0.5 Yc (wet UD over-wrap) | C1 parachute opening 4.8 g, aft (deployment along the flight |

### Mass change vs selected_design.json
| item | delta (kg) |
|---|---|
| wing spars + torsion skin (in wing 73.7 kg) | -9.3 |
| booms (33.8 kg) | -2.4 |
| gear cross tubes (in landing gear 27.0 kg) | +3.1 |
| rotor pylons x 8 (not in the breakdown) | +5.3 |
| tail spar (in tail 8.3 kg) | +0.3 |
| gear energy absorbers (4 dampers, estimate; design change) | +6.0 |
| **total** | **+3.0** (MTOW ~1005 kg) |

Not added (assumed inside the Raymer structure masses, to be confirmed with the CAD weights): machined fittings
48 kg as modelled (P1 x4 3.1, P2 x4 9.7,
P3 x8 13.7, P4 x4 16.6, P5 x3 3.4,
P6 x8 1.7 kg; P3 and P4 have large margins and can be lightened), cabin primary members
42 kg (keels, floor, frames, battery boxes; inside fuselage 39.7 kg + battery overhead).

### Deflections (limit)
Wing tip 218 mm at +3.8 g (5 % of the semi-span); boom ends 115 mm in 1 g hover and 180 mm at max thrust / one motor out
(front and rear rotors tilt ~2-3 deg: rotor-shaft pre-cant or stiffer outer boom segments recommended); parachute vertical
case 390 mm at the boom ends.

### Dynamics and aeroelasticity (`results/dynamics.json`, `docs/models/fea/campbell.png`, `flutter_vg.png`, `airframe_modes.png`)
* Free-free modes (Hz): 2.6, 2.7, 3.6, 3.6, 3.8, 3.9, 4.2, 4.8, 5.5, 8.3, 8.6, 11.4, ... The first eight (2.6-5.5 Hz) are rotors rocking on the booms (boom torsion + pylon
  bending) - inside the flight-control bandwidth: notch filters / structural-coupling test needed; a +1.5 mm +-45 over-wrap
  only raises them ~5 %, a larger boom diameter (GJ ~ D^3) is the effective fix.
* Campbell: lift 1P (hover 1,964 rpm = 32.7 Hz, range 1,450-2,409 rpm) and 2P cross a dense band of boom/pylon modes;
  11 HIGH flags = boom-dominated modes within +-10 % of hover 1P/2P (29.6, 30.0, 32.3, 32.6 Hz; 59-66 Hz) and the
  tail/boom modes at 101-104 Hz near the pusher 3P at cruise rpm. Stiffening studies (+2 mm UD: +17 kg; pylon 120 x 3)
  only move modes within the band. Mitigations: rotor balance/track to a tight standard, elastomeric motor-mount isolators
  tuned below 1P, avoid steady hover dwell at the crossing rpm, ground vibration test to update the beam model.
* Divergence: V_div 364 m/s EAS vs 1.2 V_D = 66.6 m/s.
* Flutter (24 modes, strip Theodorsen, k-method, g = 0.02): first crossing 254 m/s at
  5.3 Hz vs 1.2 V_D = 66.6 m/s (margin +2.8). Ailerons and elevator to be
  mass-balanced (control-surface flutter not modelled).
* Pusher whirl flutter: mount K = 1.74 MN m/rad (tail cone), stable to 1.3 V_D; still stable with 1.1 % of
  the stiffness at 1.2 V_D. Lift rotors: edgewise flow in transition, stopped in cruise -> classical whirl not applicable.

### Design changes required / recommended
1. **Landing gear (required):** the elastic aluminium skid gear is far too stiff for a 0.33 m limit drop with 2/3 W rotor lift:
   n = 12.8 g and the cross tubes yield. Add energy absorbers (oleo-pneumatic or gas-spring struts, >= 75 mm stroke at
   eta 0.8; or >= 130 mm with a linear spring) between the cross tubes and the keel, or a long composite bow (an elastic 6061
   arm would need ~2 m). Estimate +6 kg. Re-check the gear and saddles with the damper load (2.3 W).
2. **Boom saddles:** rear saddle with fore-aft slotted holes (or elastomeric bushing) as modelled; otherwise the boom-spar
   portal attracts ~60 kN fore-aft forces into the clamp bolts.
3. **Rotor pylons** (0.5 m, not in the mass breakdown): +5.3 kg; boom/rotor frequency placement as above (open item, needs GVT).
4. **One-motor-out at 1.2 g** needs 103 % thrust: no reserve for flare with a failed rotor (flight-control/propulsion item).
5. Parachute loads drive the booms, rear spar web and wing-root lugs: confirm the vendor opening load for 1,002 kg at the
   maximum deployment speed and limit the deployment speed if needed.
6. Fittings P3/P4 can be lightened (MS +2.8 / +0.4 after the mesh factor); CAD (WP G) should adopt the dimensions above and
   the detailed models be rerun on the STEP parts.

## Known limitations

* Beam model: wing ribs and fittings are stiff links; fitting flexibility and local load introduction are analysed
  with CalculiX part models (C3D10/C3D20R, `ccx.py`) using the fitting loads from `airframe_<tag>.json`.
* Tapered members are piecewise constant; stresses converge O(h) (verification B2) – keep >= 20 elements per
  half-span (study L7: 0.7 % on spar stress at 20, used by default).
* Composite S8R shells in CalculiX do **not** capture sandwich core shear (verification C6: 70 % too stiff); sandwich
  panels are modelled with layered solids (C3D20R) or checked with sandwich beam/plate theory.
* CalculiX `*EL PRINT` shell stresses come in the element/ply axes (C4, C7), not global axes.
* Aeroelastic (divergence, flutter, whirl) checks are not part of these tools; the free-free modes and rotor
  excitation frequencies are reported for the frequency-placement check.
