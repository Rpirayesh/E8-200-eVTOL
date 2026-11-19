# Independent design check - selected

Design: **E8-200 selected design: 8 x 1.85 m lift rotors (MOT-REB60), CELL-P50B 159s5p x 3 packs, 8.6 m wing, 150 km/h**  
Input: `design/selected_design.json`  
Checker: `methods/check_design.py` (equations in `methods/EQUATIONS.md`; tags in the *eq* column).

Summary: **48 PASS, 10 WARN, 1 FAIL**, 0 informational (no D value), 0 missing.

M = this independent check, D = value reported in the design file. diff = (M - D)/D.

| status | quantity | M | D | diff | unit | tolerance | eq | note |
|---|---|---|---|---|---|---|---|---|
| PASS | wing span: geometry.json vs selected_design | 8.600 | 8.600 | +0.0% | m | ±1% warn / ±5% fail | - |  |
| PASS | wing area from geometry.json chords | 9.890 | 9.890 | -0.0% | m^2 | ±1% warn / ±5% fail | trapezoid |  |
| PASS | MTOW = empty (excl. battery) + battery + payload | 1089.7 | 1089.7 | +0.0% | kg | ±1% warn / ±5% fail | [M0] | bookkeeping closure of D's own numbers |
| PASS | wing span <= footprint limit | 8.600 | - | - | m | <= 9 | req. |  |
| PASS | overall length incl. booms and rotor discs <= footprint limit | 8.468 | - | - | m | <= 9 | req. |  |
| PASS | disk loading | 497.0 | 497.0 | -0.0% | N/m^2 | ±1% warn / ±5% fail | [H0] |  |
| PASS | figure of merit (M: blade-element estimate) | 0.718 | 0.719 | -0.0% | - | ±10% warn / ±20% fail | [H2]-[H3] |  |
| PASS | hover shaft power per motor, site (500 m ISA+15) | 29.8 | 29.8 | -0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3] |  |
| PASS | hover electrical power total, site | 271.2 | 271.2 | -0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover electrical power total, 1000 m ISA+15 ceiling | 275.2 | 275.2 | -0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover shaft power per motor at 1000 m ISA+15 <= motor continuous | 30.2 | - | - | kW | <= 36 | [H1] |  |
| PASS | lift-rotor hover tip Mach (ISA+15) | 0.516 | 0.516 | +0.0% | - | ±3% warn / ±8% fail | [H7] |  |
| PASS | lift-rotor tip Mach (noise screen) | 0.516 | - | - | - | <= 0.55 | [H7] | NASA UAM concepts use 550-600 ft/s (Mtip ~0.49-0.54) |
| PASS | hover blade loading CT/sigma (stall margin for transition) | 0.114 | - | - | - | <= 0.14 | [H5] |  |
| PASS | rotor-out shaft power, most loaded motor (incl. 10 % thrust control margin) | 49.7 | 53.7 | -7.4% | kW | ±10% warn / ±20% fail | [H6] |  |
| PASS | rotor-out power <= motor peak power | 49.7 | - | - | kW | <= 60 | [H6] req. |  |
| PASS | rotor-out torque <= motor max torque | 212.3 | - | - | N m | <= 250 | [H6] |  |
| PASS | Oswald efficiency | 0.825 | 0.825 | -0.0% | - | ±15% warn / ±30% fail | [I2] |  |
| PASS | zero-lift drag area D/q | 0.533 | 0.533 | +0.1% | m^2 | ±15% warn / ±30% fail | [D1]-[D9] |  |
| PASS | cruise drag | 1132.1 | 1131.6 | +0.0% | N | ±15% warn / ±30% fail | [I1] |  |
| PASS | cruise L/D | 9.440 | 9.444 | -0.0% | - | ±15% warn / ±30% fail | [I1] |  |
| PASS | pusher propulsive efficiency | 0.792 | 0.792 | -0.0% | - | ±10% warn / ±20% fail | [P1]-[P2] |  |
| PASS | cruise electrical power | 68.9 | 68.9 | +0.0% | kW | ±10% warn / ±20% fail | [E1] |  |
| PASS | cruise shaft power <= pusher motor continuous | 59.6 | - | - | kW | <= 60 | [E1] |  |
| PASS | pusher helical tip Mach in cruise | 0.560 | - | - | - | <= 0.7 | [H7] |  |
| PASS | stall speed (sea level ISA, MTOW) | 29.6 | 29.6 | +0.0% | m/s | ±3% warn / ±8% fail | [S1] |  |
| PASS | cruise speed >= 1.3 x stall (TAS at cruise altitude) | 1.341 | - | - | - | >= 1.3 | [S2] |  |
| PASS | cruise speed >= requirement | 150.0 | - | - | km/h | >= 150 | req. |  |
| PASS | gust load factor at VC (Ude 15.24 m/s) <= design limit | 2.225 | - | - | g | <= 3.8 | [L3] |  |
| PASS | nominal energy from cells (series x parallel x cell Wh) | 42.9 | 42.9 | +0.0% | kWh | ±1% warn / ±5% fail | [B1] |  |
| PASS | battery pack mass (cells / (1 - overhead)) | 241.9 | 225.8 | +7.1% | kg | ±10% warn / ±20% fail | [B2] | overhead fraction 0.30 |
| PASS | mission energy (design range, at battery terminals / eta_batt) | 24.3 | 25.9 | -6.0% | kWh | ±10% warn / ±20% fail | [E2]-[E4] |  |
| WARN | range to 20 % reserve at EOL capacity | 26.5 | 23.3 | +13.7% | km | ±10% warn / ±20% fail | [R1] |  |
| PASS | range at EOL with 20 % reserve >= design range | 26.5 | - | - | km | >= 20 | [R1] |  |
| PASS | nominal battery energy >= required (EOL, reserve) | 42.9 | - | - | kWh | >= 36.1326 | [B3] |  |
| WARN | hover C-rate at EOL capacity (ceiling) | 8.435 | 9.665 | -12.7% | 1/h | ±10% warn / ±20% fail | [B4] |  |
| PASS | hover C-rate <= cell continuous rating - 0.3 C margin | 8.435 | - | - | 1/h | <= 9.7 | [B4] req. |  |
| PASS | rotor-out C-rate <= cell peak rating | 7.970 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | independent battery packs/buses | 3 | - | - | - | >= 2 | req. |  |
| PASS | C-rate with one pack failed (hover landing) <= cell peak rating | 12.7 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | lift motor mass each (catalog) vs NDARC torque regression | 13.7 | 15.3 | -10.7% | kg | ±25% warn / ±50% fail | [M8] |  |
| PASS | inverters + HV harness (vs NASA 0.63 x motor accessory factor) | 57.7 | 67.5 | -14.6% | kg | ±25% warn / ±50% fail | [M16] |  |
| PASS | wing mass | 74.0 | 72.7 | +1.7% | kg | ±25% warn / ±50% fail | [M1] |  |
| WARN | fuselage mass | 47.5 | 66.3 | -28.3% | kg | ±25% warn / ±50% fail | [M5] |  |
| PASS | landing gear mass | 40.4 | 52.7 | -23.4% | kg | ±25% warn / ±50% fail | [M6] |  |
| PASS | booms mass | 47.4 | 46.4 | +2.2% | kg | ±25% warn / ±50% fail | [M10] |  |
| PASS | lift motors mass | 109.3 | 122.4 | -10.7% | kg | ±25% warn / ±50% fail | [M8] |  |
| PASS | lift rotors mass | 27.7 | 31.6 | -12.4% | kg | ±25% warn / ±50% fail | [M9] |  |
| WARN | parachute mass | 21.3 | 35.4 | -39.7% | kg | ±25% warn / ±50% fail | [M15] |  |
| WARN | tail (H + V) mass | 7.889 | 10.6 | -25.3% | kg | ±25% warn / ±50% fail | [M3]-[M4] |  |
| WARN | pusher motor mass | 18.6 | 27.3 | -32.0% | kg | ±25% warn / ±50% fail | [M8] |  |
| WARN | pusher propeller mass | 1.861 | 3.630 | -48.7% | kg | ±25% warn / ±50% fail | [M9] |  |
| WARN | seats mass | 33.9 | 22.7 | +49.7% | kg | ±25% warn / ±50% fail | [M11] |  |
| PASS | avionics mass | 10.7 | 12.5 | -14.7% | kg | ±25% warn / ±50% fail | [M12] |  |
| PASS | lv electrical mass | 10.0 | 10.0 | +0.0% | kg | ±25% warn / ±50% fail | [M13] |  |
| WARN | wing mass, NDARC AFDD93 cross-check | 102.2 | 72.7 | +40.6% | kg | ±25% warn / ±50% fail | [M2] |  |
| FAIL | empty mass excluding battery | 515.3 | 663.9 | -22.4% | kg | ±10% warn / ±20% fail | [M0] | D's breakdown contains a growth allowance; M has none |
| WARN | MTOW recomputed (M empty + D battery + payload) | 941.1 | 1089.7 | -13.6% | kg | ±10% warn / ±20% fail | [M0] |  |
| PASS | acquisition cost per aircraft (Eastlake airframe + COTS propulsion/systems) | 4.14e+05 | 447765 | -7.6% | USD | ±30% warn / ±60% fail | [C1]-[C9] | recurring airframe (Eastlake hours x rate + materials) + D's COTS propulsion/systems total |

