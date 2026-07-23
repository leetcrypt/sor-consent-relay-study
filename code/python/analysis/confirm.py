"""RQ1/RQ2 confirmatory decision layer — the frozen prereg §6 gates, in code.

This turns the §6 analysis plan into mechanical, pre-registered decisions for the
four confirmatory tests the **lead paper (G4 + RQ1 + RQ2)** reports:

  * **RQ1-P1 (leak):** bridge-on correlation AUC + BCa 95% CI. Gate = the CI
    **excludes 0.5** (D2). Materiality is a *separate label*, not the gate:
    CI lower bound ≥ 0.60 ⇒ "material", 0.5 < lo < 0.60 ⇒ "weak-but-real".
  * **RQ1-P2 (padding efficacy):** paired ΔAUC = AUC(no-pad) − AUC(pad) over
    circuits; effective iff the CI **> 0**.
  * **RQ2-P1 (anonymity set, two-sided):** ΔH = H(federated) − H(single, matched
    N) with Miller–Madow per-circuit entropy; **grow** if CI > 0, **honest-shrink**
    if CI < 0, **inconclusive** if it spans 0. The sign is *not* presumed.
  * **RQ2-P3 (mechanism):** Spearman ρ between top-k=3 bridge concentration and
    per-circuit H; negative ρ quantifies funnelling.

Multiplicity: :func:`apply_holm` corrects the reported tests against the **full
frozen family of 7** (§6), not the reported subset — see the module's
``FROZEN_FAMILY`` and the stage-05 Holm clarification. The bootstrap p-values are
used only to *order* the Holm step-down; every reported decision is a CI gate,
never a bare p (§6, rigor-standards §Statistics).

Pure analysis: no I/O beyond what a caller serialises, no engine, no traffic. All
detectors are the §5-calibrated instruments (`detectors.py`), never re-fit here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from cmd_chat.sor.analysis.detectors import auc
from cmd_chat.sor.analysis.stats import (
    CIResult,
    HolmResult,
    bootstrap_ci,
    holm_bonferroni,
    mean,
    miller_madow_entropy_bits,
    spearman,
    two_sample_diff_ci,
    two_sided_bootstrap_p,
)

# The pre-registered confirmatory family (frozen prereg §6). The lead paper
# reports the first four; RQ3's three are the severable follow-on (D6/§8). The
# family SIZE stays 7 for Holm regardless of how many are reported here.
FROZEN_FAMILY: Tuple[str, ...] = (
    "RQ1-P1", "RQ1-P2", "RQ2-P1", "RQ2-P3",
    "RQ3-P1-perf", "RQ3-P1-latency", "RQ3-P2",
)
FROZEN_FAMILY_SIZE = len(FROZEN_FAMILY)  # 7
LEAD_PAPER_TESTS: Tuple[str, ...] = ("RQ1-P1", "RQ1-P2", "RQ2-P1", "RQ2-P3")

MATERIALITY_FLOOR = 0.60  # §6 [APPROVAL] — a *label*, not the RQ1 gate.
TOP_K = 3  # RQ2-P3 [APPROVAL].

# A circuit-pair scored by the correlator: (score, linked?) — linked = same
# circuit (diagonal), unlinked = different (off-diagonal).
Pair = Tuple[float, bool]


@dataclass(frozen=True)
class ConfirmTest:
    """One confirmatory test's frozen decision: the effect size, its CI, the
    pre-registered gate outcome, any secondary label, and the bootstrap p used
    only for Holm ordering."""

    name: str
    effect: str          # human name of the effect size (e.g. "AUC", "ΔH")
    ci: CIResult
    decision: str        # e.g. "leak", "null", "grow", "shrink", "inconclusive"
    label: str           # secondary label (materiality / direction); "" if none
    p_for_holm: float

    def as_dict(self) -> Dict:
        return {
            "name": self.name,
            "effect": self.effect,
            "decision": self.decision,
            "label": self.label,
            "p_for_holm": self.p_for_holm,
            **self.ci.as_dict(),
        }


def _auc_of_pairs(pairs: Sequence[Pair]) -> float:
    pos = [s for s, linked in pairs if linked]
    neg = [s for s, linked in pairs if not linked]
    return auc(pos, neg)


def rq1_p1_leak(
    pairs: Sequence[Pair], *, seed: int = 0, n_resamples: int = 10_000, alpha: float = 0.05
) -> ConfirmTest:
    """RQ1-P1: bridge-on correlation AUC with BCa CI over circuit pairs. Gate = CI
    excludes 0.5 (a leak is present). Materiality label from the CI lower bound."""
    ci, dist = bootstrap_ci(list(pairs), _auc_of_pairs, n_resamples=n_resamples,
                            alpha=alpha, seed=seed, return_dist=True)
    if ci.excludes(0.5) and ci.strictly_greater(0.5):
        decision = "leak"
        label = "material" if ci.lo >= MATERIALITY_FLOOR else "weak-but-real"
    elif ci.strictly_less(0.5):
        decision = "anomaly-below-chance"  # AUC < 0.5 (should not happen for a real leak)
        label = ""
    else:
        decision = "null"  # CI spans 0.5 — no measurable leak
        label = ""
    return ConfirmTest("RQ1-P1", "AUC", ci, decision, label,
                       two_sided_bootstrap_p(dist, 0.5))


@dataclass(frozen=True)
class PairedCircuit:
    """One circuit contributing correlator pairs under both conditions — the unit
    of the RQ1-P2 *paired* bootstrap."""

    nopad_pairs: Tuple[Pair, ...]
    pad_pairs: Tuple[Pair, ...]


def _delta_auc(units: Sequence[PairedCircuit]) -> float:
    nopad = [p for u in units for p in u.nopad_pairs]
    pad = [p for u in units for p in u.pad_pairs]
    return _auc_of_pairs(nopad) - _auc_of_pairs(pad)


def rq1_p2_padding(
    circuits: Sequence[PairedCircuit], *, seed: int = 0,
    n_resamples: int = 10_000, alpha: float = 0.05,
) -> ConfirmTest:
    """RQ1-P2: paired ΔAUC = AUC(no-pad) − AUC(pad), resampling circuits (the
    paired unit). Padding effective iff the CI > 0."""
    ci, dist = bootstrap_ci(list(circuits), _delta_auc, n_resamples=n_resamples,
                            alpha=alpha, seed=seed, return_dist=True)
    decision = "padding-effective" if ci.strictly_greater(0.0) else "padding-ineffective"
    return ConfirmTest("RQ1-P2", "ΔAUC", ci, decision, "",
                       two_sided_bootstrap_p(dist, 0.0))


def _mean_mm_entropy(circuits: Sequence[Sequence[float]]) -> float:
    """Mean per-circuit Miller–Madow entropy (bits) over an arm's circuits."""
    return mean([miller_madow_entropy_bits(c) for c in circuits])


