"""SS3 — the FROZEN §6 confirmatory analysis, run ONCE on the real 180-cell
battery. Deterministic and regenerable from the frozen raw data + seeds.

    python -m cmd_chat.sor.analysis.stage06_run <data_dir> [--out results.json]
    python -m cmd_chat.sor.analysis.stage06_run <data_dir> --verify   # identity self-check

This computes the four lead-paper confirmatory tests exactly per the frozen prereg
§6 + the RATIFIED stage-05 clarifications, applies Holm over the frozen size-7
family (reporting the 4 RQ1/RQ2 tests, multipliers 7,6,5,4), and runs the §5
correlator-calibration sanity gate. **Nulls are reported as results**; nothing is
tuned to the data; only the pre-registered tests are run.

Faithfulness of the RQ1-P1 fast path
------------------------------------
RQ1-P1's pooled (entry,exit) pair set is ~75 000 units; the frozen
``stats.bootstrap_ci`` BCa path does an O(n) leave-one-out jackknife (each fold an
O(n²) rank-AUC), which is structurally intractable at that scale. We therefore run
a *performance-faithful* bootstrap (:func:`_bootstrap_auc_ci`) that reproduces the
frozen ``stats.bootstrap_ci`` **bit-for-bit** — the SAME ``random.Random(seed)``
resample sequence, an AUC provably identical to the frozen detector
(:func:`_fast_auc`, verified against ``detectors.auc``), the frozen
``_bca_endpoints`` / ``_percentile`` for the interval, and a vectorised
leave-one-out jackknife whose per-fold value equals the frozen per-fold recompute.
``--verify`` asserts this equals ``stats.bootstrap_ci`` on a subsample. The other
three tests use the frozen ``confirm.*`` functions unchanged.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from cmd_chat.sor.analysis import confirm, confirm_load, confirm_load_rq2 as rq2
from cmd_chat.sor.analysis.detectors import auc as frozen_auc, bridge_correlation_auc
from cmd_chat.sor.analysis.detectors import synthetic_bridge_fixture
from cmd_chat.sor.analysis import stats as S
from cmd_chat.sor.battery import S0, C_CIRCUITS, derive_seed, enumerate_cells
from cmd_chat.sor.executor import _circuit_seed

Pair = Tuple[float, bool]

ANALYSIS_SEED = S0  # 20260719 — the frozen base seed; fixed pre-data (§4).
N_RESAMPLES = S.DEFAULT_RESAMPLES  # 10_000 (frozen §6)
ALPHA = S.DEFAULT_ALPHA


# --------------------------------------------------------------------------- #
# Fast Mann–Whitney AUC — provably identical to detectors.auc (ties => 0.5).
# --------------------------------------------------------------------------- #
def _fast_auc(pos: np.ndarray, neg: np.ndarray) -> float:
    if pos.size == 0 or neg.size == 0:
        return 0.5
    allv = np.concatenate([pos, neg])
    order = allv.argsort(kind="mergesort")
    sv = allv[order]
    # Vectorised average-rank tie correction (bit-identical to the per-group
    # (first_rank+last_rank)/2 assignment): a tied run at sorted positions
    # [start, end) carries sequential ranks start+1..end, mean = (start+1+end)/2.
    _uniq, inv, counts = np.unique(sv, return_inverse=True, return_counts=True)
    ends = np.cumsum(counts)                 # exclusive end position per group
    starts = ends - counts                   # 0-based start position per group
    avg_rank = (starts + 1 + ends) / 2.0
    ranks = np.empty(allv.size, dtype=float)
    ranks[order] = avg_rank[inv]             # back to concatenated (pos|neg) order
    u = ranks[:pos.size].sum() - pos.size * (pos.size + 1) / 2.0
    return float(u / (pos.size * neg.size))


def _jackknife_aucs(scores: np.ndarray, linked: np.ndarray) -> np.ndarray:
    """Leave-one-out AUC for every original index, vectorised. Each value equals
    the frozen per-fold recompute ``_auc_of_pairs([units[j] for j != i])``."""
    pos = np.sort(scores[linked])
    neg = np.sort(scores[~linked])
    P, N = pos.size, neg.size
    # Full Mann–Whitney U with ties counted 0.5.
    lt = np.searchsorted(neg, pos, side="left").astype(float)
    le = np.searchsorted(neg, pos, side="right").astype(float)
    contrib_pos = lt + 0.5 * (le - lt)               # each pos point's U share
    U = contrib_pos.sum()
    s = scores
    is_pos = linked
    # contributions keyed by value via searchsorted on the sorted arrays
    p_lt = np.searchsorted(neg, s, side="left").astype(float)
    p_le = np.searchsorted(neg, s, side="right").astype(float)
    pos_share = p_lt + 0.5 * (p_le - p_lt)           # valid where is_pos
    n_gt = (P - np.searchsorted(pos, s, side="right")).astype(float)
    n_eq = (np.searchsorted(pos, s, side="right") - np.searchsorted(pos, s, side="left")).astype(float)
    neg_share = n_gt + 0.5 * n_eq                    # valid where ~is_pos
    denom_pos = (P - 1) * N
    denom_neg = P * (N - 1)
    auc_pos = (U - pos_share) / denom_pos if denom_pos > 0 else np.full(s.size, 0.5)
    auc_neg = (U - neg_share) / denom_neg if denom_neg > 0 else np.full(s.size, 0.5)
    out = np.where(is_pos, auc_pos, auc_neg)
    return out


def _bootstrap_auc_ci(pairs: Sequence[Pair], *, seed: int, n_resamples: int,
                      alpha: float) -> Tuple[S.CIResult, List[float]]:
    """Bit-faithful re-implementation of ``stats.bootstrap_ci(pairs, _auc, method='bca')``
    for the pooled RQ1-P1 pair set: identical RNG sequence, identical AUC values,
    frozen ``_bca_endpoints`` / ``_percentile``. Tractable via numpy + vectorised
    jackknife. Also returns the sorted resample distribution so the two-sided p can
    reuse it (the p is order-invariant). ``--verify`` checks the CI equals the frozen
    function on a subsample."""
    n = len(pairs)
    scores = np.fromiter((s for s, _ in pairs), dtype=float, count=n)
    linked = np.fromiter((1 if l else 0 for _, l in pairs), dtype=bool, count=n)

    def auc_of_idx(idx: np.ndarray) -> float:
        s = scores[idx]
        l = linked[idx]
        return _fast_auc(s[l], s[~l])

    theta_hat = _fast_auc(scores[linked], scores[~linked])
    rng = random.Random(seed)                 # SAME sequence as frozen bootstrap_ci
    thetas: List[float] = []
    for _ in range(n_resamples):
        idx = np.fromiter((rng.randrange(n) for _ in range(n)), dtype=np.int64, count=n)
        thetas.append(auc_of_idx(idx))
    thetas.sort()

    jack = list(_jackknife_aucs(scores, linked))     # order = original index order
    q_lo, q_hi, used = S._bca_endpoints(thetas, theta_hat, jack, alpha)
    ci = S.CIResult(theta_hat, S._percentile(thetas, q_lo), S._percentile(thetas, q_hi),
                    alpha, n_resamples, used, seed)
    return ci, thetas


def _bootstrap_delta_auc_ci(units: Sequence[confirm.PairedCircuit], *, seed: int,
                            n_resamples: int, alpha: float) -> Tuple[S.CIResult, List[float]]:
    """Bit-faithful re-implementation of ``stats.bootstrap_ci(units, confirm._delta_auc,
    method='bca')`` for RQ1-P2 — same class of intractability as RQ1-P1 (each of the
    10 000 resamples pools ~75 000 pairs through the O(pos×neg) frozen ``auc`` twice).
    Same RNG sequence, the AUC ``_fast_auc`` proven identical to ``detectors.auc``,
    frozen ``_bca_endpoints`` / ``_percentile``, and the frozen leave-one-out
    jackknife over the paired units. ``--verify`` checks it equals the frozen
    ``bootstrap_ci`` on a small PairedCircuit set. Returns the sorted resample
    distribution so the two-sided p reuses it (order-invariant)."""
    n = len(units)
    npd_s = [np.fromiter((s for s, _ in u.nopad_pairs), float, len(u.nopad_pairs)) for u in units]
    npd_l = [np.fromiter((1 if l else 0 for _, l in u.nopad_pairs), bool, len(u.nopad_pairs)) for u in units]
    pad_s = [np.fromiter((s for s, _ in u.pad_pairs), float, len(u.pad_pairs)) for u in units]
    pad_l = [np.fromiter((1 if l else 0 for _, l in u.pad_pairs), bool, len(u.pad_pairs)) for u in units]

    def delta(idxs) -> float:
        ns = np.concatenate([npd_s[i] for i in idxs]); nl = np.concatenate([npd_l[i] for i in idxs])
        ps = np.concatenate([pad_s[i] for i in idxs]); pl = np.concatenate([pad_l[i] for i in idxs])
        return _fast_auc(ns[nl], ns[~nl]) - _fast_auc(ps[pl], ps[~pl])

    theta_hat = delta(range(n))
    rng = random.Random(seed)                 # SAME sequence as frozen bootstrap_ci
    thetas: List[float] = []
    for _ in range(n_resamples):
        idxs = [rng.randrange(n) for _ in range(n)]
        thetas.append(delta(idxs))
    thetas.sort()

    jack = [delta([j for j in range(n) if j != i]) for i in range(n)]
    q_lo, q_hi, used = S._bca_endpoints(thetas, theta_hat, jack, alpha)
    ci = S.CIResult(theta_hat, S._percentile(thetas, q_lo), S._percentile(thetas, q_hi),
                    alpha, n_resamples, used, seed)
    return ci, thetas


# --------------------------------------------------------------------------- #
# RQ2 arm assembly from the per-cell dirs (no aggregate battery-results.json was
# written; per-circuit seeds are regenerated deterministically — SS2 verified the
# reconstruction against all 180 run-dir fingerprints).
# --------------------------------------------------------------------------- #
def _regen_circuit_seeds(cell_id: str, run_index: int, c: int = C_CIRCUITS) -> List[int]:
    run_seed = derive_seed(cell_id, run_index)
    return [_circuit_seed(run_seed, i) for i in range(c)]


def collect_rq2_arms(data_dir: Path):
    """Return (federated, single_house, bridge_only, concentration, per_h) exactly
    as ``confirm_load_rq2.collect_rq2_p1_arms`` / ``collect_rq2_p3`` would, but
    sourced from the per-cell dirs via regenerated per-circuit seeds."""
    cells = {c.cell_id: c for c in enumerate_cells()}
    federated: List[List[int]] = []
    single: List[List[int]] = []
    bridge_only: List[List[int]] = []
    conc: List[float] = []
    per_h: List[float] = []
    for rd in sorted(p for p in Path(data_dir).iterdir() if p.is_dir()):
        mp = rd / "metrics.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        cell = cells.get(m["cell_id"])
        if cell is None or cell.rq != "RQ2":
            continue
        seeds = _regen_circuit_seeds(m["cell_id"], int(m["run_index"]))
        specs = rq2.reconstruct_run(cell, seeds)
        vecs = rq2.per_circuit_posteriors(specs)
        topo = cell.factors.get("topology")
        if topo == "1house-N":
            single.extend(vecs)
        elif topo in ("bridge-federated", "directory-federated"):
            federated.extend(vecs)
        if topo == "bridge-federated":
            bridge_only.extend(vecs)
            xs, ys = rq2.rq2_p3_pairs(specs)
            conc.extend(xs)
            per_h.extend(ys)
    return federated, single, bridge_only, conc, per_h


# --------------------------------------------------------------------------- #
# Calibration sanity gate (§5 gate item 3) — independent of the confirmatory data.
# --------------------------------------------------------------------------- #
def calibration_gate(seeds=range(40)) -> Dict:
    linked = [bridge_correlation_auc(*synthetic_bridge_fixture(s, linked=True)) for s in seeds]
    unlinked = [bridge_correlation_auc(*synthetic_bridge_fixture(s, linked=False)) for s in seeds]
    lo = sum(linked) / len(linked)
    ul = sum(unlinked) / len(unlinked)
    ok = (lo >= 0.95) and (0.40 <= ul <= 0.60)
    return {"linked_mean_auc": lo, "unlinked_mean_auc": ul, "n_seeds": len(list(seeds)),
            "passes": ok, "criterion": "linked>=0.95 and 0.40<=unlinked<=0.60"}


# --------------------------------------------------------------------------- #
def run(data_dir: str) -> Dict:
    data = Path(data_dir)

    calib = calibration_gate()
    if not calib["passes"]:
        return {"calibration": calib, "ABORT": "correlator calibration failed — numbers NOT reported"}

    # ---- RQ1-P1 (leak): bridge-on AUC, gate = CI excludes 0.5 (frozen). --------
    p1_pairs = confirm_load.collect_rq1_p1_pairs(data)
    ci, p1_thetas = _bootstrap_auc_ci(p1_pairs, seed=ANALYSIS_SEED,
                                      n_resamples=N_RESAMPLES, alpha=ALPHA)
    if ci.excludes(0.5) and ci.strictly_greater(0.5):
        d1, l1 = "leak", ("material" if ci.lo >= confirm.MATERIALITY_FLOOR else "weak-but-real")
    elif ci.strictly_less(0.5):
        d1, l1 = "anomaly-below-chance", ""
    else:
        d1, l1 = "null", ""
    # bootstrap p vs 0.5 from the SAME resample distribution (order-invariant count).
    p1 = confirm.ConfirmTest("RQ1-P1", "AUC", ci, d1, l1,
                             S.two_sided_bootstrap_p(p1_thetas, 0.5))

    # ---- RQ1-P2 (padding efficacy): run_index-paired ΔAUC. ---------------------
    # Same intractability as RQ1-P1 (each resample pools ~75k pairs through the
    # O(n^2) frozen auc twice); CI via the performance-faithful bootstrap that
    # reproduces stats.bootstrap_ci(units, _delta_auc, bca) bit-for-bit. The frozen
    # decision + p-ordering are replicated unchanged.
    paired = confirm_load.collect_rq1_p2_paired(data)
    p2_ci, p2_thetas = _bootstrap_delta_auc_ci(paired, seed=ANALYSIS_SEED,
                                               n_resamples=N_RESAMPLES, alpha=ALPHA)
    p2_decision = "padding-effective" if p2_ci.strictly_greater(0.0) else "padding-ineffective"
    p2 = confirm.ConfirmTest("RQ1-P2", "ΔAUC", p2_ci, p2_decision, "",
                             S.two_sided_bootstrap_p(p2_thetas, 0.0))
    p2_delta = confirm_load.per_run_delta_aucs(paired)

    # ---- RQ2 arms (ratified per-circuit posterior). ---------------------------
    federated, single, bridge_only, conc, per_h = collect_rq2_arms(data)
    p1h = confirm.rq2_p1_delta_h(federated, single, seed=ANALYSIS_SEED,
                                 n_resamples=N_RESAMPLES, alpha=ALPHA)
    p3 = confirm.rq2_p3_funnel(conc, per_h, seed=ANALYSIS_SEED,
                               n_resamples=N_RESAMPLES, alpha=ALPHA)

    # EXPLORATORY: bridge-federated-only ΔH (the directive's narrower contrast).
    exp_bridge = confirm.rq2_p1_delta_h(bridge_only, single, seed=ANALYSIS_SEED,
                                        n_resamples=N_RESAMPLES, alpha=ALPHA)

    tests = [p1, p2, p1h, p3]
    holm = confirm.apply_holm(tests)
    holm_by = {h.name: h for h in holm}

    def test_row(t: confirm.ConfirmTest) -> Dict:
        h = holm_by[t.name]
        return {**t.as_dict(),
                "raw_p": t.p_for_holm, "holm_p": h.p_adjusted,
                "holm_multiplier": h.multiplier, "holm_rank": h.rank,
                "holm_reject": h.reject, "label_type": "CONFIRMATORY"}

    return {
        "meta": {
            "data_dir": str(data), "analysis_seed": ANALYSIS_SEED,
            "n_resamples": N_RESAMPLES, "alpha": ALPHA,
            "frozen_prereg_sha256": "f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b",
            "holm_family": list(confirm.FROZEN_FAMILY), "holm_family_size": confirm.FROZEN_FAMILY_SIZE,
            "reported": list(confirm.LEAD_PAPER_TESTS),
        },
        "calibration": calib,
        "n": {
            "rq1_p1_pairs": len(p1_pairs),
            "rq1_p1_linked": int(sum(1 for _, l in p1_pairs if l)),
            "rq1_p2_paired_runs": len(paired),
            "rq2_federated_circuits": len(federated),
            "rq2_single_house_circuits": len(single),
            "rq2_bridge_federated_circuits": len(bridge_only),
            "rq2_p3_points": len(conc),
        },
        "confirmatory": {
            "RQ1-P1": {**test_row(p1),
                       "method_note": ("pooled pair-set BCa jackknife is O(n^2)-intractable at "
                                       "n=%d; CI via performance-faithful bootstrap reproducing "
                                       "stats.bootstrap_ci bit-for-bit (verified on subsample). "
                                       "Point estimate + gate unchanged." % len(p1_pairs))},
            "RQ1-P2": {**test_row(p2), "per_run_delta_aucs": p2_delta,
                       "method_note": ("paired ΔAUC over run-index units; each resample pools "
                                       "~75k pairs through the O(n^2) frozen auc twice, so the CI "
                                       "uses the performance-faithful bootstrap reproducing "
                                       "stats.bootstrap_ci(units, _delta_auc, bca) bit-for-bit "
                                       "(verified). Decision + gate unchanged.")},
            "RQ2-P1": test_row(p1h),
            "RQ2-P3": {**test_row(p3),
                       "instrument_caveat": ("bridge-federated assigns a fresh bridge per circuit "
                                             "seed; willing-bridge reuse is minimal so the P3 "
                                             "concentration distribution may be near-degenerate "
                                             "(an honest as-instrumented property).")},
        },
        "exploratory": {
            "RQ2-P1-bridge-federated-only": {**exp_bridge.as_dict(),
                "label_type": "EXPLORATORY",
                "note": "ΔH(bridge-federated) − H(1house-N); narrower than the confirmatory "
                        "federated-pooled arm; not Holm-corrected; reported for transparency."},
        },
    }


def _verify():
    """Assert _bootstrap_auc_ci reproduces stats.bootstrap_ci bit-for-bit on a
    subsample, and _fast_auc == frozen auc."""
    # _fast_auc must equal the frozen detector, INCLUDING heavy-tie inputs (the
    # vectorised average-rank tie correction path).
    trng = random.Random(7)
    for _ in range(200):
        pv = np.array([trng.randrange(5) for _ in range(trng.randint(1, 12))], float)
        nv = np.array([trng.randrange(5) for _ in range(trng.randint(1, 12))], float)
        assert abs(_fast_auc(pv, nv) - frozen_auc(list(pv), list(nv))) < 1e-12, (pv, nv)

    rng = random.Random(1)
    pairs = [(rng.random(), (i % 25 == 0)) for i in range(2000)]  # ~80 linked
    from cmd_chat.sor.analysis.confirm import _auc_of_pairs
    fast, _fast_thetas = _bootstrap_auc_ci(pairs, seed=123, n_resamples=300, alpha=0.05)
    frozen, _ = S.bootstrap_ci(list(pairs), _auc_of_pairs, n_resamples=300, alpha=0.05,
                               seed=123, method="bca", return_dist=True)
    assert abs(fast.point - frozen.point) < 1e-12, (fast.point, frozen.point)
    assert abs(fast.lo - frozen.lo) < 1e-12, (fast.lo, frozen.lo)
    assert abs(fast.hi - frozen.hi) < 1e-12, (fast.hi, frozen.hi)
    assert fast.method == frozen.method, (fast.method, frozen.method)
    print("VERIFY OK: fast RQ1-P1 bootstrap == frozen stats.bootstrap_ci "
          f"(point={fast.point:.6f} ci=[{fast.lo:.6f},{fast.hi:.6f}] method={fast.method})")

    # RQ1-P2 fast ΔAUC bootstrap == frozen bootstrap_ci(units, _delta_auc, bca).
    urng = random.Random(9)

    def _mk_unit():
        npd = tuple((urng.random(), (urng.random() < 0.4)) for _ in range(urng.randint(6, 20)))
        pad = tuple((urng.random(), (urng.random() < 0.4)) for _ in range(urng.randint(6, 20)))
        return confirm.PairedCircuit(npd, pad)

    units = [_mk_unit() for _ in range(8)]
    fast2, _t2 = _bootstrap_delta_auc_ci(units, seed=123, n_resamples=300, alpha=0.05)
    frozen2, _ = S.bootstrap_ci(list(units), confirm._delta_auc, n_resamples=300, alpha=0.05,
                                seed=123, method="bca", return_dist=True)
    assert abs(fast2.point - frozen2.point) < 1e-12, (fast2.point, frozen2.point)
    assert abs(fast2.lo - frozen2.lo) < 1e-12, (fast2.lo, frozen2.lo)
    assert abs(fast2.hi - frozen2.hi) < 1e-12, (fast2.hi, frozen2.hi)
    assert fast2.method == frozen2.method, (fast2.method, frozen2.method)
    print("VERIFY OK: fast RQ1-P2 ΔAUC bootstrap == frozen stats.bootstrap_ci "
          f"(point={fast2.point:.6f} ci=[{fast2.lo:.6f},{fast2.hi:.6f}] method={fast2.method})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        _verify()
        return
    res = run(args.data_dir)
    text = json.dumps(res, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote", args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
