# Input schema for the independent checker (`design/selected_design.json` + `design/geometry.json`)

Owner of the files: WP D. Reader: `methods/check_design.py` (WP M), and CFD/FEA/CAD for `geometry.json`.
A complete worked example: `methods/examples/example_750kg_selected_design.json` and
`methods/examples/example_750kg_geometry.json`.

Rules: SI units (kg, m, m², s, W reported as kW where the key says `_kw`, km/h only where the key says `_kmh`);
coordinates in metres, x aft from the nose, y right, z up (WORKPLAN.md). Keys not listed are allowed and ignored.
**Required** keys are marked R; the others are optional but each one that is missing removes a comparison from the report
(it shows as `INFO`/not compared).

## `selected_design.json`

```jsonc
{
  "schema_version": "1.0",                      // R
  "name": "E8-200 baseline ...",                // R
  "requirements": {"range_km": 100, "cruise_speed_kmh_min": 150, "payload_kg": 200},

  "mass_kg": {                                  // R
    "mtow": 0,                                  // R  maximum take-off mass
    "payload": 200,                             // R
    "battery": 0,                               // R  installed pack mass (all packs)
    "empty": 0,                                 // R  empty mass EXCLUDING battery (mtow = empty + battery + payload)
    "breakdown": {                              // component masses compared one-to-one where the names match:
      "wing": 0, "fuselage": 0, "tail": 0, "booms": 0, "landing_gear": 0,
      "lift_motors": 0, "lift_rotors": 0, "inverters": 0, "hv_harness": 0, "cooling": 0,
      "pusher_motor": 0, "pusher_propeller": 0, "parachute": 0, "seats": 0, "avionics": 0,
      "lv_electrical": 0, "growth": 0           // growth allowance stated separately
    }
  },

  "environment": {"hover_design_altitude_m": 500, "hover_ceiling_m": 1000, "hover_isa_offset_C": 15,
                  "cruise_altitude_m": 500, "cruise_isa_offset_C": 15},

  "lift_rotors": {                              // R
    "count": 8,                                 // R  number of rotors (a coaxial pair counts 2)
    "coaxial": false,
    "diameter_m": 1.8,                          // R
    "blades": 2,
    "blade_chord_m": 0.17,                      // mean chord (or "solidity")
    "tip_speed_hover_ms": 150,
    "figure_of_merit": 0.72,                    // value used by D
    "download_fraction": 0.03,
    "stopped_drag_area_m2_each": null,          // D/q of one stopped rotor incl. motor and pylon, if D has it (else M estimates from the next 3 keys)
    "motor_diameter_m": 0.27, "motor_exposed_height_m": 0.08, "pylon_frontal_area_m2": 0.012,
    "motor": {"name": "MGM REB 50", "mass_kg": 12.0, "continuous_power_kw": 35, "peak_power_kw": 50, "max_torque_nm": 200},
    "positions": null                           // optional, if geometry.json is not supplied: [[x,y,z],...]
  },

  "pusher": {"diameter_m": 1.7, "blades": 3, "rpm_cruise": 2200, "eta_cruise": 0.82,
             "motor": {"name": "", "mass_kg": 0, "continuous_power_kw": 0, "peak_power_kw": 0}},

  "wing": {                                     // R
    "span_m": 9.0, "area_m2": 10.0,             // R
    "mac_m": 1.1, "thickness_ratio": 0.15, "max_thickness_x_c": 0.30, "sweep_deg": 0, "taper": 0.6,
    "cl_max": 1.5,                              // flaps as used for the stall-speed claim
    "oswald": 0.8,                              // value used by D
    "removable_for_transport": true
  },
  "fuselage": {"length_m": 4.8, "max_width_m": 1.15, "max_height_m": 1.35,   // R
               "wetted_area_m2": 15.5, "tail_arm_m": 3.3},
  "booms": {"count": 2, "length_m": 8.0, "diameter_m": 0.12, "rotor_arms_m": [1.5, 3.4]},  // arms: distance rotor hub -> wing spar
  "tail": {"horizontal_area_m2": 2.9, "vertical_area_m2": 1.6, "vertical_count": 2, "mac_m": 0.75, "thickness_ratio": 0.10},
  "landing_gear": {"type": "skid", "length_m": 0.5, "frontal_area_m2": 0.05},
  "drag": {"cd0": 0.032, "drag_area_m2": 0.33, "extra_items_m2": {"cooling_inlets": 0.01}},

  "battery": {                                  // R
    "energy_nominal_kwh": 60,                   // R  nameplate, beginning of life
    "series": 110, "parallel": 30, "independent_packs": 2,
    "cell": {"name": "Molicel P50B", "energy_wh": 18.0, "mass_kg": 0.071, "capacity_ah": 5.0, "v_nom": 3.6,
             "max_continuous_discharge_a": 40, "max_peak_discharge_a": 60}
  },
  "efficiencies": {"motor": 0.93, "inverter": 0.97, "wiring": 0.98},
  "aux_power_kw": 1.5,

  "mission": {                                  // R
    "range_km": 100, "cruise_speed_kmh": 150,   // R
    "hover_takeoff_s": 60, "hover_landing_s": 60, "transition_each_s": 30, "transitions": 2, "vertical_climb_m": 30
  },
  "cabin": {"seats": 2},
  "systems": {"avionics_uninstalled_kg": 10, "hv_cable_length_m": 40},
  "structure": {"limit_load_factor_positive": 3.8, "limit_load_factor_negative": -1.5, "landing_load_factor": 3.0},
  "limits": {"footprint_max_m": 9.0},
  "cost": {"units_produced_5yr": 10, "composite_fraction": 0.8, "cots_propulsion_systems_usd": 0,
           "labour_rates_usd_h": {"engineering": 95, "tooling": 65, "manufacturing": 55}, "f_cert": 0.5},

  "results": {                                  // D's reported performance: each key is compared with M's value
    "disk_loading_N_m2": 0,
    "hover_shaft_power_per_motor_kw": 0,        // at 500 m ISA+15
    "hover_electrical_power_kw": 0,             // total, 500 m ISA+15, incl. aux
    "hover_electrical_power_ceiling_kw": 0,     // total, 1000 m ISA+15
    "rotor_out_max_shaft_power_kw": 0,          // most loaded motor, one motor failed, incl. control margin
    "cruise_drag_N": 0, "cruise_LD": 0, "cruise_electrical_power_kw": 0,
    "mission_energy_kwh": 0,                    // design mission at the cells
    "range_km": 0,                              // to 20 % reserve at end-of-life capacity
    "stall_speed_ms": 0,                        // sea-level ISA, MTOW, EAS
    "tip_mach_hover": 0,                        // ISA+15
    "c_rate_hover": 0,                          // at the ceiling, end-of-life capacity
    "cost_usd": 0                               // acquisition cost per aircraft
  },

  "assumptions_for_checker": {}                 // optional overrides of DEFAULTS in check_design.py (only with a reason)
}
```

## `geometry.json` (keys the checker reads)

```jsonc
{
  "cg_mtow_m": [3.1, 0.0, 0.85],                 // CG at MTOW (needed for the rotor-out trim)
  "wing": {"span_m": 9.0, "root_chord_m": 1.25, "tip_chord_m": 0.85, ...},
  "lift_rotors": [                               // one entry per rotor
    {"id": "RP1", "hub": [0.0, -1.95, 1.55], "diameter_m": 1.8, "spin": 1},   // spin +1 = CCW seen from above
    ...
  ]
}
```

All other geometry content (spars, booms, stations, tail, gear, packs, seats) is defined by WP D for CFD/FEA/CAD;
the checker uses it only through the keys above.

## Output

`validation/methods/check_report.json` and `.md` (or `check_report_<tag>.*` with `--tag`): one row per comparison with
M value, D value, relative difference, tolerance, equation tag (methods/EQUATIONS.md) and PASS / WARN / FAIL; plus the
recomputed drag build-up, component masses, energy split and all assumptions. Exit code 1 if any FAIL.
