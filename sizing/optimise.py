"""Mixed discrete/continuous optimiser for the E8-200 (work package D).

Objective: acquisition cost per aircraft (USD) + complexity penalty (USD 5,000 per distinct propulsion/actuated part
type + USD 500 per propulsion line-replaceable unit, model.A0), subject to every constraint of sizing.model (g <= 0).
Search: vectorised real/integer-coded genetic algorithm (tournament selection, blend crossover, Gaussian and
categorical mutation, elitism) with a static penalty for constraint violation, followed by a coordinate polish on the
rounded design.  Each call evaluates ~10^5 designs in a few seconds because sizing.model is vectorised.
"""
from __future__ import annotations

import numpy as np

from .model import evaluate

# variable: (kind, low/high or choices)
SPACE = {
    "D": ("c", 1.40, 2.20), "vtip": ("c", 130.0, 190.0), "span": ("c", 7.0, 9.0), "chord": ("c", 0.80, 1.70),
    "V": ("c", 120 / 3.6, 200 / 3.6), "Dp": ("c", 1.40, 2.05), "delta_w": ("c", 0.0, 0.40),
    "nb": ("d", [2, 3]), "flap": ("d", [0, 1, 2, 3]), "lm": ("d", [0, 1, 2, 3, 4, 5, 6]), "pm": ("d", [0, 1, 2, 3, 4, 5, 6, 7, 8]), "pnb": ("d", [2, 3]),
    "cell": ("d", [0, 1, 2]), "npk": ("d", [2, 3, 4, 5, 6, 7, 8]), "airfoil": ("d", [0, 1, 2, 3, 4]),
}
ROUND = {"D": 0.05, "vtip": 1.0, "span": 0.1, "chord": 0.05, "Dp": 0.05, "delta_w": 0.05}


def penalised(out):
    viol = np.nan_to_num(np.clip(out["G"], 0, None), nan=10.0, posinf=10.0).sum(axis=1)
    f = np.where(out["feasible"], out["objective"], 1e6 + 1e6 * np.minimum(viol, 1e3))
    return np.nan_to_num(f, nan=1e12, posinf=1e12)


def _sample(space, N, rng):
    X = {}
    for k, (kind, *b) in space.items():
        if kind == "c":
            X[k] = rng.uniform(b[0], b[1], N)
        elif kind == "d":
            X[k] = rng.choice(np.asarray(b[0]), N)
        else:                                  # fixed
            X[k] = np.full(N, b[0])
    return X


def ga(cfg, fixed=None, pop=1500, gens=45, seed=1, space=None, verbose=False):
    """Returns (best X dict of scalars, best out dict, history)."""
    space = dict(space or SPACE)
    for k, v in (fixed or {}).items():
        space[k] = ("f", v)
    rng = np.random.default_rng(seed)
    X = _sample(space, pop, rng)
    out = evaluate(X, cfg)
    f = penalised(out)
    hist = []
    for g in range(gens):
        # tournament selection (2 parents per child)
        i1, i2 = rng.integers(0, pop, (2, pop)), rng.integers(0, pop, (2, pop))
        pa = np.where(f[i1[0]] < f[i1[1]], i1[0], i1[1])
        pb = np.where(f[i2[0]] < f[i2[1]], i2[0], i2[1])
        C = {}
        scale = 0.15 * (1 - g / gens) + 0.02
        for k, (kind, *b) in space.items():
            if kind == "c":
                w = rng.uniform(-0.25, 1.25, pop)
                c = X[k][pa] + w * (X[k][pb] - X[k][pa])
                mut = rng.random(pop) < 0.3
                c = c + mut * rng.normal(0, scale * (b[1] - b[0]), pop)
                C[k] = np.clip(c, b[0], b[1])
            elif kind == "d":
                c = np.where(rng.random(pop) < 0.5, X[k][pa], X[k][pb])
                mut = rng.random(pop) < 0.08
                C[k] = np.where(mut, rng.choice(np.asarray(b[0]), pop), c)
            else:
                C[k] = X[k]
        oc = evaluate(C, cfg)
        fc = penalised(oc)
        # elitist (mu + lambda) survival
        allf = np.concatenate([f, fc])
        keep = np.argsort(allf)[:pop]
        X = {k: np.concatenate([X[k], C[k]])[keep] for k in X}
        f = allf[keep]
        hist.append(float(f[0]))
        if verbose and g % 10 == 0:
            print(g, f[0])
    best = {k: X[k][0] for k in X}
    return best, f[0], hist


def evaluate_one(x, cfg):
    o = evaluate({k: np.atleast_1d(v) for k, v in x.items()}, cfg)
    return o


def polish(x, cfg, space=None, fixed=None):
    """Round to buildable values, then coordinate search on the continuous variables (one step = rounding unit)."""
    space = dict(space or SPACE)
    fixed = fixed or {}
    x = dict(x)
    for k, st in ROUND.items():
        if k not in fixed:
            x[k] = round(x[k] / st) * st
    x["V"] = round(x["V"] * 3.6) / 3.6

    def score(xx):
        return float(penalised(evaluate_one(xx, cfg))[0])
    best = score(x)
    steps = dict(ROUND, V=1 / 3.6)
    improved = True
    while improved:
        improved = False
        for k, st in steps.items():
            if k in fixed:
                continue
            lo, hi = space[k][1], space[k][2]
            for d in (-1, 1):
                for mult in (1, 2):
                    y = dict(x)
                    y[k] = min(max(x[k] + d * mult * st, lo), hi)
                    s = score(y)
                    if s < best - 1e-6:
                        x, best, improved = y, s, True
        for k, (kind, *b) in space.items():
            if kind != "d" or k in fixed:
                continue
            for c in b[0]:
                y = dict(x)
                y[k] = c
                s = score(y)
                if s < best - 1e-6:
                    x, best, improved = y, s, True
    return x, best


def optimise(cfg, fixed=None, seeds=(1, 2), pop=1500, gens=45):
    best_x, best_f = None, np.inf
    for s in seeds:
        x, f, _ = ga(cfg, fixed, pop, gens, seed=s)
        if f < best_f:
            best_x, best_f = x, f
    x, f = polish(best_x, cfg, fixed=fixed)
    return x, f
