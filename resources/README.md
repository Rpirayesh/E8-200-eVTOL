# E8-200 reference library

Curated literature, regulations, datasheets and tool documentation for the E8-200 crewed lift + cruise eVTOL (200 kg payload, fixed lift rotors on two booms, high wing, rear pusher, low-cost in-house construction).

Links were checked on 2026-11-12. Machine-readable versions: [`sources.json`](sources.json) (all sources, with quoted key data) and [`benchmarks_raw.json`](benchmarks_raw.json) (benchmark aircraft, one source per number).

## How to use this library

- **Source IDs** (SZ, BT, RA, AE, ST, MF, BM, TL) are stable; cite them in code comments and reports, e.g. `# SZ01 Table 3`.
- **Work packages:** R literature, M methods/benchmarks, P parts/manufacturing, D sizing/design, C CFD, F FEA, G CAD, V verification and validation.
- **Key data** are quoted from the source with page/table where known. Where a number could not be found it is not given; gaps are listed explicitly.
- **Local copies** in [`papers/`](papers/) are limited to US-government public-use documents (NASA NTRS items marked public use permitted, FAA ACs, CFR extracts), each under 10 MB. Everything else is linked only.
- **Credibility** notes are our assessment: regulator and NASA documents and peer-reviewed papers rank highest; manufacturer claims are taken as claims; directory and trade-press numbers are flagged.
- Several publisher sites (AIAA, Elsevier, MDPI, PNAS, ASTM, Cambridge) refuse automated link checks; their DOIs were verified through Crossref and resolve in a browser.

## Contents

