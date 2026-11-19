# WP P verification: propulsion parts consistency

Pass 2 (final design, iteration 3) is the first section below; the pass-1 screening (method, grid results, risks 1-11) follows it.

Purpose (pass 1): confirm that the motor + inverter + rotor families short-listed in [bom/catalog.json](../../bom/catalog.json)
are mutually consistent (voltage, current, power, torque, rpm, tip speed) over the expected design space, before WP D
freezes the configuration. This is a screening check; WP D owns the final sizing.

## Pass 2: final design (iteration 3.3, ALL_rpmfree, frozen)

The frozen design is:
- lift: 8 x EMRAX 268 MV, liquid cooled, with 8 x E-PROPS 1.85 m 2-blade rotors;
- pusher: 2 x MGM REB 90 on the boom tails with 2 x E-PROPS 1.75 m 2-blade propellers, both turning the same way;
- inverters: 10 x HBCi 400800;
- battery: 4 packs of 175s5p Molicel P50B (3,500 cells, 63 kWh);
- MTOW 1,350 kg.

Inputs are `design/selected_design.json`, `design/geometry.json` and `bom/catalog.json`. The tables are in
[results_tables.md](results_tables.md) (section "Final design").

| Check | Result | Verdict |
|---|---|---|
| EMRAX 268 LC against the datasheet (91 kW / 205 N m continuous, 210 kW / 500 N m peak, 4,500 rpm limit) | hover 39.9 kW / 202 N m at 1,889 rpm (torque margin **+1.6 %**); OEI 1.0 g 72.1 kW / 301 N m (+66 %); OEI flare 71.0 kW / 296 N m (+69 %) | pass, but hover sits on the continuous-torque limit; EMRAX quote item 2 |
| Winding / voltage | the MV winding (KV 8.68 rpm/V no-load) gives 2,289 rpm at the 492 V worst bus (minimum KV 5.9). It would turn **about 6,400 rpm no-load at the 735 V full-charge bus, above the 4,500 rpm limit** | open: EMRAX winding choice (HV, KV 5.83, is just below the minimum), inverter speed limiting; EMRAX quote item 1 |
| Rotor rpm cap (flight-control software) | the OEI rpm (2,289) is far below the motor limit | the cap is a software requirement for WP V; the motor overspeed protection belongs in the inverter |
| Pusher REB 90 x 2 | 53.0 kW / 244 N m per unit at 2,074 rpm against the assumed 60 kW continuous (+13 %); 60 kW at 2,074 rpm implies 276 N m continuous, while MGM publishes 300 N m without a torque-speed curve | depends on the unpublished curve; MGM quote item 1 |
| Bus (P50B DCIR, 3.45 V/cell at low SOC) | all packs: 525 V and 35.1 A per cell; one pack out: 492 V and 49.9 A per cell | pass |
| Inverter HBCi 400800 | 160 A at OEI vs 400 A; 735 V vs 800 V | pass; MGM must confirm the HBCi drives the EMRAX (resolver) |
| Motor axial load | 2,511 N lift (OEI flare), 2,305 N pusher; the EMRAX axial limit is not published (REB limit 2,500 N) | open: EMRAX quote item 3 |
| Lift rotors | 1.85 m is within the 1.90 m matched CW/CCW range; 72 kW against the 86 kW 2-blade rating; tip Mach 0.64 at OEI | pass |
| Pusher propellers | 1.75 m (68.9 in), both the same rotation, within the published CW range (82 in) | pass. The 3.2 counter-rotation problem is gone |
| Independent hover check (momentum theory, WP D FM 0.726, 3.3 % download) | 40.9 kW vs WP D 39.9 kW (+2.5 %) | consistent |

Pass-2 risks. These replace the 3.2 items and extend the pass-1 list below.

| # | Risk | Mitigation |
|---|---|---|
| 12 | Hover is within 1.6 % of the EMRAX 268 LC continuous torque | stand test with the coolant loop; the combined-cooled (CC, 226 N m) variant needs airflow |
| 13 | The EMRAX MV winding overspeeds at full-charge voltage; the HV winding is just below the KV needed with one pack out | EMRAX winding quote; HBCi speed limiting |
| 14 | EMRAX 188-348 going out of production | quote the next-generation equivalent |
| 15 | REB 90 continuous torque at about 2,070 rpm not published | MGM curve |
| 16 | `design/geometry.json` gear_strut_section (5.82 mm wall) differs from the CAD leg (3 x 0.095 in) | WP D/G to align |
| 17 | `cad/parts.json` MOT-PB note still says "same motor type as the lift units" (now REB 90 vs EMRAX) | WP G text fix |

