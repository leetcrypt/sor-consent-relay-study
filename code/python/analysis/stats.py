"""Pre-registered inferential statistics for the RQ1/RQ2 confirmatory analysis.

This module is the *turnkey* implementation of the frozen prereg §6 analysis plan
(`sor-consent-prereg.md`), written **before** any confirmatory data exists so the
analysis precedes the data (`rigor-standards §Statistics`). It computes nothing
study-specific by itself — it is a small, stdlib-only inference toolkit:

  * :func:`bootstrap_ci` / :func:`two_sample_diff_ci` — BCa (bias-corrected and
    accelerated) bootstrap 95% CIs, 10,000 resamples by default, with a percentile
    fallback when the acceleration/bias terms are degenerate (§6: "Bootstrap:
    10,000 resamples, BCa intervals; seed spot-check");
  * :func:`miller_madow_entropy_bits` — plug-in Shannon entropy with the
    Miller–Madow finite-sample bias correction (§3 estimator [APPROVAL]);
  * :func:`spearman` — Spearman rank correlation (RQ2-P3 mechanism test);
  * :func:`holm_bonferroni` — Holm step-down multiplicity correction over the
    frozen confirmatory family, with an explicit ``family_size`` so a lead paper
    that reports a subset of the 7 pre-registered tests still corrects against the
    full family (§6; never re-optimised to the reported subset).

It performs no I/O, moves no traffic, and spawns no engine. Resampling is seeded
(``random.Random(seed)``) and the seed is returned in every :class:`CIResult`, so
a CI is reproducible and the §6 three-seed spot-check is mechanical.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable, List, Sequence, TypeVar

T = TypeVar("T")

_NORM = NormalDist(0.0, 1.0)
DEFAULT_RESAMPLES = 10_000
DEFAULT_ALPHA = 0.05


@dataclass(frozen=True)
class CIResult:
    """A point estimate with a bootstrap confidence interval and full provenance
    (method actually used, resample count, seed, alpha) so it is reproducible and
    auditable. ``excludes(v)`` is the pre-registered gate primitive: True iff the
    whole interval lies on one side of ``v`` (e.g. RQ1-P1's "CI excludes 0.5")."""

    point: float
    lo: float
    hi: float
    alpha: float
    n_resamples: int
    method: str  # "bca" | "percentile"
    seed: int

    def excludes(self, v: float) -> bool:
        return (self.lo > v) or (self.hi < v)

    def strictly_greater(self, v: float) -> bool:
        return self.lo > v

    def strictly_less(self, v: float) -> bool:
        return self.hi < v

    def as_dict(self) -> dict:
        return {
            "point": self.point,
            "ci_lo": self.lo,
            "ci_hi": self.hi,
            "alpha": self.alpha,
            "n_resamples": self.n_resamples,
            "method": self.method,
            "seed": self.seed,
        }


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile of an already-sorted sequence, ``q`` in
    [0, 1]. Empty -> NaN; clamps out-of-range q to the endpoints."""
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo]) * (1 - frac) + float(sorted_vals[hi]) * frac


def _bca_endpoints(
    thetas: Sequence[float], theta_hat: float, jack: Sequence[float], alpha: float
) -> tuple[float, float, str]:
    """Return (q_lo, q_hi, method) adjusted percentiles for a BCa interval, or the
    plain (alpha/2, 1-alpha/2, "percentile") pair when the bias/acceleration terms
    are degenerate (all resamples equal, or zero jackknife spread)."""
    b = len(thetas)
    n_less = sum(1 for t in thetas if t < theta_hat)
    # Bias correction z0. If every resample is on one side, z0 is undefined ->
    # fall back to the percentile interval rather than emit a garbage bound.
    if n_less == 0 or n_less == b:
        return alpha / 2.0, 1.0 - alpha / 2.0, "percentile"
    z0 = _NORM.inv_cdf(n_less / b)

    # Acceleration from the jackknife leave-one-out estimates.
    jbar = sum(jack) / len(jack)
    diffs = [jbar - j for j in jack]
    denom = 6.0 * (sum(d * d for d in diffs) ** 1.5)
    if denom == 0.0:
        return alpha / 2.0, 1.0 - alpha / 2.0, "percentile"
    a = sum(d ** 3 for d in diffs) / denom

    z_lo = _NORM.inv_cdf(alpha / 2.0)
    z_hi = _NORM.inv_cdf(1.0 - alpha / 2.0)

    def adjust(z: float) -> float:
        num = z0 + z
        return _NORM.cdf(z0 + num / (1.0 - a * num))

    q_lo = adjust(z_lo)
    q_hi = adjust(z_hi)
    if not (0.0 < q_lo < q_hi < 1.0):
        return alpha / 2.0, 1.0 - alpha / 2.0, "percentile"
    return q_lo, q_hi, "bca"


def two_sided_bootstrap_p(thetas: Sequence[float], null: float) -> float:
    """A bootstrap two-sided p-value for H0: θ = ``null`` from a bootstrap
    distribution ``thetas`` — 2·min(P(θ* ≤ null), P(θ* ≥ null)), capped at 1.0.
    Used only to *order* the Holm family; the pre-registered decision gates are
    the CIs, never a p-value alone (§6)."""
    b = len(thetas)
    if b == 0:
        return 1.0
    le = sum(1 for t in thetas if t <= null) / b
    ge = sum(1 for t in thetas if t >= null) / b
    return min(1.0, 2.0 * min(le, ge))


def bootstrap_ci(
    units: Sequence[T],
    statistic: Callable[[Sequence[T]], float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = 0,
    method: str = "bca",
    return_dist: bool = False,
):
    """One-sample bootstrap CI of ``statistic`` over ``units`` (the unit of
    analysis — a circuit-pair for RQ1, a circuit for RQ2). Resamples ``units`` with
    replacement ``n_resamples`` times. ``method="bca"`` applies bias-correction +
    acceleration (falling back to percentile if degenerate); ``"percentile"``
    forces the plain interval. With ``return_dist=True`` also returns the sorted
    bootstrap distribution (so a p-value can be derived from the same resamples)."""
    n = len(units)
    if n == 0:
        res = CIResult(float("nan"), float("nan"), float("nan"),
                       alpha, n_resamples, "empty", seed)
        return (res, []) if return_dist else res
    theta_hat = float(statistic(units))
    rng = random.Random(seed)
    thetas: List[float] = []
    for _ in range(n_resamples):
        sample = [units[rng.randrange(n)] for _ in range(n)]
        thetas.append(float(statistic(sample)))
    thetas.sort()

    if method == "bca" and n > 1:
        jack = [float(statistic([units[j] for j in range(n) if j != i])) for i in range(n)]
        q_lo, q_hi, used = _bca_endpoints(thetas, theta_hat, jack, alpha)
    else:
        q_lo, q_hi, used = alpha / 2.0, 1.0 - alpha / 2.0, "percentile"

    res = CIResult(theta_hat, _percentile(thetas, q_lo), _percentile(thetas, q_hi),
                   alpha, n_resamples, used, seed)
    return (res, thetas) if return_dist else res


def two_sample_diff_ci(
    units_a: Sequence[T],
    units_b: Sequence[T],
    statistic: Callable[[Sequence[T]], float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = 0,
    method: str = "bca",
    return_dist: bool = False,
):
    """Bootstrap CI for the difference ``statistic(A) - statistic(B)`` of two
    independent arms (RQ2-P1: ΔH = H(federated) − H(single-house, matched N)).
    Each arm is resampled independently. BCa uses a combined leave-one-out
    jackknife across both arms (each point dropped from its own arm). With
    ``return_dist=True`` also returns the sorted bootstrap distribution."""
    na, nb = len(units_a), len(units_b)
    if na == 0 or nb == 0:
        res = CIResult(float("nan"), float("nan"), float("nan"),
                       alpha, n_resamples, "empty", seed)
        return (res, []) if return_dist else res
    theta_hat = float(statistic(units_a)) - float(statistic(units_b))
    rng = random.Random(seed)
    thetas: List[float] = []
    for _ in range(n_resamples):
        sa = [units_a[rng.randrange(na)] for _ in range(na)]
        sb = [units_b[rng.randrange(nb)] for _ in range(nb)]
        thetas.append(float(statistic(sa)) - float(statistic(sb)))
    thetas.sort()

    if method == "bca" and na > 1 and nb > 1:
        stat_b_full = float(statistic(units_b))
        stat_a_full = float(statistic(units_a))
        jack: List[float] = []
        for i in range(na):
            jack.append(float(statistic([units_a[j] for j in range(na) if j != i])) - stat_b_full)
        for i in range(nb):
            jack.append(stat_a_full - float(statistic([units_b[j] for j in range(nb) if j != i])))
        q_lo, q_hi, used = _bca_endpoints(thetas, theta_hat, jack, alpha)
    else:
        q_lo, q_hi, used = alpha / 2.0, 1.0 - alpha / 2.0, "percentile"

    res = CIResult(theta_hat, _percentile(thetas, q_lo), _percentile(thetas, q_hi),
                   alpha, n_resamples, used, seed)
    return (res, thetas) if return_dist else res


def mean(xs: Sequence[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sequence (a bootstrap resample is never
    empty, but degenerate jackknife folds can be)."""
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


# --------------------------------------------------------------------------- #
# RQ2 — Miller–Madow bias-corrected entropy (§3 estimator [APPROVAL]).
# --------------------------------------------------------------------------- #
def miller_madow_entropy_bits(counts: Sequence[float]) -> float:
    """Shannon entropy in bits with the Miller–Madow bias correction.

    H_MM = H_plugin + (K − 1) / (2 N ln 2), where K is the number of observed
    (non-zero) categories and N the total count. This corrects the systematic
    downward bias of the plug-in (MLE) estimator at finite N. Empty/all-zero -> 0.
    """
    vals = [c for c in counts if c > 0]
    total = float(sum(vals))
    if total <= 0:
        return 0.0
    h = 0.0
    for c in vals:
        p = c / total
        h -= p * math.log2(p)
    k = len(vals)
    return h + (k - 1) / (2.0 * total * math.log(2.0))


# --------------------------------------------------------------------------- #
# RQ2-P3 — Spearman rank correlation.
# --------------------------------------------------------------------------- #
def _rankdata(values: Sequence[float]) -> List[float]:
    """Fractional ranks (ties get the average of the ranks they span)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank over the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / (dx * dy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman ρ = Pearson correlation of the fractional ranks. Returns 0.0 for
    empty, length-mismatched, or zero-variance inputs."""
    if len(xs) != len(ys) or not xs:
        return 0.0
    return _pearson(_rankdata(xs), _rankdata(ys))


# --------------------------------------------------------------------------- #
# Multiplicity — Holm–Bonferroni over the frozen confirmatory family.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HolmResult:
    name: str
    p: float
    p_adjusted: float
    reject: bool
    rank: int  # 1-based ascending rank among the reported tests
    multiplier: int  # Holm denominator actually used (family_size − rank + 1)


def holm_bonferroni(
    pvalues: dict, alpha: float = DEFAULT_ALPHA, family_size: int | None = None
) -> List[HolmResult]:
    """Holm step-down correction.

    ``pvalues`` maps test-name -> raw p. ``family_size`` is the size of the frozen
    confirmatory family (default = number of tests supplied). When a lead paper
    reports a **subset** of the pre-registered family (e.g. the 4 RQ1/RQ2 tests of
    a 7-test frozen family), pass ``family_size=7``: the k-th smallest reported p
    is then tested against ``alpha / (family_size − k + 1)`` — i.e. the reported
    tests are treated as occupying the *smallest* slots of the full family, giving
    the largest (most conservative) Holm multipliers. This is strictly no less
    stringent than the true embedded correction and can never re-optimise the
    family down to the reported subset (which would inflate the false-rejection
    rate and constitute p-hacking).

    Adjusted p-values are made monotone non-decreasing in rank (standard Holm) and
    capped at 1.0. ``reject`` is ``p_adjusted <= alpha``.
    """
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = family_size if family_size is not None else len(items)
    if m < len(items):
        raise ValueError(f"family_size {m} < number of reported tests {len(items)}")

    out: List[HolmResult] = []
    running = 0.0
    for k, (name, p) in enumerate(items, start=1):
        mult = m - k + 1
        adj = min(1.0, mult * p)
        running = max(running, adj)  # enforce step-down monotonicity
        out.append(HolmResult(name=name, p=p, p_adjusted=running,
                              reject=running <= alpha, rank=k, multiplier=mult))
    return out
