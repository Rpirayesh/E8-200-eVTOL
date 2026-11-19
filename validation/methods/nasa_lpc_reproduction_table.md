# Reproduction of the NASA Lift+Cruise (electric) concept vehicle

Script: `methods/nasa_lpc_reproduction.py` (uses the functions of `methods/check_design.py`).

Published values: [S18] Silva et al., AIAA 2018-3847, Table 1, Table 3 (L+C E), sec. VI (https://www.nasa.gov/wp-content/uploads/2026/03/silva2018.pdf); [JS22] Johnson & Silva, Aeronautical Journal 2022, Table 3 (https://ntrs.nasa.gov/api/citations/20210026170/downloads/1521_Johnson%20%26%20Silva_122721%20.pdf).

| quantity | M (this check) | NASA | diff | unit | source | note |
|---|---|---|---|---|---|---|
| lift-rotor disk loading | 13.07 | 13.1 | -0.3% | lb/ft^2 | [S18] T3 | DGW / (8 pi R^2) |
| hover shaft power per lifter, 6000 ft ISA, FM = 0.74 (published) | 144.6 | 139 | +4.0% | hp | [S18] T3 MRP per lifter | M uses [H1] + published FM; NASA MRP is the installed rating |
| aircraft hover figure of merit (M blade-element [H2]) | 0.6822 | 0.74 | -7.8% | - | [S18] T3 |  |
| hover shaft power per lifter with M's FM | 156.8 | 139 | +12.8% | hp | [S18] T3 |  |
| battery mass from published capacity at 530 Wh/kg cell-usable (sec. VI A) | 1659 | 1693 | -2.0% | lb | [S18] T3 + sec. VI A | 1436 MJ / 530 Wh/kg; check of NASA's capacity bookkeeping |
| usable energy at 400 Wh/kg pack x battery mass | 1106 | 1113 | -0.6% | MJ | [S18] T3 + sec. VI A | battery is sized by the design mission: usable = energy burn |
| hover C-rate = P_hover,elec / capacity | 2.446 | 2.4 | +1.9% | 1/h | [S18] T3 | M drive efficiency 0.884 |
| cruise C-rate = (W V / (L/De)) / eta_drive / capacity | 0.702 | 0.7 | +0.3% | 1/h | [S18] T3 |  |
| propulsion group excl. battery (8 lift + 1 cruise motor, eq. 1 x 1.63) | 1678 | 1493 | +12.4% | lb | [S18] T3 + eq. 1 | cruise motor at 2000-2500 rpm: 306-371 lb |
| rotor group (8 lift rotors, AFDD00, no tech factor) | 383.2 | 948 | -59.6% | lb | [S18] T3 | NASA's rotor group also contains the pusher, spinners and rotor supports (not separately published) |
| design-mission energy, reading A: 2 x 37.5 nm + 20 min reserve | 1415 | 1113 | +27.1% | MJ | [S18] T1, T3 | M hover with published FM, cruise from published L/De at Vbr, 10 kt headwind |
| design-mission energy, reading B: 2 x 37.5 nm, reserve not in 'energy burn' | 1079 | 1113 | -3.1% | MJ | [S18] T1, T3 | same segments without segment 10 |
| design-mission energy, reading C: 1 x 37.5 nm + 20 min reserve (Table 1 as listed) | 875.4 | 1113 | -21.3% | MJ | [S18] T1, T3 |  |
| empty-weight fraction incl. battery | 0.8527 | 0.8527 | +0.0% | - | [S18] T3 | identity check |
| [2022] lift-rotor disk loading | 15.09 | 15.1 | -0.1% | lb/ft^2 | [JS22] T3 |  |
| [2022] hover shaft power per lifter, 6000 ft ISA, FM 0.74 | 179.5 | 189 | -5.0% | hp | [JS22] T3 | published power is the installed rating |
| [2022] propulsion group (8 lift + 1 cruise motor, eq. 1 x 1.63) | 2268 | 1866 | +21.5% | lb | [JS22] T3 | 2022 table lists battery separately |

## Cruise drag: span back-out

The wing span of the NASA vehicle is not published in [S18]/[JS22]. With the published D/q = 16.9 ft^2 (1.570 m^2), DGW, Vbr = 112 kt at 10,000 ft ISA (q = 1502 Pa), an assumed propeller efficiency 0.85 and Oswald factor 0.8, the published L/De = 8.5 implies a total drag of 3652 N, of which 2358 N is parasite; the remaining induced drag 1294 N corresponds to a span of 16.5 m. This is offered as a consistency check, not a reproduction.

## Mission energy split (M)

Per flight 149.8 kWh (climb 263 s); reserve 93.3 kWh; total 393.0 kWh = 1415 MJ.
