"""R7 (partial) — offline detector primitives + seeded synthetic fixtures.

Pure, stdlib-only calibration instruments (gate items 3 and 4). No I/O, no
engine, no pcaps: they operate on in-memory numeric series/distributions so they
can be validated entirely offline against synthetic ground truth. Determinism is
inherited from the R1 ``SorRng`` so a calibration fixture is reproducible from
its seed alone.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Union

from cmd_chat.sor.config import Domain, SorRng

Number = Union[int, float]
Series = Sequence[Number]


# --------------------------------------------------------------------------- #
# RQ2 — anonymity-set entropy (gate item 4).
# --------------------------------------------------------------------------- #
def shannon_entropy_bits(weights: Union[Dict[object, Number], Sequence[Number]]) -> float:
    """Shannon entropy in **bits** of an observed sender distribution.

    ``weights`` is either a mapping ``sender -> count`` or a sequence of
    non-negative weights. For ``N`` equiprobable senders this returns exactly
    ``log2(N)`` (the maximum for an N-set), which is the gate item 4 predicate.
    An empty or all-zero distribution has entropy 0."""
    vals = list(weights.values()) if isinstance(weights, dict) else list(weights)
    total = float(sum(vals))
    if total <= 0:
        return 0.0
    h = 0.0
    for c in vals:
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


# --------------------------------------------------------------------------- #
# RQ1 — bridge-linkability correlation scorer (gate item 3).
# --------------------------------------------------------------------------- #
def pearson(xs: Series, ys: Series) -> float:
    """Pearson correlation coefficient of two equal-length numeric series.
    Returns 0.0 for empty, mismatched-length, or zero-variance inputs (a flat
    series carries no linkage signal)."""
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


def score_matrix(ingress: Sequence[Series], egress: Sequence[Series]) -> List[List[float]]:
    """Full pairwise linkage-score matrix ``S[i][j] = pearson(ingress[i],
    egress[j])``. The candidate true pairing is the diagonal (``i == j``)."""
    return [[pearson(a, b) for b in egress] for a in ingress]


def auc(pos: Series, neg: Series) -> float:
    """Rank AUC = P(pos ranked above neg) with ties counted as 0.5 (Mann-Whitney
    U normalized). AUC 1.0 = perfect separation, 0.5 = chance. Empty side -> 0.5."""
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1.0
            elif p == q:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def linkage_auc(scores: Sequence[Sequence[float]]) -> float:
    """AUC of the diagonal (linked) scores against the off-diagonal (unlinked)
    scores of a square score matrix — the RQ1 bridge-correlation AUC."""
    n = len(scores)
    pos = [scores[i][i] for i in range(n)]
    neg = [scores[i][j] for i in range(n) for j in range(n) if i != j]
    return auc(pos, neg)


def bridge_correlation_auc(ingress: Sequence[Series], egress: Sequence[Series]) -> float:
    """RQ1 scorer: how well the correlator links each ingress flow to its true
    egress flow, as AUC over all candidate pairings. ≈1 for a linked bridge,
    ≈0.5 for an unlinked one (gate item 3)."""
    return linkage_auc(score_matrix(ingress, egress))


# --------------------------------------------------------------------------- #
# Seeded synthetic calibration fixtures (ground truth known by construction).
# --------------------------------------------------------------------------- #
def synthetic_bridge_fixture(
    seed: int,
    n_flows: int = 8,
    bins: int = 64,
    jitter: int = 5,
    linked: bool = True,
) -> tuple[List[List[int]], List[List[int]]]:
    """Deterministically build ``(ingress, egress)`` flow sets of per-bin byte
    counts from ``seed`` alone (reuses the R1 ``SorRng`` streams).

    - ``linked=True``: each egress flow is its ingress flow plus small independent
      padding/latency ``jitter`` — the *known-linked* control (diagonal
      correlation dominates -> AUC ≈ 1).
    - ``linked=False``: egress flows are drawn from an independent domain stream,
      uncorrelated with ingress — the *known-unlinked* control (no diagonal
      advantage -> AUC ≈ 0.5).
    """
    rng = SorRng(seed)
    sig = rng.stream(Domain.PATH)  # ingress signal
    ingress = [[sig.next_below(1000) for _ in range(bins)] for _ in range(n_flows)]
    if linked:
        noise = rng.stream(Domain.PADDING)
        span = 2 * jitter + 1
        egress = [
            [v + (noise.next_below(span) - jitter) for v in flow] for flow in ingress
        ]
    else:
        alt = rng.stream(Domain.CHURN)  # independent of the PATH signal
        egress = [[alt.next_below(1000) for _ in range(bins)] for _ in range(n_flows)]
    return ingress, egress