Files

- [check_propulsion.py](check_propulsion.py) - the check (reads component data IDs from `bom/catalog.json`).
- [results.json](results.json) - every case with pass/fail reasons.
- [results_tables.md](results_tables.md) - generated tables (do not edit by hand).

Run: `python3 validation/parts/check_propulsion.py`

## Method and assumptions

| Item | Value | Basis |
|---|---|---|
| Sizing atmosphere | 1000 m, ISA+15 C, rho = 1.055 kg/m3 | hover ceiling in `requirements/requirements.yaml` |
| Hover power | momentum theory, P = T^1.5 / sqrt(2 rho A) / FM, FM = 0.70 | estimate; typical 0.6-0.75 for propellers used as lift rotors |
| Download | +5 % thrust | estimate (wing/boom blockage); WP C to replace |
| Motor / inverter efficiency | 0.92 / 0.97 | estimate (EMRAX lists up to 96 % peak) |
| Hover tip speed | from CT/sigma <= 0.13 with sigma = 0.10, minimum 140 m/s | calibrated: NS62x24 at its 101.4 kgf bench point gives CT = 0.0131 (CT/sigma = 0.131 at sigma 0.10) |
| One-motor-out (OEI) | worst rotor thrust x n/(n-2) x 1.10 control margin; fixed pitch so Q ~ T, P ~ T^1.5, rpm ~ sqrt(T) | estimate: opposite rotor throttled back for balance; requirement: OEI at MTOW within 100 % peak power |
| Bus voltage | low-SOC loaded cell 3.3 V; max 4.2 V | estimate / datasheet |
| KV under load | 0.79 x no-load KV | U15XXL bench (2203 rpm at 96 V, KV 29) |
| Tip Mach limit (OEI) | 0.65 | estimate (noise/compressibility screen) |
| Inverter short-time current HBCi 100400 | 125 A | estimate = 50 kW short-time / 400 V (MGM page) |

Calibration: the model's overall hover efficiency (FM x eta_motor x eta_inv = 0.625) is lower than the overall
efficiency implied by the T-Motor NS62x24 bench data (0.73-0.75, bench density assumed 1.18 kg/m3), so the power
figures are conservative.

## Results

Grid: MTOW 500-900 kg, 6 or 8 lift rotors, D = 1.8-2.6 m. Full tables in [results_tables.md](results_tables.md).

| Combination | Passes | First failure | Comment |
|---|---|---|---|
| A: MGM REB 30 + HBCi 100400, 8 rotors, 94s bus | MTOW 500-600 kg at D 1.8-2.2 m; 700 kg at D 1.8-1.9 m | 700 kg at D >= 2.0 m: OEI torque 152-157 Nm > 150 Nm; 800 kg: OEI torque and inverter current | Lightest lift set (8 x 7.7 kg motors, 8 x 1.8 kg inverters). At 700 kg / 1.8 m the OEI DC current (107 A) relies on the inverter short-time rating. 96s gives 403 V max: the bus must be 94s or fewer for a 400 V inverter. |
| B: MGM REB 50 + HBCi 400800, 6 rotors, 180s bus | MTOW 500 kg (all D), 600 kg at D 2.0 m | 600-900 kg: OEI torque 215-382 Nm > 200 Nm | With 6 rotors the n/(n-2) = 1.5 OEI factor drives torque beyond every motor screened. |
| B8: MGM REB 50 + HBCi 400800, 8 rotors, 180s bus | all MTOW 500-900 kg at D 1.9 m; to 800 kg at D 2.2-2.4 m | 900 kg at D >= 2.2 m: OEI torque 215-229 Nm | Robust over the whole MTOW range, at +34 kg motor mass and +18 kg inverter mass vs combination A. |
| D: MAD M90C60 EEE + HBCi 400400, 8 rotors, 94s bus | all cases to 900 kg at D 1.9 and 2.2 m | 800-900 kg at D 1.8 m: OEI rpm exceeds what a 9 KV winding reaches at 310 V | Passes on power only: no torque or continuous rating published by the maker. |
| E: EMRAX 228 MV as direct-drive lift, 6 rotors | 500 kg, 600 kg at D 2.0 m | hover torque > 130 Nm continuous from 600-700 kg | Axial-flux EMRAX motors are torque-limited at rotor rpm; not a lift option. |
| T-Motor U15XXL kit (24S, NS62x24 1.575 m), 8 rotors, bench table | 500 kg at sea level ISA+15 only | 500 kg at 1000 m ISA+15: OEI thrust beyond the 101 kgf bench maximum; 600 kg: hover current above the 150 A ESC continuous rating | Not viable for the hot-and-high OEI requirement. |