## Key recomputed values

- Disk loading 497 N/m^2; hover FM (M) 0.718; hover electrical 271.2 kW at the site, 275.2 kW at the ceiling.
- Cruise: CL 1.123, CD0 0.0539, L/D 9.44, drag 1132 N, propeller eta 0.792, electrical 68.9 kW.
- Mission energy 24.34 kWh (hover 9.59, transitions 2.98, climb 2.10, cruise 9.67); nominal energy required 36.1 kWh; range 26.5 km.
- C-rates at EOL: hover (site) 8.31, hover (ceiling) 8.43, cruise 2.11, rotor-out (approx.) 7.97.
- Gust load factor at VC 2.22 g; wing loading 1081 N/m^2.
- Empty mass excluding battery (M) 515.3 kg; MTOW (M) 941.1 kg.

### Drag-area build-up (m^2)

| item | D/q |
|---|---|
| wing | 0.0759 |
| fuselage | 0.0890 |
| booms | 0.0180 |
| tail_h | 0.0127 |
| tail_v | 0.0076 |
| stopped_lift_rotors | 0.1704 |
| landing_gear | 0.1012 |
| other_listed | 0.0100 |
| excrescence_interference | 0.0485 |
| total | 0.5334 |
| swet_wing_m2 | 18.2407 |
| swet_fuselage_m2 | 15.7880 |

