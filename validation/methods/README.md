# WP M verification and validation evidence

| File | What it shows |
|---|---|
| [nasa_lpc_reproduction.md](nasa_lpc_reproduction.md) | Validation of the WP M equations against the published NASA Lift+Cruise (electric) concept vehicle: hover power, C-rates and battery energy within ±5 %, propulsion mass +12 to +22 %, mission energy -3 % (with the stated reserve reading). Generated table: [nasa_lpc_reproduction_table.md](nasa_lpc_reproduction_table.md), data `nasa_lpc_reproduction.json`. |
| [check_report_example_750kg.md](check_report_example_750kg.md) | Checker test on the hand-built 750 kg / 200 kg payload input (`methods/examples/`). Exercises every comparison; the input imitates an optimistic sizing tool and is caught: range 55 km instead of the claimed 101 km (end-of-life and reserve not applied), empty mass +49 %, drag area +63 %. |
| `check_report.md` / `.json` | Written by `methods/check_design.py` when `design/selected_design.json` exists (WP D). Not yet produced: the design file did not exist at the time of writing. |

Run:

```bash
~/tools/cadenv/bin/python methods/check_design.py                      # design/selected_design.json (+ geometry.json)
~/tools/cadenv/bin/python methods/check_design.py methods/examples/example_750kg_selected_design.json \
      --geometry methods/examples/example_750kg_geometry.json --tag example_750kg
~/tools/cadenv/bin/python methods/nasa_lpc_reproduction.py
```

Equations, tolerances and open items: [methods/EQUATIONS.md](../../methods/EQUATIONS.md). Input schema for WP D:
[methods/design_schema.md](../../methods/design_schema.md).
