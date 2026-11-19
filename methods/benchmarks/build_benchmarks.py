#!/usr/bin/env python3
"""Benchmark aircraft data for E8-200 (work package M): writes benchmarks.csv (one source per value),
benchmarks_wide.csv (one row per aircraft, derived ratios) and the trend plots in plots/.

    ~/tools/cadenv/bin/python methods/benchmarks/build_benchmarks.py

Data quality codes (column `quality`):
  claim      manufacturer specification, press release or web page (not independently measured)
  document   manufacturer technical document (flight manual, spec sheet) - calculated or flight-test based
  certified  value fixed by a type certificate / approved limitation
  study      published engineering design study (e.g. NASA NDARC concept vehicle)
  secondary  encyclopaedia or trade-press database repeating manufacturer figures
  derived    computed here from other listed values (formula in `note`)
Values with no published source are left out rather than estimated.  Sources checked 2026-11-12/13.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LB, FT, HP = 0.45359237, 0.3048, 0.745699872

U = dict(
    jetson="https://jetson.com/jetson-one",
    jetson_wp="https://en.wikipedia.org/wiki/Jetson_One",
    blackfly_wp="https://en.wikipedia.org/wiki/Opener_BlackFly",
    helix="https://evtol.news/pivotal-helix-production-model",
    v2x_wp="https://en.wikipedia.org/wiki/Volocopter_2X",
    volocity="https://key4biz.it/wp-content/uploads/2021/10/20190819_VoloCity_Specs.pdf",
    ehang_fi="https://flightplan.forecastinternational.com/2024/05/02/uam-snapshot-ehang-eh216-s/",
    ehang_bd="https://www.batterydesign.net/ehang-eh216-s-evtol-battery/",
    cora="https://evtol.news/kitty-hawk-cora",
    heaviside="https://www.wingsofhistory.org/wp-content/uploads/2025/11/Heaviside-2.2-Aircraft-Flight-Manual_Rev-IR_09-21-21.pdf",
    cityairbus="https://evtol.news/airbus-helicopters-cityairbus-nextgen-technology-demonstrator",
    alia_wp="https://en.wikipedia.org/wiki/Beta_Technologies_Alia",
    joby="https://evtol.news/joby-aviation-s4-production-prototype",
    archer_avweb="https://www.avweb.com/aviation-news/archers-midnight-evtol-completes-first-transition-flight/",
    archer_vm="https://verticalmag.com/news/archer-unveils-midnight-first-production-evtol/",
    archer_ain="https://backend.ainonline.com/news-article/2022-11-17/archer-aviation-reveals-full-sized-midnight-evtol-air-taxi",
    archer_wp="https://en.wikipedia.org/wiki/Archer_Midnight",
    vx4="https://evtol.news/vertical-aerospace-va-1x",
    hexa="https://www.evtol.news/lift-hexa",
    hexa_navair="https://www.navair.navy.mil/osbp/node/10826",
    vahana_wp="https://en.wikipedia.org/wiki/Airbus_A%C2%B3_Vahana",
    velis_wp="https://en.wikipedia.org/wiki/Pipistrel_Velis_Electro",
    nasa18="https://www.nasa.gov/wp-content/uploads/2026/03/silva2018.pdf",
    nasa22="https://ntrs.nasa.gov/api/citations/20210026170/downloads/1521_Johnson%20%26%20Silva_122721%20.pdf",
)

AIRCRAFT = {
    # name: (configuration, seats, status)
    "Jetson One": ("multicopter (4 coaxial pairs)", 1, "production, ultralight"),
    "Opener/Pivotal BlackFly": ("tandem tilt-wing, 8 rotors", 1, "production, ultralight"),
    "Pivotal Helix": ("tandem tilt-wing, 8 rotors", 1, "production, ultralight"),
    "Volocopter 2X": ("multicopter, 18 rotors", 2, "prototype"),
    "Volocopter VoloCity": ("multicopter, 18 rotors", 2, "certification programme"),
    "EHang EH216-S": ("multicopter (8 coaxial pairs)", 2, "type certified (CAAC)"),
    "Wisk Cora (Gen 5)": ("lift + cruise, 12 lift + 1 pusher", 2, "prototype"),
    "Kitty Hawk Heaviside 2 Block 2": ("tilt-rotor, 8 rotors (6 wing, 2 canard)", 1, "prototype (programme ended)"),
    "CityAirbus NextGen": ("lift + cruise-like, 8 propellers incl. 2 pushers", 4, "demonstrator"),
    "Beta Alia A250": ("lift + cruise, 4 lift + 1 pusher", 6, "prototype"),
    "Joby S4": ("tilt-rotor, 6 propellers", 5, "certification programme"),
    "Archer Midnight": ("tilt + lift, 6 tilting + 6 lift", 5, "certification programme"),
    "Vertical VX4": ("tilt + lift, 8 propellers", 5, "prototype"),
    "LIFT Hexa": ("multicopter, 18 rotors", 1, "production, ultralight"),
    "Airbus Vahana Alpha": ("tilt-wing, 8 rotors", 1, "demonstrator (ended)"),
    "Pipistrel Velis Electro": ("conventional take-off, 1 propeller", 2, "type certified (EASA)"),
    "NASA Lift+Cruise E (2018)": ("lift + cruise, 8 lift + 1 pusher", 6, "design study (NDARC)"),
    "NASA Lift+Cruise E (2022)": ("lift + cruise, 8 lift + 1 pusher", 6, "design study (NDARC)"),
}

R = []  # (aircraft, parameter, value, unit, quality, source, note)


def add(ac, par, val, unit, q, src, note=""):
    R.append(dict(aircraft=ac, parameter=par, value=val, unit=unit, quality=q, source_url=src, note=note))


# --- Jetson One
add("Jetson One", "empty_mass_incl_battery", 115, "kg", "claim", U["jetson"], "'mass including batteries'; empty mass without batteries 55 kg")
add("Jetson One", "payload", 95, "kg", "claim", U["jetson"], "maximum pilot weight")
add("Jetson One", "endurance", 20, "min", "claim", U["jetson"], "approx.")
add("Jetson One", "max_speed", 102, "km/h", "claim", U["jetson"], "software-limited")
add("Jetson One", "lift_rotors", 8, "-", "claim", U["jetson"])
add("Jetson One", "installed_power", round(102 * HP, 1), "kW", "secondary", U["jetson_wp"], "102 hp total")
# --- BlackFly
for p, v, u in (("empty_mass_incl_battery", 142, "kg"), ("mtow", 255, "kg"), ("payload", 113, "kg"), ("battery_energy", 12, "kWh"),
                ("range", 64, "km"), ("cruise_speed", 130, "km/h"), ("lift_rotors", 8, "-"), ("rotor_diameter", 0.91, "m"),
                ("installed_power", 8 * 31.3, "kW"), ("span", 4.14, "m")):
    add("Opener/Pivotal BlackFly", p, v, u, "secondary", U["blackfly_wp"],
        "BlackFly International (non-US) figures; range 'plus reserves'" if p in ("range", "cruise_speed") else
        ("8 x 31.3 kW (42 hp) per motor" if p == "installed_power" else ""))
# --- Helix
for p, v, u in (("empty_mass_incl_battery", 158, "kg"), ("mtow", 258, "kg"), ("payload", 100, "kg"), ("battery_energy", 8, "kWh"),
                ("range", 32, "km"), ("cruise_speed", 101, "km/h"), ("lift_rotors", 8, "-")):
    add("Pivotal Helix", p, v, u, "claim", U["helix"], "range '20+ miles'" if p == "range" else "")
# --- Volocopter 2X
for p, v, u in (("empty_mass_incl_battery", 290, "kg"), ("mtow", 450, "kg"), ("payload", 160, "kg"), ("range", 27, "km"),
                ("cruise_speed", 70, "km/h"), ("endurance", 27, "min"), ("max_speed", 100, "km/h"), ("lift_rotors", 18, "-"),
                ("rotor_diameter", 1.80, "m")):
    add("Volocopter 2X", p, v, u, "secondary", U["v2x_wp"], "range quoted at 70 km/h" if p in ("range", "cruise_speed") else "")
# --- VoloCity (2019 design specification)
for p, v, u in (("empty_mass_incl_battery", 700, "kg"), ("mtow", 900, "kg"), ("payload", 200, "kg"), ("range", 35, "km"),
                ("max_speed", 110, "km/h"), ("lift_rotors", 18, "-"), ("rotor_diameter", 2.3, "m")):
    add("Volocopter VoloCity", p, v, u, "document", U["volocity"], "Volocopter design specification Aug 2019: 'calculated approximations not yet tested in flight'")
# --- EHang EH216-S
add("EHang EH216-S", "mtow", 620, "kg", "claim", U["ehang_fi"])
add("EHang EH216-S", "payload", 220, "kg", "claim", U["ehang_fi"])
add("EHang EH216-S", "battery_energy", 17, "kWh", "secondary", U["ehang_bd"], "12 batteries")
add("EHang EH216-S", "range", 35, "km", "secondary", U["ehang_bd"], "21 min flight; Forecast International gives 30 km")
add("EHang EH216-S", "endurance", 21, "min", "secondary", U["ehang_bd"])
add("EHang EH216-S", "lift_rotors", 16, "-", "secondary", U["ehang_bd"])
add("EHang EH216-S", "empty_mass_incl_battery", 400, "kg", "derived", U["ehang_fi"], "MTOW - payload")
# --- Wisk Cora
for p, v, u in (("payload", 181, "kg"), ("range", 100, "km"), ("cruise_speed", 180, "km/h"), ("lift_rotors", 12, "-"), ("span", 11, "m")):
    add("Wisk Cora (Gen 5)", p, v, u, "claim", U["cora"], "MTOW and empty mass not published")
# --- Heaviside (flight manual)
for p, v, u, n in (("empty_mass_incl_battery", 310, "kg", "Heaviside 2 Block 2 with Puma controllers"), ("mtow", 400, "kg", "MGW"),
                   ("payload", 80, "kg", ""), ("battery_energy", 18, "kWh", "four 528 V packs, ~39 Ah"),
                   ("range", 129, "km", "~80 miles at 96 kt, calculated; flight tests reported 100 miles + minimal reserve"),
                   ("cruise_speed", 178, "km/h", "96 kt (range speed)"), ("max_speed", 198, "km/h", "VH 107 KTAS"),
                   ("stall_speed", 111, "km/h", "~60 kt wing stall"), ("lift_rotors", 8, "-", "tilting"),
                   ("installed_power", 8 * 28, "kW", "8 x 28 kW PMSM, 60 N m, 5000 rpm"), ("span", 6.5, "m", "~23 ft"),
                   ("limit_load_factor", 4.4, "g", "+4.4 / -2.4")):
    add("Kitty Hawk Heaviside 2 Block 2", p, v, u, "document", U["heaviside"], n)
# --- CityAirbus NextGen
for p, v, u in (("empty_mass_incl_battery", 2000, "kg"), ("range", 80, "km"), ("cruise_speed", 120, "km/h"), ("lift_rotors", 8, "-"),
                ("span", 12, "m")):
    add("CityAirbus NextGen", p, v, u, "claim", U["cityairbus"], "page states all specifications are estimates")
# --- Beta Alia A250
add("Beta Alia A250", "mtow", 2720, "kg", "secondary", U["alia_wp"], "6,000 lb aircraft weight (not labelled MTOW)")
add("Beta Alia A250", "range", 463, "km", "secondary", U["alia_wp"], "planned maximum 250 nmi")
add("Beta Alia A250", "cruise_speed", 270, "km/h", "secondary", U["alia_wp"])
add("Beta Alia A250", "lift_rotors", 4, "-", "secondary", U["alia_wp"])
add("Beta Alia A250", "span", 15, "m", "secondary", U["alia_wp"])
# --- Joby S4
for p, v, u, n in (("mtow", 2404, "kg", "approx. 5,300 lb"), ("empty_mass_incl_battery", 1950, "kg", "approx. 4,300 lb"),
                   ("payload", 453, "kg", ""), ("range", 161, "km", "100 miles incl. energy reserves"),
                   ("cruise_speed", 322, "km/h", "maximum cruise"), ("lift_rotors", 6, "-", "tilting"),
                   ("installed_power", 6 * 236, "kW", "6 x 236 kW peak"), ("pack_specific_energy", 235, "Wh/kg", "cell 288 Wh/kg")):
    add("Joby S4", p, v, u, "claim", U["joby"], n)
# --- Archer Midnight
add("Archer Midnight", "mtow", round(6500 * LB), "kg", "claim", U["archer_avweb"], "design MTOW 6,500 lb")
add("Archer Midnight", "payload", 454, "kg", "claim", U["archer_vm"], "> 1,000 lb expected")
add("Archer Midnight", "max_speed", 241, "km/h", "claim", U["archer_vm"])
add("Archer Midnight", "lift_rotors", 12, "-", "claim", U["archer_vm"], "6 tilting + 6 lift-only")
add("Archer Midnight", "range", 161, "km", "secondary", U["archer_wp"])
add("Archer Midnight", "span", round(47 * FT, 1), "m", "secondary", U["archer_ain"], "47 ft")
# --- Vertical VX4
for p, v, u in (("payload", 450, "kg"), ("range", 161, "km"), ("cruise_speed", 241, "km/h"), ("lift_rotors", 8, "-"), ("span", 15, "m")):
    add("Vertical VX4", p, v, u, "secondary", U["vx4"])
# --- LIFT Hexa
add("LIFT Hexa", "empty_mass_incl_battery", 196, "kg", "claim", U["hexa"], "432 lb")
add("LIFT Hexa", "payload", 113, "kg", "claim", U["hexa"], "250 lb; company page elsewhere 220 lb")
add("LIFT Hexa", "battery_mass", round(133 * LB, 1), "kg", "secondary", U["hexa_navair"], "133 lb of batteries included in empty weight")
add("LIFT Hexa", "endurance", 15, "min", "claim", U["hexa"], "plus reserve")
add("LIFT Hexa", "cruise_speed", 72, "km/h", "claim", U["hexa"])
add("LIFT Hexa", "lift_rotors", 18, "-", "claim", U["hexa"])
add("LIFT Hexa", "mtow", 196 + 113, "kg", "derived", U["hexa"], "empty + payload")
# --- Vahana
for p, v, u, n in (("empty_mass_incl_battery", 695, "kg", ""), ("mtow", 815, "kg", ""), ("payload", 90, "kg", "Alpha One; Alpha Two 200 kg"),
                   ("range", 50, "km", ""), ("cruise_speed", 200, "km/h", ""), ("rotor_diameter", 1.5, "m", ""),
                   ("span", 6.25, "m", "")):
    add("Airbus Vahana Alpha", p, v, u, "secondary", U["vahana_wp"], n)
# --- Velis Electro
for p, v, u, q, n in (("empty_mass_incl_battery", 428, "kg", "secondary", ""), ("mtow", 600, "kg", "certified", "EASA TC (CS-LSA based)"),
                      ("payload", 172, "kg", "secondary", "useful load"), ("battery_energy", 24.8, "kWh", "secondary", ""),
                      ("battery_mass", 140, "kg", "secondary", "two 70 kg packs"), ("endurance", 50, "min", "secondary", "plus VFR reserve"),
                      ("cruise_speed", 170, "km/h", "secondary", ""), ("stall_speed", 83, "km/h", "secondary", "flaps down"),
                      ("span", 10.71, "m", "secondary", ""), ("wing_area", 9.51, "m2", "secondary", ""),
                      ("installed_power", 57.6, "kW", "secondary", "take-off rating 90 s; 49.2 kW continuous")):
    add("Pipistrel Velis Electro", p, v, u, q, U["velis_wp"], n)
# --- ranges derived from endurance x cruise speed (no reserve correction)
add("Pipistrel Velis Electro", "range", round(50 / 60 * 170), "km", "derived", U["velis_wp"], "endurance 50 min x cruise 170 km/h")
add("LIFT Hexa", "range", round(15 / 60 * 72), "km", "derived", U["hexa"], "endurance 15 min x cruise 72 km/h")
# --- NASA Lift+Cruise electric (2018), Table 3 of AIAA 2018-3847
nasa = (("mtow", round(8210 * LB), "kg", "DGW 8,210 lb"), ("empty_mass_incl_battery", round(7001 * LB), "kg", "7,001 lb"),
        ("payload", round(1200 * LB), "kg", "1,200 lb, 6 occupants"), ("battery_mass", round(1693 * LB), "kg", "1,693 lb"),
        ("battery_energy", round(1436 / 3.6), "kWh", "1,436 MJ capacity"), ("range", 139, "km", "75 nm design mission + 20 min reserve"),
        ("cruise_speed", round(112 * 1.852), "km/h", "Vbr 112 kt"), ("lift_rotors", 8, "-", ""), ("rotor_diameter", round(10 * FT, 3), "m", "R = 5 ft"),
        ("disk_loading", round(13.1 * 47.880, 1), "N/m2", "13.1 lb/ft2"), ("installed_power_lift", round(8 * 139 * HP, 1), "kW", "8 x 139 hp MRP"),
        ("installed_power", round((8 * 139 + 628) * HP, 1), "kW", "8 x 139 hp + 628 hp cruise"), ("hover_FM", 0.74, "-", "aircraft FM"),
        ("tip_speed", round(585 * FT, 1), "m/s", "585 ft/s"), ("L_De", 8.5, "-", "W V / P"), ("drag_area", round(16.9 * FT**2, 3), "m2", "D/q 16.9 ft2"),
        ("pack_specific_energy", 400, "Wh/kg", "sec. VI A, usable at pack level"), ("c_rate_hover", 2.4, "1/h", ""))
for p, v, u, n in nasa:
    add("NASA Lift+Cruise E (2018)", p, v, u, "study", U["nasa18"], n)
for p, v, u, n in (("mtow", round(9482 * LB), "kg", "DGW 9,482 lb"), ("empty_mass_incl_battery", round(8274 * LB), "kg", ""),
                   ("payload", round(1200 * LB), "kg", ""), ("battery_mass", round(2058 * LB), "kg", ""), ("range", 139, "km", "75 nm"),
                   ("cruise_speed", round(83 * 1.852), "km/h", "Vbr 83 kt"), ("lift_rotors", 8, "-", ""),
                   ("rotor_diameter", round(10 * FT, 3), "m", ""), ("disk_loading", round(15.1 * 47.880, 1), "N/m2", "15.1 lb/ft2"),
                   ("installed_power_lift", round(8 * 189 * HP, 1), "kW", "8 x 189 hp"), ("installed_power", round((8 * 189 + 838) * HP, 1), "kW", ""),
                   ("tip_speed", round(550 * FT, 1), "m/s", ""), ("L_De", 7.9, "-", "")):
    add("NASA Lift+Cruise E (2022)", p, v, u, "study", U["nasa22"], n)


def wide():
    rows = []
    for ac, (cfg, seats, status) in AIRCRAFT.items():
        vals = {r["parameter"]: r for r in R if r["aircraft"] == ac}
        g = lambda k: vals[k]["value"] if k in vals else None
        row = dict(aircraft=ac, configuration=cfg, seats=seats, status=status)
        for k in ("mtow", "empty_mass_incl_battery", "payload", "battery_mass", "battery_energy", "range", "cruise_speed",
                  "lift_rotors", "rotor_diameter", "installed_power", "installed_power_lift", "span"):
            row[k] = g(k)
        m = g("mtow")
        if m is None and g("empty_mass_incl_battery") and g("payload"):
            m = g("empty_mass_incl_battery") + g("payload")
            row["mtow_note"] = "derived: empty + payload"
        row["mtow_used"] = m
        q = sorted({v["quality"] for v in vals.values()})
        row["quality_set"] = "+".join(q)
        row["quality_class"] = ("study" if "study" in q else "document/certified" if ("document" in q or "certified" in q) else "claim/secondary")
        if m:
            if g("empty_mass_incl_battery"):
                row["empty_fraction"] = g("empty_mass_incl_battery") / m
            if g("payload"):
                row["payload_fraction"] = g("payload") / m
            if g("battery_mass"):
                row["battery_mass_fraction"] = g("battery_mass") / m
            if g("battery_energy"):
                row["battery_Wh_per_kg_MTOW"] = g("battery_energy") * 1000 / m
            if g("rotor_diameter") and g("lift_rotors"):
                n = g("lift_rotors")
                n_disc = n // 2 if "coaxial" in cfg else n
                A = n_disc * math.pi * g("rotor_diameter") ** 2 / 4
                row["disk_loading_N_m2"] = m * 9.80665 / A
            P = g("installed_power_lift") or (g("installed_power") if "multicopter" in cfg or "tilt" in cfg else None)
            if P:
                row["power_loading_N_per_kW"] = m * 9.80665 / P
                row["power_basis"] = "lift power" if g("installed_power_lift") else "total installed power"
        rows.append(row)
    return rows


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    with open(HERE / "benchmarks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["aircraft", "parameter", "value", "unit", "quality", "source_url", "note"])
        w.writeheader()
        w.writerows(R)
    rows = wide()
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(HERE / "benchmarks_wide.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    # regression of empty fraction (incl. battery) against MTOW, all data with a measured/claimed MTOW
    pts = [(r["mtow_used"], r["empty_fraction"]) for r in rows if r.get("empty_fraction") and r.get("mtow")]
    x, y = np.array(pts).T
    b1, b0 = np.polyfit(np.log(x), np.log(y), 1)
    fits = dict(empty_fraction_vs_mtow=dict(form="We/W0 = A * W0^C (W0 in kg)", A=float(math.exp(b0)), C=float(b1), n=len(x),
                                            note="all configurations; empty mass includes battery"))
    (HERE / "trend_fits.json").write_text(json.dumps(fits, indent=1))

    PLOT = HERE / "plots"
    PLOT.mkdir(exist_ok=True)
    styles = {"claim/secondary": ("#2a78d6", "o", "manufacturer claim / secondary"),
              "document/certified": ("#eb6834", "s", "manufacturer document / certified"),
              "study": ("#1baf7a", "^", "design study (NASA NDARC)")}

    def scatter(ax, xs, ys, labels, cls):
        for c, (col, mk, lab) in styles.items():
            sel = [i for i in range(len(xs)) if cls[i] == c]
            ax.scatter([xs[i] for i in sel], [ys[i] for i in sel], s=46, c=col, marker=mk, edgecolors="white", linewidths=1.5,
                       label=lab, zorder=3)
        for xi, yi, l in zip(xs, ys, labels):
            ax.annotate(l, (xi, yi), xytext=(4, 3), textcoords="offset points", fontsize=6.5, color="#52514e")
        ax.grid(alpha=0.25, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)

    def short(n):
        return (n.replace("Kitty Hawk ", "").replace(" 2 Block 2", "").replace("Opener/Pivotal ", "").replace("Volocopter ", "")
                .replace("Pipistrel ", "").replace("Airbus ", "").replace(" Alpha", "").replace("NASA Lift+Cruise", "NASA L+C"))

    # 1 empty fraction vs MTOW
    sel = [r for r in rows if r.get("empty_fraction")]
    fig, ax = plt.subplots(figsize=(7, 4.4), dpi=150)
    scatter(ax, [r["mtow_used"] for r in sel], [r["empty_fraction"] for r in sel], [short(r["aircraft"]) for r in sel],
            [r["quality_class"] for r in sel])
    xx = np.linspace(200, 4000, 100)
    ax.plot(xx, fits["empty_fraction_vs_mtow"]["A"] * xx ** fits["empty_fraction_vs_mtow"]["C"], color="#898781", lw=1.2, ls="--",
            label=f"fit: {fits['empty_fraction_vs_mtow']['A']:.2f} W0^{fits['empty_fraction_vs_mtow']['C']:.3f}")
    ax.axhline(1 - 200 / 1000, color="#c3c2b7", lw=1)
    ax.text(3000, 0.805, "200 kg payload at 1000 kg", fontsize=7, color="#52514e")
    ax.set_xscale("log")
    ax.set_xlabel("MTOW (kg)")
    ax.set_ylabel("Empty-mass fraction incl. battery")
    ax.set_title("Empty-mass fraction vs MTOW", fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(PLOT / "empty_fraction_vs_mtow.png")
    plt.close(fig)

    # 2 disk loading vs hover power loading, with momentum-theory lines
    sel = [r for r in rows if r.get("disk_loading_N_m2") and r.get("power_loading_N_per_kW")]
    fig, ax = plt.subplots(figsize=(7, 4.4), dpi=150)
    scatter(ax, [r["disk_loading_N_m2"] for r in sel], [r["power_loading_N_per_kW"] for r in sel],
            [short(r["aircraft"]) + (" (total P)" if r["power_basis"] != "lift power" else "") for r in sel], [r["quality_class"] for r in sel])
    DL = np.linspace(50, 1000, 200)
    for fm, ls in ((0.6, ":"), (0.75, "--")):
        ax.plot(DL, 1000 * fm * np.sqrt(2 * 1.225 / DL), color="#898781", lw=1.1, ls=ls, label=f"momentum theory, FM {fm}, sea level")
    ax.set_xlabel("Disk loading W/A (N/m$^2$)")
    ax.set_ylabel("Power loading W/P (N/kW)")
    ax.set_title("Disk loading vs power loading (installed power: a lower bound on hover power loading)", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(PLOT / "disk_loading_vs_power_loading.png")
    plt.close(fig)

    # 3 battery fraction vs range (mass fraction where known, else installed Wh per kg MTOW / 180 Wh/kg)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    sel = [r for r in rows if r.get("battery_mass_fraction") and r.get("range")]
    scatter(axs[0], [r["range"] for r in sel], [r["battery_mass_fraction"] for r in sel], [short(r["aircraft"]) for r in sel],
            [r["quality_class"] for r in sel])
    axs[0].set_xlabel("Range (km, as published)")
    axs[0].set_ylabel("Battery mass / MTOW")
    axs[0].set_title("Battery mass fraction (published masses)", fontsize=9)
    sel = [r for r in rows if r.get("battery_Wh_per_kg_MTOW") and r.get("range")]
    scatter(axs[1], [r["range"] for r in sel], [r["battery_Wh_per_kg_MTOW"] for r in sel], [short(r["aircraft"]) for r in sel],
            [r["quality_class"] for r in sel])
    axs[1].set_xlabel("Range (km, as published)")
    axs[1].set_ylabel("Installed battery energy per MTOW (Wh/kg)")
    axs[1].set_title("Battery energy per unit MTOW", fontsize=9)
    try:
        est = json.loads((HERE.parent / "initial_estimate.json").read_text())
        pts = [(c["range_km"], c["battery_kwh"] * 1000 / c["mtow_kg"]) for c in est["cases"] + est.get("variant_cases", [])
               if c.get("feasible") and c["n_rot"] == 8 and not c["coax"]]
        if pts:
            axs[1].scatter(*zip(*pts), s=46, facecolors="none", edgecolors="#0b0b0b", marker="D", lw=1.2, zorder=4,
                           label="E8-200 first-order closures (this study)")
            axs[1].legend(frameon=False, fontsize=7, loc="upper left")
    except FileNotFoundError:
        pass
    for ax in axs:
        ax.set_ylim(bottom=0)
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(PLOT / "battery_fraction_vs_range.png")
    plt.close(fig)

    # 4 payload fraction vs MTOW and range
    sel = [r for r in rows if r.get("payload_fraction")]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    scatter(axs[0], [r["mtow_used"] for r in sel], [r["payload_fraction"] for r in sel], [short(r["aircraft"]) for r in sel],
            [r["quality_class"] for r in sel])
    axs[0].set_xscale("log")
    axs[0].set_xlabel("MTOW (kg)")
    axs[0].set_ylabel("Payload / MTOW")
    axs[0].set_title("Payload fraction vs MTOW", fontsize=9)
    sel2 = [r for r in sel if r.get("range")]
    scatter(axs[1], [r["range"] for r in sel2], [r["payload_fraction"] for r in sel2], [short(r["aircraft"]) for r in sel2],
            [r["quality_class"] for r in sel2])
    axs[1].set_xlabel("Range (km, as published)")
    axs[1].set_ylabel("Payload / MTOW")
    axs[1].set_title("Payload fraction vs range", fontsize=9)
    for ax in axs:
        ax.axhline(0.2, color="#c3c2b7", lw=1)
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(PLOT / "payload_fraction.png")
    plt.close(fig)
    print(f"{len(R)} values, {len(rows)} aircraft; fit {fits}")
    for r in rows:
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in
               ("aircraft", "mtow_used", "empty_fraction", "payload_fraction", "battery_mass_fraction", "battery_Wh_per_kg_MTOW",
                "disk_loading_N_m2", "power_loading_N_per_kW")})


if __name__ == "__main__":
    main()