### Component mass estimates (kg)

| item | kg |
|---|---|
| wing | 74.0 |
| tail_horizontal | 4.5 |
| tail_vertical | 3.4 |
| fuselage | 47.5 |
| landing_gear | 40.4 |
| flight_controls | 7.1 |
| booms_and_fittings | 47.4 |
| lift_motors | 109.3 |
| pusher_motor | 18.6 |
| lift_rotors_blades_hubs | 27.7 |
| pusher_propeller | 1.9 |
| inverters_cooling_accessories | 57.7 |
| parachute | 21.3 |
| avionics_installed | 10.7 |
| electrical_lv | 10.0 |
| furnishings_seats | 33.9 |

### Assumptions used by the checker

```json
{
 "kappa_induced": 1.2,
 "cd0_blade": 0.015,
 "coax_factor": 1.0,
 "download_fraction": 0.03,
 "control_thrust_margin": 0.1,
 "eta_motor": 0.93,
 "eta_inverter": 0.97,
 "eta_wiring": 0.98,
 "eta_battery": 0.95,
 "aux_power_kw": 1.5,
 "battery_eol_fraction": 0.8,
 "reserve_fraction": 0.2,
 "c_rate_margin": 0.3,
 "pack_overhead_fraction": 0.3,
 "laminar_fraction_wing": 0.1,
 "laminar_fraction_body": 0.05,
 "excrescence_factor": 1.1,
 "cl_max_default": 1.4,
 "prop_profile_factor": 0.9,
 "eta_prop_cap": 0.86,
 "climb_rate_ms": 2.5,
 "cruise_alt_m": 500.0,
 "takeoff_alt_m": 0.0,
 "gust_ude_ms": 15.24,
 "transition_power_rule": "mean",
 "tech_factor_structure": 0.85,
 "tech_factor_rotor": 1.0,
 "flap_frequency": 1.1,
 "parachute_points": [
  [
   600.0,
   12.3
  ],
  [
   750.0,
   14.8
  ],
  [
   1050.0,
   21.7
  ],
  [
   757.0,
   12.4
  ],
  [
   950.0,
   17.6
  ]
 ],
 "cfrp_allowable_mpa": 300.0,
 "cfrp_density": 1550.0,
 "boom_fitting_factor": 1.6,
 "copper_density": 8960.0,
 "hv_current_density_a_mm2": 5.0,
 "harness_overhead": 1.4,
 "seat_mass_kg": 8.0,
 "accessory_factor": 0.4511,
 "lv_electrical_kg": 10.0,
 "_reasons": {
  "tech_factor_structure": "foam-core / wet-laid carbon sandwich structure; Raymer table 15.4 composite factor 0.85 (the WP M 'light' scenario uses the same value)",
  "accessory_factor": "inverters from the catalog (MGM HBCi, 1 per motor), HV harness from [M14] physics, cooling build-up; replaces the NASA 1.63 technology factor",
  "lv_electrical_kg": "COTS build-up (2 x 600 W DC-DC, 24 V LiFePO4, LV harness, panel, lights) instead of the Raymer GA electrical-system regression"
 }
}
```
