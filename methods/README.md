# WP M - equations, benchmark data, independent design checks

| File | Content |
|---|---|
| [EQUATIONS.md](EQUATIONS.md) | Conceptual-design equation set with tags, units, validity and references; checker tolerances; open items |
| [design_schema.md](design_schema.md) | Input schema of `design/selected_design.json` / `geometry.json` as read by the checker (for WP D) |
| [check_design.py](check_design.py) | Independent checker (numpy; scipy optional). Writes `validation/methods/check_report*.json/.md` |
| [examples/](examples/) | Hand-built 750 kg test input (design + geometry) |
| [nasa_lpc_reproduction.py](nasa_lpc_reproduction.py) | Reproduction of the NASA Lift+Cruise vehicle -> `validation/methods/nasa_lpc_reproduction*` |
| [initial_estimate.md](initial_estimate.md) / [.py](initial_estimate.py) | First-order design space for 200 kg payload: MTOW, battery, power, cost vs range and rotor count |
| [benchmarks/](benchmarks/README.md) | 18 benchmark aircraft, 150 sourced values, trend plots |

All scripts run with `~/tools/cadenv/bin/python` from the project root or from `methods/`.
