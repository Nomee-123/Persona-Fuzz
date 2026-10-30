from __future__ import annotations

import math
from typing import Iterable


def wilson_ci(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def rate(values: Iterable[bool]) -> tuple[float, int, int]:
    vals = list(values)
    n = len(vals)
    k = sum(1 for v in vals if v)
    return ((k / n) if n else 0.0, k, n)


def _binom_pmf(k: int, n: int) -> float:
    return math.comb(n, k) * (0.5**n)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar test for paired binary outcomes."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(_binom_pmf(i, n) for i in range(0, k + 1)) * 2
    return min(1.0, p)


def paired_mcnemar(pairs: list[tuple[bool, bool]]) -> dict[str, float | int]:
    b = sum(1 for a, d in pairs if a and not d)
    c = sum(1 for a, d in pairs if not a and d)
    return {"before_only": b, "after_only": c, "p_value": round(mcnemar_exact(b, c), 6)}