def rq2_p1_delta_h(
    federated: Sequence[Sequence[float]],
    single_house: Sequence[Sequence[float]],
    *, seed: int = 0, n_resamples: int = 10_000, alpha: float = 0.05,
) -> ConfirmTest:
    """RQ2-P1 (two-sided): ΔH = mean H(federated) − mean H(single-house, matched
    N), Miller–Madow per circuit, BCa CI over circuits. grow / honest-shrink /
    inconclusive by the sign of the CI — the design does not presume the sign.

    ``federated`` / ``single_house`` are lists of per-circuit sender-posterior
    count vectors. The caller is responsible for the §6 matched-N sizing (the
    single-house arm's node count equals the federated arm's total consenting
    nodes); this function asserts nothing about N — it reports ΔH honestly."""
    ci, dist = two_sample_diff_ci(list(federated), list(single_house), _mean_mm_entropy,
                                  n_resamples=n_resamples, alpha=alpha, seed=seed,
                                  return_dist=True)
    if ci.strictly_greater(0.0):
        decision, label = "grow", "federation grows the anonymity set"
    elif ci.strictly_less(0.0):
        decision, label = "shrink", "honest null — federation shrinks (reported with equal prominence)"
    else:
        decision, label = "inconclusive", "CI spans 0"
    return ConfirmTest("RQ2-P1", "ΔH", ci, decision, label,
                       two_sided_bootstrap_p(dist, 0.0))


def rq2_p3_funnel(
    concentration: Sequence[float], per_circuit_h: Sequence[float],
    *, seed: int = 0, n_resamples: int = 10_000, alpha: float = 0.05,
) -> ConfirmTest:
    """RQ2-P3 (mechanism): Spearman ρ between top-k=3 bridge concentration and
    per-circuit entropy H, with BCa CI over circuits. Negative ρ quantifies
    funnelling. ``concentration[i]``/``per_circuit_h[i]`` are the two measurements
    for circuit i."""
    units = list(zip(concentration, per_circuit_h))
    stat = lambda us: spearman([x for x, _ in us], [y for _, y in us])
    ci, dist = bootstrap_ci(units, stat, n_resamples=n_resamples, alpha=alpha,
                            seed=seed, return_dist=True)
    if ci.strictly_less(0.0):
        decision, label = "funnel", "negative ρ — concentration funnels the anonymity set"
    elif ci.strictly_greater(0.0):
        decision, label = "anti-funnel", "positive ρ"
    else:
        decision, label = "inconclusive", "CI spans 0"
    return ConfirmTest("RQ2-P3", "spearman_rho", ci, decision, label,
                       two_sided_bootstrap_p(dist, 0.0))


def apply_holm(
    tests: Sequence[ConfirmTest], *, alpha: float = 0.05,
    family_size: int = FROZEN_FAMILY_SIZE,
) -> List[HolmResult]:
    """Holm–Bonferroni over the reported ``tests``, corrected against the full
    frozen family (``family_size`` defaults to 7). Reporting a subset of the
    pre-registered family never shrinks the correction to the subset — see the
    stage-05 Holm clarification. Ordering uses the bootstrap p-values; the
    reported decisions remain the CI gates above."""
    return holm_bonferroni({t.name: t.p_for_holm for t in tests},
                           alpha=alpha, family_size=family_size)
