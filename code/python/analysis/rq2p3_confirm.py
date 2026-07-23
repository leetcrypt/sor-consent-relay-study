"""RQ2-P3′ confirmatory battery — OFFLINE + DETERMINISTIC (frozen prereg
`docs/rq2p3-mechanism-prereg.md`, FROZEN 2026-07-21, SHA in the sidecar
`rq2p3-mechanism-prereg.sha256`).

Why this can run offline. RQ2-P3′ measures **no live-only DV** — the per-circuit
anonymity-set entropy ``H_i`` is analytic (Miller–Madow over the observation-
consistent posterior) and the willing-bridge assignment is a **deterministic**
function of the circuit seed (``assembler.assemble`` under the
``bridge-federated-pool`` branch). Every circuit is recomputable from its seed with
no engine, no traffic, no grid — the SAME offline reconstruction path
``confirm_load_rq2`` uses for the lead RQ2. There is nothing to fabricate: unlike
RQ1's pcap-timing AUC or RQ3's added-latency, the RQ2-P3 DVs are not measured from a
running circuit. Containment is therefore satisfied by construction (no forwarder
ever runs); budget is $0.

Seeds (frozen §6). Per-run seed = ``derive_seed(cell_id, run_index)`` =
``SHA256(S0=20260719 ‖ cell_id ‖ run_index)``; per-circuit seed = the confirmatory
executor's real rule ``executor._circuit_seed(run_seed, c)`` =
``SHA256("sor-circuit|{run_seed}|{c}")`` — reused verbatim so these offline circuits
are byte-identical to the ones a live executor would persist as ``per_circuit_seeds``.

Design (frozen §4). The 9 sweep cells ``B ∈ {2,4,8} × alpha ∈ {0, 1.0, 2.0}`` at
``R = 30`` runs × ``C = 50`` circuits. The ``B=50, alpha=0`` calibration anchor from
``enumerate_rq2p3_cells()`` is NOT a confirmatory cell (§4: exactly 9) and is excluded
here.

Analysis (frozen §8, two-sided / direction-agnostic; effect + BCa 95% CI, never a bare
p; 10,000 resamples; α = 0.05):
  * **H1 (pooled Spearman ρ, run-level cluster bootstrap).** ρ between per-circuit
    top-3 concentration ``c_i`` and entropy ``H_i`` over all bridged circuits, with the
    **run** as the resampling unit (resample whole runs, pool their circuits) — circuits
    sharing a bridge are pseudo-replicates, so per-circuit resampling would falsely
    narrow the CI (§8). Funnel iff CI < 0, mix iff CI > 0, inconclusive iff it spans 0.
  * **H2 (dose-response OLS slope, run-level cluster bootstrap).** Slope β of per-run
    mean-H on per-run mean top-3 concentration over the 270 per-run points, resampling
    whole runs. Funnel iff slope CI < 0, mix iff > 0.
  * **H3 (joint).** RESOLVED iff H1 and H2 agree in sign AND both exclude 0.
  * **Multiplicity.** Holm–Bonferroni over THIS study's own family {H1-pooled,
    H2-slope} (family_size = 2). The lead study's family-of-7 is closed and not reopened.

Frozen instruments reused UNCHANGED (§3): ``stats.bootstrap_ci`` (BCa),
``stats.spearman``, ``stats.holm_bonferroni``, ``confirm_load_rq2.bridge_concentration``
/``per_circuit_entropy``/``top_k_bridge_concentration``, ``assembler.assemble``,
``executor._circuit_seed``. The only new code is this harness (seed enumeration, the
run-as-unit grouping, and an OLS-slope helper) — no detector is re-fit.

Honest-disclosure (mandatory, §7 scope note). The §7 dry calibration pass already
PREVIEWED a mix (ρ 0→+0.838 across the sweep); this confirmatory battery **quantifies**
an effect already visible at calibration. The pre-commitment stays **two-sided**; if the
data show a mix (ρ > 0) that plainly **qualifies/corrects** the lead RQ2-P1 "shrink"
headline as a unique-bridge artifact — that correction IS the finding, reported openly.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from cmd_chat.sor.analysis.confirm_load_rq2 import (
    bridge_concentration,
    per_circuit_entropy,
    top_k_bridge_concentration,
)
from cmd_chat.sor.analysis.stats import (
    DEFAULT_ALPHA,
    DEFAULT_RESAMPLES,
    bootstrap_ci,
    holm_bonferroni,
    spearman,
    two_sided_bootstrap_p,
)
from cmd_chat.sor.assembler import assemble
from cmd_chat.sor.battery import (
    C_CIRCUITS,
    R_RUNS,
    S0,
    derive_seed,
    enumerate_rq2p3_cells,
)
from cmd_chat.sor.executor import _circuit_seed

# A run's pooled per-circuit measurements: parallel (c_i, H_i) over its bridged
# circuits — the cluster unit for the H1 run-level bootstrap.
RunPairs = List[Tuple[float, float]]

# A single per-run dose-response point (mean top-3 concentration, mean H) — the unit
# for the H2 slope bootstrap.
RunPoint = Tuple[float, float]


def confirmatory_cells():
    """The 9 frozen §4 sweep cells (B ∈ {2,4,8} × alpha ∈ {0,1,2}). The B=50 anchor
    in ``enumerate_rq2p3_cells()`` is a calibration anchor (§7 gate item 1), NOT a
    confirmatory cell, and is excluded."""
    return [c for c in enumerate_rq2p3_cells() if int(c.factors["pool_B"]) in (2, 4, 8)]


def _assemble_run(cell, run_index: int, c: int = C_CIRCUITS,
                  *, engine: str = "docker", hops: int = 3):
    """Reconstruct one run's C circuit specs OFFLINE from the frozen seeds. Persists
    nothing itself; the caller records ``per_circuit_seeds`` for the immutable seal."""
    run_seed = derive_seed(cell.cell_id, run_index)
    seeds = [_circuit_seed(run_seed, c_ix) for c_ix in range(c)]
    specs = [assemble(cell, s, engine=engine, hops=hops) for s in seeds]
    return run_seed, seeds, specs


def _run_pairs(specs) -> RunPairs:
    """Parallel (c_i, H_i) over the run's bridged circuits (all circuits are bridged
    in the pool topology; a None-concentration circuit — none here — is dropped)."""
    conc = bridge_concentration(specs)
    ent = per_circuit_entropy(specs)
    return [(c, h) for c, h in zip(conc, ent) if c is not None]


def _pooled_spearman(runs: Sequence[RunPairs]) -> float:
    """Spearman ρ over the circuits of ALL runs in the (possibly resampled) cluster
    sample — the run-level cluster-bootstrap statistic for H1."""
    xs: List[float] = []
    ys: List[float] = []
    for run in runs:
        for c, h in run:
            xs.append(c)
            ys.append(h)
    return spearman(xs, ys)


def _ols_slope(points: Sequence[RunPoint]) -> float:
    """OLS slope β of y on x = cov(x,y)/var(x) over the per-run points (H2). Harness
    grouping only — the frozen instruments are untouched. Zero-variance x → 0.0."""
    n = len(points)
    if n < 2:
        return 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx == 0.0:
        return 0.0
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    return sxy / sxx


@dataclass(frozen=True)
class CellRecord:
    cell_id: str
    B: int
    alpha: float
    n_runs: int
    n_bridged_circuits: int
    mean_top3_concentration: float
    mean_entropy_bits: float
    exploratory_pooled_spearman: float  # EXPLORATORY per-cell ρ (§8)


def collect(r: int = R_RUNS, c: int = C_CIRCUITS) -> Dict:
    """Reconstruct the full 9×R×C battery offline and return the immutable record:
    per-cell summaries, the pooled (run-clustered) H1 pairs, the 270 H2 per-run
    points, and the per-run seed provenance (for the seal)."""
    cells = confirmatory_cells()
    per_cell: List[CellRecord] = []
    h1_runs: List[RunPairs] = []         # one RunPairs per (cell, run) — H1 cluster units
    h2_points: List[RunPoint] = []       # 9*R per-run (mean_conc, mean_H) points — H2 units
    seed_manifest: List[Dict] = []
    for cell in cells:
        b = int(cell.factors["pool_B"])
        alpha = float(cell.factors["pool_alpha"])
        cell_runs: List[RunPairs] = []
        cell_top3: List[float] = []
        cell_meanh: List[float] = []
        cell_bridged = 0
        for ri in range(r):
            run_seed, seeds, specs = _assemble_run(cell, ri, c)
            pairs = _run_pairs(specs)
            cell_runs.append(pairs)
            cell_bridged += len(pairs)
            top3 = top_k_bridge_concentration(specs, k=3)
            mean_h = statistics.fmean(h for _, h in pairs) if pairs else 0.0
            cell_top3.append(top3)
            cell_meanh.append(mean_h)
            h2_points.append((top3, mean_h))
            seed_manifest.append({
                "cell_id": cell.cell_id, "run_index": ri, "run_seed": run_seed,
                "per_circuit_seeds": seeds,
            })
        h1_runs.extend(cell_runs)
        per_cell.append(CellRecord(
            cell_id=cell.cell_id, B=b, alpha=alpha, n_runs=r,
            n_bridged_circuits=cell_bridged,
            mean_top3_concentration=statistics.fmean(cell_top3),
            mean_entropy_bits=statistics.fmean(cell_meanh),
            exploratory_pooled_spearman=_pooled_spearman(cell_runs),
        ))
    return {
        "cells": per_cell,
        "h1_runs": h1_runs,
        "h2_points": h2_points,
        "seed_manifest": seed_manifest,
        "n_pooled_bridged_circuits": sum(len(run) for run in h1_runs),
    }


def _boot_seed(tag: str) -> int:
    """Deterministic bootstrap seed derived from the frozen base seed S0 so the CIs
    are reproducible (the §8 seed spot-check is mechanical)."""
    return int.from_bytes(hashlib.sha256(f"rq2p3-confirm|{tag}|{S0}".encode()).digest()[:8], "big")


def analyze(collected: Dict, *, n_resamples: int = DEFAULT_RESAMPLES,
            alpha: float = DEFAULT_ALPHA) -> Dict:
    """Run the frozen §8 H1/H2/H3 analysis on the collected battery. Effect + BCa
    95% CI for both; run-level cluster bootstrap; Holm over {H1-pooled, H2-slope}."""
    h1_runs: List[RunPairs] = collected["h1_runs"]
    h2_points: List[RunPoint] = collected["h2_points"]

    # H1 — pooled Spearman ρ, resampling whole RUNS (cluster unit), BCa CI.
    h1_ci, h1_dist = bootstrap_ci(
        h1_runs, _pooled_spearman, n_resamples=n_resamples, alpha=alpha,
        seed=_boot_seed("H1-pooled"), method="bca", return_dist=True,
    )
    h1_p = two_sided_bootstrap_p(h1_dist, 0.0)
    h1_decision = ("funnel" if h1_ci.strictly_less(0.0)
                   else "mix" if h1_ci.strictly_greater(0.0)
                   else "inconclusive")

    # H2 — OLS dose-response slope over the 270 per-run points, resampling whole RUNS.
    h2_ci, h2_dist = bootstrap_ci(
        h2_points, _ols_slope, n_resamples=n_resamples, alpha=alpha,
        seed=_boot_seed("H2-slope"), method="bca", return_dist=True,
    )
    h2_p = two_sided_bootstrap_p(h2_dist, 0.0)
    h2_decision = ("funnel" if h2_ci.strictly_less(0.0)
                   else "mix" if h2_ci.strictly_greater(0.0)
                   else "inconclusive")

    # H3 — joint: RESOLVED iff H1 and H2 agree in sign AND both exclude 0.
    both_exclude = h1_ci.excludes(0.0) and h2_ci.excludes(0.0)
    same_sign = (h1_ci.point > 0) == (h2_ci.point > 0)
    h3_resolved = bool(both_exclude and same_sign)
    h3_finding = (h1_decision if h3_resolved else "unresolved")

    # Multiplicity — Holm over THIS study's own family {H1-pooled, H2-slope}, size 2.
    holm = holm_bonferroni({"H1-pooled": h1_p, "H2-slope": h2_p},
                           alpha=alpha, family_size=2)

    return {
        "H1_pooled_spearman": {
            "effect": "spearman_rho", "decision": h1_decision,
            "p_for_holm": h1_p, **h1_ci.as_dict(),
        },
        "H2_dose_response_slope": {
            "effect": "ols_slope_H_on_conc", "decision": h2_decision,
            "n_points": len(h2_points), "p_for_holm": h2_p, **h2_ci.as_dict(),
        },
        "H3_joint": {
            "resolved": h3_resolved, "finding": h3_finding,
            "both_exclude_zero": both_exclude, "agree_in_sign": same_sign,
        },
        "holm_own_family": [
            {"name": h.name, "p": h.p, "p_adjusted": h.p_adjusted,
             "reject": h.reject, "rank": h.rank, "multiplier": h.multiplier}
            for h in holm
        ],
    }


def run_confirmatory(r: int = R_RUNS, c: int = C_CIRCUITS,
                     *, n_resamples: int = DEFAULT_RESAMPLES,
                     alpha: float = DEFAULT_ALPHA) -> Dict:
    """The full offline RQ2-P3′ confirmatory report: collect → analyze → assemble the
    sealed record (with per-run seed provenance and the honest-disclosure note)."""
    collected = collect(r, c)
    results = analyze(collected, n_resamples=n_resamples, alpha=alpha)
    cells = collected["cells"]
    return {
        "schema": "sor-rq2p3-confirmatory/1",
        "prereg": "docs/rq2p3-mechanism-prereg.md",
        "prereg_frozen": "2026-07-21",
        "prereg_sha256_sidecar": "docs/rq2p3-mechanism-prereg.sha256",
        "offline_deterministic": True,
        "no_engine_no_traffic_no_grid": True,
        "base_seed_S0": S0,
        "R": r, "C": c, "n_cells": len(cells),
        "n_pooled_bridged_circuits": collected["n_pooled_bridged_circuits"],
        "n_resamples": n_resamples, "alpha": alpha,
        "sweep": [
            {"cell_id": cr.cell_id, "B": cr.B, "alpha": cr.alpha,
             "n_runs": cr.n_runs, "n_bridged_circuits": cr.n_bridged_circuits,
             "mean_top3_concentration": cr.mean_top3_concentration,
             "mean_entropy_bits": cr.mean_entropy_bits,
             "exploratory_pooled_spearman": cr.exploratory_pooled_spearman}
            for cr in cells
        ],
        "results": results,
        "seed_manifest": collected["seed_manifest"],
        "honest_disclosure": (
            "The §7 dry calibration pass already PREVIEWED a mix (rho 0->+0.838 across "
            "the sweep); this confirmatory battery QUANTIFIES an effect already visible "
            "at calibration. The pre-commitment stays two-sided. A mix (rho>0) qualifies/"
            "corrects the lead RQ2-P1 'shrink' headline as a unique-bridge artifact — "
            "that correction IS the finding, reported openly. The lead RQ2-P1 result is "
            "NOT re-litigated; any pool DeltaH is EXPLORATORY (prereg §1)."
        ),
    }


def _seal(out_dir: Path, report: Dict) -> Dict[str, str]:
    """Write the immutable results + a SHA256SUMS over them. ``output/`` is gitignored;
    the caller force-adds the anchors so the sealed raw record enters the commit."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "rq2p3-confirmatory-results.json"
    results_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    sums: Dict[str, str] = {}
    for p in sorted(out_dir.glob("*.json")):
        sums[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    sums_path = out_dir / "SHA256SUMS"
    sums_path.write_text(
        "".join(f"{h}  {name}\n" for name, h in sorted(sums.items())), encoding="utf-8")
    return {"results": str(results_path), "sha256sums": str(sums_path), **sums}


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m cmd_chat.sor.analysis.rq2p3_confirm",
        description="RQ2-P3' confirmatory battery — OFFLINE + DETERMINISTIC (frozen prereg).",
    )
    ap.add_argument("--out", default="output/sor-rq2p3-confirmatory",
                    help="immutable seal dir (gitignored; force-add the anchors)")
    ap.add_argument("--r-runs", type=int, default=R_RUNS)
    ap.add_argument("--c-circuits", type=int, default=C_CIRCUITS)
    ap.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    args = ap.parse_args(argv)

    report = run_confirmatory(args.r_runs, args.c_circuits, n_resamples=args.resamples)
    sealed = _seal(Path(args.out), report)

    h1 = report["results"]["H1_pooled_spearman"]
    h2 = report["results"]["H2_dose_response_slope"]
    h3 = report["results"]["H3_joint"]
    print(f"[RQ2-P3'] OFFLINE confirmatory — {report['n_cells']} cells x R={report['R']} "
          f"x C={report['C']} = {report['n_pooled_bridged_circuits']} bridged circuits")
    print(f"[H1] pooled Spearman rho = {h1['point']:+.4f}  "
          f"95% BCa CI [{h1['ci_lo']:+.4f}, {h1['ci_hi']:+.4f}]  "
          f"({h1['method']})  -> {h1['decision']}")
    print(f"[H2] OLS slope H~conc   = {h2['point']:+.4f}  "
          f"95% BCa CI [{h2['ci_lo']:+.4f}, {h2['ci_hi']:+.4f}]  "
          f"({h2['method']}, n={h2['n_points']})  -> {h2['decision']}")
    print(f"[H3] joint -> resolved={h3['resolved']} finding={h3['finding']}")
    print("[Holm own-family {H1-pooled,H2-slope}] " + ", ".join(
        f"{h['name']}:p_adj={h['p_adjusted']:.4g}({'reject' if h['reject'] else 'retain'})"
        for h in report["results"]["holm_own_family"]))
    print(f"[seal] {sealed['results']}")
    print(f"[seal] {sealed['sha256sums']}")
    print("[disclosure] " + report["honest_disclosure"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