- [1. eVTOL conceptual sizing and design methods](#1-evtol-conceptual-sizing-and-design-methods) (15 sources)
- [2. Batteries: cells, pack overhead, safety requirements](#2-batteries-cells-pack-overhead-safety-requirements) (12 sources)
- [3. Rotor aerodynamics and interference](#3-rotor-aerodynamics-and-interference) (14 sources)
- [4. Wing / aircraft aerodynamics and CFD validation](#4-wing--aircraft-aerodynamics-and-cfd-validation) (10 sources)
- [5. Regulations, structures, loads, crashworthiness, recovery](#5-regulations-structures-loads-crashworthiness-recovery) (18 sources)
- [6. Materials and manufacturing](#6-materials-and-manufacturing) (10 sources)
- [7. Benchmark aircraft data sources](#7-benchmark-aircraft-data-sources) (8 sources)
- [8. Open-source tools](#8-open-source-tools) (13 sources)
- [Benchmark aircraft summary](#benchmark-aircraft-summary)
- [Known gaps and open items](#known-gaps-and-open-items)

## 1. eVTOL conceptual sizing and design methods

### SZ01 - VTOL Urban Air Mobility Concept Vehicles for Technology Development

- **Citation:** Silva, C.; Johnson, W.; Solis, E.; Patterson, M. D.; Antcliff, K. R. (2018). *VTOL Urban Air Mobility Concept Vehicles for Technology Development*. AIAA Aviation Technology, Integration, and Operations Conference, AIAA 2018-3847, doi:10.2514/6.2018-3847.
- **Link:** [https://ntrs.nasa.gov/citations/20180006683](https://ntrs.nasa.gov/citations/20180006683)
- **Local copy:** [`papers/NASA-20180006683_Silva2018_UAM_concept_vehicles.pdf`](papers/NASA-20180006683_Silva2018_UAM_concept_vehicles.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP M, D, V.
- **What it is:** Defines the NASA RVLT UAM reference vehicles (quadrotor, side-by-side, lift+cruise) sized in NDARC to a common 6-passenger (1,200 lb payload) mission. The lift+cruise has 8 RPM-controlled fixed-pitch lift rotors on booms, a high wing and one pusher; the paper gives a complete weight/power/drag breakdown and the battery, motor and accessory technology factors.
- **How we use it:** WP M/D: closest published reference for our configuration; use Table 3 as a scaling and sanity check of weight fractions, disk loading, D/q, L/De and hover C-rate; use the battery derating chain (cell -> usable -> installed) and motor accessory factor in the sizing code. WP V: benchmark for the sizing model.
- **Key data:**
  - Battery: cell 650 Wh/kg -> minus 20% (5% top + 15% bottom of charge) = 530 Wh/kg usable -> 30% weight for BMS/pack structure -> 400 Wh/kg installed (p.10, Sec. VI.A)
  - Motor weight W = 0.3928 Q^0.8587 (NDARC empirical relation; units as defined in the NDARC manual, SZ05), accessory (inverter, cooling, wiring) factor 1.63 x motor weight (p.11, Eq. 1)
  - Electric lift+cruise (Table 3): DGW 8,210 lb, empty 7,001 lb, payload 1,200 lb, 8 lifters, radius 5.0 ft, disk loading 13.1 lb/ft2, hover tip speed 585 ft/s, thrust-weighted solidity 0.267
  - Electric lift+cruise (Table 3): battery 1,436 MJ, 1,693 lb; MRP 139 hp per lifter; pusher 628 hp; D/q 16.9 ft2; L/De 8.5; aircraft hover FM 0.74; hover C-rate 2.4 /hr; cruise C-rate 0.7 /hr
  - Lift rotor diameter capped at 10 ft for RPM-control responsiveness (p.11); hover tip speed kept ~550-600 ft/s for noise (p.14)
  - Hover C-rate relation x_hover ~ sqrt(W/2rhoA) * eta_cruise (L/De) / (eta_hover FM Range) (Eq. 3, p.11)
  - Lift+cruise FM highest of the three types 'due to the very small download' (p.14)
- **Credibility:** High. NASA RVLT authors; NDARC-based conceptual design, not flight data. Technology level is 'advanced' (650 Wh/kg cell), so battery numbers must be re-based to today's cells.

### SZ02 - Concept Vehicles for VTOL Air Taxi Operations

- **Citation:** Johnson, W.; Silva, C.; Solis, E. (2018). *Concept Vehicles for VTOL Air Taxi Operations*. AHS Technical Conference on Aeromechanics Design for Transformative Vertical Flight, San Francisco, Jan. 2018.
- **Link:** [https://ntrs.nasa.gov/citations/20180003381](https://ntrs.nasa.gov/citations/20180003381)
- **Local copy:** [`papers/NASA-20180003381_Johnson2018_concept_vehicles_air_taxi.pdf`](papers/NASA-20180003381_Johnson2018_concept_vehicles_air_taxi.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP M, D.
- **What it is:** The original NASA air-taxi concept set, including a single-passenger (250 lb payload, 50 nm) electric quadrotor that is the closest NASA reference to our payload class. Gives the battery technology table used across NASA UAM work and weight-vs-range sensitivity.
- **How we use it:** WP M/D: battery technology levels and installation fractions; the 1-passenger electric quadrotor (DGW ~1,250 lb) is a direct mass-scale benchmark for a 200 kg payload aircraft and for the range sensitivity check (50/100/150 km).
- **Key data:**
  - Table 2 battery technology: uninstalled 240/300/325/487.5/650 Wh/kg; usable fraction 70/75/80/80/80%; installation fraction 0.8/0.5/0.3/0.3/0.3; installed 93/150/200/300/400 Wh/kg; max burst discharge 4/6/8/14/20 C; DoD max 0.80-0.85
  - Discharge currents must be limited to 2-3C for good battery life (p.4)
  - 1-pax electric quadrotor (Table 9): DGW 1,252 lb, WE 997 lb, battery 272 lb / 178 MJ, disk loading 2.5 lb/ft2, radius 6.31 ft, 4 x 21.6 hp, tip speed 450 ft/s, D/q 3.43 ft2, Vbr 86 kt
  - Doubling range to 100 nm increases DGW of the 1-pax electric quadrotor by 50%; no closure at 200 nm (p.8)
- **Credibility:** High (NASA). Conceptual design results; the 1-pax vehicle is a multicopter, not lift+cruise.

### SZ03 - Observations from Exploration of VTOL Urban Air Mobility Designs

- **Citation:** Johnson, W.; Silva, C. (2018). *Observations from Exploration of VTOL Urban Air Mobility Designs*. Asian/Australian Rotorcraft Forum, Jeju, Korea, Oct.-Nov. 2018.
- **Link:** [https://ntrs.nasa.gov/citations/20180007847](https://ntrs.nasa.gov/citations/20180007847)
- **Local copy:** [`papers/NASA-20180007847_Johnson2018_observations_UAM.pdf`](papers/NASA-20180007847_Johnson2018_observations_UAM.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP D, P.
- **What it is:** Summary of lessons from the NASA UAM concept vehicles: hover vs cruise efficiency, rotor-rotor interference, download, noise and a qualitative cost statement.
- **How we use it:** WP D: justification text for design choices (stopped lift rotors, rotor placement) and the cost-driver statement used in the objective function.
- **Key data:**
  - Purchase cost is roughly (20% accuracy) driven by empty weight, installed power and complexity plus electronics; for electric aircraft battery cost must be included explicitly (p.7)
- **Credibility:** High (NASA), qualitative overview.

### SZ04 - NASA concept vehicles and the engineering of advanced air mobility aircraft

- **Citation:** Johnson, W.; Silva, C. (2022). *NASA concept vehicles and the engineering of advanced air mobility aircraft*. The Aeronautical Journal 126(1295), 59-91, doi:10.1017/aer.2021.92.
- **Link:** [https://ntrs.nasa.gov/citations/20210026170](https://ntrs.nasa.gov/citations/20210026170)
- **Type:** paper (peer-reviewed). **Used by:** WP M, D.
- **What it is:** Journal review of all NASA UAM reference vehicles and the design/technology issues (batteries, rotors, noise, safety) behind them.
- **How we use it:** WP M/D: overview reference when writing the design rationale; link only (published by Cambridge University Press, not stored).
- **Credibility:** High; peer-reviewed review by the NDARC author.

### SZ05 - NDARC - NASA Design and Analysis of Rotorcraft: Theory (Vol. 1) and Appendix 3

- **Citation:** Johnson, W. (2022). *NDARC - NASA Design and Analysis of Rotorcraft: Theory (Vol. 1) and Appendix 3*. NASA TP-20220000355 (theory), NASA TP-2009-215402 Appendix 3.
- **Link:** [https://ntrs.nasa.gov/citations/20220000355](https://ntrs.nasa.gov/citations/20220000355); [https://rotorcraft.arc.nasa.gov/Publications/files/NASA%20TP-2009-215402-app3.pdf](https://rotorcraft.arc.nasa.gov/Publications/files/NASA%20TP-2009-215402-app3.pdf); [https://rotorcraft.arc.nasa.gov/ndarc/](https://rotorcraft.arc.nasa.gov/ndarc/)
- **Type:** NASA report (technical publication). **Used by:** WP M, D.
- **What it is:** Full theory manual of NDARC: mission and sizing logic, momentum-theory based rotor performance with induced (kappa) and profile power models, weight equations (AFDD), battery and motor models.
- **How we use it:** WP M: source of the rotor hover/forward-flight power equations (ideal induced power, kappa, profile power coefficient) and the empirical weight equations used in methods/EQUATIONS.md.
- **Credibility:** High; the standard US government rotorcraft sizing method. Weight equations are calibrated on helicopters and must be used with care for small electric aircraft.

### SZ06 - A Proposed Approach to Studying Urban Air Mobility Missions Including an Initial Exploration of Mission Requirements

- **Citation:** Patterson, M. D.; Antcliff, K. R.; Kohlman, L. W. (2018). *A Proposed Approach to Studying Urban Air Mobility Missions Including an Initial Exploration of Mission Requirements*. AHS International 74th Annual Forum, Phoenix, May 2018.
- **Link:** [https://ntrs.nasa.gov/citations/20190000991](https://ntrs.nasa.gov/citations/20190000991)
- **Local copy:** [`papers/NASA-20190000991_Patterson2018_UAM_missions.pdf`](papers/NASA-20190000991_Patterson2018_UAM_missions.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP D, V.
- **What it is:** NASA Langley study of UAM mission definitions (segments, reserves, hover times) and their effect on vehicle size.
- **How we use it:** WP D: cross-check of our mission profile (60 s hover, 30 s transitions, 20% energy reserve) against published mission assumptions.
- **Credibility:** High (NASA); mission assumptions, not regulations.

### SZ07 - Benefits of Hybrid-Electric Propulsion to Achieve 4x Increase in Cruise Efficiency for a VTOL Aircraft

- **Citation:** Fredericks, W. J.; Moore, M. D.; Busan, R. C. (2013). *Benefits of Hybrid-Electric Propulsion to Achieve 4x Increase in Cruise Efficiency for a VTOL Aircraft*. AIAA International Powered Lift Conference, AIAA 2013-4324, doi:10.2514/6.2013-4324.
- **Link:** [https://ntrs.nasa.gov/citations/20140001088](https://ntrs.nasa.gov/citations/20140001088)
- **Local copy:** [`papers/NASA-20140001088_Fredericks2013_GL10.pdf`](papers/NASA-20140001088_Fredericks2013_GL10.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP D, M.
- **What it is:** Design history of NASA's GL-10 'Greased Lightning' distributed-electric tilt-wing, from configuration brainstorm through subscale build and transition flight tests.
- **How we use it:** WP D/M: supports the argument that a winged electric VTOL can reach a cruise L/D several times that of a helicopter; subscale build lessons relevant to the E8-S demonstrator path.
- **Key data:**
  - Helicopters typically achieve L/D 4-5; GL-10 designed for L/D ~20 (abstract)
  - Cruise span ~20 ft for the concept variants (design table, p.~9)
  - Electric motor/generators assumed 0.5 lb/hp in early sizing (p.3)
- **Credibility:** High (NASA); UAV-scale (20 ft span) hybrid vehicle, so numbers are not directly transferable.

### SZ08 - Conceptual Design and Mission Analysis for eVTOL Urban Air Mobility Flight Vehicle Configurations

- **Citation:** Kadhiresan, A. R.; Duffy, M. J. (2019). *Conceptual Design and Mission Analysis for eVTOL Urban Air Mobility Flight Vehicle Configurations*. AIAA Aviation 2019 Forum, AIAA 2019-2873, doi:10.2514/6.2019-2873.
- **Link:** [https://doi.org/10.2514/6.2019-2873](https://doi.org/10.2514/6.2019-2873)
- **Type:** paper (AIAA conference). **Used by:** WP D, M.
- **What it is:** Boeing/Purdue study comparing multicopter, lift+cruise and tilting configurations on UAM missions with a common sizing method, including mission-length sensitivity.
- **How we use it:** WP D/M: configuration trade background for lift+cruise vs multicopter as a function of range; link only (AIAA copyright).
- **Credibility:** Medium-high: AIAA conference paper (not journal-reviewed) by industry authors. Abstract not available in open indexes; numbers not quoted here until the paper is read in full.

### SZ09 - Vehicle Design and Optimization Model for Urban Air Mobility

- **Citation:** Brown, A.; Harris, W. L. (2020). *Vehicle Design and Optimization Model for Urban Air Mobility*. Journal of Aircraft 57(6), 1003-1013, doi:10.2514/1.C035756.
- **Link:** [https://doi.org/10.2514/1.C035756](https://doi.org/10.2514/1.C035756)
- **Type:** paper (peer-reviewed). **Used by:** WP D, M.
- **What it is:** MIT geometric-programming sizing tool combining vehicle, mission and cost models for UAM; compares configurations and identifies the battery and pilot as the main cost drivers.
- **How we use it:** WP D: template for a cost-in-the-loop sizing objective; supports our choice to optimise acquisition cost rather than mass. Sensitivities to reserve, range and battery energy density.
- **Key data:**
  - Configurations with higher L/D but higher disk loading generally weigh less and cost less to operate (abstract)
  - Battery and pilot identified as the two main cost drivers (abstract)
- **Credibility:** High; peer-reviewed journal paper.

### SZ10 - Electric VTOL Configurations Comparison

- **Citation:** Bacchini, A.; Cestino, E. (2019). *Electric VTOL Configurations Comparison*. Aerospace 6(3), 26, doi:10.3390/aerospace6030026.
- **Link:** [https://doi.org/10.3390/aerospace6030026](https://doi.org/10.3390/aerospace6030026)
- **Type:** paper (peer-reviewed, open access). **Used by:** WP M, D.
- **What it is:** Compares a multirotor, a lift+cruise and a vectored-thrust eVTOL on disk loading, hover time, cruise speed, range and energy for urban, extra-urban and long-range missions.
- **How we use it:** WP D/M: published energy comparison of configurations; the paper's mission-energy method is a simple independent check for methods/check_design.py.
- **Key data:**
  - Multirotor most efficient in hover; vectored-thrust jet most efficient in cruise; lift+cruise is the compromise (abstract)
- **Credibility:** Medium-high: open-access MDPI journal; uses public data of real aircraft with simplified models.

### SZ11 - A Study in Reducing the Cost of Vertical Flight with Electric Propulsion

- **Citation:** Duffy, M. J.; Wakayama, S. R.; Hupp, R. (2017). *A Study in Reducing the Cost of Vertical Flight with Electric Propulsion*. 17th AIAA Aviation Technology, Integration, and Operations Conference, AIAA 2017-3442, doi:10.2514/6.2017-3442.
- **Link:** [https://doi.org/10.2514/6.2017-3442](https://doi.org/10.2514/6.2017-3442)
- **Type:** paper (AIAA conference). **Used by:** WP D, P.
- **What it is:** Boeing study of how electric propulsion changes acquisition and operating cost of VTOL aircraft (part count, maintenance, energy cost).
- **How we use it:** WP D/P: cost-model background for 'minimum acquisition cost and build complexity'. Link only.
- **Credibility:** Medium-high: AIAA conference paper by industry; numbers not quoted here.

### SZ12 - Propulsion Scaling Methods in the Era of Electric Flight

- **Citation:** Duffy, M.; Sevier, A.; Hupp, R.; Perdomo, E.; Wakayama, S. (2018). *Propulsion Scaling Methods in the Era of Electric Flight*. AIAA/IEEE Electric Aircraft Technologies Symposium, AIAA 2018-4978, doi:10.2514/6.2018-4978.
- **Link:** [https://doi.org/10.2514/6.2018-4978](https://doi.org/10.2514/6.2018-4978)
- **Type:** paper (AIAA conference). **Used by:** WP M, P.
- **What it is:** Scaling relations for electric motors, controllers and rotors used in distributed-propulsion eVTOL sizing.
- **How we use it:** WP M/P: cross-check of motor mass vs torque/power scaling used for COTS motor selection.
- **Credibility:** Medium-high: AIAA conference paper.

### SZ13 - Fast-Forwarding to a Future of On-Demand Urban Air Transportation (Uber Elevate white paper)

- **Citation:** Holden, J.; Goel, N. (Uber Elevate) (2016). *Fast-Forwarding to a Future of On-Demand Urban Air Transportation (Uber Elevate white paper)*. Uber Technologies, Oct. 2016 (hosted by the Vertical Flight Society).
- **Link:** [https://evtol.news/__media/PDFs/UberElevateWhitePaperOct2016.pdf](https://evtol.news/__media/PDFs/UberElevateWhitePaperOct2016.pdf)
- **Type:** industry white paper. **Used by:** WP D.
- **What it is:** The industry paper that launched the UAM wave; sets out vehicle, battery, noise and cost assumptions for eVTOL air taxis.
- **How we use it:** WP R/D: historical context and the commonly cited 400 Wh/kg pack target; not used for design numbers.
- **Key data:**
  - Economic model assumes 400 Wh/kg pack-level batteries with 2,000-cycle life (p.~90)
  - 'nominally a 140 kWh pack' for eVTOLs (p.~30)
- **Credibility:** Low-medium: corporate white paper, not reviewed; battery targets were aspirational.

### SZ14 - Vahana Configuration Trade Study, Parts I and II (with MATLAB sizing code)

- **Citation:** Airbus A3 Vahana team (Bower, G. et al.) (2016). *Vahana Configuration Trade Study, Parts I and II (with MATLAB sizing code)*. Airbus A3 blog, Dec. 2016 (archived); code at github.com/VahanaOpenSource.
- **Link:** [https://web.archive.org/web/2019/https://acubed.airbus.com/blog/vahana/vahana-configuration-trade-study-part-i/](https://web.archive.org/web/2019/https://acubed.airbus.com/blog/vahana/vahana-configuration-trade-study-part-i/); [https://github.com/VahanaOpenSource/vahanaTradeStudy](https://github.com/VahanaOpenSource/vahanaTradeStudy)
- **Type:** industry blog + open-source code. **Used by:** WP D, M, V.
- **What it is:** Airbus' published sizing trade between an electric helicopter and an 8-fan tandem tilt-wing for a single-passenger eVTOL, solved with MDO; the sizing code is open source.
- **How we use it:** WP D/M: an open, executable single-seat eVTOL sizing model to benchmark our sizing code against; mission and battery assumptions at our scale.
- **Key data:**
  - Installed pack specific energy 'just under 200 Wh/kg' at the time, projected 230 Wh/kg after 3 years (5-6%/yr) (Part I)
  - Hover and each transition assumed ~90 s; reserve 20 min at minimum-power speed (Part I)
  - 8 fans chosen for motor-out redundancy and small footprint (Part I)
- **Credibility:** Medium: company blog, not peer-reviewed, but code is open and inspectable. Original URL now redirects; use the archive copy.

### SZ15 - eVTOL Stored Energy Overview (McDonald and German, Uber Elevate Summit 2017) - research summary

- **Citation:** German, B. J. (Georgia Tech); McDonald, R. (Uber) (2017). *eVTOL Stored Energy Overview (McDonald and German, Uber Elevate Summit 2017) - research summary*. Presentation, Uber Elevate Summit, Dallas, Apr. 2017; summary on Georgia Tech research page.
- **Link:** [https://bgerman.ae.gatech.edu/research.html](https://bgerman.ae.gatech.edu/research.html)
- **Type:** university research page. **Used by:** WP R.
- **What it is:** Study of how battery specific energy drives eVTOL size and range for Uber's Dallas-Fort Worth market. Only a summary page could be located; the slide deck itself was not found at a stable URL.
- **How we use it:** Context only; no numbers are taken from it.
- **Credibility:** Low as a citable source (presentation, not located in full). Listed because the work package brief named it.

## 2. Batteries: cells, pack overhead, safety requirements

### BT01 - Molicel INR-21700-P50B product data sheet (v1.1)

- **Citation:** Molicel (E-One Moli Energy) (2022). *Molicel INR-21700-P50B product data sheet (v1.1)*. Manufacturer data sheet.
- **Link:** [https://www.molicel.com/wp-content/uploads/4.TR%E7%B0%A1%E6%98%93%E8%A6%8F%E6%A0%BC_INR21700P50B_1.1_Product-Data-Sheet-of-INR-21700-P50B-80122.pdf](https://www.molicel.com/wp-content/uploads/4.TR%E7%B0%A1%E6%98%93%E8%A6%8F%E6%A0%BC_INR21700P50B_1.1_Product-Data-Sheet-of-INR-21700-P50B-80122.pdf); [https://www.molicel.com/product/inr-21700-p50b/](https://www.molicel.com/product/inr-21700-p50b/)
- **Type:** datasheet. **Used by:** WP D, P.
- **What it is:** One-page cell data sheet for the high-power/high-energy 21700 cell used in the first E8 iteration.
- **How we use it:** WP D/P: baseline cell for pack sizing (energy, mass, current limit, resistance for voltage sag).
- **Key data:**
  - Capacity 5,000 mAh typ / 4,850 mAh min; 18.0 Wh typ / 17.5 Wh min; 3.6 V nominal, 4.2 V charge, 2.5 V cutoff
  - Continuous discharge 60 A (80 C cutoff); max charge 25 A
  - 260 Wh/kg, 714 Wh/L; DC impedance 12.8 mOhm (50% SOC), AC 6.5 mOhm (30% SOC)
  - Mass 71 g max; 21.55 mm x 70.15 mm max
- **Credibility:** High for nominal values (manufacturer); data sheet states it is for reference only. Pack-level performance must be derated (see BT06, SZ01, SZ02).

### BT02 - Molicel INR-21700-P45B product page

- **Citation:** Molicel (2026). *Molicel INR-21700-P45B product page*. Manufacturer web page.
- **Link:** [https://www.molicel.com/product/inr-21700-p45b/](https://www.molicel.com/product/inr-21700-p45b/)
- **Type:** manufacturer product page. **Used by:** WP D, P.
- **What it is:** Specification summary of the lower-impedance 4.5 Ah 21700 cell (full data sheet behind a request form).
- **How we use it:** WP D: alternative cell for a power-limited (hover/OEI) pack design.
- **Key data:**
  - 4.5 Ah typ, 3.6 V; 45 A continuous; 69 g max; 242 Wh/kg, 643 Wh/L (product page)
- **Credibility:** High (manufacturer), summary values only.

### BT03 - Samsung SDI INR21700-50G specification of product (V1.0)

- **Citation:** Samsung SDI (2018). *Samsung SDI INR21700-50G specification of product (V1.0)*. Manufacturer specification (hosted by distributor Master Instruments).
- **Link:** [https://www.master-instruments.com.au/file/67273/1/Samsung-INR21700-50G.pdf](https://www.master-instruments.com.au/file/67273/1/Samsung-INR21700-50G.pdf)
- **Type:** datasheet. **Used by:** WP D.
- **What it is:** Full cell specification for an energy-type 21700 cell.
- **How we use it:** WP D: energy-optimised cell option; shows the low continuous current of energy cells (relevant to hover C-rate).
- **Key data:**
  - 4,900 mAh min standard capacity (0.2C); 4,753 mAh min rated (1C); 3.63 V nominal
  - Max continuous discharge 3C = 14.7 A (-20 to 30 C) or 2C = 9.8 A (31 to 60 C)
  - 71 g max; cycle life >= 80% rated capacity after 500 cycles
- **Credibility:** High (manufacturer document), distributor-hosted copy.

### BT04 - Samsung SDI INR21700-50S introduction (2021 v2)

- **Citation:** Samsung SDI (2021). *Samsung SDI INR21700-50S introduction (2021 v2)*. Manufacturer product introduction (hosted by distributor).
- **Link:** [https://salespot.com.ua/content/files/introduction-of-inr21700-50s_2021_v220210104-66391931.pdf](https://salespot.com.ua/content/files/introduction-of-inr21700-50s_2021_v220210104-66391931.pdf)
- **Type:** manufacturer presentation. **Used by:** WP D.
- **What it is:** Manufacturer slide set with capacity, discharge capability and cycle-life data for the 50S high-power 21700 cell.
- **How we use it:** WP D: alternative high-power cell; ratings to compare with P50B.
- **Key data:**
  - Standard capacity 5,000 mAh typ (0.2C), rated 4,800 mAh min (10 A)
  - Max continuous discharge 25 A without temperature cutoff; 45 A with 80 C cutoff
  - Cycle life 60% after 250 cycles at 6 A charge / 25 A discharge
- **Credibility:** Medium: genuine manufacturer slides but hosted by a third party and marked confidential; cell mass not stated in this document (vendors list ~70-72 g, not verified here).

### BT05 - Amprius SiCore cells (SA109 450 Wh/kg pouch, aviation cells) - product pages

- **Citation:** Amprius Technologies (2025). *Amprius SiCore cells (SA109 450 Wh/kg pouch, aviation cells) - product pages*. Manufacturer web pages.
- **Link:** [https://amprius.com/products/sa109/](https://amprius.com/products/sa109/); [https://amprius.com/products](https://amprius.com/products)
- **Type:** manufacturer product page. **Used by:** WP D.
- **What it is:** Silicon-anode pouch cells marketed for aviation; the SA109 is listed as preliminary.
- **How we use it:** WP D: technology-sensitivity case only (future cell). Not a baseline: pouch format, limited availability, preliminary data.
- **Key data:**
  - SA109: 450 Wh/kg, 1,000 Wh/L (product page; press release quotes 950 Wh/L), 11.5 Ah, marked preliminary
  - Aviation product line listed as 15+ Ah, 380+ Wh/kg at C/5 with 6C long pulse (products page)
- **Credibility:** Low-medium for design use: marketing values, 'preliminary', no full data sheet located. Site blocks automated link checks (HTTP 403) but pages were reached through search on 2026-11-12.

### BT06 - Performance Metrics Required of Next-Generation Batteries to Electrify Vertical Takeoff and Landing (VTOL) Aircraft

- **Citation:** Fredericks, W. L.; Sripad, S.; Bower, G. C.; Viswanathan, V. (2018). *Performance Metrics Required of Next-Generation Batteries to Electrify Vertical Takeoff and Landing (VTOL) Aircraft*. ACS Energy Letters 3(12), 2989-2994, doi:10.1021/acsenergylett.8b02195.
- **Link:** [https://doi.org/10.1021/acsenergylett.8b02195](https://doi.org/10.1021/acsenergylett.8b02195)
- **Type:** paper (peer-reviewed). **Used by:** WP D, M.
- **What it is:** Derives the specific power and energy a battery must deliver in the hover/landing segments of an eVTOL mission (high power at low state of charge) and its consequences for cell selection and cycle life.
- **How we use it:** WP D/M: the reason we check pack power at end-of-mission SOC and end-of-life capacity, not just energy.
- **Credibility:** High; peer-reviewed. Numbers to be taken from the paper when read in full (publisher blocks automated retrieval).

### BT07 - The promise of energy-efficient battery-powered urban aircraft

- **Citation:** Sripad, S.; Viswanathan, V. (2021). *The promise of energy-efficient battery-powered urban aircraft*. PNAS 118(45), e2111164118, doi:10.1073/pnas.2111164118.
- **Link:** [https://doi.org/10.1073/pnas.2111164118](https://doi.org/10.1073/pnas.2111164118)
- **Type:** paper (peer-reviewed, open access). **Used by:** WP M, V.
- **What it is:** Energy-per-passenger-mile and battery specific power/energy requirements for many published UAM aircraft, compared with ground vehicles.
- **How we use it:** WP M: published energy-intensity numbers to place our design (Wh per payload-km) against other eVTOLs.
- **Key data:**
  - UAM aircraft consume 130 to ~1,200 Wh/passenger-mile depending on design (abstract)
  - Several designs approach viability with current Li-ion on specific power and energy; cycle life remains uncertain (abstract)
- **Credibility:** High; PNAS, open access.

### BT08 - Lithium-Ion Battery Modeling for Aerospace Applications

- **Citation:** Clarke, M.; Alonso, J. J. (2021). *Lithium-Ion Battery Modeling for Aerospace Applications*. Journal of Aircraft 58(6), 1323-1335, doi:10.2514/1.C036209.
- **Link:** [https://doi.org/10.2514/1.C036209](https://doi.org/10.2514/1.C036209)
- **Type:** paper (peer-reviewed). **Used by:** WP D, M.
- **What it is:** Equivalent-circuit and thermal battery model as implemented in SUAVE, validated on cell data, for mission analysis of electric aircraft.
- **How we use it:** WP D: voltage-sag/thermal model form for the mission simulation (R0 + RC model using data-sheet impedance).
- **Credibility:** High; peer-reviewed, open-source implementation.

### BT09 - Means of Compliance with the Special Condition VTOL, MOC-3 SC-VTOL (Issue 2) - incl. MOC VTOL.2440 propulsion battery thermal runaway

- **Citation:** EASA (2023). *Means of Compliance with the Special Condition VTOL, MOC-3 SC-VTOL (Issue 2) - incl. MOC VTOL.2440 propulsion battery thermal runaway*. EASA, 21 June 2023.
- **Link:** [https://www.easa.europa.eu/en/downloads/136701/en](https://www.easa.europa.eu/en/downloads/136701/en); [https://www.easa.europa.eu/en/downloads/138076/en](https://www.easa.europa.eu/en/downloads/138076/en)
- **Type:** regulation (EASA means of compliance). **Used by:** WP D, P, V.
- **What it is:** EASA's accepted means of compliance for VTOL propulsion batteries, including how to address cell thermal runaway and propagation (DO-311A containment test or a time-based continued-safe-flight-and-landing test).
- **How we use it:** WP D/P/V: pack architecture requirements (cell-to-cell propagation barriers, venting, containment) for our 2 independent packs.
- **Key data:**
  - Two compliance routes for propulsion batteries under MOC VTOL.2440: RTCA DO-311A containment test or a CSFL-time-based test (as summarised in the MOC and its CRD)
- **Credibility:** High (regulator). Applies formally to EASA SC-VTOL projects; used here as best-practice design guidance.

### BT10 - RTCA DO-311A, Minimum Operational Performance Standards for Rechargeable Lithium Batteries and Battery Systems

- **Citation:** RTCA SC-225 (2017). *RTCA DO-311A, Minimum Operational Performance Standards for Rechargeable Lithium Batteries and Battery Systems*. RTCA, Washington DC.
- **Link:** [https://www.rtca.org/](https://www.rtca.org/); [https://www.batterydesign.net/legislation-rules-and-regulations/do-311a/](https://www.batterydesign.net/legislation-rules-and-regulations/do-311a/)
- **Type:** standard (paywalled) + secondary summary. **Used by:** WP P, V.
- **What it is:** The aviation MOPS for rechargeable lithium batteries, including the thermal-runaway containment test referenced by FAA and EASA guidance.
- **How we use it:** WP P/V: test requirement reference for pack design; we cite it but do not hold the paywalled text.
- **Credibility:** High (standard) but not held; secondary summary is medium credibility.

### BT11 - AC 20-184, Guidance on Testing and Installation of Rechargeable Lithium Battery and Battery Systems on Aircraft

- **Citation:** FAA (2015). *AC 20-184, Guidance on Testing and Installation of Rechargeable Lithium Battery and Battery Systems on Aircraft*. FAA Advisory Circular.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-184.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-184.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP P, V.
- **What it is:** FAA installation and test guidance for rechargeable lithium batteries, built around DO-311.
- **How we use it:** WP P/V: installation requirements (venting, isolation, monitoring) for the battery bays.
- **Credibility:** High (regulator guidance). Written for non-propulsion batteries; propulsion packs need more (see BT09, ST05).

### BT12 - Ehang EH216-S eVTOL Battery

- **Citation:** Battery Design (batterydesign.net) (2024). *Ehang EH216-S eVTOL Battery*. Web article.
- **Link:** [https://www.batterydesign.net/ehang-eh216-s-evtol-battery/](https://www.batterydesign.net/ehang-eh216-s-evtol-battery/)
- **Type:** technical blog (secondary). **Used by:** WP M.
- **What it is:** Collects public statements on the EH216-S battery (pack count, energy) with links to the original claims.
- **How we use it:** WP M: only source found for EH216-S battery energy; used with a low-credibility flag in benchmarks_raw.json.
- **Key data:**
  - 17 kWh total, 12 batteries combined as one system (attributed to EHang)
  - 21 min flight time with baseline pack
- **Credibility:** Low-medium: secondary site; pack mass in the article is an estimate.

## 3. Rotor aerodynamics and interference

### RA01 - Principles of Helicopter Aerodynamics, 2nd ed.

- **Citation:** Leishman, J. G. (2006). *Principles of Helicopter Aerodynamics, 2nd ed.*. Cambridge University Press, ISBN 978-0-521-85860-1.
- **Link:** [https://doi.org/10.1017/S0001924000064058](https://doi.org/10.1017/S0001924000064058)
- **Type:** book. **Used by:** WP M, D, C.
- **What it is:** Standard rotor aerodynamics text: momentum theory, figure of merit, blade element and BEMT with tip-loss, rotor wakes, ground effect, rotor-airframe interaction.
- **How we use it:** WP M: equations for ideal hover power P = T^1.5/sqrt(2 rho A), figure of merit, BEMT and Prandtl tip loss used in methods/EQUATIONS.md and the rotor model. (Link is the Aeronautical Journal review record; the book is not freely available.)
- **Credibility:** High; standard graduate text.

### RA02 - Rotorcraft Aeromechanics

- **Citation:** Johnson, W. (2013). *Rotorcraft Aeromechanics*. Cambridge University Press, doi:10.1017/CBO9781139235655.
- **Link:** [https://doi.org/10.1017/CBO9781139235655](https://doi.org/10.1017/CBO9781139235655)
- **Type:** book. **Used by:** WP M.
- **What it is:** Comprehensive reference on rotor performance, induced-power factors, forward-flight rotor theory, wake and interference.
- **How we use it:** WP M: induced power factor and edgewise-flight rotor power for transition; background to NDARC (SZ05).
- **Credibility:** High.

### RA03 - Rotor/Wing Aerodynamic Interactions in Hover

- **Citation:** Felker, F. F.; Light, J. S. (1986). *Rotor/Wing Aerodynamic Interactions in Hover*. NASA TM-88255.
- **Link:** [https://ntrs.nasa.gov/citations/19860018588](https://ntrs.nasa.gov/citations/19860018588)
- **Local copy:** [`papers/NASA-19860018588_Felker1986_rotor_wing_download.pdf`](papers/NASA-19860018588_Felker1986_rotor_wing_download.pdf)
- **Type:** NASA report (technical memorandum). **Used by:** WP C, D, V.
- **What it is:** Experimental and theoretical study of the download a rotor wake produces on a wing below it (tilt-rotor geometry), with effects of flap angle, incidence and rotor-wing spacing.
- **How we use it:** WP C/D: download allowance for wing area under the lift rotors and for the boom/wing layout; validation case for our hover CFD of the rotor-wing interaction.
- **Key data:**
  - Tilt-rotor wing download can be as large as 15% of rotor thrust in hover (p.1, refs 1-2)
  - Download reduced ~30% by a 75 deg flap vs 0 deg; 25% from 0 to 60 deg flap; XV-15 flight data 32% for 0 to 60 deg (p.~8)
  - Wing incidence 0 to -8 deg increased download ~6%; 0 to +8 deg reduced it ~10% (p.~8)
- **Credibility:** High (NASA test data). Tilt-rotor geometry (wing directly under the rotor) is the worst case; lift+cruise booms with rotors outboard of the wing give much smaller download.

### RA04 - Impact of lift propeller drag on the performance of eVTOL lift+cruise aircraft

- **Citation:** Bacchini, A.; Cestino, E.; Van Magill, B.; Verstraete, D. (2021). *Impact of lift propeller drag on the performance of eVTOL lift+cruise aircraft*. Aerospace Science and Technology 109, 106429, doi:10.1016/j.ast.2020.106429.
- **Link:** [https://doi.org/10.1016/j.ast.2020.106429](https://doi.org/10.1016/j.ast.2020.106429); [https://iris.polito.it/handle/11583/2859251](https://iris.polito.it/handle/11583/2859251)
- **Type:** paper (peer-reviewed). **Used by:** WP M, C, D.
- **What it is:** Wind-tunnel measurement of the parasitic drag of stopped lift propellers on a lift+cruise model, and its effect on cruise speed and range.
- **How we use it:** WP M/C/D: stopped-rotor drag increment in the cruise drag build-up; justification for aligning stopped blades with the flow and for the boom/rotor fairing design.
- **Key data:**
  - Retracting the lift propellers reduced parasitic drag by 38% (abstract)
  - Retraction allows 21% higher cruise speed at the same range or 13% more range at the same speed for a passenger lift+cruise (abstract)
- **Credibility:** High; peer-reviewed, experimental. Model-scale; the 38% figure is configuration-specific.

### RA05 - High-Fidelity Computational Aerodynamics of Multi-Rotor Unmanned Aerial Vehicles

- **Citation:** Ventura Diaz, P.; Yoon, S. (2018). *High-Fidelity Computational Aerodynamics of Multi-Rotor Unmanned Aerial Vehicles*. AIAA SciTech 2018, AIAA 2018-1266, doi:10.2514/6.2018-1266.
- **Link:** [https://ntrs.nasa.gov/citations/20180001326](https://ntrs.nasa.gov/citations/20180001326)
- **Local copy:** [`papers/NASA-20180001326_VenturaDiaz2018_multirotor_CFD.pdf`](papers/NASA-20180001326_VenturaDiaz2018_multirotor_CFD.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP C.
- **What it is:** OVERFLOW overset CFD of small multicopters (DJI Phantom 3, Elytron) in hover and forward flight, including airframe download and rotor-rotor interaction.
- **How we use it:** WP C: method reference (grid spacing, wake resolution, turbulence model) for rotor CFD; evidence that airframe in the wake gives download but can reduce rotor-rotor interaction.
- **Key data:**
  - Complete Phantom 3 airframe: net thrust 1% lower than simplified airframe because of download on landing gear/battery (p.10)
  - Wake region grid spacing 10% of tip chord (p.~4)
- **Credibility:** High (NASA); small-UAV scale.

### RA06 - Computational Study of NASA's Quadrotor Urban Air Taxi Concept

- **Citation:** Ventura Diaz, P.; Yoon, S. (2020). *Computational Study of NASA's Quadrotor Urban Air Taxi Concept*. AIAA SciTech 2020, AIAA 2020-0302, doi:10.2514/6.2020-0302.
- **Link:** [https://ntrs.nasa.gov/citations/20200000444](https://ntrs.nasa.gov/citations/20200000444)
- **Local copy:** [`papers/NASA-20200000444_VenturaDiaz2020_quadrotor_air_taxi.pdf`](papers/NASA-20200000444_VenturaDiaz2020_quadrotor_air_taxi.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP D, C.
- **What it is:** OVERFLOW/CAMRAD II simulation of the NASA 6-passenger quadrotor; studies the effect of raising the rear rotors above the front rotors on cruise power.
- **How we use it:** WP D/C: guidance on vertical offset of front/rear lift rotors on the booms (fore-aft wake interaction).
- **Key data:**
  - Raising rear rotors to z = 0.6R above the front rotors reduced total rotor cruise power by 8% (p.~11, Fig. 14)
  - Up to 311 million grid points with 10% c_tip off-body spacing (p.~7)
- **Credibility:** High (NASA).

### RA07 - High-Fidelity Simulations of a Quadrotor Vehicle for Urban Air Mobility

- **Citation:** Ventura Diaz, P.; Yoon, S. (2022). *High-Fidelity Simulations of a Quadrotor Vehicle for Urban Air Mobility*. AIAA SciTech 2022, AIAA 2022-0152, doi:10.2514/6.2022-0152.
- **Link:** [https://doi.org/10.2514/6.2022-0152](https://doi.org/10.2514/6.2022-0152)
- **Type:** paper (AIAA conference). **Used by:** WP C.
- **What it is:** DDES simulations of the NASA quadrotor in hover and cruise with collective trim; compares isolated rotors with the complete vehicle.
- **How we use it:** WP C: isolated-rotor vs installed-rotor comparison method.
- **Credibility:** High (NASA authors, AIAA paper).

### RA08 - High-Fidelity Analysis of Lift+Cruise VTOL Urban Air Mobility Concept Aircraft

- **Citation:** Liu, Y.; Druyor, C. T.; Wang, L. (2023). *High-Fidelity Analysis of Lift+Cruise VTOL Urban Air Mobility Concept Aircraft*. AIAA Aviation 2023, AIAA 2023-3671, doi:10.2514/6.2023-3671.
- **Link:** [https://ntrs.nasa.gov/citations/20230004303](https://ntrs.nasa.gov/citations/20230004303)
- **Type:** NASA report (conference paper). **Used by:** WP C.
- **What it is:** FUN3D overset CFD coupled with comprehensive analysis of the NASA lift+cruise (SZ01) in hover and low-speed flight; compares SA-neg and SA-neg-R turbulence models.
- **How we use it:** WP C: the closest high-fidelity study of our configuration; turbulence-model choice (rotation correction) for rotor wakes. Link only (NTRS marks it government-permitted, not public).
- **Key data:**
  - Rotation-corrected SA (SA-neg-R) significantly improves resolution of secondary vortices and wake interactions (abstract)
- **Credibility:** High (NASA).

### RA09 - Computational Investigation of Multirotor Interactional Aerodynamics with Hub Lateral and Longitudinal Canting

- **Citation:** Healy, R.; Gandhi, F.; Mistry, M. (2022). *Computational Investigation of Multirotor Interactional Aerodynamics with Hub Lateral and Longitudinal Canting*. AIAA Journal 60(2), 872-882, doi:10.2514/1.J060530.
- **Link:** [https://doi.org/10.2514/1.J060530](https://doi.org/10.2514/1.J060530)
- **Type:** paper (peer-reviewed). **Used by:** WP D, C.
- **What it is:** DES study of a front and aft 5.5 ft rotor in line with the flow at 30 kt (transition-like condition), with canting variations.
- **How we use it:** WP D/C: aft-rotor lift deficit in transition, used as a margin on the rear rotors of each boom.
- **Key data:**
  - Uncanted aft rotor: ~15% lift deficit relative to an isolated rotor at 5 lb/ft2 and 30 kt (abstract)
  - Inward longitudinal cant raised the deficit to 21% (abstract)
- **Credibility:** High; peer-reviewed.

### RA10 - Wind Tunnel and Hover Performance Test Results for Multicopter UAS Vehicles

- **Citation:** Russell, C. R.; Jung, J.; Willink, G.; Glasner, B. (2016). *Wind Tunnel and Hover Performance Test Results for Multicopter UAS Vehicles*. AHS 72nd Annual Forum, West Palm Beach, May 2016.
- **Link:** [https://ntrs.nasa.gov/citations/20160007399](https://ntrs.nasa.gov/citations/20160007399)
- **Local copy:** [`papers/NASA-20160007399_Russell2016_multicopter_tests.pdf`](papers/NASA-20160007399_Russell2016_multicopter_tests.pdf)
- **Type:** NASA report (conference paper). **Used by:** WP C, V.
- **What it is:** Wind-tunnel and hover test data (forces, moments, electrical power) for five multicopters and their isolated rotors in the 7x10 ft tunnel at NASA Ames.
- **How we use it:** WP C/V: validation data for small-rotor BEMT/CFD and for the subscale E8-S rotor.
- **Credibility:** High (NASA test data); small-scale rotors.

### RA11 - Propeller Performance Data at Low Reynolds Numbers (and UIUC Propeller Data Site)

- **Citation:** Brandt, J. B.; Selig, M. S. (2011). *Propeller Performance Data at Low Reynolds Numbers (and UIUC Propeller Data Site)*. 49th AIAA Aerospace Sciences Meeting, AIAA 2011-1255, doi:10.2514/6.2011-1255.
- **Link:** [https://m-selig.ae.illinois.edu/props/propDB.html](https://m-selig.ae.illinois.edu/props/propDB.html); [https://doi.org/10.2514/6.2011-1255](https://doi.org/10.2514/6.2011-1255)
- **Type:** paper (AIAA conference) + database. **Used by:** WP V, C.
- **What it is:** Measured CT, CP and efficiency of many small propellers; database maintained at UIUC.
- **How we use it:** WP V/C: validation of the propeller/BEMT model at low Reynolds number (E8-S subscale and pusher model checks).
- **Credibility:** High (university test data); small propellers only.

### RA12 - Multirotor Drone Aerodynamic Interaction Investigation

- **Citation:** Shukla, D.; Komerath, N. (2018). *Multirotor Drone Aerodynamic Interaction Investigation*. Drones 2(4), 43, doi:10.3390/drones2040043.
- **Link:** [https://doi.org/10.3390/drones2040043](https://doi.org/10.3390/drones2040043)
- **Type:** paper (peer-reviewed, open access). **Used by:** WP D.
- **What it is:** PIV and load measurements of side-by-side small rotors at varying tip spacing.
- **How we use it:** WP D: minimum lateral tip clearance between adjacent lift rotors.
- **Credibility:** Medium-high: open-access journal, low Reynolds number.

### RA13 - Modeling Multirotor Aerodynamic Interactions Through the Vortex Particle Method

- **Citation:** Alvarez, E. J.; Ning, A. (2019). *Modeling Multirotor Aerodynamic Interactions Through the Vortex Particle Method*. AIAA Aviation 2019, AIAA 2019-2827, doi:10.2514/6.2019-2827.
- **Link:** [https://doi.org/10.2514/6.2019-2827](https://doi.org/10.2514/6.2019-2827)
- **Type:** paper (AIAA conference). **Used by:** WP C.
- **What it is:** Mid-fidelity vortex-particle modelling of rotor-rotor interaction (basis of the open-source FLOWUnsteady code).
- **How we use it:** WP C: alternative mid-fidelity method to DUST for transition interaction studies.
- **Credibility:** Medium-high: AIAA conference paper; method later published in journals.

### RA14 - Mid-fidelity numerical approach for the investigation of wing-propeller aerodynamic interaction

- **Citation:** Niro, C.; Savino, A.; Cocco, A.; Zanotti, A. (2024). *Mid-fidelity numerical approach for the investigation of wing-propeller aerodynamic interaction*. Aerospace Science and Technology 146, 108950, doi:10.1016/j.ast.2024.108950.
- **Link:** [https://doi.org/10.1016/j.ast.2024.108950](https://doi.org/10.1016/j.ast.2024.108950)
- **Type:** paper (peer-reviewed). **Used by:** WP C.
- **What it is:** Validation of the DUST vortex-particle solver for wing-propeller interaction against experiments.
- **How we use it:** WP C: validation evidence for using DUST (TL06) for boom/wing/rotor interaction.
- **Credibility:** High; peer-reviewed.

## 4. Wing / aircraft aerodynamics and CFD validation

### AE01 - Aircraft Design: A Conceptual Approach, 6th ed.

- **Citation:** Raymer, D. P. (2018). *Aircraft Design: A Conceptual Approach, 6th ed.*. AIAA Education Series, doi:10.2514/4.104909.
- **Link:** [https://doi.org/10.2514/4.104909](https://doi.org/10.2514/4.104909)
- **Type:** book. **Used by:** WP M, D.
- **What it is:** Standard conceptual-design text: component drag build-up (form factors, interference factors, skin friction), statistical weights (incl. general-aviation equations), tail sizing by volume coefficients, Oswald efficiency estimates, cost models.
- **How we use it:** WP M/D: drag build-up equations (Cf, FF, Q), GA weight equations for wing/fuselage/tail, tail volume coefficients.
- **Credibility:** High; standard text.

### AE02 - General Aviation Aircraft Design: Applied Methods and Procedures, 2nd ed.

- **Citation:** Gudmundsson, S. (2022). *General Aviation Aircraft Design: Applied Methods and Procedures, 2nd ed.*. Butterworth-Heinemann (Elsevier), ISBN 978-0-12-818465-3.
- **Link:** [https://doi.org/10.1016/b978-0-12-818465-3.00001-x](https://doi.org/10.1016/b978-0-12-818465-3.00001-x)
- **Type:** book. **Used by:** WP M, P, D.
- **What it is:** GA-focused design text with detailed drag of small-aircraft components (landing gear, antennas, gaps), cost estimation for GA aircraft (Eastlake-type model), structural layout and composite construction.
- **How we use it:** WP M/P/D: drag of protuberances and gear; GA development/production cost model for the cost objective. (Link is Chapter 1 DOI.)
- **Credibility:** High; widely used GA design text.

### AE03 - Airplane Design, Parts I-VIII

- **Citation:** Roskam, J. (2017). *Airplane Design, Parts I-VIII*. DARcorporation, Lawrence KS (reprint editions).
- **Link:** [https://www.darcorp.com/](https://www.darcorp.com/)
- **Type:** book. **Used by:** WP M.
- **What it is:** Classic multi-volume design method: weight sizing, preliminary configuration, component weights (Cessna/USAF/Torenbeek methods), drag polar estimation.
- **How we use it:** WP M: alternative component weight equations for cross-checking Raymer.
- **Credibility:** High; classic text (publisher home page linked).

### AE04 - Fluid-Dynamic Drag: Practical Information on Aerodynamic Drag and Hydrodynamic Resistance

- **Citation:** Hoerner, S. F. (1965). *Fluid-Dynamic Drag: Practical Information on Aerodynamic Drag and Hydrodynamic Resistance*. Hoerner Fluid Dynamics, Bricktown NJ (self-published).
- **Link:** [https://openlibrary.org/search?q=hoerner+fluid-dynamic+drag](https://openlibrary.org/search?q=hoerner+fluid-dynamic+drag)
- **Type:** book. **Used by:** WP M, C.
- **What it is:** The empirical drag compendium: drag of bluff bodies, cylinders, struts, fairings, wheels, interference and excrescences.
- **How we use it:** WP M/C: drag coefficients of round booms, struts, motor pods, landing skids and stopped blades for the parasite-drag build-up.
- **Credibility:** High as an empirical reference; old data, check Reynolds-number range. Library record linked (book is not freely available).

### AE05 - Estimating the Oswald Factor from Basic Aircraft Geometrical Parameters

- **Citation:** Nita, M.; Scholz, D. (2012). *Estimating the Oswald Factor from Basic Aircraft Geometrical Parameters*. Deutscher Luft- und Raumfahrtkongress 2012, Document ID 281424.
- **Link:** [https://www.fzt.haw-hamburg.de/pers/Scholz/OPerA/OPerA_PUB_DLRK_12-09-10.pdf](https://www.fzt.haw-hamburg.de/pers/Scholz/OPerA/OPerA_PUB_DLRK_12-09-10.pdf)
- **Type:** paper (conference). **Used by:** WP M.
- **What it is:** Reviews Oswald-factor estimation methods and proposes one: a theoretical value from taper and sweep, corrected for fuselage, zero-lift drag and Mach effects using statistical data.
- **How we use it:** WP M: Oswald efficiency estimate for the high-wing with booms; to be cross-checked with AVL/VSPAERO span efficiency.
- **Credibility:** Medium-high: conference paper, widely cited, transparent method.

### AE06 - UIUC Airfoil Coordinates Database and Summary of Low-Speed Airfoil Data

- **Citation:** Selig, M. S. et al. (UIUC Applied Aerodynamics Group) (2026). *UIUC Airfoil Coordinates Database and Summary of Low-Speed Airfoil Data*. University of Illinois.
- **Link:** [https://m-selig.ae.illinois.edu/ads/coord_database.html](https://m-selig.ae.illinois.edu/ads/coord_database.html)
- **Type:** database (university). **Used by:** WP D, C, G.
- **What it is:** Coordinates for ~1,600 airfoils and the low-speed wind-tunnel data series.
- **How we use it:** WP D/C/G: airfoil geometry for the wing, tail and rotor blades; low-Re validation of NeuralFoil/XFOIL.
- **Credibility:** High (university test programme).

### AE07 - XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils

- **Citation:** Drela, M. (1989). *XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils*. Lecture Notes in Engineering 54, Springer, doi:10.1007/978-3-642-84010-4_1.
- **Link:** [https://web.mit.edu/drela/Public/web/xfoil/](https://web.mit.edu/drela/Public/web/xfoil/); [https://doi.org/10.1007/978-3-642-84010-4_1](https://doi.org/10.1007/978-3-642-84010-4_1)
- **Type:** paper (conference). **Used by:** WP C, M.
- **What it is:** Panel method with coupled integral boundary layer and e^N transition for airfoil polars.
- **How we use it:** WP C/M: airfoil polars (and the training reference for NeuralFoil).
- **Credibility:** High; standard tool, decades of validation.

### AE08 - NASA Turbulence Modeling Resource (TMR) - verification and validation cases

- **Citation:** Rumsey, C. L.; Smith, B. R.; Huang, G. P. (2010). *NASA Turbulence Modeling Resource (TMR) - verification and validation cases*. NASA Langley web site; described in AIAA 2010-4742, doi:10.2514/6.2010-4742.
- **Link:** [https://turbmodels.larc.nasa.gov/](https://turbmodels.larc.nasa.gov/); [https://doi.org/10.2514/6.2010-4742](https://doi.org/10.2514/6.2010-4742)
- **Type:** NASA web resource + paper. **Used by:** WP C, V.
- **What it is:** Reference definitions of RANS turbulence models and verification/validation cases (flat plate, NACA 0012, bump) with grids and reference results from CFL3D/FUN3D.
- **How we use it:** WP C/V: OpenFOAM/SU2 set-up verification (flat plate skin friction, NACA 0012 CL/CD vs alpha) before aircraft runs.
- **Credibility:** High (NASA). Note: the site did not answer automated checks from our network on 2026-11-12; the URL is the long-standing official address.

### AE09 - Retrospective on the Common Research Model for Computational Fluid Dynamics Validation Studies

- **Citation:** Vassberg, J. C.; DeHaan, M. A.; Rivers, S. M.; Wahls, R. A. (2018). *Retrospective on the Common Research Model for Computational Fluid Dynamics Validation Studies*. Journal of Aircraft 55(4), 1325-1337, doi:10.2514/1.C034906.
- **Link:** [https://doi.org/10.2514/1.C034906](https://doi.org/10.2514/1.C034906); [https://doi.org/10.2514/6.2008-6919](https://doi.org/10.2514/6.2008-6919)
- **Type:** paper (peer-reviewed). **Used by:** WP C, V.
- **What it is:** History and lessons of the NASA CRM and the AIAA Drag Prediction Workshops: grid convergence practice and the scatter of CFD drag predictions.
- **How we use it:** WP C/V: grid-convergence practice (Richardson extrapolation, grid families) and realistic expectations on CFD drag accuracy.
- **Credibility:** High; peer-reviewed. Transonic transport case, so used for practice, not numbers.

### AE10 - Summary of Airfoil Data (NACA Report 824)

- **Citation:** Abbott, I. H.; von Doenhoff, A. E.; Stivers, L. S. (1945). *Summary of Airfoil Data (NACA Report 824)*. NACA Report 824.
- **Link:** [https://ntrs.nasa.gov/citations/19930090976](https://ntrs.nasa.gov/citations/19930090976)
- **Type:** NACA report. **Used by:** WP C, V.
- **What it is:** Wind-tunnel section data for NACA 4-, 5- and 6-series airfoils.
- **How we use it:** WP C/V: experimental airfoil polars (e.g. NACA 0012, 23012, 63-series) for 2-D validation at Re ~3-9 million.
- **Credibility:** High (NACA test data); NTRS record verified (title 'Summary of Airfoil Data', 1945). A second NTRS record 19930092747 holds another scan.

## 5. Regulations, structures, loads, crashworthiness, recovery

### ST01 - 14 CFR Part 103 - Ultralight Vehicles (Sec. 103.1 Applicability)

- **Citation:** FAA (2024). *14 CFR Part 103 - Ultralight Vehicles (Sec. 103.1 Applicability)*. Code of Federal Regulations, 1-1-24 edition (govinfo); eCFR current.
- **Link:** [https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-103](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-103); [https://www.govinfo.gov/content/pkg/CFR-2024-title14-vol2/pdf/CFR-2024-title14-vol2-sec103-1.pdf](https://www.govinfo.gov/content/pkg/CFR-2024-title14-vol2/pdf/CFR-2024-title14-vol2-sec103-1.pdf)
- **Local copy:** [`papers/14CFR-103.1_2024.pdf`](papers/14CFR-103.1_2024.pdf)
- **Type:** regulation. **Used by:** WP D, V.
- **What it is:** Definition of an ultralight vehicle.
- **How we use it:** WP D/V: documents why Part 103 does not apply: our aircraft carries 2 occupants / 200 kg payload and has an empty mass far above 254 lb.
- **Key data:**
  - Single occupant; recreation/sport only; no airworthiness certificate
  - Powered: empty weight < 254 lb (excluding floats and safety devices for potentially catastrophic situations); fuel <= 5 US gal; <= 55 kt CAS at full power; power-off stall <= 24 kt CAS
- **Credibility:** High (law).

### ST02 - AC 21.17-4, Type Certification - Powered-lift

- **Citation:** FAA (AIR-600) (2025). *AC 21.17-4, Type Certification - Powered-lift*. FAA Advisory Circular, 18 July 2025.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_21.17-4.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_21.17-4.pdf)
- **Local copy:** [`papers/FAA_AC_21.17-4_2025.pdf`](papers/FAA_AC_21.17-4_2025.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP D, F, V.
- **What it is:** FAA's certification path for powered-lift under 14 CFR 21.17(b), with Appendix A airworthiness criteria (PL.xxxx) that are performance-based, derived from Part 23 amdt 64.
- **How we use it:** WP D/F/V: the US certification-basis reference for the design (structures PL.2200-2270, energy system PL.2430, occupant protection). We design to it as a standard even though a kit/experimental route is likely.
- **Key data:**
  - Applicability: powered-lift <= 12,500 lb max gross weight, <= 6 passenger seats, battery-powered electric engines driving propellers (Sec. 5.2)
  - PL.2230: limit loads = structural design loads; ultimate = limit x 1.5 unless otherwise provided (Appendix A)
  - PL.2270: emergency landing must include dynamic conditions; occupant loads within human-injury criteria; items of mass near cabin restrained (Appendix A)
  - PL.2430(a)(1): energy system independence so that failure of one component does not cause unacceptable loss of energy supply; (b)(2) energy storage isolated from occupant compartments
- **Credibility:** High (regulator).

### ST03 - Integration of Powered-Lift: Pilot Certification and Operations; Miscellaneous Amendments Related to Rotorcraft and Airplanes (SFAR No. 120)

- **Citation:** FAA (2024). *Integration of Powered-Lift: Pilot Certification and Operations; Miscellaneous Amendments Related to Rotorcraft and Airplanes (SFAR No. 120)*. Federal Register 89 FR 92296, 21 Nov 2024, Doc. 2024-24886, RIN 2120-AL72.
- **Link:** [https://www.federalregister.gov/documents/2024/11/21/2024-24886/integration-of-powered-lift-pilot-certification-and-operations-miscellaneous-amendments-related-to](https://www.federalregister.gov/documents/2024/11/21/2024-24886/integration-of-powered-lift-pilot-certification-and-operations-miscellaneous-amendments-related-to)
- **Type:** regulation (federal rule). **Used by:** WP V.
- **What it is:** Final rule creating SFAR 120 (14 CFR part 194) for powered-lift pilot certification and operations, valid 10 years, effective 21 Jan 2025.
- **How we use it:** WP V: operational and pilot-certification context for the requirements document; no design numbers.
- **Key data:**
  - SFAR valid for 10 years; effective 21 Jan 2025 (Federal Register summary)
- **Credibility:** High (law).

### ST04 - Special Condition SC-VTOL-01, Issue 1: Small-category VTOL aircraft

- **Citation:** EASA (2019). *Special Condition SC-VTOL-01, Issue 1: Small-category VTOL aircraft*. EASA, 2 July 2019.
- **Link:** [https://www.easa.europa.eu/en/downloads/99956/en](https://www.easa.europa.eu/en/downloads/99956/en); [https://www.easa.europa.eu/en/document-library/product-certification-consultations/special-condition-vtol](https://www.easa.europa.eu/en/document-library/product-certification-consultations/special-condition-vtol)
- **Type:** regulation (EASA special condition). **Used by:** WP D, F, V.
- **What it is:** EASA's airworthiness basis for person-carrying VTOL aircraft with distributed lift/thrust units; defines Category Basic (controlled emergency landing) and Category Enhanced (continued safe flight and landing).
- **How we use it:** WP D/F/V: certification basis reference (structures VTOL.2200-2270, lift/thrust system failure, energy storage VTOL.2430). The consultation page also lists the MOC documents (MOC-2 to MOC-5).
- **Key data:**
  - Applicability: passenger seating <= 9 and MTOM <= 3,175 kg (7,000 lb) (VTOL.2000)
  - Category Enhanced: continued safe flight and landing after a failure; Category Basic: controlled emergency landing (VTOL.2000)
  - VTOL.2230: ultimate load = limit load x 1.5 factor of safety unless otherwise provided
  - VTOL.2270: emergency landing dynamic conditions; occupant loads within human-injury criteria
- **Credibility:** High (regulator).

### ST05 - Airworthiness Criteria: Special Class Airworthiness Criteria for the Joby Aero, Inc. Model JAS4-1 Powered-Lift

- **Citation:** FAA (2024). *Airworthiness Criteria: Special Class Airworthiness Criteria for the Joby Aero, Inc. Model JAS4-1 Powered-Lift*. Federal Register 89 FR 17230, 8 Mar 2024, Doc. 2024-04690, Docket FAA-2021-0638.
- **Link:** [https://www.govinfo.gov/content/pkg/FR-2024-03-08/html/2024-04690.htm](https://www.govinfo.gov/content/pkg/FR-2024-03-08/html/2024-04690.htm)
- **Type:** regulation (airworthiness criteria). **Used by:** WP D, V, M.
- **What it is:** The first final FAA powered-lift airworthiness criteria for a specific eVTOL; precedent for AC 21.17-4 and source of the Joby MTOW figure.
- **How we use it:** WP D/V: worked example of a complete powered-lift certification basis; WP M benchmark number (Joby MTOW).
- **Key data:**
  - JAS4-1 maximum gross takeoff weight 4,800 lb, pilot + 4 passengers, VFR, parts 91/135 (background section)
  - Criteria based on part 23 amdt 23-64, part 33 amdt 33-34, part 35 amdt 35-10 plus powered-lift specific criteria
- **Credibility:** High (regulator).

### ST06 - 14 CFR 23.337 Limit maneuvering load factors (pre-Amendment 23-64 text, 1-1-16 edition)

- **Citation:** FAA (2016). *14 CFR 23.337 Limit maneuvering load factors (pre-Amendment 23-64 text, 1-1-16 edition)*. Code of Federal Regulations, 1-1-2016 edition (govinfo).
- **Link:** [https://www.govinfo.gov/content/pkg/CFR-2016-title14-vol1/pdf/CFR-2016-title14-vol1-sec23-337.pdf](https://www.govinfo.gov/content/pkg/CFR-2016-title14-vol1/pdf/CFR-2016-title14-vol1-sec23-337.pdf)
- **Local copy:** [`papers/14CFR-23.337_2016.pdf`](papers/14CFR-23.337_2016.pdf)
- **Type:** regulation. **Used by:** WP F, M.
- **What it is:** The prescriptive normal-category manoeuvre load factor formula that ASTM F3116 and our requirements (n = +3.8/-1.5) descend from; also contains the 23.341 gust load factor formula.
- **How we use it:** WP F/M: limit load factors and gust load factor formula (Pratt) for the V-n diagram.
- **Key data:**
  - Normal category positive limit n >= 2.1 + 24,000/(W + 10,000), W in lb, need not exceed 3.8 (23.337(a)(1))
  - Negative limit n >= 0.4 x positive for normal category (23.337(b)(1))
  - Gust: n = 1 + Kg Ude V a / (498 W/S), Kg = 0.88 mu_g/(5.3 + mu_g), mu_g = 2(W/S)/(rho C a g) (23.341(c))
- **Credibility:** High (law, historical edition). Superseded by performance-based Part 23 amdt 64 + ASTM F3116; numbers still the accepted means.

### ST07 - 14 CFR 23.562 Emergency landing dynamic conditions (1-1-16 edition)

- **Citation:** FAA (2016). *14 CFR 23.562 Emergency landing dynamic conditions (1-1-16 edition)*. Code of Federal Regulations, 1-1-2016 edition (govinfo).
- **Link:** [https://www.govinfo.gov/content/pkg/CFR-2016-title14-vol1/pdf/CFR-2016-title14-vol1-sec23-562.pdf](https://www.govinfo.gov/content/pkg/CFR-2016-title14-vol1/pdf/CFR-2016-title14-vol1-sec23-562.pdf); [https://www.ecfr.gov/current/title-14/section-27.562](https://www.ecfr.gov/current/title-14/section-27.562)
- **Local copy:** [`papers/14CFR-23.562_2016.pdf`](papers/14CFR-23.562_2016.pdf)
- **Type:** regulation. **Used by:** WP F, P.
- **What it is:** Dynamic seat test conditions and injury criteria for small aeroplanes (rotorcraft equivalent is 27.562).
- **How we use it:** WP F/P: energy-absorbing seat requirement (vertical 60 deg pitched test and longitudinal test), lumbar load and HIC limits for seat selection/design.
- **Key data:**
  - Test 1: dV >= 31 ft/s, 60 deg pitch, peak >= 19 g (first row) within 0.05 s
  - Test 2: dV >= 42 ft/s, 10 deg yaw, peak >= 26 g (first row) within 0.05 s
  - HIC <= 1,000; shoulder strap <= 1,750 lb (single) / 2,000 lb (dual); pelvis-lumbar compressive load <= 1,500 lb; 170 lb ATD (49 CFR 572 subpart B)
- **Credibility:** High (law, historical edition; carried into ASTM F3083 / AC 23.562-1 practice).

### ST08 - AC 23.562-1, Dynamic Testing of Part 23 Airplane Seat/Restraint Systems and Occupant Protection

- **Citation:** FAA (ACE-100) (1989). *AC 23.562-1, Dynamic Testing of Part 23 Airplane Seat/Restraint Systems and Occupant Protection*. FAA Advisory Circular, 22 June 1989.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_23_562-1.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_23_562-1.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP F, P.
- **What it is:** Acceptable means of compliance and test procedures for 23.562 dynamic seat tests.
- **How we use it:** WP F/P: seat and floor attachment design, test pulse shapes for the seat FEA load cases.
- **Credibility:** High (regulator guidance).

### ST09 - CS-23 Amendment 5 (and Amendment 4 for the prescriptive load formulas)

- **Citation:** EASA (2017). *CS-23 Amendment 5 (and Amendment 4 for the prescriptive load formulas)*. EASA Certification Specifications for Normal-Category Aeroplanes.
- **Link:** [https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-5](https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-5); [https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-4](https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-4)
- **Type:** regulation (EASA certification specification). **Used by:** WP F, V.
- **What it is:** Amendment 5 is the performance-based CS-23 whose AMC accepts ASTM consensus standards; Amendment 4 retains the prescriptive CS 23.337 load factors.
- **How we use it:** WP F/V: European normal-category reference; same load factor values as ST06.
- **Credibility:** High (regulator).

### ST10 - ASTM F3264, Standard Specification for Normal Category Aeroplanes Certification (and referenced F3116 design loads, F3114 structures)

- **Citation:** ASTM Committee F44 (2023). *ASTM F3264, Standard Specification for Normal Category Aeroplanes Certification (and referenced F3116 design loads, F3114 structures)*. ASTM International.
- **Link:** [https://store.astm.org/f3264-23.html](https://store.astm.org/f3264-23.html)
- **Type:** standard (paywalled). **Used by:** WP F, V.
- **What it is:** Umbrella standard listing which ASTM F44 standards satisfy each Part 23 amdt 64 requirement; F3116 holds the design load values (not held, so not quoted here).
- **How we use it:** WP F/V: compliance mapping for structural requirements. Not held (paywalled).
- **Credibility:** High (consensus standard) but not held; values in requirements.yaml are taken from ST06 until F3116 is purchased.

### ST11 - ASTM F2316-12, Standard Specification for Airframe Emergency Parachutes for Light Sport Aircraft

- **Citation:** ASTM Committee F37 (2012). *ASTM F2316-12, Standard Specification for Airframe Emergency Parachutes for Light Sport Aircraft*. ASTM International.
- **Link:** [https://store.astm.org/f2316-12.html](https://store.astm.org/f2316-12.html)
- **Type:** standard (paywalled). **Used by:** WP P, F.
- **What it is:** Design and test standard for whole-airframe emergency parachutes; cited by Galaxy GRS for its 1.5 safety coefficient.
- **How we use it:** WP P/F: parachute selection and hard-point load requirement.
- **Credibility:** High (standard), not held.

### ST12 - Galaxy GRS 6/800-990 SDS (175 m2) whole-aircraft rescue system - product data

- **Citation:** Galaxy Holding s.r.o. (2026). *Galaxy GRS 6/800-990 SDS (175 m2) whole-aircraft rescue system - product data*. Manufacturer product page.
- **Link:** [https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en](https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en); [https://galaxysky.cz/grs-6-750-sds-ff-140m2-p42-en](https://galaxysky.cz/grs-6-750-sds-ff-140m2-p42-en)
- **Type:** datasheet. **Used by:** WP P, D, F.
- **What it is:** Ballistic rescue parachute family covering 650-1,050 kg aircraft, with total system mass, canopy area, maximum deployment speed, descent rate and opening shock.
- **How we use it:** WP P/D/F: parachute mass in the weight statement; opening shock for the parachute hard-point FEA.
- **Key data:**
  - GRS 6/800-990 SDS: MTOW variants 800 / 900 / 1,050 kg; total weight 21.7 kg (Soft B2 pack) +/-4%; canopy 175 m2
  - Max deployment speed 380 / 350 / 315 km/h; opening shock 46.0 / 45.5 / 47.4 kN at Vne and MTOW; descent 7.1-7.9 m/s at 1,000 m AMSL
  - GRS 6/750 SDS: MTOW 650/700/750 kg variants, 14.8 kg, 140 m2, opening shock 28.8 kN at MTOW (search summary of manufacturer page)
  - Designed to ASTM F2316-12 with total safety coefficient 1.5
- **Credibility:** Medium-high: manufacturer data; pages for the same product show some internal inconsistencies (title range 800-990 kg vs table 800/900/1,050 kg).

### ST13 - BRS Aerospace whole-aircraft recovery parachute systems (BRS-6 family)

- **Citation:** BRS Aerospace (2026). *BRS Aerospace whole-aircraft recovery parachute systems (BRS-6 family)*. Manufacturer web site.
- **Link:** [https://brsaerospace.com/](https://brsaerospace.com/)
- **Type:** manufacturer web page. **Used by:** WP P.
- **What it is:** Manufacturer of certified (Cirrus, Cessna 172/182 retrofit) and experimental/LSA whole-aircraft parachutes; BRS-6 models 600-1800 (lb ratings).
- **How we use it:** WP P: second supplier option; ratings and masses must be obtained from the BRS-6 owner's manual or a quote (not retrieved).
- **Credibility:** Medium: manufacturer site; no numbers taken.

### ST14 - MIL-HDBK-5J, Metallic Materials and Elements for Aerospace Vehicle Structures

- **Citation:** US Department of Defense (2003). *MIL-HDBK-5J, Metallic Materials and Elements for Aerospace Vehicle Structures*. MIL-HDBK-5J (superseded by MMPDS, distribution A).
- **Link:** [https://www.everyspec.com/MIL-HDBK/MIL-HDBK-0001-0099/MIL_HDBK_5J_139/](https://www.everyspec.com/MIL-HDBK/MIL-HDBK-0001-0099/MIL_HDBK_5J_139/)
- **Type:** handbook (public domain). **Used by:** WP F, P.
- **What it is:** A- and B-basis design allowables for aluminium (2024, 6061, 7075...), steel (4130) and fastener/joint data.
- **How we use it:** WP F/P: allowables for 6061-T6/7075-T6 extrusions and sheet, 4130 tube and rivet/bolt joints.
- **Credibility:** High; last public edition (MMPDS is the paid successor, values largely unchanged for common alloys).

### ST15 - Composite Materials Handbook CMH-17 (formerly MIL-HDBK-17)

- **Citation:** CMH-17 Organization / SAE International (2026). *Composite Materials Handbook CMH-17 (formerly MIL-HDBK-17)*. CMH-17 Rev. H.
- **Link:** [https://www.cmh17.org/](https://www.cmh17.org/)
- **Type:** handbook (paywalled) / organisation. **Used by:** WP F, P, V.
- **What it is:** Statistically-based composite allowables, test methods, building-block approach and design guidance, including wet-layup and sandwich structures.
- **How we use it:** WP F/P: B-basis knockdown philosophy and environmental factors for wet-layup laminates; building-block test plan for V&V.
- **Credibility:** High; not held (paid).

### ST16 - AC 20-107B (with Change 1), Composite Aircraft Structure

- **Citation:** FAA (2010). *AC 20-107B (with Change 1), Composite Aircraft Structure*. FAA Advisory Circular.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-107B_with_change_1.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-107B_with_change_1.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP F, P, V.
- **What it is:** FAA guidance on substantiating composite structure: material and process control, allowables, damage tolerance, environmental effects, bonded joints.
- **How we use it:** WP F/P/V: knock-downs (environment, damage) and process-control expectations for wet-layup parts.
- **Credibility:** High (regulator).

### ST17 - Design, Fabrication, and Testing of Composite Energy-Absorbing Keel Beams for General Aviation Type Aircraft

- **Citation:** Kellas, S.; Knight, N. F., Jr. (2002). *Design, Fabrication, and Testing of Composite Energy-Absorbing Keel Beams for General Aviation Type Aircraft*. NASA CR (NTRS 20030004235).
- **Link:** [https://ntrs.nasa.gov/citations/20030004235](https://ntrs.nasa.gov/citations/20030004235)
- **Type:** NASA contractor report. **Used by:** WP F, P.
- **What it is:** Design and test of composite crush structures for GA fuselages.
- **How we use it:** WP F/P: sub-floor energy absorber concept under the seats.
- **Credibility:** High (NASA).

### ST18 - EASA TCDS EASA.A.573, Virus SW 121 (incl. Section B: Virus SW 128 Velis Electro), Issue 13

- **Citation:** EASA (2025). *EASA TCDS EASA.A.573, Virus SW 121 (incl. Section B: Virus SW 128 Velis Electro), Issue 13*. EASA, 19 Nov 2025.
- **Link:** [https://www.easa.europa.eu/en/downloads/20704/en](https://www.easa.europa.eu/en/downloads/20704/en)
- **Type:** regulation (EASA type certificate data sheet). **Used by:** WP M, V.
- **What it is:** Type certificate data sheet of the only type-certificated electric aeroplane; gives masses, wing, motor, propeller, battery and load factors.
- **How we use it:** WP M: primary-source benchmark for an electric 2-seat aircraft at 600 kg; certification basis example (CS-LSA + special conditions for lithium propulsion batteries).
- **Key data:**
  - SW 128: MTOW 600 kg; span 10.70 m; wing area 9.51 m2; load factors +4 g / -2 g
  - Engine E-811/268MVLC: MTOP 57.6 kW / 2,500 rpm (max 90 s); MCP 49.2 kW / 2,350 rpm
  - Propeller P-812/164-F3A: 3 blades, 1,640 mm, fixed pitch, 4.88 kg
  - ESS: two lithium batteries in parallel, PB345V124E-L 11.0 kWh each (or PB345V119E-L 10.0 kWh each), 345 V nominal, liquid cooled
  - VNE 108 KIAS; certification basis CS-LSA Amdt 1 + SC-LSA-F2480-01, SC-LSA-15-01, SC-ELA.2015-01 (lithium battery installations)
- **Credibility:** High (regulator).

## 6. Materials and manufacturing

### MF01 - AC 43.13-1B (Change 1), Acceptable Methods, Techniques, and Practices - Aircraft Inspection and Repair

- **Citation:** FAA (1998). *AC 43.13-1B (Change 1), Acceptable Methods, Techniques, and Practices - Aircraft Inspection and Repair*. FAA Advisory Circular.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43.13-1B_w-chg1.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43.13-1B_w-chg1.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP P, G.
- **What it is:** The workshop bible for light aircraft: rivet and bolt practice, edge distances, sheet-metal repairs, welding, composite (fibreglass/carbon) repair and wet lay-up practices, hardware tables.
- **How we use it:** WP P/G: rivet pitch/edge distance, bolt torque, fastener selection for aluminium parts; wet lay-up practices.
- **Credibility:** High (regulator guidance).

### MF02 - AC 20-27G, Certification and Operation of Amateur-Built Aircraft

- **Citation:** FAA (2009). *AC 20-27G, Certification and Operation of Amateur-Built Aircraft*. FAA Advisory Circular.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-27G.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-27G.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP V, P.
- **What it is:** Experimental amateur-built certification process (major portion rule, documentation).
- **How we use it:** WP V/P: realistic first-flight route for an in-house built prototype.
- **Credibility:** High (regulator guidance).

### MF03 - AC 90-89C, Amateur-Built Aircraft and Ultralight Flight Testing Handbook

- **Citation:** FAA (2015). *AC 90-89C, Amateur-Built Aircraft and Ultralight Flight Testing Handbook*. FAA Advisory Circular.
- **Link:** [https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_90-89C.pdf](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_90-89C.pdf)
- **Type:** regulation (FAA advisory circular). **Used by:** WP V.
- **What it is:** Phase I flight-test programme guidance for experimental aircraft.
- **How we use it:** WP V: flight test plan structure.
- **Credibility:** High.

### MF04 - Toray TORAYCA T700S carbon fibre technical data sheet

- **Citation:** Toray Composite Materials America (2025). *Toray TORAYCA T700S carbon fibre technical data sheet*. Manufacturer data sheet.
- **Link:** [https://www.toraycma.com/wp-content/uploads/T700S-Data-Sheet.pdf](https://www.toraycma.com/wp-content/uploads/T700S-Data-Sheet.pdf)
- **Type:** datasheet. **Used by:** WP F, P.
- **What it is:** Fibre and unidirectional composite properties for T700S, the fibre used in most COTS pultruded and roll-wrapped carbon tubes.
- **How we use it:** WP F/P: upper-bound laminate properties; knock down for wet layup (lower Vf) and tube manufacturing route.
- **Key data:**
  - Fibre: 4,900 MPa tensile strength, 230 GPa modulus, 2.1% strain, 1.80 g/cm3, 7 um
  - UD composite (60% Vf, epoxy): 2,860 MPa / 134 GPa tension (D3039), 1,450 MPa compression, 1,690 MPa flexural, ILSS 86.9 MPa
- **Credibility:** High (manufacturer), but properties are lot averages at 60% Vf, 'not for specification'.

### MF05 - Diab Divinycell H PVC foam core - product page and data sheet

- **Citation:** Diab Group (2026). *Diab Divinycell H PVC foam core - product page and data sheet*. Manufacturer web page.
- **Link:** [https://www.diabgroup.com/products-services/divinycell-pvc/divinycell-h/](https://www.diabgroup.com/products-services/divinycell-pvc/divinycell-h/)
- **Type:** manufacturer product page. **Used by:** WP F, P.
- **What it is:** Cross-linked PVC foam core grades (H45-H250) with shear/compression properties for sandwich panels.
- **How we use it:** WP F/P: core properties for sandwich skins, floors and wing ribs (foam-core construction).
- **Credibility:** High (manufacturer).

### MF06 - Hexcel honeycomb data sheets and sandwich design technology

- **Citation:** Hexcel Corporation (2026). *Hexcel honeycomb data sheets and sandwich design technology*. Manufacturer data sheet library.
- **Link:** [https://www.hexcel.com/Resources/DataSheets/Honeycomb](https://www.hexcel.com/Resources/DataSheets/Honeycomb)
- **Type:** manufacturer technical library. **Used by:** WP F.
- **What it is:** Honeycomb core data and Hexcel's sandwich design guide (face wrinkling, core shear, intra-cell buckling formulas).
- **How we use it:** WP F: sandwich failure-mode checks.
- **Credibility:** High (manufacturer).

### MF07 - WEST SYSTEM instruction manuals (incl. Vacuum Bagging Techniques)

- **Citation:** Gougeon Brothers, Inc. (2026). *WEST SYSTEM instruction manuals (incl. Vacuum Bagging Techniques)*. Manufacturer manuals.
- **Link:** [https://www.westsystem.com/instruction-manuals/](https://www.westsystem.com/instruction-manuals/)
- **Type:** manufacturer manuals. **Used by:** WP P.
- **What it is:** Practical epoxy wet-layup and vacuum-bagging procedures (bagging materials, pressure, bleed, cure).
- **How we use it:** WP P: process sheets for wet-layup/vacuum-bag parts in manufacturing/MANUFACTURING.md.
- **Credibility:** Medium-high: reputable resin manufacturer, practical guidance not test data.

### MF08 - NCAMP - National Center for Advanced Materials Performance (Wichita State NIAR)

- **Citation:** NIAR / Wichita State University (2026). *NCAMP - National Center for Advanced Materials Performance (Wichita State NIAR)*. Public material qualification programme.
- **Link:** [https://www.wichita.edu/industry_and_defense/NIAR/Research/ncamp.php](https://www.wichita.edu/industry_and_defense/NIAR/Research/ncamp.php)
- **Type:** organisation (public allowables). **Used by:** WP F.
- **What it is:** Publicly released, FAA-accepted statistically based allowables for composite material systems and the shared-database process.
- **How we use it:** WP F: source of B-basis allowables and knock-down ratios to compare with wet-layup estimates.
- **Credibility:** High (FAA-recognised programme); mostly prepreg systems, so only indicative for wet layup.

### MF09 - Van's Aircraft kit aircraft (e.g. RV-12iS) - aluminium kit construction reference

- **Citation:** Van's Aircraft, Inc. (2026). *Van's Aircraft kit aircraft (e.g. RV-12iS) - aluminium kit construction reference*. Manufacturer web site.
- **Link:** [https://www.vansaircraft.com/rv-12is/](https://www.vansaircraft.com/rv-12is/)
- **Type:** manufacturer web site. **Used by:** WP P, G.
- **What it is:** Matched-hole, pre-punched aluminium kit construction with pulled rivets; reference for low-tooling aluminium structures and builder hours.
- **How we use it:** WP P/G: design-for-assembly reference for flat-pattern aluminium parts (booms fittings, cabin frame).
- **Credibility:** Medium: manufacturer marketing; construction practice is well established.

### MF10 - EAA aircraft building resources (composite, metal, wood construction guides)

- **Citation:** Experimental Aircraft Association (2026). *EAA aircraft building resources (composite, metal, wood construction guides)*. EAA web site.
- **Link:** [https://www.eaa.org/eaa/aircraft-building](https://www.eaa.org/eaa/aircraft-building)
- **Type:** organisation (homebuilder resources). **Used by:** WP P.
- **What it is:** Homebuilder guidance including moldless foam-core composite construction (Rutan-style) and sheet-metal techniques.
- **How we use it:** WP P: practical build methods; low credibility for numbers.
- **Credibility:** Medium: community resource.

## 7. Benchmark aircraft data sources

### BM01 - Electric VTOL News (Vertical Flight Society) aircraft directory - individual aircraft pages

- **Citation:** Vertical Flight Society (2026). *Electric VTOL News (Vertical Flight Society) aircraft directory - individual aircraft pages*. evtol.news directory (pages listed in benchmarks_raw.json).
- **Link:** [https://evtol.news/](https://evtol.news/)
- **Type:** directory (secondary). **Used by:** WP M.
- **What it is:** Curated VFS directory that compiles manufacturer-announced specifications for >1,000 eVTOL concepts.
- **How we use it:** WP M: main source for benchmark specs when no regulator or manufacturer document gives the number.
- **Credibility:** Medium: secondary compilation of manufacturer claims; some typos (e.g. Lilium MTOW in 'km', Wisk MTOW labelled as payload). Each number is tagged with the exact page URL in benchmarks_raw.json.

### BM02 - EHang EH216-S product page

- **Citation:** EHang (2026). *EHang EH216-S product page*. Manufacturer web page.
- **Link:** [https://www.ehang.com/ehang216s/](https://www.ehang.com/ehang216s/)
- **Type:** manufacturer web page. **Used by:** WP M.
- **What it is:** Official EH216-S specifications.
- **How we use it:** WP M: EH216-S MTOW, speed, range.
- **Key data:**
  - MTOW 620 kg; max design speed 130 km/h; range 30 km; width 5.73 m; height 1.93 m; coaxial dual-rotor layout
- **Credibility:** Medium-high (manufacturer; aircraft is CAAC type-certificated, Oct 2023).

### BM03 - Pipistrel Velis Electro product page

- **Citation:** Pipistrel (Textron eAviation) (2026). *Pipistrel Velis Electro product page*. Manufacturer web page.
- **Link:** [https://www.pipistrel-aircraft.com/products/velis-electro/](https://www.pipistrel-aircraft.com/products/velis-electro/)
- **Type:** manufacturer web page. **Used by:** WP M.
- **What it is:** Manufacturer performance data for the Velis Electro.
- **How we use it:** WP M: empty mass, cruise power/speed and endurance (complements ST18).
- **Key data:**
  - Empty 428 kg typical with batteries; MTOW 600 kg; useful load 172 kg
  - Cruise 88 KTAS at 35 kW; endurance ~50 min typical (+ VFR reserve)
- **Credibility:** Medium-high (manufacturer).

### BM04 - Archer Unveils its Production Aircraft, Midnight (16 Nov 2022)

- **Citation:** Archer Aviation (2022). *Archer Unveils its Production Aircraft, Midnight (16 Nov 2022)*. Press release (investor site PDF).
- **Link:** [https://s206.q4cdn.com/823642595/files/doc_news/Archer-Unveils-its-Production-Aircraft-Midnight-2022.pdf](https://s206.q4cdn.com/823642595/files/doc_news/Archer-Unveils-its-Production-Aircraft-Midnight-2022.pdf); [https://www.businesswire.com/news/home/20221116006108/en](https://www.businesswire.com/news/home/20221116006108/en)
- **Type:** manufacturer press release. **Used by:** WP M.
- **What it is:** Archer's production-aircraft announcement.
- **How we use it:** WP M: Midnight payload and rotor count.
- **Key data:**
  - Pilot + 4 passengers; expected payload over 1,000 lb; optimised for back-to-back ~20-mile trips; 12 propellers (6 tilt, 6 lift)
- **Credibility:** Medium (manufacturer claims, 'expected').

### BM05 - Update: Archer's Midnight eVTOL Completes First Transition Flight

- **Citation:** AVweb (2024). *Update: Archer's Midnight eVTOL Completes First Transition Flight*. AVweb news.
- **Link:** [https://www.avweb.com/aviation-news/archers-midnight-evtol-completes-first-transition-flight/](https://www.avweb.com/aviation-news/archers-midnight-evtol-completes-first-transition-flight/)
- **Type:** trade press. **Used by:** WP M.
- **What it is:** News report quoting Archer's design MTOW.
- **How we use it:** WP M: Midnight MTOW.
- **Key data:**
  - Design maximum takeoff weight about 6,500 lb (as reported)
- **Credibility:** Medium-low: trade press; directory sites quote 7,000 lb instead.

### BM06 - Wisk - Generation 6 aircraft page

- **Citation:** Wisk Aero (2026). *Wisk - Generation 6 aircraft page*. Manufacturer web page.
- **Link:** [https://wisk.aero/aircraft/](https://wisk.aero/aircraft/)
- **Type:** manufacturer web page. **Used by:** WP M.
- **What it is:** Official Gen 6 performance summary.
- **How we use it:** WP M: Wisk range, speed, seats.
- **Key data:**
  - 4 passengers with carry-on luggage; 90 miles with reserves; ~120 kt cruise; 2,500+ ft cruise altitude; ~15 min charge
- **Credibility:** Medium (manufacturer, pre-certification).

### BM07 - NAVAIR Office of Small Business Programs - LIFT Aircraft company profile

- **Citation:** US Navy NAVAIR (2023). *NAVAIR Office of Small Business Programs - LIFT Aircraft company profile*. Company profile.
- **Link:** [https://www.navair.navy.mil/osbp/node/10826](https://www.navair.navy.mil/osbp/node/10826)
- **Type:** government web page. **Used by:** WP M.
- **What it is:** Company-supplied profile of LIFT Aircraft hosted by NAVAIR.
- **How we use it:** WP M: Hexa battery mass and useful load.
- **Key data:**
  - HEXA empty weight 432 lb including ~133 lb of batteries; useful load 220 lb; range 10 nm; ~18 min operating time
- **Credibility:** Medium: company-supplied text on a government site.

### BM08 - Vertical reveals second eVTOL prototype ahead of flight testing (AIN FutureFlight, 18 Jul 2024)

- **Citation:** AIN (2024). *Vertical reveals second eVTOL prototype ahead of flight testing (AIN FutureFlight, 18 Jul 2024)*. AIN Online.
- **Link:** [https://www.ainonline.com/aviation-news/futureflight/2024-07-18/vertical-reveals-second-evtol-prototype-ahead-flight-testing](https://www.ainonline.com/aviation-news/futureflight/2024-07-18/vertical-reveals-second-evtol-prototype-ahead-flight-testing)
- **Type:** trade press. **Used by:** WP M.
- **What it is:** Trade report on the VX4 prototype.
- **How we use it:** WP M: confirms VX4 MTOW is not publicly disclosed.
- **Key data:**
  - VX4 MTOW not disclosed by Vertical (as reported)
- **Credibility:** Medium (trade press).

## 8. Open-source tools

### TL01 - OpenFOAM v2412 (ESI/OpenCFD) release and documentation

- **Citation:** OpenCFD Ltd (2024). *OpenFOAM v2412 (ESI/OpenCFD) release and documentation*. openfoam.com.
- **Link:** [https://www.openfoam.com/news/main-news/openfoam-v2412](https://www.openfoam.com/news/main-news/openfoam-v2412); [https://www.openfoam.com/](https://www.openfoam.com/)
- **Type:** tool doc. **Used by:** WP C.
- **What it is:** Finite-volume CFD toolbox installed in ~/tools/envs/cfd; simpleFoam/pimpleFoam, actuator-disk and MRF/AMI rotor options, snappyHexMesh.
- **How we use it:** WP C: main RANS solver for the airframe, with actuator-disk lift rotors; verification against AE08 cases.
- **Credibility:** High (widely validated open-source code).

### TL02 - SU2: An Open-Source Suite for Multiphysics Simulation and Design

- **Citation:** Economon, T. D.; Palacios, F.; Copeland, S. R.; Lukaczyk, T. W.; Alonso, J. J. (2016). *SU2: An Open-Source Suite for Multiphysics Simulation and Design*. AIAA Journal 54(3), 828-846, doi:10.2514/1.J053813.
- **Link:** [https://su2code.github.io/](https://su2code.github.io/); [https://github.com/su2code/SU2](https://github.com/su2code/SU2); [https://doi.org/10.2514/1.J053813](https://doi.org/10.2514/1.J053813)
- **Type:** tool doc + paper. **Used by:** WP C, V.
- **What it is:** Open-source compressible/incompressible RANS solver with adjoint capability.
- **How we use it:** WP C/V: independent second CFD code for cross-checking OpenFOAM drag.
- **Credibility:** High.

### TL03 - AeroSandbox (Python aircraft design optimisation library)

- **Citation:** Sharpe, P. D. (2026). *AeroSandbox (Python aircraft design optimisation library)*. GitHub / ReadTheDocs.
- **Link:** [https://github.com/peterdsharpe/AeroSandbox](https://github.com/peterdsharpe/AeroSandbox); [https://aerosandbox.readthedocs.io/](https://aerosandbox.readthedocs.io/)
- **Type:** tool doc. **Used by:** WP D, C.
- **What it is:** Differentiable aircraft design framework with vortex-lattice, lifting-line, drag build-up, propulsion and mission tools (installed in ~/tools/cadenv).
- **How we use it:** WP D: optimisation framework for sizing; WP C: quick VLM checks.
- **Credibility:** Medium-high: MIT-developed, well documented; not an industry-validated code.

### TL04 - NeuralFoil: An Airfoil Aerodynamics Analysis Tool Using Physics-Informed Machine Learning

- **Citation:** Sharpe, P.; Hansman, R. J. (2025). *NeuralFoil: An Airfoil Aerodynamics Analysis Tool Using Physics-Informed Machine Learning*. arXiv:2503.16323.
- **Link:** [https://arxiv.org/abs/2503.16323](https://arxiv.org/abs/2503.16323); [https://github.com/peterdsharpe/NeuralFoil](https://github.com/peterdsharpe/NeuralFoil)
- **Type:** paper (preprint) + tool. **Used by:** WP D, C.
- **What it is:** Neural-network surrogate trained on XFOIL data that returns airfoil polars with uncertainty estimates.
- **How we use it:** WP D/C: fast airfoil polars inside the optimiser; validated against XFOIL/UIUC data (AE06, AE07).
- **Credibility:** Medium: preprint; accuracy bounded by XFOIL training data.

### TL05 - AVL (Athena Vortex Lattice)

- **Citation:** Drela, M.; Youngren, H. (2022). *AVL (Athena Vortex Lattice)*. MIT.
- **Link:** [https://web.mit.edu/drela/Public/web/avl/](https://web.mit.edu/drela/Public/web/avl/)
- **Type:** tool doc. **Used by:** WP M, C, D.
- **What it is:** Vortex-lattice code for lift distribution, span efficiency, stability derivatives and trim.
- **How we use it:** WP M/C/D: span efficiency, neutral point, tail sizing and control derivatives.
- **Credibility:** High (widely used).

### TL06 - OpenVSP and VSPAERO

- **Citation:** NASA / OpenVSP community (2026). *OpenVSP and VSPAERO*. openvsp.org.
- **Link:** [https://openvsp.org/](https://openvsp.org/); [https://github.com/OpenVSP/OpenVSP](https://github.com/OpenVSP/OpenVSP); [https://openvsp.org/wiki/doku.php?id=vspaerotutorial](https://openvsp.org/wiki/doku.php?id=vspaerotutorial)
- **Type:** tool doc. **Used by:** WP G, M, C.
- **What it is:** NASA parametric geometry tool with wetted-area, parasite-drag build-up and the VSPAERO VLM/panel solver with actuator disks.
- **How we use it:** WP G/M/C: wetted areas for the drag build-up and a quick rotor-wing interaction estimate.
- **Credibility:** High (NASA-originated).

### TL07 - DUST - mid-fidelity vortex-particle aerodynamic solver (Politecnico di Milano)

- **Citation:** Politecnico di Milano DAER (2026). *DUST - mid-fidelity vortex-particle aerodynamic solver (Politecnico di Milano)*. GitLab repository.
- **Link:** [https://public.gitlab.polimi.it/DAER/dust](https://public.gitlab.polimi.it/DAER/dust)
- **Type:** tool doc. **Used by:** WP C.
- **What it is:** Open-source mid-fidelity solver (panels/lifting lines + vortex particle wake) for rotorcraft and interacting rotor/wing configurations.
- **How we use it:** WP C: transition and rotor-boom-wing interaction where RANS is too costly; validated in RA14.
- **Credibility:** Medium-high: research code with journal validation. Host was intermittently unreachable during the check on 2026-11-12.

### TL08 - CalculiX CrunchiX 2.23 user's manual

- **Citation:** Dhondt, G. (2025). *CalculiX CrunchiX 2.23 user's manual*. calculix.de / dhondt.de.
- **Link:** [https://www.dhondt.de/ccx_2.23.pdf](https://www.dhondt.de/ccx_2.23.pdf); [http://www.calculix.de/](http://www.calculix.de/)
- **Type:** tool doc. **Used by:** WP F.
- **What it is:** Open-source implicit FE solver (Abaqus-like input), shells, composites, buckling, modal.
- **How we use it:** WP F: structural FEA of the wing spar, booms, fittings and seat structure.
- **Credibility:** High (mature open-source FE code).

### TL09 - Gmsh: a 3-D finite element mesh generator with built-in pre- and post-processing facilities

- **Citation:** Geuzaine, C.; Remacle, J.-F. (2009). *Gmsh: a 3-D finite element mesh generator with built-in pre- and post-processing facilities*. Int. J. Numer. Meth. Eng. 79(11), 1309-1331, doi:10.1002/nme.2579.
- **Link:** [https://gmsh.info/](https://gmsh.info/); [https://doi.org/10.1002/nme.2579](https://doi.org/10.1002/nme.2579)
- **Type:** tool doc + paper. **Used by:** WP F, C.
- **What it is:** Mesh generator with OpenCASCADE geometry kernel and Python API.
- **How we use it:** WP F/C: FE and CFD meshing from STEP.
- **Credibility:** High.

### TL10 - build123d (Python CAD on OpenCASCADE) and FreeCAD

- **Citation:** build123d contributors; FreeCAD project (2026). *build123d (Python CAD on OpenCASCADE) and FreeCAD*. ReadTheDocs / freecad.org.
- **Link:** [https://build123d.readthedocs.io/en/latest/](https://build123d.readthedocs.io/en/latest/); [https://github.com/gumyr/build123d](https://github.com/gumyr/build123d); [https://www.freecad.org/](https://www.freecad.org/)
- **Type:** tool doc. **Used by:** WP G.
- **What it is:** Code-based parametric CAD producing STEP/STL; FreeCAD as interactive viewer/editor.
- **How we use it:** WP G: all parts and the assembly built from design/geometry.json.
- **Credibility:** Medium-high: active open-source projects.

### TL11 - SUAVE / RCAIDE: open-source conceptual vehicle design environments

- **Citation:** Lukaczyk, T. W.; Wendorff, A. D.; Colonno, M.; Economon, T. D.; Alonso, J. J. (2015). *SUAVE / RCAIDE: open-source conceptual vehicle design environments*. AIAA 2015-3087, doi:10.2514/6.2015-3087.
- **Link:** [https://github.com/suavecode/SUAVE](https://github.com/suavecode/SUAVE); [https://suave.stanford.edu/](https://suave.stanford.edu/); [https://github.com/leadsgroup/RCAIDE_LEADS](https://github.com/leadsgroup/RCAIDE_LEADS); [https://doi.org/10.2514/6.2015-3087](https://doi.org/10.2514/6.2015-3087)
- **Type:** tool doc + paper. **Used by:** WP V, D.
- **What it is:** Stanford conceptual design environment with eVTOL (lift+cruise) examples, battery and propeller models; RCAIDE is its maintained successor.
- **How we use it:** WP V: independent mission-energy cross-check of the sizing result using a third-party code.
- **Credibility:** Medium-high: academic code, published validation.

### TL12 - OpenMDAO: an open-source framework for multidisciplinary design, analysis, and optimization

- **Citation:** Gray, J. S.; Hwang, J. T.; Martins, J. R. R. A.; Moore, K. T.; Naylor, B. A. (2019). *OpenMDAO: an open-source framework for multidisciplinary design, analysis, and optimization*. Structural and Multidisciplinary Optimization 59, doi:10.1007/s00158-019-02211-z.
- **Link:** [https://openmdao.org/](https://openmdao.org/); [https://github.com/OpenMDAO/OpenMDAO](https://github.com/OpenMDAO/OpenMDAO)
- **Type:** tool doc + paper. **Used by:** WP D.
- **What it is:** NASA Glenn MDO framework with analytic derivatives and many optimisers.
- **How we use it:** WP D: optional optimiser wrapper if the sizing outgrows AeroSandbox.
- **Credibility:** High (NASA, peer-reviewed).

### TL13 - NDARC software page (NASA Ames)

- **Citation:** NASA Ames Aeromechanics Office (2026). *NDARC software page (NASA Ames)*. rotorcraft.arc.nasa.gov.
- **Link:** [https://rotorcraft.arc.nasa.gov/ndarc/](https://rotorcraft.arc.nasa.gov/ndarc/)
- **Type:** tool doc. **Used by:** WP M.
- **What it is:** Distribution page for NDARC (export-controlled software; theory manuals public).
- **How we use it:** WP M: reference only; we implement the published equations ourselves.
- **Credibility:** High.

## Benchmark aircraft summary

Values as published (see `benchmarks_raw.json` for the source ID and URL of each number, and for notes). '-' = not found in any source checked. Masses in kg (converted from lb where the source gives lb).

| Aircraft | Class | MTOW kg | Empty kg | Payload kg | Battery kWh | Lift/prop rotors | Span / width | Cruise | Range |
|---|---|---|---|---|---|---|---|---|---|
| Jetson ONE (production model) | single-seat multicopter (Part 103 intent) | 210 | 115 | 95 | - | 8 | - | 102 km/h | - |
| Opener BlackFly v3 | single-seat tandem-wing tilt-body | 255 | 142 | 113 | - | 8 | 4.1 m | 62 mph | 40 mi |
| Pivotal Helix (production model) | single-seat tandem-wing tilt-body | 258 | 158 | 100 | 8 | 8 | - | 63 mph | 20 mi |
| LIFT Aircraft HEXA | single-seat multicopter (Part 103 with safety-device allowance) | - | 196 | 113 | - | 18 | - | 45 mph | 10 nmi |
| Volocopter 2X | 2-seat multicopter | 450 | 290 | 160 | - | 18 | 9.15 m | 102 km/h | 27 km |
| Volocopter VoloCity | 2-seat multicopter | 900 | 700 | 200 | - | 18 | 11.3 m | 90 km/h | 35-65 km |
| EHang EH216-S | 2-seat autonomous coaxial multicopter | 620 | - | 220 | 17 | 16 | 5.73 m | 100 km/h | 30 km |
| Kitty Hawk / Wisk Cora | 2-seat autonomous lift+cruise (12 lift rotors + pusher) | - | - | 181 | - | 13 | 11 m | 180 km/h | 100 km |
| Wisk Generation 6 | 4-seat autonomous lift+cruise with tilting front rotors | 2449 | - | 408 | - | 12 | - | 120 kt | 90 mi |
| Kitty Hawk Heaviside | single-seat tilt-rotor | - | - | - | - | 8 | 6 m | 354 km/h | 100 mi |
| Airbus A3 Vahana Alpha One | single-seat (uncrewed demonstrator) tandem tilt-wing | 816 | 476 | 91 | - | 8 | 6.25 m | 200 km/h | 60 km |
| Airbus CityAirbus NextGen | 4-seat lift+cruise (6 lift + 2 pusher props) | - | - | - | - | 8 | 12 m (unverified) | 120 km/h | 80 km |
| BETA Technologies ALIA A250 | 5-6 seat lift+cruise (4 lift + 1 pusher) | 3175 | - | - | - | 5 | 15 m | - | 250 mi |
| Joby S4 / JAS4-1 | 5-seat tilt-rotor (6 tilting props) | 2177 | - | - | - | 6 | 10.7 m | 200 mph | 150 mi |
| Archer Midnight | 5-seat lift+cruise with 6 tilting + 6 lift props | 2948 | - | 454 | - | 12 | - | - | 20 mi |
| Lilium Jet (7-seater) | 7-seat ducted-fan vectored thrust | 3175 | - | - | - | 36 ducted fans | - | 250 km/h | 250 km |
| Vertical Aerospace VX4 | 5-seat lift+cruise with 4 tilting front + 4 fixed rear props | - | - | 450 | - | 8 | 15 m | 241 km/h | 161 km |
| ASKA A5 | 4-seat roadable hybrid-electric lift+cruise/tilt | - | - | - | - | 6 | - | 241 km/h | 402 km |
| Pipistrel Velis Electro (Virus SW 128) | 2-seat electric fixed-wing (type-certificated) | 600 | 428 | 172 | 22.0 | 1 propeller | 10.7 m | 88 KTAS | - |
| NASA RVLT Lift+Cruise reference (battery-electric) | 6-pax lift+cruise reference concept (NDARC) | 3724 | 3176 | 544 | 399 | 9 | - | - | - |
| NASA single-passenger electric quadrotor | 1-pax multicopter reference concept (NDARC) | 568 | 452 | 113 | 49 | 4 | - | 86 kt | 50 nmi |

Notes: span column for wingless multicopters is the overall width/rotor-rim diameter. Kitty Hawk/Wisk Cora is the closest configuration match to E8-200 but has no published masses. The only regulator-sourced numbers are Joby MTOW (ST05) and all Velis Electro TCDS values (ST18). Hybrid ASKA A5 range is not comparable with battery-only aircraft.

## Known gaps and open items

- **Battery energy** is unpublished for almost every eVTOL benchmark; only Pivotal Helix (8 kWh, VFS), EHang EH216-S (17 kWh, secondary source), Velis Electro (TCDS) and the NASA reference concepts have values. Pack-level specific energy must therefore be built bottom-up from cell data (BT01-BT04) and overhead factors (SZ01, SZ02, SZ14).
- **Empty masses** are missing for EH216-S, Wisk, Joby, Archer, Beta, Lilium, VX4, CityAirbus, Cora, Heaviside, ASKA.
- **Rotor diameters** are published only for VoloCity (2.3 m), Velis (1.64 m prop) and the NASA concepts.
- **ASTM F3116/F3264, F2316, DO-311A and CMH-17** are paywalled and not held; requirement values currently come from the historical CFR text (ST06, ST07) and regulator MOCs.
- **Kadhiresan & Duffy (SZ08), Duffy et al. (SZ11, SZ12), Fredericks et al. 2018 (BT06)** are cited for method only; no numbers are quoted until the full papers are obtained.
- **McDonald & German 'eVTOL stored energy overview' (SZ15)** could not be located beyond a research-page summary.
- **BRS parachute ratings and masses (ST13)** were not retrievable; Galaxy GRS data (ST12) are used for the parachute mass and opening load.
- **Conflicting values** (flagged in `benchmarks_raw.json`): Archer MTOW (6,500 vs 7,000 lb), Hexa payload (250 vs 220 lb), EH216-S range (30 vs 35 km), Wisk MTOW labelling, Vahana Alpha One vs Alpha Two masses, Pivotal Helix empty mass vs the Part 103 limit, Amprius SA109 volumetric energy (950 vs 1,000 Wh/L).
- The predecessor projects keep their own dated source ledgers (component prices, motors, propellers): `../E8-eVTOL-Design-Explorer/aircraft/sources/README.md`.
