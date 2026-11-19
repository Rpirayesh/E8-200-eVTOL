"""Small helpers shared by the 2-D and 3-D OpenFOAM set-ups (dictionary writing, running, reading)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]          # project root (E8-200-eVTOL)
CFD = ROOT / "cfd"
CACHE = CFD / ".cache"                               # scratch cases (git-ignored)
VAL = ROOT / "validation" / "cfd"
FOAM_ENV = Path.home() / "tools" / "foamenv.sh"
MAX_CORES = 12

HDR = "FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n\n"


def wfile(case: Path, rel: str, cls: str, obj: str, body: str) -> None:
    p = case / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HDR.format(cls=cls, obj=obj) + body)


def sh(cmd: str, cwd: Path, log: str) -> int:
    """Run an OpenFOAM command in `cwd` with the environment sourced; output to `log`."""
    full = f"source {FOAM_ENV} && cd {cwd} && {cmd} > {log} 2>&1"
    return subprocess.run(["bash", "-c", full]).returncode


def read_dat(path: Path) -> tuple[list[str], np.ndarray]:
    lines = path.read_text().splitlines()
    hdr = [l for l in lines if l.startswith("#")][-1].lstrip("#").split()
    rows = []
    for l in lines:
        if l and not l.startswith("#"):
            v = l.replace("(", " ").replace(")", " ").split()
            rows.append([float(x) for x in v])
    return hdr, np.array(rows)


def coeff_history(case: Path, fo: str = "forceCoeffs") -> tuple[dict, np.ndarray]:
    files = sorted((case / "postProcessing" / fo).glob("*/coefficient*.dat"), key=lambda p: float(p.parent.name))
    hdr, arr = None, []
    for f in files:
        hdr, a = read_dat(f)
        arr.append(a)
    arr = np.vstack(arr)
    return {h: i for i, h in enumerate(hdr)}, arr


def coeffs(case: Path, avg: int = 500, fo: str = "forceCoeffs") -> dict:
    """Mean and standard deviation of the force coefficients over the last `avg` iterations."""
    col, arr = coeff_history(case, fo)
    tail = arr[-avg:]
    out = {k: float(tail[:, col[k]].mean()) for k in ("Cd", "Cl", "CmPitch")}
    out["Cl_std"] = float(tail[:, col["Cl"]].std())
    out["Cd_std"] = float(tail[:, col["Cd"]].std())
    out["iterations"] = int(arr[-1, 0])
    return out


def check_mesh_summary(log: Path) -> dict:
    """Key numbers from a checkMesh log."""
    txt = log.read_text() if log.exists() else ""
    out = {"mesh_ok": "Mesh OK" in txt, "failed_checks": txt.count("***")}
    import re
    num = r"([-+0-9.eE]+)"
    pats = {"cells": r"^\s*cells:\s+(\d+)", "max_skewness": r"Max skewness = " + num,
            "max_non_orth": r"non-orthogonality Max: " + num, "max_aspect_ratio": r"Max aspect ratio[ =:]+" + num}
    for key, pat in pats.items():
        m = re.search(pat, txt, re.M)
        if m:
            out[key] = int(m.group(1)) if key == "cells" else float(m.group(1))
    m = re.search(r"(\d+) highly skew faces", txt)
    out["n_skew_faces"] = int(m.group(1)) if m else 0
    return out
