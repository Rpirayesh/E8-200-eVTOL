"""Convergence watchdog: stops steady cases whose force coefficients no longer change.

For every running case under cfd/.cache (log.simpleFoam modified in the last minutes) the force-coefficient
history is checked; when, over the last `window` iterations, the change of the running mean of Cl and Cd
(two half-windows compared) is below the tolerance, `stopAt writeNow` is set in system/controlDict (the cases
run with runTimeModifiable true).  Oscillating (unsteady) cases are left to reach their iteration limit.

    python cfd/tools/watchdog.py [--window 400] [--tol-cl 2e-4] [--tol-cd 2e-6]
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import numpy as np

CACHE = Path(__file__).resolve().parents[1] / ".cache"


def history(case: Path):
    for fo in ("forceCoeffs", "coeffs"):
        files = sorted((case / "postProcessing" / fo).glob("*/coefficient*.dat"))
        if files:
            rows, hdr = [], None
            for f in files:
                for l in f.read_text().splitlines():
                    if l.startswith("#"):
                        hdr = l.lstrip("#").split()
                    elif l.strip():
                        rows.append([float(x) for x in l.split()])
            if rows and hdr:
                return {h: i for i, h in enumerate(hdr)}, np.array(rows)
    return None, None


def converged(col, arr, window, tol_cl, tol_cd) -> bool:
    if arr is None or len(arr) < 2 * window:
        return False
    t = arr[-window:]
    h = window // 2
    for q, tol in (("Cl", tol_cl), ("Cd", tol_cd)):
        a, b = t[:h, col[q]].mean(), t[h:, col[q]].mean()
        if abs(b - a) > tol:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=400)
    ap.add_argument("--tol-cl", type=float, default=2e-4)
    ap.add_argument("--tol-cd", type=float, default=2e-6)
    ap.add_argument("--min-iter", type=int, default=800)
    ap.add_argument("--pattern", default="cfd2d/*/*")
    a = ap.parse_args()
    stopped = set()
    while True:
        for case in {p.parent for p in CACHE.glob(a.pattern + "/log.simpleFoam*")}:
            newest = max(case.glob("log.simpleFoam*"), key=lambda p: p.stat().st_mtime)
            if case in stopped or time.time() - newest.stat().st_mtime > 300:
                continue
            col, arr = history(case)
            if arr is None or arr[-1, 0] < a.min_iter:
                continue
            if converged(col, arr, a.window, a.tol_cl, a.tol_cd):
                cd = case / "system" / "controlDict"
                txt = cd.read_text()
                if "stopAt writeNow" not in txt:
                    cd.write_text(re.sub(r"stopAt \w+;", "stopAt writeNow;", txt))
                    print(time.strftime("%H:%M:%S"), "stop", case.relative_to(CACHE), int(arr[-1, 0]), flush=True)
                stopped.add(case)
        time.sleep(30)


if __name__ == "__main__":
    main()
