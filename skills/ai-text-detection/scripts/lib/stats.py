"""Small statistics used by the calibration steps (standard library only)."""

from __future__ import annotations

import math


def missing(v: object) -> bool:
    """Whether a value is absent: None or NaN."""
    return v is None or (isinstance(v, float) and math.isnan(v))


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """Probability that a positive scores above a negative (ties count half); None when
    either side is empty."""
    if not pos or not neg:
        return None
    ranked = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        mean_rank = (i + j + 1) / 2
        rank_sum += mean_rank * sum(1 for k in range(i, j) if ranked[k][1] == 1)
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def quantile(vals: list[float], q: float) -> float:
    """Linear-interpolated quantile, q in [0, 1]; NaN for an empty list."""
    s = sorted(vals)
    if not s:
        return float("nan")
    pos = q * (len(s) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def pearson(x: list[float], y: list[float]) -> float | None:
    """Pearson correlation; None when either side does not vary."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = sum((a - mx) ** 2 for a in x)
    sy = sum((b - my) ** 2 for b in y)
    if sx == 0 or sy == 0:
        return None
    return (
        sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / (sx * sy) ** 0.5
    )


def rate(flags: list[bool], digits: int = 3) -> float | None:
    """Share of True values, rounded; None for an empty list."""
    return round(sum(flags) / len(flags), digits) if flags else None
