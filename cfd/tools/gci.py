"""Grid convergence index (Roache 1994; Celik et al. 2008, ASME J. Fluids Eng. 130, 078001).

Index 1 = finest grid.  Returns the observed order, Richardson extrapolation and GCI of the fine
and medium grids, and the asymptotic-range check GCI_21 * r^p / GCI_32 ~ 1."""
from __future__ import annotations

import math


def celik(h: tuple[float, float, float], f: tuple[float, float, float], fs: float = 1.25, p_formal: float = 2.0) -> dict:
    h1, h2, h3 = h
    f1, f2, f3 = f
    r21, r32 = h2 / h1, h3 / h2
    e21, e32 = f2 - f1, f3 - f2
    out = dict(h=h, f=f, r21=r21, r32=r32)
    if e21 == 0 or e32 == 0:
        return out | dict(note="zero difference between grids")
    if abs(e21) >= abs(e32):
        # the change grows under refinement: no observed order, use Roache's safety factor 3 on the fine difference
        ea21 = abs(e21 / f1) if f1 else float("nan")
        return out | dict(p=None, note="not converging monotonically (|e21| >= |e32|): GCI = 3 |e21| / |f1|",
                          f_ext=None, ea21=ea21, gci21=3 * ea21, gci32=None, asymptotic_ratio=None, oscillatory=e32 / e21 < 0)
    s = math.copysign(1.0, e32 / e21)
    oscill = e32 / e21 < 0
    p = 2.0
    for _ in range(200):
        q = math.log((r21**p - s) / (r32**p - s))
        p_new = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(p_new - p) < 1e-10:
            break
        p = p_new
    p_obs = p
    p = min(p, p_formal)          # observed order above the formal order of the scheme is not credited
    f_ext = (r21**p * f1 - f2) / (r21**p - 1)
    ea21 = abs((f1 - f2) / f1) if f1 else float("nan")
    eext21 = abs((f_ext - f1) / f_ext) if f_ext else float("nan")
    gci21 = fs * ea21 / (r21**p - 1)
    ea32 = abs((f2 - f3) / f2) if f2 else float("nan")
    gci32 = fs * ea32 / (r32**p - 1)
    return out | dict(p=p_obs, p_used=p, oscillatory=oscill, f_ext=f_ext, ea21=ea21, eext21=eext21, gci21=gci21, gci32=gci32,
                      asymptotic_ratio=(fs * ea32 / (r32**p_obs - 1)) / (r21**p_obs * fs * ea21 / (r21**p_obs - 1)) if ea21 else float("nan"))