Pusher (direct drive, static tip speed 200 m/s, D 1.6-1.9 m, 2010-2390 rpm): only the **REB 90** provides >= 40 kW
continuous (60 kW); REB 50 gives 30 kW continuous / 42-50 kW peak and EMRAX 228 gives 27-33 kW continuous /
46-55 kW peak at these speeds. Helical tip Mach at 150 km/h is 0.59. A single motor type for lift and pusher (REB 50)
is therefore only possible if WP D shows a continuous cruise shaft power <= 30 kW.

Battery: with P50B cells (18 Wh, 60 A) a 40-80 kWh pack at 150-300 kW hover runs at 1.9-7.5C (9-38 A per cell);
with one of two packs out the cell current doubles to 19-75 A, so a 40 kWh / 300 kW case would exceed the 60 A
rating. Pack energy and hover power from WP D must keep the one-pack-out cell current at or below 60 A
(two packs) or the aircraft needs more than two packs.

## Conclusions for the catalog

1. Baseline: **8 lift rotors of 1.8-1.9 m** (largest diameter with COTS matched CW/CCW pairs from E-PROPS; Sensenich
   and Helix cover larger sizes but need quotes).
2. **REB 30 + HBCi 100400 on a 94s bus for MTOW <= 700 kg; REB 50 + 800 V-class MGM inverter on a ~180s bus for
   700-900 kg.** WP D should feed back the MTOW so the choice can be frozen.
3. Pusher: REB 90 unless cruise shaft power is <= 30 kW continuous (then REB 50 for a single motor type).
4. MGM does not publish KV; the winding must be specified to MGM for the chosen bus voltage and the hover/OEI
   rpm in this table (1,400-2,100 rpm).

## Risks (propulsion parts)

| # | Risk | Effect | Mitigation |
|---|---|---|---|
| 1 | MGM/EMRAX ratings are catalogue values, installation dependent ("30-40 kW" ranges, 25 C ambient) | OEI margin smaller in a hot nacelle | Request continuous/peak maps at 40 C and the chosen cooling; bench test one motor + inverter + rotor on a thrust stand before ordering the set |
| 2 | No KV/winding data for MGM motors | rpm/voltage mismatch | Specify winding with supplier; check at 3.3 V/cell low-SOC voltage |
| 3 | HBCi 100400 OEI current near/above 100 A continuous (fluid cooled) | inverter derating or trip in OEI | Fluid cold plate; confirm short-time (>=60 s) current; consider HBCi 400400 for growth |
| 4 | 96 cells x 4.2 V = 403 V exceeds 400 V inverter limit | overvoltage at full charge | 94s maximum (or charge to 4.15 V) |
| 5 | Fixed-pitch rotor thrust response slow at 1.5-1.9 m (rotor inertia) | reduced control bandwidth, especially after a motor failure | WP D/F control analysis with rotor inertia; keep rotors <= 1.9 m |
| 6 | E-PROPS/Sensenich UAV props sold for drones; VTOL use excluded from E-PROPS manned warranty | no fatigue substantiation for edgewise flow / transition | Obtain supplier load data and RPM limits; whirl and fatigue test; ASTM F2506-type testing |
| 7 | China export licensing (from 18 Nov 2026) and US entity listing | T-Motor/MAD/Hobbywing supply uncertain | Baseline uses EU motors, inverters and propellers |
| 8 | EMRAX range going out of production | pusher alternate may change | Quote successor model |
| 9 | Single-source MGM for motors and inverters | schedule | Keep EMRAX/Geiger as pusher fallback; MAD M90C60 as lift fallback |
| 10 | One-pack-out cell current | cell overheating | Size packs so one-pack-out current <= 60 A/cell (P50B) or use 3-4 packs |
| 11 | OEI rule n/(n-2) is a screening simplification | real worst-rotor factor depends on layout and control allocation | WP D to compute with the actual rotor positions and yaw authority |
